from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.runtime import GestaltRuntime, RuntimeSessionState

pytestmark = pytest.mark.unit


class FakeRouter:
    default_persona_id = "default"

    def select_persona(self, event: Any, personas: Any) -> Any:
        class FakePersona:
            persona_id = "test"
            metadata = {}

        return FakePersona()


class FakePersonaEngine:
    async def build_system_prompt(self, **kwargs: Any) -> str:
        return "system prompt"

    async def update_state(self, **kwargs: Any) -> None:
        pass


class FakeProviderRouter:
    providers = {}
    default_provider_name = "test"

    def resolve_provider_name(self, persona_id: str, mode: str) -> str:
        return "test"


class FakeToolRunner:
    class FakeRegistry:
        def schemas(self, allowlist: Any = None) -> list[dict]:
            return []

        def definitions(self) -> list[Any]:
            return []

    registry = FakeRegistry()

    async def execute_with_trace(self, **kwargs: Any) -> tuple[list[Any], list[dict]]:
        return [], []


class FakeMemoryManager:
    async def load_context(self, **kwargs: Any) -> tuple[list[dict], str]:
        return [], ""

    async def write_buffer_message(self, *args: Any) -> None:
        pass

    async def write_summary(self, **kwargs: Any) -> None:
        pass

    async def write_fact(self, *args: Any) -> None:
        pass


class FakeRAGStore:
    async def search(self, **kwargs: Any) -> list[Any]:
        return []


class FakeSummaryEngine:
    pass


class FakePersonaCatalog:
    def by_id(self, persona_id: str) -> Any:
        class FakePersona:
            persona_id = persona_id or "default"
            metadata = {}

        return FakePersona()


class FakeToolPolicy:
    max_tool_calls_per_turn = 10
    network_enabled = True
    dangerous_enabled = False

    def allowed_tools(self, **kwargs: Any) -> list[str]:
        return []

    def is_tool_allowed(self, name: str, allowed: list[str]) -> bool:
        return True

    tool_risk_tiers = {}


def _create_test_runtime() -> GestaltRuntime:
    """Create a test runtime with all required dependencies."""
    return GestaltRuntime(
        router=FakeRouter(),
        persona_engine=FakePersonaEngine(),
        provider_router=FakeProviderRouter(),
        tool_runner=FakeToolRunner(),
        memory_manager=FakeMemoryManager(),
        summary_engine=FakeSummaryEngine(),
        rag_store=FakeRAGStore(),
        personas=FakePersonaCatalog(),
        tool_policy=FakeToolPolicy(),
    )


@pytest.mark.asyncio
async def test_tick_without_scheduler() -> None:
    """Test that tick() works without a scheduler attached."""
    runtime = _create_test_runtime()

    # Tick should work without scheduler
    result = await runtime.tick()

    assert result["scheduler_present"] is False
    assert result["scheduler_enabled"] is False
    assert result["work_done"] is False
    assert result["error"] is None


@pytest.mark.asyncio
async def test_tick_with_scheduler_but_disabled() -> None:
    """Test that tick() respects opt-in requirement."""
    runtime = _create_test_runtime()

    # Create a mock scheduler
    mock_scheduler = MagicMock()
    mock_scheduler.tick = AsyncMock(return_value=False)
    runtime.scheduler = mock_scheduler

    # Tick should not call scheduler without ENABLE_GOAL_SCHEDULING
    result = await runtime.tick()

    assert result["scheduler_present"] is True
    assert result["scheduler_enabled"] is False
    assert result["work_done"] is False
    mock_scheduler.tick.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_with_scheduler_enabled_via_env() -> None:
    """Test that tick() calls scheduler when enabled via env var."""
    runtime = _create_test_runtime()

    # Create a mock scheduler
    mock_scheduler = MagicMock()
    mock_scheduler.tick = AsyncMock(return_value=True)
    runtime.scheduler = mock_scheduler

    with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": "true"}):
        result = await runtime.tick()

    assert result["scheduler_present"] is True
    assert result["scheduler_enabled"] is True
    assert result["work_done"] is True
    mock_scheduler.tick.assert_awaited_once()


@pytest.mark.asyncio
async def test_tick_with_scheduler_various_env_values() -> None:
    """Test that various env values enable/disable scheduling."""
    runtime = _create_test_runtime()
    runtime.scheduler = MagicMock()
    runtime.scheduler.tick = AsyncMock(return_value=False)

    # Test different truthy values
    for value in ["true", "1", "yes", "TRUE", "True"]:
        runtime._goal_scheduling_enabled = False  # Reset
        with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": value}):
            result = await runtime.tick()
        assert result["scheduler_enabled"] is True, f"Failed for value: {value}"

    # Test falsy values
    for value in ["false", "0", "no", "", "FALSE"]:
        runtime._goal_scheduling_enabled = False  # Reset
        with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": value}):
            result = await runtime.tick()
        assert result["scheduler_enabled"] is False, f"Failed for value: {value}"


@pytest.mark.asyncio
async def test_tick_scheduler_error_handling() -> None:
    """Test that tick() handles scheduler errors gracefully."""
    runtime = _create_test_runtime()

    # Create a mock scheduler that raises an exception
    mock_scheduler = MagicMock()
    mock_scheduler.tick = AsyncMock(side_effect=RuntimeError("Scheduler failure"))
    runtime.scheduler = mock_scheduler

    with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": "true"}):
        result = await runtime.tick()

    assert result["scheduler_present"] is True
    assert result["scheduler_enabled"] is True
    assert result["work_done"] is False
    assert result["error"] == "Scheduler failure"


@pytest.mark.asyncio
async def test_tick_once_enabled_stays_enabled() -> None:
    """Test that once scheduling is enabled, it stays enabled."""
    runtime = _create_test_runtime()
    runtime.scheduler = MagicMock()
    runtime.scheduler.tick = AsyncMock(return_value=False)

    # First call enables scheduling
    with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": "true"}):
        await runtime.tick()

    assert runtime._goal_scheduling_enabled is True

    # Second call without env var should still work (cached)
    with patch.dict("os.environ", {}, clear=True):
        result = await runtime.tick()

    assert result["scheduler_enabled"] is True


@pytest.mark.asyncio
async def test_tick_scheduler_work_done_true() -> None:
    """Test that work_done is correctly propagated from scheduler."""
    runtime = _create_test_runtime()

    mock_scheduler = MagicMock()
    mock_scheduler.tick = AsyncMock(return_value=True)
    runtime.scheduler = mock_scheduler

    with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": "true"}):
        result = await runtime.tick()

    assert result["work_done"] is True


@pytest.mark.asyncio
async def test_tick_scheduler_work_done_false() -> None:
    """Test that work_done=False is correctly propagated."""
    runtime = _create_test_runtime()

    mock_scheduler = MagicMock()
    mock_scheduler.tick = AsyncMock(return_value=False)
    runtime.scheduler = mock_scheduler

    with patch.dict("os.environ", {"ENABLE_GOAL_SCHEDULING": "true"}):
        result = await runtime.tick()

    assert result["work_done"] is False


@pytest.mark.asyncio
async def test_tick_backward_compatibility() -> None:
    """Test that tick() doesn't break existing runtime behavior."""
    runtime = _create_test_runtime()

    # Should work without any scheduler configuration
    result = await runtime.tick()

    # Should return consistent structure
    assert "scheduler_enabled" in result
    assert "scheduler_present" in result
    assert "work_done" in result
    assert "error" in result

    # Should not raise any exceptions
    assert result["error"] is None
