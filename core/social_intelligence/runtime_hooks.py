"""Runtime hooks for Social Intelligence Layer (SIL) observation.

This module provides integration points between the core runtime and the
Social Intelligence Layer, enabling observation capture and social event
emission without breaking existing runtime behavior.

All hooks are opt-in via configuration and respect CONVERSATION_MODE_ENABLED.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, Any, Callable

from core.social_intelligence.pipeline import (
    ObservationPipeline,
    SimpleOpportunityDetector,
    SimpleSentimentExtractor,
    SimpleVibeAnalyzer,
)
from core.social_intelligence.types import SocialContext, SocialEvent

if TYPE_CHECKING:
    from core.runtime import GestaltRuntime, RuntimeSessionState
    from core.schemas import Event, Response

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SILHookConfig:
    """Configuration for SIL runtime hooks.

    All settings are opt-in with safe defaults that minimize overhead.
    """

    enabled: bool = False
    respect_conversation_mode: bool = True
    max_latency_ms: float = 5.0
    emit_vibe_events: bool = True
    emit_user_pattern_events: bool = True
    capture_signals: bool = True

    @classmethod
    def from_env(cls) -> SILHookConfig:
        """Create config from environment variables.

        Environment variables:
            SIL_ENABLED: Enable SIL hooks (default: false)
            SIL_RESPECT_CONVERSATION_MODE: Respect CONVERSATION_MODE_ENABLED (default: true)
            SIL_MAX_LATENCY_MS: Maximum allowed latency overhead (default: 5.0)
            SIL_EMIT_VIBE_EVENTS: Emit vibe detection events (default: true)
            SIL_EMIT_USER_PATTERNS: Emit user pattern events (default: true)
            SIL_CAPTURE_SIGNALS: Capture social signals (default: true)
        """
        return cls(
            enabled=os.getenv("SIL_ENABLED", "false").lower() in ("true", "1", "yes"),
            respect_conversation_mode=os.getenv(
                "SIL_RESPECT_CONVERSATION_MODE", "true"
            ).lower()
            in ("true", "1", "yes"),
            max_latency_ms=float(os.getenv("SIL_MAX_LATENCY_MS", "5.0")),
            emit_vibe_events=os.getenv("SIL_EMIT_VIBE_EVENTS", "true").lower()
            in ("true", "1", "yes"),
            emit_user_pattern_events=os.getenv("SIL_EMIT_USER_PATTERNS", "true").lower()
            in ("true", "1", "yes"),
            capture_signals=os.getenv("SIL_CAPTURE_SIGNALS", "true").lower()
            in ("true", "1", "yes"),
        )


@dataclass(slots=True)
class SILObservationResult:
    """Result of SIL observation processing.

    Contains captured social context and timing information for monitoring.
    """

    social_context: SocialContext | None = None
    latency_ms: float = 0.0
    signals_extracted: int = 0
    opportunities_detected: int = 0
    error: str | None = None


class SILRuntimeHooks:
    """Runtime hooks for SIL observation integration.

    This class provides non-breaking injection points into the runtime
    message processing flow for social intelligence observation capture.

    Usage:
        hooks = SILRuntimeHooks.from_env()
        if hooks.should_observe():
            result = await hooks.observe_incoming_event(event, session)
            # result.social_context contains captured social signals
    """

    def __init__(self, config: SILHookConfig | None = None) -> None:
        """Initialize SIL runtime hooks.

        Args:
            config: SIL configuration. If None, uses environment defaults.
        """
        self.config = config or SILHookConfig.from_env()
        self._pipeline: ObservationPipeline | None = None
        self._event_handlers: list[Callable[[SocialEvent], Any]] = []
        self._context_cache: dict[str, SocialContext] = {}
        self._cache_size_limit = 100

        if self.config.enabled and self.config.capture_signals:
            self._initialize_pipeline()

    def _initialize_pipeline(self) -> None:
        """Initialize the observation pipeline with default extractors."""
        try:
            extractors = []
            if self.config.capture_signals:
                extractors.append(SimpleSentimentExtractor())

            vibe_analyzer = (
                SimpleVibeAnalyzer() if self.config.emit_vibe_events else None
            )
            detectors = []
            if self.config.emit_user_pattern_events:
                detectors.append(SimpleOpportunityDetector())

            self._pipeline = ObservationPipeline(
                signal_extractors=extractors,
                vibe_analyzer=vibe_analyzer,
                opportunity_detectors=detectors,
                max_signals_per_context=10,
            )
            logger.debug("SIL observation pipeline initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize SIL pipeline: {e}")
            self._pipeline = None

    @classmethod
    def from_env(cls) -> SILRuntimeHooks:
        """Create hooks instance from environment configuration."""
        return cls(SILHookConfig.from_env())

    def should_observe(self) -> bool:
        """Check if observation should be performed.

        Returns True only if:
        1. SIL is enabled in config
        2. Pipeline is initialized successfully
        3. CONVERSATION_MODE_ENABLED is respected (if configured)
        """
        if not self.config.enabled:
            return False

        if self._pipeline is None:
            return False

        if self.config.respect_conversation_mode:
            # Check CONVERSATION_MODE_ENABLED from config module
            try:
                from config import Config

                conversation_mode = getattr(Config, "CONVERSATION_MODE_ENABLED", False)
                if not conversation_mode:
                    return False
            except ImportError:
                logger.debug(
                    "Could not import Config, skipping conversation mode check"
                )

        return True

    async def observe_incoming_event(
        self,
        event: Event,
        session: RuntimeSessionState | None = None,
    ) -> SILObservationResult:
        """Observe an incoming event and extract social context.

        This is the main entry point for SIL observation. It converts the
        runtime Event to a SocialEvent and processes it through the
        observation pipeline.

        Args:
            event: The runtime event to observe
            session: Optional session state for context enrichment

        Returns:
            SILObservationResult containing social context and timing data
        """
        start_time = perf_counter()
        result = SILObservationResult()

        if not self.should_observe():
            return result

        try:
            # Convert runtime event to social event
            social_event = self._create_social_event(event)

            # Get existing context for this session/channel
            existing_context = None
            if session:
                cache_key = f"{session.session_id}:{event.room_id or 'default'}"
                existing_context = self._context_cache.get(cache_key)

            # Process through observation pipeline
            social_context = await self._pipeline.process_event(
                social_event, existing_context
            )

            # Cache the context for future events
            if session:
                cache_key = f"{session.session_id}:{event.room_id or 'default'}"
                self._context_cache[cache_key] = social_context
                self._prune_cache_if_needed()

            # Emit social events for downstream processing
            await self._emit_social_events(social_event, social_context)

            # Populate result
            result.social_context = social_context
            result.signals_extracted = len(social_context.recent_signals)
            result.opportunities_detected = len(social_context.engagement_opportunities)

        except Exception as e:
            logger.warning(f"SIL observation failed: {e}")
            result.error = str(e)

        finally:
            elapsed_ms = (perf_counter() - start_time) * 1000
            result.latency_ms = elapsed_ms

            # Log if latency exceeds threshold
            if elapsed_ms > self.config.max_latency_ms:
                logger.warning(
                    f"SIL observation exceeded latency threshold: {elapsed_ms:.2f}ms "
                    f"(max: {self.config.max_latency_ms}ms)"
                )

        return result

    async def observe_outgoing_response(
        self,
        event: Event,
        response: Response,
        session: RuntimeSessionState | None = None,
        social_context: SocialContext | None = None,
    ) -> SILObservationResult:
        """Observe an outgoing response for social signal capture.

        Captures the persona's response for pattern learning and context updates.

        Args:
            event: The original runtime event
            response: The response being sent
            session: Optional session state
            social_context: Optional social context from incoming observation

        Returns:
            SILObservationResult with updated context
        """
        start_time = perf_counter()
        result = SILObservationResult()

        if not self.should_observe():
            return result

        try:
            # Create response social event
            response_event = SocialEvent(
                source_event_id=event.event_id,
                event_type="persona_response",
                user_id=response.persona_id,
                channel_id=event.room_id or "",
                raw_content=response.text,
                metadata={
                    "tool_calls": [tc.name for tc in response.tool_calls],
                    "platform": event.platform,
                },
            )

            # Get existing context or use provided
            existing_context = social_context
            if not existing_context and session:
                cache_key = f"{session.session_id}:{event.room_id or 'default'}"
                existing_context = self._context_cache.get(cache_key)

            # Process response through pipeline
            if self._pipeline:
                updated_context = await self._pipeline.process_event(
                    response_event, existing_context
                )
                result.social_context = updated_context

                # Update cache
                if session:
                    cache_key = f"{session.session_id}:{event.room_id or 'default'}"
                    self._context_cache[cache_key] = updated_context

            await self._emit_social_events(response_event, result.social_context)

        except Exception as e:
            logger.warning(f"SIL response observation failed: {e}")
            result.error = str(e)

        finally:
            result.latency_ms = (perf_counter() - start_time) * 1000

        return result

    def _create_social_event(self, event: Event) -> SocialEvent:
        """Convert a runtime Event to a SocialEvent.

        Args:
            event: Runtime event to convert

        Returns:
            SocialEvent for pipeline processing
        """
        return SocialEvent(
            source_event_id=event.event_id,
            event_type=event.type,
            user_id=event.user_id,
            channel_id=event.room_id or "",
            timestamp=event.timestamp,
            raw_content=event.text,
            metadata={
                "platform": event.platform,
                "kind": event.kind,
                "session_id": event.session_id,
            },
        )

    async def _emit_social_events(
        self, social_event: SocialEvent, context: SocialContext | None
    ) -> None:
        """Emit social events for downstream processing.

        Currently calls registered event handlers. Future versions may
        use an event bus for decoupled processing.

        Args:
            social_event: The social event to emit
            context: Associated social context
        """
        if not context:
            return

        for handler in self._event_handlers:
            try:
                if hasattr(handler, "__call__"):
                    result = handler(social_event)
                    if hasattr(result, "__await__"):
                        await result
            except Exception as e:
                logger.warning(f"Social event handler failed: {e}")

    def register_event_handler(self, handler: Callable[[SocialEvent], Any]) -> None:
        """Register a handler for social events.

        Args:
            handler: Callable that receives SocialEvent instances
        """
        self._event_handlers.append(handler)
        logger.debug(f"Registered social event handler: {handler}")

    def unregister_event_handler(self, handler: Callable[[SocialEvent], Any]) -> None:
        """Unregister a social event handler.

        Args:
            handler: The handler to remove
        """
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
            logger.debug(f"Unregistered social event handler: {handler}")

    def _prune_cache_if_needed(self) -> None:
        """Prune context cache if it exceeds size limit."""
        if len(self._context_cache) > self._cache_size_limit:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self._context_cache.keys())[
                : len(self._context_cache) - self._cache_size_limit
            ]
            for key in keys_to_remove:
                del self._context_cache[key]
            logger.debug(f"Pruned {len(keys_to_remove)} entries from SIL context cache")

    def get_cached_context(
        self, session_id: str, room_id: str = "default"
    ) -> SocialContext | None:
        """Get cached social context for a session/room.

        Args:
            session_id: The session identifier
            room_id: The room/channel identifier

        Returns:
            Cached SocialContext or None
        """
        cache_key = f"{session_id}:{room_id}"
        return self._context_cache.get(cache_key)

    def clear_cache(self) -> None:
        """Clear the context cache."""
        self._context_cache.clear()
        logger.debug("SIL context cache cleared")


# Global hooks instance for singleton access
_global_hooks: SILRuntimeHooks | None = None


def get_sil_hooks() -> SILRuntimeHooks:
    """Get the global SIL hooks instance.

    Lazily initializes on first call. Safe to call multiple times.

    Returns:
        The global SILRuntimeHooks instance
    """
    global _global_hooks
    if _global_hooks is None:
        _global_hooks = SILRuntimeHooks.from_env()
    return _global_hooks


def reset_sil_hooks() -> None:
    """Reset the global hooks instance.

    Useful for testing and configuration reloading.
    """
    global _global_hooks
    _global_hooks = None
    logger.debug("SIL hooks reset")
