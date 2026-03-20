"""CLI adapter entry point for running with `python -m adapters.cli`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Sequence

from adapters.cli.adapter import CLIInputAdapter, CLIOutputAdapter
from adapters.cli.play import PlayConfig, PlayRunner
from core.interfaces import AcoreEvent, PlatformFacts, build_runtime_event_from_facts
from gestalt.runtime_bootstrap import create_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def _handle_cli_event(runtime, output: CLIOutputAdapter, event: AcoreEvent) -> None:
    """Route CLI adapter messages through the maintained runtime path."""
    if event.type != "message":
        return

    payload = event.payload
    message = payload.get("message")
    persona_id = str(payload.get("persona_id") or "default")
    if message is None:
        return

    runtime_event = build_runtime_event_from_facts(
        facts=PlatformFacts(
            text=str(message.text or ""),
            user_id=str(message.author_id or "cli_user"),
            room_id=str(message.channel_id or "cli_channel"),
        ),
        platform_name="cli",
        persona_id=persona_id,
    )
    response = await runtime.handle_event(runtime_event)
    await output.send(
        channel_id=str(message.channel_id or "cli_channel"),
        text=str(response.text or ""),
        persona_id=str(response.persona_id or ""),
    )


def _build_event_handler(runtime, output: CLIOutputAdapter):
    def _handler(event: AcoreEvent) -> None:
        asyncio.create_task(_handle_cli_event(runtime, output, event))

    return _handler


async def main() -> None:
    """Main entry point for CLI adapter."""
    logger.info("Starting CLI adapter...")
    runtime = create_runtime()
    input_adapter = CLIInputAdapter()
    output_adapter = CLIOutputAdapter()
    input_adapter.on_event(_build_event_handler(runtime, output_adapter))
    await input_adapter.start()

    try:
        while input_adapter._running:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await input_adapter.stop()
        await runtime.close()
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
    runtime = create_runtime()
    runner = PlayRunner(runtime=runtime, config=config)
    try:
        return await runner.run()
    finally:
        await runtime.close()


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
