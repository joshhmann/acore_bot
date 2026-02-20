# Acore Bot - AI Character Ecosystem

**Status**: **PRODUCTION READY** (2025-12-11)

A Discord bot featuring multiple AI personas that interact with users and each other, building relationships over time.

**Latest Release**: Production-ready with comprehensive testing, 21 services, 10 active characters, and full feature set operational.

---

## What is Acore?

Acore is a **multi-platform AI character framework** that happens to include a full-featured Discord bot. The same engine that powers your Discord characters can run on the command line, integrate with other platforms, or embed into your own applications.

**For Discord users**: You get a bot with multiple AI personas that chat, build relationships, and remember your users.

**For developers**: You get a modular framework with clean Core/Adapter architecture, event-driven messaging, and platform-agnostic business logic.

---

## Quick Start

### Option 1: Discord Bot (Recommended)

```bash
# 1. Install dependencies (using uv - recommended)
uv sync

# Alternative: pip installation
pip install -e .

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your Discord token and LLM provider settings

# 3. Run the bot
uv run python main.py

# Or use the launcher
uv run python launcher.py

# Or install as systemd service (production)
sudo ./install_service.sh
```

### Option 2: CLI Mode

Chat with personas directly from your terminal:

```bash
# Start CLI mode
ACORE_CLI_ENABLED=true uv run python launcher.py

# Or run directly
uv run python -m adapters.cli

# Chat with a specific persona
echo "@dagoth_ur Hello, how are you?" | uv run python -m adapters.cli
```

**Production Deployment**: See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) for comprehensive deployment guide.

---

## Framework Architecture

Acore uses a **Core/Adapter architecture** that separates platform-agnostic business logic from platform-specific integrations.

```
+------------------+     +------------------+     +------------------+
|  Discord Adapter |     |   CLI Adapter    |     |  [Your Adapter]  |
|  (Production)    |     |  (Terminal)      |     |  (Custom)        |
+------------------+     +------------------+     +------------------+
         |                       |                        |
         +-----------------------+------------------------+
                                 |
                    +------------v-------------+
                    |       Core Layer         |
                    |  - Platform-agnostic     |
                    |  - Event-driven          |
                    |  - Business logic        |
                    +------------+-------------+
                                 |
                    +------------v-------------+
                    |     Service Layer        |
                    |  - Persona System        |
                    |  - Memory/RAG            |
                    |  - LLM Services          |
                    |  - Voice Pipeline        |
                    +--------------------------+
```

**Key Benefits**:
- Run the same personas on Discord, CLI, or your own platform
- Test core logic without Discord dependencies
- Add new platforms by implementing adapter interfaces
- Clean separation keeps code maintainable

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full technical details.

---

## Adapters

Acore includes adapters for different platforms. Each adapter handles platform-specific I/O while the core manages personas and responses.

### Discord Adapter (Production)

Full-featured Discord bot with webhooks, slash commands, and voice support.

```bash
# Run Discord bot
uv run python main.py
# Or via launcher
ACORE_DISCORD_ENABLED=true uv run python launcher.py
```

**Features**:
- Webhook persona spoofing (each character has unique name/avatar)
- Slash commands and traditional prefix commands
- Voice channel support (TTS, STT, RVC)
- Reaction handling and message tracking

### CLI Adapter (Terminal)

Chat with personas from the command line. Great for testing and development.

```bash
# Interactive mode
uv run python -m adapters.cli

# Pipe a message
echo "@scav Tell me a story" | uv run python -m adapters.cli

# With launcher
ACORE_CLI_ENABLED=true uv run python launcher.py
```

**Usage**:
```
# Address a specific persona
@dagoth_ur What is your favorite game?

# Or use default persona
Hello, how are you today?
```

### Creating Custom Adapters

Want to integrate Acore with Telegram, Slack, or your own platform? See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#creating-new-adapters) for a step-by-step guide.

Basic adapter structure:
```python
from core.interfaces import InputAdapter, OutputAdapter

class MyAdapter(InputAdapter):
    async def start(self): ...
    async def stop(self): ...
    def on_event(self, callback): ...
```

---

## Core Features

