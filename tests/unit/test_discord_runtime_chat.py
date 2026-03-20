from __future__ import annotations

from types import SimpleNamespace

import pytest

from adapters.discord.commands.runtime_chat import RuntimeChatCog
from core.schemas import Response


pytestmark = pytest.mark.unit


class _FakeResponseChannel:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []
        self.typing_entered = 0

    def typing(self):
        channel = self

        class _Typing:
            async def __aenter__(self_inner):
                channel.typing_entered += 1
                return self_inner

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        return _Typing()

    async def send(self, content, reference=None, mention_author=False):
        self.sent.append(
            {
                "content": content,
                "reference": reference,
                "mention_author": mention_author,
            }
        )


class _FakeInteractionResponse:
    def __init__(self) -> None:
        self.defer_calls: list[dict[str, object]] = []

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.defer_calls.append({"ephemeral": ephemeral, "thinking": thinking})


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

    async def handle_event(self, event):
        self.calls.append(event)
        return Response(text="runtime reply", persona_id="tai")


class _FakeBot:
    def __init__(self) -> None:
        self.user = SimpleNamespace(id=99)
        self.command_prefix = "!"


@pytest.mark.asyncio
async def test_runtime_chat_slash_command_routes_through_runtime() -> None:
    runtime = _FakeRuntime()
    cog = RuntimeChatCog(_FakeBot(), runtime)
    interaction = SimpleNamespace(
        channel=SimpleNamespace(id=123),
        user=SimpleNamespace(id=456),
        response=_FakeInteractionResponse(),
        followup=_FakeFollowup(),
    )

    await cog.chat.callback(cog, interaction, "hello there")

    assert interaction.response.defer_calls == [{"ephemeral": False, "thinking": True}]
    assert len(runtime.calls) == 1
    event = runtime.calls[0]
    assert event.text == "hello there"
    assert event.platform == "discord"
    assert event.session_id == "discord:123:456"
    assert interaction.followup.calls == [
        {"content": "runtime reply", "embed": None, "ephemeral": False}
    ]


@pytest.mark.asyncio
async def test_runtime_chat_on_message_requires_direct_mention() -> None:
    runtime = _FakeRuntime()
    bot = _FakeBot()
    cog = RuntimeChatCog(bot, runtime)
    channel = _FakeResponseChannel()
    message = SimpleNamespace(
        id=1,
        content="hello world",
        author=SimpleNamespace(id=123, bot=False),
        channel=channel,
        mentions=[],
        is_system=lambda: False,
    )

    await cog.on_message(message)

    assert runtime.calls == []
    assert channel.sent == []


@pytest.mark.asyncio
async def test_runtime_chat_on_message_replies_once_for_direct_mention() -> None:
    runtime = _FakeRuntime()
    bot = _FakeBot()
    cog = RuntimeChatCog(bot, runtime)
    channel = _FakeResponseChannel()
    message = SimpleNamespace(
        id=7,
        content="<@99> hey runtime",
        author=SimpleNamespace(id=123, bot=False),
        channel=SimpleNamespace(
            id=456,
            send=channel.send,
            typing=channel.typing,
        ),
        mentions=[SimpleNamespace(id=99)],
        is_system=lambda: False,
    )

    await cog.on_message(message)
    await cog.on_message(message)

    assert len(runtime.calls) == 2
    assert runtime.calls[0].text == "hey runtime"
    assert channel.sent[0]["content"] == "runtime reply"
    assert channel.sent[0]["reference"] is message
    assert channel.sent[0]["mention_author"] is False
