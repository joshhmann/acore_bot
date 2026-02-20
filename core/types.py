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
    """

    id: str
    name: str
    type: str  # "text", "dm", "thread", "voice"


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