### 🎭 Multi-Persona System
- **6+ Active Characters**: Dagoth Ur, Scav, Toad, Maury, HAL 9000, Zenos
- **Webhook Spoofing**: Each character appears with their own name/avatar
- **Dynamic Routing**: Bot selects appropriate character based on context/mentions
- **Character Import**: Import SillyTavern PNG cards with `!import`

### 🤝 Persona Relationships
Characters build relationships with each other over time:
- **Affinity System**: 0-100 score between each pair
- **Banter Scaling**: Higher affinity = more likely to respond to each other
- **Relationship Stages**: strangers → acquaintances → friends → besties
- **Organic Cliques**: Similar characters naturally bond more

### 🧠 AI-First Architecture
- **Thinking Model**: Cheap/fast LLM for internal decisions (spam prevention, routing)
- **Main Model**: Quality LLM for actual character responses
- **Self-Aware Spam Prevention**: Bot checks if it's being ignored before speaking

### 📚 Memory Systems
- **User Profiles**: Learn facts, interests, preferences about users
- **Affection Tracking**: Build relationships with users over time
- **RAG (Retrieval)**: Vector search for relevant knowledge
- **Lorebooks/World Info**: SillyTavern-compatible context injection
- **Conversation Summarization**: Long-term memory via summaries

### 🎤 Voice Features
- **TTS**: Kokoro or SuperTonic text-to-speech
- **RVC**: Voice conversion for character voices
- **STT**: Parakeet speech recognition
- **Voice Channel Support**: Listen and respond in voice

### 🚀 Advanced Autonomous Behavior (NEW - Phase 1 & 2)

**18 AI enhancements** that make personas feel truly alive and adaptive:

**Core Intelligence** (Phase 1):
- **Dynamic Mood System**: Personas have emotional states that evolve based on conversations
- **Context-Aware Responses**: Adjusts verbosity automatically (brief for quick questions, detailed for complex topics)
- **Memory Isolation**: Each persona maintains separate memories (no cross-contamination)
- **Curiosity-Driven Questions**: Asks thoughtful follow-ups based on curiosity level
- **Topic Interest Filtering**: Personas engage more with topics they care about
- **Adaptive Ambient Timing**: Learns channel activity patterns and adjusts proactive behavior
- **Character Evolution**: Personas evolve through milestones (50, 100, 500, 1000, 5000 messages)
- **Persona Conflicts**: Dynamic tension between incompatible personalities
- **Activity-Based Routing**: Matches personas to user activities (gaming, music, etc.)
- **Framework Blending**: Dynamically adapts personality based on context (supportive, playful, analytical)
- **Emotional Contagion**: Mirrors or supports user's emotional state

**Adaptive Behavior** (Phase 2):
- **Semantic Lorebook**: Uses AI to match lore conceptually, not just by keywords (ML-powered)
- **Real-Time Analytics Dashboard**: Web UI for monitoring persona metrics with live updates

**Performance**: All features exceed targets by 10x-5000x with <5ms total overhead per message

See [example_advanced_persona.json](prompts/characters/example_advanced_persona.json) for a showcase of all features.

### 📊 Analytics Dashboard (T23-T24)

Monitor your bot's performance in real-time with a beautiful web dashboard:

**Features:**
- **Real-Time Metrics**: Messages processed, active users, uptime, response times
- **Persona Monitoring**: Track each character's message count, mood, evolution stage
- **Interactive Charts**: Visualize message volume and performance trends with Chart.js
- **WebSocket Updates**: Live data pushed every 2 seconds
- **Secure Access**: API key authentication protects sensitive data

**Setup:**
```env
# Enable dashboard in .env
ANALYTICS_DASHBOARD_ENABLED=true
ANALYTICS_DASHBOARD_PORT=8080
ANALYTICS_API_KEY=your_secure_random_key_here
```

**Access:** Navigate to `http://localhost:8080` and enter your API key when prompted.

**Technologies:** FastAPI + WebSocket + Chart.js

### 💬 Bot-to-Bot Conversations (NEW)

Enable AI personas to converse with each other in structured, multi-turn conversations:

**Features:**
- **2-5 Personas:** Structured conversations between multiple characters
- **Up to 10 Turns:** Configurable conversation length (max 20)
- **Quality Metrics:** Automated assessment of conversation quality
- **Review Workflow:** Human approval before archiving
- **RAG Integration:** Searchable conversation history
- **Headless Testing:** Reproducible conversations for testing

