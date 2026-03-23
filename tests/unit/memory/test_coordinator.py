"""Unit tests for the memory coordinator system.

Phase 3 Slice 3: Memory Coordinator + Memory Scoping

These tests validate the MemoryCoordinator and SharedMemoryTier classes,
ensuring proper typed memory operations, scoping behavior, and backward
compatibility with legacy MemoryContextBundle.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from memory.base import MemoryNamespace
from memory.coordinator import (
    MemoryCoordinator,
    SharedMemoryTier,
    _compute_typed_context_revision,
    _generate_id,
    create_persona_namespace,
    determine_scope,
)
from memory.episodes import Episode
from memory.local_json import LocalJsonMemoryStore
from memory.manager import MemoryContextBundle, MemoryManager
from memory.summary import DeterministicSummary
from memory.types import (
    ActionRecord,
    Fact,
    MemoryScope,
    Preference,
    Procedure,
    ShortTermTurn,
    TypedMemoryContext,
)
from personas.state import PersonaState


# Helper for creating shared namespaces (now delegated to manager)
def create_shared_namespace(room_id: str) -> MemoryNamespace:
    """Create a memory namespace for shared memory scope."""
    return MemoryNamespace(persona_id="_shared_", room_id=room_id)

# Mark all tests in this file as unit tests.
pytestmark = pytest.mark.unit


# ============================================================================
# Setup Fixtures
# ============================================================================


@pytest.fixture
def mock_memory_store():
    """Create a mock MemoryStore for testing."""
    store = AsyncMock()
    store.append_short_term = AsyncMock()
    store.get_short_term = AsyncMock(return_value=[])
    store.get_long_term_summary = AsyncMock(return_value="")
    store.set_long_term_summary = AsyncMock()
    store.get_state = AsyncMock(return_value={})
    store.set_state = AsyncMock()
    return store


@pytest.fixture
def mock_memory_manager(mock_memory_store):
    """Create a mock MemoryManager for isolated tests."""
    manager = Mock(spec=MemoryManager)
    manager.store = mock_memory_store
    manager.episodic_memory = None

    # Mock async methods
    manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[],
            summary="",
            facts=[],
            persona_state=PersonaState(),
            revision="test_revision_123",
        )
    )
    manager.write_buffer_message = AsyncMock()
    manager.write_fact = AsyncMock()
    manager.write_summary = AsyncMock(return_value="")
    manager.get_persona_state = AsyncMock(return_value=PersonaState())
    manager.set_persona_state = AsyncMock()
    manager._state_namespace = Mock(
        side_effect=lambda ns: MemoryNamespace(
            persona_id=f"persona_state:{ns.persona_id}",
            room_id=ns.room_id,
        )
    )
    manager.get_shared_namespace = Mock(
        side_effect=lambda room_id: MemoryNamespace(
            persona_id="_shared_", room_id=room_id
        )
    )

    # Mock typed record methods
    manager.store_fact_record = AsyncMock()
    manager.get_fact_records = AsyncMock(return_value=[])
    manager.store_preference_record = AsyncMock()
    manager.get_preference_records = AsyncMock(return_value=[])
    manager.store_procedure_record = AsyncMock()
    manager.get_procedure_records = AsyncMock(return_value=[])
    manager.store_action_record = AsyncMock()
    manager.get_action_records = AsyncMock(return_value=[])

    return manager


@pytest.fixture
def coordinator(mock_memory_manager):
    """Create a MemoryCoordinator instance with mock manager."""
    return MemoryCoordinator(manager=mock_memory_manager)


@pytest.fixture
def sample_namespace():
    """Create a sample MemoryNamespace for testing."""
    return MemoryNamespace(persona_id="test_persona", room_id="test_room")


@pytest.fixture
def shared_tier(coordinator):
    """Create a SharedMemoryTier instance."""
    return SharedMemoryTier(coordinator=coordinator, room_id="test_room")


# ============================================================================
# Typed Memory Context Tests
# ============================================================================


async def test_get_typed_context_returns_typed_memory_context(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_typed_context returns a TypedMemoryContext."""
    context = await coordinator.get_typed_context(sample_namespace)

    assert isinstance(context, TypedMemoryContext)
    assert hasattr(context, "recent_turns")
    assert hasattr(context, "facts")
    assert hasattr(context, "preferences")
    assert hasattr(context, "procedures")
    assert hasattr(context, "action_history")
    assert hasattr(context, "episodes")
    assert hasattr(context, "revision")


