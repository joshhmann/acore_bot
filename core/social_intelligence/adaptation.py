"""User-Specific Adaptation System.

Learns and adapts to individual users:
- Optimal engagement timing (morning vs evening)
- Preferred cognitive modes
- Communication style preferences
- Trigger sensitivity (how often to engage)

Stores learned preferences and applies them to
routing and trigger decisions.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserPreferences:
    """Learned preferences for a user."""

    user_id: str

    # Timing preferences (hour of day, 0-23)
    optimal_hours: dict[int, float] = field(default_factory=lambda: defaultdict(float))

    # Mode preferences (frequency of use)
    mode_preferences: dict[str, float] = field(
        default_factory=lambda: defaultdict(float)
    )

    # Communication style
    prefers_emoji: float = 0.5  # 0 (never) to 1 (always)
    prefers_formal: float = 0.5  # 0 (casual) to 1 (formal)
    response_length_preference: str = "medium"  # short/medium/long

    # Trigger sensitivity (0 = rare, 1 = frequent)
    trigger_sensitivity: float = 0.5

    # Explicit overrides (user-set preferences)
    explicit_mute: bool = False
    explicit_quiet_hours: tuple[int, int] | None = None  # (start, end)
    explicit_max_engagements_per_hour: int | None = None

    # Statistics
    total_interactions: int = 0
    positive_interactions: int = 0
    last_interaction_time: float = 0.0

    def update_timing(self, hour: int, success: bool) -> None:
        """Update optimal hours based on interaction success."""
        # Simple moving average
        alpha = 0.3
        current = self.optimal_hours.get(hour, 0.5)
        reward = 1.0 if success else 0.0
        self.optimal_hours[hour] = current * (1 - alpha) + reward * alpha

    def update_mode_preference(self, mode: str, success: bool) -> None:
        """Update mode preference based on interaction success."""
        alpha = 0.3
        current = self.mode_preferences.get(mode, 0.5)
        reward = 1.0 if success else 0.0
        self.mode_preferences[mode] = current * (1 - alpha) + reward * alpha

    def get_best_hours(self, n: int = 3) -> list[int]:
        """Get top N best hours for engagement."""
        if not self.optimal_hours:
            return [9, 14, 20]  # Default: morning, afternoon, evening

        sorted_hours = sorted(
            self.optimal_hours.items(), key=lambda x: x[1], reverse=True
        )
        return [hour for hour, _ in sorted_hours[:n]]

    def get_preferred_mode(self) -> str | None:
        """Get user's preferred cognitive mode."""
        if not self.mode_preferences:
            return None
        return max(self.mode_preferences.items(), key=lambda x: x[1])[0]

    def should_trigger_at_hour(self, hour: int) -> bool:
        """Check if we should trigger at given hour."""
        # Check explicit quiet hours
        if self.explicit_quiet_hours:
            start, end = self.explicit_quiet_hours
            if start <= hour <= end:
                return False

        # Check learned preferences
        score = self.optimal_hours.get(hour, 0.5)
        return score > 0.3  # Threshold for engagement

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "optimal_hours": dict(self.optimal_hours),
            "mode_preferences": dict(self.mode_preferences),
            "prefers_emoji": self.prefers_emoji,
            "prefers_formal": self.prefers_formal,
            "response_length_preference": self.response_length_preference,
            "trigger_sensitivity": self.trigger_sensitivity,
            "explicit_mute": self.explicit_mute,
            "explicit_quiet_hours": self.explicit_quiet_hours,
            "explicit_max_engagements_per_hour": self.explicit_max_engagements_per_hour,
            "total_interactions": self.total_interactions,
            "positive_interactions": self.positive_interactions,
            "last_interaction_time": self.last_interaction_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPreferences":
        """Deserialize from dictionary."""
        prefs = cls(user_id=data["user_id"])
        prefs.optimal_hours = defaultdict(float, data.get("optimal_hours", {}))
        prefs.mode_preferences = defaultdict(float, data.get("mode_preferences", {}))
        prefs.prefers_emoji = data.get("prefers_emoji", 0.5)
        prefs.prefers_formal = data.get("prefers_formal", 0.5)
        prefs.response_length_preference = data.get(
            "response_length_preference", "medium"
        )
        prefs.trigger_sensitivity = data.get("trigger_sensitivity", 0.5)
        prefs.explicit_mute = data.get("explicit_mute", False)
        prefs.explicit_quiet_hours = data.get("explicit_quiet_hours")
        prefs.explicit_max_engagements_per_hour = data.get(
            "explicit_max_engagements_per_hour"
        )
        prefs.total_interactions = data.get("total_interactions", 0)
        prefs.positive_interactions = data.get("positive_interactions", 0)
        prefs.last_interaction_time = data.get("last_interaction_time", 0.0)
        return prefs


