"""Mock Discord objects for headless testing of bot-to-bot conversations."""

from .discord_mocks import (
    MockWebhook,
    MockUser,
    MockMessage,
    MockConversationChannel,
    MockTypingContext,
    MockGuild,
    MockBot,
)

__all__ = [
    "MockWebhook",
    "MockUser",
    "MockMessage",
    "MockConversationChannel",
    "MockTypingContext",
    "MockGuild",
    "MockBot",
]