async def test_get_typed_context_includes_turns(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_typed_context includes recent turns."""
    # Setup mock return with history
    mock_memory_manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[
                {
                    "turn_id": "turn_1",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "role": "user",
                    "content": "Hello",
                    "session_id": "session_123",
                    "metadata": {},
                },
                {
                    "turn_id": "turn_2",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "role": "assistant",
                    "content": "Hi there!",
                    "session_id": "session_123",
                    "metadata": {},
                },
            ],
            summary="",
            facts=[],
            persona_state=PersonaState(),
            revision="rev_123",
        )
    )

    context = await coordinator.get_typed_context(sample_namespace)

    assert len(context.recent_turns) == 2
    assert all(isinstance(turn, ShortTermTurn) for turn in context.recent_turns)
    assert context.recent_turns[0].role == "user"
    assert context.recent_turns[1].role == "assistant"


async def test_get_typed_context_includes_facts(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_typed_context includes facts from manager's typed storage."""
    from datetime import datetime, timezone
    mock_memory_manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[],
            summary="",
            facts=[],
            persona_state=PersonaState(),
            revision="rev_456",
        )
    )
    mock_memory_manager.get_fact_records = AsyncMock(
        return_value=[
            Fact(
                fact_id="f1",
                content="User likes Python",
                source="test",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            ),
            Fact(
                fact_id="f2",
                content="User prefers dark mode",
                source="test",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )

    context = await coordinator.get_typed_context(sample_namespace)

    assert len(context.facts) == 2
    assert all(isinstance(fact, Fact) for fact in context.facts)
    assert context.facts[0].content == "User likes Python"
    assert context.facts[1].content == "User prefers dark mode"


async def test_get_typed_context_merges_shared_records(
    coordinator, mock_memory_manager, sample_namespace
):
    """Persona context should include room-level shared typed memory."""
    shared_namespace = MemoryNamespace(persona_id="_shared_", room_id="test_room")
    mock_memory_manager.get_shared_namespace = Mock(return_value=shared_namespace)

    async def _get_fact_records(namespace, **_kwargs):
        if namespace.persona_id == "_shared_":
            return [
                Fact(
                    fact_id="shared_1",
                    content="Shared room fact",
                    source="test",
                    persona_id=namespace.persona_id,
                    scope=MemoryScope.SHARED.value,
                    created_at=datetime.now(timezone.utc),
                )
            ]
        return [
            Fact(
                fact_id="persona_1",
                content="Persona fact",
                source="test",
                persona_id=namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            )
        ]

    mock_memory_manager.get_fact_records = AsyncMock(side_effect=_get_fact_records)
    mock_memory_manager.get_preference_records = AsyncMock(return_value=[])
    mock_memory_manager.get_procedure_records = AsyncMock(return_value=[])
    mock_memory_manager.get_action_records = AsyncMock(return_value=[])

    context = await coordinator.get_typed_context(sample_namespace)

    assert [fact.content for fact in context.facts] == [
        "Persona fact",
        "Shared room fact",
    ]


async def test_get_typed_context_preserves_legacy_bundle_facts(
    coordinator, mock_memory_manager, sample_namespace
):
    """Legacy raw facts should remain visible in typed context."""
    mock_memory_manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[],
            summary="",
            facts=["Legacy fact from prior storage"],
            persona_state=PersonaState(),
            revision="legacy_rev",
        )
    )
    mock_memory_manager.get_fact_records = AsyncMock(return_value=[])
    mock_memory_manager.get_preference_records = AsyncMock(return_value=[])
    mock_memory_manager.get_procedure_records = AsyncMock(return_value=[])
    mock_memory_manager.get_action_records = AsyncMock(return_value=[])

    context = await coordinator.get_typed_context(sample_namespace)

    assert [fact.content for fact in context.facts] == [
        "Legacy fact from prior storage"
    ]
    assert context.facts[0].source == "legacy_memory_manager"


