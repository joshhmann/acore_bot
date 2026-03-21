"""Trace emitter system for runtime observability.

This module provides the trace emission infrastructure for operator introspection,
as defined in Phase 3 Slice 2. All traces are runtime-owned; adapters do not
create traces directly.

Key Components:
- TraceType: Enumeration of standardized trace types
- TraceEmitter: Runtime-owned trace emission interface
- TraceSpan: Individual trace span with timing and metadata
- TraceSnapshot: Aggregated view of traces for a session
- TraceSummary: Human-readable summary for operators

Trace Taxonomy Compliance:
- ADAPTER_*: Ingress/egress at adapter boundaries
- SESSION_*: Session lifecycle events
- PROVIDER_*: Provider/model interactions
- TOOL_*: Tool execution events
- MEMORY_*: Memory system operations
- ERROR_*: Error conditions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from core.schemas import TraceOutput, TraceSpan, TraceSummary


class TraceType(str, Enum):
    """Standardized trace types for consistent operator introspection.

    All trace types are runtime-owned and follow the taxonomy:
    - ADAPTER_*: Ingress/egress at adapter boundaries
    - SESSION_*: Session lifecycle events
    - PROVIDER_*: Provider/model interactions
    - TOOL_*: Tool execution events
    - MEMORY_*: Memory system operations
    - ERROR_*: Error conditions
    - COMMAND_*: Command dispatch
    - ACTION_*: Action dispatch
    - APPROVAL_*: Approval queue events
    - CONTEXT_CACHE: Cache events
    """

    # Adapter traces
    ADAPTER_INGRESS = "adapter_ingress"
    ADAPTER_EGRESS = "adapter_egress"

    # Session traces
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_RESUME = "session_resume"
    SESSION_LIFECYCLE = "session_lifecycle"  # Legacy alias

    # Provider traces
    PROVIDER_REQUEST = "provider_request"
    PROVIDER_RESPONSE = "provider_response"
    PROVIDER_STREAM = "provider_stream"

    # Tool traces
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"

    # Command/Action traces
    COMMAND_DISPATCH = "command_dispatch"
    ACTION_DISPATCH = "action_dispatch"

    # Memory traces
    MEMORY_ASSEMBLY = "memory_assembly"
    MEMORY_STORE = "memory_store"
    MEMORY_RETRIEVE = "memory_retrieve"

    # Approval traces
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"

    # Error traces
    ERROR = "error"
    ERROR_RUNTIME = "error_runtime"
    ERROR_PROVIDER = "error_provider"
    ERROR_TOOL = "error_tool"

    # Cache traces
    CONTEXT_CACHE = "context_cache"

@dataclass
class TraceSnapshot:
    """Structured snapshot for operator consumption of trace data.

    TraceSnapshot aggregates traces by session and provides filtering
    capabilities for introspection and debugging. It is designed to
    hold a window of recent traces for a single session.
    """

    session_id: str = ""
    max_traces: int = 200
    _traces: list[TraceSpan] = field(default_factory=list, repr=False)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Ensure traces list is initialized."""
        if self._traces is None:
            self._traces = []

    def add_trace(self, trace: TraceOutput | TraceSpan) -> None:
        """Add a trace to the snapshot."""
        if isinstance(trace, TraceOutput):
            span = TraceSpan(
                span_id=trace.span_id,
                trace_type=trace.trace_type,
                session_id=trace.session_id,
                data=dict(trace.data),
                parent_span_id=trace.parent_span_id,
                start_ts=trace.start_ts,
                end_ts=trace.end_ts,
                status=trace.status,
                error_message=trace.error_message,
                name=trace.name,
            )
        else:
            span = trace

        self._traces.append(span)

        # Trim to max size
        if len(self._traces) > self.max_traces:
            self._traces = self._traces[-self.max_traces :]

    def add_span(self, span: TraceSpan) -> None:
        """Add a span to this snapshot (alias for add_trace)."""
        self.add_trace(span)

    def add_traces(self, traces: list[TraceOutput | TraceSpan]) -> None:
        """Add multiple traces to the snapshot."""
        for trace in traces:
            self.add_trace(trace)

    def get_recent(self, limit: int = 10) -> list[TraceSpan]:
        """Get the most recent traces (oldest first)."""
        return self._traces[-limit:]

    def get_by_type(self, trace_type: TraceType) -> list[TraceSpan]:
        """Get all traces of a specific type."""
        return [
            t
            for t in self._traces
            if (
                t.trace_type == trace_type
                or str(getattr(t.trace_type, "value", t.trace_type)) == trace_type.value
            )
        ]

    def get_by_parent_span(self, parent_span_id: str) -> list[TraceSpan]:
        """Get all child traces of a specific parent span."""
        return [t for t in self._traces if t.parent_span_id == parent_span_id]

    def get_time_range(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TraceSpan]:
        """Get traces within a time range."""
        result = self._traces[:]
        if start:
            result = [t for t in result if t.start_ts >= start]
        if end:
            result = [t for t in result if t.start_ts <= end]
        return result

    def get_errors(self) -> list[TraceSpan]:
        """Get all error spans."""
        return [t for t in self._traces if t.has_error]

    def get_trace_count(self) -> int:
        """Return the total number of traces in the snapshot."""
        return len(self._traces)

    def get_type_counts(self) -> dict[str, int]:
        """Get a count of traces by type."""
        counts: dict[str, int] = {}
        for trace in self._traces:
            key = (
                trace.trace_type.value
                if isinstance(trace.trace_type, TraceType)
                else str(trace.trace_type)
            )
            counts[key] = counts.get(key, 0) + 1
        return counts

    def clear(self) -> None:
        """Clear all traces from the snapshot."""
        self._traces.clear()

    def to_dict(self) -> dict[str, Any]:
        """Export snapshot to a dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "captured_at": self.captured_at.isoformat(),
            "count": len(self._traces),
            "max_traces": self.max_traces,
            "type_counts": self.get_type_counts(),
            "spans": [t.to_dict() for t in self._traces],
        }

    def to_outputs(self) -> list[TraceOutput]:
        """Convert all traces to TraceOutput objects."""
        return [t.to_output() for t in self._traces]

    def to_summary(self) -> TraceSummary:
        """Generate a summary from this snapshot."""
        if not self._traces:
            return TraceSummary(session_id=self.session_id)

        # Calculate counts by type
        counts = self.get_type_counts()

        # Calculate duration from earliest start to latest end
        start_times = [s.start_ts for s in self._traces]
        end_times = [s.end_ts for s in self._traces if s.end_ts is not None]

        if end_times:
            duration_ms = (max(end_times) - min(start_times)).total_seconds() * 1000
        else:
            duration_ms = 0.0

        # Error count
        error_count = sum(1 for s in self._traces if s.has_error)

        # Generate summary text
        summary_text = (
            f"Session {self.session_id}: {len(self._traces)} spans, {error_count} errors"
        )

        return TraceSummary(
            session_id=self.session_id,
            total_spans=len(self._traces),
            span_counts_by_type=counts,
            error_count=error_count,
            duration_ms=duration_ms,
            summary_text=summary_text,
        )


class TraceEmitter:
    """Runtime-owned trace emission interface.

    Adapters do not create traces directly. They provide facts to the runtime,
    and the runtime emits traces as part of processing.

    Usage:
        emitter = TraceEmitter()
        trace = emitter.emit_adapter_ingress(
            session_id="sess_123",
            span_id=generate_span_id(),
            data={"platform": "discord", "text": "hello"}
        )
    """

    def __init__(self) -> None:
        """Initialize the trace emitter with default state."""
        self._emitted_count: int = 0
        self._snapshots: dict[str, TraceSnapshot] = {}
        self._enabled = True

    @property
    def emitted_count(self) -> int:
        """Return the total number of traces emitted."""
        return self._emitted_count

    @property
    def is_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable trace emission."""
        self._enabled = True

    def disable(self) -> None:
        """Disable trace emission."""
        self._enabled = False

    def clear(self) -> None:
        """Clear all spans and snapshots (for testing)."""
        self._emitted_count = 0
        self._snapshots.clear()

    def clear_all(self) -> None:
        """Compatibility alias for clearing all emitter state."""
        self.clear()

    def _get_or_create_snapshot(self, session_id: str) -> TraceSnapshot:
        """Get existing snapshot or create new one for session."""
        if session_id not in self._snapshots:
            self._snapshots[session_id] = TraceSnapshot(session_id=session_id)
        return self._snapshots[session_id]

    def _create_trace(
        self,
        trace_type: TraceType,
        session_id: str,
        span_id: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Create a standardized TraceOutput with the given parameters."""
        if self._enabled:
            self._emitted_count += 1

        output = TraceOutput(
            trace_type=trace_type.value,
            data=dict(data) if data else {},
            session_id=session_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )
        if self._enabled and session_id:
            snapshot = self._get_or_create_snapshot(session_id)
            snapshot.add_trace(output)
        return output

    def emit(
        self,
        trace_type: TraceType,
        session_id: str,
        span_id: str | None = None,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit a generic trace span.

        Args:
            trace_type: The type of trace to emit
            session_id: Session identifier
            span_id: Optional span ID (auto-generated if not provided)
            data: Additional trace-specific data
            parent_span_id: Optional parent span for nesting

        Returns:
            The created TraceSpan
        """
        if span_id is None:
            span_id = generate_span_id()

        span = TraceSpan(
            span_id=span_id,
            trace_type=trace_type,
            session_id=session_id,
            data=data or {},
            parent_span_id=parent_span_id,
        )

        if self._enabled and session_id:
            snapshot = self._get_or_create_snapshot(session_id)
            snapshot.add_span(span)

        return span

    def emit_adapter_ingress(
        self,
        session_id: str,
        span_id: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for adapter event ingestion (platform -> runtime)."""
        return self._create_trace(
            TraceType.ADAPTER_INGRESS,
            session_id,
            span_id,
            data,
            parent_span_id,
        )

    def emit_session_start(
        self,
        session_id: str,
        span_id: str | None = None,
        persona_id: str = "",
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for session lifecycle start."""
        merged_data = {"event": "created", "persona_id": persona_id, **(data or {})}
        return self.emit(
            trace_type=TraceType.SESSION_START,
            session_id=session_id,
            span_id=span_id,
            data=merged_data,
            parent_span_id=parent_span_id,
        )

    def emit_session_end(
        self,
        session_id: str,
        span_id: str | None = None,
        reason: str = "",
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for session lifecycle end."""
        return self.emit(
            trace_type=TraceType.SESSION_END,
            session_id=session_id,
            span_id=span_id,
            data={"event": "destroyed", "reason": reason},
            parent_span_id=parent_span_id,
        )

    def emit_session_activity(
        self,
        session_id: str,
        span_id: str,
        activity_type: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for general session activity."""
        merged_data = {"event": "activity", "activity_type": activity_type, **(data or {})}
        return self._create_trace(
            TraceType.SESSION_LIFECYCLE,
            session_id,
            span_id,
            merged_data,
            parent_span_id,
        )

    def emit_provider_request(
        self,
        session_id: str,
        span_id: str | None = None,
        provider_id: str = "",
        model_id: str = "",
        request_preview: dict[str, Any] | None = None,
        *,
        provider: str = "",
        model: str = "",
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for provider request."""
        merged_data = {
            "provider_id": provider_id or provider,
            "model_id": model_id or model,
            "request_preview": request_preview or data or {},
        }
        return self.emit(
            trace_type=TraceType.PROVIDER_REQUEST,
            session_id=session_id,
            span_id=span_id,
            data=merged_data,
            parent_span_id=parent_span_id,
        )

    def emit_provider_response(
        self,
        session_id: str,
        span_id: str | None = None,
        provider_id: str = "",
        model_id: str = "",
        response_summary: dict[str, Any] | None = None,
        *,
        provider: str = "",
        model: str = "",
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for provider response."""
        merged_data = {
            "provider_id": provider_id or provider,
            "model_id": model_id or model,
            "response_summary": response_summary or data or {},
        }
        return self.emit(
            trace_type=TraceType.PROVIDER_RESPONSE,
            session_id=session_id,
            span_id=span_id,
            data=merged_data,
            parent_span_id=parent_span_id,
        )

    def emit_tool_call(
        self,
        session_id: str,
        span_id: str | None = None,
        tool_name: str = "",
        arguments: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for tool execution call."""
        merged_data = {
            "tool_name": tool_name,
            "arguments": arguments or {},
        }
        return self.emit(
            trace_type=TraceType.TOOL_CALL,
            session_id=session_id,
            span_id=span_id,
            data=merged_data,
            parent_span_id=parent_span_id,
        )

    def emit_tool_result(
        self,
        session_id: str,
        span_id: str | None = None,
        tool_name: str = "",
        success: bool = True,
        result_preview: dict[str, Any] | None = None,
        error: str | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for tool execution result."""
        merged_data = {
            "tool_name": tool_name,
            "success": success,
            "result_preview": result_preview or {},
        }
        span = self.emit(
            trace_type=TraceType.TOOL_RESULT,
            session_id=session_id,
            span_id=span_id,
            data=merged_data,
            parent_span_id=parent_span_id,
        )
        if error:
            span.error = error
        return span

    def emit_command_dispatch(
        self,
        session_id: str,
        span_id: str,
        command: str,
        args: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for command routing/handling."""
        merged_data = {
            "command": command,
            "args": dict(args) if args else {},
            **(data or {}),
        }
        return self._create_trace(
            TraceType.COMMAND_DISPATCH,
            session_id,
            span_id,
            merged_data,
            parent_span_id,
        )

    def emit_action_dispatch(
        self,
        session_id: str,
        span_id: str,
        action_type: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for action execution."""
        merged_data = {"action_type": action_type, **(data or {})}
        return self._create_trace(
            TraceType.ACTION_DISPATCH,
            session_id,
            span_id,
            merged_data,
            parent_span_id,
        )

    def emit_memory_assembly(
        self,
        session_id: str,
        span_id: str | None = None,
        context_stats: dict[str, Any] | None = None,
        *,
        memory_type: str = "",
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for memory context assembly."""
        return self.emit(
            trace_type=TraceType.MEMORY_ASSEMBLY,
            session_id=session_id,
            span_id=span_id,
            data={
                "memory_type": memory_type,
                "context_stats": context_stats or data or {},
            },
            parent_span_id=parent_span_id,
        )

    def emit_approval_request(
        self,
        session_id: str,
        span_id: str,
        request_type: str,
        request_id: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for approval queue events."""
        merged_data = {
            "request_type": request_type,
            "request_id": request_id,
            **(data or {}),
        }
        return self._create_trace(
            TraceType.APPROVAL_REQUEST,
            session_id,
            span_id,
            merged_data,
            parent_span_id,
        )

    def emit_approval_decision(
        self,
        session_id: str,
        span_id: str,
        request_id: str,
        decision: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for approval resolution."""
        merged_data = {
            "request_id": request_id,
            "decision": decision,
            **(data or {}),
        }
        return self._create_trace(
            TraceType.APPROVAL_DECISION,
            session_id,
            span_id,
            merged_data,
            parent_span_id,
        )

    def emit_error(
        self,
        session_id: str,
        span_id: str | None = None,
        error_type: str = "runtime",
        error_message: str = "",
        stack_info: str | None = None,
        *,
        error_code: str = "",
        message: str = "",
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """Emit trace for error conditions."""
        resolved_message = message or error_message
        # Map error_type to TraceType
        trace_type_map = {
            "runtime": TraceType.ERROR_RUNTIME,
            "provider": TraceType.ERROR_PROVIDER,
            "tool": TraceType.ERROR_TOOL,
        }
        trace_type = trace_type_map.get(error_type, TraceType.ERROR_RUNTIME)

        merged_data = {
            "error_type": error_type,
            "error_code": error_code,
            "error_message": resolved_message,
            "has_stack": stack_info is not None,
        }
        if data:
            merged_data.update(data)
        if stack_info:
            merged_data["stack_info"] = stack_info

        span = self.emit(
            trace_type=trace_type,
            session_id=session_id,
            span_id=span_id,
            data=merged_data,
            parent_span_id=parent_span_id,
        )
        span.error = resolved_message
        return span

    def emit_context_cache(
        self,
        session_id: str,
        span_id: str,
        cache_hit: bool,
        cache_key: str,
        data: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        """Emit trace for cache hit/miss events."""
        merged_data = {
            "cache_hit": cache_hit,
            "cache_key": cache_key,
            **(data or {}),
        }
        return self._create_trace(
            TraceType.CONTEXT_CACHE,
            session_id,
            span_id,
            merged_data,
            parent_span_id,
        )

    def get_snapshot(self, session_id: str) -> TraceSnapshot | None:
        """Get the current snapshot for a session."""
        snapshot = self._snapshots.get(session_id)
        if snapshot is None:
            return None

        normalized = TraceSnapshot(session_id=session_id, max_traces=snapshot.max_traces)
        seen_span_ids: set[str] = set()
        for span in snapshot.get_recent(limit=snapshot.max_traces):
            if span.span_id in seen_span_ids:
                continue
            normalized.add_trace(span)
            seen_span_ids.add(span.span_id)
        return normalized

    def get_all_spans(self) -> list[TraceSpan]:
        """Get all emitted spans across all sessions."""
        spans: list[TraceSpan] = []
        for snapshot in self._snapshots.values():
            spans.extend(snapshot._traces)
        return spans


def generate_span_id() -> str:
    """Generate a unique span identifier."""
    return str(uuid.uuid4())


def now_utc() -> datetime:
    """Get the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)
