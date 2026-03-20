from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adapters.web import adapter as web_adapter
from adapters.web.auth import reset_auth
from core.social_intelligence import runtime_hooks as sil_runtime_hooks


pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _TextOutput:
    text: str
    persona_id: str = ""


@dataclass(slots=True)
class _Mutation:
    path: str
    old: Any = None
    new: Any = None


@dataclass(slots=True)
class _TraceOutput:
    trace_type: str
    session_id: str
    span_id: str = "span-1"
    parent_span_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    start_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class _StructuredOutput:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _Envelope:
    event_id: str
    session_id: str
    outputs: list[Any] = field(default_factory=list)
    mutations: list[Any] = field(default_factory=list)


class _FakeRuntime:
    def __init__(self) -> None:
        self.received_events: list[Any] = []
        self.router = type("Router", (), {"default_persona_id": "alpha"})()

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
            "model": "fake-model",
            "provider_usage": {
                "input_tokens": 42,
                "output_tokens": 9,
                "cached_input_tokens": 12,
            },
        }

    def get_session_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "session_id": kwargs["session_id"],
            "persona_id": kwargs["persona_id"] or "alpha",
            "mode": kwargs.get("mode", ""),
            "platform": kwargs["platform"],
            "room_id": kwargs["room_id"],
            "flags": dict(kwargs.get("flags", {})),
            "yolo": False,
            "provider": "fake",
            "model": "fake-model",
            "social": self.get_social_state_snapshot(**kwargs),
            "last_response_at": None,
            "last_persona_text": "",
            "autopilot_active": False,
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
                "session_id": "web:main",
                "persona_id": "alpha",
                "mode": "tai",
                "platform": "web",
                "room_id": "web_room",
                "flags": {"user_scope": "browser-user"},
                "yolo": False,
                "provider": "fake",
                "model": "fake-model",
                "social": self.get_social_state_snapshot(
                    session_id="web:main",
                    persona_id="alpha",
                    room_id="web_room",
                    platform="web",
                    mode="tai",
                    flags={},
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
        return [{"name": "shell", "risk_tier": "high", "enabled": True}]

    def get_context_cache_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "session_id": kwargs["session_id"],
            "cache_model": "stable_prefix",
            "entry_count": 1,
            "total_hits": 3,
            "tokens_saved_estimate": 72,
            "provider_cached_input_tokens": 12,
            "last_cache_key": "web:main:alpha:fake:fake-model",
            "last_cache_hit": True,
            "last_cache_reason": "stable_prefix_reused",
            "memory_revision": "rev-1",
            "entries": [
                {
                    "cache_key": "web:main:alpha:tai",
                    "persona_id": kwargs.get("persona_id") or "alpha",
                    "mode": kwargs.get("mode") or "default",
                    "context_tokens_estimate": 24,
                    "hit_count": 3,
                    "created_at": "2026-03-15T00:00:00+00:00",
                    "last_used_at": "2026-03-15T00:10:00+00:00",
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

    async def handle_event(self, event: Any):
        return type(
            "Response",
            (),
            {
                "text": f"echo:{event.text}",
                "persona_id": event.metadata.get("persona_id", "alpha"),
                "metadata": {},
            },
        )()

    async def handle_event_envelope(self, event: Any) -> _Envelope:
        self.received_events.append(event)
        persona_id = "system" if str(event.kind) == "command" else "alpha"
        return _Envelope(
            event_id="evt-1",
            session_id=event.session_id,
            outputs=[
                _TextOutput(text=f"echo:{event.text}", persona_id=persona_id),
                _TraceOutput(
                    trace_type="decision",
                    session_id=event.session_id,
                    data={"kind": event.kind},
                ),
            ],
            mutations=[_Mutation(path="session.mode", old="", new="tai_core")],
        )

    async def stream_event(self, event: Any):
        if str(event.kind) != "chat":
            envelope = await self.handle_event_envelope(event)
            for output in envelope.outputs:
                yield {
                    "type": "output",
                    "output": output,
                    "event_id": envelope.event_id,
                }
            return
        yield {
            "type": "text_delta",
            "text": "echo:",
            "aggregate_text": "echo:",
            "persona_id": "alpha",
        }
        yield {
            "type": "trace",
            "trace": _TraceOutput(
                trace_type="provider",
                session_id=event.session_id,
                data={"provider": "fake", "duration_ms": 12},
            ),
        }
        yield {
            "type": "output",
            "output": _TextOutput(text="echo:hello from web", persona_id="alpha"),
            "event_id": "evt-1",
        }


def _build_client(
    monkeypatch: pytest.MonkeyPatch, *, api_token: str | None = None
) -> TestClient:
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: _FakeRuntime()
    )
    if api_token is None:
        monkeypatch.delenv("GESTALT_API_TOKEN", raising=False)
        monkeypatch.delenv("ACORE_WEB_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GESTALT_API_TOKEN", api_token)
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    return TestClient(adapter._app)


def test_runtime_commands_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    response = client.get("/api/runtime/commands")
    assert response.status_code == 200
    assert response.json()["commands"][0]["usage"] == "/status"


def test_runtime_endpoints_require_auth_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch, api_token="secret-token")
    unauthorized = client.get("/api/runtime/commands")
    authorized = client.get(
        "/api/runtime/commands",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_runtime_snapshot_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    payload = {
        "session_id": "web:main",
        "persona_id": "tai",
        "room_id": "web_room",
        "platform": "web",
        "mode": "",
        "flags": {},
    }

    status = client.post("/api/runtime/status", json=payload)
    session = client.post("/api/runtime/session", json=payload)
    sessions = client.post(
        "/api/runtime/sessions",
        json={"limit": 5, "platform": "web", "user_scope": "browser-user"},
    )
    tools = client.post("/api/runtime/tools", json=payload)
    context = client.post("/api/runtime/context", json=payload)
    context_reset = client.post("/api/runtime/context/reset", json=payload)
    trace = client.post(
        "/api/runtime/trace", json={"session_id": "web:main", "limit": 3}
    )
    presence = client.post("/api/runtime/presence", json=payload)
    social = client.post("/api/runtime/social", json=payload)
    social_mode = client.post(
        "/api/runtime/social/mode",
        json={**payload, "social_mode": "logic"},
    )
    social_reset = client.post("/api/runtime/social/reset", json=payload)
    providers = client.post("/api/runtime/providers", json=payload)

    assert status.status_code == 200
    assert status.json()["snapshot"]["persona"] == "tai"
    assert status.json()["snapshot"]["provider_usage"]["cached_input_tokens"] == 12
    assert session.json()["session"]["platform"] == "web"
    assert sessions.json()["sessions"][0]["session_id"] == "web:main"
    assert tools.json()["tools"][0]["name"] == "shell"
    assert context.json()["snapshot"]["entry_count"] == 1
    assert context.json()["snapshot"]["cache_model"] == "stable_prefix"
    assert context.json()["snapshot"]["last_cache_reason"] == "stable_prefix_reused"
    assert context_reset.json()["snapshot"]["cleared"] == 1
    assert trace.json()["trace"]["spans"][0]["limit"] == 3
    assert presence.json()["snapshot"]["avatar_format"] == "vrm"
    assert social.json()["snapshot"]["effective_mode"] == "default"
    assert social_mode.json()["snapshot"]["override"] == "logic"
    assert social_reset.json()["snapshot"]["override"] == "auto"
    assert providers.json()["providers"][0]["provider"] == "fake"


def test_runtime_sessions_endpoint_scopes_by_platform_and_user_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch)
    response = client.post(
        "/api/runtime/sessions",
        json={"limit": 5, "platform": "web", "user_scope": "someone-else"},
    )

    assert response.status_code == 200
    assert response.json()["sessions"] == []


def test_runtime_sessions_endpoint_uses_client_scope_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/runtime/sessions",
        json={"limit": 5, "platform": "web"},
        headers={"x-gestalt-client-id": "browser-user"},
    )

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["flags"]["user_scope"] == "browser-user"


