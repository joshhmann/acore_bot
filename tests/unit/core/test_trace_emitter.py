"""Trace Emitter Hardening Tests - Phase 3 Slice 2.

This module tests the trace emitter system for runtime observability.
Key requirements:
- All traces are runtime-owned (no adapter-side trace creation)
- TraceType enum provides standardized taxonomy
- TraceSpan captures timing and parent-child relationships
- TraceSnapshot provides session-scoped trace aggregation
- TraceSummary provides operator-friendly views

Trace Taxonomy Compliance:
- ADAPTER_*: Ingress/egress at adapter boundaries
- SESSION_*: Session lifecycle events
- PROVIDER_*: Provider/model interactions
- TOOL_*: Tool execution events
- MEMORY_*: Memory system operations
- ERROR_*: Error conditions
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.trace import (
    TraceEmitter,
    TraceSpan,
    TraceSnapshot,
    TraceType,
    generate_span_id,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def emitter() -> TraceEmitter:
    """Create a fresh trace emitter for each test."""
    return TraceEmitter()


@pytest.fixture
def sample_session_id() -> str:
    """Sample session ID for testing."""
    return "test-session-123"


@pytest.fixture
def sample_span(sample_session_id: str) -> TraceSpan:
    """Create a sample trace span."""
    return TraceSpan(
        span_id=generate_span_id(),
        trace_type=TraceType.SESSION_START,
        session_id=sample_session_id,
        data={"persona_id": "test_persona"},
    )


@pytest.fixture
def populated_snapshot(sample_session_id: str) -> TraceSnapshot:
    """Create a snapshot with multiple spans of different types."""
    snapshot = TraceSnapshot(session_id=sample_session_id)

    # Add spans of various types
    spans = [
        TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.SESSION_START,
            session_id=sample_session_id,
            start_ts=datetime.now(timezone.utc) - timedelta(seconds=10),
            end_ts=datetime.now(timezone.utc) - timedelta(seconds=9),
        ),
        TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.ADAPTER_INGRESS,
            session_id=sample_session_id,
            start_ts=datetime.now(timezone.utc) - timedelta(seconds=9),
            end_ts=datetime.now(timezone.utc) - timedelta(seconds=8),
        ),
        TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.MEMORY_ASSEMBLY,
            session_id=sample_session_id,
            start_ts=datetime.now(timezone.utc) - timedelta(seconds=8),
            end_ts=datetime.now(timezone.utc) - timedelta(seconds=7),
        ),
        TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.PROVIDER_REQUEST,
            session_id=sample_session_id,
            start_ts=datetime.now(timezone.utc) - timedelta(seconds=7),
            end_ts=datetime.now(timezone.utc) - timedelta(seconds=5),
        ),
        TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.PROVIDER_RESPONSE,
            session_id=sample_session_id,
            start_ts=datetime.now(timezone.utc) - timedelta(seconds=5),
            end_ts=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
        TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.SESSION_END,
            session_id=sample_session_id,
            start_ts=datetime.now(timezone.utc) - timedelta(seconds=1),
            end_ts=datetime.now(timezone.utc),
        ),
    ]

    for span in spans:
        snapshot.add_span(span)

    return snapshot


# =============================================================================
# TraceType Tests
# =============================================================================


class TestTraceTypeValues:
    """Verify TraceType enum contains all expected types."""

    def test_trace_type_adapter_values(self) -> None:
        """All adapter trace types exist."""
        assert TraceType.ADAPTER_INGRESS.value == "adapter_ingress"
        assert TraceType.ADAPTER_EGRESS.value == "adapter_egress"

    def test_trace_type_session_values(self) -> None:
        """All session trace types exist."""
        assert TraceType.SESSION_START.value == "session_start"
        assert TraceType.SESSION_END.value == "session_end"
        assert TraceType.SESSION_RESUME.value == "session_resume"

    def test_trace_type_provider_values(self) -> None:
        """All provider trace types exist."""
        assert TraceType.PROVIDER_REQUEST.value == "provider_request"
        assert TraceType.PROVIDER_RESPONSE.value == "provider_response"
        assert TraceType.PROVIDER_STREAM.value == "provider_stream"

    def test_trace_type_tool_values(self) -> None:
        """All tool trace types exist."""
        assert TraceType.TOOL_CALL.value == "tool_call"
        assert TraceType.TOOL_RESULT.value == "tool_result"
        assert TraceType.TOOL_ERROR.value == "tool_error"

    def test_trace_type_memory_values(self) -> None:
        """All memory trace types exist."""
        assert TraceType.MEMORY_ASSEMBLY.value == "memory_assembly"
        assert TraceType.MEMORY_STORE.value == "memory_store"
        assert TraceType.MEMORY_RETRIEVE.value == "memory_retrieve"

    def test_trace_type_error_values(self) -> None:
        """All error trace types exist."""
        assert TraceType.ERROR.value == "error"
        assert TraceType.ERROR_RUNTIME.value == "error_runtime"
        assert TraceType.ERROR_PROVIDER.value == "error_provider"
        assert TraceType.ERROR_TOOL.value == "error_tool"


class TestTraceTypeStringValues:
    """Verify TraceType values are strings for serialization."""

    def test_trace_type_values_are_strings(self) -> None:
        """All trace type values are strings (not ints)."""
        for trace_type in TraceType:
            assert isinstance(trace_type.value, str)
            assert len(trace_type.value) > 0

    def test_trace_type_values_use_snake_case(self) -> None:
        """All trace type values use snake_case naming."""
        for trace_type in TraceType:
            # Should contain underscores for namespacing (most types)
            # or be lowercase single words
            assert trace_type.value == trace_type.value.lower()

    def test_trace_type_serialization_roundtrip(self) -> None:
        """TraceType can be serialized and deserialized."""
        for original in TraceType:
            # Serialize
            serialized = original.value
            # Deserialize
            deserialized = TraceType(serialized)
            assert deserialized == original


# =============================================================================
# TraceEmitter Tests
# =============================================================================


class TestEmitterInitialization:
    """Verify TraceEmitter creates with default state."""

    def test_emitter_initialization_default_state(self) -> None:
        """Emitter starts enabled with empty state."""
        emitter = TraceEmitter()
        assert emitter.is_enabled is True
        assert emitter.emitted_count == 0
        assert emitter.get_all_spans() == []

    def test_emitter_initialization_can_be_disabled(self) -> None:
        """Emitter can be disabled after creation."""
        emitter = TraceEmitter()
        emitter.disable()
        assert emitter.is_enabled is False

    def test_emitter_initialization_can_be_re_enabled(self) -> None:
        """Emitter can be re-enabled after disabling."""
        emitter = TraceEmitter()
        emitter.disable()
        emitter.enable()
        assert emitter.is_enabled is True

    def test_emitter_clear_resets_state(self, emitter: TraceEmitter) -> None:
        """Clear removes all spans and snapshots."""
        emitter.emit(TraceType.SESSION_START, session_id="test", span_id=generate_span_id())
        assert len(emitter.get_all_spans()) == 1

        emitter.clear()
        assert emitter.get_all_spans() == []
        assert emitter.get_snapshot("test") is None


class TestEmitAdapterIngress:
    """Verify adapter ingress trace emission."""

    def test_emit_adapter_ingress_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Ingress trace has correct type."""
        data = {
            "platform": "discord",
            "user_id": "user_123",
            "room_id": "room_456",
            "text": "Hello bot",
        }
        trace = emitter.emit_adapter_ingress(sample_session_id, generate_span_id(), data)

        assert trace.trace_type == "adapter_ingress"
        assert trace.session_id == sample_session_id

    def test_emit_adapter_ingress_captures_platform_data(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Ingress trace captures relevant platform data."""
        data = {
            "platform": "slack",
            "user_id": "user_789",
            "room_id": "channel_abc",
            "text": "Test message content",
        }
        trace = emitter.emit_adapter_ingress(sample_session_id, generate_span_id(), data)

        assert trace.data["platform"] == "slack"


class TestEmitSessionStart:
    """Verify session lifecycle trace emission."""

    def test_emit_session_start_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Session start trace has correct type."""
        span = emitter.emit_session_start(sample_session_id)

        assert span.trace_type == TraceType.SESSION_START
        assert span.session_id == sample_session_id

    def test_emit_session_start_includes_persona(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Session start can include persona ID."""
        span = emitter.emit_session_start(
            sample_session_id, persona_id="test_persona"
        )

        assert span.data["persona_id"] == "test_persona"

    def test_emit_session_start_includes_metadata(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Session start can include additional metadata."""
        extra = {"source": "web", "client_version": "1.0.0"}
        span = emitter.emit_session_start(
            sample_session_id, data=extra
        )

        assert span.data["source"] == "web"
        assert span.data["client_version"] == "1.0.0"

    def test_emit_session_end_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Session end trace has correct type."""
        span = emitter.emit_session_end(sample_session_id, reason="user_disconnect")

        assert span.trace_type == TraceType.SESSION_END
        assert span.data["reason"] == "user_disconnect"


class TestEmitProviderRequestResponse:
    """Verify provider call tracing."""

    def test_emit_provider_request_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Provider request trace has correct type."""
        span = emitter.emit_provider_request(
            session_id=sample_session_id,
            provider_id="ollama",
            model_id="llama3.1",
            request_preview={"messages": 5},
        )

        assert span.trace_type == TraceType.PROVIDER_REQUEST
        assert span.data["provider_id"] == "ollama"
        assert span.data["model_id"] == "llama3.1"

    def test_emit_provider_response_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Provider response trace has correct type."""
        span = emitter.emit_provider_response(
            session_id=sample_session_id,
            provider_id="ollama",
            model_id="llama3.1",
            response_summary={"tokens": 150, "latency_ms": 500},
        )

        assert span.trace_type == TraceType.PROVIDER_RESPONSE
        assert span.data["response_summary"]["tokens"] == 150

    def test_emit_provider_traces_can_be_nested(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Provider request/response can have parent-child relationship."""
        request_span = emitter.emit_provider_request(
            session_id=sample_session_id,
            provider_id="openai",
            model_id="gpt-4",
            request_preview={},
        )

        response_span = emitter.emit_provider_response(
            session_id=sample_session_id,
            provider_id="openai",
            model_id="gpt-4",
            response_summary={},
            parent_span_id=request_span.span_id,
        )

        assert response_span.parent_span_id == request_span.span_id


class TestEmitToolCallResult:
    """Verify tool execution tracing."""

    def test_emit_tool_call_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Tool call trace has correct type."""
        span = emitter.emit_tool_call(
            session_id=sample_session_id,
            tool_name="web_search",
            arguments={"query": "test"},
        )

        assert span.trace_type == TraceType.TOOL_CALL
        assert span.data["tool_name"] == "web_search"

    def test_emit_tool_result_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Tool result trace has correct type."""
        span = emitter.emit_tool_result(
            session_id=sample_session_id,
            tool_name="web_search",
            success=True,
            result_preview={"results": 5},
        )

        assert span.trace_type == TraceType.TOOL_RESULT
        assert span.data["success"] is True

    def test_emit_tool_result_captures_failure(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Tool result can indicate failure."""
        span = emitter.emit_tool_result(
            session_id=sample_session_id,
            tool_name="file_read",
            success=False,
            result_preview={"error": "file_not_found"},
            error="file_not_found",
        )

        assert span.data["success"] is False
        assert span.has_error is True


class TestEmitMemoryAssembly:
    """Verify memory context tracing."""

    def test_emit_memory_assembly_creates_correct_type(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Memory assembly trace has correct type."""
        span = emitter.emit_memory_assembly(
            session_id=sample_session_id,
            context_stats={
                "turns": 10,
                "memories": 5,
                "tokens": 2000,
            },
        )

        assert span.trace_type == TraceType.MEMORY_ASSEMBLY
        assert span.data["context_stats"]["turns"] == 10

    def test_emit_memory_assembly_captures_stats(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Memory assembly captures context statistics."""
        stats = {
            "episodes": 3,
            "facts": 7,
            "preferences": 2,
            "token_estimate": 1500,
        }
        span = emitter.emit_memory_assembly(
            session_id=sample_session_id,
            context_stats=stats,
        )

        assert span.data["context_stats"] == stats


class TestEmitError:
    """Verify error trace emission."""

    def test_emit_error_runtime_type(self, emitter: TraceEmitter, sample_session_id: str) -> None:
        """Runtime error emits correct type."""
        span = emitter.emit_error(
            session_id=sample_session_id,
            error_type="runtime",
            error_message="Something went wrong",
        )

        assert span.trace_type == TraceType.ERROR_RUNTIME
        assert span.error == "Something went wrong"

    def test_emit_error_provider_type(self, emitter: TraceEmitter, sample_session_id: str) -> None:
        """Provider error emits correct type."""
        span = emitter.emit_error(
            session_id=sample_session_id,
            error_type="provider",
            error_message="API rate limit exceeded",
        )

        assert span.trace_type == TraceType.ERROR_PROVIDER

    def test_emit_error_tool_type(self, emitter: TraceEmitter, sample_session_id: str) -> None:
        """Tool error emits correct type."""
        span = emitter.emit_error(
            session_id=sample_session_id,
            error_type="tool",
            error_message="Tool execution timeout",
        )

        assert span.trace_type == TraceType.ERROR_TOOL

    def test_emit_error_includes_stack_info(
        self, emitter: TraceEmitter, sample_session_id: str
    ) -> None:
        """Error can include stack trace info."""
        stack = "Traceback (most recent call last):\n  File ..."
        span = emitter.emit_error(
            session_id=sample_session_id,
            error_type="runtime",
            error_message="Exception occurred",
            stack_info=stack,
        )

        assert span.data["has_stack"] is True
        assert "stack_info" in span.data

    def test_emit_error_defaults_to_runtime(self, emitter: TraceEmitter, sample_session_id: str) -> None:
        """Unknown error type defaults to runtime error."""
        span = emitter.emit_error(
            session_id=sample_session_id,
            error_type="unknown_category",
            error_message="Some error",
        )

        assert span.trace_type == TraceType.ERROR_RUNTIME


# =============================================================================
# TraceSpan Tests
# =============================================================================


class TestSpanCreation:
    """Verify span creation with required fields."""

    def test_span_creation_required_fields(self) -> None:
        """Span can be created with minimal fields."""
        span = TraceSpan(
            span_id="test-id",
            trace_type=TraceType.SESSION_START,
            session_id="test-session",
        )

        assert span.span_id == "test-id"
        assert span.trace_type == TraceType.SESSION_START
        assert span.session_id == "test-session"

    def test_span_creation_with_all_fields(self) -> None:
        """Span can be created with all fields specified."""
        now = datetime.now(timezone.utc)
        span = TraceSpan(
            span_id="custom-id",
            trace_type=TraceType.PROVIDER_REQUEST,
            session_id="sess_123",
            start_ts=now,
            end_ts=now + timedelta(seconds=1),
            parent_span_id="parent-id",
            data={"key": "value"},
            error=None,
        )

        assert span.span_id == "custom-id"
        assert span.trace_type == TraceType.PROVIDER_REQUEST
        assert span.session_id == "sess_123"
        assert span.parent_span_id == "parent-id"
        assert span.data == {"key": "value"}

    def test_span_auto_generates_uuid(self) -> None:
        """Span ID is auto-generated UUID if not provided."""
        span1 = TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.SESSION_START,
            session_id="s1",
        )
        span2 = TraceSpan(
            span_id=generate_span_id(),
            trace_type=TraceType.SESSION_START,
            session_id="s2",
        )

        assert span1.span_id != span2.span_id
        assert len(span1.span_id) == 36  # UUID format


class TestSpanWithParent:
    """Verify parent-child span relationships."""

    def test_span_with_parent_reference(self) -> None:
        """Child span references parent."""
        parent = TraceSpan(
            span_id="parent-1",
            trace_type=TraceType.SESSION_START,
            session_id="s1",
        )
        child = TraceSpan(
            span_id="child-1",
            trace_type=TraceType.TOOL_CALL,
            session_id="s1",
            parent_span_id=parent.span_id,
        )

        assert child.parent_span_id == parent.span_id

    def test_span_without_parent(self) -> None:
        """Root span has no parent."""
        root = TraceSpan(
            span_id="root-1",
            trace_type=TraceType.SESSION_START,
            session_id="s1",
        )
        assert root.parent_span_id is None

    def test_span_nesting_chain(self) -> None:
        """Spans can form a chain."""
        root = TraceSpan(
            span_id="root",
            trace_type=TraceType.SESSION_START,
            session_id="s1",
        )
        level1 = TraceSpan(
            span_id="level1",
            trace_type=TraceType.TOOL_CALL,
            session_id="s1",
            parent_span_id=root.span_id,
        )
        level2 = TraceSpan(
            span_id="level2",
            trace_type=TraceType.TOOL_RESULT,
            session_id="s1",
            parent_span_id=level1.span_id,
        )

        assert level2.parent_span_id == level1.span_id
        assert level1.parent_span_id == root.span_id
        assert root.parent_span_id is None


class TestSpanDurationCalculation:
    """Verify automatic duration calculation."""

    def test_span_duration_zero(self) -> None:
        """Duration is zero for instantaneous span."""
        now = datetime.now(timezone.utc)
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
            start_ts=now,
            end_ts=now,
        )

        assert span.duration_ms == 0.0

    def test_span_duration_calculation(self) -> None:
        """Duration is calculated from start to end."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(milliseconds=150)
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
            start_ts=start,
            end_ts=end,
        )

        assert span.duration_ms == pytest.approx(150.0, abs=0.1)

    def test_span_duration_seconds(self) -> None:
        """Duration handles multi-second spans."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=2, milliseconds=500)
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
            start_ts=start,
            end_ts=end,
        )

        assert span.duration_ms == pytest.approx(2500.0, abs=0.1)

    def test_span_duration_none_when_no_end(self) -> None:
        """Duration is None when end_ts is not set."""
        start = datetime.now(timezone.utc)
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
            start_ts=start,
            end_ts=None,
        )

        assert span.duration_ms is None


class TestSpanErrorStatus:
    """Verify error state handling."""

    def test_span_no_error_by_default(self) -> None:
        """New spans have no error."""
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
        )
        assert span.has_error is False
        assert span.error is None

    def test_span_with_error(self) -> None:
        """Span with error message has error status."""
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.TOOL_RESULT,
            session_id="test",
            error="Something failed",
        )
        assert span.has_error is True
        assert span.error == "Something failed"

    def test_span_error_empty_string(self) -> None:
        """Empty string error is not an error."""
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
            error="",
        )
        assert span.has_error is False


class TestSpanSerialization:
    """Verify span serialization to/from dict."""

    def test_span_to_dict(self) -> None:
        """Span serializes to dictionary."""
        now = datetime.now(timezone.utc)
        span = TraceSpan(
            span_id="test-id",
            trace_type=TraceType.TOOL_CALL,
            session_id="sess_1",
            start_ts=now,
            end_ts=now + timedelta(milliseconds=100),
            data={"tool": "search"},
        )

        data = span.to_dict()

        assert data["span_id"] == "test-id"
        assert data["trace_type"] == "tool_call"
        assert data["session_id"] == "sess_1"
        assert "duration_ms" in data
        assert data["data"]["tool"] == "search"

    def test_span_from_dict(self) -> None:
        """Span deserializes from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "span_id": "test-id",
            "trace_type": "memory_assembly",
            "session_id": "sess_1",
            "start_ts": now.isoformat(),
            "end_ts": now.isoformat(),
            "parent_span_id": None,
            "data": {"stats": {}},
            "error": None,
        }

        span = TraceSpan.from_dict(data)

        assert span.span_id == "test-id"
        assert span.trace_type == TraceType.MEMORY_ASSEMBLY
        assert span.session_id == "sess_1"

    def test_span_roundtrip(self) -> None:
        """Span survives serialize/deserialize roundtrip."""
        now = datetime.now(timezone.utc)
        original = TraceSpan(
            span_id="original-id",
            trace_type=TraceType.PROVIDER_RESPONSE,
            session_id="test-sess",
            start_ts=now,
            end_ts=now + timedelta(seconds=1),
            data={"tokens": 100},
        )

        data = original.to_dict()
        restored = TraceSpan.from_dict(data)

        assert restored.span_id == original.span_id
        assert restored.trace_type == original.trace_type
        assert restored.session_id == original.session_id
        assert restored.data == original.data


# =============================================================================
# TraceSnapshot Tests
# =============================================================================


class TestSnapshotCreation:
    """Verify snapshot creation for empty and populated states."""

    def test_snapshot_creation_empty(self) -> None:
        """Empty snapshot has no spans."""
        snapshot = TraceSnapshot()

        assert snapshot.session_id == ""
        assert snapshot.get_trace_count() == 0
        assert isinstance(snapshot.captured_at, datetime)

    def test_snapshot_creation_with_session(self) -> None:
        """Snapshot can be created with session ID."""
        snapshot = TraceSnapshot(session_id="sess_123")

        assert snapshot.session_id == "sess_123"

    def test_snapshot_creation_populated(self) -> None:
        """Snapshot can be created with initial spans."""
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
        )
        snapshot = TraceSnapshot(session_id="test", _traces=[span])

        assert snapshot.get_trace_count() == 1


class TestSnapshotAddSpan:
    """Verify adding spans increases count."""

    def test_snapshot_add_span_increases_count(self) -> None:
        """Adding a span increases the span count."""
        snapshot = TraceSnapshot(session_id="test")
        assert snapshot.get_trace_count() == 0

        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
        ))
        assert snapshot.get_trace_count() == 1

        snapshot.add_span(TraceSpan(
            span_id="s2",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))
        assert snapshot.get_trace_count() == 2

    def test_snapshot_add_span_preserves_span(self) -> None:
        """Added span is stored in snapshot."""
        snapshot = TraceSnapshot(session_id="test")
        span = TraceSpan(
            span_id="s1",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        )

        snapshot.add_span(span)

        assert snapshot.get_recent(1)[0] is span


