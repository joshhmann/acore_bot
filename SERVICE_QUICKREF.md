# Service Quick Reference

Quick command reference for managing the Discord bot systemd service.

## Installation

```bash
# Make executable
chmod +x install_service.sh

# Install
sudo ./install_service.sh

# Start
sudo systemctl start discordbot
```

## Daily Commands

```bash
# Start bot
sudo systemctl start discordbot

# Stop bot
sudo systemctl stop discordbot

# Restart bot
sudo systemctl restart discordbot

# Check status
sudo systemctl status discordbot

# View logs (live)
sudo journalctl -u discordbot -f

# View recent logs
sudo journalctl -u discordbot -n 100
```

## Auto-Start

```bash
# Enable auto-start on boot (default)
sudo systemctl enable discordbot

# Disable auto-start
sudo systemctl disable discordbot

# Check if enabled
systemctl is-enabled discordbot
```

## Troubleshooting

```bash
# Check if running
systemctl is-active discordbot

# View full status
sudo systemctl status discordbot

# View all logs
sudo journalctl -u discordbot --no-pager

# View errors only
sudo journalctl -u discordbot -p err

# Check service file
sudo cat /etc/systemd/system/discordbot.service
```

## After Code Changes

```bash
# Restart to apply changes
sudo systemctl restart discordbot

# View logs to verify
sudo journalctl -u discordbot -f
```

## Uninstall

```bash
sudo ./uninstall_service.sh
```

## Common Issues

### Service won't start
```bash
# Check logs for errors
sudo journalctl -u discordbot -n 50

# Common fixes:
# - Check .env file exists
# - Verify FFmpeg installed
# - Ensure Ollama running
```

### Bot not responding
```bash
# Check if actually running
ps aux | grep python

# Restart
sudo systemctl restart discordbot
```

### Update bot code
```bash
# Pull latest code
git pull

# Restart service
sudo systemctl restart discordbot

# Monitor logs
sudo journalctl -u discordbot -f
```

---

**Full documentation:** [Service Scripts Guide](docs/setup/SERVICE_SCRIPTS.md)
