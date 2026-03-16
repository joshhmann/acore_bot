"""Cross-Modal Style Learning.

Learns mapping from (CognitiveMode + SocialContext) to action style.
Applies to:
- Text: emoji usage, formatting, tone
- VRM: gesture expressiveness, animation style

Tracks user reactions to learn preferred styles.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleProfile:
    """Style profile for a specific mode."""

    # Text styles
    emoji_frequency: float = 0.5  # 0 (none) to 1 (lots)
    formatting_level: float = 0.5  # 0 (plain) to 1 (rich)
    enthusiasm: float = 0.5  # 0 (calm) to 1 (excited)

    # VRM styles (for future VRM integration)
    gesture_expressiveness: float = 0.5  # 0 (minimal) to 1 (expressive)
    animation_speed: float = 0.5  # 0 (slow) to 1 (fast)
    facial_expression_intensity: float = 0.5  # 0 (subtle) to 1 (intense)

    # Success tracking
    usage_count: int = 0
    positive_reactions: int = 0
    negative_reactions: int = 0

    def get_score(self) -> float:
        """Calculate style success score."""
        if self.usage_count == 0:
            return 0.5
        return (self.positive_reactions - self.negative_reactions) / self.usage_count


@dataclass
class UserStylePreferences:
    """Cross-modal style preferences for a user."""

    user_id: str

    # Per-mode style profiles
    creative_style: StyleProfile = field(default_factory=StyleProfile)
    logic_style: StyleProfile = field(default_factory=StyleProfile)
    facilitator_style: StyleProfile = field(default_factory=StyleProfile)

    # Context-specific overrides
    context_styles: dict[str, StyleProfile] = field(default_factory=dict)

    # General preferences
    preferred_text_length: str = "medium"  # short/medium/long
    code_formatting: bool = True
    use_markdown: bool = True

    def get_style_for_mode(self, mode: str) -> StyleProfile:
        """Get style profile for a cognitive mode."""
        mode = mode.lower()
        if mode == "creative":
            return self.creative_style
        elif mode == "logic":
            return self.logic_style
        elif mode == "facilitator":
            return self.facilitator_style
        else:
            return self.creative_style  # Default

    def update_style(
        self,
        mode: str,
        feedback: float,  # -1 to 1
        text_features: dict[str, Any] | None = None,
    ) -> None:
        """Update style based on feedback."""
        style = self.get_style_for_mode(mode)
        style.usage_count += 1

        if feedback > 0:
            style.positive_reactions += 1
        elif feedback < 0:
            style.negative_reactions += 1

        # Adjust style based on feedback and observed features
        if text_features:
            self._adjust_from_features(style, text_features, feedback)

    def _adjust_from_features(
        self,
        style: StyleProfile,
        features: dict[str, Any],
        feedback: float,
    ) -> None:
        """Adjust style based on observed text features."""
        alpha = 0.1 * abs(feedback)  # Learning rate scaled by feedback strength

        # Emoji frequency
        if "emoji_count" in features and "total_words" in features:
            observed_emoji_freq = features["emoji_count"] / max(
                features["total_words"], 1
            )
            style.emoji_frequency = style.emoji_frequency * (
                1 - alpha
            ) + observed_emoji_freq * alpha * (1 if feedback > 0 else -1)
            style.emoji_frequency = max(0.0, min(1.0, style.emoji_frequency))

        # Enthusiasm (exclamation marks, caps, etc.)
        if "enthusiasm_score" in features:
            style.enthusiasm = style.enthusiasm * (1 - alpha) + features[
                "enthusiasm_score"
            ] * alpha * (1 if feedback > 0 else -1)
            style.enthusiasm = max(0.0, min(1.0, style.enthusiasm))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""

        def style_to_dict(s: StyleProfile) -> dict:
            return {
                "emoji_frequency": s.emoji_frequency,
                "formatting_level": s.formatting_level,
                "enthusiasm": s.enthusiasm,
                "gesture_expressiveness": s.gesture_expressiveness,
                "animation_speed": s.animation_speed,
                "facial_expression_intensity": s.facial_expression_intensity,
                "usage_count": s.usage_count,
                "positive_reactions": s.positive_reactions,
                "negative_reactions": s.negative_reactions,
            }

        return {
            "user_id": self.user_id,
            "creative_style": style_to_dict(self.creative_style),
            "logic_style": style_to_dict(self.logic_style),
            "facilitator_style": style_to_dict(self.facilitator_style),
            "preferred_text_length": self.preferred_text_length,
            "code_formatting": self.code_formatting,
            "use_markdown": self.use_markdown,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserStylePreferences":
        """Deserialize from dictionary."""
        prefs = cls(user_id=data["user_id"])

        def dict_to_style(d: dict) -> StyleProfile:
            s = StyleProfile()
            s.emoji_frequency = d.get("emoji_frequency", 0.5)
            s.formatting_level = d.get("formatting_level", 0.5)
            s.enthusiasm = d.get("enthusiasm", 0.5)
            s.gesture_expressiveness = d.get("gesture_expressiveness", 0.5)
            s.animation_speed = d.get("animation_speed", 0.5)
            s.facial_expression_intensity = d.get("facial_expression_intensity", 0.5)
            s.usage_count = d.get("usage_count", 0)
            s.positive_reactions = d.get("positive_reactions", 0)
            s.negative_reactions = d.get("negative_reactions", 0)
            return s

        prefs.creative_style = dict_to_style(data.get("creative_style", {}))
        prefs.logic_style = dict_to_style(data.get("logic_style", {}))
        prefs.facilitator_style = dict_to_style(data.get("facilitator_style", {}))
        prefs.preferred_text_length = data.get("preferred_text_length", "medium")
        prefs.code_formatting = data.get("code_formatting", True)
        prefs.use_markdown = data.get("use_markdown", True)

        return prefs


class CrossModalStyleLearner:
    """Learns cross-modal style preferences from user interactions."""

    def __init__(self, storage_dir: str = "data/style_preferences"):
        self.storage_dir = storage_dir
        self._preferences: dict[str, UserStylePreferences] = {}

    def get_preferences(self, user_id: str) -> UserStylePreferences:
        """Get or create style preferences for user."""
        if user_id not in self._preferences:
            # Try to load existing
            import os

            filepath = f"{self.storage_dir}/{user_id}.json"
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)
                self._preferences[user_id] = UserStylePreferences.from_dict(data)
            else:
                # Create new
                self._preferences[user_id] = UserStylePreferences(user_id=user_id)

        return self._preferences[user_id]

    def record_response(
        self,
        user_id: str,
        mode: str,
        response_text: str,
    ) -> None:
        """Record a response for style analysis."""
        prefs = self.get_preferences(user_id)
        style = prefs.get_style_for_mode(mode)

        # Analyze text features
        features = self._analyze_text(response_text)

        # Update style with observed features (neutral update)
        style.usage_count += 1
        prefs._adjust_from_features(style, features, 0.0)

    def record_feedback(
        self,
        user_id: str,
        mode: str,
        feedback: float,  # -1 to 1
        response_text: str | None = None,
    ) -> None:
        """Record feedback about a response style."""
        prefs = self.get_preferences(user_id)

        features = None
        if response_text:
            features = self._analyze_text(response_text)

        prefs.update_style(mode, feedback, features)

    def _analyze_text(self, text: str) -> dict[str, Any]:
        """Analyze text for style features."""
        words = text.split()

        # Count emojis (simple heuristic: non-ASCII chars)
        emoji_count = sum(1 for c in text if ord(c) > 127)

        # Enthusiasm markers
        exclamation_count = text.count("!")
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)

        # Calculate enthusiasm score
        enthusiasm = min(1.0, (exclamation_count + caps_words) / max(len(words), 1))

        return {
            "emoji_count": emoji_count,
            "total_words": len(words),
            "enthusiasm_score": enthusiasm,
            "has_code_blocks": "```" in text,
            "has_markdown": any(c in text for c in ["**", "*", "`", "#"]),
        }

    def apply_style(
        self,
        user_id: str,
        mode: str,
        base_response: str,
    ) -> str:
        """Apply learned style to a response.

        Currently a placeholder - real implementation would
        adjust formatting, add emoji, etc. based on preferences.
        """
        prefs = self.get_preferences(user_id)
        style = prefs.get_style_for_mode(mode)

        # Simple example: add emoji if preferred
        if style.emoji_frequency > 0.7 and not any(ord(c) > 127 for c in base_response):
            # Could add emoji based on sentiment
            pass

        return base_response

    def get_style_recommendation(
        self,
        user_id: str,
        mode: str,
    ) -> dict[str, Any]:
        """Get style recommendations for a user and mode."""
        prefs = self.get_preferences(user_id)
        style = prefs.get_style_for_mode(mode)

        return {
            "use_emoji": style.emoji_frequency > 0.5,
            "emoji_frequency": style.emoji_frequency,
            "enthusiasm": style.enthusiasm,
            "gesture_expressiveness": style.gesture_expressiveness,
            "text_length": prefs.preferred_text_length,
            "use_markdown": prefs.use_markdown,
            "success_score": style.get_score(),
        }

    def save_all(self) -> None:
        """Save all style preferences."""
        import os

        os.makedirs(self.storage_dir, exist_ok=True)

        for user_id, prefs in self._preferences.items():
            filepath = f"{self.storage_dir}/{user_id}.json"
            with open(filepath, "w") as f:
                json.dump(prefs.to_dict(), f, indent=2)


# Global instance
_style_learner: CrossModalStyleLearner | None = None


def get_style_learner() -> CrossModalStyleLearner:
    """Get global style learner."""
    global _style_learner
    if _style_learner is None:
        _style_learner = CrossModalStyleLearner()
    return _style_learner
