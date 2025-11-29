# Logging & Metrics Configuration Guide

## Overview

Your bot now has comprehensive, configurable logging with multiple levels, rotating log files, and customizable metrics collection intervals.

---

## 🎚️ Log Levels

### Available Levels (in order of verbosity):

1. **DEBUG** - Detailed information, typically of interest only when diagnosing problems
   - Shows: All requests, internal state changes, TTFT times, RAG searches
   - Use for: Development, troubleshooting
   - Example: `OpenRouter TTFT: 8.38s`

2. **INFO** - Confirmation that things are working as expected
   - Shows: Main operations, response times, TPS, errors
   - Use for: Normal operation, performance monitoring
   - Example: `OpenRouter response: 7.02s | Tokens: 331 | TPS: 47.2`

3. **WARNING** - An indication that something unexpected happened
   - Shows: Recoverable errors, performance issues
   - Use for: Production monitoring
   - Example: `Streaming TPS below 15, consider switching modes`

4. **ERROR** - More serious problem, bot couldn't perform function
   - Shows: Failed requests, timeouts, exceptions
   - Use for: Production + error tracking
   - Example: `OpenRouter streaming timeout after 180.3s`

5. **CRITICAL** - Serious error, program may be unable to continue
   - Shows: Fatal errors
   - Use for: Alerts only
   - Example: `Failed to initialize bot: ...`

---

## ⚙️ Configuration Options

### In `.env` file:

```bash
# ===================================================================
# Logging Configuration
# ===================================================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_TO_FILE=true  # Save logs to file
LOG_FILE_PATH=logs/bot.log  # Log file location
LOG_MAX_BYTES=10485760  # Max log file size (10MB)
LOG_BACKUP_COUNT=5  # Number of backup files

# Performance Logging
LOG_PERFORMANCE=true  # General metrics
LOG_LLM_REQUESTS=true  # Every LLM request
LOG_TTS_REQUESTS=true  # Every TTS request

# ===================================================================
# Metrics Configuration
# ===================================================================
METRICS_ENABLED=true  # Collect and save metrics
METRICS_SAVE_INTERVAL_MINUTES=60  # Save every N minutes
METRICS_RETENTION_DAYS=30  # Keep files for N days
```

---

## 📊 Common Logging Scenarios

### 1. Development / Debugging
```bash
LOG_LEVEL=DEBUG
LOG_TO_FILE=true
LOG_PERFORMANCE=true
LOG_LLM_REQUESTS=true
LOG_TTS_REQUESTS=true
METRICS_SAVE_INTERVAL_MINUTES=15  # Save every 15 minutes
```

**What you'll see:**
- Every RAG search with similarity scores
- TTFT (time to first token) for streaming
- All internal state changes
- Detailed error traces
- Metrics saved 4x per hour

### 2. Production / Normal Operation
```bash
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_PERFORMANCE=true
LOG_LLM_REQUESTS=true
LOG_TTS_REQUESTS=true
METRICS_SAVE_INTERVAL_MINUTES=60  # Hourly
```

**What you'll see:**
- Main operations and responses
- Performance metrics (TPS, response time)
- Errors and warnings
- Hourly metrics snapshots

### 3. Production / Quiet Mode
```bash
LOG_LEVEL=WARNING
LOG_TO_FILE=true
LOG_PERFORMANCE=false
LOG_LLM_REQUESTS=false
LOG_TTS_REQUESTS=false
METRICS_SAVE_INTERVAL_MINUTES=360  # Every 6 hours
```

**What you'll see:**
- Only warnings and errors
- Less disk usage
- Cleaner logs for alerts

### 4. Performance Monitoring
```bash
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_PERFORMANCE=true
LOG_LLM_REQUESTS=true  # ← Keep this on!
LOG_TTS_REQUESTS=true  # ← Keep this on!
METRICS_SAVE_INTERVAL_MINUTES=30  # Save every 30 minutes
```

**What you'll see:**
- All response times
- TPS for every request
- Frequent metrics for analysis
- Can graph trends over time

---

## 📂 Log File Management

### Rotating Files

With `LOG_MAX_BYTES=10485760` (10MB) and `LOG_BACKUP_COUNT=5`:

```
logs/
├── bot.log          ← Current log (active)
├── bot.log.1        ← Previous rotation
├── bot.log.2        ← 2nd previous
├── bot.log.3        ← 3rd previous
├── bot.log.4        ← 4th previous
└── bot.log.5        ← Oldest (will be deleted next rotation)
```

When `bot.log` reaches 10MB:
1. `bot.log.5` is deleted
2. All files are renamed (`.4` → `.5`, `.3` → `.4`, etc.)
3. `bot.log` → `bot.log.1`
4. New `bot.log` is created

**Total disk usage**: Max 60MB (10MB × 6 files)

---

## 📊 Metrics Save Intervals

### How Often to Save?

**Every 15 minutes** (Development):
```bash
METRICS_SAVE_INTERVAL_MINUTES=15
```
- Files created: 96 per day
- Good for: Active development, real-time analysis
- Disk usage: ~50-100MB per day

**Every 60 minutes** (Production - Default):
```bash
METRICS_SAVE_INTERVAL_MINUTES=60
```
- Files created: 24 per day + 1 daily summary
- Good for: Normal operation
- Disk usage: ~10-20MB per day

