"""Contextual Bandit Learning with LinUCB Algorithm.

Implements Linear Upper Confidence Bound (LinUCB) for learning
optimal trigger decisions based on context.

Actions:
    - wait: Wait for better timing
    - engage_now: Engage immediately
    - ask_clarification: Ask for more information
    - switch_mode: Switch cognitive mode

Context Features:
    - sentiment: Conversation sentiment (-1 to 1)
    - time_of_day: Hour of day (0-23)
    - relationship_depth: How well we know user (0-1)
    - conversation_phase: Beginning/middle/end (0-1)

Reward:
    - User engagement score based on response behavior
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class BanditAction:
    """An action the bandit can take."""

    name: str
    index: int
    theta: np.ndarray = field(repr=False)  # Parameter vector
    A: np.ndarray | None = field(default=None, repr=False)  # Design matrix
    b: np.ndarray | None = field(default=None, repr=False)  # Response vector

    count: int = 0
    total_reward: float = 0.0

    def __post_init__(self):
        """Initialize matrices if not provided."""
        n_features = len(self.theta)
        if self.A is None:
            self.A = np.eye(n_features)
        if self.b is None:
            self.b = np.zeros(n_features)


@dataclass
class BanditContext:
    """Context features for decision making."""

    sentiment: float = 0.0  # -1 (negative) to 1 (positive)
    time_of_day: int = 12  # 0-23
    relationship_depth: float = 0.5  # 0 (new) to 1 (close)
    conversation_phase: float = 0.5  # 0 (start) to 1 (end)
    user_active: bool = True  # Is user currently active
    recent_engagement: float = 0.5  # Recent engagement level

    def to_vector(self) -> np.ndarray:
        """Convert context to feature vector."""
        # Normalize time to [0, 1] with sin/cos encoding
        time_norm = self.time_of_day / 24.0
        time_sin = np.sin(2 * np.pi * time_norm)
        time_cos = np.cos(2 * np.pi * time_norm)

        return np.array(
            [
                self.sentiment,
                time_sin,
                time_cos,
                self.relationship_depth,
                self.conversation_phase,
                1.0 if self.user_active else 0.0,
                self.recent_engagement,
                1.0,  # Bias term
            ]
        )


class LinUCB:
    """Linear Upper Confidence Bound bandit algorithm.

    Learns optimal actions based on context using linear regression
    with exploration via confidence bounds.

    Reference:
        Li et al. "A Contextual-Bandit Approach to Personalized News Article Recommendation"
        https://arxiv.org/abs/1003.0146
    """

    ACTIONS = ["wait", "engage_now", "ask_clarification", "switch_mode"]

    def __init__(
        self,
        n_features: int = 8,
        alpha: float = 1.0,  # Exploration parameter
        user_id: str | None = None,
    ):
        self.n_features = n_features
        self.alpha = alpha
        self.user_id = user_id

        # Initialize actions
        self.actions: dict[str, BanditAction] = {}
        for i, name in enumerate(self.ACTIONS):
            self.actions[name] = BanditAction(
                name=name,
                index=i,
                theta=np.zeros(n_features),
            )

        # Statistics
        self.total_rounds = 0
        self.total_reward = 0.0
        self.history: list[dict[str, Any]] = []

    def select_action(self, context: BanditContext) -> tuple[str, float]:
        """Select action using LinUCB algorithm.

        Args:
            context: Current context

        Returns:
            Tuple of (action_name, confidence)
        """
        x = context.to_vector()

        best_action = None
        best_ucb = -float("inf")

        for name, action in self.actions.items():
            # Compute parameter estimate
            theta = np.linalg.solve(action.A, action.b)

            # Compute predicted reward
            pred_reward = np.dot(theta, x)

            # Compute confidence interval
            # UCB = x^T theta + alpha * sqrt(x^T A^{-1} x)
            A_inv = np.linalg.inv(action.A)
            uncertainty = np.sqrt(np.dot(x, np.dot(A_inv, x)))
            ucb = pred_reward + self.alpha * uncertainty

            if ucb > best_ucb:
                best_ucb = ucb
                best_action = action

        # Calculate confidence
        confidence = min(1.0, best_ucb / (1 + self.alpha))

        return best_action.name, confidence

    def update(
        self,
        action_name: str,
        context: BanditContext,
        reward: float,
    ) -> None:
        """Update bandit with observed reward.

        Args:
            action_name: Action that was taken
            context: Context when action was taken
            reward: Observed reward (-1 to 1)
        """
        if action_name not in self.actions:
            raise ValueError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        x = context.to_vector()

        # Update design matrix and response vector
        action.A += np.outer(x, x)
        action.b += reward * x

        # Update statistics
        action.count += 1
        action.total_reward += reward
        self.total_rounds += 1
        self.total_reward += reward

        # Record history
        self.history.append(
            {
                "timestamp": time.time(),
                "action": action_name,
                "context": {
                    "sentiment": context.sentiment,
                    "time_of_day": context.time_of_day,
                    "relationship_depth": context.relationship_depth,
                    "conversation_phase": context.conversation_phase,
                },
                "reward": reward,
            }
        )

        # Limit history size
        if len(self.history) > 10000:
            self.history = self.history[-5000:]

    def calculate_reward(
        self,
        user_responded: bool,
        response_time_seconds: float | None = None,
        response_quality: float = 0.5,  # Estimated quality
    ) -> float:
        """Calculate reward from user behavior.

        Args:
            user_responded: Did user respond
            response_time_seconds: How long until response
            response_quality: Quality of response (0-1)

        Returns:
            Reward value (-1 to 1)
        """
        if not user_responded:
            return -0.5  # Ignored

        # Base reward for response
        reward = 0.5

        # Bonus for quick response (< 5 minutes)
        if response_time_seconds and response_time_seconds < 300:
            reward += 0.3
        elif response_time_seconds and response_time_seconds < 900:
            reward += 0.1

        # Factor in response quality
        reward += response_quality * 0.2

        return min(1.0, reward)

    def get_action_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for each action."""
        stats = {}
        for name, action in self.actions.items():
            avg_reward = action.total_reward / action.count if action.count > 0 else 0
            stats[name] = {
                "count": action.count,
                "total_reward": round(action.total_reward, 2),
                "avg_reward": round(avg_reward, 3),
            }
        return stats

    def get_performance(self) -> dict[str, Any]:
        """Get bandit performance metrics."""
        avg_reward = (
            self.total_reward / self.total_rounds if self.total_rounds > 0 else 0
        )
        return {
            "total_rounds": self.total_rounds,
            "total_reward": round(self.total_reward, 2),
            "avg_reward": round(avg_reward, 3),
            "action_stats": self.get_action_stats(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize bandit state to dictionary."""
        return {
            "user_id": self.user_id,
            "n_features": self.n_features,
            "alpha": self.alpha,
            "total_rounds": self.total_rounds,
            "total_reward": self.total_reward,
            "actions": {
                name: {
                    "A": action.A.tolist(),
                    "b": action.b.tolist(),
                    "count": action.count,
                    "total_reward": action.total_reward,
                }
                for name, action in self.actions.items()
            },
            "history": self.history[-1000:],  # Last 1000 entries
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinUCB":
        """Restore bandit from dictionary."""
        bandit = cls(
            n_features=data.get("n_features", 8),
            alpha=data.get("alpha", 1.0),
            user_id=data.get("user_id"),
        )

        bandit.total_rounds = data.get("total_rounds", 0)
        bandit.total_reward = data.get("total_reward", 0.0)
        bandit.history = data.get("history", [])

        # Restore action states
        for name, action_data in data.get("actions", {}).items():
            if name in bandit.actions:
                action = bandit.actions[name]
                action.A = np.array(action_data["A"])
                action.b = np.array(action_data["b"])
                action.count = action_data.get("count", 0)
                action.total_reward = action_data.get("total_reward", 0.0)

        return bandit

    def save(self, filepath: str) -> None:
        """Save bandit state to file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, filepath: str) -> "LinUCB":
        """Load bandit state from file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)


class UserBanditManager:
    """Manages per-user bandit instances."""

    def __init__(self, storage_dir: str = "data/bandits"):
        self.storage_dir = storage_dir
        self._bandits: dict[str, LinUCB] = {}

    def get_bandit(self, user_id: str) -> LinUCB:
        """Get or create bandit for user."""
        if user_id not in self._bandits:
            # Try to load existing
            import os

            filepath = f"{self.storage_dir}/{user_id}.json"
            if os.path.exists(filepath):
                self._bandits[user_id] = LinUCB.load(filepath)
            else:
                # Create new
                self._bandits[user_id] = LinUCB(user_id=user_id)

        return self._bandits[user_id]

    def save_all(self) -> None:
        """Save all bandit states."""
        import os

        os.makedirs(self.storage_dir, exist_ok=True)

        for user_id, bandit in self._bandits.items():
            filepath = f"{self.storage_dir}/{user_id}.json"
            bandit.save(filepath)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all users."""
        return {
            user_id: bandit.get_performance()
            for user_id, bandit in self._bandits.items()
        }
