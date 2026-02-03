"""Mock Discord objects for headless testing of bot-to-bot conversations."""

from unittest.mock import AsyncMock, MagicMock
from typing import List, Optional, Dict, Any
import discord
from datetime import datetime


class MockWebhook:
    """Mock Discord webhook for testing."""

    def __init__(
        self,
        name: str = "TestWebhook",
        id: int = 12345,
        channel: "MockConversationChannel" = None,
    ):
        self.name = name
        self.id = id
        self.token = "mock_token"
        self.url = f"https://discord.com/api/webhooks/{id}/mock_token"
        self.sent_messages: List["MockMessage"] = []
        self.channel = channel

    async def send(
        self,
        content: str = None,
        username: str = None,
        avatar_url: str = None,
        wait: bool = False,
        **kwargs,
    ) -> "MockMessage":
        """Mock send method."""
        message = MockMessage(
            content=content,
            author=MockUser(username=username or self.name),
            webhook_id=self.id,
            channel=self.channel,
        )
        self.sent_messages.append(message)
        if self.channel:
            self.channel.messages.append(message)
        return message

    async def edit(self, **kwargs):
        """Mock edit method."""
        pass

    async def delete(self):
        """Mock delete method."""
        pass


class MockUser:
    """Mock Discord user."""

    def __init__(self, username: str, id: int = 12345, bot: bool = False):
        self.username = username
        self.display_name = username
        self.id = id
        self.bot = bot
        self.avatar_url = f"https://cdn.discordapp.com/avatars/{id}/mock.png"

    def __str__(self):
        return self.username


class MockMessage:
    """Mock Discord message."""

    def __init__(
        self,
        content: str = "",
        author: MockUser = None,
        channel: "MockConversationChannel" = None,
        id: int = 12345,
        webhook_id: Optional[int] = None,
    ):
        self.content = content
        self.author = author or MockUser("TestUser")
        self.channel = channel
        self.id = id
        self.webhook_id = webhook_id
        self.created_at = datetime.now()
        self._bot_conversation_id: Optional[str] = None

    async def reply(self, content: str, **kwargs):
        """Mock reply method."""
        return MockMessage(content=content, channel=self.channel)

    async def edit(self, **kwargs):
        """Mock edit method."""
        pass

    async def delete(self):
        """Mock delete method."""
        pass


class MockTypingContext:
    """Mock typing indicator context manager."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockConversationChannel:
    """Mock Discord channel for bot-to-bot conversations."""

    def __init__(self, name: str = "test-channel", id: int = 12345):
        self.name = name
        self.id = id
        self.messages: List[MockMessage] = []
        self.webhooks_list: List[MockWebhook] = []
        self.typing_active = False

    async def send(self, content: str = None, **kwargs) -> MockMessage:
        """Send a message to the channel."""
        message = MockMessage(content=content, channel=self)
        self.messages.append(message)
        return message

    async def create_webhook(self, name: str, **kwargs) -> MockWebhook:
        """Create a webhook in the channel."""
        webhook = MockWebhook(
            name=name, id=len(self.webhooks_list) + 1000, channel=self
        )
        self.webhooks_list.append(webhook)
        return webhook

    async def webhooks(self) -> List[MockWebhook]:
        """Get all webhooks in the channel."""
        return self.webhooks_list

    def typing(self):
        """Return typing context manager."""
        return MockTypingContext()

    def get_conversation_log(self) -> List[Dict]:
        """Get conversation log for verification."""
        return [
            {
                "speaker": msg.author.username,
                "content": msg.content,
                "is_webhook": msg.webhook_id is not None,
            }
            for msg in self.messages
        ]


class MockGuild:
    """Mock Discord guild/server."""

    def __init__(self, name: str = "TestGuild", id: int = 12345):
        self.name = name
        self.id = id
        self.channels: List[MockConversationChannel] = []

    def get_channel(self, channel_id: int) -> Optional[MockConversationChannel]:
        """Get channel by ID."""
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return None


class MockBot:
    """Mock Discord bot for testing."""

    def __init__(self):
        self.guilds: List[MockGuild] = []
        self.user = MockUser("TestBot", bot=True)

    def get_guild(self, guild_id: int) -> Optional[MockGuild]:
        """Get guild by ID."""
        for guild in self.guilds:
            if guild.id == guild_id:
                return guild
        return None

    async def wait_for(self, event: str, **kwargs):
        """Mock wait_for method."""
        return None