**Quick Example:**
```
/bot_conversation participants:dagoth_ur,scav topic:The nature of artificial intelligence
```

**Use Cases:**
- Character development and relationship building
- Entertainment (watch characters debate and interact)
- Behavior research and emergent AI dynamics

**Documentation:**
- [User Guide](docs/BOT_CONVERSATIONS.md) - Commands, troubleshooting, best practices
- [Architecture](docs/BOT_CONVERSATIONS_ARCHITECTURE.md) - Technical deep dive

## Configuration

### Essential .env Variables

```env
# Discord
DISCORD_TOKEN=your_token_here
DISCORD_PREFIX=!

# LLM Provider (openrouter or ollama)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=x-ai/grok-3-fast

# Thinking Model (cheap model for decisions)
THINKING_MODEL=meta-llama/llama-3.2-1b-instruct
THINKING_MODEL_PROVIDER=openrouter

# Persona System
USE_PERSONA_SYSTEM=true
ACTIVE_PERSONAS=dagoth_ur.json,scav.json,toad.json,maury.json,hal9000.json,zenos.json

# Features
USER_PROFILES_AUTO_LEARN=true
PROACTIVE_ENGAGEMENT_ENABLED=true
RAG_ENABLED=true

# Adapters (for launcher.py)
ACORE_DISCORD_ENABLED=true
ACORE_CLI_ENABLED=false
```

### Key Directories

```
prompts/
├── characters/          # Character definitions (JSON)
│   ├── dagoth_ur.json
│   ├── scav.json
│   └── ...
├── frameworks/          # Behavior templates
│   └── neuro.json
└── system/              # System prompts

data/
├── lorebooks/           # World info (SillyTavern format)
├── user_profiles/       # Per-user memory
├── persona_relationships.json  # Character affinity data
└── import_cards/        # Drop PNG cards here for bulk import

core/                    # Platform-agnostic framework core
├── types.py            # AcoreMessage, AcoreUser, etc.
└── interfaces.py       # Adapter interfaces

adapters/                # Platform-specific adapters
├── discord/            # Discord bot implementation
└── cli/                # Command-line interface
```

## Commands

### Chat Commands
| Command | Description |
|---------|-------------|
| `@Bot message` | Direct mention to chat |
| `@CharacterName message` | Chat with specific character |

### Character Management
| Command | Description |
|---------|-------------|
| `!import` | Import SillyTavern PNG card (attach file) |
| `!import_folder` | Bulk import from `data/import_cards/` |
| `!reload_characters` | Reload characters without restart |
| `/set_character <name>` | Switch active character |
| `/list_characters` | Show available characters |
| `!interact <char1> <char2> <topic>` | Force two characters to interact |

### Bot-to-Bot Conversations
| Command | Description |
|---------|-------------|
| `/bot_conversation participants:<bots> topic:<topic>` | Start bot conversation |
| `/review_conversation conversation_id:<id>` | Post conversation for review |
| `/list_conversations` | List recent conversations |
| `/get_conversation conversation_id:<id>` | Retrieve conversation transcript |
| `/archive_conversation conversation_id:<id>` | Manually archive conversation |

### Utility
| Command | Description |
|---------|-------------|
| `!quiet` / `!mute` | Silence the bot |
| `@Bot unmute` | Wake the bot up |

## Production Status

### Verified Production-Ready (2025-12-11)

**Startup Validation:**
- All 21 services initialize successfully
- 12 cogs + extensions load without errors
- Graceful shutdown and cleanup verified
- Command tree sync with error handling
- 0 critical linting errors (168 fixed)

**Active Services:**
- **LLM**: Ollama, OpenRouter, Thinking, Cache, Fallback
- **Voice**: TTS (Kokoro/Supertonic), RVC, STT (Parakeet)
- **Memory**: History, Profiles, RAG, Summarizer, Context Router
- **Persona**: System, Router, Relationships, Behavior, Lorebook
- **Discord**: Music, Reminders, Notes, Web Search
- **Core**: Metrics, Context Manager, Tool System (21 tools)