class UserAdaptationManager:
    """Manages per-user adaptation and preferences."""

    def __init__(self, storage_dir: str = "data/user_preferences"):
        self.storage_dir = storage_dir
        self._preferences: dict[str, UserPreferences] = {}

    def get_preferences(self, user_id: str) -> UserPreferences:
        """Get or create preferences for user."""
        if user_id not in self._preferences:
            # Try to load existing
            import os

            filepath = f"{self.storage_dir}/{user_id}.json"
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)
                self._preferences[user_id] = UserPreferences.from_dict(data)
            else:
                # Create new
                self._preferences[user_id] = UserPreferences(user_id=user_id)

        return self._preferences[user_id]

    def record_interaction(
        self,
        user_id: str,
        timestamp: float,
        mode: str,
        positive: bool,
    ) -> None:
        """Record an interaction for learning.

        Args:
            user_id: User who interacted
            timestamp: When interaction occurred
            mode: Cognitive mode used
            positive: Whether interaction was positive
        """
        prefs = self.get_preferences(user_id)

        # Extract hour from timestamp
        from datetime import datetime

        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour

        # Update preferences
        prefs.update_timing(hour, positive)
        prefs.update_mode_preference(mode, positive)

        # Update stats
        prefs.total_interactions += 1
        if positive:
            prefs.positive_interactions += 1
        prefs.last_interaction_time = timestamp

        # Update trigger sensitivity based on success rate
        if prefs.total_interactions > 10:
            success_rate = prefs.positive_interactions / prefs.total_interactions
            # Gradually adjust sensitivity
            prefs.trigger_sensitivity = (
                prefs.trigger_sensitivity * 0.9 + success_rate * 0.1
            )

    def set_explicit_preference(
        self,
        user_id: str,
        preference_type: str,
        value: Any,
    ) -> None:
        """Set explicit user preference (overrides learned).

        Args:
            user_id: User to set preference for
            preference_type: Type of preference (mute, quiet_hours, etc.)
            value: Preference value
        """
        prefs = self.get_preferences(user_id)

        if preference_type == "mute":
            prefs.explicit_mute = bool(value)
        elif preference_type == "quiet_hours":
            prefs.explicit_quiet_hours = value  # Tuple (start, end)
        elif preference_type == "max_engagements_per_hour":
            prefs.explicit_max_engagements_per_hour = int(value)
        elif preference_type == "preferred_mode":
            prefs.mode_preferences[value] = 1.0  # Lock in preference
        elif preference_type == "trigger_sensitivity":
            prefs.trigger_sensitivity = float(value)
        elif preference_type == "prefers_emoji":
            prefs.prefers_emoji = float(value)
        elif preference_type == "prefers_formal":
            prefs.prefers_formal = float(value)
        elif preference_type == "response_length":
            prefs.response_length_preference = str(value)

    def get_adapted_trigger_threshold(self, user_id: str) -> float:
        """Get trigger threshold adapted for user.

        Lower threshold = more frequent engagement
        Higher threshold = less frequent engagement
        """
        prefs = self.get_preferences(user_id)

        # Base threshold on sensitivity
        # High sensitivity (1.0) -> low threshold (0.3)
        # Low sensitivity (0.0) -> high threshold (0.8)
        threshold = 0.8 - (prefs.trigger_sensitivity * 0.5)

        return threshold

    def get_optimal_engagement_time(self, user_id: str) -> list[int]:
        """Get optimal hours for engaging user."""
        prefs = self.get_preferences(user_id)
        return prefs.get_best_hours()

    def get_preferred_mode(self, user_id: str) -> str | None:
        """Get preferred cognitive mode for user."""
        prefs = self.get_preferences(user_id)
        return prefs.get_preferred_mode()

    def save_all(self) -> None:
        """Save all user preferences."""
        import os

        os.makedirs(self.storage_dir, exist_ok=True)

        for user_id, prefs in self._preferences.items():
            filepath = f"{self.storage_dir}/{user_id}.json"
            with open(filepath, "w") as f:
                json.dump(prefs.to_dict(), f, indent=2)

    def get_stats(self, user_id: str) -> dict[str, Any]:
        """Get adaptation statistics for user."""
        prefs = self.get_preferences(user_id)
        return {
            "total_interactions": prefs.total_interactions,
            "positive_rate": (
                prefs.positive_interactions / prefs.total_interactions
                if prefs.total_interactions > 0
                else 0
            ),
            "best_hours": prefs.get_best_hours(),
            "preferred_mode": prefs.get_preferred_mode(),
            "trigger_sensitivity": prefs.trigger_sensitivity,
            "communication_style": {
                "emoji": prefs.prefers_emoji,
                "formal": prefs.prefers_formal,
                "length": prefs.response_length_preference,
            },
        }


# Global instance
_adaptation_manager: UserAdaptationManager | None = None


def get_adaptation_manager() -> UserAdaptationManager:
    """Get global adaptation manager."""
    global _adaptation_manager
    if _adaptation_manager is None:
        _adaptation_manager = UserAdaptationManager()
    return _adaptation_manager