**Every 6 hours** (Low Traffic):
```bash
METRICS_SAVE_INTERVAL_MINUTES=360
```
- Files created: 4 per day
- Good for: Low-traffic bots, disk space concerns
- Disk usage: ~2-5MB per day

**Disable Metrics Entirely**:
```bash
METRICS_ENABLED=false
```
- No metric files saved
- Dashboard still works (in-memory only)
- Logs still capture performance data

---

## 🔍 Viewing Logs

### Real-Time Monitoring:

```bash
# All logs
journalctl -u acore_bot -f

# Only performance metrics
journalctl -u acore_bot -f | grep -E "OpenRouter|TPS|TTFT"

# Only errors
journalctl -u acore_bot -f | grep -E "ERROR|WARNING"

# Only RAG searches
journalctl -u acore_bot -f | grep "Vector Search"
```

### File Logs:

```bash
# Tail current log
tail -f /root/acore_bot/logs/bot.log

# View with color highlighting
tail -f /root/acore_bot/logs/bot.log | grep --color -E "ERROR|WARNING|$"

# Search for specific errors
grep "timeout" /root/acore_bot/logs/bot.log

# Count errors
grep -c "ERROR" /root/acore_bot/logs/bot.log
```

---

## 📈 Log Level Impact on Performance

| Log Level | Disk I/O | Performance Impact | Use Case |
|-----------|----------|-------------------|----------|
| DEBUG | Very High | 5-10% overhead | Development only |
| INFO | Moderate | 1-3% overhead | Production default |
| WARNING | Low | < 1% overhead | Production quiet |
| ERROR | Minimal | < 0.5% overhead | Minimal logging |

**Recommendation**: Use INFO for production, DEBUG only when troubleshooting.

---

## 🎯 Quick Setup Examples

### I want maximum detail for troubleshooting:
```bash
LOG_LEVEL=DEBUG
METRICS_SAVE_INTERVAL_MINUTES=15
```

### I want to monitor performance closely:
```bash
LOG_LEVEL=INFO
LOG_LLM_REQUESTS=true
LOG_TTS_REQUESTS=true
METRICS_SAVE_INTERVAL_MINUTES=30
```

### I want minimal logging (production):
```bash
LOG_LEVEL=WARNING
LOG_PERFORMANCE=false
METRICS_SAVE_INTERVAL_MINUTES=360
```

### I want to save disk space:
```bash
LOG_MAX_BYTES=5242880  # 5MB instead of 10MB
LOG_BACKUP_COUNT=3  # Keep only 3 backups
METRICS_SAVE_INTERVAL_MINUTES=180  # Every 3 hours
METRICS_RETENTION_DAYS=7  # Keep only 1 week
```

---

## 🔧 Changing Log Level at Runtime

### Method 1: Restart with new config
```bash
# Edit .env
nano /root/acore_bot/.env
# Change LOG_LEVEL=DEBUG

# Restart bot
systemctl restart acore_bot
```

### Method 2: Quick toggle (without restart)
For temporary debugging, you can run:
```bash
# This would require adding a slash command - not implemented yet
# /set_log_level DEBUG
```

---

## 📊 Log Examples by Level

### DEBUG Output:
```
2025-11-28 01:11:39 - services.rag - DEBUG - Searching vector store for: 'no eight hours just 6'
2025-11-28 01:11:39 - services.rag - INFO - Vector Search found 3 results
2025-11-28 01:11:39 - services.openrouter - DEBUG - OpenRouter TTFT: 10.62s
2025-11-28 01:11:51 - services.openrouter - INFO - OpenRouter stream: 11.25s | ~53 tokens | TPS: 4.7
```

### INFO Output:
```
2025-11-28 01:11:39 - services.rag - INFO - Vector Search found 3 results
2025-11-28 01:11:51 - services.openrouter - INFO - OpenRouter stream: 11.25s | ~53 tokens | TPS: 4.7
2025-11-28 01:11:59 - services.mood_system - INFO - Mood changed: thoughtful → calm
```

### WARNING Output:
```
2025-11-28 01:11:51 - services.openrouter - WARNING - Streaming TPS (4.7) below threshold, consider non-streaming
```

### ERROR Output:
```
2025-11-28 01:01:53 - cogs.chat - ERROR - Chat command failed: TimeoutError
2025-11-28 01:01:53 - services.openrouter - ERROR - OpenRouter streaming timeout after 180.3s
```

---

## 💡 Best Practices

1. **Start with INFO** - Good balance of detail and performance
2. **Use DEBUG temporarily** - Only when troubleshooting specific issues
3. **Monitor log file size** - Adjust MAX_BYTES if files grow too large
4. **Set appropriate retention** - 30 days default, adjust based on needs
5. **Save metrics less frequently** if disk space is limited
6. **Keep LOG_LLM_REQUESTS=true** - Essential for performance analysis
7. **Review logs periodically** - Look for patterns, errors, performance issues

---

## 🎉 Summary

You now have full control over logging:
- ✅ **5 log levels** (DEBUG to CRITICAL)
- ✅ **Rotating log files** (prevents disk filling)
- ✅ **Configurable metrics intervals** (15min to 24hr+)
- ✅ **Performance logging toggles** (LLM, TTS)
- ✅ **Retention policies** (auto-cleanup old files)

All changes take effect immediately on bot restart!
