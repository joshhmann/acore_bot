#!/usr/bin/env python3
"""Simple test runner for Phase 4 optimizations (no pytest required)."""

import asyncio
import tempfile
import sys
from pathlib import Path
from collections import OrderedDict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ollama import RequestDeduplicator
from utils.helpers import ChatHistoryManager
from services.metrics import MetricsService


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name):
        """Decorator to register a test."""

        def decorator(func):
            self.tests.append((name, func))
            return func

        return decorator

    async def run_all(self):
        """Run all registered tests."""
        print("=" * 70)
        print("PHASE 4 OPTIMIZATIONS TEST SUITE")
        print("=" * 70)
        print()

        for name, func in self.tests:
            try:
                print(f"Testing: {name}...", end=" ")
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    func()
                print("✅ PASSED")
                self.passed += 1
            except AssertionError as e:
                print(f"❌ FAILED: {e}")
                self.failed += 1
            except Exception as e:
                print(f"❌ ERROR: {e}")
                self.failed += 1

        print()
        print("=" * 70)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print("=" * 70)

        return self.failed == 0


# Initialize test runner
runner = TestRunner()


# ============================================================================
# REQUEST DEDUPLICATION TESTS
# ============================================================================


@runner.test("RequestDeduplicator: Hash is deterministic")
def test_hash_deterministic():
    dedup = RequestDeduplicator()
    messages = [{"role": "user", "content": "Hello"}]

    hash1 = dedup._hash_request(messages, "llama3.2", 0.7)
    hash2 = dedup._hash_request(messages, "llama3.2", 0.7)

    assert hash1 == hash2, "Hashes should be identical"
    assert len(hash1) == 64, "SHA-256 should produce 64 hex chars"


@runner.test("RequestDeduplicator: Different messages produce different hashes")
def test_hash_different():
    dedup = RequestDeduplicator()

    hash1 = dedup._hash_request([{"role": "user", "content": "Hello"}], "llama3.2", 0.7)
    hash2 = dedup._hash_request(
        [{"role": "user", "content": "Goodbye"}], "llama3.2", 0.7
    )

    assert hash1 != hash2, "Different messages should produce different hashes"


@runner.test("RequestDeduplicator: Single request executes")
async def test_single_request():
    dedup = RequestDeduplicator()
    call_count = [0]

    async def test_coro():
        call_count[0] += 1
        await asyncio.sleep(0.01)
        return "result"

    result = await dedup.deduplicate("key1", test_coro())

    assert result == "result", "Should return result"
    assert call_count[0] == 1, "Should call function once"


