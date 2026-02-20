"""
CLI adapter implementation for Acore bot.

This module provides a command-line interface for interacting with Acore personas:
- CLIInputAdapter: reads from stdin (async) and converts input into AcoreEvent
- CLIOutputAdapter: writes to stdout for outgoing messages

Usage:
    echo "@dagoth_ur hello" | python -m adapters.cli
"""

import asyncio
import logging
import re
import sys
from typing import Any, Callable, Optional

from core.interfaces import InputAdapter, OutputAdapter, AcoreEvent
from core.types import AcoreMessage

logger = logging.getLogger(__name__)


class CLIInputAdapter(InputAdapter):
    """Input adapter that reads user input from stdin and emits AcoreEvent.

    Parses messages in the format: @persona_name message_content
    Creates AcoreMessage with author_id="cli_user", channel_id="cli_channel"
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._running: bool = False
        self._event_callback: Optional[Callable[[AcoreEvent], None]] = None
        self._reader_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the CLI input listener.

        Spawns a background task that reads from stdin and converts lines into
        AcoreEvent instances.
        """
        self._running = True
        self._reader_task = asyncio.create_task(self._read_stdin_loop())
        logger.info("CLIInputAdapter started")

    async def stop(self) -> None:
        """Stop the CLI input listener."""
        self._running = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        logger.info("CLIInputAdapter stopped")

    def on_event(self, callback: Callable[[AcoreEvent], None]) -> None:
        """Register a callback to handle incoming events.

        Args:
            callback: A function that will be called with each AcoreEvent
                received by this adapter.
        """
        self._event_callback = callback

    async def _read_stdin_loop(self) -> None:
        """Background task that continuously reads from stdin."""
        try:
            while self._running:
                # Read line from stdin asynchronously
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                except (KeyboardInterrupt, EOFError):
                    break

                if not line:
                    # EOF reached
                    break

                line = line.strip()
                if line:
                    await self._process_input_line(line)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in stdin reader: {e}")

    async def _process_input_line(self, line: str) -> None:
        """Process a single input line and emit an event.

        Parses format: @persona_name message_content
        """
        # Parse @persona_name prefix
        persona_id: Optional[str] = None
        message_content = line

        # Match @persona_name at the start of the message
        match = re.match(r"^@(\w+)\s*(.*)", line)
        if match:
            persona_id = match.group(1)
            message_content = match.group(2).strip()
        else:
            # No persona specified, use default
            persona_id = "default"
            message_content = line

        # Create AcoreMessage
        message = AcoreMessage(
            text=message_content,
            author_id="cli_user",
            channel_id="cli_channel",
        )

        # Create AcoreEvent
        event = AcoreEvent(
            type="message",
            payload={
                "message": message,
                "persona_id": persona_id,
                "raw_content": line,
            },
            source_adapter="cli",
        )

        # Emit event via callback
        if self._event_callback:
            try:
                result = self._event_callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in event callback: {e}")


class CLIOutputAdapter(OutputAdapter):
    """Output adapter that writes to stdout.

    Prints messages in a human-readable format with optional persona prefix.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message to stdout.

        Args:
            channel_id: The identifier of the target channel (ignored for CLI).
            text: The message text to send.
            **options: Optional send options.
                - persona_id: ID of the persona speaking
                - display_name: Display name for the persona
        """
        persona_name = options.get("display_name") or options.get("persona_id")

        if persona_name:
            output = f"[{persona_name}]: {text}"
        else:
            output = text

        print(output, flush=True)

    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content to stdout.

        Args:
            channel_id: The identifier of the target channel (ignored for CLI).
            embed: A dictionary representing the embed content.
        """
        # Format embed for CLI output
        lines = []

        if "title" in embed:
            lines.append(f"** {embed['title']} **")

        if "description" in embed:
            lines.append(embed["description"])

        if "fields" in embed:
            for field in embed["fields"]:
                name = field.get("name", "")
                value = field.get("value", "")
                lines.append(f"\n{name}:\n  {value}")

        if "footer" in embed:
            footer = embed.get("footer", {})
            if isinstance(footer, dict):
                text = footer.get("text", "")
            else:
                text = str(footer)
            if text:
                lines.append(f"\n— {text}")

        output = "\n".join(lines) if lines else str(embed)
        print(output, flush=True)


__all__ = ["CLIInputAdapter", "CLIOutputAdapter"]
