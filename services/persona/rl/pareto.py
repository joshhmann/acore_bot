"""Pareto frontier action selection for multi-objective RL.

This module implements Pareto-optimal action selection, enabling the agent
to balance multiple reward objectives (engagement, quality, affinity, curiosity)
when choosing actions.

Pareto Dominance:
    Action A dominates Action B if:
    - A is >= B in ALL objectives
    - A is > B in AT LEAST ONE objective

The Pareto frontier contains all non-dominated actions.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .constants import (
    REWARD_WEIGHT_ENGAGEMENT,
    REWARD_WEIGHT_QUALITY,
    REWARD_WEIGHT_AFFINITY,
    REWARD_WEIGHT_CURIOSITY,
)
from .types import RLAction


# Default weights for multi-objective optimization
DEFAULT_WEIGHTS: Dict[str, float] = {
    "engagement": REWARD_WEIGHT_ENGAGEMENT,
    "quality": REWARD_WEIGHT_QUALITY,
    "affinity": REWARD_WEIGHT_AFFINITY,
    "curiosity": REWARD_WEIGHT_CURIOSITY,
}

# Objective names for validation
OBJECTIVE_NAMES = frozenset(["engagement", "quality", "affinity", "curiosity"])


@dataclass
class ActionProfile:
    """Action with its multi-objective Q-values.

    Attributes:
        action: The RL action (WAIT, REACT, ENGAGE, INITIATE)
        q_values: Dictionary mapping objective names to Q-values
    """

    action: RLAction
    q_values: Dict[str, float]

    def dominates(self, other: "ActionProfile") -> bool:
        """Check if this action Pareto-dominates another.

        An action A dominates B if:
        - A >= B in all objectives
        - A > B in at least one objective

        Args:
            other: The ActionProfile to compare against

        Returns:
            True if this action dominates the other
        """
        if not self.q_values or not other.q_values:
            return False

        # Get common objectives
        common_objectives = set(self.q_values.keys()) & set(other.q_values.keys())
        if not common_objectives:
            return False

        at_least_one_strictly_better = False

        for obj in common_objectives:
            self_val = self.q_values[obj]
            other_val = other.q_values[obj]

            if self_val < other_val:
                # Worse in at least one objective -> doesn't dominate
                return False
            if self_val > other_val:
                at_least_one_strictly_better = True

        return at_least_one_strictly_better

    def weighted_sum(self, weights: Dict[str, float]) -> float:
        """Calculate weighted sum of Q-values.

        Args:
            weights: Dictionary mapping objective names to weights

        Returns:
            Weighted sum of Q-values
        """
        total = 0.0
        for obj, q_val in self.q_values.items():
            total += q_val * weights.get(obj, 0.0)
        return total

    def min_q_value(self) -> float:
        """Get minimum Q-value across all objectives.

        Returns:
            Minimum Q-value, or negative infinity if no Q-values
        """
        if not self.q_values:
            return float("-inf")
        return min(self.q_values.values())


class ParetoSelector:
    """Pareto frontier action selection for multi-objective RL.

    Supports multiple selection strategies:
    - weighted_sum: Select action with highest weighted sum of Q-values
    - pareto_epsilon: Epsilon-greedy selection from Pareto frontier
    - maximin: Select action that maximizes minimum objective (fairness)

    Attributes:
        strategy: The selection strategy to use
        weights: Dictionary mapping objective names to weights
    """

    VALID_STRATEGIES = frozenset(["weighted_sum", "pareto_epsilon", "maximin"])

    def __init__(
        self,
        strategy: str = "weighted_sum",
        weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the Pareto selector.

        Args:
            strategy: Selection strategy ("weighted_sum", "pareto_epsilon", "maximin")
            weights: Optional custom weights. If None, uses DEFAULT_WEIGHTS.

        Raises:
            ValueError: If strategy is not recognized
        """
        if strategy not in self.VALID_STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Valid: {self.VALID_STRATEGIES}"
            )

        self.strategy = strategy
        self.weights = weights if weights is not None else DEFAULT_WEIGHTS.copy()

        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def find_pareto_frontier(
        self, action_profiles: List[ActionProfile]
    ) -> List[ActionProfile]:
        """Find all non-dominated actions (Pareto frontier).

        An action is on the Pareto frontier if no other action dominates it.

        Time complexity: O(n^2) where n is number of actions.
        For small action spaces (4 actions), this is negligible (<1ms).

        Args:
            action_profiles: List of ActionProfile to evaluate

        Returns:
            List of non-dominated ActionProfiles (Pareto frontier)
        """
        if not action_profiles:
            return []

        if len(action_profiles) == 1:
            return action_profiles.copy()

        frontier: List[ActionProfile] = []

        for candidate in action_profiles:
            is_dominated = False

            for other in action_profiles:
                if other is candidate:
                    continue
                if other.dominates(candidate):
                    is_dominated = True
                    break

            if not is_dominated:
                frontier.append(candidate)

        return frontier

    def select_action(
        self,
        action_profiles: List[ActionProfile],
        epsilon: float = 0.0,
    ) -> RLAction:
        """Select an action using the configured strategy.

        Args:
            action_profiles: List of ActionProfile to choose from
            epsilon: Exploration rate for pareto_epsilon strategy

        Returns:
            Selected RLAction

        Raises:
            ValueError: If action_profiles is empty or strategy is unknown
        """
        if not action_profiles:
            raise ValueError("action_profiles cannot be empty")

        if self.strategy == "weighted_sum":
            return self._weighted_sum_selection(action_profiles)
        elif self.strategy == "pareto_epsilon":
            return self._pareto_epsilon_selection(action_profiles, epsilon)
        elif self.strategy == "maximin":
            return self._maximin_selection(action_profiles)
        else:
            # Should never reach here due to __init__ validation
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def _weighted_sum_selection(self, action_profiles: List[ActionProfile]) -> RLAction:
        """Select action with highest weighted sum of Q-values.

        Args:
            action_profiles: List of ActionProfile to choose from

        Returns:
            RLAction with highest weighted sum
        """
        best_action = action_profiles[0].action
        best_score = action_profiles[0].weighted_sum(self.weights)

        for profile in action_profiles[1:]:
            score = profile.weighted_sum(self.weights)
            if score > best_score:
                best_score = score
                best_action = profile.action

        return best_action

    def _pareto_epsilon_selection(
        self,
        action_profiles: List[ActionProfile],
        epsilon: float,
    ) -> RLAction:
        """Epsilon-greedy selection from Pareto frontier.

        With probability epsilon: Random action from Pareto frontier
        Otherwise: Best action from frontier (by weighted sum)

        Args:
            action_profiles: List of ActionProfile to choose from
            epsilon: Exploration rate (0.0 to 1.0)

        Returns:
            Selected RLAction
        """
        frontier = self.find_pareto_frontier(action_profiles)

        if not frontier:
            # Fallback to weighted sum on all actions
            return self._weighted_sum_selection(action_profiles)

        if random.random() < epsilon:
            # Explore: random action from frontier
            return random.choice(frontier).action
        else:
            # Exploit: best from frontier by weighted sum
            return self._weighted_sum_selection(frontier)

    def _maximin_selection(self, action_profiles: List[ActionProfile]) -> RLAction:
        """Select action that maximizes minimum objective value.

        This strategy prioritizes fairness across objectives,
        ensuring no single objective is severely neglected.

        Args:
            action_profiles: List of ActionProfile to choose from

        Returns:
            RLAction with highest minimum Q-value
        """
        best_action = action_profiles[0].action
        best_min_value = action_profiles[0].min_q_value()

        for profile in action_profiles[1:]:
            min_value = profile.min_q_value()
            if min_value > best_min_value:
                best_min_value = min_value
                best_action = profile.action

        return best_action

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update the objective weights.

        Weights are automatically normalized to sum to 1.0.

        Args:
            weights: Dictionary mapping objective names to weights
        """
        total = sum(weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in weights.items()}
        else:
            self.weights = DEFAULT_WEIGHTS.copy()

    def set_strategy(self, strategy: str) -> None:
        """Change the selection strategy.

        Args:
            strategy: New strategy ("weighted_sum", "pareto_epsilon", "maximin")

        Raises:
            ValueError: If strategy is not recognized
        """
        if strategy not in self.VALID_STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Valid: {self.VALID_STRATEGIES}"
            )
        self.strategy = strategy

    def get_weights(self) -> Dict[str, float]:
        """Get current objective weights.

        Returns:
            Copy of the weights dictionary
        """
        return self.weights.copy()


def create_action_profiles_from_q_matrix(
    q_matrix: Dict[RLAction, Dict[str, float]],
) -> List[ActionProfile]:
    """Helper to create ActionProfiles from a Q-value matrix.

    Args:
        q_matrix: Dictionary mapping RLAction to objective Q-values

    Returns:
        List of ActionProfile instances
    """
    return [
        ActionProfile(action=action, q_values=q_vals)
        for action, q_vals in q_matrix.items()
    ]