def test_runtime_event_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    response = client.post(
        "/api/runtime/event",
        json={
            "session_id": "web:main",
            "persona_id": "tai",
            "room_id": "web_room",
            "platform": "web",
            "mode": "",
            "flags": {},
            "text": "/status",
            "kind": "command",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "web:main"
    assert payload["outputs"][0]["text"] == "echo:/status"
    assert payload["mutations"][0]["path"] == "session.mode"


def test_runtime_event_endpoint_uses_runtime_default_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    response = client.post(
        "/api/runtime/event",
        json={
            "session_id": "web:main",
            "room_id": "web_room",
            "platform": "web",
            "mode": "",
            "flags": {},
            "text": "hello",
            "kind": "chat",
        },
    )

    assert response.status_code == 200
    assert runtime.received_events
    assert runtime.received_events[-1].metadata["persona_id"] == "alpha"


def test_runtime_event_endpoint_uses_user_id_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    response = client.post(
        "/api/runtime/event",
        json={
            "session_id": "web:main",
            "room_id": "web_room",
            "platform": "web",
            "mode": "",
            "flags": {},
            "text": "hello",
            "kind": "chat",
        },
        headers={"x-gestalt-user-id": "browser-user"},
    )

    assert response.status_code == 200
    assert runtime.received_events
    assert runtime.received_events[-1].user_id == "browser-user"
    assert runtime.received_events[-1].metadata["flags"]["user_id"] == "browser-user"
    assert runtime.received_events[-1].metadata["flags"]["is_direct_mention"] is False
    assert runtime.received_events[-1].metadata["flags"]["author_is_bot"] is False


def test_runtime_event_endpoint_uses_authenticated_actor_id_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    monkeypatch.setenv("GESTALT_API_TOKEN", "secret-token")
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    response = client.post(
        "/api/runtime/event",
        json={
            "session_id": "web:main",
            "room_id": "web_room",
            "platform": "web",
            "mode": "",
            "flags": {},
            "text": "hello",
            "kind": "chat",
        },
        headers={
            "Authorization": "Bearer secret-token",
            "x-gestalt-client-id": "browser-scope",
            "x-gestalt-user-id": "browser-user",
        },
    )

    assert response.status_code == 200
    assert runtime.received_events
    assert runtime.received_events[-1].user_id == "authenticated:web:browser-scope"
    assert runtime.received_events[-1].metadata["flags"]["claimed_user_id"] == "browser-user"
    assert (
        runtime.received_events[-1].metadata["flags"]["user_id"]
        == "authenticated:web:browser-scope"
    )


def test_runtime_event_endpoint_uses_authenticated_actor_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    monkeypatch.setenv("GESTALT_API_TOKEN", "secret-token")
    reset_auth()
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    response = client.post(
        "/api/runtime/event",
        json={
            "session_id": "web:main",
            "room_id": "web_room",
            "platform": "web",
            "mode": "",
            "flags": {},
            "text": "hello",
            "kind": "chat",
        },
        headers={
            "authorization": "Bearer secret-token",
            "x-gestalt-client-id": "browser-scope",
            "x-gestalt-user-id": "spoofed-user",
        },
    )

    assert response.status_code == 200
    assert runtime.received_events
    assert runtime.received_events[-1].user_id == "authenticated:web:browser-scope"
    assert (
        runtime.received_events[-1].metadata["flags"]["claimed_user_id"]
        == "spoofed-user"
    )


def test_runtime_websocket_streams_transcript_trace_and_presence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch)
    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        connected = websocket.receive_json()
        status = websocket.receive_json()

        websocket.send_json(
            {"type": "send_event", "text": "/status", "kind": "command"}
        )
        transcript = websocket.receive_json()
        trace = websocket.receive_json()
        presence = websocket.receive_json()
        complete = websocket.receive_json()

    assert connected["type"] == "connected"
    assert status["type"] == "runtime_status"
    assert transcript["type"] == "transcript_entry"
    assert transcript["lane"] == "SYSTEM"
    assert transcript["text"] == "echo:/status"
    assert trace["type"] == "trace_entry"
    assert trace["span"]["trace_type"] == "decision"
    assert presence["type"] == "presence_update"
    assert presence["snapshot"]["persona"] == "tai"
    assert complete["type"] == "request_complete"


def test_runtime_websocket_uses_user_id_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect(
        "/api/runtime/ws",
        headers={"x-gestalt-user-id": "browser-user"},
    ) as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"type": "send_event", "text": "/status", "kind": "command"})
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()

    assert runtime.received_events
    assert runtime.received_events[-1].user_id == "browser-user"
    assert runtime.received_events[-1].metadata["flags"]["user_id"] == "browser-user"
    assert runtime.received_events[-1].metadata["flags"]["is_direct_mention"] is False
    assert runtime.received_events[-1].metadata["flags"]["author_is_bot"] is False


