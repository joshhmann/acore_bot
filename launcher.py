#!/usr/bin/env python3
"""Unified runtime-first launcher for maintained Gestalt surfaces."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from typing import Any

from gestalt.env import load_environment_profile
from gestalt.runtime_bootstrap import create_runtime_host


# Legacy compatibility symbol retained for tests and boundary checks.
ServiceFactory = None


MODEL_PRESETS: dict[str, str] = {
    "claude": "anthropic/claude-3.5-sonnet",
    "gpt4o": "openai/gpt-4o-mini",
    "llama": "llama3.2",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LaunchConfig:
    discord_enabled: bool
    cli_enabled: bool
    web_enabled: bool
    web_port: int
    env_profile: str = ""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="launcher.py")
    parser.add_argument(
        "--profile",
        choices=("discord", "cli", "web", "all"),
        default="all",
        help="Startup profile preset",
    )
    parser.add_argument("--discord", action="store_true", help="Enable Discord")
    parser.add_argument("--no-discord", action="store_true", help="Disable Discord")
    parser.add_argument("--cli", action="store_true", help="Enable CLI")
    parser.add_argument("--no-cli", action="store_true", help="Disable CLI")
    parser.add_argument("--web", action="store_true", help="Enable web")
    parser.add_argument("--no-web", action="store_true", help="Disable web")
    parser.add_argument("--web-port", type=int, default=8000, help="Web adapter port")
    parser.add_argument(
        "--env-profile",
        default="",
        help="Optional .env profile suffix to load before startup",
    )
    parser.add_argument("--provider", default="", help="Override LLM provider")
    parser.add_argument("--model", default="", help="Override model")
    parser.add_argument(
        "--model-preset",
        choices=tuple(sorted(MODEL_PRESETS.keys())),
        default="",
        help="Apply a named model preset",
    )
    return parser


def _resolve_launch_config(args: argparse.Namespace) -> LaunchConfig:
    profile_defaults = {
        "discord": {"discord_enabled": True, "cli_enabled": False, "web_enabled": False},
        "cli": {"discord_enabled": False, "cli_enabled": True, "web_enabled": False},
        "web": {"discord_enabled": False, "cli_enabled": False, "web_enabled": True},
        "all": {"discord_enabled": True, "cli_enabled": True, "web_enabled": True},
    }
    resolved = dict(profile_defaults[str(args.profile)])

    if args.discord:
        resolved["discord_enabled"] = True
    if args.no_discord:
        resolved["discord_enabled"] = False
    if args.cli:
        resolved["cli_enabled"] = True
    if args.no_cli:
        resolved["cli_enabled"] = False
    if args.web:
        resolved["web_enabled"] = True
    if args.no_web:
        resolved["web_enabled"] = False

    if not any(resolved.values()):
        raise ValueError("No adapters enabled")

    return LaunchConfig(
        discord_enabled=bool(resolved["discord_enabled"]),
        cli_enabled=bool(resolved["cli_enabled"]),
        web_enabled=bool(resolved["web_enabled"]),
        web_port=max(1, int(args.web_port)),
        env_profile=str(args.env_profile or "").strip().lower(),
    )


def _apply_env_profile(profile: str) -> None:
    load_environment_profile(profile)


def _apply_llm_overrides(args: argparse.Namespace) -> None:
    provider = str(args.provider or os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider:
        os.environ["LLM_PROVIDER"] = provider

    requested_model = ""
    if args.model_preset:
        requested_model = MODEL_PRESETS[str(args.model_preset)]
    elif args.model:
        requested_model = str(args.model).strip()

    if not requested_model:
        return

    active_provider = str(os.getenv("LLM_PROVIDER") or provider or "ollama").lower()
    os.environ["OPENAI_COMPAT_MODEL"] = requested_model
    if active_provider == "ollama":
        os.environ["OLLAMA_MODEL"] = requested_model
    elif active_provider == "openrouter":
        os.environ["OPENROUTER_MODEL"] = requested_model


class AcoreLauncher:
    """Runtime-first multi-surface launcher."""

    def __init__(self) -> None:
        self.adapters: dict[str, dict[str, Any]] = {}
        self.runtime_host = None
        self._shutdown_event = asyncio.Event()

    async def start(self, config: LaunchConfig) -> None:
        logger.info("Starting Gestalt runtime surfaces")
        self.runtime_host = create_runtime_host()

        if config.cli_enabled:
            await self._start_cli()
        if config.web_enabled:
            await self._start_web(config.web_port)
        if config.discord_enabled:
            await self._start_discord()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._signal_handler)
            except NotImplementedError:
                pass

        await self._shutdown_event.wait()

    async def _start_cli(self) -> None:
        from adapters.cli.__main__ import _build_event_handler
        from adapters.cli.adapter import CLIInputAdapter, CLIOutputAdapter

        input_adapter = CLIInputAdapter()
        output_adapter = CLIOutputAdapter()
        input_adapter.on_event(_build_event_handler(self.runtime_host.runtime, output_adapter))
        await input_adapter.start()
        self.adapters["cli"] = {"input": input_adapter, "output": output_adapter}
        logger.info("CLI adapter started")

    async def _start_web(self, port: int) -> None:
        from adapters.web.output import WebOutputAdapter

        input_adapter = self.runtime_host.create_web_adapter(port=port)
        output_adapter = WebOutputAdapter()
        await input_adapter.start()
        await output_adapter.start()
        self.adapters["web"] = {"input": input_adapter, "output": output_adapter}
        logger.info("Web adapter started on port %s", port)

    async def _start_discord(self) -> None:
        from adapters.discord.discord_bot import GestaltDiscordBot

        token = str(os.environ.get("DISCORD_TOKEN") or "").strip()
        if not token:
            raise ValueError("DISCORD_TOKEN environment variable not set")

        bot = GestaltDiscordBot(runtime_host=self.runtime_host, command_prefix="!")
        task = asyncio.create_task(bot.start(token))
        self.adapters["discord"] = {"bot": bot, "task": task}
        logger.info("Discord adapter started")

    def _signal_handler(self) -> None:
        self._shutdown_event.set()

    async def stop(self) -> None:
        logger.info("Stopping Gestalt runtime surfaces")
        for name, adapter in self.adapters.items():
            try:
                if name == "discord":
                    bot = adapter.get("bot")
                    task = adapter.get("task")
                    if bot is not None:
                        await bot.close()
                    if task is not None:
                        try:
                            await asyncio.wait_for(task, timeout=5.0)
                        except Exception:
                            pass
                    continue
                if "input" in adapter:
                    await adapter["input"].stop()
                if "output" in adapter:
                    await adapter["output"].stop()
            except Exception as exc:
                logger.error("Error stopping %s adapter: %s", name, exc)

        if self.runtime_host is not None:
            await self.runtime_host.close()
            self.runtime_host = None


async def _run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _apply_env_profile(str(args.env_profile or ""))
    _apply_llm_overrides(args)
    config = _resolve_launch_config(args)

    launcher = AcoreLauncher()
    try:
        await launcher.start(config)
    finally:
        await launcher.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_run(argv))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logger.error("Fatal launcher error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
