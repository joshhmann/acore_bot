"""
CLI adapters scaffolding for Acore bot.

This module provides skeleton classes for a simple command-line interface:
- CLIInputAdapter: reads from stdin (async) and converts input into AcoreEvent
- CLIOutputAdapter: writes to stdout (async) for outgoing events

Notes:
- This is intentionally minimal. It only provides the required abstract method
  implementations so the classes can be instantiated and imported without
  errors. It is not a full REPL yet.
- Async stdin handling is prepared to be wired in later, using asyncio streams.
- No Discord imports are used.
"""

import asyncio
from typing import Any

from core.interfaces import InputAdapter, OutputAdapter


class CLIInputAdapter(InputAdapter):
    """Input adapter that will read user input from stdin and emit AcoreEvent.

    Skeleton implementation: methods are stubs that can be extended to hook
    into an asyncio event loop reading from sys.stdin.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._running: bool = False

    async def start(self) -> None:
        """Start the CLI input listener.

        Currently a placeholder to illustrate async startup. The eventual
        implementation will spawn a background task that reads from stdin and
        converts lines into AcoreEvent instances.
        """
        self._running = True
        # Placeholder: in a real implementation you might do something like:
        # self._reader_task = asyncio.create_task(self._read_stdin_loop())
        return None

    async def stop(self) -> None:
        """Stop the CLI input listener."""
        self._running = False
        # Placeholder: cancel the background stdin reader if it exists
        return None

    async def on_event(self, event: Any) -> None:
        """Handle an incoming event produced by the input layer.

        This is a stub to satisfy the abstract method contract. The real
        implementation would push the converted AcoreEvent into the central
        processing queue.
        """
        # TODO: convert event to AcoreEvent and dispatch
        return None


class CLIOutputAdapter(OutputAdapter):
    """Output adapter that will write to stdout.

    Skeleton implementation to illustrate async capability. Real printing logic
    will be added when integrating with the rest of the system.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    async def send(self, event: Any) -> None:
        """Send a basic event to stdout (plain text)."""
        # Placeholder: in a real implementation convert event to string and print
        return None

    async def send_embed(self, embed: Any) -> None:
        """Send an embed-style payload to stdout (human-friendly print)."""
        # Placeholder: format embed for stdout if needed
        return None


__all__ = ["CLIInputAdapter", "CLIOutputAdapter"]
