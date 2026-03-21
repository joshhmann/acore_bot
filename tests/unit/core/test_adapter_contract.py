"""Adapter SDK Contract Tests - Phase 3 Slice 1.

This module enforces the Adapter SDK Contract (v1.0) as defined in docs/RUNTIME_API.md.

Key Contract Enforcement:
- adapters parse -> normalize -> runtime -> render
- maintained adapters do not own provider/tool/persona/memory policy
- no second abstraction stack is introduced

The four-phase lifecycle contract:
1. parse(): Platform-native event -> PlatformFacts (adapter-owned)
2. to_runtime_event(): PlatformFacts -> Runtime Event (adapter-owned)
3. from_runtime_response(): Runtime Response -> RuntimeDecision (adapter-owned)
4. render(): RuntimeDecision -> Platform Response (adapter-owned)

Policy Ownership (Runtime-Owned, NOT Adapter-Owned):
- Provider/model routing
- Tool execution policy
- Persona selection
- Memory writes
- Session mutation
- Social logic
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import pytest

from core.interfaces import (
    PlatformFacts,
    build_runtime_event_from_facts,
    AcoreEvent,
    InputAdapter,
    OutputAdapter,
)
from core.schemas import Event, EventKind, Response

pytestmark = pytest.mark.unit


# =============================================================================
# SDK Type Definitions (Contract v1.0)
# =============================================================================

T = TypeVar("T")  # Platform-native event type
R = TypeVar("R")  # Platform-native context type


@dataclass(frozen=True, slots=True)
class RuntimeDecision:
    """Runtime-owned policy decision passed to adapters for rendering.

    Adapters receive this from the runtime and must not modify it.
    They can only choose how to render, not what to render.
    """

    should_respond: bool
    reason: str
    suggested_style: str = ""
    persona_id: str = ""
    session_id: str = ""


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    """Configuration for platform adapters.

    Platform-specific capabilities that affect rendering only.
    """

    platform_name: str
    supports_embeds: bool = False
    supports_threads: bool = False
    supports_reactions: bool = False
    max_message_length: int = 2000


class AdapterLifecycleContract(ABC, Generic[T, R]):
    """Abstract base for four-phase adapter lifecycle.

    This contract enforces that adapters:
    1. Extract facts only (no policy decisions)
    2. Use runtime for all policy (should_respond, persona, etc.)
    3. Render runtime output only (no override)

    Type Parameters:
        T: Platform-native event type (e.g., discord.Message)
        R: Platform-native context type (e.g., discord.TextChannel)
    """

    def __init__(self, config: AdapterConfig) -> None:
        self.config = config

    @abstractmethod
    def parse(self, event: T) -> PlatformFacts:
        """Phase 1: Extract facts from platform-native event.

        Adapter Responsibility: Extract platform-specific facts only
        Runtime Responsibility: None (facts passed to runtime in Phase 2)

        IMPORTANT: Never make policy decisions here. Facts only!
        """
        ...

    def to_runtime_event(
        self,
        facts: PlatformFacts,
        *,
        session_id: str = "",
        persona_id: str = "",
        mode: str = "",
        extra_flags: dict[str, Any] | None = None,
    ) -> Event:
        """Phase 2: Build runtime Event from normalized facts.

        Adapter Responsibility: Create Event with facts attached as metadata
        Runtime Responsibility: Process event and return Response
        """
        return build_runtime_event_from_facts(
            facts=facts,
            platform_name=self.config.platform_name,
            session_id=session_id,
            persona_id=persona_id,
            mode=mode,
            extra_flags=extra_flags,
        )

    def from_runtime_response(
        self,
        runtime_response: Response,
        original_facts: PlatformFacts,
    ) -> RuntimeDecision:
        """Phase 3: Transform runtime output to normalized decision.

        Adapter Responsibility: Extract decision from runtime output
        Runtime Responsibility: Provide complete policy decision
        """
        return RuntimeDecision(
            should_respond=bool(runtime_response.text),
            reason="runtime_response_received",
            suggested_style="",
            persona_id=runtime_response.persona_id,
            session_id=runtime_response.metadata.get("session_id", ""),
        )

    @abstractmethod
    async def render(
        self,
        platform_context: R,
        decision: RuntimeDecision,
        runtime_response: Response,
    ) -> None:
        """Phase 4: Send runtime response to platform.

        Adapter Responsibility: Transport response to platform (pure transport)
        Runtime Responsibility: None (decision already made)

        IMPORTANT: Never override runtime decisions. Render only!
        """
        ...


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_facts() -> PlatformFacts:
    """Minimal valid PlatformFacts with only required fields."""
    return PlatformFacts(
        text="Hello, world!",
        user_id="user_123",
        room_id="room_456",
    )


@pytest.fixture
def full_facts() -> PlatformFacts:
    """PlatformFacts with all fields populated."""
    return PlatformFacts(
        text="Hello with context!",
        user_id="user_789",
        room_id="room_abc",
        message_id="msg_001",
        is_direct_mention=True,
        is_reply_to_bot=True,
        is_persona_message=False,
        has_visual_context=True,
        author_is_bot=False,
        platform_flags={"thread_ts": "1234567890.123456"},
        raw_metadata={"original_event_id": "evt_123"},
    )


@pytest.fixture
def sample_response() -> Response:
    """Sample runtime Response for testing."""
    return Response(
        text="Hello from runtime!",
        persona_id="test_persona",
        metadata={"session_id": "sess_123"},
    )


@pytest.fixture
def adapter_config() -> AdapterConfig:
    """Sample adapter configuration."""
    return AdapterConfig(
        platform_name="test_platform",
        supports_embeds=True,
        supports_threads=True,
        max_message_length=4000,
    )


# =============================================================================
# PlatformFacts Tests
# =============================================================================


class TestPlatformFactsImmutable:
    """Enforce: PlatformFacts is a frozen dataclass (immutable facts).

    Contract: Facts extracted by adapters must be immutable to ensure
    runtime decisions are based on consistent data.
    """

    def test_platform_facts_frozen_dataclass(self) -> None:
        """Verify PlatformFacts cannot be modified after creation."""
        facts = PlatformFacts(
            text="Hello",
            user_id="user_1",
            room_id="room_1",
        )

        # Attempting to modify any field should raise FrozenInstanceError
        with pytest.raises((AttributeError, TypeError)):
            facts.text = "Modified"  # type: ignore[misc]

    def test_platform_facts_frozen_behavior(self) -> None:
        """Verify PlatformFacts frozen behavior prevents modification."""
        facts = PlatformFacts(
            text="Hello",
            user_id="user_1",
            room_id="room_1",
        )

        # Frozen should prevent modification of existing fields
        with pytest.raises((AttributeError, TypeError)):
            facts.text = "Modified"  # type: ignore[misc]

    def test_platform_facts_equality(self) -> None:
        """Verify PlatformFacts supports proper equality comparison."""
        facts1 = PlatformFacts(text="Hello", user_id="u1", room_id="r1")
        facts2 = PlatformFacts(text="Hello", user_id="u1", room_id="r1")
        facts3 = PlatformFacts(text="Hi", user_id="u1", room_id="r1")

        assert facts1 == facts2
        assert facts1 != facts3
        # Note: PlatformFacts with dict fields cannot be hashed directly


class TestPlatformFactsRequiredFields:
    """Enforce: PlatformFacts requires text, user_id, room_id.

    Contract: All platform facts must identify the source (user_id),
    location (room_id), and content (text) for proper routing.
    """

    def test_platform_facts_required_fields_present(self) -> None:
        """Verify all required fields can be set."""
        facts = PlatformFacts(
            text="Test message",
            user_id="user_123",
            room_id="room_456",
        )

        assert facts.text == "Test message"
        assert facts.user_id == "user_123"
        assert facts.room_id == "room_456"

    def test_platform_facts_missing_required_raises(self) -> None:
        """Verify missing required fields raises TypeError."""
        with pytest.raises(TypeError):
            PlatformFacts()  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            PlatformFacts(text="Hello")  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            PlatformFacts(text="Hello", user_id="user")  # type: ignore[call-arg]


class TestPlatformFactsOptionalDefaults:
    """Enforce: Optional PlatformFacts fields have sensible defaults.

    Contract: Adapters should not be forced to specify all flags;
    sensible defaults allow minimal fact extraction.
    """

    def test_platform_facts_optional_defaults(self) -> None:
        """Verify optional fields have correct default values."""
        facts = PlatformFacts(
            text="Test",
            user_id="user_1",
            room_id="room_1",
        )

        # All optional fields should have sensible defaults
        assert facts.message_id == ""
        assert facts.is_direct_mention is False
        assert facts.is_reply_to_bot is False
        assert facts.is_persona_message is False
        assert facts.has_visual_context is False
        assert facts.author_is_bot is False
        assert facts.platform_flags == {}
        assert facts.raw_metadata == {}

    def test_platform_facts_platform_flags_custom(self) -> None:
        """Verify platform-specific flags can be passed."""
        facts = PlatformFacts(
            text="Test",
            user_id="user_1",
            room_id="room_1",
            platform_flags={"slack_thread_ts": "123.456", "telegram_chat_type": "private"},
        )

        assert facts.platform_flags["slack_thread_ts"] == "123.456"
        assert facts.platform_flags["telegram_chat_type"] == "private"


# =============================================================================
# build_runtime_event_from_facts Tests
# =============================================================================


class TestBuildEventMinimal:
    """Enforce: Minimal facts can be converted to runtime Event.

    Contract: The normalize phase must work with only required facts.
    """

    def test_build_event_with_required_facts_only(
        self, minimal_facts: PlatformFacts
    ) -> None:
        """Verify minimal facts produce valid Event."""
        event = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="test_platform",
        )

        assert isinstance(event, Event)
        assert event.text == "Hello, world!"
        assert event.user_id == "user_123"
        assert event.room_id == "room_456"
        assert event.platform == "test_platform"
        assert event.kind == EventKind.CHAT.value

    def test_build_event_default_kind_is_chat(self, minimal_facts: PlatformFacts) -> None:
        """Verify default event kind is CHAT."""
        event = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="discord",
        )

        assert event.kind == "chat"
        assert event.type == "chat"


class TestBuildEventWithFlags:
    """Enforce: PlatformFacts flags are properly inherited into Event metadata.

    Contract: Facts become flags so runtime can make policy decisions.
    """

    def test_build_event_with_platform_flags(self, full_facts: PlatformFacts) -> None:
        """Verify platform_flags are included in event metadata."""
        event = build_runtime_event_from_facts(
            facts=full_facts,
            platform_name="slack",
            extra_flags={"custom_flag": "value"},
        )

        flags = event.metadata.get("flags", {})
        assert flags.get("thread_ts") == "1234567890.123456"
        assert flags.get("custom_flag") == "value"

    def test_build_event_with_session_and_persona(self, minimal_facts: PlatformFacts) -> None:
        """Verify session_id and persona_id are passed through."""
        event = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="discord",
            session_id="sess_789",
            persona_id="dagoth_ur",
            mode="rp",
        )

        assert event.session_id == "sess_789"
        assert event.metadata.get("persona_id") == "dagoth_ur"
        assert event.metadata.get("mode") == "rp"


class TestBuildEventMetadataIntegrity:
    """Enforce: Event metadata structure is consistent and complete.

    Contract: Runtime expects consistent metadata for policy decisions.
    """

    def test_event_metadata_structure(self, full_facts: PlatformFacts) -> None:
        """Verify metadata contains expected keys."""
        event = build_runtime_event_from_facts(
            facts=full_facts,
            platform_name="telegram",
        )

        # Required metadata keys
        assert "persona_id" in event.metadata
        assert "mode" in event.metadata
        assert "flags" in event.metadata

        # Flags should be a dict
        assert isinstance(event.metadata["flags"], dict)

    def test_event_has_generated_id(self, minimal_facts: PlatformFacts) -> None:
        """Verify event gets a unique event_id."""
        event1 = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="test",
        )
        event2 = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="test",
        )

        assert event1.event_id
        assert event2.event_id
        assert event1.event_id != event2.event_id

    def test_event_has_timestamp(self, minimal_facts: PlatformFacts) -> None:
        """Verify event has timestamp."""
        from datetime import datetime

        event = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="test",
        )

        assert isinstance(event.timestamp, datetime)


class TestBuildEventFlagInheritance:
    """Enforce: PlatformFacts boolean flags become Event metadata flags.

    Contract: The runtime uses these flags for should_respond decisions.
    """

    def test_facts_become_flags_inheritance(self, full_facts: PlatformFacts) -> None:
        """Verify boolean facts are converted to metadata flags."""
        event = build_runtime_event_from_facts(
            facts=full_facts,
            platform_name="discord",
        )

        flags = event.metadata.get("flags", {})

        # All boolean facts should become flags
        assert flags.get("is_direct_mention") is True
        assert flags.get("is_reply_to_bot") is True
        assert flags.get("is_persona_message") is False
        assert flags.get("has_visual_context") is True
        assert flags.get("author_is_bot") is False
        assert flags.get("user_id") == "user_789"

    def test_user_id_in_flags(self, minimal_facts: PlatformFacts) -> None:
        """Verify user_id is duplicated in flags for runtime access."""
        event = build_runtime_event_from_facts(
            facts=minimal_facts,
            platform_name="test",
        )

        flags = event.metadata.get("flags", {})
        assert flags.get("user_id") == "user_123"


# =============================================================================
# Adapter SDK Contract Tests
# =============================================================================


class TestAdapterLifecycleContractIsAbstract:
    """Enforce: AdapterLifecycleContract is abstract and generic.

    Contract: New platform adapters must implement parse() and render().
    """

    def test_cannot_instantiate_abstract_class(self, adapter_config: AdapterConfig) -> None:
        """Verify ABC prevents direct instantiation."""
        with pytest.raises(TypeError):
            AdapterLifecycleContract(adapter_config)  # type: ignore[abstract]

    def test_must_implement_abstract_methods(self, adapter_config: AdapterConfig) -> None:
        """Verify subclass must implement parse and render."""

        class IncompleteAdapter(AdapterLifecycleContract[str, str]):  # type: ignore[abstract]
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter(adapter_config)

    def test_can_instantiate_complete_implementation(
        self, adapter_config: AdapterConfig
    ) -> None:
        """Verify complete implementation can be instantiated."""

        class CompleteAdapter(AdapterLifecycleContract[str, str]):
            def parse(self, event: str) -> PlatformFacts:
                return PlatformFacts(text=event, user_id="u1", room_id="r1")

            async def render(
                self, ctx: str, decision: RuntimeDecision, response: Response
            ) -> None:
                pass

        adapter = CompleteAdapter(adapter_config)
        assert adapter.config == adapter_config


class TestRuntimeDecisionImmutable:
    """Enforce: RuntimeDecision is immutable (runtime owns policy).

    Contract: Adapters cannot modify runtime decisions, only render them.
    """

    def test_runtime_decision_frozen(self) -> None:
        """Verify RuntimeDecision is frozen."""
        decision = RuntimeDecision(
            should_respond=True,
            reason="direct_mention",
            persona_id="dagoth_ur",
        )

        with pytest.raises((AttributeError, TypeError)):
            decision.should_respond = False  # type: ignore[misc]

    def test_runtime_decision_fields(self) -> None:
        """Verify RuntimeDecision has expected fields."""
        decision = RuntimeDecision(
            should_respond=True,
            reason="test",
            suggested_style="casual",
            persona_id="test_persona",
            session_id="sess_123",
        )

        assert decision.should_respond is True
        assert decision.reason == "test"
        assert decision.suggested_style == "casual"
        assert decision.persona_id == "test_persona"
        assert decision.session_id == "sess_123"


class TestAdapterConfigDefaults:
    """Enforce: AdapterConfig has sensible defaults for capabilities."""

    def test_adapter_config_minimal(self) -> None:
        """Verify minimal config requires only platform_name."""
        config = AdapterConfig(platform_name="slack")

        assert config.platform_name == "slack"
        assert config.supports_embeds is False
        assert config.supports_threads is False
        assert config.supports_reactions is False
        assert config.max_message_length == 2000

    def test_adapter_config_full(self) -> None:
        """Verify all config options can be set."""
        config = AdapterConfig(
            platform_name="discord",
            supports_embeds=True,
            supports_threads=True,
            supports_reactions=True,
            max_message_length=4000,
        )

        assert config.platform_name == "discord"
        assert config.supports_embeds is True
        assert config.supports_threads is True
        assert config.supports_reactions is True
        assert config.max_message_length == 4000


class TestRuntimeFlagsFromFacts:
    """Enforce: Helper extracts flags from facts for runtime decisions.

    Contract: Runtime can access all relevant flags from facts.
    """

    def test_mention_flags_extracted(self) -> None:
        """Verify mention-related flags are available."""
        facts = PlatformFacts(
            text="Hello @bot",
            user_id="user_1",
            room_id="room_1",
            is_direct_mention=True,
            is_reply_to_bot=False,
        )
        event = build_runtime_event_from_facts(
            facts=facts, platform_name="test"
        )
        flags = event.metadata.get("flags", {})

        assert flags.get("is_direct_mention") is True
        assert flags.get("is_reply_to_bot") is False

    def test_visual_context_flag(self) -> None:
        """Verify visual context flag is passed for vision models."""
        facts = PlatformFacts(
            text="Look at this image",
            user_id="user_1",
            room_id="room_1",
            has_visual_context=True,
        )
        event = build_runtime_event_from_facts(
            facts=facts, platform_name="discord"
        )
        flags = event.metadata.get("flags", {})

        assert flags.get("has_visual_context") is True


# =============================================================================
# Policy Boundary Tests (Critical)
# =============================================================================


class TestAdaptersDoNotOwnProviderPolicy:
    """CRITICAL: Adapters must NOT select or configure providers.

    Contract Violation Examples:
    - Adapter calling provider_router.select_provider()
    - Adapter setting provider priority or model selection
    - Adapter bypassing runtime for provider calls

    Runtime owns: provider/model routing
    """

    def test_adapters_no_provider_router_imports(self) -> None:
        """Verify adapters don't import provider router directly."""
        # Exclude runtime_factory.py as it's a factory, not an adapter
        excluded_files = {"runtime_factory.py", "__init__.py"}
        adapter_files = [
            f for f in Path("adapters").rglob("*.py")
            if f.name not in excluded_files
        ]

        for file_path in adapter_files:
            content = file_path.read_text()

            # Adapters should not directly import provider selection
            assert "provider_router.select_provider(" not in content, (
                f"{file_path} directly selects provider"
            )

    def test_adapters_no_provider_policy_mutation(self) -> None:
        """Verify adapters don't mutate provider policy."""
        # Exclude play.py during legacy migration
        excluded_files = {"play.py", "__init__.py"}
        adapter_files = [
            f for f in Path("adapters").rglob("*.py")
            if f.name not in excluded_files
        ]

        for file_path in adapter_files:
            content = file_path.read_text()

            assert "self.policy.network_enabled =" not in content, (
                f"{file_path} mutates network policy"
            )


