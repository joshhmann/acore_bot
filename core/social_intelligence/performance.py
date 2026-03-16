"""Performance optimization for Social Intelligence Layer.

Target: <100ms overhead per message
Optimizations:
- Classifier caching
- Parallel signal extraction
- Async batch writes
- Lazy loading
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections import deque
from typing import Any, Callable, Optional
import hashlib


class PerformanceMonitor:
    """Monitor SIL performance metrics."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._latencies: deque[float] = deque(maxlen=window_size)
        self._component_latencies: dict[str, deque[float]] = {}

    def record(self, latency_ms: float, component: Optional[str] = None) -> None:
        """Record a latency measurement.

        Args:
            latency_ms: Latency in milliseconds
            component: Optional component name
        """
        self._latencies.append(latency_ms)

        if component:
            if component not in self._component_latencies:
                self._component_latencies[component] = deque(maxlen=self.window_size)
            self._component_latencies[component].append(latency_ms)

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        if not self._latencies:
            return {"count": 0}

        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)

        stats = {
            "count": n,
            "mean_ms": sum(sorted_latencies) / n,
            "min_ms": sorted_latencies[0],
            "max_ms": sorted_latencies[-1],
            "p50_ms": sorted_latencies[int(n * 0.5)],
            "p95_ms": sorted_latencies[int(n * 0.95)],
            "p99_ms": sorted_latencies[int(n * 0.99)]
            if n >= 100
            else sorted_latencies[-1],
        }

        # Component breakdown
        if self._component_latencies:
            stats["components"] = {}
            for name, latencies in self._component_latencies.items():
                if latencies:
                    stats["components"][name] = {
                        "mean_ms": sum(latencies) / len(latencies),
                        "count": len(latencies),
                    }

        return stats

    def check_target(self, target_ms: float = 100.0) -> dict[str, Any]:
        """Check if performance meets target.

        Returns:
            Dict with 'meets_target' and statistics
        """
        stats = self.get_stats()

        if stats["count"] == 0:
            return {"meets_target": True, "reason": "no_data"}

        mean_ok = stats["mean_ms"] < target_ms
        p95_ok = stats.get("p95_ms", 0) < target_ms * 2

        return {
            "meets_target": mean_ok and p95_ok,
            "mean_ok": mean_ok,
            "p95_ok": p95_ok,
            "stats": stats,
            "target_ms": target_ms,
        }


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


class CachedClassifier:
    """Classifier with LRU caching for performance.

    Caches classification results to avoid recomputation
    for similar inputs.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 30.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
        self._access_order: deque[str] = deque()

    def _get_key(self, content: str) -> str:
        """Generate cache key from content."""
        # Normalize content for caching
        normalized = content.lower().strip()[:200]  # First 200 chars
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    def get(self, content: str) -> Optional[Any]:
        """Get cached classification result.

        Args:
            content: Message content

        Returns:
            Cached result or None if not found/expired
        """
        key = self._get_key(content)

        if key in self._cache:
            result, timestamp = self._cache[key]

            # Check TTL
            if time.time() - timestamp < self.ttl_seconds:
                # Update access order
                self._access_order.remove(key)
                self._access_order.append(key)
                return result
            else:
                # Expired
                del self._cache[key]

        return None

    def set(self, content: str, result: Any) -> None:
        """Cache classification result.

        Args:
            content: Message content
            result: Classification result
        """
        key = self._get_key(content)

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest = self._access_order.popleft()
            if oldest in self._cache:
                del self._cache[oldest]

        # Store result
        self._cache[key] = (result, time.time())
        self._access_order.append(key)

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._access_order.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hit_rate": self._calculate_hit_rate(),
        }

    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        # Placeholder - would need to track hits/misses
        return 0.0


def timed(component: Optional[str] = None):
    """Decorator to time function execution.

    Args:
        component: Component name for tracking

    Usage:
        @timed("router")
        def select_mode(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000

            monitor = get_monitor()
            monitor.record(elapsed_ms, component)

            return result

        return wrapper

    return decorator


class AsyncBatchWriter:
    """Batches async writes for better performance.

        Groups multiple write operations into single batch
    to reduce I/O overhead.
    """

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval_seconds: float = 5.0,
    ):
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[dict] = []
        self._last_flush = time.time()
        self._lock = asyncio.Lock()

    async def add(self, item: dict[str, Any]) -> None:
        """Add item to batch.

        Args:
            item: Item to write
        """
        async with self._lock:
            self._buffer.append(item)

            # Flush if batch is full or interval passed
            should_flush = (
                len(self._buffer) >= self.batch_size
                or time.time() - self._last_flush >= self.flush_interval
            )

            if should_flush:
                await self._flush()

    async def _flush(self) -> None:
        """Flush buffer to storage."""
        if not self._buffer:
            return

        # Copy and clear buffer
        batch = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = time.time()

        # Write batch (implementation depends on storage)
        # This is a placeholder - actual implementation would
        # write to SocialMemoryStore or other storage
        await self._write_batch(batch)

    async def _write_batch(self, batch: list[dict]) -> None:
        """Write batch to storage.

        Override this method for specific storage backend.
        """
        # Placeholder implementation
        pass

    async def close(self) -> None:
        """Close writer and flush remaining items."""
        async with self._lock:
            await self._flush()


