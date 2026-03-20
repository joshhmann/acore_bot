"""RL package for persona autonomy."""

from .types import RLAction, RLState
from .constants import (
    RL_EPSILON_START,
    RL_EPSILON_END,
    RL_EPSILON_DECAY,
    RL_Q_INIT,
    RL_LEARNING_RATE,
    RL_DISCOUNT_FACTOR,
    RL_PERSIST_INTERVAL,
    RL_LOCK_TIMEOUT,
    RL_MAX_LATENCY_SEC,
    RL_REWARD_SPEED_THRESHOLD,
    RL_REWARD_LONG_MSG_CHAR,
    RL_CONTEXT_MAX_AGE,
    RL_MAX_AGENTS_PER_CHANNEL,
)
from .agent import RLAgent
from .service import RLService

__all__ = [
    "RLAction",
    "RLState",
    "RLAgent",
    "RLService",
    "RL_EPSILON_START",
    "RL_EPSILON_END",
    "RL_EPSILON_DECAY",
    "RL_Q_INIT",
    "RL_LEARNING_RATE",
    "RL_DISCOUNT_FACTOR",
    "RL_PERSIST_INTERVAL",
    "RL_LOCK_TIMEOUT",
    "RL_MAX_LATENCY_SEC",
    "RL_REWARD_SPEED_THRESHOLD",
    "RL_REWARD_LONG_MSG_CHAR",
    "RL_CONTEXT_MAX_AGE",
    "RL_MAX_AGENTS_PER_CHANNEL",
]


# Bandit exports
from .bandit import LinUCBBandit as LinUCBBandit
from .bandit_reward import compute_mode_switch_reward as compute_mode_switch_reward
from .bandit_types import (
    BanditConfig as BanditConfig,
    BanditContext as BanditContext,
    ModeSwitchAction as ModeSwitchAction,
)

__all__.extend([
    "LinUCBBandit",
    "ModeSwitchAction",
    "BanditContext",
    "BanditConfig",
    "compute_mode_switch_reward",
])
