"""Auto-summary pipeline for post-conversation summarization.

Provides automatic generation of memory entries after meaningful conversations.
Integrates with the memory manager for storage and triggers based on turn thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from memory.base import MemoryNamespace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummaryResult:
    """Result of a summary generation operation.

    Attributes:
        summary: The generated summary text
        confidence: Confidence score (0.0-1.0)
        key_points: Extracted key points from the conversation
        metadata: Additional metadata about the summary
    """

    summary: str
    confidence: float
    key_points: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if this summary meets minimum quality standards."""
        return bool(self.summary.strip()) and self.confidence > 0.5


class MemoryStore(Protocol):
    """Protocol for memory store interface."""

    async def get_short_term(
        self, namespace: MemoryNamespace, limit: int = 12
    ) -> list[dict[str, Any]]: ...

    async def get_long_term_summary(self, namespace: MemoryNamespace) -> str: ...

    async def set_long_term_summary(
        self, namespace: MemoryNamespace, summary: str
    ) -> None: ...

    async def get_state(self, namespace: MemoryNamespace) -> dict[str, Any]: ...

    async def set_state(
        self, namespace: MemoryNamespace, state: dict[str, Any]
    ) -> None: ...


class SummaryGenerator(Protocol):
    """Protocol for summary generator interface."""

    async def generate_summary(
        self, messages: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


@dataclass
class AutoSummaryPipeline:
    """Pipeline for automatically summarizing conversations.

    Triggers summary generation after conversation turn thresholds are met
    and stores results in the memory system.

    Attributes:
        memory_store: Storage backend for summaries and state
        summary_generator: LLM-based summary generator
        turn_threshold: Number of turns before triggering summary
        confidence_threshold: Minimum confidence to accept a summary
        min_messages: Minimum messages required to generate summary
    """

    memory_store: MemoryStore
    summary_generator: SummaryGenerator
    turn_threshold: int = 5
    confidence_threshold: float = 0.7
    min_messages: int = 3

    def __post_init__(self) -> None:
        """Initialize pipeline statistics."""
        self._stats: dict[str, int] = {
            "summaries_generated": 0,
            "summaries_stored": 0,
            "errors": 0,
            "skipped_too_short": 0,
            "skipped_low_confidence": 0,
        }

    async def should_trigger_summary(self, namespace: MemoryNamespace) -> bool:
        """Check if summary should be triggered for this namespace.

        Args:
            namespace: Memory namespace to check

        Returns:
            True if summary should be generated
        """
        try:
            state = await self.memory_store.get_state(namespace)
            turn_count = state.get("turn_count", 0)
            last_summary_turn = state.get("last_summary_turn", 0)
            turns_since_summary = turn_count - last_summary_turn

            return turns_since_summary >= self.turn_threshold

        except Exception as e:
            logger.error(f"Error checking summary trigger for {namespace}: {e}")
            return False

    async def generate_and_store_summary(
        self, namespace: MemoryNamespace
    ) -> SummaryResult | None:
        """Generate and store a summary for the namespace.

        Args:
            namespace: Memory namespace to summarize

        Returns:
            SummaryResult if successful, None otherwise
        """
        try:
            # Fetch recent messages
            messages = await self.memory_store.get_short_term(
                namespace, limit=self.turn_threshold * 2
            )

            if len(messages) < self.min_messages:
                logger.debug(
                    f"Too few messages for summary in {namespace}: {len(messages)}"
                )
                self._stats["skipped_too_short"] += 1
                return None

            # Generate summary
            result_data = await self.summary_generator.generate_summary(messages)
            self._stats["summaries_generated"] += 1

            result = SummaryResult(
                summary=result_data.get("summary", ""),
                confidence=result_data.get("confidence", 0.0),
                key_points=result_data.get("key_points", []),
                metadata={
                    "namespace": namespace.key(),
                    "message_count": len(messages),
                },
            )

            # Check confidence threshold
            if result.confidence < self.confidence_threshold:
                logger.debug(
                    f"Summary confidence too low for {namespace}: {result.confidence}"
                )
                self._stats["skipped_low_confidence"] += 1
                return None

            # Store summary
            await self._store_summary(namespace, result)
            self._stats["summaries_stored"] += 1

            return result

        except Exception as e:
            logger.error(f"Error generating summary for {namespace}: {e}")
            self._stats["errors"] += 1
            return None

    async def _store_summary(
        self, namespace: MemoryNamespace, result: SummaryResult
    ) -> None:
        """Store the summary in memory.

        Args:
            namespace: Memory namespace
            result: Summary result to store
        """
        # Format summary for storage
        summary_text = self._format_summary_for_storage(result)

        # Get existing summary and append
        existing = await self.memory_store.get_long_term_summary(namespace)
        if existing:
            combined = f"{existing}\n\n---\n\n{summary_text}"
        else:
            combined = summary_text

        await self.memory_store.set_long_term_summary(namespace, combined)

        # Update state to track when summary was made
        state = await self.memory_store.get_state(namespace)
        state["last_summary_turn"] = state.get("turn_count", 0)
        await self.memory_store.set_state(namespace, state)

        logger.info(
            f"Stored summary for {namespace} with confidence {result.confidence}"
        )

    def _format_summary_for_storage(self, result: SummaryResult) -> str:
        """Format summary result for storage.

        Args:
            result: Summary result

        Returns:
            Formatted summary text
        """
        lines = [f"Summary (confidence: {result.confidence:.2f}):", result.summary]

        if result.key_points:
            lines.append("\nKey points:")
            for point in result.key_points:
                lines.append(f"- {point}")

        return "\n".join(lines)

    async def maybe_summarize(self, namespace: MemoryNamespace) -> SummaryResult | None:
        """Check conditions and generate summary if appropriate.

        This is the main entry point - it checks if summary should be triggered
        and generates one if conditions are met.

        Args:
            namespace: Memory namespace to potentially summarize

        Returns:
            SummaryResult if generated, None otherwise
        """
        if not await self.should_trigger_summary(namespace):
            return None

        return await self.generate_and_store_summary(namespace)

    async def record_turn(self, namespace: MemoryNamespace) -> None:
        """Record a conversation turn.

        Call this after each meaningful interaction to track turn count.

        Args:
            namespace: Memory namespace
        """
        try:
            state = await self.memory_store.get_state(namespace)
            state["turn_count"] = state.get("turn_count", 0) + 1
            await self.memory_store.set_state(namespace, state)
        except Exception as e:
            logger.error(f"Error recording turn for {namespace}: {e}")

    def get_stats(self) -> dict[str, int]:
        """Get pipeline statistics.

        Returns:
            Dictionary of statistics
        """
        return dict(self._stats)

    def update_turn_threshold(self, threshold: int) -> None:
        """Update the turn threshold.

        Args:
            threshold: New threshold value
        """
        self.turn_threshold = max(1, threshold)
        logger.info(f"Updated turn threshold to {self.turn_threshold}")

    def update_confidence_threshold(self, threshold: float) -> None:
        """Update the confidence threshold.

        Args:
            threshold: New threshold value (0.0-1.0)
        """
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Updated confidence threshold to {self.confidence_threshold}")
