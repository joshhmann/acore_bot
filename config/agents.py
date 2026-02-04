"""Agent orchestration configuration."""

from .base import BaseConfig


class AgentConfig(BaseConfig):
    """Agent orchestration configuration."""

    ROUTING_ENABLED: bool = BaseConfig._get_env_bool("AGENT_ROUTING_ENABLED", True)
    ROUTING_STRATEGY: str = BaseConfig._get_env(
        "AGENT_ROUTING_STRATEGY", "highest_confidence"
    )
    MIN_CONFIDENCE: float = BaseConfig._get_env_float("AGENT_MIN_CONFIDENCE", 0.3)
    CHAINING_ENABLED: bool = BaseConfig._get_env_bool("AGENT_CHAINING_ENABLED", True)
    MAX_CHAIN_LENGTH: int = BaseConfig._get_env_int("AGENT_MAX_CHAIN_LENGTH", 3)
    HEALTH_CHECK_INTERVAL: float = BaseConfig._get_env_float(
        "AGENT_HEALTH_CHECK_INTERVAL", 60.0
    )
    TIMEOUT_SECONDS: float = BaseConfig._get_env_float("AGENT_TIMEOUT_SECONDS", 30.0)