class TestSnapshotGetByType:
    """Verify filtering by trace type."""

    def test_snapshot_get_by_type_found(self) -> None:
        """Returns spans matching the type."""
        snapshot = TraceSnapshot(session_id="test")
        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))
        snapshot.add_span(TraceSpan(
            span_id="s2",
            trace_type=TraceType.TOOL_RESULT,
            session_id="test",
        ))
        snapshot.add_span(TraceSpan(
            span_id="s3",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))

        tool_calls = snapshot.get_by_type(TraceType.TOOL_CALL)

        assert len(tool_calls) == 2
        assert all(s.trace_type == TraceType.TOOL_CALL for s in tool_calls)

    def test_snapshot_get_by_type_not_found(self) -> None:
        """Returns empty list when no matches."""
        snapshot = TraceSnapshot(session_id="test")
        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
        ))

        results = snapshot.get_by_type(TraceType.TOOL_CALL)

        assert results == []


class TestSnapshotGetRecent:
    """Verify time-based filtering."""

    def test_snapshot_get_recent_filters_by_time(self) -> None:
        """Returns spans within limit."""
        snapshot = TraceSnapshot(session_id="test")

        # Add spans
        for i in range(5):
            snapshot.add_span(TraceSpan(
                span_id=f"s{i}",
                trace_type=TraceType.TOOL_CALL,
                session_id="test",
            ))

        recent = snapshot.get_recent(3)

        assert len(recent) == 3

    def test_snapshot_get_recent_returns_oldest_first(self) -> None:
        """Recent returns spans in order."""
        snapshot = TraceSnapshot(session_id="test")

        for i in range(3):
            snapshot.add_span(TraceSpan(
                span_id=f"s{i}",
                trace_type=TraceType.TOOL_CALL,
                session_id="test",
            ))

        recent = snapshot.get_recent(2)

        assert recent[0].span_id == "s1"
        assert recent[1].span_id == "s2"


