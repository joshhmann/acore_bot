from typing import Any

import pytest

from core.persona_engine import PersonaEngine
from core.router import Router
from core.runtime import GestaltRuntime
from core.schemas import Event, TextOutput
from memory.manager import MemoryManager
from memory.local_json import LocalJsonMemoryStore
from memory.rag import RAGStore
from memory.summary import DeterministicSummary
from personas.loader import PersonaCatalog, PersonaDefinition
from providers.base import LLMResponse, LLMStreamChunk, ProviderMessage
from providers.router import ProviderRouter
from tools.policy import ToolPolicy
from tools.registry import ToolRegistry
from tools.runner import ToolRunner


class _FakeProvider:
    async def chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        del tools, stream, kwargs
        last_user = ""
        for message in reversed(messages):
            if message.role == "user":
                last_user = message.content
                break
        return LLMResponse(content=f"echo:{last_user}")

    async def stream_chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        response = await self.chat(messages=messages, tools=tools, stream=True, **kwargs)
        yield LLMStreamChunk(kind="text_delta", text="echo:")
        yield LLMStreamChunk(kind="response", response=response)


def _build_runtime(tmp_path, *, default_persona_id: str = "dagoth_ur") -> GestaltRuntime:
    memory_store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")
    summary_engine = DeterministicSummary()
    memory_manager = MemoryManager(store=memory_store, summary_engine=summary_engine)
    persona_engine = PersonaEngine(memory_manager=memory_manager)
    catalog = PersonaCatalog(
        personas={
            default_persona_id: PersonaDefinition(
                persona_id=default_persona_id,
                display_name=default_persona_id.replace("_", " ").title(),
            ),
        }
    )
    return GestaltRuntime(
        router=Router(default_persona_id=default_persona_id),
        persona_engine=persona_engine,
        provider_router=ProviderRouter(
            default_provider_name="fake",
            providers={"fake": _FakeProvider()},
            persona_provider_map={},
        ),
        tool_runner=ToolRunner(registry=ToolRegistry(), policy=ToolPolicy()),
        memory_manager=memory_manager,
        summary_engine=summary_engine,
        rag_store=RAGStore(),
        personas=catalog,
        tool_policy=ToolPolicy(),
    )