def test_runtime_websocket_uses_authenticated_actor_id_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    monkeypatch.setenv("GESTALT_API_TOKEN", "secret-token")
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect(
        "/api/runtime/ws",
        headers={
            "Authorization": "Bearer secret-token",
            "x-gestalt-client-id": "browser-scope",
            "x-gestalt-user-id": "browser-user",
        },
    ) as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "auth_token": "secret-token",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"type": "send_event", "text": "/status", "kind": "command"})
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()

    assert runtime.received_events
    assert runtime.received_events[-1].user_id == "authenticated:web:browser-scope"
    assert (
        runtime.received_events[-1].metadata["flags"]["user_id"]
        == "authenticated:web:browser-scope"
    )


def test_root_ui_includes_runtime_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _build_client(monkeypatch)
    response = client.get("/")

    assert response.status_code == 200
    assert "Cache Model" in response.text
    assert "Saved Tokens" in response.text
    assert "refreshRuntimePanel" in response.text


def test_runtime_websocket_uses_authenticated_actor_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    monkeypatch.setenv("GESTALT_API_TOKEN", "secret-token")
    reset_auth()
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect(
        "/api/runtime/ws",
        headers={
            "x-gestalt-user-id": "spoofed-user",
            "x-gestalt-client-id": "browser-scope",
        },
    ) as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
                "auth_token": "secret-token",
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"type": "send_event", "text": "/status", "kind": "command"})
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()

    assert runtime.received_events
    assert runtime.received_events[-1].user_id == "authenticated:web:browser-scope"
    assert (
        runtime.received_events[-1].metadata["flags"]["claimed_user_id"]
        == "spoofed-user"
    )