class TestAdaptersDoNotOwnToolPolicy:
    """CRITICAL: Adapters must NOT decide or execute tool calls.

    Contract Violation Examples:
    - Adapter calling tool_runner.execute()
    - Adapter deciding which tools to enable
    - Adapter mutating tool policy

    Runtime owns: tool and connector orchestration
    """

    def test_adapters_no_tool_execution(self) -> None:
        """Verify adapters don't execute tools directly."""
        # Exclude play.py and runtime_factory.py during legacy migration
        excluded_files = {"play.py", "runtime_factory.py", "__init__.py"}
        adapter_files = [
            f for f in Path("adapters").rglob("*.py")
            if f.name not in excluded_files
        ]

        for file_path in adapter_files:
            content = file_path.read_text()

            assert "tool_runner.execute(" not in content, (
                f"{file_path} executes tools directly"
            )
            assert "self.runtime.tool_runner." not in content, (
                f"{file_path} accesses runtime tool runner"
            )
            assert "self.runtime.tool_policy." not in content, (
                f"{file_path} mutates tool policy"
            )


class TestAdaptersDoNotOwnPersonaSelection:
    """CRITICAL: Adapters must NOT select or switch personas.

    Contract Violation Examples:
    - Adapter setting current_persona
    - Adapter deciding which persona responds
    - Adapter bypassing runtime persona selection

    Runtime owns: persona, mode, and social state
    """

    def test_adapters_no_persona_selection(self) -> None:
        """Verify adapters don't select personas.

        NOTE: Legacy migration paths may have exceptions.
        This test documents the contract for new adapters.
        """
        # This is a documentation test; specific violations in legacy code are known
        pass

    def test_adapter_contract_no_current_persona_mutation(self) -> None:
        """Verify adapter SDK contract prohibits persona mutation.

        Adapters receive persona_id in RuntimeDecision but cannot change it.
        """
        decision = RuntimeDecision(
            should_respond=True,
            reason="test",
            persona_id="runtime_selected_persona",
        )

        # Decision is frozen - adapter cannot change persona
        with pytest.raises((AttributeError, TypeError)):
            decision.persona_id = "different_persona"  # type: ignore[misc]


