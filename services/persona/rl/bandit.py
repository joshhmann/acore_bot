"""LinUCB Contextual Bandit implementation for mode switching."""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from .bandit_types import ModeSwitchAction, BanditContext, BanditConfig

logger = logging.getLogger(__name__)


@dataclass
class BanditState:
    """Serializable state for LinUCB bandit."""

    A: List[List[float]] = field(default_factory=list)  # d x d matrix
    b: List[float] = field(default_factory=list)  # d-dimensional vector
    theta: List[float] = field(default_factory=list)  # d-dimensional weights
    counts: List[int] = field(default_factory=list)  # Action counts

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "A": self.A,
            "b": self.b,
            "theta": self.theta,
            "counts": self.counts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BanditState":
        """Create from dictionary."""
        return cls(
            A=data.get("A", []),
            b=data.get("b", []),
            theta=data.get("theta", []),
            counts=data.get("counts", []),
        )


class LinUCBBandit:
    """LinUCB contextual bandit for mode switching decisions."""

    def __init__(self, config: Optional[BanditConfig] = None):
        """Initialize LinUCB bandit.

        Args:
            config: Bandit configuration
        """
        self.config = config or BanditConfig()
        self.d = self.config.feature_dim
        self.n_actions = len(ModeSwitchAction)

        # Initialize parameters for each action
        # A[a]: d x d matrix (inverse covariance)
        # b[a]: d-dimensional vector (linear term)
        # theta[a]: d-dimensional weight vector (computed from A^-1 * b)
        self.A: Dict[int, np.ndarray] = {}
        self.b: Dict[int, np.ndarray] = {}
        self.theta: Dict[int, np.ndarray] = {}
        self.counts: Dict[int, int] = {}

        self._init_params()

    def _init_params(self) -> None:
        """Initialize bandit parameters."""
        for action in ModeSwitchAction:
            self.A[action.value] = np.eye(self.d)  # Identity matrix
            self.b[action.value] = np.zeros(self.d)
            self.theta[action.value] = np.zeros(self.d)
            self.counts[action.value] = 0

    def select_action(self, context: BanditContext) -> Tuple[ModeSwitchAction, float]:
        """Select action using LinUCB algorithm.

        Args:
            context: Current context features

        Returns:
            Tuple of (selected action, confidence bound)
        """
        x = np.array(context.to_feature_vector(self.d))  # Context feature vector

        # Compute UCB for each action
        ucb_values = {}
        for action in ModeSwitchAction:
            a_idx = action.value
            A_inv = np.linalg.inv(self.A[a_idx])
            self.theta[a_idx] = A_inv @ self.b[a_idx]

            # Estimated reward: theta^T * x
            estimated_reward = self.theta[a_idx].T @ x

            # Confidence interval: alpha * sqrt(x^T * A^-1 * x)
            confidence = self.config.alpha * np.sqrt(x.T @ A_inv @ x)

            # UCB = estimated_reward + confidence
            ucb_values[action] = estimated_reward + confidence

        # Select action with highest UCB
        best_action = max(ucb_values.keys(), key=lambda a: ucb_values[a])
        best_ucb = ucb_values[best_action]

        logger.debug(f"Bandit selected {best_action.name} with UCB={best_ucb:.3f}")
        return best_action, float(best_ucb)

    def update(
        self, action: ModeSwitchAction, context: BanditContext, reward: float
    ) -> None:
        """Update bandit parameters after observing reward.

        Args:
            action: Action that was taken
            context: Context when action was taken
            reward: Observed reward
        """
        x = np.array(context.to_feature_vector(self.d))
        a_idx = action.value

        # Update A and b for the selected action
        # A[a] = A[a] + x * x^T
        # b[a] = b[a] + reward * x
        self.A[a_idx] += np.outer(x, x)
        self.b[a_idx] += reward * x
        self.counts[a_idx] += 1

        # Recompute theta
        A_inv = np.linalg.inv(self.A[a_idx])
        self.theta[a_idx] = A_inv @ self.b[a_idx]

        logger.debug(f"Bandit updated {action.name} with reward={reward:.3f}")

    def get_state(self) -> BanditState:
        """Get current bandit state for persistence."""
        return BanditState(
            A=[self.A[a].tolist() for a in range(self.n_actions)],
            b=[self.b[a].tolist() for a in range(self.n_actions)],
            theta=[self.theta[a].tolist() for a in range(self.n_actions)],
            counts=[self.counts[a] for a in range(self.n_actions)],
        )

    def set_state(self, state: BanditState) -> None:
        """Restore bandit state from persistence."""
        if not state.A or not state.b:
            logger.warning("Empty bandit state, using defaults")
            self._init_params()
            return

        try:
            for a in range(self.n_actions):
                if a < len(state.A):
                    self.A[a] = np.array(state.A[a])
                    self.b[a] = np.array(state.b[a])
                    self.theta[a] = (
                        np.array(state.theta[a])
                        if a < len(state.theta)
                        else np.zeros(self.d)
                    )
                    self.counts[a] = state.counts[a] if a < len(state.counts) else 0
                else:
                    self.A[a] = np.eye(self.d)
                    self.b[a] = np.zeros(self.d)
                    self.theta[a] = np.zeros(self.d)
                    self.counts[a] = 0
        except (IndexError, ValueError) as e:
            logger.error(f"Failed to load bandit state: {e}, using defaults")
            self._init_params()

    def get_stats(self) -> Dict[str, any]:
        """Get bandit statistics for monitoring."""
        total_pulls = sum(self.counts.values())
        return {
            "total_pulls": total_pulls,
            "action_counts": {
                ModeSwitchAction(a).name: self.counts[a] for a in range(self.n_actions)
            },
            "action_probs": {
                ModeSwitchAction(a).name: self.counts[a] / max(total_pulls, 1)
                for a in range(self.n_actions)
            },
        }
