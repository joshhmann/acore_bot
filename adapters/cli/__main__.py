"""CLI adapter entry point for running with `python -m adapters.cli`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Sequence

from adapters.cli.adapter import CLIInputAdapter, CLIOutputAdapter
from adapters.cli.play import PlayConfig, PlayRunner
from adapters.runtime_factory import build_gestalt_runtime
from core.interfaces import AcoreEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_event(event: AcoreEvent) -> None:
    """Handle incoming events from the CLI input adapter."""
    logger.info(f"Received event: type={event.type}, source={event.source_adapter}")

    if event.type == "message":
        payload = event.payload
        message = payload.get("message")
        persona_id = payload.get("persona_id")

        if message:
            logger.info(f"Message from {message.author_id}: {message.text}")
            logger.info(f"Target persona: {persona_id}")
            output = CLIOutputAdapter()
            response_text = f"Received: '{message.text}' (targeting @{persona_id})"
            await output.send(
                channel_id=message.channel_id,
                text=response_text,
                persona_id="cli_bot",
                display_name="CLI Bot",
            )


def handle_event_sync(event: AcoreEvent) -> None:
    asyncio.create_task(handle_event(event))


async def main() -> None:
    """Main entry point for CLI adapter."""
    logger.info("Starting CLI adapter...")

    # Create input adapter
    input_adapter = CLIInputAdapter()

    # Register event handler
    input_adapter.on_event(handle_event_sync)

    # Start input adapter
    await input_adapter.start()

    try:
        # Wait for input processing to complete (EOF or interrupt)
        while input_adapter._running:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await input_adapter.stop()
        logger.info("CLI adapter stopped")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gestalt")
    subparsers = parser.add_subparsers(dest="command")

    play_parser = subparsers.add_parser(
        "play",
        help="Run bounded MCP play loop (CLI demo)",
    )
    play_parser.add_argument("--persona", required=True, help="Persona id")
    play_parser.add_argument("--room", required=True, help="Room id")
    play_parser.add_argument("--server", required=True, help="MCP server name")
    play_parser.add_argument("--bot", required=True, help="Bot name for rs tools")
    play_parser.add_argument("--steps", type=int, default=10, help="Step count")
    play_parser.add_argument(
        "--tick-seconds", type=float, default=1.0, help="Delay between steps"
    )
    play_parser.add_argument(
        "--enable-network-tools",
        action="store_true",
        default=False,
        help="Enable network-tier tools for this run",
    )
    play_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print calls without executing",
    )
    play_parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Verbose per-step output",
    )
    return parser


def _build_play_config(args: argparse.Namespace) -> PlayConfig:
    return PlayConfig(
        persona_id=str(args.persona),
        room_id=str(args.room),
        server_name=str(args.server),
        bot_name=str(args.bot),
        steps=max(1, int(args.steps)),
        tick_seconds=max(0.0, float(args.tick_seconds)),
        enable_network_tools=bool(args.enable_network_tools),
        dry_run=bool(args.dry_run),
        verbose=bool(args.verbose),
    )


async def _run_play(args: argparse.Namespace) -> int:
    config = _build_play_config(args)
    runtime = build_gestalt_runtime(legacy_llm=None)
    runner = PlayRunner(runtime=runtime, config=config)
    return await runner.run()


async def _dispatch(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    raw_args = list(argv) if argv is not None else list(sys.argv[1:])
    if raw_args and raw_args[0] == "gestalt":
        raw_args = raw_args[1:]
    args = parser.parse_args(raw_args)

    if args.command == "play":
        return await _run_play(args)

    await main()
    return 0


def cli(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_dispatch(argv))


if __name__ == "__main__":
    raise SystemExit(cli())
