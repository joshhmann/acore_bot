# Task 2 Implementation Guide: Loop Prevention Bypass

## Overview
Modify the MessageHandler to bypass the 50% decay loop prevention during orchestrated bot-to-bot conversations.

## Problem
Current loop prevention (`cogs/chat/message_handler.py:410-423`) kills multi-turn conversations:
```python
# 50% chance of ignoring each message
if random.random() > 0.5:
    return False  # Message ignored
```

For 10 turns: `0.5^10 = 0.0977%` chance of completion (essentially impossible)

## Solution
Add a bypass flag that skips loop prevention for orchestrated conversations.

## Files to Modify

### 1. `config.py` - Add Configuration

```python
# Add to config.py

class Config:
    # ... existing config ...
    
    # Bot-to-bot conversation settings
    BOT_CONVERSATION_ENABLED = os.getenv("BOT_CONVERSATION_ENABLED", "true").lower() == "true"
    BOT_CONVERSATION_MAX_TURNS = int(os.getenv("BOT_CONVERSATION_MAX_TURNS", "10"))
    BOT_CONVERSATION_TIMEOUT_MINUTES = int(os.getenv("BOT_CONVERSATION_TIMEOUT_MINUTES", "30"))
```

### 2. `cogs/chat/message_handler.py` - Add Bypass Logic

```python
# Add to MessageHandler class

class MessageHandler:
    def __init__(self, ...):
        # ... existing init ...
        self._active_conversations: Dict[str, str] = {}  # message_id -> conversation_id
    
    def register_conversation_message(self, message_id: str, conversation_id: str):
        """Mark a message as part of an orchestrated conversation."""
        self._active_conversations[message_id] = conversation_id
    
    async def check_and_handle_message(self, message: discord.Message) -> bool:
        """Check if message should be handled, with loop prevention bypass."""
        
        # Check if this is part of an orchestrated conversation
        if hasattr(message, '_bot_conversation_id') and message._bot_conversation_id:
            logger.debug(f"Loop Prevention Bypass: Message part of conversation {message._bot_conversation_id}")
            # Skip loop prevention - always respond during orchestrated conversations
            return await self._process_message(message)
        
        # Check if this is a webhook message from our bot (bot-to-bot)
        if message.webhook_id:
            webhook = await self._get_webhook_by_id(message.webhook_id)
            if webhook and webhook.name == "PersonaBot_Proxy":
                # Check if this webhook message is part of active conversation
                if message.id in self._active_conversations:
                    logger.debug(f"Loop Prevention Bypass: Webhook message in active conversation")
                    return await self._process_message(message)
        
        # Existing loop prevention logic
        return await self._check_with_loop_prevention(message)
    
    async def _check_with_loop_prevention(self, message: discord.Message) -> bool:
        """Original loop prevention logic."""
        # ... existing 50% decay logic ...
        if random.random() > 0.5:
            logger.info(f"Loop Prevention: Ignored message from {message.author}")
            return False
        return await self._process_message(message)
```

### 3. Alternative: Message Metadata Approach

```python
# In orchestrator, when creating messages:

class BotConversationOrchestrator:
    async def _send_as_persona(self, persona_id: str, content: str, channel: discord.TextChannel):
        """Send message via webhook with conversation metadata."""
        
        webhook = await self._get_webhook(channel, persona_id)
        
        # Create message with metadata
        message = await webhook.send(
            content=content,
            username=persona_id,
            avatar_url=self._get_avatar_url(persona_id),
            wait=True  # Wait for message to be created
        )
        
        # Attach conversation metadata (monkey patch for bypass)
        message._bot_conversation_id = self.conversation_id
        
        # Register with message handler
        self.message_handler.register_conversation_message(
            message.id, 
            self.conversation_id
        )
        
        return message
```

## Testing

### Test File: `tests/unit/test_loop_bypass.py`

```python
"""Tests for loop prevention bypass."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from cogs.chat.message_handler import MessageHandler


class TestLoopPreventionBypass:
    @pytest.fixture
    def message_handler(self):
        handler = MessageHandler(
            bot=MagicMock(),
            persona_router=MagicMock(),
            ollama=MagicMock()
        )
        return handler
    
    @pytest.mark.asyncio
    async def test_bypass_with_conversation_flag(self, message_handler):
        """Test that messages with _bot_conversation_id bypass loop prevention."""
        
        # Create mock message with conversation flag
        message = MagicMock(spec=discord.Message)
        message._bot_conversation_id = "conv-123"
        message.author = MagicMock()
        message.author.display_name = "TestBot"
        
        # Mock _process_message to return True
        message_handler._process_message = AsyncMock(return_value=True)
        
        # Should bypass loop prevention and process
        result = await message_handler.check_and_handle_message(message)
        
        assert result is True
        message_handler._process_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_normal_message_uses_loop_prevention(self, message_handler):
        """Test that normal messages still use 50% decay."""
        
        message = MagicMock(spec=discord.Message)
        # No _bot_conversation_id attribute
        message.author = MagicMock()
        message.author.display_name = "User"
        
        # Mock _check_with_loop_prevention
        message_handler._check_with_loop_prevention = AsyncMock(return_value=True)
        
        result = await message_handler.check_and_handle_message(message)
        
        assert result is True
        message_handler._check_with_loop_prevention.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_webhook_message_in_conversation(self, message_handler):
        """Test webhook messages registered in active conversations."""
        
        message = MagicMock(spec=discord.Message)
        message.webhook_id = 12345
        message.id = 67890
        message.author = MagicMock()
        message.author.display_name = "PersonaBot"
        
        # Register as part of conversation
        message_handler.register_conversation_message(67890, "conv-123")
        
        # Mock webhook lookup
        webhook = MagicMock()
        webhook.name = "PersonaBot_Proxy"
        message_handler._get_webhook_by_id = AsyncMock(return_value=webhook)
        
        # Mock _process_message
        message_handler._process_message = AsyncMock(return_value=True)
        
        result = await message_handler.check_and_handle_message(message)
        
        assert result is True
        message_handler._process_message.assert_called_once()
```

## Integration Points

- Called by `BotConversationOrchestrator` when sending messages
- Must not affect normal human-bot conversations
- Should work with existing webhook system

## Verification

```bash
# Run tests
uv run pytest tests/unit/test_loop_bypass.py -v

# Manual verification
# 1. Start bot-to-bot conversation
# 2. Verify all 10 turns complete without random aborts
# 3. Verify normal conversations still have loop prevention
```
