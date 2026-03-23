from __future__ import annotations

import asyncio

import pytest

from adapters.cli.__main__ import _build_event_handler, _handle_cli_event
from core.interfaces import AcoreEvent
from core.schemas import Response
from core.types import AcoreMessage


pytestmark = pytest.mark.unit


class _FakeRuntime:
    def __init__(self) -> None:
        self.last_event = None

    async def handle_event(self, event):
        self.last_event = event
        return Response(text="Hello from runtime", persona_id="dagoth_ur")


class _FakeOutput:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, channel_id: str, text: str, **options):
        self.sent.append(
            {
                "channel_id": channel_id,
                "text": text,
                "persona_id": options.get("persona_id", ""),
            }
        )


@pytest.mark.asyncio
async def test_handle_cli_event_routes_to_runtime() -> None:
    runtime = _FakeRuntime()
    output = _FakeOutput()
    event = AcoreEvent(
        type="message",
        payload={
            "message": AcoreMessage(
                text="hello",
                author_id="cli_user",
                channel_id="cli_channel",
            ),
            "persona_id": "default",
        },
        source_adapter="cli",
    )

    await _handle_cli_event(runtime, output, event)

    assert runtime.last_event is not None
    assert runtime.last_event.text == "hello"
    assert runtime.last_event.user_id == "cli_user"
    assert runtime.last_event.room_id == "cli_channel"
    assert runtime.last_event.platform == "cli"
    assert runtime.last_event.metadata["persona_id"] == "default"
    assert output.sent == [
        {
            "channel_id": "cli_channel",
            "text": "Hello from runtime",
            "persona_id": "dagoth_ur",
        }
    ]


@pytest.mark.asyncio
async def test_event_handler_schedules_runtime_processing() -> None:
    runtime = _FakeRuntime()
    output = _FakeOutput()
    handler = _build_event_handler(runtime, output)
    event = AcoreEvent(
        type="message",
        payload={
            "message": AcoreMessage(
                text="queued",
                author_id="cli_user",
                channel_id="cli_channel",
            ),
            "persona_id": "default",
        },
        source_adapter="cli",
    )

    handler(event)
    await asyncio.sleep(0)

    assert runtime.last_event is not None
    assert runtime.last_event.text == "queued"
    assert output.sent[0]["text"] == "Hello from runtime"