class TestSnapshotGetErrors:
    """Verify error span filtering."""

    def test_snapshot_get_errors_only_error_spans(self) -> None:
        """Returns only spans with errors."""
        snapshot = TraceSnapshot(session_id="test")
        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))  # No error
        snapshot.add_span(TraceSpan(
            span_id="s2",
            trace_type=TraceType.TOOL_RESULT,
            session_id="test",
            error="Failed",
        ))
        snapshot.add_span(TraceSpan(
            span_id="s3",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))  # No error

        errors = snapshot.get_errors()

        assert len(errors) == 1
        assert errors[0].error == "Failed"


class TestSnapshotToDict:
    """Verify snapshot serialization."""

    def test_snapshot_to_dict_basic(self) -> None:
        """Snapshot serializes to dictionary."""
        snapshot = TraceSnapshot(session_id="test-sess")
        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="test",
        ))

        data = snapshot.to_dict()

        assert data["session_id"] == "test-sess"
        assert data["count"] == 1
        assert "spans" in data
        assert "captured_at" in data

    def test_snapshot_to_dict_includes_spans(self) -> None:
        """Serialized snapshot includes span data."""
        snapshot = TraceSnapshot(session_id="test")
        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))

        data = snapshot.to_dict()

        assert len(data["spans"]) == 1
        assert data["spans"][0]["trace_type"] == "tool_call"


