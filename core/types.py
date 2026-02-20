"""Core platform-agnostic types for the Acore framework.

These types replace Discord-specific types (discord.Message, discord.User, etc.)
in the core services, enabling multi-platform support and MCP compatibility.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AcoreMessage:
    """Platform-agnostic message representation.

    Attributes:
        text: The message content/text.
        author_id: Unique identifier of the message author.
        channel_id: Unique identifier of the channel where the message was sent.
        timestamp: When the message was sent. Defaults to current UTC time if not provided.
        attachments: List of attachment metadata dictionaries.
            Each dict may contain: url, filename, content_type, size, etc.
    """

    text: str
    author_id: str
    channel_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attachments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AcoreUser:
    """Platform-agnostic user representation.

    Attributes:
        id: Unique identifier for the user.
        display_name: The user's display name (may differ from username).
        metadata: Additional platform-specific metadata (e.g., roles, permissions).
    """

    id: str
    display_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AcoreChannel:
    """Platform-agnostic channel representation.

    Attributes:
        id: Unique identifier for the channel.
        name: The channel name or display name.
        type: Channel type - one of "text", "dm", "thread", "voice".
        parent_id: Optional parent channel ID (for threads).
    """

    id: str
    name: str
    type: str  # "text", "dm", "thread", "voice"
    parent_id: Optional[str] = None


@dataclass
class AcoreContext:
    """Platform-agnostic context wrapper for message processing.

    This class encapsulates all contextual information needed to process
    a message, including the message itself, channel, user, and a callback
    for sending replies.

    Attributes:
        message: The AcoreMessage being processed.
        channel: The channel where the message was sent.
        user: The user who sent the message.
        reply_callback: A callable that sends a reply to the channel.
            Expected signature: reply_callback(text: str) -> Any
    """

    message: AcoreMessage
    channel: AcoreChannel
    user: AcoreUser
    reply_callback: Callable[[str], Any]

    def reply(self, text: str) -> Any:
        """Send a reply to the channel using the configured callback.

        Args:
            text: The text content to send as a reply.

        Returns:
            The result of the reply_callback execution.
        """
        return self.reply_callback(text)


@dataclass
class PersonaSpokeEvent:
    """Event emitted when a persona speaks in a conversation.

    Attributes:
        conversation_id: Unique identifier for the conversation.
        channel_id: Platform-specific channel ID where the message should be sent.
        persona_id: Unique identifier for the speaking persona.
        display_name: Display name to show for the persona.
        avatar_url: URL to the persona's avatar image.
        content: The message content.
        timestamp: When the event was created.
    """

    conversation_id: str
    channel_id: str
    persona_id: str
    display_name: str
    avatar_url: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConversationTypingEvent:
    """Event emitted to show typing indicator in a channel.

    Attributes:
        channel_id: Platform-specific channel ID.
        duration_seconds: How long to show the typing indicator.
    """

    channel_id: str
    duration_seconds: float = 1.0


@dataclass
class ConversationSummaryEvent:
    """Event emitted when a conversation completes.

    Attributes:
        conversation_id: Unique identifier for the conversation.
        channel_id: Platform-specific channel ID where the summary should be sent.
        participants: List of participant persona IDs.
        topic: Conversation topic.
        turn_count: Number of turns completed.
        max_turns: Maximum allowed turns.
        termination_reason: Why the conversation ended.
        avg_latency: Average response latency in seconds.
    """

    conversation_id: str
    channel_id: str
    participants: List[str]
    topic: str
    turn_count: int
    max_turns: int
    termination_reason: str
    avg_latency: float