async def test_get_typed_context_includes_episodes(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_typed_context includes episodes from episodic memory."""
    # Create mock episodic memory
    mock_episodic = AsyncMock()
    mock_episodic.get_episodes = AsyncMock(
        return_value=[
            Episode(
                episode_id="ep_1",
                context="Test context",
                actions=[{"tool": "test", "args": {}}],
                outcome="success",
            )
        ]
    )
    mock_memory_manager.episodic_memory = mock_episodic
    mock_memory_manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[],
            summary="",
            facts=[],
            persona_state=PersonaState(),
            revision="rev_789",
        )
    )

    context = await coordinator.get_typed_context(sample_namespace)

    assert len(context.episodes) == 1
    assert isinstance(context.episodes[0], Episode)
    assert context.episodes[0].episode_id == "ep_1"


# ============================================================================
# ShortTermTurn Tests
# ============================================================================


async def test_record_turn_creates_turn_with_metadata(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that record_turn creates a turn with proper metadata."""
    turn = await coordinator.record_turn(
        namespace=sample_namespace,
        role="user",
        content="Hello, world!",
        session_id="session_123",
        metadata={"source": "discord", "guild_id": "123"},
    )

    assert isinstance(turn, ShortTermTurn)
    assert turn.role == "user"
    assert turn.content == "Hello, world!"
    assert turn.session_id == "session_123"
    assert turn.metadata == {"source": "discord", "guild_id": "123"}
    assert turn.persona_id == sample_namespace.persona_id
    assert turn.turn_id  # Should have auto-generated ID
    assert isinstance(turn.timestamp, datetime)


async def test_record_turn_stores_in_buffer(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that record_turn stores the turn in the buffer."""
    turn = await coordinator.record_turn(
        namespace=sample_namespace,
        role="assistant",
        content="Test response",
        session_id="session_456",
    )

    # Verify write_buffer_message was called
    mock_memory_manager.write_buffer_message.assert_called_once()
    call_args = mock_memory_manager.write_buffer_message.call_args
    assert call_args[0][0] == sample_namespace
    stored_message = call_args[0][1]
    assert stored_message["turn_id"] == turn.turn_id
    assert stored_message["role"] == "assistant"
    assert stored_message["content"] == "Test response"


async def test_record_turn_preserves_session_id(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that record_turn preserves the session ID."""
    turn = await coordinator.record_turn(
        namespace=sample_namespace,
        role="system",
        content="System message",
        session_id="unique_session_789",
    )

    assert turn.session_id == "unique_session_789"


# ============================================================================
# Fact Tests
# ============================================================================


async def test_store_fact_creates_fact(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that store_fact creates a Fact object."""
    fact = await coordinator.store_fact(
        namespace=sample_namespace,
        content="Python is a programming language",
        source="user_conversation",
        confidence=0.95,
    )

    assert isinstance(fact, Fact)
    assert fact.content == "Python is a programming language"
    assert fact.source == "user_conversation"
    assert fact.confidence == 0.95
    assert fact.persona_id == sample_namespace.persona_id
    assert fact.scope == MemoryScope.PERSONA.value
    assert fact.fact_id
    assert isinstance(fact.created_at, datetime)


async def test_store_fact_with_persona_scope(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that store_fact can create a persona-scoped fact."""
    fact = await coordinator.store_fact(
        namespace=sample_namespace,
        content="Persona-specific fact",
        source="system",
        scope=MemoryScope.PERSONA,
    )

    assert fact.scope == MemoryScope.PERSONA.value
    mock_memory_manager.write_fact.assert_called_once()
    mock_memory_manager.store_fact_record.assert_called_once()


async def test_store_fact_with_shared_scope(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that store_fact can create a shared-scoped fact."""
    fact = await coordinator.store_fact(
        namespace=sample_namespace,
        content="Shared fact",
        source="user_conversation",
        scope=MemoryScope.SHARED,
    )

    assert fact.scope == MemoryScope.SHARED.value
    mock_memory_manager.store_fact_record.assert_called_once()


async def test_get_facts_delegates_to_manager(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_facts delegates to manager's get_fact_records."""
    from datetime import datetime, timezone
    mock_memory_manager.get_fact_records = AsyncMock(
        return_value=[
            Fact(
                fact_id="f1",
                content="Fact 1",
                source="test",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )

    facts = await coordinator.get_facts(
        namespace=sample_namespace,
        scope=MemoryScope.PERSONA,
    )

    mock_memory_manager.get_fact_records.assert_called_once_with(
        sample_namespace, scope=MemoryScope.PERSONA.value, limit=50
    )
    assert all(f.scope == MemoryScope.PERSONA.value for f in facts)


async def test_get_facts_filters_by_scope_shared(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_facts can filter by SHARED scope."""
    from datetime import datetime, timezone
    mock_memory_manager.get_fact_records = AsyncMock(
        return_value=[
            Fact(
                fact_id="f1",
                content="Shared fact 1",
                source="test",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.SHARED.value,
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )

    facts = await coordinator.get_facts(
        namespace=sample_namespace,
        scope=MemoryScope.SHARED,
    )

    mock_memory_manager.get_fact_records.assert_called_once_with(
        sample_namespace, scope=MemoryScope.SHARED.value, limit=50
    )
    assert all(f.scope == MemoryScope.SHARED.value for f in facts)


async def test_get_facts_returns_all_when_scope_none(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_facts returns all facts when scope is None."""
    from datetime import datetime, timezone
    mock_memory_manager.get_fact_records = AsyncMock(
        return_value=[
            Fact(
                fact_id=f"f{i}",
                content=f"Fact {i}",
                source="test",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]
    )

    facts = await coordinator.get_facts(
        namespace=sample_namespace,
        scope=None,
    )

    mock_memory_manager.get_fact_records.assert_called_once_with(
        sample_namespace, scope=None, limit=50
    )
    assert len(facts) == 3


# ============================================================================
# Preference Tests
# ============================================================================


async def test_store_preference_creates_preference(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that store_preference creates a Preference object."""
    preference = await coordinator.store_preference(
        namespace=sample_namespace,
        key="communication_style",
        value="casual",
        user_id="user_123",
        category="style",
    )

    assert isinstance(preference, Preference)
    assert preference.key == "communication_style"
    assert preference.value == "casual"
    assert preference.user_id == "user_123"
    assert preference.category == "style"
    assert preference.persona_id == sample_namespace.persona_id
    assert preference.scope == MemoryScope.PERSONA.value
    assert preference.preference_id
    assert isinstance(preference.updated_at, datetime)
    mock_memory_manager.store_preference_record.assert_called_once()


async def test_store_preference_with_scope(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that store_preference respects scope parameter."""
    preference = await coordinator.store_preference(
        namespace=sample_namespace,
        key="shared_setting",
        value=True,
        user_id="user_456",
        scope=MemoryScope.SHARED,
    )

    assert preference.scope == MemoryScope.SHARED.value
    mock_memory_manager.store_preference_record.assert_called_once()


async def test_get_preferences_delegates_to_manager(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_preferences delegates to manager's get_preference_records."""
    from datetime import datetime, timezone
    mock_memory_manager.get_preference_records = AsyncMock(
        return_value=[
            Preference(
                preference_id="pref_1",
                key="theme",
                value="dark",
                user_id="user_123",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                category="ui",
                updated_at=datetime.now(timezone.utc),
            ),
        ]
    )

    preferences = await coordinator.get_preferences(
        namespace=sample_namespace,
        user_id="user_123",
    )

    mock_memory_manager.get_preference_records.assert_called_once_with(
        sample_namespace, user_id="user_123", scope=None
    )
    assert len(preferences) == 1
    assert preferences[0].user_id == "user_123"
    assert preferences[0].key == "theme"


async def test_get_preferences_filters_by_scope(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_preferences can filter by scope."""
    from datetime import datetime, timezone
    mock_memory_manager.get_preference_records = AsyncMock(
        return_value=[
            Preference(
                preference_id="pref_2",
                key="shared_pref",
                value="value2",
                user_id="user_1",
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.SHARED.value,
                category="general",
                updated_at=datetime.now(timezone.utc),
            ),
        ]
    )

    shared_prefs = await coordinator.get_preferences(
        namespace=sample_namespace,
        scope=MemoryScope.SHARED,
    )

    mock_memory_manager.get_preference_records.assert_called_once_with(
        sample_namespace, user_id=None, scope=MemoryScope.SHARED.value
    )
    assert len(shared_prefs) == 1
    assert shared_prefs[0].scope == MemoryScope.SHARED.value
    assert shared_prefs[0].key == "shared_pref"


# ============================================================================
# Procedure Tests
# ============================================================================


async def test_store_procedure_creates_procedure(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that store_procedure creates a Procedure object."""
    procedure = await coordinator.store_procedure(
        namespace=sample_namespace,
        name="Greeting Procedure",
        steps=["Acknowledge user", "Ask how to help", "Wait for response"],
        description="Standard greeting workflow",
        scope=MemoryScope.PERSONA,
    )

    assert isinstance(procedure, Procedure)
    assert procedure.name == "Greeting Procedure"
    assert procedure.steps == ["Acknowledge user", "Ask how to help", "Wait for response"]
    assert procedure.description == "Standard greeting workflow"
    assert procedure.scope == MemoryScope.PERSONA.value
    assert procedure.persona_id == sample_namespace.persona_id
    assert procedure.procedure_id
    assert procedure.success_count == 0
    assert isinstance(procedure.created_at, datetime)
    mock_memory_manager.store_procedure_record.assert_called_once()


async def test_get_procedures_delegates_to_manager(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_procedures delegates to manager's get_procedure_records."""
    from datetime import datetime, timezone
    mock_memory_manager.get_procedure_records = AsyncMock(
        return_value=[
            Procedure(
                procedure_id="proc_2",
                name="Shared Procedure",
                description="",
                steps=["step1", "step2"],
                persona_id=sample_namespace.persona_id,
                scope=MemoryScope.SHARED.value,
                success_count=5,
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )

    shared_procs = await coordinator.get_procedures(
        namespace=sample_namespace,
        scope=MemoryScope.SHARED,
    )

    mock_memory_manager.get_procedure_records.assert_called_once_with(
        sample_namespace, scope=MemoryScope.SHARED.value
    )
    assert len(shared_procs) == 1
    assert shared_procs[0].name == "Shared Procedure"
    assert shared_procs[0].scope == MemoryScope.SHARED.value


# ============================================================================
# ActionRecord Tests
# ============================================================================


async def test_record_action_creates_action_record(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that record_action creates an ActionRecord."""
    action = await coordinator.record_action(
        namespace=sample_namespace,
        action_type="tool_call",
        inputs={"query": "test query"},
        output="Tool result",
        outcome="success",
        tool_name="search_tool",
        session_id="session_abc",
    )

    assert isinstance(action, ActionRecord)
    assert action.action_type == "tool_call"
    assert action.inputs == {"query": "test query"}
    assert action.output == "Tool result"
    assert action.outcome == "success"
    assert action.tool_name == "search_tool"
    assert action.session_id == "session_abc"
    assert action.persona_id == sample_namespace.persona_id
    assert action.action_id
    assert isinstance(action.timestamp, datetime)
    mock_memory_manager.store_action_record.assert_called_once()


async def test_record_action_with_outcome(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that record_action records different outcomes correctly."""
    error_action = await coordinator.record_action(
        namespace=sample_namespace,
        action_type="memory_write",
        inputs={"key": "value"},
        output="",
        outcome="error",
        session_id="session_err",
    )

    assert error_action.outcome == "error"
    assert mock_memory_manager.store_action_record.call_count == 1

    pending_action = await coordinator.record_action(
        namespace=sample_namespace,
        action_type="approval_request",
        inputs={},
        output="Waiting for approval",
        outcome="pending",
        session_id="session_pending",
    )

    assert pending_action.outcome == "pending"
    assert mock_memory_manager.store_action_record.call_count == 2


async def test_get_action_history_delegates_to_manager(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_action_history delegates to manager's get_action_records."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    mock_memory_manager.get_action_records = AsyncMock(
        return_value=[
            ActionRecord(
                action_id="action_2",
                action_type="memory_write",
                tool_name=None,
                inputs={"key": "val"},
                output="",
                outcome="success",
                persona_id=sample_namespace.persona_id,
                session_id="session_1",
                timestamp=now,
            ),
            ActionRecord(
                action_id="action_1",
                action_type="tool_call",
                tool_name="tool1",
                inputs={},
                output="result1",
                outcome="success",
                persona_id=sample_namespace.persona_id,
                session_id="session_1",
                timestamp=now,
            ),
        ]
    )

    actions = await coordinator.get_action_history(
        namespace=sample_namespace,
        limit=10,
    )

    mock_memory_manager.get_action_records.assert_called_once_with(
        sample_namespace, limit=10
    )
    assert len(actions) == 2
    assert actions[0].action_id == "action_2"
    assert actions[1].action_id == "action_1"


async def test_get_action_history_respects_limit(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that get_action_history respects the limit parameter."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    mock_memory_manager.get_action_records = AsyncMock(
        return_value=[
            ActionRecord(
                action_id=f"action_{i}",
                action_type="tool_call",
                tool_name=None,
                inputs={},
                output="",
                outcome="success",
                persona_id=sample_namespace.persona_id,
                session_id="session",
                timestamp=now,
            )
            for i in range(3)
        ]
    )

    actions = await coordinator.get_action_history(
        namespace=sample_namespace,
        limit=3,
    )

    mock_memory_manager.get_action_records.assert_called_once_with(
        sample_namespace, limit=3
    )
    assert len(actions) == 3


# ============================================================================
# Shared Memory Tier Tests
# ============================================================================


async def test_shared_tier_has_shared_scope(shared_tier, mock_memory_manager):
    """Test that SharedMemoryTier uses SHARED scope."""
    assert shared_tier.room_id == "test_room"
    ns = shared_tier._namespace()
    mock_memory_manager.get_shared_namespace.assert_called_once_with("test_room")
    assert ns.persona_id == "_shared_"
    assert ns.room_id == "test_room"


async def test_shared_tier_store_and_get_facts(
    coordinator, shared_tier, mock_memory_manager
):
    """Test that SharedMemoryTier can store and retrieve facts."""
    # Setup mock for get_facts
    mock_memory_manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[],
            summary="",
            facts=["Shared fact 1", "Shared fact 2"],
            persona_state=PersonaState(),
            revision="rev_shared",
        )
    )

    # Store a fact through shared tier
    fact = await shared_tier.store_fact(
        content="Room-specific fact",
        source="conversation",
        confidence=0.9,
    )

    assert isinstance(fact, Fact)
    assert fact.content == "Room-specific fact"
    assert fact.scope == MemoryScope.SHARED.value

    # Get facts through shared tier
    facts = await shared_tier.get_facts(limit=10)
    assert all(f.scope == MemoryScope.SHARED.value for f in facts)


async def test_shared_tier_isolated_by_room(coordinator, mock_memory_manager):
    """Test that SharedMemoryTier instances are isolated by room."""
    tier_room_a = SharedMemoryTier(coordinator=coordinator, room_id="room_a")
    tier_room_b = SharedMemoryTier(coordinator=coordinator, room_id="room_b")

    ns_a = tier_room_a._namespace()
    ns_b = tier_room_b._namespace()

    assert ns_a.room_id == "room_a"
    assert ns_b.room_id == "room_b"
    assert ns_a.persona_id == "_shared_"
    assert ns_b.persona_id == "_shared_"
    assert ns_a != ns_b  # Different namespaces due to room_id


# ============================================================================
# Scoping Tests (Critical)
# ============================================================================


async def test_persona_scope_isolated_between_personas(
    coordinator, mock_memory_manager
):
    """Test that persona-scoped memory is isolated between different personas."""
    ns_persona_a = MemoryNamespace(persona_id="persona_a", room_id="room_1")
    ns_persona_b = MemoryNamespace(persona_id="persona_b", room_id="room_1")

    # Store fact for persona A
    await coordinator.store_fact(
        namespace=ns_persona_a,
        content="Persona A's secret",
        source="conversation",
        scope=MemoryScope.PERSONA,
    )

    # Verify different namespaces are used
    assert ns_persona_a.persona_id != ns_persona_b.persona_id
    assert ns_persona_a.room_id == ns_persona_b.room_id

    # The write_fact should be called with different namespaces
    calls = mock_memory_manager.write_fact.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == ns_persona_a


async def test_shared_scope_visible_across_personas(coordinator):
    """Test that shared-scoped memory is accessible across personas."""
    # Both personas in the same room should access shared memory
    shared_ns = create_shared_namespace(room_id="room_1")

    # Shared namespace should have the special _shared_ persona_id
    assert shared_ns.persona_id == "_shared_"
    assert shared_ns.room_id == "room_1"

    # Both personas can access the same shared namespace
    # (though they use different persona namespaces, the shared tier
    # uses the shared namespace)
    shared_tier_a = coordinator.get_shared_tier("room_1")
    shared_tier_b = coordinator.get_shared_tier("room_1")

    assert shared_tier_a.room_id == shared_tier_b.room_id
    assert shared_tier_a._namespace() == shared_tier_b._namespace()


async def test_shared_namespace_uses_shared_prefix():
    """Test that shared namespace uses the correct persona_id prefix."""
    shared_ns = create_shared_namespace(room_id="test_room")
    assert shared_ns.persona_id == "_shared_"
    assert shared_ns.room_id == "test_room"

    persona_ns = create_persona_namespace(
        persona_id="test_persona", room_id="test_room"
    )
    assert persona_ns.persona_id == "test_persona"
    assert persona_ns.room_id == "test_room"

    # They should be different
    assert shared_ns != persona_ns


# ============================================================================
# Backward Compatibility Tests
# ============================================================================


async def test_to_memory_context_bundle_converts_correctly(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that to_memory_context_bundle correctly converts TypedMemoryContext."""
    # Create a typed context with sample data
    now = datetime.now(timezone.utc)
    typed_context = TypedMemoryContext(
        recent_turns=[
            ShortTermTurn(
                turn_id="t1",
                timestamp=now,
                role="user",
                content="Hello",
                persona_id="p1",
                session_id="s1",
            ),
            ShortTermTurn(
                turn_id="t2",
                timestamp=now,
                role="assistant",
                content="Hi!",
                persona_id="p1",
                session_id="s1",
            ),
        ],
        facts=[
            Fact(
                fact_id="f1",
                content="Fact 1",
                source="conv",
                persona_id="p1",
                scope=MemoryScope.PERSONA.value,
                created_at=now,
            )
        ],
        preferences=[],
        procedures=[],
        action_history=[],
        episodes=[
            Episode(
                episode_id="e1",
                context="Test situation",
                actions=[],
                outcome="success",
            )
        ],
        revision="rev_abc",
    )

    bundle = coordinator.to_memory_context_bundle(typed_context)

    assert isinstance(bundle, MemoryContextBundle)
    assert len(bundle.recent_history) == 2
    assert bundle.recent_history[0]["role"] == "user"
    assert bundle.recent_history[0]["content"] == "Hello"
    assert len(bundle.facts) == 1
    assert bundle.facts[0] == "Fact 1"
    assert bundle.revision == "rev_abc"
    assert isinstance(bundle.persona_state, PersonaState)


async def test_legacy_bundle_has_required_fields(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that the legacy bundle has all required fields."""
    typed_context = TypedMemoryContext(
        recent_turns=[],
        facts=[],
        preferences=[],
        procedures=[],
        action_history=[],
        episodes=[],
        revision="test_rev",
    )

    bundle = coordinator.to_memory_context_bundle(typed_context)

    # Required fields from MemoryContextBundle
    assert hasattr(bundle, "recent_history")
    assert hasattr(bundle, "summary")
    assert hasattr(bundle, "facts")
    assert hasattr(bundle, "persona_state")
    assert hasattr(bundle, "revision")

    # Types
    assert isinstance(bundle.recent_history, list)
    assert isinstance(bundle.facts, list)
    assert isinstance(bundle.persona_state, PersonaState)


# ============================================================================
# Integration Tests
# ============================================================================


async def test_full_memory_flow_turns_facts_preferences(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test a full memory flow with turns, facts, and preferences."""
    # Record some turns
    turn1 = await coordinator.record_turn(
        namespace=sample_namespace,
        role="user",
        content="I like Python",
        session_id="session_1",
    )

    turn2 = await coordinator.record_turn(
        namespace=sample_namespace,
        role="assistant",
        content="That's great! Python is a versatile language.",
        session_id="session_1",
    )

    # Store a fact
    fact = await coordinator.store_fact(
        namespace=sample_namespace,
        content="User likes Python programming",
        source="conversation",
        confidence=0.9,
    )

    # Store a preference
    preference = await coordinator.store_preference(
        namespace=sample_namespace,
        key="favorite_language",
        value="Python",
        user_id="user_123",
        category="programming",
    )

    # Verify all operations succeeded
    assert isinstance(turn1, ShortTermTurn)
    assert isinstance(turn2, ShortTermTurn)
    assert isinstance(fact, Fact)
    assert isinstance(preference, Preference)

    # Verify manager methods were called
    assert mock_memory_manager.write_buffer_message.call_count == 2
    mock_memory_manager.write_fact.assert_called_once()
    mock_memory_manager.store_fact_record.assert_called_once()
    mock_memory_manager.store_preference_record.assert_called_once()


async def test_coordinator_uses_real_memory_manager_methods(
    coordinator, mock_memory_manager, sample_namespace
):
    """Test that coordinator properly delegates to MemoryManager methods."""
    # Test write_buffer_message is called for turns
    await coordinator.record_turn(
        namespace=sample_namespace,
        role="user",
        content="Test",
        session_id="s1",
    )
    mock_memory_manager.write_buffer_message.assert_called()

    # Test write_fact is called for facts
    await coordinator.store_fact(
        namespace=sample_namespace,
        content="Test fact",
        source="test",
    )
    mock_memory_manager.write_fact.assert_called()

    # Test load_context is called for get_typed_context
    mock_memory_manager.load_context = AsyncMock(
        return_value=MemoryContextBundle(
            recent_history=[],
            summary="",
            facts=[],
            persona_state=PersonaState(),
            revision="rev",
        )
    )
    await coordinator.get_typed_context(sample_namespace)
    mock_memory_manager.load_context.assert_called()


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_create_persona_namespace():
    """Test create_persona_namespace helper function."""
    ns = create_persona_namespace(persona_id="my_persona", room_id="my_room")
    assert ns.persona_id == "my_persona"
    assert ns.room_id == "my_room"


def test_create_shared_namespace():
    """Test create_shared_namespace helper function."""
    ns = create_shared_namespace(room_id="my_room")
    assert ns.persona_id == "_shared_"
    assert ns.room_id == "my_room"


def test_determine_scope():
    """Test determine_scope helper function."""
    assert determine_scope(is_shared=True) == MemoryScope.SHARED
    assert determine_scope(is_shared=False) == MemoryScope.PERSONA


def test_generate_id():
    """Test _generate_id creates valid IDs."""
    id1 = _generate_id()
    id2 = _generate_id()

    assert isinstance(id1, str)
    assert len(id1) == 16  # uuid4 hex[:16]
    assert id1 != id2  # Should be unique


def test_compute_typed_context_revision():
    """Test _compute_typed_context_revision generates consistent hashes."""
    now = datetime.now(timezone.utc)
    context = TypedMemoryContext(
        recent_turns=[
            ShortTermTurn(
                turn_id="t1",
                timestamp=now,
                role="user",
                content="Hello",
                persona_id="p1",
                session_id="s1",
            )
        ],
        facts=[Fact(
            fact_id="f1",
            content="Fact",
            source="conv",
            persona_id="p1",
            scope=MemoryScope.PERSONA.value,
            created_at=now,
        )],
        preferences=[Preference(
            preference_id="pref1",
            key="key",
            value="val",
            user_id="u1",
            persona_id="p1",
            scope=MemoryScope.PERSONA.value,
            category="general",
            updated_at=now,
        )],
        procedures=[Procedure(
            procedure_id="proc1",
            name="Proc",
            description="",
            steps=["step1"],
            persona_id="p1",
            scope=MemoryScope.PERSONA.value,
        )],
        action_history=[ActionRecord(
            action_id="a1",
            action_type="tool",
            tool_name=None,
            inputs={},
            output="",
            outcome="success",
            persona_id="p1",
            session_id="s1",
            timestamp=now,
        )],
        episodes=[],
        revision="",
    )

    revision1 = _compute_typed_context_revision(context)
    revision2 = _compute_typed_context_revision(context)

    assert isinstance(revision1, str)
    assert len(revision1) == 64  # SHA256 hex digest
    assert revision1 == revision2  # Should be deterministic

    # Modify context and verify revision changes
    context.facts[0].content = "Modified fact"
    revision3 = _compute_typed_context_revision(context)
    assert revision3 != revision1

async def test_typed_fact_storage_retains_recent_records_only(tmp_path):
    """Typed fact storage should retain only the bounded recent window."""
    store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")
    manager = MemoryManager(store=store, summary_engine=DeterministicSummary())
    namespace = MemoryNamespace(persona_id="persona_a", room_id="room_1")

    for index in range(105):
        await manager.store_fact_record(
            namespace,
            Fact(
                fact_id=f"fact_{index}",
                content=f"Fact {index}",
                source="test",
                persona_id=namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            ),
        )

    facts = await manager.get_fact_records(namespace, limit=200)

    assert len(facts) == 100
    assert facts[0].fact_id == "fact_5"
    assert facts[-1].fact_id == "fact_104"


for _name, _obj in list(globals().items()):
    if _name.startswith("test_") and asyncio.iscoroutinefunction(_obj):
        globals()[_name] = pytest.mark.asyncio(_obj)
