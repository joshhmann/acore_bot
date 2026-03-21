"""WebSocket handlers for Web Adapter.

Provides real-time bidirectional communication for chat and runtime events.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from core.interfaces import PlatformFacts, build_runtime_event_from_facts
from core.schemas import Event, EventKind
from .auth import WebAuth, extract_request_client_scope, extract_request_user_id, resolve_request_actor_id

if TYPE_CHECKING:
    from core.runtime import GestaltRuntime

# FastAPI imports with fallback
try:
    from fastapi import WebSocket, WebSocketDisconnect

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    WebSocket = object  # type: ignore
    WebSocketDisconnect = Exception  # type: ignore

logger = logging.getLogger(__name__)


def _extract_bearer_token(raw: Optional[str]) -> str:
    """Extract bearer token from header value."""
    if not raw:
        return ""
    value = raw.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _is_text_output(output: Any) -> bool:
    """Check if output is a text output."""
    return hasattr(output, "text")


def _is_error_output(output: Any) -> bool:
    """Check if output is an error output."""
    return hasattr(output, "message") and not _is_text_output(output)


def _is_trace_output(output: Any) -> bool:
    """Check if output is a trace output."""
    return hasattr(output, "trace_type") and hasattr(output, "session_id")


def _lane_for_output(output: Any) -> Optional[str]:
    """Determine the lane (TAI/SYSTEM/ERROR) for an output."""
    if _is_text_output(output):
        persona_id = str(getattr(output, "persona_id", "") or "").upper()
        return "SYSTEM" if persona_id == "SYSTEM" else "TAI"
    if _is_error_output(output):
        return "ERROR"
    return None


def _text_for_output(output: Any) -> str:
    """Extract text from output object."""
    if _is_text_output(output):
        return str(getattr(output, "text", "") or "")
    if _is_error_output(output):
        return str(getattr(output, "message", "") or "Unknown runtime error")
    return ""


def _trace_payload(output: Any) -> Dict[str, Any]:
    """Serialize trace output to dict."""
    data = dict(getattr(output, "data", {}) or {})
    return {
        "trace_type": str(getattr(output, "trace_type", "") or "trace"),
        "session_id": str(getattr(output, "session_id", "") or ""),
        "span_id": str(getattr(output, "span_id", "") or ""),
        "parent_span_id": getattr(output, "parent_span_id", None),
        "start_ts": getattr(output, "start_ts", datetime.now(timezone.utc)).isoformat()
        if hasattr(getattr(output, "start_ts", None), "isoformat")
        else str(getattr(output, "start_ts", "")),
        "end_ts": getattr(output, "end_ts", datetime.now(timezone.utc)).isoformat()
        if hasattr(getattr(output, "end_ts", None), "isoformat")
        else str(getattr(output, "end_ts", "")),
        "data": data,
    }


def _progressive_text_frames(text: str, *, chunk_chars: int = 32) -> List[str]:
    """Break text into progressive frames for streaming display.

    Args:
        text: The full text to break into frames.
        chunk_chars: Number of characters per chunk.

    Returns:
        List of progressively longer text frames.
    """
    normalized = text.strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_chars:
        return [normalized]

    frames = [
        normalized[:index] for index in range(chunk_chars, len(normalized), chunk_chars)
    ]
    if not frames or frames[-1] != normalized:
        frames.append(normalized)
    return frames


class WebSocketManager:
    """Manager for WebSocket connections.

    Handles real-time bidirectional communication between clients and
    the Gestalt runtime.
    """

    def __init__(
        self,
        runtime: "GestaltRuntime",
        api_token: Optional[str] = None,
        event_callback: Optional[Callable[[Any], Any]] = None,
    ):
        """Initialize WebSocket manager.

        Args:
            runtime: The GestaltRuntime instance.
            api_token: Optional API token for authentication.
            event_callback: Optional callback for external event handling.
        """
        self.runtime = runtime
        self.api_token = api_token
        self.event_callback = event_callback
        self._connections: Dict[str, WebSocket] = {}

    def _authorize_token(self, token: str) -> bool:
        """Validate authentication token."""
        if not self.api_token:
            return True
        return bool(token) and token == self.api_token

    async def handle_runtime_websocket(self, websocket: WebSocket) -> None:
        """Handle runtime protocol WebSocket connection.

        This WebSocket uses a structured protocol for runtime communication,
        supporting streaming responses and trace events.

        Args:
            websocket: The FastAPI WebSocket connection.
        """
        await websocket.accept()
        session_context: Optional[Dict[str, Any]] = None

        try:
            # Expect initial connect message
            initial = await websocket.receive_json()
            if (
                not isinstance(initial, dict)
                or str(initial.get("type") or "") != "connect"
            ):
                await websocket.send_json(
                    {
                        "type": "request_error",
                        "session_id": "",
                        "message": "First websocket message must be connect",
                    }
                )
                await websocket.close()
                return

            # Validate auth token
            auth_token = _extract_bearer_token(str(initial.get("auth_token") or ""))
            if not auth_token and hasattr(websocket, "headers"):
                auth_token = _extract_bearer_token(
                    str(websocket.headers.get("authorization") or "")
                )
            if not self._authorize_token(auth_token):
                await websocket.send_json(
                    {
                        "type": "runtime_status",
                        "status": "unauthorized",
                        "detail": "runtime authorization failed",
                    }
                )
                await websocket.close(code=4401)
                return

            requested_platform = str(initial.get("platform") or "web")
            auth = WebAuth(self.api_token)
            client_scope = extract_request_client_scope(websocket)
            claimed_user_id = extract_request_user_id(websocket)
            actor_id = resolve_request_actor_id(
                websocket,
                auth=auth,
                client_scope=client_scope,
                platform=requested_platform,
            )

            flags = (
                dict(initial.get("flags"))
                if isinstance(initial.get("flags"), dict)
                else {}
            )
            if claimed_user_id and auth.is_enabled and claimed_user_id != actor_id:
                flags.setdefault("claimed_user_id", claimed_user_id)
            flags.setdefault("user_id", actor_id)

            # Set up session context
            default_persona_id = str(
                getattr(getattr(self.runtime, "router", None), "default_persona_id", "default")
                or "default"
            )
            session_context = {
                "session_id": str(initial.get("session_id") or "web:main"),
                "persona_id": str(initial.get("persona_id") or default_persona_id),
                "mode": str(initial.get("mode") or ""),
                "platform": requested_platform,
                "room_id": str(initial.get("room_id") or "web_room"),
                "user_id": actor_id,
                "flags": flags,
            }

            # Send connection confirmation
            await websocket.send_json(
                {
                    "type": "connected",
                    "session_id": session_context["session_id"],
                    "command": "web runtime",
                }
            )
            await websocket.send_json(
                {
                    "type": "runtime_status",
                    "status": "connected",
                    "detail": "live runtime connected",
                    "persona_id": session_context["persona_id"],
                }
            )

            # Main message loop
            while True:
                payload = await websocket.receive_json()
                if not isinstance(payload, dict):
                    continue

                message_type = str(payload.get("type") or "")
                if message_type == "send_event":
                    await self._handle_runtime_event(websocket, payload, session_context)
                    continue
                if message_type == "observation":
                    await self._handle_observation_event(
                        websocket, payload, session_context
                    )
                    continue
                await websocket.send_json(
                    {
                        "type": "request_error",
                        "session_id": session_context["session_id"],
                        "message": f"Unsupported websocket message type: {message_type or 'unknown'}",
                    }
                )

        except WebSocketDisconnect:
            logger.info("Runtime websocket disconnected: %s", session_context)
        except Exception as exc:
            logger.error("Runtime websocket error: %s", exc)
            try:
                await websocket.send_json(
                    {
                        "type": "request_error",
                        "session_id": (
                            str(session_context.get("session_id"))
                            if isinstance(session_context, dict)
                            else ""
                        ),
                        "message": str(exc),
                    }
                )
            except Exception:
                pass

    async def _handle_runtime_event(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
        session_context: Dict[str, Any],
    ) -> None:
        """Handle a single runtime event from websocket.

        Args:
            websocket: The WebSocket connection.
            payload: The received message payload.
            session_context: The current session context.
        """
        kind = str(payload.get("kind") or EventKind.CHAT.value).strip().lower()
        text = str(payload.get("text") or "")

        event_kind = (
            EventKind.COMMAND.value
            if kind == EventKind.COMMAND.value or text.strip().startswith("/")
            else EventKind.CHAT.value
        )
        event = build_runtime_event_from_facts(
            facts=PlatformFacts(
                text=text,
                user_id=str(session_context.get("user_id") or "web_live"),
                room_id=str(session_context["room_id"]),
                message_id=str(payload.get("message_id") or ""),
            ),
            platform_name=str(session_context["platform"]),
            kind=event_kind,
            session_id=str(session_context["session_id"]),
            persona_id=str(session_context["persona_id"]),
            mode=str(session_context["mode"]),
            extra_flags=dict(session_context["flags"]),
        )
        event.type = "command" if event_kind == EventKind.COMMAND.value else "message"

        try:
            # Try streaming if available
            if kind == EventKind.CHAT.value and hasattr(self.runtime, "stream_event"):
                async for item in self.runtime.stream_event(event):
                    await self._send_stream_item(
                        websocket, item, event, session_context
                    )
                await websocket.send_json(
                    {
                        "type": "request_complete",
                        "event_id": event.event_id,
                        "session_id": session_context["session_id"],
                    }
                )
                return

            # Fall back to non-streaming
            envelope = await self.runtime.handle_event_envelope(event)
            await self._send_envelope_outputs(websocket, envelope, session_context)

        except Exception as exc:
            await websocket.send_json(
                {
                    "type": "request_error",
                    "session_id": session_context["session_id"],
                    "message": str(exc),
                }
            )

    async def _handle_observation_event(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
        session_context: Dict[str, Any],
    ) -> None:
        """Handle observation event forwarded from web clients."""
        raw_observation = payload.get("data")
        observation_data = dict(raw_observation) if isinstance(raw_observation, dict) else {}
        observation_type = str(observation_data.get("type") or "unknown")

        event = Event(
            type="observation",
            kind=EventKind.SYSTEM.value,
            text="",
            user_id=str(session_context.get("user_id") or "web_live"),
            room_id=str(session_context["room_id"]),
            platform=str(session_context["platform"]),
            session_id=str(session_context["session_id"]),
            metadata={
                "persona_id": str(session_context["persona_id"]),
                "mode": str(session_context["mode"]),
                "flags": dict(session_context["flags"]),
                "observation": {
                    "type": observation_type,
                    "data": observation_data,
                    "timestamp": payload.get("timestamp"),
                },
            },
        )

        try:
            from core.social_intelligence import runtime_hooks as sil_runtime_hooks

            hooks = sil_runtime_hooks.SILRuntimeHooks.from_env()
            if hooks.should_observe():
                result = await hooks.observe_incoming_event(event, session_context)
                event.metadata["social_context"] = {
                    "signals_extracted": int(
                        getattr(result, "signals_extracted", 0) or 0
                    ),
                    "opportunities_detected": int(
                        getattr(result, "opportunities_detected", 0) or 0
                    ),
                    "latency_ms": float(getattr(result, "latency_ms", 0.0) or 0.0),
                }
        except Exception:
            # SIL hooks are best-effort and should not block websocket observation flow.
            pass

        await self.runtime.handle_event_envelope(event)
        await websocket.send_json(
            {
                "type": "runtime_status",
                "status": "observation_accepted",
                "detail": observation_type,
                "session_id": session_context["session_id"],
            }
        )

    async def _send_stream_item(
        self,
        websocket: WebSocket,
        item: Dict[str, Any],
        event: Event,
        session_context: Dict[str, Any],
    ) -> None:
        """Send a streaming item to the websocket.

        Args:
            websocket: The WebSocket connection.
            item: The stream item from runtime.
            event: The original event.
            session_context: The session context.
        """
        item_type = str(item.get("type") or "")

        if item_type == "text_delta":
            aggregate = str(item.get("aggregate_text") or "")
            await websocket.send_json(
                {
                    "type": "transcript_delta",
                    "lane": "TAI",
                    "text": aggregate,
                    "done": False,
                    "entry_id": f"{event.event_id}:stream",
                    "event_id": event.event_id,
                    "session_id": session_context["session_id"],
                }
            )
            await websocket.send_json(
                {
                    "type": "presence_update",
                    "session_id": session_context["session_id"],
                    "snapshot": self.runtime.get_presence_snapshot(**session_context),
                }
            )
        elif item_type == "trace":
            await websocket.send_json(
                {
                    "type": "trace_entry",
                    "session_id": session_context["session_id"],
                    "span": _trace_payload(item.get("trace")),
                }
            )
        elif item_type == "output":
            output = item.get("output")
            lane = _lane_for_output(output)
            if lane is not None:
                text = _text_for_output(output)
                if lane == "TAI":
                    frames = _progressive_text_frames(text)
                    for idx, frame in enumerate(frames):
                        await websocket.send_json(
                            {
                                "type": "transcript_delta",
                                "lane": lane,
                                "text": frame,
                                "done": idx == len(frames) - 1,
                                "entry_id": f"{event.event_id}:stream",
                                "event_id": event.event_id,
                                "session_id": session_context["session_id"],
                            }
                        )
                else:
                    await websocket.send_json(
                        {
                            "type": "transcript_entry",
                            "lane": lane,
                            "text": text,
                            "event_id": event.event_id,
                            "session_id": session_context["session_id"],
                            }
                        )
            elif hasattr(output, "kind"):
                structured_kind = str(getattr(output, "kind", "") or "")
                structured_data = dict(getattr(output, "data", {}) or {})
                if structured_kind in {"action_request", "expression_set"}:
                    await websocket.send_json(
                        {
                            "type": structured_kind,
                            **structured_data,
                            "event_id": event.event_id,
                            "session_id": session_context["session_id"],
                        }
                    )
            if _is_trace_output(output):
                await websocket.send_json(
                    {
                        "type": "trace_entry",
                        "session_id": session_context["session_id"],
                        "span": _trace_payload(output),
                    }
                )

    async def _send_envelope_outputs(
        self,
        websocket: WebSocket,
        envelope: Any,
        session_context: Dict[str, Any],
    ) -> None:
        """Send envelope outputs to websocket.

        Args:
            websocket: The WebSocket connection.
            envelope: The response envelope from runtime.
            session_context: The session context.
        """
        outputs = getattr(envelope, "outputs", [])
        event_id = getattr(envelope, "event_id", "")
        session_id = getattr(envelope, "session_id", session_context["session_id"])

        for output_idx, output in enumerate(outputs):
            lane = _lane_for_output(output)
            if lane is not None:
                text = _text_for_output(output)
                if lane == "TAI":
                    frames = _progressive_text_frames(text)
                    for idx, frame in enumerate(frames):
                        await websocket.send_json(
                            {
                                "type": "transcript_delta",
                                "lane": lane,
                                "text": frame,
                                "done": idx == len(frames) - 1,
                                "entry_id": f"{event_id}:{output_idx}",
                                "event_id": event_id,
                                "session_id": session_id,
                            }
                        )
                else:
                    await websocket.send_json(
                        {
                            "type": "transcript_entry",
                            "lane": lane,
                            "text": text,
                            "event_id": event_id,
                            "session_id": session_id,
                        }
                    )
            elif hasattr(output, "kind"):
                structured_kind = str(getattr(output, "kind", "") or "")
                structured_data = dict(getattr(output, "data", {}) or {})
                if structured_kind in {"action_request", "expression_set"}:
                    await websocket.send_json(
                        {
                            "type": structured_kind,
                            **structured_data,
                            "event_id": event_id,
                            "session_id": session_id,
                        }
                    )

            if _is_trace_output(output):
                await websocket.send_json(
                    {
                        "type": "trace_entry",
                        "session_id": session_id,
                        "span": _trace_payload(output),
                    }
                )

        await websocket.send_json(
            {
                "type": "presence_update",
                "session_id": session_id,
                "snapshot": self.runtime.get_presence_snapshot(**session_context),
            }
        )
        await websocket.send_json(
            {
                "type": "request_complete",
                "event_id": event_id,
                "session_id": session_id,
            }
        )

    async def handle_simple_websocket(self, websocket: WebSocket) -> None:
        """Handle simple chat WebSocket connection.

        This is a simpler protocol for basic chat interactions.

        Args:
            websocket: The FastAPI WebSocket connection.
        """
        await websocket.accept()
        client_id = f"ws_{id(websocket)}"
        logger.info(f"WebSocket client connected: {client_id}")

        try:
            while True:
                data = await websocket.receive_json()

                message_text = data.get("message", "")
                persona_id = data.get("persona_id", "dagoth_ur")
                user_id = data.get("user_id", client_id)

                if not message_text:
                    await websocket.send_json(
                        {"type": "error", "message": "No message provided"}
                    )
                    continue

                # Call external event callback if registered
                if self.event_callback:
                    from core.interfaces import AcoreEvent
                    from core.types import AcoreMessage

                    message = AcoreMessage(
                        text=message_text,
                        author_id=user_id,
                        channel_id=client_id,
                        timestamp=datetime.now(timezone.utc),
                    )
                    event = AcoreEvent(
                        type="message",
                        payload={
                            "message": message,
                            "persona_id": persona_id,
                            "websocket": websocket,
                        },
                        source_adapter="web",
                    )

                    result = self.event_callback(event)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)

                # Send to runtime
                runtime_response = await self.runtime.handle_event(
                    Event(
                        type="message",
                        text=message_text,
                        user_id=user_id,
                        room_id=client_id,
                        platform="web",
                        session_id=f"web:{client_id}",
                        metadata={"persona_id": persona_id},
                    )
                )

                await websocket.send_json(
                    {
                        "type": "response",
                        "text": runtime_response.text,
                        "persona_id": runtime_response.persona_id,
                    }
                )

                await websocket.send_json(
                    {
                        "type": "ack",
                        "message_id": id(data),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
