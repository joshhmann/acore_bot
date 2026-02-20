"""Discord command cogs (migrated from cogs/)."""

from .chat import ChatCog

__all__ = ["ChatCog"]

try:
    from .voice import VoiceCog

    __all__.append("VoiceCog")
except ImportError:
    pass
