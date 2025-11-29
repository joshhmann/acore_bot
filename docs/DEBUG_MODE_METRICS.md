# DEBUG Mode Enhanced Metrics

## Overview

When `LOG_LEVEL=DEBUG`, the bot automatically captures **way more detailed information** and saves it all to JSON files for easy analysis.

---

## 🎯 Why DEBUG Mode for Optimization?

**Problem**: You're restarting the bot frequently while optimizing, and want detailed metrics without parsing logs.

**Solution**: DEBUG mode automatically:
- ✅ Saves metrics **every 10 minutes** (vs 60 in INFO)
- ✅ Tracks **last 500 responses** (vs 100 in INFO)
- ✅ Logs **every single request** with full details to JSON
- ✅ Includes **streaming TTFT** for each request
- ✅ Captures **RAG similarity scores**
- ✅ Records **TPS variations** per request

---

## 📊 What Gets Logged in DEBUG Mode

### Standard Metrics (INFO mode):
```json
{
  "response_times": {
    "avg": 8523.4,
    "min": 5472.1,
    "max": 17883.2,
    "count": 100
  },
  "token_usage": {
    "total_tokens": 45000,
    "by_model": {
      "gpt-4": 45000
    }
  }
}
```

### Enhanced Metrics (DEBUG mode):
```json
{
  "debug_mode": true,
  "response_times": {
    "avg": 8523.4,
    "min": 5472.1,
    "max": 17883.2,
    "count": 500  // ← 5x more history!
  },
  "detailed_request_count": 100,
  "detailed_requests": [
    {
      "timestamp": "2025-11-28T01:10:51.017Z",
      "duration_ms": 9520,
      "request_type": "streaming",
      "tokens": 54,
      "tps": 5.7,
      "ttft": 8.38,
      "model": "gpt-4",
      "streaming": true,
      "prompt_tokens": 1250,
      "completion_tokens": 54,
      "user_id": "68554430370283520",
      "channel_id": "1431878519016915044",
      "message_length": 125
    },
    {
      "timestamp": "2025-11-28T01:10:58.035Z",
      "duration_ms": 7020,
      "request_type": "non_streaming",
      "tokens": 331,
      "tps": 47.2,
      "model": "gpt-4",
      "streaming": false,
      "prompt_tokens": 1580,
      "completion_tokens": 331,
      "user_id": "68554430370283520",
      "channel_id": "1431878519016915044",
      "message_length": 87,
      "rag_context_used": true,
      "rag_similarity": 0.33
    }
    // ... 98 more detailed requests
  ]
}
```

---

## 🚀 Quick Start for Optimization

### 1. Enable DEBUG Mode

Edit `.env`:
```bash
LOG_LEVEL=DEBUG
```

Restart bot:
```bash
systemctl restart acore_bot
```

### 2. Use Bot Normally

Chat with it, test different scenarios. Metrics save **every 10 minutes automatically**.

### 3. Analyze the JSON

After 10-30 minutes:
```bash
# View latest metrics
cat /root/acore_bot/data/metrics/hourly_$(date +%Y%m%d_%H).json | jq .

# See detailed requests
cat /root/acore_bot/data/metrics/hourly_*.json | jq '.detailed_requests[]' | head -20

# Find slow requests
cat /root/acore_bot/data/metrics/hourly_*.json | jq '.detailed_requests[] | select(.duration_ms > 10000)'

# Compare streaming vs non-streaming
cat /root/acore_bot/data/metrics/hourly_*.json | jq '.detailed_requests[] | select(.streaming == true) | {tps, ttft, duration_ms}'
```

### 4. Switch Back to INFO

When optimization is done:
```bash
LOG_LEVEL=INFO  # in .env
systemctl restart acore_bot
```

---

## 📈 Analysis Examples

### Find Slowest Requests:
```bash
jq '.detailed_requests | sort_by(.duration_ms) | reverse | .[0:10]' hourly_*.json
```

### Average TPS by Request Type:
```bash
jq '.detailed_requests | group_by(.streaming) | map({streaming: .[0].streaming, avg_tps: (map(.tps) | add / length)})' hourly_*.json
```

