# Acore Bot - AI Character Ecosystem

A Discord bot featuring multiple AI personas that interact with users and each other, building relationships over time.

## Quick Start

```bash
# 1. Install dependencies
pip install -e .

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your Discord token and OpenRouter API key

# 3. Run the bot
python main.py

# Or install as systemd service
./install_service.sh
```

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
│                      Service Layer                            │
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
