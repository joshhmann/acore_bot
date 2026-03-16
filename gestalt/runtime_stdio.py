from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any

from core.schemas import Event, EventKind
from gestalt.runtime_bootstrap import RuntimeHost, create_runtime, create_runtime_host


def _serialize_output(output: Any) -> dict[str, Any]:
    return {"type": output.__class__.__name__, **asdict(output)}


def _serialize_mutation(mutation: Any) -> dict[str, Any]:
    return asdict(mutation)


def _request_context(args: dict[str, Any]) -> dict[str, Any]:
    flags = args.get("flags")
    return {
        "session_id": str(args.get("session_id") or "stdio:default"),
        "persona_id": str(args.get("persona_id") or ""),
        "mode": str(args.get("mode") or ""),
        "platform": str(args.get("platform") or "stdio"),
        "room_id": str(args.get("room_id") or "stdio_room"),
        "flags": flags if isinstance(flags, dict) else {},
    }


def _serialize_envelope(envelope: Any) -> dict[str, Any]:
    return {
        "event_id": envelope.event_id,
        "session_id": envelope.session_id,
        "outputs": [_serialize_output(out) for out in envelope.outputs],
        "mutations": [_serialize_mutation(mutation) for mutation in envelope.mutations],
    }


async def _dispatch(runtime, payload: dict[str, Any]) -> dict[str, Any]:
    method = str(payload.get("method") or "")
    params = payload.get("params")
    args = params if isinstance(params, dict) else {}

    if method == "send_event":
        event = Event(
            type=str(args.get("type") or "message"),
            kind=str(args.get("kind") or EventKind.CHAT.value),
            text=str(args.get("text") or ""),
            user_id=str(args.get("user_id") or "stdio_user"),
            room_id=str(args.get("room_id") or "stdio_room"),
            platform=str(args.get("platform") or "stdio"),
            session_id=str(args.get("session_id") or "stdio:default"),
            metadata=(
                args.get("metadata") if isinstance(args.get("metadata"), dict) else {}
            ),
        )
        envelope = await runtime.handle_event_envelope(event)
        return _serialize_envelope(envelope)

    if method == "list_commands":
        return {"commands": runtime.list_commands()}

    context = _request_context(args)
    session_id = context["session_id"]
    persona_id = context["persona_id"]
    if method == "get_status":
        snapshot = runtime.get_status_snapshot(**context)
        return {"snapshot": snapshot}
    if method == "get_session":
        snapshot = runtime.get_session_snapshot(**context)
        return {"session": snapshot}
    if method == "list_sessions":
        limit = max(1, int(args.get("limit") or 20))
        return {
            "sessions": runtime.list_sessions_snapshot(
                limit=limit,
                platform=str(args.get("platform") or ""),
                room_id=str(args.get("room_id") or ""),
                user_scope=str(args.get("user_scope") or ""),
            )
        }
    if method == "get_tools":
        return {"tools": runtime.get_tools_snapshot(**context)}
    if method == "get_context":
        return {"snapshot": runtime.get_context_cache_snapshot(**context)}
    if method == "reset_context":
        return {"snapshot": runtime.reset_context_cache(**context)}
    if method == "get_trace":
        limit = max(1, int(args.get("limit") or 10))
        return {"trace": runtime.get_trace_snapshot(session_id=session_id, limit=limit)}
    if method == "get_presence":
        snapshot_fn = getattr(runtime, "get_presence_snapshot", None)
        if not callable(snapshot_fn):
            raise ValueError("Runtime does not support presence snapshots")
        return {"snapshot": snapshot_fn(**context)}
    if method == "get_providers":
        snapshot_fn = getattr(runtime, "get_providers_snapshot", None)
        if callable(snapshot_fn):
            providers = snapshot_fn(session_id=session_id)
        else:
            providers = runtime.list_provider_status(session_id=session_id)
        return {"providers": providers}
    if method == "get_social":
        return {"snapshot": runtime.get_social_state_snapshot(**context)}
    if method == "set_social_mode":
        social_mode = str(args.get("social_mode") or "auto")
        return {
            "snapshot": runtime.set_social_mode(
                **context,
                social_mode=social_mode,
            )
        }
    if method == "reset_social_state":
        return {"snapshot": runtime.reset_social_state(**context)}
    if method == "help":
        command = str(args.get("command") or "").strip()
        text = f"/help {command}" if command else "/help"
    elif method == "set_model":
        spec = str(args.get("spec") or "").strip()
        text = "/model reset" if spec.lower() == "reset" else f"/model {spec}"
    elif method == "set_persona":
        text = f"/persona {str(args.get('persona') or '').strip()}"
    elif method == "set_flag":
        flag = str(args.get("flag") or "").strip().lower()
        value = str(args.get("value") or "").strip().lower()
        if flag != "yolo":
            raise ValueError("Unsupported flag")
        text = f"/yolo {value}"
    elif method == "list_tools":
        text = "/tools"
    elif method == "auth_list":
        from core.auth import AuthStore

        store = AuthStore()
        return {"providers": store.list_provider_summaries()}
    else:
        raise ValueError("Unknown method")

    event = Event(
        type="command",
        kind=EventKind.COMMAND.value,
        text=text,
        user_id="stdio_user",
        room_id=context["room_id"],
        platform=context["platform"],
        session_id=session_id,
        metadata={
            "persona_id": persona_id,
            "mode": context["mode"],
            "flags": dict(context["flags"]),
        },
    )
    envelope = await runtime.handle_event_envelope(event)
    return _serialize_envelope(envelope)


async def run_stdio_server(
    runtime: Any | None = None,
    *,
    runtime_host: RuntimeHost | None = None,
) -> int:
    host = runtime_host
    active_runtime = runtime
    if host is None and active_runtime is None:
        host = create_runtime_host()
        active_runtime = host.runtime
    elif host is not None:
        active_runtime = host.runtime
    else:
        active_runtime = active_runtime or create_runtime()

    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            request_id: Any = None
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("request must be an object")
                request_id = payload.get("id")
                result = await _dispatch(active_runtime, payload)
                response = {"id": request_id, "ok": True, "result": result}
            except Exception as exc:
                response = {
                    "id": request_id,
                    "ok": False,
                    "error": {"code": "RUNTIME_STDIO_ERROR", "message": str(exc)},
                }
            sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
            sys.stdout.flush()
        return 0
    finally:
        if host is not None:
            await host.close()
