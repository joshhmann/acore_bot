"""Recall tuning and noise controls for gestalt-terminal T15.

GT-V4: Implements confidence thresholds, noise filtering, and relevance scoring
for proactive memory recall to improve retrieval quality.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MemoryEntry(Protocol):
    """Protocol for memory entries that can be scored."""

    content: str
    timestamp: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecallTuningConfig:
    """Configuration for memory recall tuning.

    All thresholds are configurable via environment variables or code.
    """

    # Confidence thresholds for proactive recall (0.0 - 1.0)
    min_confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.75
    critical_confidence_threshold: float = 0.9

    # Noise filtering settings
    min_quality_score: float = 0.3
    max_age_seconds: float = 86400 * 30  # 30 days default
    deduplication_enabled: bool = True
    deduplication_threshold: float = 0.85

    # Relevance scoring weights
    recency_weight: float = 0.25
    quality_weight: float = 0.35
    semantic_weight: float = 0.40

    # Retrieval limits
    max_proactive_recalls: int = 5
    min_relevance_for_proactive: float = 0.6

    # Adaptive tuning
    adaptive_tuning_enabled: bool = True
    feedback_window_size: int = 100
    success_rate_target: float = 0.7

    def validate(self) -> bool:
        """Validate configuration values are in valid ranges."""
        errors = []

        if not (0.0 <= self.min_confidence_threshold <= 1.0):
            errors.append(
                f"min_confidence_threshold must be in [0, 1], got {self.min_confidence_threshold}"
            )
        if not (0.0 <= self.high_confidence_threshold <= 1.0):
            errors.append(
                f"high_confidence_threshold must be in [0, 1], got {self.high_confidence_threshold}"
            )
        if not (0.0 <= self.critical_confidence_threshold <= 1.0):
            errors.append(
                f"critical_confidence_threshold must be in [0, 1], got {self.critical_confidence_threshold}"
            )

        # Ensure threshold ordering
        if not (
            self.min_confidence_threshold
            <= self.high_confidence_threshold
            <= self.critical_confidence_threshold
        ):
            errors.append("Confidence thresholds must be in ascending order")

        if not (0.0 <= self.min_quality_score <= 1.0):
            errors.append(
                f"min_quality_score must be in [0, 1], got {self.min_quality_score}"
            )

        if not (0.0 <= self.recency_weight <= 1.0):
            errors.append(
                f"recency_weight must be in [0, 1], got {self.recency_weight}"
            )
        if not (0.0 <= self.quality_weight <= 1.0):
            errors.append(
                f"quality_weight must be in [0, 1], got {self.quality_weight}"
            )
        if not (0.0 <= self.semantic_weight <= 1.0):
            errors.append(
                f"semantic_weight must be in [0, 1], got {self.semantic_weight}"
            )

        # Weights should sum to approximately 1.0
        weight_sum = self.recency_weight + self.quality_weight + self.semantic_weight
        if not (0.99 <= weight_sum <= 1.01):
            errors.append(f"Relevance weights must sum to ~1.0, got {weight_sum}")

        if self.max_age_seconds <= 0:
            errors.append(
                f"max_age_seconds must be positive, got {self.max_age_seconds}"
            )

        if errors:
            for error in errors:
                logger.error(f"RecallTuningConfig validation: {error}")
            return False

        return True


@dataclass
class RecallMetrics:
    """Metrics for tracking recall tuning effectiveness."""

    total_recalls: int = 0
    filtered_by_confidence: int = 0
    filtered_by_quality: int = 0
    filtered_by_age: int = 0
    filtered_by_duplicate: int = 0
    proactive_triggers: int = 0
    high_confidence_triggers: int = 0

    # Success tracking for adaptive tuning
    feedback_scores: list[float] = field(default_factory=list)
    last_tuning_adjustment: float = field(default_factory=time.time)

    @property
    def total_filtered(self) -> int:
        """Total number of memories filtered out."""
        return (
            self.filtered_by_confidence
            + self.filtered_by_quality
            + self.filtered_by_age
            + self.filtered_by_duplicate
        )

    @property
    def filter_rate(self) -> float:
        """Percentage of memories that were filtered."""
        if self.total_recalls == 0:
            return 0.0
        return self.total_filtered / self.total_recalls

    @property
    def proactive_success_rate(self) -> float:
        """Success rate of proactive recalls based on feedback."""
        if not self.feedback_scores:
            return 0.0
        # Count positive feedback (score > 0.5) as success
        successes = sum(1 for score in self.feedback_scores if score > 0.5)
        return successes / len(self.feedback_scores)

    def add_feedback(self, score: float) -> None:
        """Add a feedback score (0.0 - 1.0) for adaptive tuning."""
        self.feedback_scores.append(score)
        # Keep only recent feedback
        if len(self.feedback_scores) > 1000:
            self.feedback_scores = self.feedback_scores[-1000:]

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "total_recalls": self.total_recalls,
            "filtered_by_confidence": self.filtered_by_confidence,
            "filtered_by_quality": self.filtered_by_quality,
            "filtered_by_age": self.filtered_by_age,
            "filtered_by_duplicate": self.filtered_by_duplicate,
            "proactive_triggers": self.proactive_triggers,
            "high_confidence_triggers": self.high_confidence_triggers,
            "filter_rate": self.filter_rate,
            "proactive_success_rate": self.proactive_success_rate,
        }


@dataclass(slots=True)
class ScoredMemory:
    """A memory entry with computed relevance scores."""

    content: str
    timestamp: float
    metadata: dict[str, Any]
    confidence: float = 0.0
    quality_score: float = 0.0
    recency_score: float = 0.0
    semantic_score: float = 0.0
    overall_score: float = 0.0
    is_duplicate: bool = False

    @property
    def age_seconds(self) -> float:
        """Calculate age of memory in seconds."""
        return time.time() - self.timestamp


class RecallTuner:
    """Tuning engine for memory recall with noise filtering.

    Implements GT-V4 recall tuning requirements:
    - Confidence thresholds for proactive memory recall
    - Noise filtering (exclude low-quality memories)
    - Relevance scoring for memory retrieval
    - Metrics/logging for tuning effectiveness

    Example:
        config = RecallTuningConfig(
            min_confidence_threshold=0.6,
            min_quality_score=0.4,
        )
        tuner = RecallTuner(config)

        # Score and filter memories
        memories = [...]  # List of memory entries
        scored = tuner.score_memories(memories, query="user query")
        filtered = tuner.apply_filters(scored)

        # Get proactive recall candidates
        candidates = tuner.get_proactive_recalls(filtered)
    """

    def __init__(self, config: RecallTuningConfig | None = None) -> None:
        """Initialize the recall tuner with configuration.

        Args:
            config: Tuning configuration. Uses defaults if not provided.
        """
        self.config = config or RecallTuningConfig()
        self.metrics = RecallMetrics()
        self._seen_hashes: set[str] = set()

        if not self.config.validate():
            raise ValueError("Invalid recall tuning configuration")

        logger.info(
            f"RecallTuner initialized with confidence_threshold={self.config.min_confidence_threshold}"
        )

    def score_memories(
        self,
        memories: list[dict[str, Any]],
        query: str | None = None,
        reference_time: float | None = None,
    ) -> list[ScoredMemory]:
        """Score a list of memories for relevance.

        Computes confidence, quality, recency, and semantic scores for each memory.

        Args:
            memories: List of memory entries with 'content', 'timestamp', 'metadata'
            query: Optional query string for semantic scoring
            reference_time: Optional reference time for recency calculation (default: now)

        Returns:
            List of ScoredMemory objects with computed scores
        """
        if reference_time is None:
            reference_time = time.time()

        scored_memories: list[ScoredMemory] = []

        for mem in memories:
            content = mem.get("content", "")
            timestamp = mem.get("timestamp", reference_time)
            metadata = mem.get("metadata", {})

            # Calculate individual scores
            quality_score = self._calculate_quality_score(content, metadata)
            recency_score = self._calculate_recency_score(timestamp, reference_time)
            semantic_score = (
                self._calculate_semantic_score(content, query) if query else 0.5
            )

            # Compute weighted overall score
            overall_score = (
                self.config.recency_weight * recency_score
                + self.config.quality_weight * quality_score
                + self.config.semantic_weight * semantic_score
            )

            # Confidence is derived from overall score and quality
            confidence = (overall_score + quality_score) / 2

            scored = ScoredMemory(
                content=content,
                timestamp=timestamp,
                metadata=metadata,
                confidence=confidence,
                quality_score=quality_score,
                recency_score=recency_score,
                semantic_score=semantic_score,
                overall_score=overall_score,
            )
            scored_memories.append(scored)

        self.metrics.total_recalls += len(memories)
        logger.debug(f"Scored {len(scored_memories)} memories")
        return scored_memories

    def _calculate_quality_score(self, content: str, metadata: dict[str, Any]) -> float:
        """Calculate quality score for a memory entry.

        Factors:
        - Content length (not too short, not too long)
        - Metadata quality indicators
        - Source reliability
        """
        scores = []

        # Length score: optimal range 50-500 chars
        length = len(content)
        if 50 <= length <= 500:
            scores.append(1.0)
        elif length < 20:
            scores.append(0.3)
        elif length > 1000:
            scores.append(0.7)
        else:
            scores.append(0.8)

        # Metadata quality
        has_metadata = bool(metadata)
        scores.append(1.0 if has_metadata else 0.6)

        # Source reliability from metadata
        source_reliability = metadata.get("source_reliability", 0.8)
        scores.append(min(1.0, max(0.0, source_reliability)))

        # User validation (if memory was validated/confirmed)
        user_validated = metadata.get("user_validated", False)
        scores.append(1.0 if user_validated else 0.7)

        return sum(scores) / len(scores)

    def _calculate_recency_score(
        self, timestamp: float, reference_time: float
    ) -> float:
        """Calculate recency score decaying over time.

        Uses exponential decay based on max_age configuration.
        """
        age = reference_time - timestamp
        if age < 0:
            age = 0

        if age > self.config.max_age_seconds:
            return 0.0

        # Exponential decay: score = e^(-3 * age/max_age)
        # This gives ~0.05 at max_age (very low but not zero)
        import math

        decay_rate = 3.0
        normalized_age = age / self.config.max_age_seconds
        return math.exp(-decay_rate * normalized_age)

    def _calculate_semantic_score(self, content: str, query: str) -> float:
        """Calculate semantic relevance score between content and query.

        This is a simplified implementation. In production, this would use
        embeddings and vector similarity.
        """
        if not query:
            return 0.5

        content_lower = content.lower()
        query_lower = query.lower()

        # Simple keyword overlap scoring
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())

        if not query_words:
            return 0.5

        overlap = query_words & content_words
        score = len(overlap) / len(query_words)

        # Boost for exact phrase match
        if query_lower in content_lower:
            score = min(1.0, score + 0.3)

        return min(1.0, score)

    def apply_filters(self, scored_memories: list[ScoredMemory]) -> list[ScoredMemory]:
        """Apply noise filters to scored memories.

        Filters out:
        - Low confidence memories
        - Low quality memories
        - Outdated memories (based on max_age)
        - Duplicate memories (if deduplication enabled)

        Args:
            scored_memories: List of scored memory entries

        Returns:
            Filtered list of memories passing all criteria
        """
        filtered: list[ScoredMemory] = []
        content_hashes: set[str] = set()

        for memory in scored_memories:
            # Confidence filter
            if memory.confidence < self.config.min_confidence_threshold:
                self.metrics.filtered_by_confidence += 1
                logger.debug(f"Filtered by confidence: {memory.confidence:.3f}")
                continue

            # Quality filter
            if memory.quality_score < self.config.min_quality_score:
                self.metrics.filtered_by_quality += 1
                logger.debug(f"Filtered by quality: {memory.quality_score:.3f}")
                continue

            # Age filter
            if memory.age_seconds > self.config.max_age_seconds:
                self.metrics.filtered_by_age += 1
                logger.debug(f"Filtered by age: {memory.age_seconds:.1f}s")
                continue

            # Deduplication filter
            if self.config.deduplication_enabled:
                content_hash = hash(memory.content.lower().strip())
                if content_hash in content_hashes:
                    memory.is_duplicate = True
                    self.metrics.filtered_by_duplicate += 1
                    logger.debug("Filtered as duplicate")
                    continue
                content_hashes.add(content_hash)

            filtered.append(memory)

        logger.info(
            f"Filter pass: {len(filtered)}/{len(scored_memories)} passed "
            f"({self.metrics.filter_rate:.1%} filtered overall)"
        )
        return filtered

    def get_proactive_recalls(
        self, scored_memories: list[ScoredMemory], limit: int | None = None
    ) -> list[ScoredMemory]:
        """Get memories suitable for proactive recall.

        Selects high-relevance memories that exceed the proactive threshold.

        Args:
            scored_memories: List of scored (and preferably filtered) memories
            limit: Maximum number of proactive recalls (default: config.max_proactive_recalls)

        Returns:
            List of memories suitable for proactive recall, sorted by overall score
        """
        if limit is None:
            limit = self.config.max_proactive_recalls

        # Filter to high-relevance memories
        candidates = [
            m
            for m in scored_memories
            if m.overall_score >= self.config.min_relevance_for_proactive
            and m.confidence >= self.config.high_confidence_threshold
        ]

        # Sort by overall score descending
        candidates.sort(key=lambda x: x.overall_score, reverse=True)

        result = candidates[:limit]

        self.metrics.proactive_triggers += len(result)
        self.metrics.high_confidence_triggers += sum(
            1
            for m in result
            if m.confidence >= self.config.critical_confidence_threshold
        )

        logger.info(f"Proactive recalls: {len(result)} candidates selected")
        return result

    def update_config(self, new_config: RecallTuningConfig) -> None:
        """Update tuner configuration at runtime.

        Args:
            new_config: New configuration to apply

        Raises:
            ValueError: If new configuration is invalid
        """
        if not new_config.validate():
            raise ValueError("Invalid recall tuning configuration")

        self.config = new_config
        logger.info("RecallTuner configuration updated")

    def add_feedback(
        self, memory: ScoredMemory, was_helpful: bool, score: float | None = None
    ) -> None:
        """Add user feedback for adaptive tuning.

        Args:
            memory: The memory that was recalled
            was_helpful: Whether the recall was helpful
            score: Optional explicit feedback score (0.0 - 1.0)
        """
        if score is None:
            score = 1.0 if was_helpful else 0.0

        self.metrics.add_feedback(score)

        # Adaptive tuning: adjust thresholds based on success rate
        if self.config.adaptive_tuning_enabled:
            self._adapt_thresholds()

    def _adapt_thresholds(self) -> None:
        """Adapt thresholds based on recent feedback.

        Adjusts confidence thresholds to maintain target success rate.
        """
        current_time = time.time()
        time_since_adjustment = current_time - self.metrics.last_tuning_adjustment

        # Only adjust periodically (every 5 minutes)
        if time_since_adjustment < 300:
            return

        if len(self.metrics.feedback_scores) < self.config.feedback_window_size:
            return  # Not enough data

        success_rate = self.metrics.proactive_success_rate
        target = self.config.success_rate_target

        # Calculate adjustment
        adjustment = (success_rate - target) * 0.1  # 10% of error

        old_threshold = self.config.min_confidence_threshold
        new_threshold = max(0.1, min(0.95, old_threshold - adjustment))

        if abs(new_threshold - old_threshold) > 0.05:
            # Create new config with adjusted threshold
            self.config = RecallTuningConfig(
                min_confidence_threshold=new_threshold,
                high_confidence_threshold=min(0.95, new_threshold + 0.2),
                critical_confidence_threshold=min(0.99, new_threshold + 0.3),
                min_quality_score=self.config.min_quality_score,
                max_age_seconds=self.config.max_age_seconds,
                deduplication_enabled=self.config.deduplication_enabled,
                deduplication_threshold=self.config.deduplication_threshold,
                recency_weight=self.config.recency_weight,
                quality_weight=self.config.quality_weight,
                semantic_weight=self.config.semantic_weight,
                max_proactive_recalls=self.config.max_proactive_recalls,
                min_relevance_for_proactive=self.config.min_relevance_for_proactive,
                adaptive_tuning_enabled=self.config.adaptive_tuning_enabled,
                feedback_window_size=self.config.feedback_window_size,
                success_rate_target=self.config.success_rate_target,
            )
            self.metrics.last_tuning_adjustment = current_time
            logger.info(
                f"Adaptive tuning adjusted confidence threshold: {old_threshold:.3f} -> {new_threshold:.3f}"
            )

    def get_metrics(self) -> RecallMetrics:
        """Get current tuning metrics."""
        return self.metrics

    def reset_metrics(self) -> None:
        """Reset tuning metrics."""
        self.metrics = RecallMetrics()
        self._seen_hashes.clear()
        logger.info("RecallTuner metrics reset")


def create_default_tuner() -> RecallTuner:
    """Create a recall tuner with default configuration.

    Returns:
        RecallTuner instance with default settings
    """
    return RecallTuner(RecallTuningConfig())


def create_aggressive_tuner() -> RecallTuner:
    """Create a recall tuner with aggressive filtering.

    Useful for high-noise environments where quality is prioritized
    over recall quantity.

    Returns:
        RecallTuner instance with aggressive filtering settings
    """
    config = RecallTuningConfig(
        min_confidence_threshold=0.7,
        high_confidence_threshold=0.85,
        min_quality_score=0.5,
        max_proactive_recalls=3,
        min_relevance_for_proactive=0.75,
    )
    return RecallTuner(config)


def create_permissive_tuner() -> RecallTuner:
    """Create a recall tuner with permissive filtering.

    Useful for low-noise environments where recall quantity is
    prioritized over precision.

    Returns:
        RecallTuner instance with permissive filtering settings
    """
    config = RecallTuningConfig(
        min_confidence_threshold=0.3,
        high_confidence_threshold=0.6,
        min_quality_score=0.2,
        max_proactive_recalls=10,
        min_relevance_for_proactive=0.4,
    )
    return RecallTuner(config)
