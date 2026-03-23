from __future__ import annotations

from types import SimpleNamespace

import pytest

from adapters.discord.commands.system import SystemCog
from core.schemas import StructuredOutput


pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self) -> None:
        self.defer_calls: list[dict[str, object]] = []
        self.send_calls: list[dict[str, object]] = []

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.defer_calls.append({"ephemeral": ephemeral, "thinking": thinking})

    async def send_message(self, content=None, embed=None, ephemeral: bool = False) -> None:
        self.send_calls.append(
            {"content": content, "embed": embed, "ephemeral": ephemeral}
        )

    def is_done(self) -> bool:
        return bool(self.defer_calls or self.send_calls)


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
                    kind="command_status",
                    data={
                        "persona": "tai",
                        "mode": "tai_anis",
                        "provider": "openrouter",
                        "model": "moonshotai/kimi-k2.5",
                        "budget_remaining": 3,
                    },
                )
            ]
        )


class _FakeChatCog:
    def __init__(self) -> None:
        self.gestalt_runtime = _FakeRuntime()


class _FakeGuild:
    def __init__(self, member_count: int) -> None:
        self.member_count = member_count


class _FakeBot:
    def __init__(self, chat_cog=None) -> None:
        self._chat_cog = chat_cog
        self.latency = 0.123
        self.guilds = [_FakeGuild(10)]
        self.voice_clients = []

    def get_cog(self, name: str):
        if name == "ChatCog":
            return self._chat_cog
        return None


class _FakeInteraction:
    def __init__(self) -> None:
        self.channel = SimpleNamespace(id=123)
        self.user = SimpleNamespace(id=456)
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()


@pytest.mark.asyncio
async def test_discord_botstatus_uses_runtime_status_command() -> None:
    chat_cog = _FakeChatCog()
    bot = _FakeBot(chat_cog)
    cog = SystemCog(bot)
    interaction = _FakeInteraction()

    await cog.botstatus.callback(cog, interaction)

    assert interaction.response.defer_calls == [{"ephemeral": True, "thinking": True}]
    assert len(chat_cog.gestalt_runtime.calls) == 1
    event = chat_cog.gestalt_runtime.calls[0]
    assert event.text == "/status"
    assert event.platform == "discord"
    assert event.session_id == "discord:123:456"

    call = interaction.followup.calls[0]
    assert call["ephemeral"] is True
    embed = call["embed"]
    assert embed is not None
    assert embed.title == "🤖 Runtime Status"
    values = {field.name: field.value for field in embed.fields}
    assert values["Persona"] == "tai"
    assert values["Mode"] == "tai_anis"
    assert values["Provider"] == "openrouter"
    assert values["Model"] == "moonshotai/kimi-k2.5"


@pytest.mark.asyncio
async def test_discord_botstatus_requires_runtime() -> None:
    bot = _FakeBot(chat_cog=None)
    cog = SystemCog(bot)
    interaction = _FakeInteraction()

    await cog.botstatus.callback(cog, interaction)

    assert interaction.followup.calls == [
        {
            "content": "❌ Runtime not available. System status requires Gestalt runtime.",
            "embed": None,
            "ephemeral": True,
        }
    ]
