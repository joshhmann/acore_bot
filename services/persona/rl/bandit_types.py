"""Contextual Bandit types and enums for mode switching."""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import List


class ModeSwitchAction(IntEnum):
    """Actions for mode switching bandit."""

    STAY_IN_MODE = 0
    SWITCH_TO_CREATIVE = 1
    SWITCH_TO_LOGIC = 2


@dataclass
class BanditContext:
    """Context features for bandit decisions."""

    sentiment: float = 0.0  # -1.0 to 1.0
    topic: str = ""  # Topic category
    user_history: List[str] = field(default_factory=list)  # Recent interactions
    current_mode: str = "default"  # Current cognitive mode

    def to_feature_vector(self, dim: int = 7) -> List[float]:
        """Convert context to feature vector for LinUCB."""
        # Normalize sentiment to [0, 1]
        sentiment_feat = (self.sentiment + 1.0) / 2.0

        # Simple topic encoding (hash-based, deterministic)
        topic_hash = hash(self.topic) % 1000 / 1000.0 if self.topic else 0.5

        # User history length normalized
        history_len = min(len(self.user_history) / 10.0, 1.0)

        # Current mode encoding
        mode_encoding = {
            "default": 0.0,
            "creative": 0.25,
            "logic": 0.5,
            "analytical": 0.75,
            "focused": 1.0,
        }.get(self.current_mode, 0.0)

        # Build feature vector with safe defaults
        features = [
            sentiment_feat,  # [0]
            topic_hash,  # [1]
            history_len,  # [2]
            mode_encoding,  # [3]
            1.0,  # [4] bias term
            0.0,  # [5] reserved
            0.0,  # [6] reserved
        ]

        # Pad or truncate to requested dimension
        if len(features) < dim:
            features.extend([0.0] * (dim - len(features)))
        return features[:dim]


@dataclass
class BanditConfig:
    """Configuration for contextual bandit."""

    feature_dim: int = 7
    alpha: float = 1.0  # Exploration parameter
    default_reward: float = 0.0
    reply_bonus: float = 1.0
    no_reply_penalty: float = -0.5
