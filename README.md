# Acore Bot - AI Character Ecosystem

**Status**: ✅ **PRODUCTION READY** (2025-12-11)

A Discord bot featuring multiple AI personas that interact with users and each other, building relationships over time.

**Latest Release**: Production-ready with comprehensive testing, 21 services, 10 active characters, and full feature set operational.

## Quick Start

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

# Or install as systemd service (production)
sudo ./install_service.sh
```

**Production Deployment**: See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) for comprehensive deployment guide.

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

**Core Intelligence** (Phase 1 - 11 features):
- **Dynamic Mood System**: Personas have emotional states that evolve based on conversations
- **Context-Aware Responses**: Adjusts verbosity automatically (brief for quick questions, detailed for complex topics)
- **Memory Isolation**: Each persona maintains separate memories - no cross-contamination
- **Curiosity-Driven Questions**: Asks thoughtful follow-ups based on curiosity level
- **Topic Interest Filtering**: Personas engage more with topics they care about
- **Adaptive Ambient Timing**: Learns channel activity patterns and adjusts proactive behavior
- **Character Evolution**: Personas evolve through milestones (50, 100, 500, 1000, 5000 messages)
- **Persona Conflicts**: Dynamic tension between incompatible personalities
- **Activity-Based Routing**: Matches personas to user activities (gaming, music, etc.)
- **Framework Blending**: Dynamically adapts personality based on context (supportive, playful, analytical)
- **Emotional Contagion**: Mirrors or supports user's emotional state

**Adaptive Behavior** (Phase 2 - 8 features):
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

### Utility
| Command | Description |
|---------|-------------|
| `!quiet` / `!mute` | Silence the bot |
| `@Bot unmute` | Wake the bot up |

## Production Status

### ✅ Verified Production-Ready (2025-12-11)

**Startup Validation:**
- ✅ All 21 services initialize successfully
- ✅ 12 cogs + extensions load without errors
- ✅ Graceful shutdown and cleanup verified
- ✅ Command tree sync with error handling
- ✅ 0 critical linting errors (168 fixed)

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