@pytest.mark.unit
def test_router_selects_persona_from_mention():
    router = Router(default_persona_id="dagoth_ur")
    catalog = PersonaCatalog(
        personas={
            "dagoth_ur": PersonaDefinition(
                persona_id="dagoth_ur", display_name="Dagoth Ur"
            ),
            "scav": PersonaDefinition(persona_id="scav", display_name="Scav"),
        }
    )
    event = Event(type="message", text="@scav hi", room_id="room-1")

    selected = router.select_persona(event, catalog)

    assert selected.persona_id == "scav"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_calls_provider_and_returns_response(tmp_path):
    memory_store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")
    summary_engine = DeterministicSummary()
    memory_manager = MemoryManager(store=memory_store, summary_engine=summary_engine)
    persona_engine = PersonaEngine(memory_manager=memory_manager)
    catalog = PersonaCatalog(
        personas={
            "dagoth_ur": PersonaDefinition(
                persona_id="dagoth_ur", display_name="Dagoth Ur"
            ),
        }
    )
    runtime = GestaltRuntime(
        router=Router(default_persona_id="dagoth_ur"),
        persona_engine=persona_engine,
        provider_router=ProviderRouter(
            default_provider_name="fake",
            providers={"fake": _FakeProvider()},
            persona_provider_map={},
        ),
        tool_runner=ToolRunner(registry=ToolRegistry(), policy=ToolPolicy()),
        memory_manager=memory_manager,
        summary_engine=summary_engine,
        rag_store=RAGStore(),
        personas=catalog,
        tool_policy=ToolPolicy(),
    )

    response = await runtime.handle_event(
        Event(
            type="message",
            text="hello runtime",
            user_id="u1",
            room_id="r1",
            platform="cli",
        )
    )

    assert response.text == "echo:hello runtime"
    assert response.persona_id == "dagoth_ur"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_exposes_close_lifecycle(tmp_path):
    runtime = _build_runtime(tmp_path)
    runtime.session_states["cli:r1"] = type(
        "SessionState",
        (),
        {"session_id": "cli:r1"},
    )()

    await runtime.close()

    assert runtime.session_states == {}
    assert runtime.context_cache == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_context_cache_snapshot_and_reset(tmp_path):
    runtime = _build_runtime(tmp_path)

    await runtime.handle_event(
        Event(
            type="message",
            text="hello cache",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "default"},
        )
    )

    snapshot = runtime.get_context_cache_snapshot(
        session_id="cli:r1:u1",
        persona_id="dagoth_ur",
        mode="default",
        platform="cli",
        room_id="r1",
        flags={},
    )
    assert snapshot["entry_count"] >= 1

    cleared = runtime.reset_context_cache(
        session_id="cli:r1:u1",
        persona_id="dagoth_ur",
        mode="default",
        platform="cli",
        room_id="r1",
        flags={},
    )
    assert cleared["cleared"] >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_command_context_returns_structured_snapshot(tmp_path):
    runtime = _build_runtime(tmp_path)

    envelope = await runtime.handle_event_envelope(
        Event(
            type="command",
            kind="command",
            text="/context",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "default"},
        )
    )

    kinds = [getattr(item, "kind", "") for item in envelope.outputs]
    assert "command_context" in kinds


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_context_cache_trace_hit_and_mode_invalidation(tmp_path):
    runtime = _build_runtime(tmp_path)

    first = await runtime.handle_event_envelope(
        Event(
            type="message",
            text="cache probe",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "default"},
        )
    )
    second = await runtime.handle_event_envelope(
        Event(
            type="message",
            text="cache probe",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "default"},
        )
    )
    third = await runtime.handle_event_envelope(
        Event(
            type="message",
            text="cache probe",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "alt_mode"},
        )
    )

    def _cache_hit(envelope: Any) -> bool | None:
        for output in envelope.outputs:
            if (
                hasattr(output, "trace_type")
                and getattr(output, "trace_type", "") == "context_cache"
            ):
                return bool(getattr(output, "data", {}).get("cache_hit"))
        return None

    assert _cache_hit(first) is False
    assert _cache_hit(second) is True
    assert _cache_hit(third) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_status_snapshot_includes_context_cache_metrics(tmp_path):
    runtime = _build_runtime(tmp_path)

    await runtime.handle_event(
        Event(
            type="message",
            text="status cache seed",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "default"},
        )
    )
    await runtime.handle_event(
        Event(
            type="message",
            text="status cache seed",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1:u1",
            metadata={"persona_id": "dagoth_ur", "mode": "default"},
        )
    )

    snapshot = runtime.get_status_snapshot(
        session_id="cli:r1:u1",
        persona_id="dagoth_ur",
        mode="default",
        platform="cli",
        room_id="r1",
        flags={},
    )

    assert "context_cache" in snapshot
    assert snapshot["context_cache"]["entry_count"] >= 1
    assert snapshot["context_cache"]["total_hits"] >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_isolation_by_persona_room(tmp_path):
    store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")

    from memory.base import MemoryNamespace

    ns_one = MemoryNamespace(persona_id="dagoth_ur", room_id="room-a")
    ns_two = MemoryNamespace(persona_id="scav", room_id="room-a")
    ns_three = MemoryNamespace(persona_id="dagoth_ur", room_id="room-b")

    await store.append_short_term(ns_one, {"role": "user", "content": "one"})
    await store.append_short_term(ns_two, {"role": "user", "content": "two"})
    await store.append_short_term(ns_three, {"role": "user", "content": "three"})

    one = await store.get_short_term(ns_one, limit=10)
    two = await store.get_short_term(ns_two, limit=10)
    three = await store.get_short_term(ns_three, limit=10)

    assert [m["content"] for m in one] == ["one"]
    assert [m["content"] for m in two] == ["two"]
    assert [m["content"] for m in three] == ["three"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_isolation_by_persona_and_room(tmp_path):
    store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")

    from memory.base import MemoryNamespace

    ns_a = MemoryNamespace(persona_id="p1", room_id="r1")
    ns_b = MemoryNamespace(persona_id="p1", room_id="r2")
    ns_c = MemoryNamespace(persona_id="p2", room_id="r1")

    await store.append_short_term(ns_a, {"role": "user", "content": "alpha"})
    await store.append_short_term(ns_b, {"role": "user", "content": "beta"})
    await store.append_short_term(ns_c, {"role": "user", "content": "gamma"})

    assert (await store.get_short_term(ns_a))[0]["content"] == "alpha"
    assert (await store.get_short_term(ns_b))[0]["content"] == "beta"
    assert (await store.get_short_term(ns_c))[0]["content"] == "gamma"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persona_state_persists_without_mutating_definition(tmp_path):
    memory_store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")
    memory_manager = MemoryManager(
        store=memory_store, summary_engine=DeterministicSummary()
    )
    persona_engine = PersonaEngine(memory_manager=memory_manager)

    from memory.base import MemoryNamespace

    definition = PersonaDefinition(
        persona_id="dagoth_ur",
        display_name="Dagoth Ur",
        description="Original description",
    )
    original_description = definition.description
    namespace = MemoryNamespace(persona_id="dagoth_ur", room_id="r1")

    await persona_engine.update_state(
        persona=definition,
        namespace=namespace,
        user_text="thanks",
        response_text="Great to see you!",
    )

    state = await memory_manager.get_persona_state(namespace)
    assert state.message_count == 1
    assert state.affinity >= 51
    assert definition.description == original_description


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_presence_snapshot_tracks_response_and_vrm_defaults(tmp_path):
    memory_store = LocalJsonMemoryStore(root_dir=tmp_path / "memory")
    summary_engine = DeterministicSummary()
    memory_manager = MemoryManager(store=memory_store, summary_engine=summary_engine)
    persona_engine = PersonaEngine(memory_manager=memory_manager)
    catalog = PersonaCatalog(
        personas={
            "dagoth_ur": PersonaDefinition(
                persona_id="dagoth_ur", display_name="Dagoth Ur"
            ),
        }
    )
    runtime = GestaltRuntime(
        router=Router(default_persona_id="dagoth_ur"),
        persona_engine=persona_engine,
        provider_router=ProviderRouter(
            default_provider_name="fake",
            providers={"fake": _FakeProvider()},
            persona_provider_map={},
        ),
        tool_runner=ToolRunner(registry=ToolRegistry(), policy=ToolPolicy()),
        memory_manager=memory_manager,
        summary_engine=summary_engine,
        rag_store=RAGStore(),
        personas=catalog,
        tool_policy=ToolPolicy(),
    )

    session = runtime._get_or_create_session(
        Event(
            type="message",
            text="hi",
            user_id="u1",
            room_id="r1",
            platform="web",
            session_id="web:main",
            metadata={"persona_id": "dagoth_ur"},
        )
    )
    runtime._append_session_traces(
        session,
        [TextOutput(text="hello there", persona_id="dagoth_ur")],
    )

    snapshot = runtime.get_presence_snapshot(
        session_id="web:main",
        persona_id="dagoth_ur",
        mode="default",
        platform="web",
        room_id="r1",
        flags={},
    )

    assert snapshot["state"] == "talking"
    assert snapshot["emotion"] == "warm"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_stream_event_emits_text_deltas(tmp_path):
    runtime = _build_runtime(tmp_path)

    items = []
    async for item in runtime.stream_event(
        Event(
            type="message",
            text="hello runtime",
            user_id="u1",
            room_id="r1",
            platform="cli",
            session_id="cli:r1",
        )
    ):
        items.append(item)

    assert any(item.get("type") == "text_delta" for item in items)
    outputs = [item for item in items if item.get("type") == "output"]
    assert outputs
    assert getattr(outputs[0]["output"], "text", "") == "echo:hello runtime"


@pytest.mark.unit
def test_runtime_surface_decision_ignores_configured_users(tmp_path, monkeypatch):
    runtime = _build_runtime(tmp_path)
    monkeypatch.setattr("config.Config.IGNORED_USERS", [321], raising=False)

    decision = runtime.decide_surface_response(
        session_id="discord:123:321",
        persona_id="",
        mode="",
        platform="discord",
        room_id="123",
        user_id="321",
        text="hello there",
        message_id="42",
        flags={"is_direct_mention": True},
    )

    assert decision["should_respond"] is False
    assert decision["reason"] == "ignored_user"


@pytest.mark.unit
def test_runtime_surface_decision_ignores_explicit_ignore_tag(tmp_path):
    runtime = _build_runtime(tmp_path)

    decision = runtime.decide_surface_response(
        session_id="discord:123:555",
        persona_id="",
        mode="",
        platform="discord",
        room_id="123",
        user_id="555",
        text="hello there #ignore",
        message_id="42",
        flags={"is_direct_mention": True},
    )

    assert decision["should_respond"] is False
    assert decision["reason"] == "ignored_tag"


@pytest.mark.unit
def test_runtime_surface_decision_respects_muted_state_until_unmuted(tmp_path):
    runtime = _build_runtime(tmp_path)

    decision = runtime.decide_surface_response(
        session_id="discord:123:555",
        persona_id="",
        mode="",
        platform="discord",
        room_id="123",
        user_id="555",
        text="hello there",
        message_id="42",
        flags={"is_direct_mention": True, "bot_is_muted": True},
    )

    assert decision["should_respond"] is False
    assert decision["reason"] == "muted"


@pytest.mark.unit
def test_runtime_surface_decision_allows_direct_unmute_request_when_muted(tmp_path):
    runtime = _build_runtime(tmp_path)

    decision = runtime.decide_surface_response(
        session_id="discord:123:555",
        persona_id="",
        mode="",
        platform="discord",
        room_id="123",
        user_id="555",
        text="please unmute now",
        message_id="42",
        flags={"is_direct_mention": True, "bot_is_muted": True},
    )

    assert decision["should_respond"] is True
    assert decision["reason"] == "unmute_request"


@pytest.mark.unit
def test_runtime_surface_decision_ignores_non_persona_bot_authors(tmp_path):
    runtime = _build_runtime(tmp_path)

    decision = runtime.decide_surface_response(
        session_id="discord:123:555",
        persona_id="",
        mode="",
        platform="discord",
        room_id="123",
        user_id="555",
        text="@gestalt hello there",
        message_id="42",
        flags={"is_direct_mention": True, "author_is_bot": True},
    )

    assert decision["should_respond"] is False
    assert decision["reason"] == "other_bot"
