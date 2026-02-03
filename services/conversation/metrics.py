"""Conversation Quality Metrics Calculator.

Calculates quality metrics for bot-to-bot conversations:
1. Character Consistency (optional/expensive): LLM judge scores each message
2. Turn Relevance: Similarity between consecutive turns
3. Response Latency: Average response time
4. Vocabulary Diversity: Unique words ratio
"""

import logging
from typing import List, Optional, Any
from datetime import datetime

from services.conversation.state import ConversationState, ConversationMetrics, Message

logger = logging.getLogger(__name__)


class ConversationMetricsCalculator:
    """Calculates quality metrics for bot conversations."""

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        detailed_metrics: bool = False,
    ):
        """
        Initialize metrics calculator.

        Args:
            llm_service: LLM service for character consistency (optional)
            detailed_metrics: Enable expensive LLM-based metrics
        """
        self.llm = llm_service
        self.detailed_metrics = detailed_metrics

    async def calculate_all_metrics(
        self, state: ConversationState
    ) -> ConversationMetrics:
        """
        Calculate all available metrics for a conversation.

        Args:
            state: Conversation state with messages

        Returns:
            ConversationMetrics with calculated values
        """
        if not state.messages:
            logger.warning("No messages to calculate metrics for")
            return ConversationMetrics()

        metrics = ConversationMetrics()

        # Calculate cheap metrics (always)
        metrics.turn_relevance = self._calculate_turn_relevance(state.messages)
        metrics.avg_latency = self._calculate_avg_latency(state.messages)
        metrics.vocab_diversity = self._calculate_vocab_diversity(state.messages)

        # Calculate expensive metrics (optional)
        if self.detailed_metrics and self.llm:
            metrics.character_consistency = await self._calculate_character_consistency(
                state
            )

        # Calculate composite quality score (0.0-1.0)
        metrics.quality_score = self._calculate_quality_score(metrics)

        logger.info(
            f"Calculated metrics: quality={metrics.quality_score:.2f}, "
            f"relevance={metrics.turn_relevance:.2f}, "
            f"latency={metrics.avg_latency:.2f}s, "
            f"diversity={metrics.vocab_diversity:.2f}"
        )

        return metrics

    def _calculate_turn_relevance(self, messages: List[Message]) -> float:
        """
        Calculate turn relevance using Jaccard similarity.

        Measures how related consecutive messages are (0.0-1.0).

        Args:
            messages: List of conversation messages

        Returns:
            Average Jaccard similarity between consecutive turns
        """
        if len(messages) < 2:
            return 1.0  # Single message is perfectly relevant

        similarities = []
        for i in range(len(messages) - 1):
            current = self._tokenize(messages[i].content)
            next_msg = self._tokenize(messages[i + 1].content)

            # Jaccard similarity: intersection / union
            intersection = len(current & next_msg)
            union = len(current | next_msg)

            if union == 0:
                similarity = 0.0
            else:
                similarity = intersection / union

            similarities.append(similarity)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _calculate_avg_latency(self, messages: List[Message]) -> float:
        """
        Calculate average response latency.

        Args:
            messages: List of conversation messages

        Returns:
            Average latency in seconds
        """
        latencies = [
            m.metadata.get("latency", 0.0) for m in messages if "latency" in m.metadata
        ]

        if not latencies:
            return 0.0

        return sum(latencies) / len(latencies)

    def _calculate_vocab_diversity(self, messages: List[Message]) -> float:
        """
        Calculate vocabulary diversity (unique words / total words).

        Higher diversity indicates richer conversation (0.0-1.0).

        Args:
            messages: List of conversation messages

        Returns:
            Vocabulary diversity ratio
        """
        all_words = []
        for message in messages:
            words = self._tokenize(message.content)
            all_words.extend(words)

        if not all_words:
            return 0.0

        unique_words = set(all_words)
        diversity = len(unique_words) / len(all_words)

        return diversity

    async def _calculate_character_consistency(self, state: ConversationState) -> float:
        """
        Calculate character consistency using LLM judge (expensive).

        Scores how well each message matches the persona's character.

        Args:
            state: Conversation state with persona information

        Returns:
            Average consistency score (0.0-1.0)
        """
        # TODO: Implement LLM-based character consistency judge
        # For V1, use simple heuristic: message length variance
        # Lower variance = more consistent
        if not state.messages:
            return 1.0

        lengths = [len(m.content) for m in state.messages]
        if len(lengths) < 2:
            return 1.0

        # Calculate coefficient of variation (CV)
        mean_length = sum(lengths) / len(lengths)
        variance = sum((x - mean_length) ** 2 for x in lengths) / len(lengths)
        std_dev = variance**0.5

        if mean_length == 0:
            return 1.0

        cv = std_dev / mean_length

        # Convert CV to consistency score (lower CV = higher consistency)
        # CV > 1.0 = very inconsistent (score ~0), CV < 0.3 = consistent (score ~1)
        consistency = max(0.0, min(1.0, 1.0 - cv))

        logger.debug(
            f"Character consistency (heuristic): {consistency:.2f} (CV={cv:.2f})"
        )
        return consistency

    def _calculate_quality_score(self, metrics: ConversationMetrics) -> float:
        """
        Calculate composite quality score from individual metrics.

        Args:
            metrics: Individual metrics

        Returns:
            Composite quality score (0.0-1.0)
        """
        scores = []
        weights = []

        # Turn relevance (weight: 0.3)
        if metrics.turn_relevance > 0:
            scores.append(metrics.turn_relevance)
            weights.append(0.3)

        # Vocabulary diversity (weight: 0.2)
        if metrics.vocab_diversity > 0:
            scores.append(metrics.vocab_diversity)
            weights.append(0.2)

        # Character consistency (weight: 0.4, if available)
        if metrics.character_consistency > 0:
            scores.append(metrics.character_consistency)
            weights.append(0.4)

        # Latency penalty (weight: 0.1)
        # Good latency: < 2s = 1.0, > 10s = 0.0
        if metrics.avg_latency > 0:
            latency_score = max(0.0, min(1.0, (10.0 - metrics.avg_latency) / 8.0))
            scores.append(latency_score)
            weights.append(0.1)

        # Weighted average
        if not scores:
            return 0.0

        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _tokenize(self, text: str) -> set:
        """
        Simple tokenization (split on whitespace, lowercase).

        Args:
            text: Input text

        Returns:
            Set of tokens
        """
        # Simple tokenization: lowercase, split on whitespace, remove punctuation
        import re

        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        tokens = text.split()

        return set(tokens)
