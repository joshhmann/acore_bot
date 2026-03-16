from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult:
    name: str
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EventKind(str, Enum):
    CHAT = "chat"
    COMMAND = "command"
    SYSTEM = "system"
    VOICE_TRANSCRIPTION = "voice_transcription"


class WebRuntimeMessageType(str, Enum):
    CONNECT = "connect"
    CONNECTED = "connected"
    RUNTIME_STATUS = "runtime_status"
    SEND_EVENT = "send_event"
    OBSERVATION = "observation"
    REQUEST_ERROR = "request_error"
    REQUEST_COMPLETE = "request_complete"
    PRESENCE_UPDATE = "presence_update"
    TRANSCRIPT_DELTA = "transcript_delta"
    TRANSCRIPT_ENTRY = "transcript_entry"
    TRACE_ENTRY = "trace_entry"
    ACTION_REQUEST = "action_request"
    EXPRESSION_SET = "expression_set"


class ObservationType(str, Enum):
    CAMERA_POSITION = "camera_position"
    EXPRESSION_STATE = "expression_state"
    CLICK = "click"
    FEEDBACK = "feedback"


@dataclass(slots=True)
class Event:
    type: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    kind: str = EventKind.CHAT.value
    text: str = ""
    user_id: str = ""
    room_id: str = ""
    platform: str = "unknown"
    message_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WebRuntimeObservation:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int | None = None


@dataclass(slots=True)
class Response:
    text: str
    persona_id: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TextOutput:
    text: str
    persona_id: str = ""


@dataclass(slots=True)
class StructuredOutput:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TraceOutput:
    trace_type: str
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    span_id: str = ""
    parent_span_id: str | None = None
    start_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class ErrorOutput:
    code: str
    message: str
    hint: str = ""


@dataclass(slots=True)
class StateMutation:
    path: str
    old: Any = None
    new: Any = None


@dataclass(slots=True)
class ResponseEnvelope:
    event_id: str
    session_id: str = ""
    outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = field(
        default_factory=list
    )
    mutations: list[StateMutation] = field(default_factory=list)


@dataclass(slots=True)
class VoiceTranscriptionEvent:
    """Event type for transcribed voice input.

    This event is created by voice adapters when STT produces transcription,
    and is sent to the runtime for processing.
    """

    transcription: str
    session_id: str
    user_id: str = ""
    platform: str = ""
    room_id: str = ""
    language: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class VoiceOutputIntent:
    """Runtime's request for voice/TTS output.

    The runtime returns this in response outputs to indicate that
    the adapter should speak the provided text using TTS.
    """

    text: str
    tts_voice: str = ""
    tts_speed: float = 1.0
    rvc_enabled: bool = False
    rvc_model: str = ""
    rvc_pitch_shift: int = 0
    rvc_index_rate: float = 0.75
    rvc_protect: float = 0.33
    priority: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
