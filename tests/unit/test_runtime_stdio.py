from __future__ import annotations

from typing import Any

import pytest

from gestalt.runtime_stdio import _dispatch, run_stdio_server


pytestmark = pytest.mark.unit


class _FakeRuntime:
    def __init__(self) -> None:
        self.closed = False

    def list_commands(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "status",
                "usage": "/status",
                "description": "Show current system state",
                "aliases": [],
            }
        ]

    def get_status_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "persona": kwargs["persona_id"],
            "session_id": kwargs["session_id"],
            "provider": "fake",
        }

    def get_session_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "session_id": kwargs["session_id"],
            "persona_id": kwargs["persona_id"] or "default",
            "mode": kwargs.get("mode", ""),
            "platform": kwargs.get("platform", "stdio"),
            "room_id": kwargs.get("room_id", "stdio_room"),
            "flags": dict(kwargs.get("flags", {})),
            "yolo": False,
            "provider": "fake",
            "model": "fake-model",
            "social": self.get_social_state_snapshot(**kwargs),
        }

    def list_sessions_snapshot(
        self,
        *,
        limit: int = 20,
        platform: str = "",
        room_id: str = "",
        user_scope: str = "",
    ) -> list[dict[str, Any]]:
        sessions = [
            {
                "session_id": "desktop:main",
                "persona_id": "tai",
                "mode": "tai",
                "platform": "desktop",
                "room_id": "desktop_room",
                "flags": {"user_scope": "desktop-user"},
                "yolo": False,
                "provider": "fake",
                "model": "fake-model",
                "social": self.get_social_state_snapshot(
                    session_id="desktop:main",
                    persona_id="tai",
                ),
            }
        ]
        if platform:
            sessions = [session for session in sessions if session["platform"] == platform]
        if room_id:
            sessions = [session for session in sessions if session["room_id"] == room_id]
        if user_scope:
            sessions = [
                session
                for session in sessions
                if session["flags"].get("user_scope") == user_scope
            ]
        return sessions[:limit]

    def get_tools_snapshot(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [
            {"name": "shell", "risk_tier": "high", "enabled": True, "source": "builtin"}
        ]

    def get_context_cache_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "session_id": kwargs["session_id"],
            "entry_count": 1,
            "total_hits": 2,
            "tokens_saved_estimate": 48,
            "entries": [
                {
                    "cache_key": "stdio:default:tai:default",
                    "persona_id": kwargs.get("persona_id") or "default",
                    "mode": kwargs.get("mode") or "default",
                    "context_tokens_estimate": 24,
                    "hit_count": 2,
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "last_used_at": "2026-03-15T00:05:00+00:00",
                }
            ],
        }

    def reset_context_cache(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "session_id": kwargs["session_id"],
            "cleared": 1,
            "remaining_global_entries": 0,
        }

    def get_trace_snapshot(self, *, session_id: str, limit: int = 10) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "count": 1,
            "spans": [{"trace_type": "decision", "limit": limit}],
        }

    def get_presence_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "session_id": kwargs["session_id"],
            "persona": kwargs["persona_id"],
            "mode": kwargs.get("mode", ""),
            "state": "idle",
            "emotion": "neutral",
            "expression": "neutral",
            "avatar_format": "vrm",
            "avatar_driver": "browser_vrm",
            "avatar_scene": "upper_body",
            "asset_status": "fallback_placeholder",
            "intensity": 0.36,
            "generating": False,
            "talking": False,
            "tool_running": False,
            "yolo": False,
            "error": False,
            "signal_active": False,
            "speech_text": "",
            "hold_ms": 900,
            "debounce_ms": 200,
        }

    def get_providers_snapshot(self, *, session_id: str = "") -> list[dict[str, Any]]:
        return [
            {
                "provider": "fake",
                "configured": True,
                "active": True,
                "model": "fake-model",
                "auth_present": False,
                "session_id": session_id,
            }
        ]

    def get_social_state_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "override": "auto",
            "current_mode": kwargs.get("mode") or "default",
            "effective_mode": kwargs.get("mode") or "default",
            "last_source": "",
            "last_confidence": 0.0,
            "mode_switches": {},
            "metadata": {},
        }

    def set_social_mode(self, **kwargs: Any) -> dict[str, Any]:
        snapshot = self.get_social_state_snapshot(**kwargs)
        snapshot["override"] = kwargs["social_mode"]
        snapshot["effective_mode"] = kwargs["social_mode"]
        return snapshot

    def reset_social_state(self, **kwargs: Any) -> dict[str, Any]:
        return self.get_social_state_snapshot(**kwargs)

    async def handle_event_envelope(self, event: Any):
        class _Envelope:
            event_id = "evt-1"
            session_id = event.session_id
            outputs = []
            mutations = []

        return _Envelope()

    async def close(self) -> None:
        self.closed = True


