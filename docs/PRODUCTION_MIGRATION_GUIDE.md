# Production Migration Guide

**For acore_bot v2.0+ with Phase 1-2 Persona Enhancements**

This guide helps you migrate existing acore_bot deployments to the latest production-ready version with comprehensive persona intelligence features.

---

## 📋 Migration Checklist

### ✅ Pre-Migration Requirements

**1. Backup Current Data**
```bash
# Backup all character configurations
cp -r data/prompts/characters/ data/prompts/characters.backup/

# Backup user profiles and memories
cp -r data/profiles/ data/profiles.backup/

# Backup conversation history
cp -r data/history/ data/history.backup/

# Export current configuration
cp .env .env.backup
```

**2. Verify Dependencies**
```bash
# Update dependencies
uv sync

# Install type stubs (recommended)
uv add --dev types-aiofiles types-psutil

# Verify bot runs
uv run python main.py --version
```

**3. Check Disk Space**
- **Required**: 2GB additional space for new features
- **Models**: Sentence-transformers cache (~1GB)
- **Logs**: Structured logging (~500MB for rotation)
- **Profiles**: Persona-scoped memory (will increase storage)

---

## 🚀 Migration Steps

### Step 1: Update Configuration

**Add New Environment Variables to `.env`:**
```env
# Phase 1-2 Features
SEMANTIC_LOREBOOK_ENABLED=true
SEMANTIC_LOREBOOK_THRESHOLD=0.65

# Analytics Dashboard (T23-T24)
ANALYTICS_DASHBOARD_ENABLED=true
ANALYTICS_DASHBOARD_PORT=8080
ANALYTICS_API_KEY=your_secure_api_key_here

# Production Logging (T9)
LOG_FORMAT=json  # or "text" for development
LOG_LEVEL=INFO

# Performance Optimization
METRICS_ENABLED=true
METRICS_SAVE_INTERVAL_MINUTES=10

# Voice Features (if used)
VOICE_ACTIVITY_DETECTION_ENABLED=false
```

**Update Existing Configurations:**
```env
# Enhanced memory system
MEMORY_CLEANUP_INTERVAL_HOURS=24

# Improved error handling
ENABLE_CIRCUIT_BREAKER=true
MAX_RETRY_ATTEMPTS=3
```

### Step 2: Migrate Persona Profiles

**Run Migration Script:**
```bash
# This creates persona-scoped memory directories
uv run python scripts/migrate_persona_profiles.py

# Verify migration
ls data/profiles/  # Should show persona_id/user_id.json structure
```

**Manual Persona Updates (if needed):**
```json
// Example: Update dagoth_ur.json with new features
{
  "display_name": "Dagoth Ur",
  "framework": "neuro",

  // NEW: Phase 1 Features
  "mood_state": {
    "current_mood": "neutral",
    "mood_sensitivity": 0.7
  },

  "verbosity_by_context": {
    "quick_reply": 75,
    "casual_chat": 150,
    "detailed_question": 300,
    "storytelling": 450
  },

  "curiosity_level": "medium",

  "topic_interests": ["gaming", "lore", "philosophy"],
  "topic_avoidances": ["politics", "religion"],

  // NEW: Phase 2 Features
  "evolution_stages": {
    "milestone_messages": [50, 100, 500, 1000, 5000],
    "current_stage": 0
  },

  "activity_preferences": {
    "gaming": ["The Elder Scrolls", "RPG"],
    "watching": ["Fantasy", "Sci-Fi"]
  },

  "framework_blend_rules": {
    "emotional": {"caring": 0.3, "assistant": 0.7},
    "analytical": {"neuro": 0.8, "assistant": 0.2}
  },

  "emotional_contagion": {
    "enabled": true,
    "sensitivity": 0.5
  }
}
```

### Step 3: Deploy Analytics Dashboard

**Optional but Recommended:**
```bash
# Enable dashboard in systemd
sudo systemctl restart discordbot

# Verify dashboard is running
curl -H "X-API-Key: your_api_key" http://localhost:8080/api/health

# Access dashboard at: http://localhost:8080
```

### Step 4: Update Systemd Service

**Enhanced systemd service file:**
```ini
[Unit]
Description=Discord AI Bot with Ollama
After=network.target

[Service]
Type=exec
User=discord
WorkingDirectory=/opt/acore_bot
Environment=PATH=/opt/acore_bot/.venv/bin
ExecStart=/opt/acore_bot/.venv/bin/uv run python main.py
Restart=always
RestartSec=10

# Resource Limits
MemoryMax=2G
CPUQuota=80%

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/acore_bot/data /opt/acore_bot/logs

[Install]
WantedBy=multi-user.target
```

