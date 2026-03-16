"""Feedback Collection System.

Collects both implicit and explicit feedback from users:
- Implicit: reply latency, reactions, emoji responses
- Explicit: "good bot" / "bad bot" patterns, direct feedback

Stores feedback with full context for learning algorithms.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeedbackEvent:
    """A feedback event from a user."""

    user_id: str
    timestamp: float
    feedback_type: str  # 'implicit' or 'explicit'
    score: float  # -1.0 to 1.0
    context: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # 'reaction', 'latency', 'message_pattern', etc.
    weight: float = 1.0  # Explicit feedback weighted higher

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "feedback_type": self.feedback_type,
            "score": self.score,
            "context": self.context,
            "source": self.source,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeedbackEvent":
        """Deserialize from dictionary."""
        return cls(
            user_id=data["user_id"],
            timestamp=data["timestamp"],
            feedback_type=data["feedback_type"],
            score=data["score"],
            context=data.get("context", {}),
            source=data.get("source", ""),
            weight=data.get("weight", 1.0),
        )


class ImplicitFeedbackDetector:
    """Detects implicit feedback from user behavior."""

    # Explicit feedback patterns (weighted highly)
    POSITIVE_PATTERNS = [
        r"\bgood\s+(bot|job|work)\b",
        r"\bthanks?\s+(you\s+)?bot\b",
        r"\bwell\s+done\b",
        r"\bawesome\b",
        r"\bperfect\b",
        r"\bexactly\b",
        r'\bthat["\']?s\s+helpful\b',
        r"\blove\s+it\b",
        r"\bgreat\s+response\b",
        r"👍|✅|🙏|❤️|💯",
    ]

    NEGATIVE_PATTERNS = [
        r"\bbad\s+(bot|job)\b",
        r'\bthat["\']?s\s+wrong\b',
        r"\bnot\s+(helpful|useful|correct)\b",
        r"\bstupid\s+bot\b",
        r"\bshut\s+up\b",
        r"\bgo\s+away\b",
        r"\bstop\s+responding\b",
        r"👎|❌|🚫|😤|😠",
    ]

    def __init__(self):
        self._positive_regex = [
            re.compile(p, re.IGNORECASE) for p in self.POSITIVE_PATTERNS
        ]
        self._negative_regex = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATIVE_PATTERNS
        ]

    def detect_from_message(self, message: str) -> FeedbackEvent | None:
        """Detect explicit feedback patterns in message."""
        message_lower = message.lower()

        # Check positive patterns
        for pattern in self._positive_regex:
            if pattern.search(message):
                return FeedbackEvent(
                    user_id="",  # To be filled by caller
                    timestamp=time.time(),
                    feedback_type="explicit",
                    score=0.8,
                    source="message_pattern_positive",
                    weight=1.5,  # High weight for explicit feedback
                )

        # Check negative patterns
        for pattern in self._negative_regex:
            if pattern.search(message):
                return FeedbackEvent(
                    user_id="",
                    timestamp=time.time(),
                    feedback_type="explicit",
                    score=-0.8,
                    source="message_pattern_negative",
                    weight=1.5,
                )

        return None

    def detect_from_reaction(self, reaction: str) -> FeedbackEvent | None:
        """Detect feedback from emoji reaction."""
        positive_reactions = ["👍", "❤️", "💯", "✅", "🙏", "🎉", "👏"]
        negative_reactions = ["👎", "❌", "🚫", "😤", "😠", "💢"]

        if reaction in positive_reactions:
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=0.6,
                source="reaction_positive",
                weight=1.0,
            )
        elif reaction in negative_reactions:
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=-0.6,
                source="reaction_negative",
                weight=1.0,
            )

        return None

    def detect_from_latency(
        self,
        response_time_seconds: float,
        user_responded: bool,
    ) -> FeedbackEvent | None:
        """Detect feedback from response latency."""
        if not user_responded:
            # No response is negative feedback
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=-0.4,
                source="no_response",
                weight=0.7,
            )

        # Fast response is positive
        if response_time_seconds < 60:
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=0.4,
                source="fast_response",
                weight=0.6,
            )
        elif response_time_seconds < 300:
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=0.2,
                source="moderate_response",
                weight=0.6,
            )

        return None

    def detect_from_message_features(self, message: str) -> FeedbackEvent | None:
        """Detect feedback from message features (emoji, length, etc.)."""
        # Count positive emojis
        positive_emojis = ["😊", "😄", "🙂", "👍", "❤️", "💯", "✨", "🎉"]
        negative_emojis = ["😤", "😠", "😒", "🙄", "💢", "😑"]

        pos_count = sum(message.count(e) for e in positive_emojis)
        neg_count = sum(message.count(e) for e in negative_emojis)

        if pos_count > neg_count:
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=0.3 * min(pos_count, 3),
                source="emoji_positive",
                weight=0.5,
            )
        elif neg_count > pos_count:
            return FeedbackEvent(
                user_id="",
                timestamp=time.time(),
                feedback_type="implicit",
                score=-0.3 * min(neg_count, 3),
                source="emoji_negative",
                weight=0.5,
            )

        return None


class FeedbackCollector:
    """Main feedback collection system."""

    def __init__(self, storage_path: str = "data/feedback/events.jsonl"):
        self.storage_path = storage_path
        self.detector = ImplicitFeedbackDetector()
        self._events: list[FeedbackEvent] = []
        self._recent_events: list[FeedbackEvent] = []  # Last 100 for quick access

    def collect_from_message(
        self,
        user_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> list[FeedbackEvent]:
        """Collect feedback from a user message."""
        events = []

        # Check for explicit patterns
        event = self.detector.detect_from_message(message)
        if event:
            event.user_id = user_id
            event.context = context or {}
            events.append(event)

        # Check for implicit features
        event = self.detector.detect_from_message_features(message)
        if event:
            event.user_id = user_id
            event.context = context or {}
            events.append(event)

        # Store events
        for event in events:
            self._store_event(event)

        return events

    def collect_from_reaction(
        self,
        user_id: str,
        reaction: str,
        message_context: dict[str, Any] | None = None,
    ) -> FeedbackEvent | None:
        """Collect feedback from a reaction."""
        event = self.detector.detect_from_reaction(reaction)
        if event:
            event.user_id = user_id
            event.context = message_context or {}
            self._store_event(event)
            return event
        return None

    def collect_from_latency(
        self,
        user_id: str,
        response_time_seconds: float,
        user_responded: bool,
        context: dict[str, Any] | None = None,
    ) -> FeedbackEvent | None:
        """Collect feedback from response latency."""
        event = self.detector.detect_from_latency(response_time_seconds, user_responded)
        if event:
            event.user_id = user_id
            event.context = context or {}
            self._store_event(event)
            return event
        return None

    def add_explicit_feedback(
        self,
        user_id: str,
        score: float,  # -1 to 1
        reason: str = "",
        context: dict[str, Any] | None = None,
    ) -> FeedbackEvent:
        """Add explicit user feedback.

        Args:
            user_id: User providing feedback
            score: Feedback score (-1 to 1)
            reason: Optional reason for feedback
            context: Additional context

        Returns:
            Created feedback event
        """
        event = FeedbackEvent(
            user_id=user_id,
            timestamp=time.time(),
            feedback_type="explicit",
            score=max(-1.0, min(1.0, score)),
            source="explicit_input",
            weight=2.0,  # Highest weight for direct feedback
            context={
                **(context or {}),
                "reason": reason,
            },
        )

        self._store_event(event)
        return event

    def _store_event(self, event: FeedbackEvent) -> None:
        """Store a feedback event."""
        self._events.append(event)
        self._recent_events.append(event)

        # Keep recent events limited
        if len(self._recent_events) > 100:
            self._recent_events = self._recent_events[-100:]

        # Append to file
        import os

        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def get_recent_feedback(
        self,
        user_id: str | None = None,
        n: int = 10,
    ) -> list[FeedbackEvent]:
        """Get recent feedback events.

        Args:
            user_id: Filter by user (None for all)
            n: Number of events to return

        Returns:
            List of recent feedback events
        """
        events = self._recent_events
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        return events[-n:]

    def get_user_feedback_summary(self, user_id: str) -> dict[str, Any]:
        """Get feedback summary for a user."""
        user_events = [e for e in self._recent_events if e.user_id == user_id]

        if not user_events:
            return {
                "total_events": 0,
                "average_score": 0.0,
                "positive_rate": 0.0,
            }

        total_score = sum(e.score * e.weight for e in user_events)
        total_weight = sum(e.weight for e in user_events)
        avg_score = total_score / total_weight if total_weight > 0 else 0

        positive_events = sum(1 for e in user_events if e.score > 0)

        return {
            "total_events": len(user_events),
            "average_score": round(avg_score, 3),
            "positive_rate": round(positive_events / len(user_events), 2),
            "explicit_count": sum(
                1 for e in user_events if e.feedback_type == "explicit"
            ),
            "implicit_count": sum(
                1 for e in user_events if e.feedback_type == "implicit"
            ),
        }

    def calculate_weighted_reward(self, user_id: str, window: int = 5) -> float:
        """Calculate weighted reward from recent feedback.

        Args:
            user_id: User to calculate for
            window: Number of recent events to consider

        Returns:
            Weighted average score
        """
        events = self.get_recent_feedback(user_id, n=window)

        if not events:
            return 0.0

        total_score = sum(e.score * e.weight for e in events)
        total_weight = sum(e.weight for e in events)

        return total_score / total_weight if total_weight > 0 else 0.0


# Global instance
_feedback_collector: FeedbackCollector | None = None


def get_feedback_collector() -> FeedbackCollector:
    """Get global feedback collector."""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector()
    return _feedback_collector
