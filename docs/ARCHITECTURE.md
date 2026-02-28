# Gestalt Framework Architecture

This document explains the Core/Adapter architecture powering the Gestalt Framework. It covers the separation of concerns, event flow, type system, and how to extend the framework with new adapters.

---

## Table of Contents

1. [Overview](#overview)
2. [Core Architecture](#core-architecture)
3. [Adapter System](#adapter-system)
4. [Event Flow](#event-flow)
5. [Type Reference](#type-reference)
6. [Creating New Adapters](#creating-new-adapters)
7. [Migration Guide](#migration-guide)

---

## Overview

The Gestalt Framework uses a **Core/Adapter architecture** that separates platform-agnostic business logic from platform-specific integrations. This design enables:

- **Multi-platform support**: Run the same bot logic on Discord, Telegram, CLI, or any other platform
- **Testability**: Core logic can be unit tested without platform dependencies
- **Maintainability**: Platform-specific code is isolated in adapters
- **Extensibility**: Adding a new platform requires only creating a new adapter

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ADAPTER LAYER                                  │
├─────────────────────────┬─────────────────────────┬─────────────────────┤
│    Discord Adapter      │      CLI Adapter        │  [Your Adapter]     │
│  (adapters/discord/)    │    (adapters/cli/)      │  (adapters/xxx/)    │
├─────────────────────────┴─────────────────────────┴─────────────────────┤
│                              CORE LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Platform-Agnostic Types                       │    │
│  │         AcoreMessage, AcoreUser, AcoreChannel, etc.            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        Event Bus                                 │    │
│  │              Decoupled communication between layers            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────┤
│                           SERVICE LAYER                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │
│  │   Persona   │ │   Memory    │ │     LLM     │ │     Voice       │    │
│  │   System    │ │   System    │ │  Services   │ │   Services      │    │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why This Separation Matters

**Before (Tightly Coupled):**
```python
# Old approach - Discord-specific code everywhere
async def handle_message(message: discord.Message):
    # Business logic mixed with Discord API calls
    await message.channel.send(response)
```

**After (Core/Adapter):**
```python
# New approach - Platform-agnostic core
async def handle_message(message: AcoreMessage, ctx: AcoreContext):
    # Pure business logic - no platform dependencies
    await ctx.reply(response)  # Callback handles platform specifics
```

---

## Core Architecture

### Location

Core components live in `core/`:
- `core/types.py` - Platform-agnostic data types
- `core/interfaces.py` - Abstract base classes for adapters and event bus

### Design Principles

1. **Platform Agnosticism**: Core never imports Discord or any platform-specific libraries
2. **Dependency Inversion**: Core defines interfaces that adapters implement
3. **Event-Driven**: Components communicate via events rather than direct calls
4. **Type Safety**: Strong typing with dataclasses for all data structures

### Key Components

#### 1. Types (`core/types.py`)

The type system provides platform-agnostic representations:

| Type | Purpose | Discord Equivalent |
|------|---------|-------------------|
| `AcoreMessage` | Message content and metadata | `discord.Message` |
| `AcoreUser` | User information | `discord.User` |
| `AcoreChannel` | Channel information | `discord.TextChannel` |
| `AcoreContext` | Context with reply callback | `discord.ext.commands.Context` |
| `AcoreEvent` | Generic event container | N/A (internal) |

#### 2. Event Bus (`core/interfaces.py`)

The event bus enables decoupled communication:

```python
from core.interfaces import SimpleEventBus

# Create event bus
event_bus = SimpleEventBus()

# Subscribe to events
event_bus.subscribe("persona_spoke", handle_persona_message)

# Emit events
event_bus.emit("persona_spoke", {
    "persona_id": "dagoth_ur",
    "content": "Welcome, Moon-and-Star..."
})
```

#### 3. Adapter Interfaces

Core defines what adapters must implement:

```python
from core.interfaces import InputAdapter, OutputAdapter

class MyInputAdapter(InputAdapter):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def on_event(self, callback) -> None: ...

class MyOutputAdapter(OutputAdapter):
    async def send(self, channel_id: str, text: str, **options) -> None: ...
    async def send_embed(self, channel_id: str, embed: dict) -> None: ...
```

---

## Adapter System

### What Is an Adapter?

An adapter bridges the Core and a specific platform. It:
- Converts platform events to `AcoreEvent` objects
- Converts Core responses to platform-specific actions
- Handles platform authentication and lifecycle

### Existing Adapters

| Adapter | Location | Status | Description |
|---------|----------|--------|-------------|
| Discord | `adapters/discord/` | Production | Full Discord integration with webhooks |
| CLI | `adapters/cli/` | Skeleton | Minimal scaffolding for CLI interface |

### Adapter Structure

Each adapter typically contains:

```
adapters/<platform>/
├── __init__.py          # Exports adapter classes
├── adapter.py           # InputAdapter implementation
├── output.py            # OutputAdapter implementation (optional)
└── commands/            # Platform-specific commands
    └── ...
```

### Discord Adapter Deep Dive

**File**: `adapters/discord/adapter.py`

The Discord adapter demonstrates the full implementation:

```python
class DiscordInputAdapter(InputAdapter):
    def __init__(self, token: str, ...):
        # Initialize discord.py bot
        self.bot = commands.Bot(...)
        
    async def _on_message(self, message: discord.Message):
        # Convert Discord message to AcoreMessage
        acore_message = self._convert_message(message)
        
        # Create platform-agnostic event
        event = AcoreEvent(
            type="message",
            payload={"message": acore_message},
            source_adapter="discord"
        )
        
        # Emit to core
        await self._emit_event(event)
```

**Webhook Spoofing**: The Discord adapter includes persona spoofing via webhooks in `adapters/discord/output.py`:

```python
class WebhookPool:
    """Manages Discord webhooks for persona spoofing."""
    
    async def send_message(
        self,
        persona_id: str,
        display_name: str,
        avatar_url: str,
        content: str
    ):
        # Sends message with custom name/avatar
```

---

## Event Flow

Understanding how data flows through the system is critical for debugging and extension.

### Complete Event Flow Diagram

```
User sends message on Discord
         │
         ▼
┌─────────────────┐
│  Discord Gateway │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DiscordInput   │  Converts discord.Message to AcoreMessage
│    Adapter      │  Creates AcoreEvent(type="message", ...)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Event Bus    │  Routes event to registered handlers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ChatCog       │  Receives AcoreEvent via on_event callback
│  (or handler)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PersonaRouter  │  Selects appropriate persona
│ BehaviorEngine  │  Decides if/how to respond
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Core Services  │  LLM generation, memory lookup, etc.
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response ready │  AcoreContext.reply_callback invoked
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DiscordOutput   │  Sends via webhook (persona spoofing)
│    Adapter      │  or regular channel.send
└────────┬────────┘
         │
         ▼
User sees response from persona
```

### Message Processing Flow

1. **Receive**: Platform adapter receives native event
2. **Convert**: Transform to platform-agnostic types
3. **Route**: Event bus routes to appropriate handlers
4. **Process**: Core services handle business logic
5. **Respond**: Reply callback sends response back
6. **Deliver**: Output adapter delivers to platform

### Code Example: Full Flow

```python
# 1. Adapter receives Discord message (adapters/discord/adapter.py)
async def _on_message(self, message: discord.Message):
    acore_message = AcoreMessage(
        text=message.content,
        author_id=str(message.author.id),
        channel_id=str(message.channel.id),
        timestamp=message.created_at,
        attachments=[...]
    )
    
    event = AcoreEvent(
        type="message",
        payload={"message": acore_message},
        source_adapter="discord"
    )
    
    await self._emit_event(event)

# 2. Core processes via handler (cogs/chat/message_handler.py)
async def check_and_handle_message(self, message: discord.Message):
    # Decision logic here...
    should_respond = True
    
    if should_respond:
        # 3. Generate response using services
        response = await self.generate_response(message)
        
        # 4. Send via output adapter
        await message.channel.send(response)
```

---

## Type Reference

### AcoreMessage

```python
@dataclass
class AcoreMessage:
    """Platform-agnostic message representation."""
    
    text: str                    # Message content
    author_id: str              # Unique author identifier
    channel_id: str             # Unique channel identifier
    timestamp: datetime         # When sent (UTC)
    attachments: List[Dict]     # Attachment metadata
```

**Usage**:
```python
from core.types import AcoreMessage

message = AcoreMessage(
    text="Hello, bot!",
    author_id="123456789",
    channel_id="987654321",
    attachments=[{
        "url": "https://example.com/image.png",
        "filename": "image.png",
        "content_type": "image/png"
    }]
)
```

### AcoreUser

```python
@dataclass
class AcoreUser:
    """Platform-agnostic user representation."""
    
    id: str                     # Unique user ID
    display_name: str          # Display name
    metadata: Dict[str, Any]   # Platform-specific data
```

**Usage**:
```python
from core.types import AcoreUser

user = AcoreUser(
    id="123456789",
    display_name="Alice",
    metadata={
        "username": "alice123",
        "roles": ["admin", "moderator"]
    }
)
```

### AcoreChannel

```python
@dataclass
class AcoreChannel:
    """Platform-agnostic channel representation."""
    
    id: str                     # Unique channel ID
    name: str                   # Channel name
    type: str                   # "text", "dm", "thread", "voice"
    parent_id: Optional[str]   # Parent channel (for threads)
```

**Usage**:
```python
from core.types import AcoreChannel

channel = AcoreChannel(
    id="987654321",
    name="general",
    type="text",
    parent_id=None
)
```

### AcoreContext

```python
@dataclass
class AcoreContext:
    """Context wrapper with reply capability."""
    
    message: AcoreMessage
    channel: AcoreChannel
    user: AcoreUser
    reply_callback: Callable[[str], Any]
    
    def reply(self, text: str) -> Any:
        """Send reply via callback."""
        return self.reply_callback(text)
```

**Usage**:
```python
from core.types import AcoreContext

async def send_reply(text: str):
    await discord_channel.send(text)

context = AcoreContext(
    message=message,
    channel=channel,
    user=user,
    reply_callback=send_reply
)

# Reply without knowing platform
await context.reply("Hello!")
```

### AcoreEvent

```python
@dataclass
class AcoreEvent:
    """Generic event container."""
    
    type: str                   # Event type (e.g., "message", "reaction")
    payload: dict              # Event-specific data
    source_adapter: str        # Which adapter created this
    timestamp: datetime        # When created
```

**Standard Event Types**:

| Event Type | Payload | Description |
|------------|---------|-------------|
| `message` | `{"message": AcoreMessage}` | New message received |
| `reaction` | `{"emoji": str, "message_id": str, ...}` | Reaction added |
| `persona_spoke` | `{"persona_id": str, "content": str, ...}` | Persona sent message |
| `conversation_typing` | `{"channel_id": str, "duration_seconds": float}` | Show typing indicator |
| `conversation_summary` | `{"conversation_id": str, ...}` | Conversation ended |

---

## Creating New Adapters

This guide walks through creating a new adapter for a hypothetical platform.

### Step 1: Create Adapter Directory

```bash
mkdir -p adapters/telegram
```

### Step 2: Implement InputAdapter

**File**: `adapters/telegram/adapter.py`

```python
"""Telegram adapter for Acore Bot."""

import asyncio
import logging
from typing import Any, Callable, Optional
from datetime import datetime

from core.interfaces import InputAdapter, OutputAdapter, AcoreEvent
from core.types import AcoreMessage, AcoreUser, AcoreChannel

logger = logging.getLogger(__name__)


class TelegramInputAdapter(InputAdapter):
    """Input adapter for Telegram Bot API."""
    
    def __init__(self, bot_token: str):
        super().__init__()
        self.bot_token = bot_token
        self._event_callback: Optional[Callable[[AcoreEvent], Any]] = None
        self._running = False
        # Initialize Telegram bot library here
        
    async def start(self) -> None:
        """Start listening for Telegram messages."""
        self._running = True
        logger.info("TelegramInputAdapter started")
        
        # Start polling loop
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
            except Exception as e:
                logger.error(f"Error polling Telegram: {e}")
                await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Stop listening."""
        self._running = False
        logger.info("TelegramInputAdapter stopped")
    
    def on_event(self, callback: Callable[[AcoreEvent], Any]) -> None:
        """Register event callback."""
        self._event_callback = callback
    
    async def _handle_update(self, update: dict) -> None:
        """Process Telegram update."""
        if "message" not in update:
            return
            
        message = update["message"]
        
        # Convert to AcoreMessage
        acore_message = AcoreMessage(
            text=message.get("text", ""),
            author_id=str(message["from"]["id"]),
            channel_id=str(message["chat"]["id"]),
            timestamp=datetime.utcnow(),
            attachments=[]  # Handle documents/photos if needed
        )
        
        # Create event
        event = AcoreEvent(
            type="message",
            payload={"message": acore_message},
            source_adapter="telegram",
            timestamp=datetime.utcnow()
        )
        
        # Emit to core
        if self._event_callback:
            result = self._event_callback(event)
            if asyncio.iscoroutine(result):
                await result
```

### Step 3: Implement OutputAdapter

```python
class TelegramOutputAdapter(OutputAdapter):
    """Output adapter for Telegram."""
    
    def __init__(self, bot_token: str):
        super().__init__()
        self.bot_token = bot_token
        # Initialize Telegram API client
    
    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send text message to Telegram chat."""
        # Call Telegram sendMessage API
        await self._api_call("sendMessage", {
            "chat_id": channel_id,
            "text": text,
            "parse_mode": options.get("parse_mode", "HTML")
        })
    
    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich content (using Telegram's formatting)."""
        # Convert embed to Telegram-compatible format
        text = f"**{embed.get('title', '')}**\n\n{embed.get('description', '')}"
        await self.send(channel_id, text, parse_mode="Markdown")
    
    async def _api_call(self, method: str, params: dict) -> dict:
        """Make Telegram Bot API call."""
        # Implementation here
        pass
```

### Step 4: Create `__init__.py`

**File**: `adapters/telegram/__init__.py`

```python
"""Telegram adapter for Acore Bot."""

from .adapter import TelegramInputAdapter, TelegramOutputAdapter

__all__ = ["TelegramInputAdapter", "TelegramOutputAdapter"]
```

### Step 5: Integrate with Bot

**File**: `main.py` or a new entry point

```python
from adapters.telegram import TelegramInputAdapter, TelegramOutputAdapter

# Create adapters
telegram_input = TelegramInputAdapter(bot_token=Config.TELEGRAM_BOT_TOKEN)
telegram_output = TelegramOutputAdapter(bot_token=Config.TELEGRAM_BOT_TOKEN)

# Register event handler
telegram_input.on_event(handle_acore_event)

# Start adapter
await telegram_input.start()
```

### Adapter Checklist

When creating a new adapter, ensure you:

- [ ] Implement `InputAdapter` interface (start, stop, on_event)
- [ ] Implement `OutputAdapter` interface (send, send_embed)
- [ ] Convert platform types to Acore types
- [ ] Handle platform authentication
- [ ] Implement graceful shutdown
- [ ] Add logging for debugging
- [ ] Handle platform-specific errors
- [ ] Support all relevant event types
- [ ] Test with actual platform

---

## Migration Guide

### From Old Architecture (Pre-Core/Adapter)

If you have code from before the Core/Adapter split, here is how to migrate.

#### Breaking Changes

1. **Type Changes**: Discord types replaced with Acore types
2. **Import Paths**: New module structure
3. **Response Methods**: Direct channel access replaced with callbacks

#### Migration Steps

**Step 1: Update Imports**

```python
# OLD - Direct Discord imports
import discord
from discord.ext import commands

# NEW - Core types
from core.types import AcoreMessage, AcoreUser, AcoreChannel, AcoreContext
from core.interfaces import InputAdapter, OutputAdapter
```

**Step 2: Update Function Signatures**

```python
# OLD - Discord-specific
async def handle_message(message: discord.Message):
    user = message.author
    channel = message.channel
    await channel.send("Response")

# NEW - Platform-agnostic
async def handle_message(message: AcoreMessage, ctx: AcoreContext):
    user = ctx.user
    channel = ctx.channel
    await ctx.reply("Response")
```

**Step 3: Update Message Access**

```python
# OLD
content = message.content
author_id = message.author.id
channel_id = message.channel.id

# NEW
content = message.text
author_id = message.author_id
channel_id = message.channel_id
```

**Step 4: Update User Access**

```python
# OLD
username = user.name
display_name = user.display_name

# NEW
username = user.metadata.get("username")  # Platform-specific
display_name = user.display_name  # Standard across platforms
```

**Step 5: Update Channel Operations**

```python
# OLD - Direct Discord operations
await channel.send("Hello")
await channel.send(embed=discord.Embed(title="Title"))

# NEW - Via context callback
await ctx.reply("Hello")
# For embeds, pass structured data and let adapter handle it
```

#### Migration Example: Complete Function

**Before**:
```python
# services/old_handler.py
import discord

async def process_message(message: discord.Message, llm_service):
    # Access Discord-specific attributes
    content = message.content
    author = message.author.display_name
    
    # Generate response
    response = await llm_service.generate(f"{author}: {content}")
    
    # Send via Discord API
    await message.channel.send(response)
```

**After**:
```python
# services/new_handler.py
from core.types import AcoreMessage, AcoreContext

async def process_message(message: AcoreMessage, ctx: AcoreContext, llm_service):
    # Access platform-agnostic attributes
    content = message.text
    author = ctx.user.display_name
    
    # Generate response
    response = await llm_service.generate(f"{author}: {content}")
    
    # Send via platform-agnostic callback
    await ctx.reply(response)
```

### Backward Compatibility

For gradual migration, you can create wrapper functions:

```python
# compatibility.py
import discord
from core.types import AcoreMessage, AcoreUser, AcoreChannel, AcoreContext

async def discord_to_acore_context(
    message: discord.Message
) -> AcoreContext:
    """Convert Discord message to AcoreContext."""
    
    acore_message = AcoreMessage(
        text=message.content or "",
        author_id=str(message.author.id),
        channel_id=str(message.channel.id),
        timestamp=message.created_at or datetime.utcnow(),
        attachments=[]
    )
    
    acore_user = AcoreUser(
        id=str(message.author.id),
        display_name=message.author.display_name,
        metadata={"username": message.author.name}
    )
    
    acore_channel = AcoreChannel(
        id=str(message.channel.id),
        name=getattr(message.channel, "name", "dm"),
        type="dm" if isinstance(message.channel, discord.DMChannel) else "text"
    )
    
    async def reply_callback(text: str):
        await message.channel.send(text)
    
    return AcoreContext(
        message=acore_message,
        channel=acore_channel,
        user=acore_user,
        reply_callback=reply_callback
    )
```

### Testing Migration

After migration, verify:

1. **Unit Tests**: Core logic works without Discord mocks
2. **Integration Tests**: Discord adapter still functions
3. **Edge Cases**: Empty messages, special characters, attachments
4. **Error Handling**: Network errors, rate limits

---

## Best Practices

### Do's

1. **Keep Core Pure**: Never import platform libraries in core
2. **Use Types**: Always use Acore types in core logic
3. **Handle Errors**: Gracefully handle adapter failures
4. **Log Context**: Include adapter name in logs
5. **Test Adapters**: Mock platform APIs for testing

### Don'ts

1. **Don't Leak Platform Types**: Convert immediately on adapter boundary
2. **Don't Use Platform Features in Core**: No Discord embeds in business logic
3. **Don't Skip Error Handling**: Platform APIs fail; handle it
4. **Don't Hardcode Platform Logic**: Use configuration for platform-specific behavior

### Configuration Pattern

```python
# config.py
class Config:
    # Platform selection
    INPUT_ADAPTER = os.getenv("INPUT_ADAPTER", "discord")
    OUTPUT_ADAPTER = os.getenv("OUTPUT_ADAPTER", "discord")
    
    # Platform-specific settings
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
```

---

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'core'`

**Solution**: Ensure `core/` is in Python path or use absolute imports:
```python
from acore_bot.core.types import AcoreMessage
```

**Issue**: Events not reaching core

**Solution**: Check that `on_event` callback is registered:
```python
adapter.on_event(handle_event)
```

**Issue**: Responses not sending

**Solution**: Verify `reply_callback` is set in AcoreContext:
```python
context = AcoreContext(
    message=message,
    channel=channel,
    user=user,
    reply_callback=your_send_function  # Must be callable
)
```

---

## Summary

The Core/Adapter architecture provides a clean separation between platform-specific code and business logic. By using platform-agnostic types and event-driven communication, the framework achieves:

- **Portability**: Same core logic on any platform
- **Testability**: Unit test without platform dependencies
- **Maintainability**: Isolate platform changes to adapters
- **Extensibility**: Add new platforms by implementing interfaces

Key files to remember:
- `core/types.py` - Platform-agnostic types
- `core/interfaces.py` - Adapter interfaces
- `adapters/discord/` - Reference implementation
- `adapters/cli/` - Minimal scaffolding

For questions or issues, refer to the existing adapter implementations as working examples.
