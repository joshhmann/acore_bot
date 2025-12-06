# Phase 4 Optimizations - Quick Usage Guide

This guide shows you how to use and monitor the Phase 4 optimizations.

## Request Deduplication

**Automatically enabled** - no configuration needed!

### Monitor Deduplication

```python
# In a debug/status command
stats = ollama_service.get_cache_stats()
print(f"Active deduplications: {stats['deduplication']['active_deduplication']}")
print(f"Pending requests: {stats['deduplication']['pending_requests']}")
```

### How It Works

When multiple users ask the same question within 5 seconds:
- First request → Makes API call
- Subsequent identical requests → Wait for first request's result
- All requests get the same response
- Result: Only 1 API call instead of N calls

---

## ChatHistoryManager (OrderedDict LRU)

**Automatically enabled** - no configuration needed!

### Benefits

- 10x faster cache operations with large channel counts
- O(1) access time instead of O(n)
- Better performance with 100+ active channels

### Monitor Cache Performance

```python
# Check cache hit rate
stats = metrics_service.get_cache_stats()
print(f"History cache hit rate: {stats['history_cache']['hit_rate']:.1f}%")
print(f"Hits: {stats['history_cache']['hits']}")
print(f"Misses: {stats['history_cache']['misses']}")
```

---

## Metrics Batch Logging

**Requires startup** - add to main.py

### Enable Batch Logging

```python
# In main.py, after creating metrics_service
metrics_service.start_batch_flush_task()
```

### Log Events

```python
# Events are automatically batched
metrics_service.log_event('command_executed', {
    'command': 'chat',
    'user_id': 123456,
    'channel_id': 789,
    'latency_ms': 245,
    'success': True
})

metrics_service.log_event('llm_response', {
    'model': 'llama3.2',
    'tokens': 150,
    'duration_ms': 2340
})
```

### Monitor Batch Status

```python
batch_stats = metrics_service.get_batch_stats()
print(f"Pending events: {batch_stats['pending_events']}")
print(f"Batch size: {batch_stats['batch_size']}")
print(f"Flush interval: {batch_stats['batch_interval']}s")
print(f"Task running: {batch_stats['batch_task_running']}")
```

### Graceful Shutdown

```python
# In shutdown handler
await metrics_service.stop_batch_flush_task()  # Flushes remaining events
```

### Tuning

```python
# Adjust batching parameters (before starting task)
metrics_service.batch_size = 100       # Flush after 100 events
metrics_service.batch_interval = 30    # Or every 30 seconds
```

---

## Performance Profiling

### Quick Start with py-spy

```bash
# 1. Start bot
python main.py

# 2. In another terminal, find process ID
pgrep -f main.py

# 3. Profile for 5 minutes
sudo py-spy record -o flamegraph.svg --pid <PID> --duration 300

# 4. Open flamegraph.svg in browser
firefox flamegraph.svg
```

### Using the Profiling Script

```bash
# Show comprehensive guide
python scripts/profile_performance.py

# cProfile mode (built-in Python profiler)
python scripts/profile_performance.py --mode cprofile --duration 60

# Memory profiling instructions
python scripts/profile_performance.py --mode memory

# Analyze existing profile
python scripts/profile_performance.py --mode analyze --profile-file myprofile.prof
```

### What to Look For

In flamegraph/profile:
1. **Wide bars** = Functions that take a lot of cumulative time (hot paths)
2. **Many calls** = Optimization opportunities (caching, memoization)
3. **Blocking operations** = Convert to async
4. **Memory growth** = Potential leaks

---

## Complete Example Integration

```python
# main.py

import asyncio
from services.metrics import MetricsService
from services.ollama import OllamaService
from utils.helpers import ChatHistoryManager

async def main():
    # Initialize services
    metrics = MetricsService()
    ollama = OllamaService(...)
    history_manager = ChatHistoryManager(...)
    
    # Start background tasks
    metrics.start_batch_flush_task()    # Batch logging
    metrics.start_hourly_reset()        # Hourly stats reset
    
    try:
        # Run bot
        await bot.start()
        
    finally:
        # Graceful shutdown
        await metrics.stop_batch_flush_task()
        await ollama.close()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Monitoring Dashboard Example

```python
async def status_command(ctx):
    """Show bot performance stats."""
    
    # Get complete metrics
    summary = metrics_service.get_summary()
    
    # Response times
    rt = summary['response_times']
    response_info = f"""
    Response Times:
    - Average: {rt['avg']:.0f}ms
    - P95: {rt['p95']:.0f}ms
    - P99: {rt['p99']:.0f}ms
    """
    
    # Cache performance
    cache = summary['cache_stats']
    cache_info = f"""
    Cache Performance:
    - History hit rate: {cache['history_cache']['hit_rate']:.1f}%
    - RAG hit rate: {cache['rag_cache']['hit_rate']:.1f}%
    """
    
    # Deduplication
    dedup = cache.get('deduplication', {})
    dedup_info = f"""
    Request Deduplication:
    - Active: {dedup.get('active_deduplication', 0)}
    - Pending: {dedup.get('pending_requests', 0)}
    """
    
    # Batch logging
    batch = summary['batch_logging']
    batch_info = f"""
    Batch Logging:
    - Pending events: {batch['pending_events']}/{batch['batch_size']}
    - Task running: {batch['batch_task_running']}
    """
    
    await ctx.send(f"{response_info}\n{cache_info}\n{dedup_info}\n{batch_info}")
```

---

## Expected Performance Improvements

| Optimization | Improvement | When Most Effective |
|-------------|-------------|---------------------|
| Request Deduplication | 20-30% fewer LLM calls | High traffic, duplicate queries |
| OrderedDict LRU | 10x faster cache ops | 100+ active channels |
| Batch Logging | 90% less disk I/O | High event logging volume |
| Combined | Lower latency, costs | All scenarios |

---

## Troubleshooting

### Deduplication not working?

Check if requests are truly identical:
- Same messages
- Same model
- Same temperature
- Same system prompt

### Batch logging not flushing?

```python
# Manually trigger flush
await metrics_service._flush_events()

# Check task status
if metrics_service._batch_task:
    print(f"Task done: {metrics_service._batch_task.done()}")
```

### High memory usage?

```bash
# Profile memory
mprof run python main.py
# Let it run, then:
mprof plot
```

Look for:
- Growing deque/set sizes
- Unbounded caches
- Memory leaks in long-running tasks

---

For more details, see:
- `PHASE4_COMPLETION_SUMMARY.md` - Full implementation details
- `IMPROVEMENT_PLAN.md` - Overall roadmap
- `scripts/profile_performance.py --mode guide` - Profiling guide
