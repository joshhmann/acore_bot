"""Core adapter interfaces for the Acore Bot framework.

This module defines abstract base classes that all platform adapters must implement.
Adapters provide the bridge between the core bot logic and specific platforms
like Discord, CLI, or future platforms.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generic, List, TypeVar

from core.schemas import Event, EventKind, Response

logger = logging.getLogger(__name__)


@dataclass
class AcoreEvent:
    """Represents an event originating from any adapter.

    Attributes:
        type: The event type (e.g., "message", "command", "reaction").
        payload: Event-specific data as a dictionary.
        source_adapter: Identifier of the adapter that produced this event.
        timestamp: UTC datetime when the event was created.
    """

    type: str
    payload: dict
    source_adapter: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class PlatformFacts:
    """Normalized adapter facts passed into runtime event construction."""

    text: str
    user_id: str
    room_id: str
    message_id: str = ""
    is_direct_mention: bool = False
    is_reply_to_bot: bool = False
    is_persona_message: bool = False
    has_visual_context: bool = False
    author_is_bot: bool = False
    platform_flags: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RuntimeDecision:
    """Runtime-owned policy decision for adapter response behavior.

    This dataclass encapsulates the runtime's decision about whether and how
    an adapter should respond to a platform event.

    Attributes:
        should_respond: Whether the adapter should send a response.
        reason: Human-readable explanation for the decision.
        suggested_style: Optional style hint for response formatting.
        persona_id: The selected persona identifier for this response.
        session_id: The session identifier associated with this decision.
    """

    should_respond: bool
    reason: str
    suggested_style: str = ""
    persona_id: str = ""
    session_id: str = ""


@dataclass(slots=True)
class AdapterConfig:
    """Configuration for platform adapter capabilities.

    Defines the platform-specific features and constraints that the runtime
    should be aware of when interacting with this adapter.

    Attributes:
        platform_name: Identifier for the platform (e.g., "discord", "slack").
        supports_embeds: Whether the platform supports rich embeds.
        supports_threads: Whether the platform supports threaded conversations.
        supports_reactions: Whether the platform supports message reactions.
        max_message_length: Maximum allowed message length for this platform.
    """

    platform_name: str
    supports_embeds: bool = False
    supports_threads: bool = False
    supports_reactions: bool = False
    max_message_length: int = 2000


# Generic type variables for platform-native types
T = TypeVar("T")  # Platform-native event type (e.g., discord.Message)
R = TypeVar("R")  # Platform-native context type (e.g., discord.TextChannel)


class AdapterLifecycleContract(ABC, Generic[T, R]):
    """Abstract base class defining the four-phase adapter lifecycle contract.

    This contract formalizes the boundary between platform adapters and the
    runtime. Adapters extract facts from platform events, the runtime makes
    policy decisions, and adapters render responses back to the platform.

    Type Parameters:
        T: Platform-native event type (e.g., discord.Message)
        R: Platform-native context type (e.g., discord.TextChannel)

    The four-phase lifecycle:
        1. parse: Extract PlatformFacts from platform-native event
        2. to_runtime_event: Convert PlatformFacts to runtime Event
        3. from_runtime_response: Extract RuntimeDecision from runtime Response
        4. render: Send the response to the platform
    """

    def __init__(self, config: AdapterConfig) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Adapter configuration defining platform capabilities.
        """
        self.config = config

    @abstractmethod
    def parse(self, event: T) -> PlatformFacts:
        """Phase 1: Extract facts from platform-native event.

        Adapters must implement this to extract normalized facts from
        platform-specific events. This method should NOT make policy decisions.

        Args:
            event: Platform-native event object.

        Returns:
            Normalized PlatformFacts extracted from the event.
        """
        ...

    def to_runtime_event(
        self,
        facts: PlatformFacts,
        *,
        session_id: str | None = None,
        persona_id: str = "",
        mode: str = "",
        kind: str = "",
        extra_flags: dict[str, Any] | None = None,
    ) -> Event:
        """Phase 2: Build runtime Event from normalized facts.

        Creates a canonical runtime Event from the adapter-extracted facts.
        Override only if the platform requires custom event construction.

        Args:
            facts: Normalized platform facts from parse().
            session_id: Optional session identifier to associate with the event.
            persona_id: Optional persona identifier for this event.
            mode: Optional mode override for this event.
            kind: Optional event kind (e.g., 'chat', 'command', 'system').
            extra_flags: Optional additional flags to include in event metadata.

        Returns:
            Canonical runtime Event ready for runtime processing.
        """
        return build_runtime_event_from_facts(
            facts=facts,
            platform_name=self.config.platform_name,
            kind=kind or EventKind.CHAT.value,
            session_id=session_id or "",
            persona_id=persona_id,
            mode=mode,
            extra_flags=extra_flags,
        )

    def from_runtime_response(
        self,
        runtime_response: Response,
        original_facts: PlatformFacts,
    ) -> RuntimeDecision:
        """Phase 3: Extract runtime decision from Response.

        Transforms the runtime's response into a normalized decision that
        the adapter can use for rendering. The decision includes policy
        information like whether to respond and which persona to use.

        Args:
            runtime_response: The response returned by the runtime.
            original_facts: The original PlatformFacts that triggered this response.

        Returns:
            Normalized RuntimeDecision extracted from the response.
        """
        # Extract should_respond from metadata if present, default to True if has text
        metadata = runtime_response.metadata or {}
        should_respond = metadata.get("should_respond", bool(runtime_response.text))

        return RuntimeDecision(
            should_respond=bool(should_respond),
            reason=metadata.get("reason", "runtime_completed"),
            suggested_style=metadata.get("suggested_style", ""),
            persona_id=runtime_response.persona_id or metadata.get("persona_id", ""),
            session_id=metadata.get("session_id", ""),
        )

    @abstractmethod
    async def render(
        self,
        platform_context: R,
        decision: RuntimeDecision,
        runtime_response: Response,
    ) -> None:
        """Phase 4: Send runtime response to platform.

        Adapters must implement this to transport the runtime's response
        back to the platform. This method should only handle presentation,
        never override runtime decisions.

        Args:
            platform_context: Platform-native context for sending the response
                (e.g., a Discord channel object).
            decision: The runtime's policy decision about this response.
            runtime_response: The actual response content from the runtime.
        """
        ...


