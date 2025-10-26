# Discord Ollama Bot with TTS & RVC

A clean, modern Discord bot featuring:
- **Ollama AI Chat** - Natural conversations with local LLM models
- **Text-to-Speech** - High-quality voice synthesis with Edge TTS
- **RVC Voice Conversion** - Clone and apply custom voices
- **Voice Channel Integration** - Play generated audio in Discord voice channels

## Features

### 💬 AI Chat
- Chat with Ollama-powered AI using `/chat`
- Conversation history per channel
- Auto-reply when bot is mentioned
- Support for multiple models (llama3.2, mistral, etc.)
- One-off questions with `/ask`

### 🎙️ Text-to-Speech
- Generate natural-sounding speech with Edge TTS
- Multiple voices and languages available
- Play audio in voice channels with `/speak`
- Customize voice, rate, and volume

### 🎤 Voice Conversion (RVC)
- Apply voice conversion to TTS output
- Use custom voice models
- `/speak_as` command for specific voices
- Support for .pth RVC models

## Requirements

- **Python 3.10+**
- **Discord Bot Token** - [Create a bot](https://discord.com/developers/applications)
- **Ollama** - [Install Ollama](https://ollama.ai)
- **FFmpeg** - Required for voice playback

### Optional
- **RVC Models** - For voice conversion (.pth files)

## Installation

### 1. Clone and Setup

```bash
cd /path/to/acore_bot
pip install -r requirements.txt
```

Or using a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Ollama

```bash
# Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama
ollama serve

# Pull a model (in another terminal)
ollama pull llama3.2
```

### 3. Install FFmpeg

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### 4. Configure Bot

Copy `.env.example` to `.env` and fill in your settings:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
DISCORD_TOKEN=your_discord_bot_token_here

# Ollama (defaults are usually fine)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Optional: Enable auto-reply
AUTO_REPLY_ENABLED=true
AUTO_REPLY_CHANNELS=123456789,987654321  # Channel IDs
```

### 5. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to **Bot** tab and create a bot
4. Copy the **token** and put it in `.env` as `DISCORD_TOKEN`
5. Enable these **Privileged Gateway Intents**:
   - Message Content Intent
   - Server Members Intent (optional)
6. Go to **OAuth2 > URL Generator**
7. Select scopes: `bot`, `applications.commands`
8. Select permissions:
   - Send Messages
   - Read Message History
   - Connect (for voice)
   - Speak (for voice)
   - Use Voice Activity
9. Copy the URL and invite the bot to your server

## Usage

### Start the Bot

```bash
python main.py
```

Or with virtual environment:

```bash
.venv/bin/python main.py
```

### Commands

#### Chat Commands

- `/chat <message>` - Chat with the AI
- `/ask <question>` - One-off question (no history)
- `/clear_history` - Clear conversation history for current channel
- `/set_model <model>` - Change Ollama model
- `/models` - List available models
- `/status` - Check AI status

#### Voice Commands

- `/join` - Join your voice channel
- `/leave` - Leave voice channel
- `/speak <text>` - Generate and play TTS audio
- `/speak_as <voice_model> <text>` - Speak with specific RVC voice
- `/voices` - List available voices
- `/set_voice <voice>` - Change default TTS voice
- `/list_tts_voices [language]` - List all available TTS voices

### Auto-Reply

When `AUTO_REPLY_ENABLED=true`:
- Mention the bot to chat: `@BotName hello!`
- Or restrict to specific channels with `AUTO_REPLY_CHANNELS`

## RVC Setup (Optional)

To use voice conversion:

1. **Download or train RVC models** (.pth files)
   - Get pre-trained models or train your own
   - See [RVC-Project](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)

2. **Place models in `data/voice_models/`**
   ```bash
   mkdir -p data/voice_models
   cp your_model.pth data/voice_models/
   ```

3. **Enable RVC in `.env`**
   ```env
   RVC_ENABLED=true
   DEFAULT_RVC_MODEL=your_model
   ```

4. **Use with `/speak_as`**
   ```
   /speak_as voice_model:your_model text:Hello world!
   ```

**Note**: The RVC implementation is currently a placeholder. For full functionality, you'll need to integrate the actual RVC inference pipeline (see `services/rvc.py` for details).

## Configuration

### Environment Variables

See `.env.example` for all available options:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Discord bot token | *Required* |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default model | `llama3.2` |
| `OLLAMA_TEMPERATURE` | Response randomness (0-1) | `0.7` |
| `CHAT_HISTORY_ENABLED` | Enable conversation history | `true` |
| `CHAT_HISTORY_MAX_MESSAGES` | Max messages to remember | `20` |
| `AUTO_REPLY_ENABLED` | Auto-reply when mentioned | `false` |
| `DEFAULT_TTS_VOICE` | TTS voice | `en-US-AriaNeural` |
| `RVC_ENABLED` | Enable voice conversion | `true` |

### Data Directories

- `data/chat_history/` - Conversation history per channel (JSON)
- `data/voice_models/` - RVC voice models (.pth)
- `data/temp/` - Temporary audio files (auto-cleaned)

## Troubleshooting

### "Cannot connect to Ollama"
- Make sure Ollama is running: `ollama serve`
- Check `OLLAMA_HOST` in `.env`
- Test with: `curl http://localhost:11434/api/tags`

### "Invalid Discord token"
- Verify `DISCORD_TOKEN` in `.env`
- Generate a new token in Discord Developer Portal

### Voice commands not working
- Install FFmpeg
- Grant bot "Connect" and "Speak" permissions
- Join a voice channel before using `/speak`

### Bot not responding
- Check bot has "Send Messages" permission
- For auto-reply: enable "Message Content Intent" in Discord Developer Portal

### RVC not working
- RVC requires additional setup (see RVC Setup section)
- Current implementation is a placeholder
- Audio will pass through unchanged without proper RVC integration

## Development

### Project Structure

```
.
├── main.py              # Bot entry point
├── config.py            # Configuration management
├── cogs/
│   ├── chat.py         # Chat commands
│   └── voice.py        # Voice commands
├── services/
│   ├── ollama.py       # Ollama LLM client
│   ├── tts.py          # TTS service
│   └── rvc.py          # RVC service (placeholder)
├── utils/
│   └── helpers.py      # Utilities & chat history
└── data/               # Runtime data
```

### Adding Features

The bot uses Discord.py cogs for organization. To add new features:

1. Create a new cog in `cogs/`
2. Register it in `main.py` with `await bot.add_cog(YourCog(...))`
3. Sync commands with `await bot.tree.sync()`

## License

This is a fork/restructure of [acore_bot](https://github.com/joshhmann/acore_bot).

## Credits

- [Ollama](https://ollama.ai) - Local LLM inference
- [Edge TTS](https://github.com/rany2/edge-tts) - Text-to-Speech
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [RVC Project](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) - Voice conversion

---

**Need help?** Open an issue or check the [Discord.py documentation](https://discordpy.readthedocs.io/).
