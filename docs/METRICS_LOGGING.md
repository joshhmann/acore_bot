# Metrics Logging System

## Overview

The bot now includes comprehensive metrics logging to disk for later analysis. Metrics are automatically saved every hour and cleaned up after 30 days.

## What Gets Logged

### Performance Metrics
- **Response Times**: Average, min, max, p50, p95, p99 percentiles
- **Uptime**: Total uptime in seconds and formatted string
- **Latency**: Discord API latency

### Token Usage
- Total tokens consumed
- Prompt vs completion token breakdown
- Token usage per model

### Error Tracking
- Total errors
- Errors by type
- Recent errors (last 20) with timestamps
- Error rate (errors per message)

### Activity Stats
- Unique active users
- Active channels
- Total messages processed
- Commands executed

### Cache Performance
- History cache hit rate
- RAG cache hit rate
- Hits vs misses breakdown

### Service Metrics
- TTS generations
- Vision requests
- Web searches
- Summarizations
- RAG queries

### Hourly Trends
- Messages per hour (last 24 hours)
- Errors per hour (last 24 hours)
- Current hour stats

## File Structure

Metrics are saved to: `/root/acore_bot/data/metrics/`

### File Types

1. **Hourly Snapshots** (auto-saved every hour)
   - Format: `hourly_YYYYMMDD_HH.json`
   - Example: `hourly_20251127_14.json`
   - Saved every hour automatically

2. **Daily Summaries** (saved at midnight)
   - Format: `daily_YYYYMMDD.json`
   - Example: `daily_20251127.json`
   - Comprehensive daily report

3. **Manual Snapshots**
   - Format: `metrics_YYYYMMDD_HHMMSS.json`
   - Created via `bot.metrics.save_metrics_to_file()`

## Automatic Features

### Auto-Save
- Runs every 1 hour by default
- Saves hourly snapshot
- At midnight (hour=0):
  - Saves daily summary
  - Cleans up old files (>30 days)

### Retention
- Default: 30 days
- Configurable via `cleanup_old_metrics(days_to_keep=N)`
- Automatic cleanup at midnight

## Manual Usage

### Save Metrics Now
```python
# In bot code
bot.metrics.save_metrics_to_file()  # Creates timestamped file
bot.metrics.save_hourly_snapshot()  # Creates hourly file
bot.metrics.save_daily_summary()    # Creates daily file
```

### Load Metrics
```python
data = bot.metrics.load_metrics_from_file("hourly_20251127_14.json")
print(data['response_times']['avg'])  # Average response time
```

### List All Saved Metrics
```python
files = bot.metrics.list_saved_metrics()
for f in files:
    print(f"{f['filename']} - {f['size_kb']}KB - {f['modified']}")
```

### Manual Cleanup
```python
bot.metrics.cleanup_old_metrics(days_to_keep=7)  # Keep only last 7 days
```

## Example Metrics File

```json
{
  "uptime_seconds": 3600,
  "uptime_formatted": "1:00:00",
  "response_times": {
    "avg": 487.5,
    "min": 123.4,
    "max": 1234.5,
    "p50": 450.2,
    "p95": 987.3,
    "p99": 1100.8,
    "count": 100
  },
  "token_usage": {
    "total_tokens": 45000,
    "prompt_tokens": 30000,
    "completion_tokens": 15000,
    "by_model": {
      "qwen2.5:32b": 45000
    }
  },
  "errors": {
    "total_errors": 3,
    "by_type": {
      "APIError": 2,
      "TimeoutError": 1
    },
    "recent_errors": [...],
    "error_rate": 0.15
  },
  "active_stats": {
    "active_users": 15,
    "active_channels": 3,
    "messages_processed": 200,
    "commands_executed": 25
  },
  "cache_stats": {
    "history_cache": {
      "hits": 150,
      "misses": 50,
      "hit_rate": 75.0
    },
    "rag_cache": {
      "hits": 80,
      "misses": 20,
      "hit_rate": 80.0
    }
  },
  "service_metrics": {
    "tts_generations": 45,
    "vision_requests": 12,
    "web_searches": 8,
    "summarizations": 3,
    "rag_queries": 22
  },
  "hourly_trends": {
    "messages_per_hour": [45, 67, 89, ...],
    "errors_per_hour": [0, 1, 0, ...],
    "current_hour_messages": 23,
    "current_hour_errors": 0
  },
  "saved_at": "2025-11-27T14:30:00.123456",
  "version": "1.0"
}
```

