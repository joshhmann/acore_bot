from __future__ import annotations

import pytest

from adapters.cli.adapter import CLIInputAdapter, get_cli_default_persona
from core.interfaces import AcoreEvent


pytestmark = pytest.mark.unit


def test_cli_default_persona_is_tai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GESTALT_CLI_DEFAULT_PERSONA", raising=False)
    assert get_cli_default_persona() == "tai"


@pytest.mark.asyncio
async def test_cli_input_uses_tai_when_no_mention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GESTALT_CLI_DEFAULT_PERSONA", raising=False)
    adapter = CLIInputAdapter()
    seen: list[AcoreEvent] = []

    def _capture(event: AcoreEvent) -> None:
        seen.append(event)

    adapter.on_event(_capture)
    await adapter._process_input_line("hello there")

    assert len(seen) == 1
    event = seen[0]
    assert event.payload["persona_id"] == "tai"


@pytest.mark.asyncio
async def test_cli_input_respects_env_default_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GESTALT_CLI_DEFAULT_PERSONA", "nora")
    adapter = CLIInputAdapter()
    seen: list[AcoreEvent] = []

    def _capture(event: AcoreEvent) -> None:
        seen.append(event)

    adapter.on_event(_capture)
    await adapter._process_input_line("hey")

    assert len(seen) == 1
    event = seen[0]
    assert event.payload["persona_id"] == "nora"
