# Production Deployment Checklist

**For acore_bot v2.0+ - Enterprise-Ready Deployment**

This checklist ensures all production requirements are met before deploying acore_bot with advanced persona intelligence features.

---

## ✅ Pre-Deployment Checklist

### 1. **Environment Requirements**

**[ ] System Requirements**
- [ ] **CPU**: 4+ cores recommended (2+ minimum)
- [ ] **Memory**: 4GB+ RAM (8GB+ recommended)
- [ ] **Storage**: 20GB+ free space (includes model cache)
- [ ] **Network**: Stable internet connection for AI services
- [ ] **OS**: Linux (Ubuntu 20.04+, CentOS 8+, Debian 11+)

**[ ] Python Environment**
```bash
# Verify Python 3.11+
python3 --version  # Should be 3.11.x or higher

# Verify uv package manager
uv --version

# Verify dependencies installed
uv sync
```

**[ ] External Services**
- [ ] **Ollama**: Running and accessible (version 0.1.x+)
- [ ] **Models**: Required AI models downloaded and available
- [ ] **Discord Bot Token**: Valid bot token with proper permissions
- [ ] **Optional**: TTS/RVC services configured if using voice features

### 2. **Configuration Verification**

**[ ] Environment Variables (.env)**
```bash
# Core Configuration
DISCORD_TOKEN=your_bot_token_here
OLLAMA_BASE_URL=http://localhost:11434

# Production Features
ANALYTICS_DASHBOARD_ENABLED=true
ANALYTICS_DASHBOARD_PORT=8080
ANALYTICS_API_KEY=generate_secure_key_here
SEMANTIC_LOREBOOK_ENABLED=true
SEMANTIC_LOREBOOK_THRESHOLD=0.65

# Production Logging
LOG_FORMAT=json
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE_PATH=logs/bot.log

# Performance Settings
METRICS_ENABLED=true
METRICS_SAVE_INTERVAL_MINUTES=10
MEMORY_CLEANUP_INTERVAL_HOURS=24

# Security
ENABLE_CIRCUIT_BREAKER=true
MAX_RETRY_ATTEMPTS=3
```

**[ ] Directory Structure**
```bash
# Verify directories exist and have correct permissions
ls -la data/
ls -la logs/
ls -la prompts/
ls -la services/

# Permissions
chmod -R 755 data/
chmod -R 755 logs/
chmod -R 644 prompts/
```

**[ ] Persona Configuration**
```bash
# Verify persona files are valid JSON
for file in prompts/characters/*.json; do
    python3 -m json.tool "$file" > /dev/null && echo "✅ $file" || echo "❌ $file"
done

# Check for required fields
grep -l "display_name\|framework" prompts/characters/*.json
```

### 3. **Security Hardening**

**[ ] API Key Security**
```bash
# Generate secure API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Verify API key strength (32+ chars, alphanumeric)
echo "$ANALYTICS_API_KEY" | wc -c
```

**[ ] File Permissions**
```bash
# Secure sensitive files
chmod 600 .env
chmod 600 data/profiles/*/*.json

# Verify no world-writable files
find . -type f -perm /002 -ls
```

**[ ] Network Security**
```bash
# Firewall rules (if needed)
sudo ufw allow 8080/tcp  # Analytics dashboard
sudo ufw allow from 127.0.0.1 to any port 11434  # Ollama
```

**[ ] SSL/TLS (External Dashboard)**
- [ ] SSL certificate configured if dashboard exposed externally
- [ ] HTTPS redirect enabled
- [ ] Security headers configured

---

## ✅ Deployment Checklist

### 4. **Service Deployment**

**[ ] Systemd Service Setup**
```bash
# Verify service file exists
ls -la /etc/systemd/system/discordbot.service

# Verify service configuration
sudo systemctl cat discordbot.service

# Enable service
sudo systemctl enable discordbot.service

# Start service
sudo systemctl start discordbot.service
```

