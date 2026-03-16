"""Core adapter interfaces for the Acore Bot framework.

This module defines abstract base classes that all platform adapters must implement.
Adapters provide the bridge between the core bot logic and specific platforms
like Discord, CLI, or future platforms.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List

from core.schemas import Event, EventKind

logger = logging.getLogger(__name__)


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


@dataclass(slots=True, frozen=True)
class PlatformFacts:
    """Normalized adapter facts passed into runtime event construction."""

    text: str
    user_id: str
    room_id: str
    message_id: str = ""
    is_direct_mention: bool = False
    is_reply_to_bot: bool = False
    is_persona_message: bool = False
    has_visual_context: bool = False
    author_is_bot: bool = False
    platform_flags: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


def build_runtime_event_from_facts(
    *,
    facts: PlatformFacts,
    platform_name: str,
    kind: str = EventKind.CHAT.value,
    session_id: str = "",
    persona_id: str = "",
    mode: str = "",
    extra_flags: dict[str, Any] | None = None,
) -> Event:
    """Build canonical runtime event from adapter-level normalized facts."""
    flags: dict[str, Any] = dict(facts.platform_flags)
    if extra_flags:
        flags.update(extra_flags)
    flags.setdefault("is_direct_mention", bool(facts.is_direct_mention))
    flags.setdefault("is_reply_to_bot", bool(facts.is_reply_to_bot))
    flags.setdefault("is_persona_message", bool(facts.is_persona_message))
    flags.setdefault("has_visual_context", bool(facts.has_visual_context))
    flags.setdefault("author_is_bot", bool(facts.author_is_bot))
    flags.setdefault("user_id", str(facts.user_id))
    if facts.raw_metadata:
        flags.setdefault("raw_metadata", dict(facts.raw_metadata))

    event_metadata: dict[str, Any] = {
        "persona_id": str(persona_id or ""),
        "mode": str(mode or ""),
        "flags": flags,
    }
    return Event(
        type=str(kind or EventKind.CHAT.value),
        kind=str(kind or EventKind.CHAT.value),
        text=str(facts.text or ""),
        user_id=str(facts.user_id or ""),
        room_id=str(facts.room_id or ""),
        message_id=str(facts.message_id or ""),
        platform=str(platform_name or "unknown"),
        session_id=str(session_id or ""),
        metadata=event_metadata,
    )


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

    @abstractmethod
    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Unsubscribe a handler from a specific event type.

        Args:
            event_type: The type of event to unsubscribe from.
            handler: The handler to remove from subscribers.
        """
        pass


class SimpleEventBus(EventBus):
    """Simple in-memory implementation of the EventBus interface."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable[..., Any]]] = {}

    def emit(self, event_type: str, payload: dict) -> None:
        """Emit an event to all subscribers."""
        if event_type not in self._handlers:
            return

        for handler in self._handlers[event_type]:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Subscribe a handler to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type} events")

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Unsubscribe a handler from a specific event type."""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler unsubscribed from {event_type} events")


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
