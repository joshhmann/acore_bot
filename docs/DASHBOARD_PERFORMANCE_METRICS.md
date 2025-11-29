# Dashboard Performance Metrics

## Overview

The web dashboard now displays real-time OpenRouter/Ollama performance metrics that update automatically.

---

## 📊 Performance Metrics Card

Located on the main dashboard at `http://your-bot:5000/`

### Displayed Metrics:

1. **Last Response Time**
   - Format: `X.XXs (XXXXms)`
   - Shows the most recent API request duration
   - **Color Coding:**
     - 🟢 Green: < 5 seconds (Excellent)
     - 🟡 Yellow: 5-10 seconds (Acceptable)
     - 🔴 Red: > 10 seconds (Slow)

2. **Tokens/Second (TPS)**
   - Format: `XX.X`
   - Shows generation speed (tokens per second)
   - **Color Coding:**
     - 🟢 Green: > 30 TPS (Fast)
     - 🟡 Yellow: 15-30 TPS (Normal)
     - 🔴 Red: < 15 TPS (Slow)

3. **Avg Response Time**
   - Format: `X.XXs (XXXXms)`
   - Rolling average of all requests since bot started

4. **Total Requests**
   - Number of API requests made since bot started

5. **Total Tokens Generated**
   - Total number of tokens generated (with thousands separator)
   - Example: `45,287`

---

## 🎨 Visual Indicators

The dashboard uses color-coded status indicators:

- **🟢 Green (status-ok)**: Performance is good
- **🟡 Yellow (status-warn)**: Performance is acceptable but could be better
- **🔴 Red (status-err)**: Performance needs attention

---

## 🔄 Auto-Refresh

The dashboard automatically refreshes every **2 seconds**, showing real-time performance data.

---

## 📈 What to Look For

### Good Performance:
```
Last Response Time: 3.2s (3200ms) [GREEN]
Tokens/Second: 45.8 [GREEN]
Avg Response Time: 3.5s (3500ms)
Total Requests: 156
Total Tokens Generated: 12,487
```

### Needs Optimization:
```
Last Response Time: 12.8s (12800ms) [RED]
Tokens/Second: 8.3 [RED]
Avg Response Time: 11.2s (11200ms)
Total Requests: 89
Total Tokens Generated: 5,234
```

---

## 🛠️ Troubleshooting Poor Performance

If you see RED indicators frequently:

1. **Check Model Size**
   - Larger models (70B+) are naturally slower
   - Consider switching to a faster model

2. **Check Context Length**
   - Long conversation histories slow down responses
   - Reduce `CHAT_HISTORY_MAX_MESSAGES` in config

3. **Check Network**
   - Slow connection to OpenRouter
   - Try different network or VPN

4. **Check OpenRouter Status**
   - Visit: https://status.openrouter.ai
   - Service might be experiencing issues

5. **Check Max Tokens**
   - Lower `OLLAMA_MAX_TOKENS` to reduce generation time
   - Shorter responses = faster completion

---

## 📊 Benchmark Examples

Typical performance for different scenarios:

### Fast Model (Mixtral 8x7B):
- Response Time: 2-4s
- TPS: 50-70
- Color: Mostly GREEN

### Medium Model (Claude 3 Sonnet):
- Response Time: 4-7s
- TPS: 30-50
- Color: GREEN to YELLOW

### Large Model (GPT-4 Turbo):
- Response Time: 3-5s
- TPS: 40-60
- Color: GREEN

### Very Large Model (Claude 3 Opus, Llama 70B):
- Response Time: 5-12s
- TPS: 20-40
- Color: YELLOW to RED

---

## 🔍 Other Dashboard Sections

The dashboard also shows:

### AI Configuration:
- LLM Provider (OpenRouter/Ollama)
- Active Model
- TTS Engine
- Voice
- RVC Status

### Current Status:
- Bot Status (Online)
- Uptime (days, hours, minutes, seconds)
- Latency to Discord API

### Bot Stats:
- Guilds (servers)
- Total users
- Active voice connections

### Cache Performance:
- History cache hit rate
- RAG cache hit rate

### Activity Stats:
- Active users
- Messages processed
- Commands executed

---

## 💡 Pro Tips

1. **Monitor Trends**: Watch the average response time over hours/days
2. **Compare Models**: Test different models and compare TPS
3. **Optimize During Peak Hours**: If performance degrades at certain times, it might be OpenRouter load
4. **Use Historical Data**: Check `/root/acore_bot/data/metrics/` for detailed historical analysis

---

## 🎯 Quick Health Check

**Dashboard Shows:**
- ✅ Green Last Response Time + Green TPS = **Excellent**
- ⚠️ Yellow on either = **Monitor, consider optimization**
- ❌ Red on either = **Needs immediate attention**

---

## 📖 Related Documentation

- `/root/acore_bot/PERFORMANCE_TRACKING_SUMMARY.md` - Full performance tracking guide
- `/root/acore_bot/docs/METRICS_LOGGING.md` - Metrics logging documentation
- Web Dashboard: `http://your-bot-ip:5000/`

---

## 🎉 Summary

The dashboard now provides **real-time visibility** into:
- ⏱️ How fast your bot responds
- 🚀 How quickly it generates tokens
- 📊 Overall performance trends
- 🎯 Easy-to-understand color coding

No need to dig through logs - just open the dashboard and see performance at a glance!
