from __future__ import annotations

import json

import pytest

from core.schemas import ToolCall
from tools.policy import ToolPolicy
from tools.registry import ToolRegistry
from tools.runner import ToolRunner
from tools.shell_exec import tool_shell_exec


pytestmark = pytest.mark.unit


def _runner() -> ToolRunner:
    registry = ToolRegistry()
    registry.register_tool(
        name="shell_exec",
        schema={"name": "shell_exec", "parameters": {"type": "object"}},
        handler=tool_shell_exec,
    )
    policy = ToolPolicy(
        allowlist_by_environment={"cli": {"shell_exec"}},
        tool_risk_tiers={"shell_exec": "safe"},
    )
    return ToolRunner(registry=registry, policy=policy)


@pytest.mark.asyncio
async def test_shell_exec_allows_safe_command() -> None:
    runner = _runner()
    results = await runner.execute(
        persona_id="tai",
        environment="cli",
        tool_calls=[ToolCall(name="shell_exec", arguments={"command": "pwd"})],
    )
    assert results[0].error is None
    payload = json.loads(results[0].output)
    assert isinstance(payload.get("exit_code"), int)


@pytest.mark.asyncio
async def test_shell_exec_blocks_dangerous_by_default() -> None:
    runner = _runner()
    results = await runner.execute(
        persona_id="tai",
        environment="cli",
        tool_calls=[
            ToolCall(name="shell_exec", arguments={"command": "rm -rf /tmp/test"})
        ],
    )
    assert results[0].error is not None
    assert "safety" in str(results[0].error).lower()


@pytest.mark.asyncio
async def test_shell_exec_truncates_large_output() -> None:
    runner = _runner()
    results = await runner.execute(
        persona_id="tai",
        environment="cli",
        tool_calls=[
            ToolCall(
                name="shell_exec",
                arguments={
                    "command": "python3 -c \"print('x'*8000)\"",
                    "max_output_chars": 500,
                },
            )
        ],
    )
    payload = json.loads(results[0].output)
    assert payload["truncated"] is True


@pytest.mark.asyncio
async def test_shell_exec_trace_redacts_command() -> None:
    runner = _runner()
    _, traces = await runner.execute_with_trace(
        persona_id="tai",
        environment="cli",
        tool_calls=[ToolCall(name="shell_exec", arguments={"command": "echo hello"})],
    )
    tool_trace = [t for t in traces if t.get("trace_type") == "tool"]
    assert tool_trace
    assert tool_trace[0]["args"]["command"] == "<redacted>"
