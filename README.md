# Discord AI Bot with Personality, Voice & Memory

A sophisticated Discord bot featuring AI personality, high-quality voice synthesis, voice conversion, user memory, and relationship building.

## 🌟 Features

### 🧠 AI Personality System
- **Ollama-powered chat** with L3-8B-Stheno-v3.2 model optimized for roleplay
- **Multiple personas** - Switch between personalities (Chief, Arbiter, Pirate, etc.)
- **Dynamic personality** based on user relationships
- **Context-aware** with real-time date/time
- **Conversation sessions** with automatic memory management

### 💖 User Relationship System
- **Affection tracking** (0-100 scale) with 5 relationship stages
- **Auto-learning** - Bot learns about users from conversations
- **Profile system** - Tracks traits, interests, preferences, memorable quotes
- **Sentiment analysis** - Conversations affect relationship level
- **Personalized responses** based on relationship stage

### 🎙️ Voice Pipeline
- **Kokoro TTS** - High-quality local text-to-speech with 50+ voices
- **RVC Voice Conversion** - Apply custom character voices (GOTHMOMMY, etc.)
- **Discord voice integration** - Speaks responses in voice channels
- **Auto-TTS** - Bot speaks when mentioned in voice channel

### 🔍 Advanced Features
- **Web search** (optional) - DuckDuckGo integration
- **MCP personality RAG** (optional) - Retrieval-augmented generation for personalities
- **Per-persona voices** - Each personality has its own voice
- **Session management** - Automatic conversation cleanup

## 📋 Requirements