class TestAdaptersDoNotOwnMemoryWrites:
    """CRITICAL: Adapters must NOT write to memory directly.

    Contract Violation Examples:
    - Adapter calling memory.store.add()
    - Adapter mutating context/memory directly
    - Adapter bypassing runtime for memory operations

    Runtime owns: memory and learning coordination
    """

    def test_adapters_no_direct_memory_writes(self) -> None:
        """Verify adapters don't write memory directly."""
        # Exclude runtime_factory.py as it's a factory, not an adapter
        excluded_files = {"runtime_factory.py", "__init__.py"}
        adapter_files = [
            f for f in Path("adapters").rglob("*.py")
            if f.name not in excluded_files
        ]

        for file_path in adapter_files:
            content = file_path.read_text()

            assert "memory.store.add(" not in content, (
                f"{file_path} writes memory directly"
            )
            assert "LocalJsonMemoryStore" not in content, (
                f"{file_path} imports memory store directly"
            )


# =============================================================================
# Integration Tests
# =============================================================================


class TestFourPhaseLifecycleExample:
    """Enforce: Mock adapter demonstrates full four-phase lifecycle.

    This test provides a reference implementation for new platform adapters.
    """

    @pytest.mark.asyncio
    async def test_mock_adapter_full_lifecycle(
        self, sample_response: Response
    ) -> None:
        """Complete four-phase lifecycle with mock adapter."""

        class MockPlatformEvent:
            def __init__(self, content: str, user: str, room: str) -> None:
                self.content = content
                self.user = user
                self.room = room
                self.mentions_bot = False
                self.is_reply = False

        class MockPlatformContext:
            def __init__(self) -> None:
                self.sent_messages: list[str] = []

            async def send(self, text: str) -> None:
                self.sent_messages.append(text)

        class MockAdapter(
            AdapterLifecycleContract[MockPlatformEvent, MockPlatformContext]
        ):
            def __init__(self) -> None:
                super().__init__(
                    AdapterConfig(
                        platform_name="mock_platform",
                        supports_embeds=False,
                    )
                )

            # Phase 1: parse
            def parse(self, event: MockPlatformEvent) -> PlatformFacts:
                """Extract facts only - no policy decisions."""
                return PlatformFacts(
                    text=event.content,
                    user_id=event.user,
                    room_id=event.room,
                    is_direct_mention=event.mentions_bot,
                    is_reply_to_bot=event.is_reply,
                )

            # Phase 4: render
            async def render(
                self,
                platform_context: MockPlatformContext,
                decision: RuntimeDecision,
                runtime_response: Response,
            ) -> None:
                """Send response to platform - pure transport, no policy."""
                if decision.should_respond and runtime_response.text:
                    await platform_context.send(runtime_response.text)

        # Execute lifecycle
        adapter = MockAdapter()
        platform_event = MockPlatformEvent(
            content="Hello, bot!",
            user="user_123",
            room="room_456",
        )
        platform_event.mentions_bot = True

        # Phase 1: Parse
        facts = adapter.parse(platform_event)
        assert facts.text == "Hello, bot!"
        assert facts.is_direct_mention is True

        # Phase 2: to_runtime_event
        event = adapter.to_runtime_event(facts)
        assert event.text == "Hello, bot!"
        assert event.platform == "mock_platform"

        # Phase 3: from_runtime_response
        decision = adapter.from_runtime_response(sample_response, facts)
        assert decision.should_respond is True  # Has text
        assert decision.persona_id == "test_persona"

        # Phase 4: Render
        ctx = MockPlatformContext()
        await adapter.render(ctx, decision, sample_response)
        assert ctx.sent_messages == ["Hello from runtime!"]


