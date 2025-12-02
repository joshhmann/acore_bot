# Monitoring & Debugging Guide

Complete guide to logging, metrics, and debugging the bot.

## Table of Contents

1. [Logging Configuration](#logging-configuration)
2. [Metrics Collection](#metrics-collection)
3. [Debug Mode](#debug-mode)
4. [Web Dashboard](#web-dashboard)
5. [Troubleshooting](#troubleshooting)

---

## Logging Configuration

### Overview
The bot uses Python's `logging` module with rotating file handlers.

### Configuration (.env)

```bash
# Logging settings
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_TO_FILE=true        # Enable file logging
LOG_FILE_PATH=logs/bot.log
LOG_MAX_BYTES=10485760  # 10 MB per log file
LOG_BACKUP_COUNT=5      # Keep 5 backup logs
```

### Log Levels

**DEBUG**
- All service calls and responses
- Detailed execution flow
- Token counts and context sizes
- Warning: Very verbose!

**INFO** (Recommended)
- User commands
- API calls
- Service initialization
- Performance warnings

**WARNING**
- Non-critical errors
- Fallback behaviors
- Rate limits
- Configuration issues

**ERROR**
- Failed operations
- API errors
- Exceptions
- Critical bugs

### Rotating Logs

Logs automatically rotate when they reach `LOG_MAX_BYTES`:
```
logs/
├── bot.log          (current)
├── bot.log.1        (previous)
├── bot.log.2
├── bot.log.3
├── bot.log.4
└── bot.log.5        (oldest)
```

### Filtering Noisy Logs

The bot automatically suppresses noisy third-party logs:
```python
# Suppressed in production (unless DEBUG)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("nemo_logger").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("discord").setLevel(logging.WARNING)
```

---

## Metrics Collection

### Overview
The bot tracks performance metrics for monitoring and optimization.

### Metrics Service

**File**: `services/metrics.py`

**Tracks**:
- Response times (LLM, TTS, total)
- Token usage (input, output, total)
- API call counts
- Error rates
- Cache hit rates
- Memory usage

### Usage

```python
from services.metrics import MetricsService

metrics = MetricsService()

# Start timing an operation
with metrics.timer("llm_generation"):
    response = await ollama.chat(prompt)

# Record a value
metrics.record("tokens_used", len(response))

# Increment counter
metrics.increment("api_calls")

# Get statistics
stats = metrics.get_stats()
print(f"Avg response time: {stats['avg_response_time']}ms")
```

### Available Metrics

**Timing Metrics**:
- `llm_generation` - Time for LLM to generate response
- `tts_generation` - Time to generate audio
- `total_response_time` - End-to-end response time
- `voice_transcription` - Time to transcribe audio

**Counter Metrics**:
- `messages_processed` - Total messages handled
- `api_calls` - Total API calls made
- `errors` - Total errors encountered
- `cache_hits` - Cache hit count
- `cache_misses` - Cache miss count

**Value Metrics**:
- `tokens_input` - Input tokens sent
- `tokens_output` - Output tokens received
- `memory_usage_mb` - Current memory usage
- `temp_files_mb` - Temp file storage used

---

## Debug Mode

### Overview
Enhanced logging and metrics collection for troubleshooting.

### Enabling Debug Mode

**Option 1: Environment Variable**
```bash
LOG_LEVEL=DEBUG
DEBUG_MODE=true
```

**Option 2: Runtime**
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Debug Features

**1. Detailed Request/Response Logging**
```
[DEBUG] LLM Request:
  Model: stheno-3.2:latest
  Tokens: 1847
  Context: [User profile, 10 messages, summary]

[DEBUG] LLM Response:
  Time: 2.3s
  Tokens: 156
  First 50 chars: "That's a great question! Let me explain..."
```

**2. Service Call Tracing**
```
[DEBUG] service_call: user_profiles.get_profile(user_id=123)
[DEBUG] service_call: memory_manager.get_conversation(channel_id=456)
[DEBUG] service_call: ollama.chat(prompt="...", history=[...])
```

**3. Performance Warnings**
```
[WARNING] Slow LLM response: 5.2s (expected < 3s)
[WARNING] Large context: 4200 tokens (recommended < 2500)
[WARNING] High memory usage: 1.8 GB (threshold: 1.5 GB)
```

**4. Error Stack Traces**
```
[ERROR] Failed to generate TTS:
Traceback (most recent call last):
  File "services/tts.py", line 45, in generate
    audio = await kokoro.synthesize(text)
  ...
```

### Debug Commands

**View Metrics** (in Discord):
```
/debug metrics
```

**View Memory Stats**:
```
/debug memory
```

**View Recent Errors**:
```
/debug errors
```

---

## Web Dashboard

### Overview
Flask-based web interface for monitoring bot performance.

### Features

**Status**: ⚠️ Code exists but status unclear
**File**: `services/web_dashboard.py`

**Provides**:
- Real-time metrics visualization
- User profile statistics
- Conversation history browser
- Memory usage graphs
- Error logs viewer
- Performance analytics

### Accessing Dashboard

```bash
# Dashboard runs on port 5000 by default
DASHBOARD_ENABLED=true
DASHBOARD_PORT=5000
```

Visit: `http://localhost:5000`

### Dashboard Pages

**1. Overview**
- Active users
- Messages/hour
- Average response time
- Memory usage
- Uptime

**2. Performance**
- Response time graphs
- Token usage trends
- API latency
- Cache performance

**3. Users**
- User profile list
- Affection levels
- Conversation counts
- Recent interactions

**4. Logs**
- Live log stream
- Error filtering
- Search functionality
- Download logs

---

## Troubleshooting

### Common Issues

**1. Slow Responses**

Check logs for:
```bash
grep "Slow LLM" logs/bot.log
grep "response_time" logs/bot.log
```

Possible causes:
- LLM provider latency
- Large context size (> 3000 tokens)
- Network issues
- CPU/memory constraints

Fix:
- Enable response streaming
- Reduce history size
- Use faster LLM model
- Check system resources

**2. High Memory Usage**

Check metrics:
```bash
grep "memory_usage" logs/bot.log
```

Possible causes:
- Temp files not cleaned up
- Large conversation histories
- Memory leaks
- Too many cached profiles

Fix:
- Verify `MEMORY_CLEANUP_ENABLED=true`
- Reduce `MAX_HISTORY_MESSAGES`
- Restart bot periodically
- Check for stuck processes

**3. Missing Logs**

Verify configuration:
```bash
# Check .env
cat .env | grep LOG

# Check log directory exists
ls -la logs/

# Check permissions
ls -la logs/bot.log
```

Fix:
- Create logs directory: `mkdir -p logs`
- Set permissions: `chmod 755 logs`
- Verify `LOG_TO_FILE=true`

**4. TTS Errors**

Check logs:
```bash
grep "TTS" logs/bot.log | grep ERROR
```

Common errors:
- `Failed to connect to RVC`: RVC service not running
- `Kokoro initialization failed`: Model not downloaded
- `Edge TTS timeout`: Network issues

Fix:
- See [setup/VOICE_SETUP_SUMMARY.md](setup/VOICE_SETUP_SUMMARY.md)

---

## Log Analysis

### Useful Grep Commands

**Find errors in last hour**:
```bash
tail -n 10000 logs/bot.log | grep ERROR
```

**Count errors by type**:
```bash
grep ERROR logs/bot.log | cut -d':' -f4 | sort | uniq -c | sort -nr
```

**Average response time**:
```bash
grep "total_response_time" logs/bot.log | awk '{sum+=$NF; count++} END {print sum/count}'
```

**Most active users**:
```bash
grep "user_id=" logs/bot.log | grep -oP 'user_id=\K[0-9]+' | sort | uniq -c | sort -nr | head -10
```

**Memory usage over time**:
```bash
grep "memory_usage_mb" logs/bot.log | awk '{print $1, $2, $NF}'
```

---

## Performance Monitoring

### Key Metrics to Watch

**Response Time**
- Target: < 2s average
- Warning: > 3s
- Critical: > 5s

**Token Usage**
- Target: < 2500 tokens/request
- Warning: > 3500
- Critical: > 5000

**Memory Usage**
- Target: < 1 GB
- Warning: > 1.5 GB
- Critical: > 2 GB

**Error Rate**
- Target: < 1%
- Warning: > 2%
- Critical: > 5%

### Setting Up Alerts

**Option 1: Log Monitoring**
```bash
# Monitor for errors
tail -f logs/bot.log | grep --line-buffered ERROR | mail -s "Bot Error" you@example.com
```

**Option 2: Metrics Threshold**
```python
# In metrics service
if metrics.get_avg("response_time") > 3000:
    logger.warning("High average response time detected!")
    # Send alert
```

**Option 3: External Monitoring**
- Use tools like Prometheus + Grafana
- Export metrics to monitoring service
- Set up alerts and dashboards

---

## Configuration Reference

```bash
# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE_PATH=logs/bot.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# Metrics
METRICS_ENABLED=true
METRICS_COLLECTION_INTERVAL=60

# Dashboard
DASHBOARD_ENABLED=false
DASHBOARD_PORT=5000
DASHBOARD_HOST=0.0.0.0

# Debug
DEBUG_MODE=false
VERBOSE_LOGGING=false
```