def build_runtime_event_from_facts(
    *,
    facts: PlatformFacts,
    platform_name: str,
    kind: str = EventKind.CHAT.value,
    session_id: str = "",
    persona_id: str = "",
    mode: str = "",
    extra_flags: dict[str, Any] | None = None,
) -> Event:
    """Build canonical runtime event from adapter-level normalized facts."""
    flags: dict[str, Any] = dict(facts.platform_flags)
    if extra_flags:
        flags.update(extra_flags)
    flags.setdefault("is_direct_mention", bool(facts.is_direct_mention))
    flags.setdefault("is_reply_to_bot", bool(facts.is_reply_to_bot))
    flags.setdefault("is_persona_message", bool(facts.is_persona_message))
    flags.setdefault("has_visual_context", bool(facts.has_visual_context))
    flags.setdefault("author_is_bot", bool(facts.author_is_bot))
    flags.setdefault("user_id", str(facts.user_id))
    if facts.raw_metadata:
        flags.setdefault("raw_metadata", dict(facts.raw_metadata))

    event_metadata: dict[str, Any] = {
        "persona_id": str(persona_id or ""),
        "mode": str(mode or ""),
        "flags": flags,
    }
    return Event(
        type=str(kind or EventKind.CHAT.value),
        kind=str(kind or EventKind.CHAT.value),
        text=str(facts.text or ""),
        user_id=str(facts.user_id or ""),
        room_id=str(facts.room_id or ""),
        message_id=str(facts.message_id or ""),
        platform=str(platform_name or "unknown"),
        session_id=str(session_id or ""),
        metadata=event_metadata,
    )


def runtime_flags_from_platform_facts(
    facts: PlatformFacts,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Extract runtime flags from PlatformFacts.

    Helper function that converts PlatformFacts into the standard flag
    dictionary format expected by the runtime. Useful for adapters that
    need to manually construct flags or extend the default flag set.

    Args:
        facts: The platform facts to convert to flags.
        extra: Optional additional flags to merge into the result.

    Returns:
        Dictionary of runtime flags extracted from facts.
    """
    flags: dict[str, Any] = {
        "is_direct_mention": facts.is_direct_mention,
        "is_reply_to_bot": facts.is_reply_to_bot,
        "is_persona_message": facts.is_persona_message,
        "has_visual_context": facts.has_visual_context,
        "author_is_bot": facts.author_is_bot,
        "user_id": facts.user_id,
    }
    if facts.platform_flags:
        flags.update(facts.platform_flags)
    if facts.raw_metadata:
        flags["raw_metadata"] = facts.raw_metadata
    if extra:
        flags.update(extra)
    return flags


class EventBus(ABC):
    """Abstract base class for the event bus.

    The event bus facilitates communication between adapters and the core
    bot by allowing publish/subscribe patterns for events.
    """

    @abstractmethod
    def emit(self, event_type: str, payload: dict) -> None:
        """Emit an event to all subscribers.

        Args:
            event_type: The type of event being emitted.
            payload: The event data as a dictionary.
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: The type of event to subscribe to.
            handler: A callable that will be invoked when events of this
                type are emitted.
        """
        pass

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Unsubscribe a handler from a specific event type.

        Args:
            event_type: The type of event to unsubscribe from.
            handler: The handler to remove from subscribers.
        """
        pass


class SimpleEventBus(EventBus):
    """Simple in-memory implementation of the EventBus interface."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable[..., Any]]] = {}

    def emit(self, event_type: str, payload: dict) -> None:
        """Emit an event to all subscribers."""
        if event_type not in self._handlers:
            return

        for handler in self._handlers[event_type]:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Subscribe a handler to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type} events")

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Unsubscribe a handler from a specific event type."""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler unsubscribed from {event_type} events")


class InputAdapter(ABC):
    """Abstract base class for input adapters.

    Input adapters listen for incoming events from a platform (e.g., Discord,
    CLI) and convert them into AcoreEvent objects that the bot can process.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start listening for input events.

        This method should establish any necessary connections and begin
        listening for events from the source platform.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening for input events.

        This method should gracefully shutdown any connections and stop
        listening for events.
        """
        pass

    @abstractmethod
    def on_event(self, callback: Callable[[AcoreEvent], None]) -> None:
        """Register a callback to handle incoming events.

        Args:
            callback: A function that will be called with each AcoreEvent
                received by this adapter.
        """
        pass


class OutputAdapter(ABC):
    """Abstract base class for output adapters.

    Output adapters send messages and content from the bot to a platform.
    They handle the platform-specific formatting and delivery mechanisms.
    """

    @abstractmethod
    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message to a channel.

        Args:
            channel_id: The identifier of the target channel.
            text: The message text to send.
            **options: Optional platform-specific send options.
        """
        pass

    @abstractmethod
    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content to a channel.

        Args:
            channel_id: The identifier of the target channel.
            embed: A dictionary representing the embed content. The structure
                is adapter-specific but typically includes fields like title,
                description, color, and fields.
        """
        pass
