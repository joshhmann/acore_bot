# Production Deployment Guide

**Last Updated**: 2025-12-12
**Status**: Production Ready
**Version**: 1.0.0

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Deployment Process](#deployment-process)
4. [Security Configuration](#security-configuration)
5. [Performance Tuning](#performance-tuning)
6. [Health Check Verification](#health-check-verification)
7. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements (Text-Only Mode)

```yaml
CPU: 2 cores (x86_64)
RAM: 2 GB
Disk: 10 GB free space
Network: 10 Mbps down/up
OS: Linux (Ubuntu 22.04+ recommended)
```

### Recommended Requirements (Full Features)

```yaml
CPU: 4+ cores (x86_64)
RAM: 8 GB (16 GB recommended)
Disk: 50 GB SSD
Network: 100 Mbps down/up
OS: Ubuntu 22.04 LTS or Debian 12
GPU: Optional (NVIDIA for RAG/embeddings acceleration)
```

### Software Dependencies

**Core:**
- Python 3.11 or higher
- uv (package manager)
- systemd (for service management)

**System Libraries:**
```bash
sudo apt update
sudo apt install -y \
    espeak-ng \
    ffmpeg \
    git \
    build-essential \
    python3-dev
```

**External Services:**
- Discord Bot Token (required)
- Ollama server (if using local LLM)
- Kokoro-FastAPI (if using TTS)
- RVC WebUI (if using voice conversion)

---

## Pre-Deployment Checklist

### Infrastructure Verification

- [ ] Server meets minimum requirements
- [ ] Firewall allows outbound HTTPS (443) for Discord API
- [ ] Port 8080 available (if using analytics dashboard)
- [ ] System time synchronized (NTP configured)
- [ ] Disk space monitoring configured
- [ ] Log rotation configured

### Application Preparation

- [ ] Git repository cloned to deployment directory
- [ ] `.env` file created from `.env.example`
- [ ] `DISCORD_TOKEN` set in `.env`
- [ ] LLM provider configured (Ollama or OpenRouter)
- [ ] Required directories exist (`data/`, `logs/`, `prompts/`)
- [ ] File permissions correct (user has read/write access)

### Security Verification

- [ ] API keys stored securely in `.env` (never in git)
- [ ] `.env` file permissions set to 600 (`chmod 600 .env`)
- [ ] Log security sanitization enabled (`LOG_LEVEL=INFO` in production)
- [ ] `ANALYTICS_API_KEY` changed from default
- [ ] No hardcoded secrets in codebase

### Dependency Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Install project dependencies
cd /path/to/acore_bot
uv sync
```

### Configuration Validation

```bash
# Test configuration loading
uv run python -c "from config import Config; Config.validate(); print('✓ Config valid')"

# Expected output: ✓ Config valid
```

---

## Deployment Process

### Step 1: Prepare Deployment Directory

```bash
# Clone repository
git clone https://github.com/yourusername/acore_bot.git /opt/acore_bot
cd /opt/acore_bot

# Create environment file
cp .env.example .env
nano .env  # Configure required settings
```

### Step 2: Configure Environment Variables

Edit `.env` with production values:

```bash
# Critical Settings
DISCORD_TOKEN=your_discord_bot_token_here
LLM_PROVIDER=ollama  # or openrouter

# Ollama Configuration (if using)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# OpenRouter Configuration (if using)
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Logging (Production)
LOG_LEVEL=INFO
LOG_FORMAT=json  # Use JSON for production log parsing
LOG_TO_FILE=true
LOG_COMPRESS=true

# Security
ANALYTICS_API_KEY=your_secure_random_key_here  # CHANGE THIS!

# Features
RAG_ENABLED=true
USER_PROFILES_ENABLED=true
WEB_SEARCH_ENABLED=true
CONVERSATION_SUMMARIZATION_ENABLED=true

# Performance
LLM_CACHE_ENABLED=true
RESPONSE_STREAMING_ENABLED=true
MEMORY_CLEANUP_ENABLED=true
```

See [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md) for complete reference.

### Step 3: Install System Dependencies

```bash
# Run as root/sudo
sudo bash install_service.sh
```

This automatically:
- Installs espeak-ng, ffmpeg, git
- Creates virtual environment with uv
- Sets up systemd service
- Configures auto-start on boot

### Step 4: Verify Installation

```bash
# Check service status
sudo systemctl status discordbot

# View startup logs
sudo journalctl -u discordbot -n 100 --no-pager

# Look for successful startup message:
# "Bot logged in successfully"
# "21 services initialized"
# "ChatCog loaded"
```

### Step 5: Enable and Start Service

```bash
# Enable auto-start on boot
sudo systemctl enable discordbot

# Start service
sudo systemctl start discordbot

# Verify running
sudo systemctl is-active discordbot
# Expected: active
```

### Step 6: Monitor Initial Startup

```bash
# Watch logs in real-time
sudo journalctl -u discordbot -f

# Expected startup sequence:
# 1. Config validation
# 2. ServiceFactory initialization (21 services)
# 3. Cog loading (12 cogs)
# 4. Command tree sync
# 5. Bot login
# 6. "Bot is ready!" message
```

### Step 7: Test Basic Functionality

In Discord:

```
# Test bot response
@YourBot hello

# Expected: Bot responds with greeting

# Test slash command
/help

# Expected: Command menu appears

# Test health check (if analytics dashboard enabled)
curl http://localhost:8080/health

# Expected: {"status": "healthy", ...}
```

---

## Security Configuration

### File Permissions

```bash
# Set .env permissions (critical)
chmod 600 .env

# Set data directory permissions
chmod 700 data/
chmod 700 logs/

# Set script permissions
chmod +x install_service.sh
chmod +x uninstall_service.sh
```

### Systemd Security Hardening

The service file includes basic hardening. For additional security, edit `/etc/systemd/system/discordbot.service`:

```ini
[Service]
# Existing settings...

# Additional hardening
ProtectSystem=strict
ReadWritePaths=/opt/acore_bot/data /opt/acore_bot/logs
ProtectHome=true
ProtectKernelLogs=true
RestrictAddressFamilies=AF_INET AF_INET6
```

Then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart discordbot
```

See [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) for complete guide.

### Log Security

Our recent security fix (Task A1) ensures:
- ✓ File paths sanitized in production logs
- ✓ API keys redacted from exception messages
- ✓ Database connection strings sanitized
- ✓ No full tracebacks in production (INFO/WARNING/ERROR levels)
- ✓ Full tracebacks only in DEBUG mode

Production logging is safe by default when `LOG_LEVEL=INFO`.

### API Key Management

**Never commit API keys to git:**

```bash
# Verify .gitignore includes .env
cat .gitignore | grep ".env"
# Expected: .env

# Check for accidentally committed secrets
git log --all --full-history -- .env
# Expected: (empty - no results)
```

---

## Performance Tuning

### Memory Optimization

**For 2GB RAM servers:**

```bash
# In .env
CHAT_HISTORY_MAX_MESSAGES=50
CONTEXT_MESSAGE_LIMIT=10
LLM_CACHE_MAX_SIZE=500
RAG_ENABLED=false  # Disable RAG to save 1GB RAM
ANALYTICS_DASHBOARD_ENABLED=false
```

**For 8GB+ RAM servers (recommended):**

```bash
# In .env
CHAT_HISTORY_MAX_MESSAGES=100
CONTEXT_MESSAGE_LIMIT=20
LLM_CACHE_MAX_SIZE=1000
RAG_ENABLED=true
ANALYTICS_DASHBOARD_ENABLED=true
```

### CPU Usage

```bash
# Limit response streaming for CPU-constrained servers
USE_STREAMING_FOR_LONG_RESPONSES=false

# Adjust typing delays (lower = less CPU idle time)
TYPING_INDICATOR_MIN_DELAY=0.3
TYPING_INDICATOR_MAX_DELAY=1.0
```

### Database Performance (RAG)

```bash
# Tune RAG cache size (affects memory vs speed tradeoff)
SEMANTIC_LOREBOOK_CACHE_SIZE=1000  # Default

# For low-memory servers
SEMANTIC_LOREBOOK_CACHE_SIZE=500

# For high-performance servers
SEMANTIC_LOREBOOK_CACHE_SIZE=2000
```

### Network Optimization

```bash
# Increase timeouts for slow connections
OPENROUTER_TIMEOUT=300
OPENROUTER_STREAM_TIMEOUT=300

# Decrease timeouts for fast connections
OPENROUTER_TIMEOUT=60
OPENROUTER_STREAM_TIMEOUT=60
```

See [PERFORMANCE_OPTIMIZATION.md](./PERFORMANCE_OPTIMIZATION.md) for detailed tuning guide.

---

## Health Check Verification

### Built-In Health Checks

The bot includes comprehensive health monitoring (Task T10).

**Check all services:**

```bash
# If analytics dashboard enabled
curl http://localhost:8080/health | jq

# Expected output:
{
  "status": "healthy",
  "timestamp": "2025-12-12T10:30:00",
  "services": {
    "llm": {"status": "healthy", "response_time": 45.2},
    "tts": {"status": "healthy", "response_time": 12.5},
    "rvc": {"status": "degraded", "details": "optional service not enabled"},
    "rag": {"status": "healthy", "details": "109 documents loaded"},
    "memory": {"status": "healthy", "details": "All directories accessible"},
    "analytics": {"status": "healthy", "details": "Dashboard running on port 8080"}
  },
  "summary": {
    "total": 6,
    "healthy": 4,
    "degraded": 2,
    "unhealthy": 0
  }
}
```

**Check critical services only (readiness):**

```bash
curl http://localhost:8080/health/ready | jq

# Expected output:
{
  "ready": true,
  "timestamp": "2025-12-12T10:30:00",
  "critical_services": {
    "llm": {"status": "healthy", ...},
    "memory": {"status": "healthy", ...}
  }
}
```

**Simple alive check:**

```bash
curl http://localhost:8080/health/live

# Expected output:
{
  "status": "healthy",
  "timestamp": "2025-12-12T10:30:00",
  "message": "Service is alive"
}
```

### Manual Verification

**Check service status:**

```bash
sudo systemctl status discordbot
# Expected: Active: active (running)
```

**Check process:**

```bash
ps aux | grep "python main.py"
# Expected: process running as configured user
```

**Check memory usage:**

```bash
sudo systemctl status discordbot | grep Memory
# Expected: Memory: 512MB - 2GB (depending on features)
```

**Check logs for errors:**

```bash
sudo journalctl -u discordbot -p err -n 50
# Expected: (empty or no recent errors)
```

### Monitoring Dashboard

If analytics dashboard enabled, access at:

```
http://your-server-ip:8080/dashboard
```

Provides real-time metrics:
- Message counts by persona
- LLM response times (avg/p95/p99)
- Token usage statistics
- Error spike detection
- Active users/channels

See [MONITORING_SETUP.md](./MONITORING_SETUP.md) for configuration.

---

## Troubleshooting

### Service Fails to Start

**Check logs:**

```bash
sudo journalctl -u discordbot -n 100 --no-pager
```

**Common issues:**

1. **Missing DISCORD_TOKEN**
   ```
   Error: DISCORD_TOKEN is required
   ```
   **Fix:** Set `DISCORD_TOKEN` in `.env` file

2. **Ollama not running**
   ```
   Error: Failed to connect to Ollama at http://localhost:11434
   ```
   **Fix:** Start Ollama service
   ```bash
   sudo systemctl start ollama
   sudo systemctl enable ollama
   ```

3. **Port already in use (analytics dashboard)**
   ```
   Error: Address already in use (port 8080)
   ```
   **Fix:** Change port or disable dashboard
   ```bash
   # In .env
   ANALYTICS_DASHBOARD_PORT=8081
   # OR
   ANALYTICS_DASHBOARD_ENABLED=false
   ```

4. **Permission denied errors**
   ```
   PermissionError: [Errno 13] Permission denied: 'data/'
   ```
   **Fix:** Fix directory ownership
   ```bash
   sudo chown -R yourusername:yourusername /opt/acore_bot
   chmod 700 data/ logs/
   ```

### Bot Not Responding in Discord

**Check bot is online:**
- Bot should appear online in Discord server member list
- If offline, check service is running: `sudo systemctl status discordbot`

**Check intents enabled:**
- Go to Discord Developer Portal > Your Bot > Bot Settings
- Enable "MESSAGE CONTENT INTENT"
- Enable "SERVER MEMBERS INTENT"
- Enable "PRESENCE INTENT"

**Check bot has permissions:**
- Verify bot role has "Send Messages", "Read Messages", "Use Slash Commands"

### High Memory Usage

**Check current usage:**

```bash
sudo systemctl status discordbot | grep Memory
```

**If over 2GB:**

1. Disable RAG: `RAG_ENABLED=false` in `.env`
2. Reduce cache: `LLM_CACHE_MAX_SIZE=500`
3. Reduce history: `CHAT_HISTORY_MAX_MESSAGES=50`
4. Disable analytics: `ANALYTICS_DASHBOARD_ENABLED=false`

**Restart after changes:**

```bash
sudo systemctl restart discordbot
```

### Slow Response Times

**Check LLM health:**

```bash
curl http://localhost:8080/health | jq '.services.llm'
```

**If response_time > 5000ms:**

1. Check Ollama/OpenRouter connectivity
2. Switch to faster model (e.g., llama3.2:3b instead of llama3.2:70b)
3. Enable caching: `LLM_CACHE_ENABLED=true`
4. Reduce max tokens: `OLLAMA_MAX_TOKENS=300`

### Logs Not Appearing

**Check log file exists:**

```bash
ls -lh logs/bot.log
```

**Check log permissions:**

```bash
# Should be writable by service user
chmod 644 logs/bot.log
```

**View systemd journal instead:**

```bash
sudo journalctl -u discordbot -f
```

### Service Crashes Repeatedly

**Check restart loop:**

```bash
sudo systemctl status discordbot
# Look for: "Start request repeated too quickly"
```

**View crash logs:**

```bash
sudo journalctl -u discordbot -p err -n 200
```

**Common crash causes:**

1. Invalid configuration (run: `uv run python -c "from config import Config; Config.validate()"`)
2. Missing dependencies (run: `uv sync`)
3. Corrupted data files (backup and remove `data/` directory)
4. Out of memory (reduce memory usage as above)

**Disable auto-restart temporarily to debug:**

```bash
sudo systemctl edit discordbot
# Add:
[Service]
Restart=no

# Save, then restart
sudo systemctl daemon-reload
sudo systemctl restart discordbot
```

---

## Next Steps

After successful deployment:

1. ✅ Review [MONITORING_SETUP.md](./MONITORING_SETUP.md) for ongoing monitoring
2. ✅ Review [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) for additional security
3. ✅ Review [PERFORMANCE_OPTIMIZATION.md](./PERFORMANCE_OPTIMIZATION.md) for tuning
4. ✅ Set up automated backups of `data/` directory
5. ✅ Configure alerting for service failures
6. ✅ Schedule regular security updates

---

## Related Documentation

- [Environment Configuration](./ENVIRONMENT_CONFIGURATION.md) - Complete environment variable reference
- [Deployment Checklist](./DEPLOYMENT_CHECKLIST.md) - Step-by-step deployment validation
- [Security Hardening](./SECURITY_HARDENING.md) - Advanced security configuration
- [Performance Optimization](./PERFORMANCE_OPTIMIZATION.md) - Detailed tuning guide
- [Monitoring Setup](./MONITORING_SETUP.md) - Metrics and alerting configuration
- [Production Readiness](./PRODUCTION_READINESS.md) - Pre-deployment validation report

---

**Questions?** Check our [GitHub Issues](https://github.com/yourusername/acore_bot/issues) or [Contributing Guide](../CONTRIBUTING.md).
