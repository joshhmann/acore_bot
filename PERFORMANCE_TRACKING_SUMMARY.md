# Performance Tracking Update Summary

## Overview

Added comprehensive performance monitoring for OpenRouter API calls with automatic metrics logging to disk for later analysis.

---

## ✅ What's Been Added

### 1. **OpenRouter Response Time Tracking**

Every API call to OpenRouter now tracks:
- **Response Time**: How long it takes to get a complete response (in seconds and milliseconds)
- **TPS (Tokens Per Second)**: Generation speed
- **TTFT (Time To First Token)**: For streaming responses, how long until first token arrives
- **Token Usage**: Total tokens generated per request
- **Average Response Time**: Rolling average across all requests

### 2. **Automatic Metrics Logging**

All metrics are now automatically saved to disk:
- **Hourly snapshots**: Saved every hour
- **Daily summaries**: Saved at midnight
- **Automatic cleanup**: Old metrics deleted after 30 days
- **Location**: `/root/acore_bot/data/metrics/`

### 3. **Improved Timeout Handling**

- Streaming timeout increased from 120s → 180s
- Better error messages when timeouts occur
- Timeout errors now logged with timing information

---

## 📊 Performance Metrics Tracked

### Dashboard Already Shows:
✅ **Uptime**: Days, hours, minutes, AND seconds (e.g., "2d 5h 32m 45s")
✅ **Latency**: Discord API latency in milliseconds

### NEW - OpenRouter Metrics:
✨ **Response Time**: Last request duration in seconds/milliseconds
✨ **TPS (Tokens/Second)**: How fast the model generates tokens
✨ **Average Response Time**: Average across all requests
✨ **Total Requests**: Number of API calls made
✨ **Total Tokens**: Total tokens generated since bot started
✨ **TTFT**: Time to first token for streaming requests

---

## 📝 Log Output Examples

### Non-Streaming Request:
```
INFO - OpenRouter response: 3.45s | Tokens: 287 | TPS: 83.2 | Total: 512
```

### Streaming Request:
```
DEBUG - OpenRouter TTFT: 0.87s
INFO - OpenRouter stream: 8.21s | ~345 tokens | TPS: 42.0 | TTFT: 0.87s
```

### Timeout Error:
```
ERROR - OpenRouter streaming timeout after 180.3s
ERROR - OpenRouter request timed out - try reducing message length or switching models
```

---

## 🔍 How to View Metrics

### In Logs (Real-Time):
```bash
tail -f /var/log/syslog | grep "OpenRouter"
```

### Saved Metrics Files:
```bash
# List all metrics files
ls -lh /root/acore_bot/data/metrics/

# View latest hourly snapshot
cat /root/acore_bot/data/metrics/hourly_$(date +%Y%m%d_%H).json | jq .

# Check OpenRouter performance
cat /root/acore_bot/data/metrics/daily_$(date +%Y%m%d).json | jq '.response_times'
```

### In Python:
```python
# Get current performance stats
stats = bot.ollama.get_performance_stats()  # If using OpenRouter
print(f"Last response: {stats['last_response_time_ms']}ms")
print(f"TPS: {stats['last_tps']}")
print(f"Average: {stats['average_response_time_ms']}ms")
```

---

## 📈 Example Metrics File

Saved hourly in `/root/acore_bot/data/metrics/`:

```json
{
  "uptime_seconds": 7200,
  "uptime_formatted": "2:00:00",
  "response_times": {
    "avg": 3245.8,
    "min": 1234.5,
    "max": 8921.2,
    "p50": 3012.4,
    "p95": 6543.1,
    "p99": 7890.2,
    "count": 150
  },
  "token_usage": {
    "total_tokens": 125000,
    "prompt_tokens": 80000,
    "completion_tokens": 45000,
    "by_model": {
      "openai/gpt-4": 125000
    }
  },
  "saved_at": "2025-11-28T01:00:00.123456",
  "version": "1.0"
}
```

---

## 🎯 What This Tells You

### Response Time Analysis:
- **< 2s**: Excellent - Fast responses
- **2-5s**: Good - Normal for most models
- **5-10s**: Slow - Consider switching models
- **> 10s**: Very slow - Check model size or network

### TPS (Tokens Per Second):
- **> 50 TPS**: Excellent generation speed
- **20-50 TPS**: Good performance
- **10-20 TPS**: Acceptable for large models
- **< 10 TPS**: Slow - consider smaller/faster model

### TTFT (Time To First Token):
- **< 1s**: Excellent responsiveness
- **1-3s**: Good
- **> 3s**: User might notice delay

---

## 🛠️ Troubleshooting

### High Response Times?
1. Check which model you're using - larger models are slower
2. Check message/context length - longer = slower
3. Check OpenRouter status: https://status.openrouter.ai
4. Consider switching to a faster model

### Frequent Timeouts?
1. **Reduce context**: Shorter conversation history
2. **Lower max_tokens**: Reduce `OLLAMA_MAX_TOKENS` in config
3. **Switch models**: Use a faster model
4. **Check network**: Test connection to OpenRouter

### Low TPS?
- Normal for large models (70B+)
- OpenRouter might be under heavy load
- Try a different model provider

---

## 📊 Performance Comparison

Example metrics for different models (approximate):

| Model | Avg Response Time | TPS | TTFT |
|-------|-------------------|-----|------|
| GPT-4 Turbo | 3-5s | 40-60 | < 1s |
| Claude 3 Opus | 4-7s | 30-50 | 1-2s |
| Llama 3 70B | 5-10s | 20-40 | 2-3s |
| Mixtral 8x7B | 2-4s | 50-70 | < 1s |

*Note: Actual performance varies based on load, prompt length, and OpenRouter routing*

---

## 🔄 Auto-Save Schedule

Metrics are automatically saved:
- **Every hour**: Snapshot of current stats
- **At midnight**: Daily summary + cleanup
- **Retention**: 30 days (configurable)

Files:
- `hourly_YYYYMMDD_HH.json` - Hourly snapshots
- `daily_YYYYMMDD.json` - Daily summaries

---

## 🚀 Next Steps

1. **Monitor for a day** to establish baseline performance
2. **Compare metrics** across different times/models
3. **Optimize** if you see:
   - Consistent high response times (> 10s)
   - Low TPS (< 15)
   - Frequent timeouts
4. **Analyze trends** using the daily summary files

---

## 📝 Configuration

### Increase Timeout (if needed):
Edit `/root/acore_bot/services/openrouter.py:221`:
```python
timeout=aiohttp.ClientTimeout(total=300)  # 5 minutes instead of 3
```

### Change Metrics Save Interval:
Edit `/root/acore_bot/main.py:450`:
```python
metrics_task = self.metrics.start_auto_save(interval_hours=2)  # Save every 2 hours
```

### Change Retention:
Edit `/root/acore_bot/services/metrics.py:440`:
```python
self.cleanup_old_metrics(days_to_keep=60)  # Keep 60 days
```

---

## 📖 Documentation

See also:
- `/root/acore_bot/docs/METRICS_LOGGING.md` - Full metrics system documentation
- Logs: `/var/log/syslog` or `journalctl -u acore_bot -f`

---

## ✨ Summary

**Before**:
- No performance tracking
- No metrics logging
- Timeouts with no context
- No way to analyze performance

**After**:
- Real-time performance metrics in logs
- Automatic hourly/daily metrics saved to disk
- TPS and response time tracking
- Better timeout error messages
- 30-day historical data for analysis

All metrics are automatically saved and you can analyze them later to optimize your bot's performance!