### Core
- **Python 3.11+**
- **Discord Bot Token** - [Create a bot](https://discord.com/developers/applications)
- **Ollama** - [Install Ollama](https://ollama.ai) with L3-8B-Stheno-v3.2 model
- **FFmpeg** - Required for voice playback

### Voice Features
- **Kokoro TTS** models (auto-downloaded on first use)
- **RVC-WebUI** (optional) - For voice conversion
  - [RVC-WebUI Setup Guide](docs/setup/RVC_WEBUI_SETUP.md)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Clone repository
git clone https://github.com/joshhmann/acore_bot.git
cd acore_bot

# Create virtual environment
python -m venv .venv311
.venv311/Scripts/activate  # Windows
# or
source .venv311/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Install Ollama & Model

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh  # Linux/Mac
# or download from https://ollama.ai for Windows

# Start Ollama
ollama serve

# Pull the Stheno model (in another terminal)
ollama pull l3-8b-stheno-v3.2
```

### 3. Configure Bot

```bash
# Copy example config
cp .env.example .env

# Edit .env with your settings
nano .env
```

Minimum required settings:
```env
DISCORD_TOKEN=your_discord_bot_token_here
OLLAMA_MODEL=l3-8b-stheno-v3.2
```

### 4. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create application → Bot → Copy token
3. Enable **Privileged Gateway Intents**:
   - Message Content Intent ✅
   - Server Members Intent ✅
4. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Permissions: Send Messages, Read History, Connect, Speak, Use Voice Activity
5. Invite bot to your server

### 5. Run Bot

```bash
python main.py
```

**For Linux VMs:** Install as a systemd service to run automatically:
```bash
chmod +x install_service.sh
sudo ./install_service.sh
sudo systemctl start discordbot
```
See [Service Scripts Guide](docs/setup/SERVICE_SCRIPTS.md) for details.

## 📖 Commands

### Chat Commands
- `/chat <message>` - Chat with AI (with personality & memory)
- `/ask <question>` - One-off question (no history)
- `/clear_history` - Clear conversation history
- `/set_persona <persona>` - Change bot personality
- `/personas` - List available personas
- `/my_profile` - View your profile & relationship status
- `/relationship` - Check your relationship with the bot

### Voice Commands
- `/join` - Join your voice channel
- `/leave` - Leave voice channel
- `/speak <text>` - Generate and play TTS
- `/set_voice <voice>` - Change TTS voice
- `/list_voices` - List available Kokoro voices

### Status Commands
- `/status` - Check bot and service status
- `/models` - List available Ollama models

## 🗂️ Project Structure

```
acore_bot/
├── main.py                 # Bot entry point
├── config.py              # Configuration management
├── cogs/
│   ├── chat.py           # Chat & AI commands
│   └── voice.py          # Voice & TTS commands
├── services/
│   ├── ollama.py         # Ollama LLM client
│   ├── kokoro_tts.py     # Kokoro TTS service
│   ├── rvc_http.py       # RVC voice conversion (HTTP)
│   ├── rvc_unified.py    # Unified RVC interface
│   ├── user_profiles.py  # User memory & affection system
│   ├── web_search.py     # DuckDuckGo search (optional)
│   ├── mcp.py            # MCP personality RAG (optional)
│   └── deprecated/       # Old implementations
├── utils/
│   ├── helpers.py        # Conversation history utilities
│   ├── persona_loader.py # Persona management
│   └── system_context.py # Date/time context injection
├── prompts/
│   └── *.txt            # Persona prompt files
├── tests/               # Test scripts
├── docs/
│   ├── setup/          # Setup guides
│   └── features/       # Feature documentation
└── data/               # Runtime data (not in git)
    ├── chat_history/   # Conversation history per channel
    ├── user_profiles/  # User profiles & affection data
    └── temp/          # Temporary audio files
```

## 🎭 Available Personas

Located in `prompts/` directory:
- **chief** - Master Chief from Halo (default)
- **arbiter** - Arbiter from Halo
- **pirate** - Pirate character
- **cortana** - Cortana AI
- **johnson** - Sergeant Johnson
- ...and more!

Add your own by creating `prompts/your_persona.txt`

## 🔧 Advanced Setup

### RVC Voice Conversion

For character voices like GOTHMOMMY:

1. **Install RVC-WebUI** (separate repo)
2. **Place model files** in RVC-WebUI's `assets/weights/`
3. **Start RVC-WebUI**: `python infer-web.py`
4. **Load model** through web interface (http://localhost:7865)
5. **Enable in bot**:
   ```env
   RVC_ENABLED=true
   RVC_MODE=webui
   RVC_WEBUI_URL=http://localhost:7865
   RVC_DEFAULT_MODEL=GOTHMOMMY
   ```

See [RVC Setup Guide](docs/setup/RVC_INTEGRATION_COMPLETE.md) for details.

### Optional Features

**Web Search:**
```env
WEB_SEARCH_ENABLED=true
```

**MCP Personality RAG:**
```env
MCP_PERSONALITY_RAG_ENABLED=true
MCP_SERVER_PATH=/path/to/mcp/server
```

## 📚 Documentation

### Setup Guides
- [Quick Start](docs/setup/QUICK_START.md) - 5-minute setup guide
- [VM Setup](docs/setup/VM_SETUP.md) - Complete Linux VM deployment
- [Service Scripts](docs/setup/SERVICE_SCRIPTS.md) - systemd service installation
- [RVC WebUI Setup](docs/setup/RVC_WEBUI_SETUP.md) - Voice conversion setup

### Features
- [Affection System](docs/features/AFFECTION_SYSTEM.md) - Relationship tracking
- [User Profile Auto-Learning](docs/features/USER_PROFILE_AUTO_LEARNING.md) - AI memory
- [Voice Features](docs/features/VOICE_FEATURES.md) - TTS and RVC pipeline
- [Kokoro Auto-Download](docs/features/KOKORO_AUTO_DOWNLOAD.md) - Automatic model setup
- [Persona Switching](docs/features/PERSONA_SWITCHING.md) - Multiple personalities

## 🐛 Troubleshooting

### "Cannot connect to Ollama"
```bash
# Start Ollama
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

### Voice not working
- Install FFmpeg
- Check bot has Connect/Speak permissions
- Join voice channel before using `/speak`

### RVC returns errors
- Ensure RVC-WebUI is running
- Model must be selected in web UI
- Check RVC-WebUI console for errors

### Profile learning not working
```env
USER_PROFILES_ENABLED=true
USER_PROFILES_AUTO_LEARN=true
```

## 🔐 Environment Variables

Key settings in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Discord bot token | *Required* |
| `OLLAMA_MODEL` | AI model | `l3-8b-stheno-v3.2` |
| `TTS_ENGINE` | TTS engine | `kokoro` |
| `DEFAULT_PERSONA` | Bot personality | `chief` |
| `USER_PROFILES_ENABLED` | Enable user memory | `true` |
| `USER_AFFECTION_ENABLED` | Enable affection system | `true` |
| `RVC_ENABLED` | Enable voice conversion | `true` |
| `RVC_MODE` | RVC mode | `webui` |

See `.env.example` for complete list.

## 🎯 How It Works

### Complete Pipeline

1. **User mentions bot** in text channel
2. **Ollama generates response** with personality & user context
3. **Kokoro TTS** converts text to speech
4. **RVC converts voice** to character (GOTHMOMMY)
5. **Bot plays audio** in Discord voice channel
6. **Profile system** learns from interaction & updates affection

### User Learning Example

```
User: "I love pizza!"
Bot: *extracts & stores* → traits: ["enthusiastic"], interests: ["pizza", "food"]

User: "I'm a developer"
Bot: *extracts & stores* → facts: ["occupation: developer"]

Next conversation:
Bot: *uses context* → "Hey developer friend! How's the coding going?"
```

## 🤝 Contributing

Issues and pull requests welcome!

## 📄 License

MIT License - See LICENSE file

## 🙏 Credits

- [Ollama](https://ollama.ai) - Local LLM inference
- [Kokoro TTS](https://github.com/nazdridoy/kokoro-tts) - High-quality TTS
- [RVC-WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) - Voice conversion
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API
- [L3-8B-Stheno](https://huggingface.co/Sao10K/L3-8B-Stheno-v3.2) - Roleplay-optimized model

---

**Need help?** Check the [docs](docs/) or open an issue!
