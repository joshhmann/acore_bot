"""
CLI adapter implementation for Acore bot following the Adapter SDK Contract.

This module provides a command-line interface for interacting with Acore personas
using the formalized four-phase lifecycle:
    parse -> to_runtime_event -> runtime -> from_runtime_response -> render

Usage:
    echo "@dagoth_ur hello" | python -m adapters.cli
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from typing import Any, Callable, Optional

from core.interfaces import (
    AcoreEvent,
    AdapterConfig,
    AdapterLifecycleContract,
    InputAdapter,
    OutputAdapter,
    PlatformFacts,
    RuntimeDecision,
)
from core.schemas import Response
from core.types import AcoreMessage

logger = logging.getLogger(__name__)


def get_cli_default_persona() -> str:
    """Get the default persona for CLI interactions.

    Reads from the GESTALT_CLI_DEFAULT_PERSONA environment variable.
    Falls back to 'tai' if not set.

    Returns:
        The default persona ID for CLI messages without explicit mentions.
    """
    return os.getenv("GESTALT_CLI_DEFAULT_PERSONA", "tai")


class CLIAdapter(AdapterLifecycleContract[str, None]):
    """CLI adapter implementing the formalized AdapterLifecycleContract.

    This adapter provides a command-line interface for interacting with Acore
    personas. It follows the four-phase lifecycle:

    1. parse: Extracts PlatformFacts from CLI input strings.
    2. to_runtime_event: Creates runtime Event from facts (inherited).
    3. from_runtime_response: Determines if response should be rendered.
    4. render: Prints response to stdout.

    The CLI adapter handles messages in the format: @persona_name message_content
    If no persona is specified, "default" is used.

    Attributes:
        config: AdapterConfig declaring CLI capabilities (no embeds/threads/reactions).
    """

    def __init__(self) -> None:
        """Initialize the CLI adapter with CLI-specific configuration."""
        super().__init__(
            AdapterConfig(
                platform_name="cli",
                supports_embeds=False,
                supports_threads=False,
                supports_reactions=False,
            )
        )

    def parse(self, raw_input: str) -> PlatformFacts:
        """Extract PlatformFacts from CLI input string.

        Parses messages in the format: @persona_name message_content.
        If no persona prefix is found, uses the maintained CLI default persona.

        Args:
            raw_input: The raw input string from stdin.

        Returns:
            PlatformFacts containing the parsed message data.
        """
        # Parse @persona_name prefix
        persona_id: str | None = None
        message_content = raw_input

        # Match @persona_name at the start of the message
        match = re.match(r"^@(\w+)\s*(.*)", raw_input)
        if match:
            persona_id = match.group(1)
            message_content = match.group(2).strip()
        else:
            # No persona specified, use maintained CLI default behavior.
            persona_id = get_cli_default_persona()
            message_content = raw_input

        return PlatformFacts(
            text=message_content,
            user_id="cli_user",
            room_id="cli_channel",
            message_id="",  # CLI doesn't have message IDs
            is_direct_mention=True,  # CLI is always direct
            is_reply_to_bot=False,
            is_persona_message=False,
            has_visual_context=False,
            author_is_bot=False,
            platform_flags={
                "requested_persona": persona_id,
                "raw_input": raw_input,
            },
            raw_metadata={
                "cli_version": "1.0",
            },
        )

    async def render(
        self,
        context: None,
        decision: RuntimeDecision,
        response: Response,
    ) -> None:
        """Render the runtime response to stdout.

        Prints the response text with an optional persona prefix.
        If decision.should_respond is False, nothing is printed.

        Args:
            context: None for CLI (no platform context needed).
            decision: The runtime's decision about whether/how to respond.
            response: The response content from the runtime.
        """
        if not decision.should_respond:
            logger.debug(f"Skipping render: {decision.reason}")
            return

        persona_name = response.persona_id or decision.persona_id or "bot"

        if response.text:
            output = f"[{persona_name}]: {response.text}"
            print(output, flush=True)


class CLIInputAdapter(InputAdapter):
    """Input adapter that reads user input from stdin and emits AcoreEvent.

    This is the legacy input adapter interface, preserved for backward
    compatibility. It uses CLIAdapter internally for the lifecycle contract.

    Parses messages in the format: @persona_name message_content
    Creates AcoreMessage with author_id="cli_user", channel_id="cli_channel"

    Attributes:
        _running: Whether the adapter is currently running.
        _event_callback: Callback function for incoming events.
        _reader_task: Background task for reading stdin.
        _adapter: The CLIAdapter instance for lifecycle contract compliance.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the CLI input adapter."""
        super().__init__(*args, **kwargs)
        self._running: bool = False
        self._event_callback: Optional[Callable[[AcoreEvent], None]] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._adapter = CLIAdapter()

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

        Uses the CLIAdapter lifecycle contract to parse the input and
        create the appropriate AcoreEvent.

        Args:
            line: The input line from stdin.
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
            # No persona specified, use default from environment
            persona_id = get_cli_default_persona()
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

    This is the legacy output adapter interface, preserved for backward
    compatibility. It prints messages in a human-readable format with
    optional persona prefix.

    For new code, consider using CLIAdapter.render() directly.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the CLI output adapter."""
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

        Since CLI doesn't support rich embeds, this formats the embed
        as plain text for human-readable output.

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


__all__ = [
    # New contract-based adapter
    "AdapterConfig",
    "AdapterLifecycleContract",
    "CLIAdapter",
    "RuntimeDecision",
    # Legacy adapters (backward compatibility)
    "CLIInputAdapter",
    "CLIOutputAdapter",
    # Utility functions
    "get_cli_default_persona",
]