**Documentation**: See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Discord Bot                            │
├──────────────────────────────────────────────────────────────┤
│  ChatCog           │  VoiceCog         │  CharacterCommandsCog│
│  • Message handling│  • TTS/STT        │  • /set_character    │
│  • Response gen    │  • Voice channels │  • !import           │
└─────────┬──────────┴────────┬──────────┴──────────┬──────────┘
          │                   │                      │
┌─────────▼───────────────────▼──────────────────────▼─────────┐
│                      Service Layer (21 Services)              │
├──────────────────────────────────────────────────────────────┤
│  PersonaRouter     │  BehaviorEngine    │  ThinkingService   │
│  • Select character│  • Reactions       │  • Spam decisions  │
│  • Route @mentions │  • Ambient msgs    │  • Yes/No logic    │
│                    │  • Self-awareness  │                    │
├──────────────────────────────────────────────────────────────┤
│  PersonaRelations  │  UserProfiles      │  RAGService        │
│  • Affinity scores │  • Facts/interests │  • Vector search   │
│  • Banter chance   │  • Affection       │  • Lorebooks       │
├──────────────────────────────────────────────────────────────┤
│  OpenRouterService │  OllamaService     │  TTSService        │
│  • API calls       │  • Local LLM       │  • Voice synth     │
└──────────────────────────────────────────────────────────────┘
```

## Creating Characters

### JSON Format
```json
{
  "id": "jerry_springer",
  "display_name": "Jerry Springer",
  "description": "Legendary talk show host known for ...",
  "personality": "Charismatic, provocative, ...",
  "scenario": "You are Jerry Springer hosting your show...",
  "first_message": "Welcome to the show! Today we have...",
  "avatar_url": "https://example.com/jerry.png",
  "framework": "neuro",
  "knowledge_domain": {
    "rag_categories": ["talk_shows"],
    "lorebooks": ["talk_show_lore"]
  }
}
```

### Import from SillyTavern
1. Download character PNG from Chub.ai or CharacterHub
2. In Discord: `!import` (attach the PNG)
3. Or bulk: Copy PNGs to `data/import_cards/`, run `!import_folder`
4. Add character ID to `ACTIVE_PERSONAS` in `.env`
5. Run `!reload_characters`

---

## Documentation

**Framework Documentation:**
- [Architecture Overview](docs/ARCHITECTURE.md) - Core/Adapter architecture, creating adapters
- [API Reference](docs/API_REFERENCE.md) - Core types, interfaces, events

**Setup and Deployment:**
- [Production Readiness](docs/PRODUCTION_READINESS.md) - Complete deployment guide
- [VM Setup](docs/setup/VM_SETUP.md) - Virtual machine configuration
- [RVC Setup](docs/setup/RVC_SETUP.md) - Voice conversion setup

**Feature Documentation:**
- [Bot Conversations](docs/BOT_CONVERSATIONS.md) - Multi-bot chat system
- [Persona System](docs/guides/Persona_System_Guide.md) - Character behavior guide
- [Voice System](docs/guides/Voice_TTS_System_Guide.md) - TTS/RVC configuration
- [Analytics](docs/guides/Analytics_Monitoring_Guide.md) - Dashboard setup

**Developer Resources:**
- [Codebase Summary](docs/codebase_summary/README.md) - Comprehensive code documentation
- [Contributing](docs/CONTRIBUTING.md) - Development guidelines

---

## Monitoring

### Logs
```bash
# Live logs
journalctl -f -u discordbot

# Bot log file
tail -f /root/acore_bot/bot.log
```

### Metrics
- Saved to `data/metrics/hourly_*.json`
- Response times, token counts, API usage

## Troubleshooting

### Bot not responding
1. Check if muted: `@Bot unmute`
2. Verify `DISCORD_TOKEN` is valid
3. Check logs for errors

### Characters not appearing
1. Ensure channel has webhook permissions
2. Check `ACTIVE_PERSONAS` includes the character file
3. Run `!reload_characters`

### High API costs
1. Set `USER_PROFILES_AUTO_LEARN=false` to reduce calls
2. Configure a cheap `THINKING_MODEL`
3. Disable `PROACTIVE_ENGAGEMENT_ENABLED` if not needed

## License

MIT License - See LICENSE file
