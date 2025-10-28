# Quick Deployment Guide

Deploy the Discord AI bot in 5 minutes!

## Prerequisites

- **Python 3.11+** installed
- **Discord account** with bot creation access
- **10GB disk space** for models

## Step 1: Install Ollama (5 minutes)

### Windows
1. Download from [https://ollama.ai](https://ollama.ai)
2. Run installer
3. Open Command Prompt and run:
```bash
ollama serve
```
4. In a new terminal:
```bash
ollama pull l3-8b-stheno-v3.2
```

### Linux/Mac
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull l3-8b-stheno-v3.2
```

## Step 2: Create Discord Bot (2 minutes)

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** → Name it → Create
3. Go to **Bot** tab → Click **"Add Bot"**
4. Copy the **Token** (you'll need this)
5. Enable these under **Privileged Gateway Intents**:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
6. Go to **OAuth2 > URL Generator**
7. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
8. Select bot permissions:
   - ✅ Send Messages
   - ✅ Read Message History
   - ✅ Connect (voice)
   - ✅ Speak (voice)
   - ✅ Use Voice Activity
9. Copy the generated URL and open it in browser
10. Select your server and authorize

## Step 3: Setup Bot (3 minutes)

```bash
# Clone repository
git clone https://github.com/joshhmann/acore_bot.git
cd acore_bot

# Create virtual environment
python -m venv .venv311
.venv311\Scripts\activate  # Windows
# or
source .venv311/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure bot
cp .env.example .env
```

Edit `.env` and add your Discord token:
```env
DISCORD_TOKEN=your_discord_bot_token_here
```

That's it! Minimum config is just the Discord token.

## Step 4: Run Bot

```bash
python main.py
```

You should see:
```
2025-10-27 20:00:00 | INFO | Bot logged in as YourBotName
2025-10-27 20:00:00 | INFO | Connected to Ollama at http://localhost:11434
2025-10-27 20:00:00 | INFO | Kokoro TTS initialized
```

## Step 5: Test in Discord

In Discord:
```
/chat hello
```

Bot should respond with AI-generated text!

## Voice Setup (Optional)

### Join Voice Channel
```
/join
```

### Speak
```
/speak hello world
```

Bot will speak in the voice channel!

## RVC Voice Conversion (Optional)

For character voices like GOTHMOMMY:

1. **Install FFmpeg** (required for voice)
   - Windows: Download from [https://ffmpeg.org](https://ffmpeg.org)
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`

2. **Setup RVC-WebUI** (see [RVC Setup Guide](docs/setup/RVC_INTEGRATION_COMPLETE.md))

3. **Enable in .env**:
```env
RVC_ENABLED=true
RVC_MODE=webui
RVC_WEBUI_URL=http://localhost:7865
RVC_DEFAULT_MODEL=GOTHMOMMY
```

## Troubleshooting

### "Cannot connect to Ollama"
```bash
# Start Ollama in a separate terminal
ollama serve
```

### "Invalid Discord token"
- Make sure you copied the correct token from Discord Developer Portal
- Token should be in `.env` as `DISCORD_TOKEN=...`

### Bot not responding
- Check bot has "Send Messages" permission in your server
- Make sure "Message Content Intent" is enabled in Developer Portal

### Voice not working
- Install FFmpeg
- Use `/join` before `/speak`
- Check bot has "Connect" and "Speak" permissions

## Running in Production

### Using Screen (Linux)
```bash
screen -S discordbot
python main.py
# Press Ctrl+A then D to detach
# Reattach: screen -r discordbot
```

### Using PM2 (Linux/Mac)
```bash
npm install -g pm2
pm2 start main.py --name discordbot --interpreter python
pm2 save
pm2 startup
```

### Using nssm (Windows Service)
```bash
# Install nssm: https://nssm.cc
nssm install DiscordBot "C:\path\to\.venv311\Scripts\python.exe" "C:\path\to\main.py"
nssm start DiscordBot
```

## Optional Features

### Enable Web Search
```env
WEB_SEARCH_ENABLED=true
```

### User Profiles & Memory
```env
USER_PROFILES_ENABLED=true
USER_PROFILES_AUTO_LEARN=true
```

### Affection System
```env
USER_AFFECTION_ENABLED=true
```

### Change Persona
```env
DEFAULT_PERSONA=chief
# Options: chief, arbiter, pirate, cortana, johnson, etc.
```

## Getting Help

- **Documentation**: Check `docs/` folder
- **Issues**: [GitHub Issues](https://github.com/joshhmann/acore_bot/issues)
- **Setup Guides**: See `docs/setup/`

## Next Steps

- [Full README](README.md) - Complete feature list
- [RVC Voice Setup](docs/setup/RVC_INTEGRATION_COMPLETE.md) - Character voices
- [Contributing Guide](CONTRIBUTING.md) - Add features

---

**Deployment time: ~10 minutes** ⚡

Ready to deploy? Follow steps 1-5 above!