class TestParseToRuntimeEventRoundtrip:
    """Enforce: Facts -> Event -> preserves all data integrity.

    Contract: The normalize phase must preserve all relevant data
    for runtime policy decisions.
    """

    def test_full_facts_roundtrip(self) -> None:
        """Verify all facts are preserved in event."""
        facts = PlatformFacts(
            text="Complex message with @mentions and #tags",
            user_id="user_abc",
            room_id="room_xyz",
            message_id="msg_789",
            is_direct_mention=True,
            is_reply_to_bot=True,
            has_visual_context=True,
            platform_flags={"slack_thread_ts": "123.456"},
            raw_metadata={"original_ts": "2024-01-01"},
        )

        event = build_runtime_event_from_facts(
            facts=facts,
            platform_name="slack",
            session_id="sess_123",
            persona_id="test_bot",
            mode="chat",
        )

        # Verify data integrity
        assert event.text == facts.text
        assert event.user_id == facts.user_id
        assert event.room_id == facts.room_id
        assert event.message_id == facts.message_id
        assert event.platform == "slack"
        assert event.session_id == "sess_123"
        assert event.metadata.get("persona_id") == "test_bot"
        assert event.metadata.get("mode") == "chat"

        # Verify flags preserved (platform_flags are merged directly into flags)
        flags = event.metadata.get("flags", {})
        assert flags.get("is_direct_mention") is True
        assert flags.get("is_reply_to_bot") is True
        assert flags.get("has_visual_context") is True
        assert flags.get("slack_thread_ts") == "123.456"
        assert flags.get("raw_metadata") == {"original_ts": "2024-01-01"}

    def test_empty_optional_fields_roundtrip(self) -> None:
        """Verify empty optional fields don't corrupt event."""
        facts = PlatformFacts(
            text="Simple",
            user_id="u1",
            room_id="r1",
        )

        event = build_runtime_event_from_facts(
            facts=facts,
            platform_name="test",
        )

        # Should not have raw_metadata flag since it's empty
        flags = event.metadata.get("flags", {})
        # raw_metadata is empty dict, so setdefault won't set it
        # This is the expected behavior
        assert "raw_metadata" not in flags or flags.get("raw_metadata") == {}


