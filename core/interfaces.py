"""Core adapter interfaces for the Acore Bot framework.

This module defines abstract base classes that all platform adapters must implement.
Adapters provide the bridge between the core bot logic and specific platforms
like Discord, CLI, or future platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


@dataclass
class AcoreEvent:
    """Represents an event originating from any adapter.

    Attributes:
        type: The event type (e.g., "message", "command", "reaction").
        payload: Event-specific data as a dictionary.
        source_adapter: Identifier of the adapter that produced this event.
        timestamp: UTC datetime when the event was created.
    """

    type: str
    payload: dict
    source_adapter: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class InputAdapter(ABC):
    """Abstract base class for input adapters.

    Input adapters listen for incoming events from a platform (e.g., Discord,
    CLI) and convert them into AcoreEvent objects that the bot can process.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start listening for input events.

        This method should establish any necessary connections and begin
        listening for events from the source platform.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening for input events.

        This method should gracefully shutdown any connections and stop
        listening for events.
        """
        pass

    @abstractmethod
    def on_event(self, callback: Callable[[AcoreEvent], None]) -> None:
        """Register a callback to handle incoming events.

        Args:
            callback: A function that will be called with each AcoreEvent
                received by this adapter.
        """
        pass


class OutputAdapter(ABC):
    """Abstract base class for output adapters.

    Output adapters send messages and content from the bot to a platform.
    They handle the platform-specific formatting and delivery mechanisms.
    """

    @abstractmethod
    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message to a channel.

        Args:
            channel_id: The identifier of the target channel.
            text: The message text to send.
            **options: Optional platform-specific send options.
        """
        pass

    @abstractmethod
    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content to a channel.

        Args:
            channel_id: The identifier of the target channel.
            embed: A dictionary representing the embed content. The structure
                is adapter-specific but typically includes fields like title,
                description, color, and fields.
        """
        pass


class EventBus(ABC):
    """Abstract base class for the event bus.

    The event bus facilitates communication between adapters and the core
    bot by allowing publish/subscribe patterns for events.
    """

    @abstractmethod
    def emit(self, event_type: str, payload: dict) -> None:
        """Emit an event to all subscribers.

        Args:
            event_type: The type of event being emitted.
            payload: The event data as a dictionary.
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: The type of event to subscribe to.
            handler: A callable that will be invoked when events of this
                type are emitted.
        """
        pass
