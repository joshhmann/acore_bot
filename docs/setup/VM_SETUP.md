# VM Setup Guide

Quick setup guide for running the bot on a Linux VM.

## Prerequisites

- Ubuntu/Debian Linux VM
- Python 3.11+
- Internet connection

## Installation Steps

### 1. Install System Dependencies

```bash
# Update package list
sudo apt update

# Install FFmpeg (required for Discord voice)
sudo apt install -y ffmpeg

# Install Python dependencies
sudo apt install -y python3-pip python3-venv

# Verify installations
ffmpeg -version
python3 --version
```

### 2. Clone Repository

```bash
git clone https://github.com/joshhmann/acore_bot.git
cd acore_bot
```

### 3. Create Virtual Environment

```bash
# Create venv
python3 -m venv .venv311

# Activate venv
source .venv311/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If you get errors about torch/torchaudio being too large, you can install CPU-only versions:

```bash
# For CPU-only PyTorch (smaller download)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 5. Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &

# Pull the model
ollama pull l3-8b-stheno-v3.2
```

### 6. Configure Bot

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

Add your Discord token:
```env
DISCORD_TOKEN=your_discord_bot_token_here
```

### 7. Download TTS Models

Models will auto-download on first run, or download manually:

```bash
# Create models directory
mkdir -p models

# Download Kokoro TTS models
cd models
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0/kokoro-v1.0.onnx
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0/voices-v1.0.bin
cd ..
```

### 8. Run Bot

```bash
# Make sure venv is activated
source .venv311/bin/activate

# Run bot
python main.py
```

## Running as a Service

To keep the bot running after you disconnect:

### Option 1: Screen (Simple)

```bash
# Install screen
sudo apt install screen

# Start screen session
screen -S discordbot

# Run bot
python main.py

# Detach: Press Ctrl+A then D
# Reattach: screen -r discordbot
```

### Option 2: systemd (Recommended)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/discordbot.service
```

Add this content:
```ini
[Unit]
Description=Discord AI Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/acore_bot
Environment="PATH=/path/to/acore_bot/.venv311/bin"
ExecStart=/path/to/acore_bot/.venv311/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable discordbot

# Start service
sudo systemctl start discordbot

# Check status
sudo systemctl status discordbot

# View logs
sudo journalctl -u discordbot -f
```

## Troubleshooting

### FFmpeg Not Found

```bash
# Install FFmpeg
sudo apt install ffmpeg

# Verify installation
which ffmpeg
ffmpeg -version
```

### Ollama Not Running

```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama
ollama serve &

# Or with systemd
sudo systemctl start ollama
```

### Permission Denied

```bash
# Make sure you own the directory
sudo chown -R $USER:$USER /path/to/acore_bot

# Or run with proper permissions
chmod +x main.py
```

### Port Already in Use

If Ollama port 11434 is in use:
```bash
# Find what's using the port
sudo lsof -i :11434

# Kill the process
sudo kill -9 <PID>
```

### Low Memory

If your VM has limited RAM:

```bash
# Monitor memory usage
htop

# Reduce batch size or use smaller model
# Edit .env:
OLLAMA_MODEL=llama3.2:1b  # Smaller model
```

## Quick Commands

```bash
# Check bot status
systemctl status discordbot

# Restart bot
systemctl restart discordbot

# View logs
journalctl -u discordbot -f

# Stop bot
systemctl stop discordbot

# Update code
git pull
systemctl restart discordbot
```

## Performance Tips

1. **Use CPU-only PyTorch** - Smaller and faster on VMs without GPU
2. **Smaller model** - Use `llama3.2:1b` instead of Stheno for lower memory
3. **Disable features** - Turn off RVC if not needed:
   ```env
   RVC_ENABLED=false
   ```
4. **Reduce chat history** - Lower memory usage:
   ```env
   CHAT_HISTORY_MAX_MESSAGES=10
   ```

## Security

```bash
# Firewall setup
sudo ufw allow 22    # SSH
sudo ufw enable

# Keep .env secure
chmod 600 .env

# Don't commit .env to git
git update-index --assume-unchanged .env
```

## Monitoring

```bash
# Check disk space
df -h

# Check memory
free -h

# Check CPU
top

# Monitor bot logs
tail -f bot.log
```

## Backup

```bash
# Backup user profiles
tar -czf profiles_backup.tar.gz data/user_profiles/

# Backup configuration
cp .env .env.backup
```

---

**Need help?** Check the main [README](../../README.md) or open an issue!
