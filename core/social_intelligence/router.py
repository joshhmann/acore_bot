"""Mode Router for Cognitive Mode Selection.

Routes incoming requests to appropriate cognitive modes based on:
- Keyword detection
- Historical performance
- Confidence scoring
- Context analysis
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.social_intelligence.modes import CognitiveMode, ModeConfig


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    mode: CognitiveMode
    confidence: float
    reason: str
    strategy: str  # Which routing strategy was used


class ModeRouter:
    """Routes events to appropriate cognitive modes.

    Uses multiple strategies:
    1. Keyword-based: Detect keywords suggesting specific modes
    2. History-based: What worked well before
    3. Confidence-based: If uncertain, use Facilitator
    4. Default: Use character's preferred mode
    """

    # Keywords that suggest specific modes
    KEYWORD_PATTERNS = {
        CognitiveMode.LOGIC: [
            r"\b(code|debug|error|fix|implement|function|class|algorithm)\b",
            r"\b(analyze|calculate|compute|solve|prove|verify|check)\b",
            r"\b(logic|reasoning|evidence|fact|data|statistics)\b",
            r"\b(why|how does|explain|clarify)\b",
        ],
        CognitiveMode.CREATIVE: [
            r"\b(brainstorm|idea|creative|imagine|design|concept)\b",
            r"\b(generate|create|invent|novel|innovative|unique)\b",
            r"\b(story|write|poem|art|artistic|inspiration)\b",
            r"\b(what if|possibility|alternative|different approach)\b",
        ],
    }

    def __init__(
        self,
        default_mode: CognitiveMode = CognitiveMode.LOGIC,
        confidence_threshold: float = 0.6,
    ):
        self.default_mode = default_mode
        self.confidence_threshold = confidence_threshold
        self._routing_history: list[tuple[str, CognitiveMode, float]] = []
        self._mode_performance: dict[CognitiveMode, float] = {
            CognitiveMode.CREATIVE: 0.5,
            CognitiveMode.LOGIC: 0.5,
            CognitiveMode.FACILITATOR: 0.5,
        }

    def select_mode(
        self,
        event: dict[str, Any],
        social_context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Select appropriate cognitive mode for an event.

        Args:
            event: The event to route (contains 'content', 'type', etc.)
            social_context: Social context (user preferences, history, etc.)

        Returns:
            RoutingDecision with selected mode and confidence
        """
        content = event.get("content", "")
        social_context = social_context or {}

        # Try keyword-based routing first
        decision = self._keyword_routing(content)
        if decision.confidence >= self.confidence_threshold:
            self._record_decision(content, decision)
            return decision

        # Try history-based routing
        decision = self._history_routing(content)
        if decision.confidence >= self.confidence_threshold:
            self._record_decision(content, decision)
            return decision

        # Try context-based routing
        decision = self._context_routing(content, social_context)
        if decision.confidence >= self.confidence_threshold:
            self._record_decision(content, decision)
            return decision

        # Low confidence - use Facilitator to decide
        decision = RoutingDecision(
            mode=CognitiveMode.FACILITATOR,
            confidence=0.5,
            reason="Low confidence in automatic routing",
            strategy="fallback_to_facilitator",
        )
        self._record_decision(content, decision)
        return decision

    def _keyword_routing(self, content: str) -> RoutingDecision:
        """Route based on keyword detection."""
        content_lower = content.lower()
        scores: dict[CognitiveMode, float] = {mode: 0.0 for mode in CognitiveMode}

        for mode, patterns in self.KEYWORD_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, content_lower, re.IGNORECASE))
                scores[mode] += matches * 0.3  # Each match adds 0.3 confidence

        # Normalize scores
        max_score = max(scores.values()) if scores else 0
        if max_score > 0:
            for mode in scores:
                scores[mode] = min(1.0, scores[mode] / max_score * 0.8 + 0.2)

        # Select mode with highest score
        best_mode = max(scores, key=lambda k: scores[k])
        best_score = scores[best_mode]

        if best_score > 0:
            return RoutingDecision(
                mode=best_mode,
                confidence=best_score,
                reason=f"Keyword match ({best_score:.2f} confidence)",
                strategy="keyword_based",
            )

        return RoutingDecision(
            mode=self.default_mode,
            confidence=0.0,
            reason="No keyword matches",
            strategy="keyword_based",
        )

    def _history_routing(self, content: str) -> RoutingDecision:
        """Route based on historical performance of similar requests."""
        if not self._routing_history:
            return RoutingDecision(
                mode=self.default_mode,
                confidence=0.0,
                reason="No routing history",
                strategy="history_based",
            )

        # Simple similarity: check for shared keywords
        content_words = set(content.lower().split())
        mode_scores: dict[CognitiveMode, list[float]] = {
            mode: [] for mode in CognitiveMode
        }

        for hist_content, hist_mode, hist_conf in self._routing_history[
            -50:
        ]:  # Last 50
            hist_words = set(hist_content.lower().split())
            overlap = len(content_words & hist_words) / max(len(content_words), 1)

            if overlap > 0.3:  # At least 30% word overlap
                mode_scores[hist_mode].append(overlap * hist_conf)

        # Calculate average confidence per mode
        avg_scores: dict[CognitiveMode, float] = {}
        for mode, scores in mode_scores.items():
            if scores:
                avg_scores[mode] = sum(scores) / len(scores)
            else:
                avg_scores[mode] = 0.0

        if avg_scores:
            best_mode = max(avg_scores, key=lambda k: avg_scores[k])
            best_score = avg_scores[best_mode]

            if best_score > 0:
                return RoutingDecision(
                    mode=best_mode,
                    confidence=best_score,
                    reason=f"Historical similarity ({best_score:.2f} confidence)",
                    strategy="history_based",
                )

        return RoutingDecision(
            mode=self.default_mode,
            confidence=0.0,
            reason="No similar historical requests",
            strategy="history_based",
        )

    def _context_routing(
        self,
        content: str,
        social_context: dict[str, Any],
    ) -> RoutingDecision:
        """Route based on social context."""
        # Check for user-preferred mode
        preferred_mode = social_context.get("preferred_mode")
        if preferred_mode:
            try:
                mode = CognitiveMode[preferred_mode.upper()]
                return RoutingDecision(
                    mode=mode,
                    confidence=0.7,
                    reason="User preferred mode",
                    strategy="context_based",
                )
            except KeyError:
                pass

        # Check for task type
        task_type = social_context.get("task_type", "")
        if task_type in ["coding", "debugging", "analysis"]:
            return RoutingDecision(
                mode=CognitiveMode.LOGIC,
                confidence=0.75,
                reason=f"Task type: {task_type}",
                strategy="context_based",
            )
        elif task_type in ["writing", "brainstorming", "design"]:
            return RoutingDecision(
                mode=CognitiveMode.CREATIVE,
                confidence=0.75,
                reason=f"Task type: {task_type}",
                strategy="context_based",
            )

        return RoutingDecision(
            mode=self.default_mode,
            confidence=0.0,
            reason="No contextual clues",
            strategy="context_based",
        )

    def _record_decision(
        self,
        content: str,
        decision: RoutingDecision,
    ) -> None:
        """Record routing decision for future learning."""
        self._routing_history.append(
            (
                content[:200],  # Truncate for memory
                decision.mode,
                decision.confidence,
            )
        )

        # Keep history manageable
        if len(self._routing_history) > 1000:
            self._routing_history = self._routing_history[-500:]

    def update_performance(
        self,
        mode: CognitiveMode,
        success: bool,
        feedback_score: float | None = None,
    ) -> None:
        """Update performance metrics for a mode.

        Args:
            mode: The cognitive mode
            success: Whether the routing was successful
            feedback_score: Optional explicit feedback (0.0 - 1.0)
        """
        current = self._mode_performance[mode]

        if feedback_score is not None:
            # Use explicit feedback
            new_score = current * 0.7 + feedback_score * 0.3
        elif success:
            # Successful routing
            new_score = min(1.0, current + 0.05)
        else:
            # Failed routing
            new_score = max(0.0, current - 0.1)

        self._mode_performance[mode] = new_score

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "total_decisions": len(self._routing_history),
            "mode_performance": {
                mode.name: score for mode, score in self._mode_performance.items()
            },
            "recent_modes": [mode.name for _, mode, _ in self._routing_history[-10:]],
        }
