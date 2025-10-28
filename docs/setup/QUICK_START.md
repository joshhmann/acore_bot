# Quick Start Guide - Arby n Chief Bot

## Current Issues & Fixes

### Issue 1: Wrong .env File
You're using the OLD AzerothCore bot's `.env` file. The new Ollama+TTS bot needs different configuration.

### Issue 2: Persona Commands Not Showing
The commands are coded but bot needs to restart to register them.

### Issue 3: User Profiles Not Working
Service was created but not fully integrated into chat flow (NOW FIXED).

### Issue 4: Web Search Not Working
Service was created but never integrated into main bot (needs integration).

---

## Step-by-Step Setup

### 1. Create Your NEW .env File

Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```

Then edit `.env` with these MINIMUM required settings:

```bash
# REQUIRED
DISCORD_TOKEN=your_discord_token_here

# Ollama Settings
OLLAMA_HOST=http://192.168.0.15:11434
OLLAMA_MODEL=fluffy/l3-8b-stheno-v3.2:latest
OLLAMA_TEMPERATURE=1.17
OLLAMA_MIN_P=0.075
OLLAMA_TOP_K=50
OLLAMA_REPEAT_PENALTY=1.1

# Character/Personality
SYSTEM_PROMPT_FILE=./prompts/chief.txt

# TTS (Kokoro - local, high quality)
TTS_ENGINE=kokoro
KOKORO_VOICE=am_onyx
KOKORO_SPEED=1.0

# User Profiles (ENABLE THIS!)
USER_PROFILES_ENABLED=true
USER_AFFECTION_ENABLED=true
USER_CONTEXT_IN_CHAT=true

# Web Search (OPTIONAL - enable when ready)
WEB_SEARCH_ENABLED=false
WEB_SEARCH_ENGINE=duckduckgo

# RVC (OPTIONAL - leave disabled for now)
RVC_ENABLED=false
```

### 2. Make Sure Ollama is Running

```bash
# On your Ollama server (192.168.0.15)
ollama serve

# Pull the Stheno model
ollama pull fluffy/l3-8b-stheno-v3.2
```

### 3. Run the Bot

```bash
.venv311\Scripts\python.exe main.py
```

### 4. Test the Commands

In Discord:
```
/chat Hello!
/list_personas
/set_persona chief
/set_persona arbiter
```

If commands don't show up, Discord needs to sync. Wait ~1 hour or:
- Kick and re-invite the bot
- Or restart the bot

---

## Troubleshooting

### Commands Not Showing in Discord

Discord caches slash commands. Solutions:
1. **Wait** - Can take up to 1 hour
2. **Kick & re-invite bot** - Forces command refresh
3. **Check bot permissions** - Needs `applications.commands` scope

### DuckDuckGo Search Explanation

**How it works without API keys:**

DuckDuckGo provides a FREE public API:
```
https://api.duckduckgo.com/?q=QUERY&format=json
```

No authentication needed! The bot just makes HTTP requests.

**Example:**
```python
# Bot makes this request:
GET https://api.duckduckgo.com/?q=Master+Chief+Halo&format=json