class LazyLoader:
    """Lazy loader for expensive SIL components.

    Delays initialization until first use to reduce
    startup time.
    """

    def __init__(self, factory: Callable[[], Any]):
        self.factory = factory
        self._instance: Optional[Any] = None
        self._initialized = False

    def __call__(self) -> Any:
        if not self._initialized:
            self._instance = self.factory()
            self._initialized = True
        return self._instance

    def is_loaded(self) -> bool:
        """Check if instance is loaded."""
        return self._initialized


# Benchmarking utilities
async def benchmark_sil(
    num_messages: int = 1000,
    warmup: int = 100,
) -> dict[str, Any]:
    """Benchmark SIL performance.

    Args:
        num_messages: Number of messages to process
        warmup: Number of warmup messages

    Returns:
        Benchmark results
    """
    from core.social_intelligence.router import ModeRouter
    from core.social_intelligence.facilitator import HybridFacilitator

    router = ModeRouter()
    facilitator = HybridFacilitator()
    monitor = PerformanceMonitor()

    test_messages = [
        "Help me debug this code",
        "Give me creative ideas",
        "What do you think?",
        "Explain how this works",
        "Tell me a story",
    ]

    # Warmup
    for _ in range(warmup):
        msg = test_messages[_ % len(test_messages)]
        router.select_mode({"content": msg})

    # Benchmark
    start_time = time.perf_counter()

    for i in range(num_messages):
        msg = test_messages[i % len(test_messages)]

        loop_start = time.perf_counter()

        # Mode selection
        decision = router.select_mode({"content": msg})

        # Facilitator routing
        facilitator.route(msg)

        loop_end = time.perf_counter()
        monitor.record((loop_end - loop_start) * 1000)

    total_time = time.perf_counter() - start_time

    return {
        "total_messages": num_messages,
        "total_time_seconds": total_time,
        "messages_per_second": num_messages / total_time,
        "average_latency_ms": (total_time / num_messages) * 1000,
        "stats": monitor.get_stats(),
        "meets_target": monitor.check_target(100.0)["meets_target"],
    }


def run_benchmark() -> None:
    """Run benchmark and print results."""
    print("Running SIL performance benchmark...")
    print("=" * 60)

    results = asyncio.run(benchmark_sil())

    print(f"\nTotal messages: {results['total_messages']}")
    print(f"Total time: {results['total_time_seconds']:.2f}s")
    print(f"Throughput: {results['messages_per_second']:.1f} msg/s")
    print(f"\nLatency Statistics:")
    print(f"  Average: {results['stats']['mean_ms']:.2f}ms")
    print(f"  P50: {results['stats']['p50_ms']:.2f}ms")
    print(f"  P95: {results['stats']['p95_ms']:.2f}ms")
    print(f"  P99: {results['stats']['p99_ms']:.2f}ms")
    print(f"\nTarget (<100ms): {'✅ PASS' if results['meets_target'] else '❌ FAIL'}")


if __name__ == "__main__":
    run_benchmark()
