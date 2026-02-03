"""Logging configuration."""

from .base import BaseConfig


class LoggingConfig(BaseConfig):
    """Logging configuration."""

    LEVEL: str = BaseConfig._get_env("LOG_LEVEL", "INFO")
    TO_FILE: bool = BaseConfig._get_env_bool("LOG_TO_FILE", True)
    FILE_PATH: str = BaseConfig._get_env("LOG_FILE_PATH", "logs/bot.log")
    MAX_BYTES: int = BaseConfig._get_env_int("LOG_MAX_BYTES", 10485760)
    BACKUP_COUNT: int = BaseConfig._get_env_int("LOG_BACKUP_COUNT", 5)
    FORMAT: str = BaseConfig._get_env("LOG_FORMAT", "text")
    COMPRESS: bool = BaseConfig._get_env_bool("LOG_COMPRESS", True)

    # Performance logging
    PERFORMANCE: bool = BaseConfig._get_env_bool("LOG_PERFORMANCE", True)
    LLM_REQUESTS: bool = BaseConfig._get_env_bool("LOG_LLM_REQUESTS", True)
    TTS_REQUESTS: bool = BaseConfig._get_env_bool("LOG_TTS_REQUESTS", True)
