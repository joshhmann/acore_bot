"""Discord bot configuration."""

from .base import BaseConfig


class DiscordConfig(BaseConfig):
    """Discord bot configuration."""

    # Bot Token and Prefix
    TOKEN: str = BaseConfig._get_env("DISCORD_TOKEN", "")
    COMMAND_PREFIX: str = BaseConfig._get_env("COMMAND_PREFIX", "!")

    # Auto-reply Settings
    AUTO_REPLY_ENABLED: bool = BaseConfig._get_env_bool("AUTO_REPLY_ENABLED", False)
    AUTO_REPLY_CHANNELS: list = BaseConfig._get_env_int_list("AUTO_REPLY_CHANNELS")
    NAME_TRIGGER_CHANNELS: list = BaseConfig._get_env_int_list("NAME_TRIGGER_CHANNELS")
    AUTO_REPLY_WITH_VOICE: bool = BaseConfig._get_env_bool(
        "AUTO_REPLY_WITH_VOICE", True
    )

    # Bot Mode
    BOT_MODE: str = BaseConfig._get_env("BOT_MODE", "hybrid").lower()

    # Conversation Settings
    CONVERSATION_TIMEOUT: int = BaseConfig._get_env_int("CONVERSATION_TIMEOUT", 300)

    # User Ignore List
    IGNORED_USERS: list = BaseConfig._get_env_int_list("IGNORED_USERS")