def test_runtime_websocket_connect_uses_runtime_default_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        status = websocket.receive_json()

    assert status["type"] == "runtime_status"
    assert status["persona_id"] == "alpha"


def test_runtime_websocket_rejects_missing_auth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch, api_token="secret-token")
    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "runtime_status"
    assert message["status"] == "unauthorized"


def test_runtime_websocket_streams_tai_transcript_deltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch)
    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(
            {"type": "send_event", "text": "hello from web", "kind": "chat"}
        )
        delta = websocket.receive_json()
        presence = websocket.receive_json()
        trace = websocket.receive_json()
        final_delta = websocket.receive_json()
        complete = websocket.receive_json()

    assert delta["type"] == "transcript_delta"
    assert delta["lane"] == "TAI"
    assert delta["text"] == "echo:"
    assert delta["done"] is False
    assert presence["type"] == "presence_update"
    assert trace["type"] == "trace_entry"
    assert final_delta["type"] == "transcript_delta"
    assert final_delta["lane"] == "TAI"
    assert final_delta["text"] == "echo:hello from web"
    assert final_delta["done"] is True
    assert complete["type"] == "request_complete"


def test_runtime_websocket_forwards_vrm_structured_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _VRMRuntime(_FakeRuntime):
        async def handle_event_envelope(self, event: Any) -> _Envelope:
            return _Envelope(
                event_id="evt-vrm",
                session_id=event.session_id,
                outputs=[
                    _TextOutput(text="ok", persona_id="tai"),
                    _StructuredOutput(
                        kind="action_request",
                        data={"action": "wave", "params": {"intensity": 0.8}},
                    ),
                    _StructuredOutput(
                        kind="expression_set",
                        data={"expression": "happy", "weight": 0.7},
                    ),
                ],
                mutations=[],
            )

    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: _VRMRuntime()
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {"type": "send_event", "text": "/status", "kind": "command"}
        )

        transcript = websocket.receive_json()
        action_request = websocket.receive_json()
        expression_set = websocket.receive_json()
        presence = websocket.receive_json()
        complete = websocket.receive_json()

    assert transcript["type"] == "transcript_delta"
    assert transcript["lane"] == "TAI"
    assert transcript["done"] is True
    assert action_request["type"] == "action_request"
    assert action_request["action"] == "wave"
    assert action_request["params"]["intensity"] == 0.8
    assert expression_set["type"] == "expression_set"
    assert expression_set["expression"] == "happy"
    assert expression_set["weight"] == 0.7
    assert presence["type"] == "presence_update"
    assert complete["type"] == "request_complete"


