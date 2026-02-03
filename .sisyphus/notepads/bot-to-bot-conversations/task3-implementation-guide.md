# Task 3 Implementation Guide: Headless Discord Mocks

## Overview
Create mock Discord objects for testing bot-to-bot conversations without connecting to Discord.

## Files to Create

### 1. `tests/mocks/discord_mocks.py`

```python
"""Mock Discord objects for headless testing of bot-to-bot conversations."""

from unittest.mock import AsyncMock, MagicMock
from typing import List, Optional, Dict, Any
import discord
from datetime import datetime


class MockWebhook:
    """Mock Discord webhook for testing."""
    
    def __init__(self, name: str = "TestWebhook", id: int = 12345):
        self.name = name
        self.id = id
        self.token = "mock_token"
        self.url = f"https://discord.com/api/webhooks/{id}/mock_token"
        self.sent_messages: List[MockMessage] = []
    
    async def send(
        self,
        content: str = None,
        username: str = None,
        avatar_url: str = None,
        wait: bool = False,
        **kwargs
    ) -> "MockMessage":
        """Mock send method."""
        message = MockMessage(
            content=content,
            author=MockUser(username=username or self.name),
            webhook_id=self.id
        )
        self.sent_messages.append(message)
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
        webhook_id: Optional[int] = None
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


class MockConversationChannel:
    """Mock Discord channel for bot-to-bot conversations."""
    
    def __init__(self, name: str = "test-channel", id: int = 12345):
        self.name = name
        self.id = id
        self.messages: List[MockMessage] = []
        self.webhooks: List[MockWebhook] = []
        self.typing_active = False
    
    async def send(self, content: str = None, **kwargs) -> MockMessage:
        """Send a message to the channel."""
        message = MockMessage(content=content, channel=self)
        self.messages.append(message)
        return message
    
    async def create_webhook(self, name: str, **kwargs) -> MockWebhook:
        """Create a webhook in the channel."""
        webhook = MockWebhook(name=name, id=len(self.webhooks) + 1000)
        self.webhooks.append(webhook)
        return webhook
    
    async def webhooks(self) -> List[MockWebhook]:
        """Get all webhooks in the channel."""
        return self.webhooks
    
    def typing(self):
        """Return typing context manager."""
        return MockTypingContext()
    
    def get_conversation_log(self) -> List[Dict]:
        """Get conversation log for verification."""
        return [
            {
                "speaker": msg.author.username,
                "content": msg.content,
                "is_webhook": msg.webhook_id is not None
            }
            for msg in self.messages
        ]


class MockTypingContext:
    """Mock typing indicator context manager."""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


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
```

### 2. Update `tests/conftest.py`

```python
# Add to existing conftest.py

import pytest
from tests.mocks.discord_mocks import (
    MockBot, MockGuild, MockConversationChannel, 
    MockUser, MockMessage, MockWebhook
)


@pytest.fixture
def mock_conversation_channel():
    """Create a mock conversation channel."""
    return MockConversationChannel(name="bot-conversation-test")


@pytest.fixture
def mock_webhook():
    """Create a mock webhook."""
    return MockWebhook(name="PersonaBot_Proxy")


@pytest.fixture
def mock_bot_with_channel():
    """Create a mock bot with a guild and channel."""
    bot = MockBot()
    guild = MockGuild(name="TestGuild")
    channel = MockConversationChannel(name="bot-conversations")
    guild.channels.append(channel)
    bot.guilds.append(guild)
    return bot, guild, channel


@pytest.fixture
def mock_persona_message():
    """Create a mock message from a persona (via webhook)."""
    def _create(persona_name: str, content: str):
        webhook = MockWebhook(name="PersonaBot_Proxy")
        return MockMessage(
            content=content,
            author=MockUser(username=persona_name),
            webhook_id=webhook.id
        )
    return _create
```

### 3. `tests/unit/test_headless_mocks.py`

```python
"""Tests for headless Discord mocks."""

import pytest
from tests.mocks.discord_mocks import (
    MockBot, MockGuild, MockConversationChannel,
    MockUser, MockMessage, MockWebhook
)


class TestMockConversationChannel:
    @pytest.mark.asyncio
    async def test_send_message(self):
        channel = MockConversationChannel()
        message = await channel.send("Hello, world!")
        
        assert message.content == "Hello, world!"
        assert len(channel.messages) == 1
        assert channel.messages[0] == message
    
    @pytest.mark.asyncio
    async def test_create_webhook(self):
        channel = MockConversationChannel()
        webhook = await channel.create_webhook(name="TestWebhook")
        
        assert webhook.name == "TestWebhook"
        assert len(channel.webhooks) == 1
    
    @pytest.mark.asyncio
    async def test_webhook_send(self):
        channel = MockConversationChannel()
        webhook = await channel.create_webhook(name="PersonaBot_Proxy")
        
        message = await webhook.send(
            content="Test message",
            username="Dagoth_Ur"
        )
        
        assert message.content == "Test message"
        assert message.author.username == "Dagoth_Ur"
        assert message.webhook_id == webhook.id
    
    def test_get_conversation_log(self):
        channel = MockConversationChannel()
        
        # Simulate conversation
        channel.messages.append(MockMessage(
            content="Hello",
            author=MockUser("Dagoth_Ur")
        ))
        channel.messages.append(MockMessage(
            content="Hi there!",
            author=MockUser("Toad")
        ))
        
        log = channel.get_conversation_log()
        
        assert len(log) == 2
        assert log[0]["speaker"] == "Dagoth_Ur"
        assert log[1]["speaker"] == "Toad"


class TestMockWebhook:
    @pytest.mark.asyncio
    async def test_send_tracks_messages(self):
        webhook = MockWebhook()
        
        await webhook.send(content="Message 1")
        await webhook.send(content="Message 2")
        
        assert len(webhook.sent_messages) == 2
        assert webhook.sent_messages[0].content == "Message 1"
        assert webhook.sent_messages[1].content == "Message 2"


class TestMockBot:
    def test_get_guild(self):
        bot = MockBot()
        guild = MockGuild(id=12345)
        bot.guilds.append(guild)
        
        found = bot.get_guild(12345)
        assert found == guild
        
        not_found = bot.get_guild(99999)
        assert not_found is None
```

## Usage in Tests

```python
# Example: Testing orchestrator with mocks

@pytest.mark.asyncio
async def test_orchestrator_with_mocks(mock_conversation_channel):
    orchestrator = BotConversationOrchestrator(...)
    
    result = await orchestrator.run_conversation(
        participants=["dagoth_ur", "toad"],
        topic="cheese",
        max_turns=3,
        channel=mock_conversation_channel
    )
    
    # Verify conversation happened
    log = mock_conversation_channel.get_conversation_log()
    assert len(log) == 3
    assert log[0]["speaker"] in ["dagoth_ur", "toad"]
```

## Deterministic Testing

```python
# For reproducible tests, use seed

import random

@pytest.fixture
def deterministic_random():
    """Set random seed for deterministic tests."""
    random.seed(42)
    yield
    random.seed()  # Reset after test

@pytest.mark.asyncio
async def test_deterministic_conversation(
    mock_conversation_channel, 
    deterministic_random
):
    # This test will produce same output every time
    pass
```

## Verification

```bash
# Run tests
uv run pytest tests/unit/test_headless_mocks.py -v

# Test with orchestrator
uv run pytest tests/unit/test_orchestrator.py -v
```