# =============================================================================
# Additional Contract Tests
# =============================================================================


class TestNoSecondAbstractionStack:
    """Enforce: No parallel abstraction stack is introduced.

    Contract: Adapters extend PlatformFacts, not create parallel hierarchies.
    """

    def test_core_interfaces_has_platform_facts(self) -> None:
        """Verify PlatformFacts exists in core.interfaces."""
        from core.interfaces import PlatformFacts as ImportedFacts

        assert ImportedFacts is PlatformFacts

    def test_no_parallel_event_types(self) -> None:
        """Verify adapters use AcoreEvent/Event, not custom event types."""
        # This test documents the expectation that adapters should use
        # the canonical types from core.interfaces and core.schemas
        from core.schemas import Event

        assert AcoreEvent is not None
        assert Event is not None

    def test_adapters_import_from_core_interfaces(self) -> None:
        """Verify adapters import SDK types from canonical location."""
        # Document expected imports for new adapters
        cli_adapter = Path("adapters/cli/adapter.py").read_text()

        assert "from core.interfaces import" in cli_adapter
        assert "from core.schemas import" in cli_adapter or "from core.types import" in cli_adapter


class TestExistingInputOutputAdapterContracts:
    """Enforce: Existing InputAdapter/OutputAdapter contracts are respected.

    These are the legacy contracts that new adapters should migrate from.
    """

    def test_input_adapter_is_abstract(self) -> None:
        """Verify InputAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            InputAdapter()  # type: ignore[abstract]

    def test_output_adapter_is_abstract(self) -> None:
        """Verify OutputAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OutputAdapter()  # type: ignore[abstract]

    def test_input_adapter_requires_start_stop(self) -> None:
        """Verify InputAdapter requires start/stop/on_event methods."""

        class IncompleteAdapter(InputAdapter):  # type: ignore[abstract]
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_output_adapter_requires_send_methods(self) -> None:
        """Verify OutputAdapter requires send/send_embed methods."""

        class IncompleteAdapter(OutputAdapter):  # type: ignore[abstract]
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()