@runner.test("RequestDeduplicator: Concurrent requests are deduplicated")
async def test_concurrent_dedup():
    dedup = RequestDeduplicator()
    call_count = [0]

    async def slow_request():
        call_count[0] += 1
        await asyncio.sleep(0.1)
        return f"result_{call_count[0]}"

    # Launch 5 identical concurrent requests
    tasks = [dedup.deduplicate("same_key", slow_request()) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    assert all(r == results[0] for r in results), "All results should be identical"
    assert call_count[0] == 1, (
        f"Should only call function once, called {call_count[0]} times"
    )


@runner.test("RequestDeduplicator: Different keys execute separately")
async def test_different_keys():
    dedup = RequestDeduplicator()
    call_count = [0]

    async def test_coro():
        call_count[0] += 1
        await asyncio.sleep(0.01)
        return call_count[0]

    result1 = await dedup.deduplicate("key1", test_coro())
    result2 = await dedup.deduplicate("key2", test_coro())

    assert result1 != result2, "Different keys should produce different results"
    assert call_count[0] == 2, "Should call function twice for different keys"


@runner.test("RequestDeduplicator: Stats are returned")
def test_dedup_stats():
    dedup = RequestDeduplicator()
    stats = dedup.get_stats()

    assert "pending_requests" in stats
    assert "active_deduplication" in stats
    assert isinstance(stats["pending_requests"], int)


# ============================================================================
# CHAT HISTORY MANAGER TESTS
# ============================================================================


@runner.test("ChatHistoryManager: Initializes with OrderedDict")
def test_manager_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(history_dir=Path(tmpdir), cache_size=5)
        assert isinstance(manager._cache, OrderedDict), "Cache should be OrderedDict"


@runner.test("ChatHistoryManager: Load empty history")
async def test_load_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(history_dir=Path(tmpdir), cache_size=5)
        history = await manager.load_history(12345)

        assert history == [], "Empty channel should return empty list"
        assert 12345 in manager._cache, "Channel should be cached"


@runner.test("ChatHistoryManager: Add and load message")
async def test_add_load_message():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(history_dir=Path(tmpdir), cache_size=5)

        await manager.add_message(
            channel_id=12345, role="user", content="Hello", username="TestUser"
        )

        history = await manager.load_history(12345)

        assert len(history) == 1, "Should have 1 message"
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"


@runner.test("ChatHistoryManager: LRU eviction works")
async def test_lru_eviction():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(history_dir=Path(tmpdir), cache_size=5)

        # Add 7 channels (exceeds cache size of 5)
        for i in range(7):
            await manager.add_message(
                channel_id=1000 + i, role="user", content=f"Message {i}"
            )

        cache_size = len(manager._cache)
        assert cache_size <= 5, f"Cache should not exceed 5, has {cache_size}"
        assert 1000 not in manager._cache, "Oldest channel should be evicted"
        assert 1006 in manager._cache, "Newest channel should be in cache"


@runner.test("ChatHistoryManager: Access updates LRU order")
async def test_lru_access_order():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(history_dir=Path(tmpdir), cache_size=5)

        # Add 3 channels
        for i in range(3):
            await manager.add_message(
                channel_id=2000 + i, role="user", content=f"Msg {i}"
            )

        # Access first channel (should become most recent)
        await manager.load_history(2000)

        # Add 3 more (total 6, exceeds cache size 5)
        for i in range(3, 6):
            await manager.add_message(
                channel_id=2000 + i, role="user", content=f"Msg {i}"
            )

        # Channel 2000 should still be cached (recently accessed)
        assert 2000 in manager._cache, (
            "Recently accessed channel should remain in cache"
        )


@runner.test("ChatHistoryManager: Clear history works")
async def test_clear_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(history_dir=Path(tmpdir), cache_size=5)

        await manager.add_message(channel_id=3000, role="user", content="Test")
        assert 3000 in manager._cache

        await manager.clear_history(3000)
        assert 3000 not in manager._cache, "Cleared channel should not be in cache"


@runner.test("ChatHistoryManager: Respects max_messages limit")
async def test_max_messages():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ChatHistoryManager(
            history_dir=Path(tmpdir), max_messages=20, cache_size=5
        )

        # Add 25 messages (exceeds max of 20)
        for i in range(25):
            await manager.add_message(
                channel_id=4000, role="user", content=f"Message {i}"
            )

        history = await manager.load_history(4000)

        assert len(history) == 20, f"Should only keep 20 messages, has {len(history)}"
        assert history[0]["content"] == "Message 5", "Should trim oldest messages"


# ============================================================================
# METRICS BATCH LOGGING TESTS
# ============================================================================


@runner.test("MetricsService: Batch logging initializes")
def test_metrics_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = MetricsService(data_dir=Path(tmpdir))

        assert hasattr(metrics, "pending_events")
        assert hasattr(metrics, "batch_size")
        assert metrics.batch_size == 50


@runner.test("MetricsService: Log event adds to buffer")
def test_log_event():
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = MetricsService(data_dir=Path(tmpdir))
        metrics.log_event("test_event", {"key": "value"})

        assert len(metrics.pending_events) == 1
        assert metrics.pending_events[0]["type"] == "test_event"
        assert metrics.pending_events[0]["data"]["key"] == "value"


@runner.test("MetricsService: Manual flush works")
async def test_manual_flush():
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = MetricsService(data_dir=Path(tmpdir))

        # Add events
        for i in range(5):
            metrics.log_event(f"event_{i}", {"index": i})

        assert len(metrics.pending_events) == 5

        # Flush
        await metrics._flush_events()

        assert len(metrics.pending_events) == 0, "Buffer should be cleared"

        # Check file was created
        event_files = list(metrics.metrics_dir.glob("events_*.jsonl"))
        assert len(event_files) > 0, "Event file should be created"


@runner.test("MetricsService: Batch stats are returned")
def test_batch_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = MetricsService(data_dir=Path(tmpdir))
        metrics.log_event("test", {})

        stats = metrics.get_batch_stats()

        assert "pending_events" in stats
        assert "batch_size" in stats
        assert stats["pending_events"] == 1


@runner.test("MetricsService: Graceful shutdown flushes events")
async def test_graceful_shutdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = MetricsService(data_dir=Path(tmpdir))

        # Add events
        for i in range(5):
            metrics.log_event("shutdown_test", {"i": i})

        assert len(metrics.pending_events) == 5

        # Graceful shutdown
        await metrics.stop_batch_flush_task()

        assert len(metrics.pending_events) == 0, "All events should be flushed"


# ============================================================================
# INTEGRATION TEST
# ============================================================================


@runner.test("Integration: All components work together")
async def test_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Initialize all components
        dedup = RequestDeduplicator()
        manager = ChatHistoryManager(history_dir=tmpdir / "history", cache_size=10)
        metrics = MetricsService(data_dir=tmpdir / "metrics")

        call_count = [0]

        async def mock_llm():
            call_count[0] += 1
            await asyncio.sleep(0.05)
            return f"Response {call_count[0]}"

        # 1. Deduplicate requests
        tasks = [dedup.deduplicate("q1", mock_llm()) for _ in range(3)]
        results = await asyncio.gather(*tasks)

        assert call_count[0] == 1, "Should deduplicate LLM calls"

        # 2. Store in history
        await manager.add_message(12345, "user", "Hello")
        await manager.add_message(12345, "assistant", results[0])

        history = await manager.load_history(12345)
        assert len(history) == 2, "Should store conversation"

        # 3. Log metrics
        metrics.log_event("llm_request", {"dedup": True})

        batch_stats = metrics.get_batch_stats()
        assert batch_stats["pending_events"] == 1, "Should buffer event"

        print(" [Integration successful]", end="")


# ============================================================================
# MAIN
# ============================================================================


async def main():
    """Run all tests."""
    success = await runner.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
