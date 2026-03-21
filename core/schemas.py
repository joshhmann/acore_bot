from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any
import uuid


class TraceSeverity(str, Enum):
    """Severity levels for trace entries."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class TraceStatus(str, Enum):
    """Status of a trace span."""

    OK = "ok"
    ERROR = "error"
    PENDING = "pending"


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
class TraceSpan:
    """A single trace span for detailed operator introspection.

    Represents one unit of work in the trace hierarchy with timing,
    status, and attributes for debugging and monitoring.
    """

    span_id: str
    trace_type: str
    session_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    name: str = ""
    start_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_ts: datetime | None = None
    duration_ms: float | None = None
    parent_span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: TraceStatus = TraceStatus.OK
    error_message: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Calculate duration if end_ts is set."""
        if self.end_ts is not None and self.duration_ms is None:
            self.duration_ms = (self.end_ts - self.start_ts).total_seconds() * 1000
        if not self.attributes and self.data:
            self.attributes = dict(self.data)
        if not self.data and self.attributes:
            self.data = dict(self.attributes)
        if self.error and not self.error_message:
            self.error_message = self.error
        if self.error_message and not self.error:
            self.error = self.error_message

    @property
    def has_error(self) -> bool:
        """Check if this span represents an error condition."""
        return bool(self.error or self.error_message)

    def to_output(self) -> TraceOutput:
        """Convert TraceSpan to TraceOutput."""
        return TraceOutput(
            trace_type=self.trace_type.value if isinstance(self.trace_type, Enum) else self.trace_type,
            data=dict(self.data),
            session_id=self.session_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            start_ts=self.start_ts,
            end_ts=self.end_ts or datetime.now(timezone.utc),
            status=self.status,
            error_message=self.error_message or self.error,
            name=self.name,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize span to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_type": self.trace_type.value if isinstance(self.trace_type, Enum) else self.trace_type,
            "session_id": self.session_id,
            "start_ts": self.start_ts.isoformat(),
            "end_ts": self.end_ts.isoformat() if self.end_ts else None,
            "duration_ms": self.duration_ms,
            "parent_span_id": self.parent_span_id,
            "data": dict(self.data),
            "error": self.error,
            "error_message": self.error_message,
            "has_error": self.has_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceSpan:
        """Deserialize span from dictionary."""
        return cls(
            span_id=data.get("span_id", str(uuid.uuid4())),
            trace_type=str(data.get("trace_type", "")),
            session_id=str(data.get("session_id", "")),
            data=dict(data.get("data", {})),
            parent_span_id=data.get("parent_span_id"),
            start_ts=datetime.fromisoformat(data["start_ts"]),
            end_ts=datetime.fromisoformat(data["end_ts"]) if data.get("end_ts") else None,
            duration_ms=float(data["duration_ms"]) if data.get("duration_ms") is not None else None,
            error=data.get("error"),
            error_message=data.get("error_message"),
        )


@dataclass(slots=True)
class TraceSummary:
    """Aggregated trace information for a session.

    Provides a high-level overview of all trace activity in a session,
    including counts by type, error rates, and total duration.
    """

    session_id: str = ""
    total_spans: int = 0
    span_counts_by_type: dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    duration_ms: float = 0.0
    summary_text: str = ""
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def counts_by_type(self) -> dict[str, int]:
        """Backward-compatible alias for span_counts_by_type."""
        return self.span_counts_by_type

    def to_human_readable(self) -> str:
        """Generate human-readable summary text."""
        lines = [
            f"Session: {self.session_id}",
            f"Total spans: {self.total_spans}",
            f"Errors: {self.error_count}",
            f"Duration: {self.duration_ms:.1f}ms",
            "",
            "Breakdown by type:",
        ]
        for trace_type, count in sorted(self.span_counts_by_type.items()):
            lines.append(f"  {trace_type}: {count}")
        return "\n".join(lines)


@dataclass(slots=True)
class OperatorTraceView:
    """Operator-friendly trace view for human consumption.

    Provides a summarized, human-readable view of trace activity
    with key metrics and related spans for operational debugging.
    """

    what_happened: str
    when: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    related_spans: list[TraceSpan] = field(default_factory=list)
    key_metrics: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    severity: TraceSeverity = TraceSeverity.INFO


@dataclass(slots=True)
class TraceOutput:
    """Enhanced trace output for operator consumption.

    Carries trace information through the ResponseEnvelope with
    complete context for debugging, monitoring, and observability.
    """

    trace_type: str
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    span_id: str = ""
    parent_span_id: str | None = None
    start_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Enhanced fields for operator consumption
    severity: TraceSeverity = TraceSeverity.INFO
    source: str = ""  # Component that emitted this trace
    name: str = ""  # Human-readable name
    status: TraceStatus = TraceStatus.OK
    error_message: str | None = None
    # Optional rich trace data (for detailed introspection)
    spans: list[TraceSpan] = field(default_factory=list)
    summary: TraceSummary | None = None
    operator_view: OperatorTraceView | None = None

    def duration_ms(self) -> float:
        """Calculate duration in milliseconds."""
        return (self.end_ts - self.start_ts).total_seconds() * 1000


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
