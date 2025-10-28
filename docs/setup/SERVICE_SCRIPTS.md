# Service Installation Scripts

Quick scripts to install the Discord bot as a systemd service on Linux.

## Quick Start

```bash
# Make script executable
chmod +x install_service.sh

# Install and enable service
sudo ./install_service.sh

# Start the bot
sudo systemctl start discordbot

# Check status
sudo systemctl status discordbot
```

## Installation Script

**File:** `install_service.sh`

This script automatically:
1. Detects your bot directory and virtual environment
2. Creates a systemd service file at `/etc/systemd/system/discordbot.service`
3. Enables the service to start on boot
4. Configures proper user permissions
5. Sets up automatic restart on failure

### What It Creates

The service file includes:
- **Description:** Discord AI Bot with Ollama
- **User:** Your current user (preserves file permissions)
- **Working Directory:** Your bot directory
- **Python Path:** Uses your `.venv311` virtual environment
- **Auto-restart:** Restarts if the bot crashes (10 second delay)
- **Ollama dependency:** Waits for Ollama service to be ready
- **Security:** NoNewPrivileges and PrivateTmp enabled

### Requirements

- Linux with systemd (Ubuntu, Debian, CentOS, etc.)
- Virtual environment at `.venv311/`
- Python 3.11+
- Sudo access

### Usage

```bash
# Install service
sudo ./install_service.sh

# Output:
# ==========================================
# Discord Bot Service Installer
# ==========================================
#
# Bot directory: /home/user/acore_bot
# Python path: /home/user/acore_bot/.venv311/bin/python
# Service user: user
#
# Creating systemd service file...
# Service file created at: /etc/systemd/system/discordbot.service
#
# Reloading systemd daemon...
# Enabling service to start on boot...
#
# ==========================================
# Installation Complete!
# ==========================================
```

## Uninstallation Script

**File:** `uninstall_service.sh`

This script:
1. Stops the running service
2. Disables the service from starting on boot
3. Removes the systemd service file
4. Reloads systemd daemon

**Note:** Your bot code and data remain intact - only the service is removed.

### Usage

```bash
# Uninstall service
sudo ./uninstall_service.sh

# Output:
# ==========================================
# Discord Bot Service Uninstaller
# ==========================================
#
# Stopping service...
# Disabling service...
# Removing service file...
# Reloading systemd daemon...
#
# ==========================================
# Uninstallation Complete!
# ==========================================
```

## Managing the Service

After installation, use standard systemd commands:

### Start/Stop

```bash
# Start bot
sudo systemctl start discordbot

# Stop bot
sudo systemctl stop discordbot

# Restart bot
sudo systemctl restart discordbot
```

### Status and Logs

```bash
# Check status
sudo systemctl status discordbot

# View live logs
sudo journalctl -u discordbot -f

# View last 100 lines
sudo journalctl -u discordbot -n 100

# View logs since boot
sudo journalctl -u discordbot -b
```

### Enable/Disable Auto-Start

```bash
# Enable start on boot (done automatically by install script)
sudo systemctl enable discordbot

# Disable start on boot
sudo systemctl disable discordbot

# Check if enabled
sudo systemctl is-enabled discordbot
```

## Service File Location

**Path:** `/etc/systemd/system/discordbot.service`

You can view or manually edit it:
```bash
# View service file
sudo cat /etc/systemd/system/discordbot.service

# Edit service file
sudo nano /etc/systemd/system/discordbot.service

# After editing, reload:
sudo systemctl daemon-reload
sudo systemctl restart discordbot
```

## Troubleshooting

### Script Says "Virtual environment not found"

**Problem:**
```
ERROR: Virtual environment not found at /path/to/.venv311
```

**Solution:**
```bash
# Create virtual environment first
python3 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
```

### Service Fails to Start

**Check logs:**
```bash
# View detailed error messages
sudo journalctl -u discordbot -n 50 --no-pager
```

**Common issues:**
1. **Missing .env file** - Create `.env` with your Discord token
2. **Ollama not running** - Start with `sudo systemctl start ollama`
3. **Permission denied** - Check file permissions with `ls -la`

### Service Starts but Bot Not Responding

**Check if bot is actually running:**
```bash
# Check process
ps aux | grep python

# Check logs for errors
sudo journalctl -u discordbot -f
```

### Change Service User

Edit the service file:
```bash
sudo nano /etc/systemd/system/discordbot.service

# Change this line:
User=your_username

# To your desired user:
User=different_user

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart discordbot
```

### Reinstall Service

If something goes wrong:
```bash
# Uninstall old service
sudo ./uninstall_service.sh

# Reinstall fresh
sudo ./install_service.sh
```

## Advanced Configuration

### Custom Virtual Environment Path

If you use a different venv name, edit the script:
```bash
# Edit install_service.sh
nano install_service.sh

# Change this line:
VENV_PATH="$BOT_DIR/.venv311"

# To your venv path:
VENV_PATH="$BOT_DIR/.venv"
```

### Custom Service Name

To use a different service name:
```bash
# Edit both scripts
nano install_service.sh
nano uninstall_service.sh

# Change:
SERVICE_NAME="discordbot"

# To:
SERVICE_NAME="mybot"
```

### Resource Limits

Add resource limits to the service file:
```bash
sudo nano /etc/systemd/system/discordbot.service

# Add under [Service]:
MemoryLimit=2G
CPUQuota=100%
```

### Environment Variables

Add environment variables directly to service:
```bash
sudo nano /etc/systemd/system/discordbot.service

# Add under [Service]:
Environment="DISCORD_TOKEN=your_token"
Environment="TTS_ENGINE=kokoro"
```

**Note:** Still recommended to use `.env` file instead for security.

## Security

The service includes security hardening:
- **NoNewPrivileges=true** - Prevents privilege escalation
- **PrivateTmp=true** - Isolates /tmp directory
- **User=** - Runs as non-root user

Additional hardening options:
```ini
[Service]
# Read-only access to most of the system
ProtectSystem=strict
ReadWritePaths=/path/to/acore_bot

# Private /home, /root, and /run/user directories
ProtectHome=true

# Deny access to kernel logs
ProtectKernelLogs=true

# Restrict network access (if bot doesn't need outbound)
RestrictAddressFamilies=AF_INET AF_INET6
```

## Monitoring

### Check if service is running

```bash
# Quick check
systemctl is-active discordbot

# Detailed status
sudo systemctl status discordbot

# Check uptime
sudo systemctl show discordbot --property=ActiveEnterTimestamp
```

### Monitor resource usage

```bash
# Real-time resource usage
sudo systemd-cgtop

# Service-specific resources
sudo systemctl status discordbot | grep -E "Memory|CPU"
```

### Automatic restart on crash

The service automatically restarts if it crashes:
```ini
Restart=on-failure
RestartSec=10
```

This means if the bot crashes, it will restart after 10 seconds.

## Related Documentation

- [VM Setup Guide](VM_SETUP.md) - Complete Linux VM setup
- [Deploy Guide](../../DEPLOY.md) - Quick deployment steps
- [README](../../README.md) - Main project documentation

---

**Need help?** Open an issue on GitHub!
