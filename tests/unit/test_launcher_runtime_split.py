from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import launcher


pytestmark = pytest.mark.unit


class _DummyInputAdapter:
    def __init__(self, *args, **kwargs):
        del args, kwargs
        self.callback = None
        self.started = False
        self.stopped = False

    def on_event(self, callback):
        self.callback = callback

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class _DummyOutputAdapter:
    def __init__(self, *args, **kwargs):
        del args, kwargs
        self.started = False
        self.stopped = False
        self.sent = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send(self, channel_id, text, **options):
        self.sent.append((channel_id, text, options))


class _DummyRuntime:
    def __init__(self):
        self.events = []
        self.closed = False

    async def handle_event(self, event):
        self.events.append(event)
        return SimpleNamespace(text="ok", persona_id="tai")

    async def close(self):
        self.closed = True


class _ForbiddenFactory:
    def __init__(self, *args, **kwargs):
        raise AssertionError("ServiceFactory should not be constructed")


class _CountingFactory:
    calls = 0

    def __init__(self, *args, **kwargs):
        del args, kwargs
        type(self).calls += 1

    def create_services(self):
        return {"legacy": True}


class _DummyDiscordBot:
    def __init__(self, runtime_host, command_prefix="!"):
        self.runtime_host = runtime_host
        self.command_prefix = command_prefix
        self.started_with = None
        self.closed = False

    async def start(self, token):
        self.started_with = token

    async def close(self):
        self.closed = True


class _DummyRuntimeHost:
    def __init__(self, runtime):
        self.runtime = runtime

    def create_web_adapter(self, *, host="0.0.0.0", port=8000):
        del host, port
        return _DummyInputAdapter()

    async def close(self):
        await self.runtime.close()


@pytest.mark.asyncio
async def test_launcher_cli_web_do_not_require_service_factory(monkeypatch):
    runtime = _DummyRuntime()
    launcher_instance = launcher.AcoreLauncher()
    launcher_instance._shutdown_event.set()

    monkeypatch.setattr(launcher, "ServiceFactory", _ForbiddenFactory)
    monkeypatch.setattr(
        launcher, "create_runtime_host", lambda: _DummyRuntimeHost(runtime)
    )

    import adapters.cli.adapter as cli_adapter
    import adapters.web.output as web_output

    monkeypatch.setattr(cli_adapter, "CLIInputAdapter", _DummyInputAdapter)
    monkeypatch.setattr(cli_adapter, "CLIOutputAdapter", _DummyOutputAdapter)
    monkeypatch.setattr(web_output, "WebOutputAdapter", _DummyOutputAdapter)

    config = launcher.LaunchConfig(
        discord_enabled=False,
        cli_enabled=True,
        web_enabled=True,
        web_port=8000,
        env_profile="",
    )

    await launcher_instance.start(config)
    await launcher_instance.stop()

    assert runtime.closed is True
    assert "cli" in launcher_instance.adapters
    assert "web" in launcher_instance.adapters


@pytest.mark.asyncio
async def test_launcher_discord_uses_runtime_first_bot(monkeypatch):
    launcher_instance = launcher.AcoreLauncher()
    launcher_instance._shutdown_event.set()
    runtime = _DummyRuntime()
    monkeypatch.setattr(launcher, "ServiceFactory", _ForbiddenFactory)
    monkeypatch.setattr(
        launcher, "create_runtime_host", lambda: _DummyRuntimeHost(runtime)
    )
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    import adapters.discord.discord_bot as discord_bot_module

    monkeypatch.setattr(discord_bot_module, "GestaltDiscordBot", _DummyDiscordBot)

    config = launcher.LaunchConfig(
        discord_enabled=True,
        cli_enabled=False,
        web_enabled=False,
        web_port=8000,
        env_profile="",
    )

    await launcher_instance.start(config)

    assert "discord" in launcher_instance.adapters
    discord_adapter = launcher_instance.adapters["discord"]
    bot = discord_adapter["bot"]
    discord_task = discord_adapter["task"]
    await asyncio.wait_for(discord_task, timeout=1.0)
    assert isinstance(bot, _DummyDiscordBot)
    assert bot.command_prefix == "!"
    assert bot.started_with == "test-token"

    await launcher_instance.stop()
    assert bot.closed is True


def test_main_py_is_explicitly_deprecated_shim() -> None:
    main_text = Path("main.py").read_text(encoding="utf-8")
    launcher_text = Path("launcher.py").read_text(encoding="utf-8")

    assert "DEPRECATED" in main_text
    assert "launcher.py --discord" in main_text
    assert "main.py is deprecated" in main_text
    assert "from services.core.factory import ServiceFactory" in main_text
    assert "from adapters.discord.discord_bot import GestaltDiscordBot" in launcher_text


def test_discord_runtime_startup_loads_runtime_native_cogs_only() -> None:
    discord_bot_text = Path("adapters/discord/discord_bot.py").read_text(
        encoding="utf-8"
    )

    assert "from adapters.discord.commands.runtime_chat import RuntimeChatCog" in discord_bot_text
    assert "from adapters.discord.commands.social import SocialCommandsCog" in discord_bot_text
    assert "from adapters.discord.commands.help import HelpCog" in discord_bot_text
    assert "from adapters.discord.commands.system import SystemCog" in discord_bot_text
    assert "from adapters.discord.commands.profile import ProfileCommandsCog" in discord_bot_text
    assert "from adapters.discord.commands.search import SearchCommandsCog" in discord_bot_text
    assert "CharacterCommandsCog" not in discord_bot_text


def test_discord_runtime_startup_does_not_import_hybrid_chat_seam() -> None:
    discord_bot_text = Path("adapters/discord/discord_bot.py").read_text(
        encoding="utf-8"
    )

    assert "from adapters.discord.commands.chat.main import ChatCog" not in discord_bot_text
    assert "from services." not in discord_bot_text


def test_discord_commands_package_does_not_reexport_hybrid_chat() -> None:
    commands_init = Path("adapters/discord/commands/__init__.py").read_text(
        encoding="utf-8"
    )

    assert "from .chat import ChatCog" not in commands_init
    assert "RuntimeChatCog" in commands_init