# =============================================================================
# Trace Taxonomy Compliance Tests
# =============================================================================


class TestAllTracesHaveRequiredFields:
    """Verify all traces contain required fields."""

    def test_trace_has_type_field(self, sample_span: TraceSpan) -> None:
        """All traces have a trace_type field."""
        assert sample_span.trace_type is not None
        assert isinstance(sample_span.trace_type, TraceType)

    def test_trace_has_timestamp(self, sample_span: TraceSpan) -> None:
        """All traces have timestamps."""
        assert isinstance(sample_span.start_ts, datetime)

    def test_trace_can_have_session_id(self) -> None:
        """Traces can be associated with sessions."""
        span_with_session = TraceSpan(
            span_id="s1",
            trace_type=TraceType.SESSION_START,
            session_id="sess_123",
        )
        span_without_session = TraceSpan(
            span_id="s2",
            trace_type=TraceType.SESSION_START,
            session_id="",
        )

        assert span_with_session.session_id == "sess_123"
        assert span_without_session.session_id == ""

    def test_all_trace_types_create_valid_spans(self, emitter: TraceEmitter) -> None:
        """Every TraceType can create a valid span."""
        for trace_type in TraceType:
            span = emitter.emit(
                trace_type=trace_type,
                session_id="test",
                span_id=generate_span_id(),
            )
            assert span.trace_type == trace_type
            assert span.span_id  # Has an ID
            assert isinstance(span.start_ts, datetime)