## Analysis Tips

### Find Peak Usage Times
```bash
# List all hourly files
ls -lh /root/acore_bot/data/metrics/hourly_*.json

# Check messages per hour
cat hourly_20251127_14.json | jq '.hourly_trends.current_hour_messages'
```

### Calculate Average Response Time
```bash
# Average response time for a specific hour
cat hourly_20251127_14.json | jq '.response_times.avg'

# Get p95 (95th percentile)
cat hourly_20251127_14.json | jq '.response_times.p95'
```

### Check Error Rates
```bash
# Get error rate
cat daily_20251127.json | jq '.errors.error_rate'

# List error types
cat daily_20251127.json | jq '.errors.by_type'
```

### Token Usage Analysis
```bash
# Total tokens used today
cat daily_20251127.json | jq '.token_usage.total_tokens'

# Tokens per model
cat daily_20251127.json | jq '.token_usage.by_model'
```

### Cache Performance
```bash
# RAG cache hit rate
cat daily_20251127.json | jq '.cache_stats.rag_cache.hit_rate'
```

## Python Analysis Script Example

```python
import json
from pathlib import Path
from datetime import datetime, timedelta

def analyze_daily_metrics(date_str):
    """Analyze metrics for a specific day.

    Args:
        date_str: Date in format YYYYMMDD
    """
    metrics_path = Path(f"/root/acore_bot/data/metrics/daily_{date_str}.json")

    with open(metrics_path) as f:
        data = json.load(f)

    print(f"=== Metrics for {date_str} ===")
    print(f"Uptime: {data['uptime_formatted']}")
    print(f"Messages processed: {data['active_stats']['messages_processed']}")
    print(f"Average response time: {data['response_times']['avg']:.2f}ms")
    print(f"Error rate: {data['errors']['error_rate']:.2f}%")
    print(f"Total tokens: {data['token_usage']['total_tokens']:,}")
    print(f"Cache hit rate: {data['cache_stats']['history_cache']['hit_rate']:.1f}%")

# Usage
analyze_daily_metrics("20251127")
```

## Dashboard Integration

Metrics are also exposed via the web dashboard at:
- Live metrics: `http://your-bot:5000/`
- API endpoint: `http://your-bot:5000/api/status`

## Troubleshooting

### Metrics Not Saving
- Check logs for errors: `grep "metrics" /root/acore_bot/logs/bot.log`
- Verify directory exists: `ls -la /root/acore_bot/data/metrics/`
- Check disk space: `df -h`

### Large File Sizes
- Reduce `days_to_keep` parameter
- Manually run cleanup: `bot.metrics.cleanup_old_metrics(days_to_keep=7)`

### Missing Data
- Metrics reset on bot restart (in-memory tracking)
- Check if auto-save is running: Look for "Metrics auto-save started" in logs
- Verify bot stayed online for full hour

## Configuration

### Change Save Interval
Edit `main.py:450`:
```python
metrics_task = self.metrics.start_auto_save(interval_hours=2)  # Save every 2 hours
```

### Change Retention Period
Edit `services/metrics.py:440`:
```python
self.cleanup_old_metrics(days_to_keep=60)  # Keep 60 days
```

## Future Enhancements

Possible additions:
- CSV export for easier analysis
- Graphing/visualization tools
- Alerting on high error rates
- Comparison tools (day-over-day, week-over-week)
- Integration with monitoring services (Prometheus, Grafana)
- Database storage for historical querying
