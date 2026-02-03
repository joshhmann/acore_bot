"""Feature toggles and miscellaneous settings."""

from pathlib import Path
from .base import BaseConfig


class MemoryConfig(BaseConfig):
    """Memory management configuration."""

    CLEANUP_ENABLED: bool = BaseConfig._get_env_bool("MEMORY_CLEANUP_ENABLED", True)
    CLEANUP_INTERVAL_HOURS: int = BaseConfig._get_env_int(
        "MEMORY_CLEANUP_INTERVAL_HOURS", 6
    )
    MAX_TEMP_FILE_AGE_HOURS: int = BaseConfig._get_env_int(
        "MAX_TEMP_FILE_AGE_HOURS", 24
    )
    MAX_HISTORY_AGE_DAYS: int = BaseConfig._get_env_int("MAX_HISTORY_AGE_DAYS", 30)


class ConversationConfig(BaseConfig):
    """Conversation settings."""

    SUMMARIZATION_ENABLED: bool = BaseConfig._get_env_bool(
        "CONVERSATION_SUMMARIZATION_ENABLED", True
    )
    AUTO_SUMMARIZE_THRESHOLD: int = BaseConfig._get_env_int(
        "AUTO_SUMMARIZE_THRESHOLD", 30
    )
    STORE_SUMMARIES_IN_RAG: bool = BaseConfig._get_env_bool(
        "STORE_SUMMARIES_IN_RAG", True
    )


class NaturalnessConfig(BaseConfig):
    """Naturalness features configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("NATURALNESS_ENABLED", True)
    REACTIONS_ENABLED: bool = BaseConfig._get_env_bool("REACTIONS_ENABLED", True)
    REACTIONS_CHANCE_MULTIPLIER: float = BaseConfig._get_env_float(
        "REACTIONS_CHANCE_MULTIPLIER", 1.0
    )
    ACTIVITY_AWARENESS_ENABLED: bool = BaseConfig._get_env_bool(
        "ACTIVITY_AWARENESS_ENABLED", True
    )
    ACTIVITY_COMMENT_CHANCE: float = BaseConfig._get_env_float(
        "ACTIVITY_COMMENT_CHANCE", 0.1
    )
    ACTIVITY_COOLDOWN_SECONDS: int = BaseConfig._get_env_int(
        "ACTIVITY_COOLDOWN_SECONDS", 300
    )


class TimingConfig(BaseConfig):
    """Natural timing configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("NATURAL_TIMING_ENABLED", True)
    MIN_DELAY: float = BaseConfig._get_env_float("NATURAL_TIMING_MIN_DELAY", 0.5)
    MAX_DELAY: float = BaseConfig._get_env_float("NATURAL_TIMING_MAX_DELAY", 2.0)
    TYPING_MIN_DELAY: float = BaseConfig._get_env_float(
        "TYPING_INDICATOR_MIN_DELAY", 0.5
    )
    TYPING_MAX_DELAY: float = BaseConfig._get_env_float(
        "TYPING_INDICATOR_MAX_DELAY", 2.0
    )


class ProactiveConfig(BaseConfig):
    """Proactive engagement configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("PROACTIVE_ENGAGEMENT_ENABLED", False)
    MIN_MESSAGES: int = BaseConfig._get_env_int("PROACTIVE_MIN_MESSAGES", 3)
    COOLDOWN: int = BaseConfig._get_env_int("PROACTIVE_COOLDOWN", 180)


class AdaptiveTimingConfig(BaseConfig):
    """Adaptive timing configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("ADAPTIVE_TIMING_ENABLED", True)
    LEARNING_WINDOW_DAYS: int = BaseConfig._get_env_int(
        "ADAPTIVE_TIMING_LEARNING_WINDOW_DAYS", 7
    )
    CHANNEL_PROFILE_PATH: Path = BaseConfig._get_env_path(
        "CHANNEL_ACTIVITY_PROFILE_PATH", "./data/channel_activity_profiles.json"
    )


class VisionConfig(BaseConfig):
    """Vision/image understanding configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("VISION_ENABLED", True)
    MODEL: str = BaseConfig._get_env("VISION_MODEL", "llava")


class WebSearchConfig(BaseConfig):
    """Web search configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("WEB_SEARCH_ENABLED", True)
    ENGINE: str = BaseConfig._get_env("WEB_SEARCH_ENGINE", "duckduckgo")
    MAX_RESULTS: int = BaseConfig._get_env_int("WEB_SEARCH_MAX_RESULTS", 3)
    RATE_LIMIT_DELAY: float = BaseConfig._get_env_float(
        "WEB_SEARCH_RATE_LIMIT_DELAY", 2.0
    )


class TriviaConfig(BaseConfig):
    """Trivia games configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("TRIVIA_ENABLED", True)


class NotesConfig(BaseConfig):
    """Notes feature configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("NOTES_ENABLED", True)


class RemindersConfig(BaseConfig):
    """Reminders configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("REMINDERS_ENABLED", True)
    MAX_PER_USER: int = BaseConfig._get_env_int("MAX_REMINDERS_PER_USER", 10)


class PerformanceConfig(BaseConfig):
    """Performance optimization configuration."""

    USE_STREAMING_FOR_LONG_RESPONSES: bool = BaseConfig._get_env_bool(
        "USE_STREAMING_FOR_LONG_RESPONSES", True
    )
    STREAMING_TOKEN_THRESHOLD: int = BaseConfig._get_env_int(
        "STREAMING_TOKEN_THRESHOLD", 300
    )
    DYNAMIC_MAX_TOKENS: bool = BaseConfig._get_env_bool("DYNAMIC_MAX_TOKENS", False)
    SERVICE_CLEANUP_TIMEOUT: float = BaseConfig._get_env_float(
        "SERVICE_CLEANUP_TIMEOUT", 2.0
    )