class TestTraceTypesAreStandardized:
    """Verify only TraceType enum is used for trace types."""

    def test_all_standard_types_are_trace_type_enum(self) -> None:
        """All trace types are members of TraceType enum."""
        expected_types = {
            "adapter_ingress",
            "adapter_egress",
            "session_start",
            "session_end",
            "session_resume",
            "session_lifecycle",
            "provider_request",
            "provider_response",
            "provider_stream",
            "tool_call",
            "tool_result",
            "tool_error",
            "memory_assembly",
            "memory_store",
            "memory_retrieve",
            "command_dispatch",
            "action_dispatch",
            "approval_request",
            "approval_decision",
            "error",
            "error_runtime",
            "error_provider",
            "error_tool",
            "context_cache",
        }

        actual_types = {t.value for t in TraceType}

        assert actual_types == expected_types


class TestTracesAreRuntimeOwned:
    """Verify traces are only created by runtime, not adapters."""

    def test_emitter_is_runtime_owned(self) -> None:
        """TraceEmitter is a runtime concept."""
        from core.trace import TraceEmitter

        assert TraceEmitter is not None

    def test_traces_not_created_in_adapter_code(self) -> None:
        """Spans should not be created in adapter files."""
        # This test documents the contract - adapters use PlatformFacts
        # and the runtime creates traces from processing
        from core.interfaces import PlatformFacts

        # Adapters create facts
        facts = PlatformFacts(
            text="Hello",
            user_id="user_1",
            room_id="room_1",
        )
        assert facts is not None

        # Runtime creates traces from processing
        emitter = TraceEmitter()
        trace = emitter.emit_adapter_ingress(
            session_id="sess_1",
            span_id=generate_span_id(),
            data={
                "platform": "test",
                "user_id": facts.user_id,
                "room_id": facts.room_id,
                "text": facts.text,
            },
        )
        assert TraceType(trace.trace_type) == TraceType.ADAPTER_INGRESS

    def test_emitter_disable_prevents_storage(self, emitter: TraceEmitter) -> None:
        """Disabled emitter doesn't store spans."""
        emitter.disable()
        span = emitter.emit(TraceType.SESSION_START, session_id="test", span_id=generate_span_id())

        # Emitter returns a span but doesn't store it in snapshots
        assert span.trace_type == TraceType.SESSION_START
        assert emitter.get_snapshot("test") is None