**Apply Changes:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart discordbot
```

---

## 🔧 Post-Migration Verification

### 1. Bot Functionality Tests

**Basic Operations:**
```bash
# Test chat functionality
/chat Hello, how are you?

# Test persona switching
/set_character dagoth_ur neuro

# Test ambient mode
/ambient status

# Check analytics
/metrics
```

**Advanced Features:**
```bash
# Test semantic lorebook (if enabled)
/chat Tell me about the Sixth House

# Test character evolution (check milestones)
/my_profile

# Test mood contagion
/chat I'm feeling really sad today
```

### 2. Health Checks

**Service Health:**
```bash
# Check all services
curl http://localhost:8080/api/health

# Detailed health report
curl http://localhost:8080/api/health/detailed

# Production readiness
curl http://localhost:8080/api/health/ready
```

### 3. Log Verification

**Structured JSON Logs:**
```bash
# Check logs are in JSON format
tail -10 logs/bot.log | jq .

# Verify trace IDs are working
grep "trace_id" logs/bot.log | head -5
```

### 4. Memory Structure

**Persona-Scoped Profiles:**
```bash
# Verify profile structure
ls -la data/profiles/

# Should see: persona_id/user_id.json structure
# Example: dagoth_ur/123456789.json
```

---

## 🚨 Troubleshooting

### Common Issues

**1. Bot Won't Start**
```bash
# Check logs
journalctl -u discordbot --no-pager -n 50

# Common fixes:
# - Missing environment variables
# - Corrupted profile files
# - Outdated dependencies
```

**2. Persona Memory Issues**
```bash
# Check profile permissions
ls -la data/profiles/
chmod -R 755 data/profiles/

# Re-run migration if needed
uv run python scripts/migrate_persona_profiles.py --force
```

**3. Analytics Dashboard Problems**
```bash
# Check API key
grep ANALYTICS_API_KEY .env

# Verify port availability
netstat -tulpn | grep 8080

# Check dashboard logs
journalctl -u discordbot | grep dashboard
```

**4. Performance Issues**
```bash
# Monitor memory usage
systemctl status discordbot

# Check metrics
/metrics  # Discord command

# Reduce load if needed:
# - Disable semantic lorebook: SEMANTIC_LOREBOOK_ENABLED=false
# - Increase cache TTL: Set higher values in config
```

### Migration Rollback

**If Issues Occur:**
```bash
# Stop bot
sudo systemctl stop discordbot

# Restore from backup
cp -r data/prompts/characters.backup/* data/prompts/characters/
cp -r data/profiles.backup/* data/profiles/
cp .env.backup .env

# Restart
sudo systemctl start discordbot
```

---

## 📊 Migration Impact

### Storage Requirements
- **Before**: ~500MB for profiles and history
- **After**: ~2GB total (includes models, logs, persona memory)

### Performance Changes
- **CPU**: +15-20% (semantic processing, analytics)
- **Memory**: +200-400MB (model loading, caching)
- **Response Time**: +10-50ms (semantic features)

### New Capabilities
- ✅ 19 advanced persona behaviors
- ✅ Real-time analytics dashboard
- ✅ Structured production logging
- ✅ Graceful error recovery
- ✅ Health monitoring
- ✅ Memory isolation per persona

---

## 🎯 Success Criteria

**Migration Complete When:**
- [ ] Bot starts without errors
- [ ] All existing commands work
- [ ] New persona features functional
- [ ] Analytics dashboard accessible
- [ ] Logs structured and readable
- [ ] Health checks passing
- [ ] Performance within acceptable range
- [ ] Memory structure correctly migrated

---

## 🆘 Support

**For Migration Issues:**
1. Check this guide first
2. Review logs for specific errors
3. Check GitHub issues for known problems
4. Create issue with:
   - Error logs
   - Configuration details
   - Steps to reproduce

**Performance Tuning:**
- Adjust `SEMANTIC_LOREBOOK_THRESHOLD` (0.6-0.8)
- Tune `MEMORY_CLEANUP_INTERVAL_HOURS` (6-24)
- Modify `METRICS_SAVE_INTERVAL_MINUTES` (5-30)
- Disable unused features to reduce resource usage

---

**Migration Complete!** 🎉

Your acore_bot now has enterprise-grade persona intelligence with production monitoring, structured logging, and graceful error handling.

*Last Updated: 2025-12-12*
*Version: 2.0+*