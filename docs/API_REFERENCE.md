# Acore Framework API Reference

Complete API reference for the Acore Bot framework.

## Table of Contents

- [Core Types](#core-types)
- [Core Interfaces](#core-interfaces)
- [Adapters](#adapters)
- [Events](#events)

---

## Core Types

Location: `core/types.py`

### AcoreMessage

Platform-agnostic message representation.

```python
@dataclass
class AcoreMessage:
    text: str
    author_id: str
    channel_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
```

**Fields:**
- `text` (str): Message content
- `author_id` (str): Unique identifier of the message author
- `channel_id` (str): Unique identifier of the channel
- `timestamp` (datetime): When the message was sent
- `attachments` (List[Dict]): List of attachment metadata

**Example:**
```python
from core.types import AcoreMessage

message = AcoreMessage(
    text="Hello world",
    author_id="user_123",
    channel_id="channel_456"
)
```

---

### AcoreUser

Platform-agnostic user representation.

```python
@dataclass
class AcoreUser:
    id: str
    display_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Fields:**
- `id` (str): Unique user identifier
- `display_name` (str): User's display name
- `metadata` (Dict): Platform-specific metadata (roles, permissions, etc.)

**Example:**
```python
from core.types import AcoreUser

user = AcoreUser(
    id="user_123",
    display_name="JohnDoe",
    metadata={"is_bot": False, "roles": ["admin"]}
)
```

---

### AcoreChannel

Platform-agnostic channel representation.

```python
@dataclass
class AcoreChannel:
    id: str
    name: str
    type: str  # "text", "dm", "thread", "voice"
    parent_id: Optional[str] = None
```

**Fields:**
- `id` (str): Unique channel identifier
- `name` (str): Channel name
- `type` (str): Channel type ("text", "dm", "thread", "voice")
- `parent_id` (Optional[str]): Parent channel ID (for threads)

**Example:**
```python
from core.types import AcoreChannel

channel = AcoreChannel(
    id="channel_123",
    name="general",
    type="text"
)
```

---

### AcoreContext

Platform-agnostic context wrapper for message processing.

```python
@dataclass
class AcoreContext:
    message: AcoreMessage
    channel: AcoreChannel
    user: AcoreUser
    reply_callback: Callable[[str], Any]

    def reply(self, text: str) -> Any:
        """Send a reply to the channel."""
```

**Fields:**
- `message` (AcoreMessage): The message being processed
- `channel` (AcoreChannel): The channel where the message was sent
- `user` (AcoreUser): The user who sent the message
- `reply_callback` (Callable): Function to send replies

**Methods:**
- `reply(text: str) -> Any`: Send a reply using the configured callback

**Example:**
```python
from core.types import AcoreContext, AcoreMessage, AcoreUser, AcoreChannel

def send_reply(text: str):
    print(f"Reply: {text}")

ctx = AcoreContext(
    message=AcoreMessage(text="Hello", author_id="u1", channel_id="c1"),
    channel=AcoreChannel(id="c1", name="general", type="text"),
    user=AcoreUser(id="u1", display_name="User"),
    reply_callback=send_reply
)

ctx.reply("Hello back!")  # Calls send_reply("Hello back!")
```

---

## Core Interfaces

Location: `core/interfaces.py`

### AcoreEvent

Represents an event from any adapter.

```python
@dataclass
class AcoreEvent:
    type: str
    payload: dict
    source_adapter: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

**Fields:**
- `type` (str): Event type (e.g., "message", "command", "reaction")
- `payload` (dict): Event-specific data
- `source_adapter` (str): Which adapter produced this event
- `timestamp` (datetime): When the event was created

---

### InputAdapter (Abstract Base Class)

Base class for all input adapters.

```python
class InputAdapter(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Start listening for input events."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening for input events."""
        pass

    @abstractmethod
    def on_event(self, callback: Callable[[AcoreEvent], None]) -> None:
        """Register a callback to handle incoming events."""
        pass
```

**Methods:**
- `start() -> None`: Begin listening for events
- `stop() -> None`: Stop listening and cleanup
- `on_event(callback) -> None`: Register event handler callback

---

### OutputAdapter (Abstract Base Class)

Base class for all output adapters.

```python
class OutputAdapter(ABC):
    @abstractmethod
    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message to a channel."""
        pass

    @abstractmethod
    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content to a channel."""
        pass
```

**Methods:**
- `send(channel_id, text, **options) -> None`: Send text message
- `send_embed(channel_id, embed) -> None`: Send embed/rich content

---

### EventBus (Abstract Base Class)

Event bus for decoupled communication.

```python
class EventBus(ABC):
    @abstractmethod
    def emit(self, event_type: str, payload: dict) -> None:
        """Emit an event to all subscribers."""
        pass

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Subscribe a handler to a specific event type."""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Unsubscribe a handler from a specific event type."""
        pass
```

**Methods:**
- `emit(event_type, payload) -> None`: Emit event to subscribers
- `subscribe(event_type, handler) -> None`: Subscribe to events
- `unsubscribe(event_type, handler) -> None`: Unsubscribe from events

---

### SimpleEventBus

Concrete implementation of EventBus.

```python
class SimpleEventBus(EventBus):
    def __init__(self):
        self._handlers: Dict[str, List[Callable[..., Any]]] = {}
```

**Usage:**
```python
from core.interfaces import SimpleEventBus

event_bus = SimpleEventBus()

# Subscribe to events
def on_message(payload):
    print(f"Received: {payload}")

event_bus.subscribe("message", on_message)

# Emit events
event_bus.emit("message", {"text": "Hello"})
```

---

## Adapters

### DiscordInputAdapter

Location: `adapters/discord/adapter.py`

Input adapter for Discord.

```python
class DiscordInputAdapter(InputAdapter):
    def __init__(
        self,
        token: str,
        command_prefix: str = "!",
        intents: Optional[discord.Intents] = None,
    )
```

**Constructor Args:**
- `token` (str): Discord bot token
- `command_prefix` (str): Command prefix (default: "!")
- `intents` (Optional[discord.Intents]): Discord intents

**Example:**
```python
from adapters.discord.adapter import DiscordInputAdapter

adapter = DiscordInputAdapter(token="your_bot_token")

@adapter.on_event
def handle_event(event):
    print(f"Event: {event.type}")

await adapter.start()
```

---

### DiscordOutputAdapter

Location: `adapters/discord/output.py`

Output adapter for Discord with webhook spoofing.

```python
class DiscordOutputAdapter(OutputAdapter):
    def __init__(self, event_bus: EventBus)
```

**Methods:**
- `send(channel_id, text, **options) -> None`: Send text
- `send_embed(channel_id, embed) -> None`: Send embed
- `start() -> None`: Start the adapter
- `stop() -> None`: Stop the adapter

---

### CLIInputAdapter

Location: `adapters/cli/adapter.py`

Input adapter for command-line interface.

```python
class CLIInputAdapter(InputAdapter):
    def __init__(self, default_persona: str = "default")
```

**Constructor Args:**
- `default_persona` (str): Default persona to use (default: "default")

**Usage:**
```python
from adapters.cli.adapter import CLIInputAdapter

adapter = CLIInputAdapter()

adapter.on_event(lambda event: print(event.payload))

await adapter.start()
```

**Message Format:**
```
@persona_name message content
```

Example:
```
@dagoth_ur Hello, how are you?
```

---

### CLIOutputAdapter

Location: `adapters/cli/adapter.py`

Output adapter for command-line interface.

```python
class CLIOutputAdapter(OutputAdapter):
    def __init__(self)
```

**Methods:**
- `send(channel_id, text, persona=None, **options) -> None`: Print to stdout
- `send_embed(channel_id, embed) -> None`: Print formatted embed

---

## Events

### PersonaSpokeEvent

Event emitted when a persona speaks.

```python
@dataclass
class PersonaSpokeEvent:
    conversation_id: str
    channel_id: str
    persona_id: str
    display_name: str
    avatar_url: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

---

### ConversationTypingEvent

Event emitted to show typing indicator.

```python
@dataclass
class ConversationTypingEvent:
    channel_id: str
    duration_seconds: float = 1.0
```

---

### ConversationSummaryEvent

Event emitted when conversation completes.

```python
@dataclass
class ConversationSummaryEvent:
    conversation_id: str
    channel_id: str
    participants: List[str]
    topic: str
    turn_count: int
    max_turns: int
    termination_reason: str
    avg_latency: float
```

---

## Type Conversion Examples

### Discord to Acore

```python
import discord
from core.types import AcoreMessage, AcoreUser, AcoreChannel

def convert_discord_message(discord_msg: discord.Message) -> AcoreMessage:
    return AcoreMessage(
        text=discord_msg.content,
        author_id=str(discord_msg.author.id),
        channel_id=str(discord_msg.channel.id),
        timestamp=discord_msg.created_at,
        attachments=[
            {
                "url": att.url,
                "filename": att.filename,
                "size": att.size
            }
            for att in discord_msg.attachments
        ]
    )

def convert_discord_user(discord_user: discord.User) -> AcoreUser:
    return AcoreUser(
        id=str(discord_user.id),
        display_name=discord_user.display_name,
        metadata={
            "is_bot": discord_user.bot,
            "is_webhook": discord_user.bot and discord_user.discriminator == "0000"
        }
    )

def convert_discord_channel(discord_ch: discord.TextChannel) -> AcoreChannel:
    channel_type = "text"
    if isinstance(discord_ch, discord.DMChannel):
        channel_type = "dm"
    elif isinstance(discord_ch, discord.Thread):
        channel_type = "thread"
    elif isinstance(discord_ch, discord.VoiceChannel):
        channel_type = "voice"

    return AcoreChannel(
        id=str(discord_ch.id),
        name=getattr(discord_ch, 'name', 'DM'),
        type=channel_type,
        parent_id=str(discord_ch.parent_id) if hasattr(discord_ch, 'parent_id') else None
    )
```

---

## Error Handling

All adapters should handle errors gracefully:

```python
import logging

logger = logging.getLogger(__name__)

async def safe_send(adapter, channel_id, text):
    try:
        await adapter.send(channel_id, text)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
```

---

## Best Practices

1. **Always use string IDs**: Convert platform-specific IDs (int, snowflake) to strings
2. **Handle missing fields gracefully**: Use Optional types and default values
3. **Log adapter operations**: Use logging for debugging
4. **Test with mocks**: Write unit tests using mock adapters
5. **Follow interface contracts**: Ensure method signatures match exactly

---

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [Configuration Guide](CONFIGURATION.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