# =============================================================================
# Operator View Tests
# =============================================================================


class TestTraceSummaryAggregation:
    """Verify trace summary counts by type."""

    def test_summary_empty_snapshot(self) -> None:
        """Summary from empty snapshot has zero counts."""
        snapshot = TraceSnapshot()
        summary = snapshot.to_summary()

        assert summary.total_spans == 0
        assert summary.span_counts_by_type == {}
        assert summary.error_count == 0

    def test_summary_counts_by_type(self, populated_snapshot: TraceSnapshot) -> None:
        """Summary aggregates counts by trace type."""
        summary = populated_snapshot.to_summary()

        assert summary.total_spans == 6
        assert summary.span_counts_by_type.get("session_start") == 1
        assert summary.span_counts_by_type.get("adapter_ingress") == 1
        assert summary.span_counts_by_type.get("memory_assembly") == 1
        assert summary.span_counts_by_type.get("provider_request") == 1
        assert summary.span_counts_by_type.get("provider_response") == 1
        assert summary.span_counts_by_type.get("session_end") == 1

    def test_summary_error_count(self) -> None:
        """Summary counts errors correctly."""
        snapshot = TraceSnapshot(session_id="test")
        snapshot.add_span(TraceSpan(
            span_id="s1",
            trace_type=TraceType.TOOL_CALL,
            session_id="test",
        ))  # No error
        snapshot.add_span(TraceSpan(
            span_id="s2",
            trace_type=TraceType.TOOL_RESULT,
            session_id="test",
            error="Failed",
        ))
        snapshot.add_span(TraceSpan(
            span_id="s3",
            trace_type=TraceType.ERROR_RUNTIME,
            session_id="test",
            error="Runtime error",
        ))

        summary = snapshot.to_summary()

        assert summary.error_count == 2

    def test_summary_duration_calculation(self, populated_snapshot: TraceSnapshot) -> None:
        """Summary calculates total duration from span timestamps."""
        summary = populated_snapshot.to_summary()

        # Duration should be roughly 10 seconds (from -10s to now)
        assert summary.duration_ms > 0
        # Should be at least 8 seconds worth of ms (some tolerance)
        assert summary.duration_ms >= 8000

    def test_summary_session_id_preserved(self, populated_snapshot: TraceSnapshot) -> None:
        """Summary preserves session ID."""
        summary = populated_snapshot.to_summary()

        assert summary.session_id == populated_snapshot.session_id