**[ ] Service Health Check**
```bash
# Check service status
sudo systemctl status discordbot.service

# Verify logs
sudo journalctl -u discordbot.service --no-pager -n 50

# Check for errors
sudo journalctl -u discordbot.service -p err --no-pager -n 20
```

**[ ] Bot Connectivity**
```bash
# Test Discord connection
curl -H "Authorization: Bot $DISCORD_TOKEN" https://discord.com/api/v10/users/@me

# Verify bot is online in Discord
# Bot should appear online in your Discord server
```

### 5. **Feature Verification**

**[ ] Core Bot Functions**
- [ ] **Chat**: `/chat test message` works
- [ ] **Persona Switching**: `/set_character dagoth_ur neuro` works
- [ ] **Help**: `/help` shows all commands
- [ ] **Status**: `/status` shows bot status

**[ ] Advanced Persona Features**
- [ ] **Mood System**: Bot responds to emotional context
- [ ] **Topic Interests**: Bot shows engagement for preferred topics
- [ ] **Memory Isolation**: Different personas have separate memories
- [ ] **Character Evolution**: Milestones track correctly

**[ ] Analytics Dashboard**
- [ ] **Dashboard Access**: http://localhost:8080 loads
- [ ] **API Key Auth**: Dashboard prompts for API key
- [ **Metrics Display**: Shows uptime, messages, users
- [ ] **Real-time Updates**: Metrics refresh every 2 seconds
- [ ] **Health Endpoint**: `/api/health` returns service status

**[ ] Production Infrastructure**
- [ ] **Structured Logging**: JSON format logs in logs/bot.log
- [ ] **Log Rotation**: Old logs compressed and rotated
- [ ] **Health Checks**: All services report healthy status
- [ ] **Error Handling**: Graceful error messages to users
- [ ] **Graceful Shutdown**: `systemctl stop discordbot` works cleanly

### 6. **Performance Validation**

**[ ] Resource Usage**
```bash
# Check memory usage
systemctl status discordbot.service  # Shows memory usage

# Check CPU usage
top -p $(pgrep -f "python main.py")

# Check disk usage
du -sh data/ logs/
```

**[ ] Response Time**
```bash
# Test chat response time
time (echo "/chat hello world" | nc -w 10 localhost 6667)

# Target: <2 seconds for simple responses
```

**[ ] Error Rate**
```bash
# Check error rate in logs
grep "ERROR" logs/bot.log | wc -l

# Target: <1% error rate
```

---

## ✅ Monitoring & Alerting

### 7. **Monitoring Setup**

**[ ] Log Monitoring**
```bash
# Set up log rotation (configured in service)
sudo logrotate -f /etc/logrotate.d/discordbot

# Monitor log file size
watch -n 60 'du -h logs/bot.log'
```

**[ ] Health Monitoring**
```bash
# Create health check script
cat > /usr/local/bin/check-acore-bot.sh << 'EOF'
#!/bin/bash
# Health check script for acore_bot

# Check service status
if ! systemctl is-active --quiet discordbot.service; then
    echo "CRITICAL: Discord bot service is not running"
    exit 2
fi

# Check dashboard health
if ! curl -sf http://localhost:8080/api/health > /dev/null; then
    echo "WARNING: Analytics dashboard not responding"
    exit 1
fi

echo "OK: All systems operational"
exit 0
EOF

chmod +x /usr/local/bin/check-acore-bot.sh

# Test health check
/usr/local/bin/check-acore-bot.sh
```

**[ ] Metrics Collection**
```bash
# Enable metrics collection
grep METRICS_ENABLED .env  # Should be true

# Check metrics file
ls -la data/metrics/
```

### 8. **Backup Strategy**

**[ ] Data Backup**
```bash
# Create backup script
cat > /usr/local/bin/backup-acore-bot.sh << 'EOF'
#!/bin/bash
# Backup script for acore_bot data

BACKUP_DIR="/opt/backups/acore-bot"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup critical data
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" data/
cp .env "$BACKUP_DIR/.env_$DATE"

# Keep last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name ".env_*" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/data_$DATE.tar.gz"
EOF

chmod +x /usr/local/bin/backup-acore-bot.sh

# Schedule daily backups
echo "0 2 * * * /usr/local/bin/backup-acore-bot.sh" | sudo crontab -
```

---

## ✅ Post-Deployment Checklist

### 9. **User Acceptance Testing**

**[ ] Feature Testing**
- [ ] All users can interact with the bot
- [ ] Persona switching works correctly
- [ ] Voice features (if enabled) work properly
- [ ] Analytics dashboard accessible to authorized users

**[ ] Performance Validation**
- [ ] Response times meet expectations (<2 seconds)
- [ ] Memory usage stable (no memory leaks)
- [ ] CPU usage reasonable (<50% on 4-core system)
- [ ] Disk space usage acceptable

**[ ] Error Handling**
- [ ] Graceful error messages for users
- [ ] No crash loops or service failures
- [ ] Appropriate logging for debugging
- [ ] Circuit breakers activate when needed

### 10. **Documentation Update**

**[ ] Update Documentation**
```bash
# Update deployment documentation with actual values
# - Server IP/hostname
# - Dashboard URL and API key
# - Specific configuration details
# - Contact information for support
```

**[ ] User Training**
- [ ] Users trained on new persona features
- [ ] Documentation provided for advanced features
- [ ] Support contact information distributed
- [ ] FAQ created for common issues

---

## ✅ Ongoing Maintenance

### 11. **Regular Maintenance Tasks**

**[ ] Daily (Automated)**
- [ ] Backups running successfully
- [ ] Log rotation working
- [ ] Health checks passing
- [ ] Disk space monitoring

**[ ] Weekly**
- [ ] Review error logs
- [ ] Check performance metrics
- [ ] Verify dashboard functionality
- [ ] Update security patches

**[ ] Monthly**
- [ ] Review and rotate API keys
- [ ] Update bot features/versions
- [ ] Clean up old log files
- [ ] Performance optimization review

**[ ] Quarterly**
- [ ] Security audit
- [ ] Backup restoration test
- [ ] Capacity planning review
- [ ] User feedback collection

### 12. **Troubleshooting Guide**

**[ ] Common Issues Resolution**
```bash
# Bot not responding
sudo systemctl restart discordbot.service

# High memory usage
sudo systemctl restart discordbot.service
# Consider reducing METRICS_SAVE_INTERVAL_MINUTES

# Dashboard not accessible
curl -H "X-API-Key: $ANALYTICS_API_KEY" http://localhost:8080/api/health

# Logs not rotating
sudo logrotate -f /etc/logrotate.d/discordbot
```

**[ ] Emergency Contacts**
- [ ] System administrator contact
- [ ] Discord bot developer contact
- [ ] Network administrator contact
- [ ] Security team contact

---

## ✅ Deployment Sign-Off

### Final Verification Checklist

**[ ] All pre-deployment items completed**
**[ ] All deployment items verified**
**[ ] All monitoring systems active**
**[ ] Backup strategy implemented**
**[ ] Documentation updated**
**[ ] User acceptance testing passed**
**[ ] Emergency procedures documented**

---

## 🎯 Deployment Complete!

**When all items are checked, your acore_bot deployment is production-ready with:**

- ✅ **19 advanced persona features** (63% of roadmap complete)
- ✅ **Enterprise-grade infrastructure** (health checks, logging, monitoring)
- ✅ **Production security** (API keys, error handling, graceful shutdown)
- ✅ **High availability** (backups, monitoring, maintenance procedures)
- ✅ **User-friendly operation** (analytics dashboard, comprehensive documentation)

**Next Steps:**
1. Monitor performance for first 24 hours
2. Collect user feedback
3. Plan Phase 3 feature implementation
4. Schedule regular maintenance

---

*Deployment Checklist Version: 2.0*
*Last Updated: 2025-12-12*
*Compatible with: acore_bot v2.0+*