"""RL Agent with Q-table and Bellman update logic."""

import random
import logging
from typing import Dict

from .types import RLAction, RLState
from .constants import (
    RL_EPSILON_START,
    RL_EPSILON_END,
    RL_EPSILON_DECAY,
    RL_Q_INIT,
    RL_LEARNING_RATE,
    RL_DISCOUNT_FACTOR,
)

logger = logging.getLogger(__name__)


class RLAgent:
    """Tabular Q-Learning agent for persona autonomy."""

    def __init__(
        self,
        epsilon: float = RL_EPSILON_START,
        epsilon_end: float = RL_EPSILON_END,
        epsilon_decay: float = RL_EPSILON_DECAY,
        q_init: float = RL_Q_INIT,
        learning_rate: float = RL_LEARNING_RATE,
        discount_factor: float = RL_DISCOUNT_FACTOR,
    ):
        self.epsilon = epsilon
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.q_init = q_init
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor

        self.q_table: Dict[RLState, Dict[RLAction, float]] = {}
        self.dirty = False

    def _get_q_row(self, state: RLState) -> Dict[RLAction, float]:
        if state not in self.q_table:
            self.q_table[state] = {action: self.q_init for action in RLAction}
        return self.q_table[state]

    def select_action(self, state: RLState) -> RLAction:
        q_row = self._get_q_row(state)

        if random.random() < self.epsilon:
            action = random.choice(list(RLAction))
        else:
            action = max(q_row.keys(), key=lambda a: q_row[a])

        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        return action

    def update(
        self,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState,
    ) -> None:
        q_row = self._get_q_row(state)
        old_q = q_row[action]

        next_q_row = self._get_q_row(next_state)
        max_next_q = max(next_q_row.values())

        new_q = old_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - old_q
        )

        q_row[action] = new_q
        self.dirty = True

    def get_action(self, state: RLState) -> RLAction:
        return self.select_action(state)

    def to_dict(self) -> dict:
        return {
            "epsilon": self.epsilon,
            "q_table": {
                str(k): {str(int(a)): v for a, v in q_row.items()}
                for k, q_row in self.q_table.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RLAgent":
        agent = cls(
            epsilon=data.get("epsilon", RL_EPSILON_START),
        )

        q_table_data = data.get("q_table", {})
        for state_str, q_row_data in q_table_data.items():
            try:
                import ast

                state = ast.literal_eval(state_str)
                if not isinstance(state, tuple) or len(state) != 3:
                    continue
                q_row = {}
                for action_str, q_value in q_row_data.items():
                    action = RLAction(int(action_str))
                    q_row[action] = q_value
                agent.q_table[state] = q_row
            except (SyntaxError, ValueError, TypeError):
                logger.warning(f"Failed to parse state: {state_str}")
                continue

        return agent
