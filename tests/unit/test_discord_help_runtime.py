from __future__ import annotations

from types import SimpleNamespace

import pytest

from adapters.discord.commands.help import HelpCog
from core.schemas import StructuredOutput


pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.calls.append({"ephemeral": ephemeral, "thinking": thinking})


class _FakeFollowup:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send(self, content=None, embed=None, ephemeral: bool = False) -> None:
        self.calls.append(
            {"content": content, "embed": embed, "ephemeral": ephemeral}
        )


class _FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def handle_event_envelope(self, event):
        self.calls.append(event)
        return SimpleNamespace(
            outputs=[
                StructuredOutput(
                    kind="command_help",
                    data={
                        "commands": [
                            {"usage": "/help", "description": "List available commands."},
                            {"usage": "/status", "description": "Show session status."},
                        ]
                    },
                )
            ]
        )


class _FakeChatCog:
    def __init__(self) -> None:
        self.gestalt_runtime = _FakeRuntime()


class _FakeBot:
    def __init__(self, chat_cog=None) -> None:
        self._chat_cog = chat_cog
        self.removed_commands: list[str] = []

    def get_cog(self, name: str):
        if name == "ChatCog":
            return self._chat_cog
        return None

    def remove_command(self, name: str) -> None:
        self.removed_commands.append(name)


class _FakeInteraction:
    def __init__(self) -> None:
        self.channel = SimpleNamespace(id=123)
        self.user = SimpleNamespace(id=456)
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()


@pytest.mark.asyncio
async def test_discord_help_command_uses_runtime_help_registry() -> None:
    chat_cog = _FakeChatCog()
    bot = _FakeBot(chat_cog)
    cog = HelpCog(bot)
    interaction = _FakeInteraction()

    await cog.help_command.callback(cog, interaction)

    assert bot.removed_commands == ["help"]
    assert interaction.response.calls == [{"ephemeral": True, "thinking": True}]
    assert len(chat_cog.gestalt_runtime.calls) == 1
    event = chat_cog.gestalt_runtime.calls[0]
    assert event.text == "/help"
    assert event.platform == "discord"
    assert event.session_id == "discord:123:456"

    call = interaction.followup.calls[0]
    assert call["ephemeral"] is True
    embed = call["embed"]
    assert embed is not None
    assert embed.title == "Gestalt Commands"
    assert "/help" in embed.fields[0].value
    assert "/status" in embed.fields[0].value


@pytest.mark.asyncio
async def test_discord_help_command_requires_runtime() -> None:
    bot = _FakeBot(chat_cog=None)
    cog = HelpCog(bot)
    interaction = _FakeInteraction()

    await cog.help_command.callback(cog, interaction)

    assert interaction.followup.calls == [
        {
            "content": "❌ Runtime not available. Help requires Gestalt runtime.",
            "embed": None,
            "ephemeral": True,
        }
    ]