### Requests with Low TPS:
```bash
jq '.detailed_requests[] | select(.tps < 15)' hourly_*.json
```

### RAG Context Impact:
```bash
jq '.detailed_requests | group_by(.rag_context_used) | map({rag_used: .[0].rag_context_used, avg_time: (map(.duration_ms) | add / length)})' hourly_*.json
```

---

## ⚙️ Automatic Adjustments in DEBUG Mode

### Metrics Save Frequency:
- **INFO mode**: Every 60 minutes (configurable)
- **DEBUG mode**: Every 10 minutes (automatic)

### Response History:
- **INFO mode**: Last 100 responses
- **DEBUG mode**: Last 500 responses (5x more!)

### Request Details:
- **INFO mode**: Aggregated statistics only
- **DEBUG mode**: Every request logged with full context

---

## 💾 Storage Impact

### INFO Mode (60min intervals):
- Files per day: ~24
- File size: ~10-50KB each
- Total: ~1-2MB per day

### DEBUG Mode (10min intervals):
- Files per day: ~144
- File size: ~100-500KB each (detailed requests)
- Total: ~15-70MB per day

**Recommendation**: Use DEBUG mode during active optimization (1-7 days), then switch back to INFO.

---

## 🎯 Common DEBUG Workflows

### Workflow 1: Performance Testing
```bash
# 1. Enable DEBUG
LOG_LEVEL=DEBUG

# 2. Restart & test for 30-60 minutes
systemctl restart acore_bot
# ... use the bot ...

# 3. Analyze
python3 scripts/analyze_performance.py

# 4. View detailed requests
jq '.detailed_requests' data/metrics/hourly_*.json | less
```

### Workflow 2: Model Comparison
```bash
# 1. Test with Model A (DEBUG mode)
OPENROUTER_MODEL=gpt-4
LOG_LEVEL=DEBUG
# ... run for 30min, note metrics file name ...

# 2. Test with Model B
OPENROUTER_MODEL=claude-3-opus
# ... run for 30min ...

# 3. Compare
jq '.detailed_requests | {avg_tps: (map(.tps) | add / length), avg_time: (map(.duration_ms) | add / length)}' modelA.json
jq '.detailed_requests | {avg_tps: (map(.tps) | add / length), avg_time: (map(.duration_ms) | add / length)}' modelB.json
```

### Workflow 3: Streaming vs Non-Streaming
```bash
# Check if streaming is actually slower
jq '.detailed_requests | group_by(.streaming) | map({
  type: (if .[0].streaming then "streaming" else "non-streaming" end),
  avg_tps: (map(.tps) | add / length),
  avg_time: (map(.duration_ms) | add / length),
  count: length
})' hourly_*.json
```

---

## 📊 What You Get

### In INFO Mode:
```
Logs: General operations, errors
Metrics: Aggregated stats every 60min
Detail: Basic performance numbers
```

### In DEBUG Mode:
```
Logs: EVERYTHING (TTFT, RAG searches, state changes)
Metrics: Detailed requests every 10min
Detail: Every request with full context
Format: Easy-to-query JSON
```

---

## 💡 Pro Tips

1. **Use DEBUG during optimization only** - Too verbose for production
2. **10 minutes is enough** - You'll have 6 snapshots per hour
3. **jq is your friend** - Learn basic jq queries for analysis
4. **Compare before/after** - Save metrics before and after changes
5. **Script your analysis** - Create custom queries for repeated analysis
6. **Clean up after** - Delete old DEBUG metrics when done optimizing

---

## 🎉 Summary

DEBUG mode gives you:
- ✅ **Automatic 10-minute saves** (vs manual or 60-minute)
- ✅ **Full request details** in easy-to-query JSON
- ✅ **5x more history** (500 vs 100 responses)
- ✅ **Per-request metrics** (TPS, TTFT, tokens, timing)
- ✅ **Context information** (RAG used, user, channel)
- ✅ **Perfect for optimization** - restart, test, analyze, repeat!

**Perfect for your use case**: Frequent restarts + detailed analysis + JSON format!