def test_runtime_websocket_accepts_observation_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "observation",
                "timestamp": 1741574400000,
                "data": {
                    "type": "expression_state",
                    "expression": "happy",
                    "action": "wave",
                },
            }
        )
        accepted = websocket.receive_json()

    assert accepted["type"] == "runtime_status"
    assert accepted["status"] == "observation_accepted"
    assert accepted["detail"] == "expression_state"
    assert runtime.received_events
    observation_event = runtime.received_events[-1]
    assert observation_event.type == "observation"
    assert observation_event.kind == "system"
    observation = observation_event.metadata["observation"]
    assert observation["type"] == "expression_state"
    assert observation["data"]["expression"] == "happy"


def test_runtime_websocket_observation_enriches_with_sil_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSILResult:
        signals_extracted = 2
        opportunities_detected = 1
        latency_ms = 1.25

    class _FakeHooks:
        @classmethod
        def from_env(cls) -> "_FakeHooks":
            return cls()

        def should_observe(self) -> bool:
            return True

        async def observe_incoming_event(
            self, event: Any, session: Any
        ) -> _FakeSILResult:
            return _FakeSILResult()

    runtime = _FakeRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    monkeypatch.setattr(sil_runtime_hooks, "SILRuntimeHooks", _FakeHooks)

    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:main",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "observation",
                "timestamp": 1741574400001,
                "data": {
                    "type": "camera_position",
                    "position": {"x": 1, "y": 2, "z": 3},
                },
            }
        )
        accepted = websocket.receive_json()

    assert accepted["type"] == "runtime_status"
    assert accepted["status"] == "observation_accepted"
    event = runtime.received_events[-1]
    assert event.metadata["social_context"]["signals_extracted"] == 2
    assert event.metadata["social_context"]["opportunities_detected"] == 1


def test_runtime_websocket_end_to_end_observation_action_feedback_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _LoopRuntime(_FakeRuntime):
        async def handle_event_envelope(self, event: Any) -> _Envelope:
            self.received_events.append(event)
            if str(event.type) == "observation":
                return _Envelope(
                    event_id="evt-observation",
                    session_id=event.session_id,
                    outputs=[],
                    mutations=[],
                )
            return _Envelope(
                event_id="evt-loop",
                session_id=event.session_id,
                outputs=[
                    _TextOutput(text="hello from loop", persona_id="tai"),
                    _StructuredOutput(
                        kind="action_request",
                        data={"action": "wave", "params": {"intensity": 0.5}},
                    ),
                    _StructuredOutput(
                        kind="expression_set",
                        data={"expression": "happy", "weight": 0.6},
                    ),
                ],
                mutations=[],
            )

    runtime = _LoopRuntime()
    monkeypatch.setattr(
        web_adapter, "create_runtime", lambda: runtime
    )
    adapter = web_adapter.WebInputAdapter()
    assert adapter._app is not None
    client = TestClient(adapter._app)

    with client.websocket_connect("/api/runtime/ws") as websocket:
        websocket.send_json(
            {
                "type": "connect",
                "session_id": "web:loop",
                "persona_id": "tai",
                "room_id": "web_room",
                "platform": "web",
                "mode": "",
                "flags": {},
            }
        )
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(
            {
                "type": "observation",
                "timestamp": 1741574401000,
                "data": {"type": "expression_state", "expression": "neutral"},
            }
        )
        observation_ack = websocket.receive_json()

        websocket.send_json(
            {"type": "send_event", "text": "/status", "kind": "command"}
        )
        transcript = websocket.receive_json()
        action_request = websocket.receive_json()
        expression_set = websocket.receive_json()
        presence = websocket.receive_json()
        complete = websocket.receive_json()

        websocket.send_json(
            {
                "type": "observation",
                "timestamp": 1741574401001,
                "data": {
                    "type": "feedback",
                    "score": 0.8,
                    "response_text": "great action",
                },
            }
        )
        feedback_ack = websocket.receive_json()

        websocket.send_json({"type": "unknown_message"})
        unsupported = websocket.receive_json()

    assert observation_ack["type"] == "runtime_status"
    assert observation_ack["status"] == "observation_accepted"
    assert transcript["type"] == "transcript_delta"
    assert action_request["type"] == "action_request"
    assert expression_set["type"] == "expression_set"
    assert presence["type"] == "presence_update"
    assert complete["type"] == "request_complete"
    assert feedback_ack["type"] == "runtime_status"
    assert feedback_ack["status"] == "observation_accepted"
    assert unsupported["type"] == "request_error"

    observation_events = [
        event for event in runtime.received_events if event.type == "observation"
    ]
    assert len(observation_events) == 2
    assert observation_events[-1].metadata["observation"]["type"] == "feedback"
