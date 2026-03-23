from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.runtime import GestaltRuntime, RuntimeSessionState
from core.schemas import ErrorOutput, Event, StructuredOutput
from core.trace import TraceEmitter
from memory.types import ActionRecord
from tools.policy import ToolPolicy, ToolRiskTier


pytestmark = pytest.mark.unit


class _FakeToolRunner:
    def __init__(self) -> None:
        self.called = False

    async def execute_with_trace(self, **kwargs):
        self.called = True
        del kwargs
        return [], []


class _RuntimeHarness:
    _safe_tool_arguments = staticmethod(GestaltRuntime._safe_tool_arguments)
    _build_span_trace = GestaltRuntime._build_span_trace
    _record_tool_action = GestaltRuntime._record_tool_action
    _partition_tool_calls_for_approval = GestaltRuntime._partition_tool_calls_for_approval
    _command_shell = GestaltRuntime._command_shell
    _command_status = GestaltRuntime._command_status

    def __init__(self) -> None:
        self.trace_emitter = TraceEmitter()
        self.context_cache = {}
        self.context_cache_ttl_seconds = 300
        self.personas = SimpleNamespace(
            by_id=lambda persona_id: SimpleNamespace(persona_id=persona_id)
        )
        self.provider_router = SimpleNamespace(
            resolve_provider_name=lambda persona_id, mode: "openrouter",
            providers={"openrouter": object()},
        )
        self.memory_coordinator = SimpleNamespace(
            record_action=AsyncMock(
                side_effect=lambda **kwargs: ActionRecord(
                    action_id="action-1",
                    action_type=kwargs["action_type"],
                    tool_name=kwargs.get("tool_name"),
                    inputs=kwargs["inputs"],
                    output=kwargs["output"],
                    outcome=kwargs["outcome"],
                    persona_id=kwargs["namespace"].persona_id,
                    session_id=kwargs["session_id"],
                    timestamp=datetime.now(timezone.utc),
                    approval_state=kwargs.get("approval_state"),
                )
            )
        )
        self.tool_runner = _FakeToolRunner()

    def _mcp_servers_snapshot(self):
        return []

    def _project_context_snapshot(self):
        return {"is_git_repo": False}

    def _context_cache_metrics_for_session(self, *, session_id: str):
        del session_id
        return {
            "cache_model": "stable_prefix",
            "entry_count": 0,
            "total_hits": 0,
            "tokens_saved_estimate": 0,
            "ttl_seconds": 300,
            "provider_cached_input_tokens": 0,
            "last_cache_key": "",
            "last_cache_hit": False,
            "last_cache_reason": "",
        }

    def _provider_model(self, provider):
        del provider
        return "test-model"


def _make_runtime() -> _RuntimeHarness:
    return _RuntimeHarness()


def _make_session() -> RuntimeSessionState:
    return RuntimeSessionState(
        session_id="session-1",
        persona_id="tai",
        mode="default",
    )


def test_tool_policy_requires_approval_for_dangerous_tools() -> None:
    policy = ToolPolicy(
        dangerous_enabled=True,
        tool_risk_tiers={"shell_exec": ToolRiskTier.DANGEROUS.value},
    )

    assert policy.requires_approval("shell_exec", yolo_enabled=False) is True
    assert policy.requires_approval("shell_exec", yolo_enabled=True) is False


@pytest.mark.asyncio
async def test_command_shell_queues_approval_for_dangerous_tool() -> None:
    runtime = _make_runtime()
    runtime.tool_policy = ToolPolicy(
        dangerous_enabled=True,
        tool_risk_tiers={"shell_exec": ToolRiskTier.DANGEROUS.value},
    )
    session = _make_session()
    event = Event(
        type="command",
        session_id=session.session_id,
        kind="command",
        text="/shell --command 'rm -rf /tmp/test'",
        user_id="user-1",
        room_id="room-1",
        platform="cli",
    )

    outputs = await runtime._command_shell(event, session, "rm -rf /tmp/test")

    assert runtime.tool_runner.called is False
    assert len(session.pending_tool_approvals) == 1
    assert any(
        isinstance(item, StructuredOutput) and item.kind == "approval_request"
        for item in outputs
    )
    error_output = next(item for item in outputs if isinstance(item, ErrorOutput))
    assert "requires approval" in error_output.message.lower()
    runtime.memory_coordinator.record_action.assert_awaited_once()


def test_command_status_includes_pending_approvals_and_recent_actions() -> None:
    runtime = _make_runtime()
    runtime.tool_policy = ToolPolicy()
    session = _make_session()
    session.pending_tool_approvals["approval-1"] = {
        "approval_id": "approval-1",
        "tool_name": "shell_exec",
        "risk_tier": "dangerous",
    }
    session.recent_action_records.append(
        ActionRecord(
            action_id="action-1",
            action_type="tool_call",
            tool_name="shell_exec",
            inputs={},
            output="Pending operator approval",
            outcome="pending",
            persona_id="tai",
            session_id=session.session_id,
            timestamp=datetime.now(timezone.utc),
            approval_state="pending",
        )
    )
    event = Event(
        type="command",
        session_id=session.session_id,
        kind="command",
        text="/status",
        user_id="user-1",
        room_id="room-1",
        platform="cli",
    )

    outputs = runtime._command_status(event=event, session=session)
    payload = next(
        item.data for item in outputs
        if isinstance(item, StructuredOutput) and item.kind == "command_status"
    )

    assert payload["pending_approvals"]["count"] == 1
    assert payload["pending_approvals"]["items"][0]["tool_name"] == "shell_exec"
    assert payload["recent_actions"][0]["approval_state"] == "pending"
