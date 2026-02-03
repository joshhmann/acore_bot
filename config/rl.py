"""RL (Reinforcement Learning) configuration."""

from pathlib import Path
from .base import BaseConfig


class RLConfig(BaseConfig):
    """RL autonomy system configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("RL_ENABLED", False)
    DATA_DIR: Path = BaseConfig._get_env_path("RL_DATA_DIR", "./data/rl")

    # Epsilon-Greedy parameters
    EPSILON_START: float = BaseConfig._get_env_float("RL_EPSILON_START", 1.0)
    EPSILON_END: float = BaseConfig._get_env_float("RL_EPSILON_END", 0.01)
    EPSILON_DECAY: float = BaseConfig._get_env_float("RL_EPSILON_DECAY", 0.9995)

    # Q-Learning parameters
    Q_INIT: float = BaseConfig._get_env_float("RL_Q_INIT", 10.0)
    LEARNING_RATE: float = BaseConfig._get_env_float("RL_LEARNING_RATE", 0.1)
    DISCOUNT_FACTOR: float = BaseConfig._get_env_float("RL_DISCOUNT_FACTOR", 0.9)

    # Service parameters
    PERSIST_INTERVAL: int = BaseConfig._get_env_int("RL_PERSIST_INTERVAL", 60)
    LOCK_TIMEOUT: float = BaseConfig._get_env_float("RL_LOCK_TIMEOUT", 0.050)
    MAX_LATENCY_SEC: float = BaseConfig._get_env_float("RL_MAX_LATENCY_SEC", 0.050)

    # Reward calculation parameters
    REWARD_SPEED_THRESHOLD: float = BaseConfig._get_env_float(
        "RL_REWARD_SPEED_THRESHOLD", 60.0
    )
    REWARD_LONG_MSG_CHAR: int = BaseConfig._get_env_int("RL_REWARD_LONG_MSG_CHAR", 100)
    CONTEXT_MAX_AGE: int = BaseConfig._get_env_int("RL_CONTEXT_MAX_AGE", 3600)
    MAX_AGENTS_PER_CHANNEL: int = BaseConfig._get_env_int(
        "RL_MAX_AGENTS_PER_CHANNEL", 100
    )
