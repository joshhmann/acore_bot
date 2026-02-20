"""Cogs package - re-exports from adapters.discord.commands for backward compatibility."""

from adapters.discord.commands.chat import ChatCog

__all__ = ["ChatCog"]

try:
    from adapters.discord.commands.voice import VoiceCog

    __all__.append("VoiceCog")
except ImportError:
    pass