class _FakeRuntimeHost:
    def __init__(self) -> None:
        self.runtime = _FakeRuntime()
        self.closed = False

    async def close(self) -> None:
        self.closed = True
        await self.runtime.close()


@pytest.mark.asyncio
async def test_runtime_stdio_lists_commands() -> None:
    result = await _dispatch(_FakeRuntime(), {"method": "list_commands"})
    assert result["commands"][0]["usage"] == "/status"


@pytest.mark.asyncio
async def test_runtime_stdio_status_snapshot() -> None:
    result = await _dispatch(
        _FakeRuntime(),
        {
            "method": "get_status",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )
    assert result["snapshot"]["persona"] == "tai"
    assert result["snapshot"]["session_id"] == "desktop:main"


@pytest.mark.asyncio
async def test_runtime_stdio_tools_trace_and_providers() -> None:
    runtime = _FakeRuntime()

    tools = await _dispatch(runtime, {"method": "get_tools"})
    trace = await _dispatch(runtime, {"method": "get_trace", "params": {"limit": 3}})
    presence = await _dispatch(
        runtime,
        {
            "method": "get_presence",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )
    providers = await _dispatch(
        runtime,
        {"method": "get_providers", "params": {"session_id": "desktop:main"}},
    )

    assert tools["tools"][0]["name"] == "shell"
    assert trace["trace"]["spans"][0]["limit"] == 3
    assert presence["snapshot"]["avatar_format"] == "vrm"
    assert providers["providers"][0]["provider"] == "fake"


@pytest.mark.asyncio
async def test_runtime_stdio_sessions_and_social() -> None:
    runtime = _FakeRuntime()

    session = await _dispatch(
        runtime,
        {
            "method": "get_session",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )
    sessions = await _dispatch(
        runtime,
        {
            "method": "list_sessions",
            "params": {"limit": 5, "platform": "desktop", "user_scope": "desktop-user"},
        },
    )
    social = await _dispatch(
        runtime,
        {
            "method": "get_social",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )
    updated = await _dispatch(
        runtime,
        {
            "method": "set_social_mode",
            "params": {
                "session_id": "desktop:main",
                "persona_id": "tai",
                "social_mode": "logic",
            },
        },
    )
    reset = await _dispatch(
        runtime,
        {
            "method": "reset_social_state",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )

    assert session["session"]["session_id"] == "desktop:main"
    assert sessions["sessions"][0]["platform"] == "desktop"
    assert social["snapshot"]["override"] == "auto"
    assert updated["snapshot"]["override"] == "logic"
    assert reset["snapshot"]["override"] == "auto"


@pytest.mark.asyncio
async def test_runtime_stdio_context_snapshot_and_reset() -> None:
    runtime = _FakeRuntime()

    snapshot = await _dispatch(
        runtime,
        {
            "method": "get_context",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )
    reset = await _dispatch(
        runtime,
        {
            "method": "reset_context",
            "params": {"session_id": "desktop:main", "persona_id": "tai"},
        },
    )

    assert snapshot["snapshot"]["entry_count"] == 1
    assert snapshot["snapshot"]["tokens_saved_estimate"] == 48
    assert reset["snapshot"]["cleared"] == 1


@pytest.mark.asyncio
async def test_runtime_stdio_list_sessions_scopes_by_platform() -> None:
    runtime = _FakeRuntime()

    sessions = await _dispatch(
        runtime,
        {
            "method": "list_sessions",
            "params": {"limit": 5, "platform": "desktop", "user_scope": "someone-else"},
        },
    )

    assert sessions["sessions"] == []


@pytest.mark.asyncio
async def test_runtime_stdio_server_accepts_injected_runtime_host(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = _FakeRuntimeHost()
    monkeypatch.setattr("sys.stdin", iter([]))

    result = await run_stdio_server(runtime_host=host)

    assert result == 0
    assert host.closed is True
    assert host.runtime.closed is True
    assert capsys.readouterr().out == ""