# Gets back:
{
  "Heading": "Master Chief (Halo)",
  "Abstract": "Master Chief Petty Officer John-117...",
  "AbstractURL": "https://en.wikipedia.org/wiki/Master_Chief_(Halo)"
}
```

**Limitations:**
- Only returns "instant answers" (Wikipedia summaries, etc.)
- Not full web search (for that, need Google API with key)
- Good enough for facts, definitions, summaries

### User Profiles Not Being Created

**NOW FIXED!** The integration is complete. Profiles will be created in:
```
data/user_profiles/user_123456789.json
```

After you chat with the bot, check that directory.

### Web Search Not Working

Web search service exists but ISN'T integrated yet. It needs to be:
1. Added to main.py
2. Connected to ChatCog
3. Called when appropriate queries detected

**Status:** Prepared but not integrated (can add if you want).

---

## Project Organization

I'll now organize the project structure:

```
acore_bot/
├── main.py                 # Main bot entry point
├── config.py               # Configuration loader
├── .env                    # YOUR CONFIG (create from .env.example)
├── .env.example            # Template
│
├── services/               # Backend services
│   ├── ollama.py          # LLM service
│   ├── tts.py             # Text-to-speech
│   ├── kokoro_tts.py      # Kokoro TTS implementation
│   ├── rvc.py             # RVC (local mode)
│   ├── rvc_webui.py       # RVC (WebUI API mode)
│   ├── rvc_unified.py     # RVC wrapper
│   ├── user_profiles.py   # User memory system ✅
│   ├── web_search.py      # Internet search ⏳ (not integrated)
│   ├── rag.py             # Document retrieval
│   └── mcp.py             # Model Context Protocol
│
├── cogs/                   # Discord command modules
│   ├── chat.py            # Chat commands ✅ (updated)
│   └── voice.py           # Voice commands
│
├── utils/                  # Helper functions
│   └── helpers.py         # Utilities, TTS cleaning ✅
│
├── prompts/                # Character personalities
│   ├── chief.txt          # Master Chief ✅
│   ├── arbiter.txt        # The Arbiter ✅
│   ├── arby.txt           # Both characters ✅
│   ├── default.txt
│   ├── pirate.txt
│   └── ...
│
├── data/                   # Runtime data
│   ├── user_profiles/     # User JSON files (auto-created)
│   ├── chat_history/      # Conversation history
│   ├── temp/              # Temporary audio files
│   └── voice_models/      # RVC models
│
├── docs/                   # 📚 DOCUMENTATION (to organize)
│   ├── setup/
│   │   ├── QUICK_START.md (this file)
│   │   ├── STHENO_SETUP.md
│   │   ├── RVC_WEBUI_SETUP.md
│   │   └── README.md
│   ├── features/
│   │   ├── PERSONA_SWITCHING.md
│   │   ├── USER_MEMORY_SYSTEM.md
│   │   ├── WEB_SEARCH.md
│   │   ├── TTS_CLEANING.md
│   │   └── VOICE_FEATURES.md
│   └── session/
│       ├── SESSION_SUMMARY.md
│       └── CONVERSATION_SESSIONS.md
│
├── tests/                  # 🧪 TEST SCRIPTS (to organize)
│   ├── test_bot.py
│   ├── test_kokoro.py
│   ├── test_rvc.py
│   ├── test_rvc_webui.py
│   ├── test_stheno_characters.py
│   └── test_tts_cleaning.py
│
└── models/                 # AI model files
    ├── kokoro-v1.0.onnx
    ├── voices-v1.0.bin
    ├── rmvpe.pt
    └── hubert_base.pt
```

---

## What's Working NOW

✅ Ollama with Stheno model (roleplay-optimized)
✅ Character system prompts (Chief & Arbiter)
✅ Persona switching commands (`/set_persona`, `/list_personas`)
✅ TTS text cleaning (no more "asterisk sighs")
✅ User profile system (JUST INTEGRATED!)
✅ Affection/relationship system (integrated with profiles)
✅ Kokoro TTS (high-quality local voices)

## What's Prepared But Not Integrated

⏳ Web search service (code exists, needs integration)
⏳ RVC voice conversion (needs RVC-WebUI setup)
⏳ Profile viewing commands (`/my_profile`, `/relationship`)

---

## Next Steps

1. **Create new .env** from template above
2. **Restart bot** to register new commands
3. **Test persona switching**: `/set_persona chief`
4. **Chat with bot** to create your user profile
5. **Check** `data/user_profiles/` for your JSON file

---

## Need Help?

- Commands not showing? Wait 1 hour or kick/re-invite bot
- Ollama not connecting? Check host: `http://192.168.0.15:11434`
- User profiles? Check `.env`: `USER_PROFILES_ENABLED=true`
- Web search? Not integrated yet (can add if needed)

Want me to integrate web search into the chat flow? Let me know!