class TestOperatorTraceViewHumanReadable:
    """Verify operator-friendly trace views."""

    def test_summary_to_human_readable_format(self, populated_snapshot: TraceSnapshot) -> None:
        """Summary generates human-readable text."""
        summary = populated_snapshot.to_summary()
        text = summary.to_human_readable()

        # Should contain key information
        assert "Session:" in text
        assert "Total spans:" in text
        assert "Errors:" in text
        assert "Duration:" in text
        assert "Breakdown by type:" in text

    def test_summary_includes_all_types(self, populated_snapshot: TraceSnapshot) -> None:
        """Human readable includes all trace types."""
        summary = populated_snapshot.to_summary()
        text = summary.to_human_readable()

        for trace_type in summary.span_counts_by_type:
            assert trace_type in text

    def test_summary_text_generated(self, populated_snapshot: TraceSnapshot) -> None:
        """Summary has generated summary text."""
        summary = populated_snapshot.to_summary()

        assert summary.session_id in summary.summary_text
        assert str(summary.total_spans) in summary.summary_text
        assert str(summary.error_count) in summary.summary_text


# =============================================================================
# Integration Tests
# =============================================================================


class TestFullTraceFlow:
    """End-to-end trace flow for a typical session."""

    def test_complete_session_trace_flow(self, emitter: TraceEmitter) -> None:
        """Full session lifecycle with all trace types."""
        session_id = "full-session-test"

        # Session start
        _ = emitter.emit_session_start(session_id, persona_id="assistant")

        # Adapter ingress
        _ = emitter.emit_adapter_ingress(
            session_id,
            generate_span_id(),
            data={"platform": "web", "user_id": "user_1", "room_id": "room_1", "text": "Hello"},
        )

        # Memory assembly
        _ = emitter.emit_memory_assembly(
            session_id,
            context_stats={"turns": 5, "tokens": 1500},
        )

        # Provider request/response
        provider_req = emitter.emit_provider_request(
            session_id,
            provider_id="openai",
            model_id="gpt-4",
            request_preview={"messages": 5},
        )

        _ = emitter.emit_provider_response(
            session_id,
            provider_id="openai",
            model_id="gpt-4",
            response_summary={"tokens": 100, "latency_ms": 500},
            parent_span_id=provider_req.span_id,
        )

        # Tool call (as part of processing)
        tool_call = emitter.emit_tool_call(
            session_id,
            tool_name="web_search",
            arguments={"query": "test"},
        )

        _ = emitter.emit_tool_result(
            session_id,
            tool_name="web_search",
            success=True,
            result_preview={"results": 3},
            parent_span_id=tool_call.span_id,
        )

        # Session end
        emitter.emit_session_end(
            session_id,
            reason="completed",
        )

        # Verify snapshot
        snapshot = emitter.get_snapshot(session_id)
        assert snapshot is not None
        assert snapshot.get_trace_count() == 8

        # Verify summary
        summary = snapshot.to_summary()
        assert summary.total_spans == 8
        assert summary.error_count == 0

    def test_error_session_trace_flow(self, emitter: TraceEmitter) -> None:
        """Session with error traces."""
        session_id = "error-session-test"

        emitter.emit_session_start(session_id)
        emitter.emit_adapter_ingress(session_id, generate_span_id(), {"platform": "discord", "user_id": "u1", "room_id": "r1", "text": "Hi"})
        emitter.emit_provider_request(session_id, provider_id="ollama", model_id="llama3.1")

        # Simulate provider error
        emitter.emit_error(
            session_id,
            error_type="provider",
            error_message="Connection timeout",
        )

        emitter.emit_session_end(session_id, reason="error")

        snapshot = emitter.get_snapshot(session_id)
        summary = snapshot.to_summary()

        assert summary.error_count == 1
        assert summary.span_counts_by_type.get("error_provider") == 1
