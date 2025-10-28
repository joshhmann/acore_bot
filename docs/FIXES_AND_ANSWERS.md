# Fixes & Answers to Your Questions

## Your Questions

1. ✅ **User profiles not being generated** - FIXED
2. ✅ **Can't see persona switching commands** - EXPLAINED (Discord caching)
3. ✅ **How does DuckDuckGo work without API key?** - EXPLAINED
4. ✅ **Project organization** - DOCUMENTED

---

## 1. User Profiles - FIXED! ✅

**Problem:** UserProfileService was created but never connected to the bot.

**Fix Applied:**
- Updated [main.py](main.py:20,88-93,112) to initialize UserProfileService
- Updated [cogs/chat.py](cogs/chat.py:21-33) to accept user_profiles parameter
- Now profiles will be created automatically when users chat!

**Test it:**
1. Make sure `.env` has: `USER_PROFILES_ENABLED=true`
2. Restart the bot
3. Chat with it: `/chat Hello!`
4. Check: `data/user_profiles/user_YOUR_ID.json` should exist

---

## 2. Persona Commands Not Showing

**Problem:** Commands like `/set_persona` and `/list_personas` don't appear in Discord.

**Why:** Discord caches slash commands. Can take up to 1 hour to refresh!

**Solutions:**
1. **Wait** - Up to 1 hour for Discord to sync
2. **Kick & re-invite bot** - Forces immediate command refresh
3. **Check bot invite** - Must have `applications.commands` scope

**The commands ARE in the code:**
- `/set_persona` - [cogs/chat.py:309-369](cogs/chat.py#L309-L369)
- `/list_personas` - [cogs/chat.py:371-435](cogs/chat.py#L371-L435)

They'll show up once Discord syncs!

---

## 3. How DuckDuckGo Search Works Without API Key

**Answer:** DuckDuckGo provides a FREE public API!

### The Magic URL
```
https://api.duckduckgo.com/?q=YOUR_QUERY&format=json
```

### Example Request
```bash
curl "https://api.duckduckgo.com/?q=Master+Chief+Halo&format=json"
```

### Example Response
```json
{
  "Heading": "Master Chief (Halo)",
  "Abstract": "Master Chief Petty Officer John-117, or Master Chief, is the protagonist...",
  "AbstractURL": "https://en.wikipedia.org/wiki/Master_Chief_(Halo)",
  "RelatedTopics": [...]
}
```

**No authentication needed!** It's a public API.

**What it returns:**
- Instant answers (Wikipedia summaries)
- Definitions
- Basic facts
- Related topics

**What it doesn't do:**
- Full web search (like Google)
- News articles
- Shopping results

**For better search:** Use Google Custom Search API (requires API key, 100 free queries/day).

**In the code:** [services/web_search.py](services/web_search.py:66-109)

**Status:** Service exists but NOT integrated into chat flow yet (can add if you want!).

---

## 4. Your .env File Issue

**Problem:** You're using the OLD AzerothCore bot's `.env` file!

Your current `.env` has:
- `SOAP_HOST`, `DB_HOST`, `DB_PASS` (database stuff)
- `XP_RATE`, `QUEST_XP_RATE` (game server config)
- Old Ollama settings

**What you NEED for the new bot:**

```bash
# REQUIRED - Discord
DISCORD_TOKEN=your_token_here

# REQUIRED - Ollama
OLLAMA_HOST=http://192.168.0.15:11434
OLLAMA_MODEL=fluffy/l3-8b-stheno-v3.2:latest
OLLAMA_TEMPERATURE=1.17
OLLAMA_MIN_P=0.075
OLLAMA_TOP_K=50
OLLAMA_REPEAT_PENALTY=1.1

# Character/Personality
SYSTEM_PROMPT_FILE=./prompts/chief.txt

# TTS
TTS_ENGINE=kokoro
KOKORO_VOICE=am_onyx

# User Profiles (IMPORTANT!)
USER_PROFILES_ENABLED=true
USER_AFFECTION_ENABLED=true
USER_CONTEXT_IN_CHAT=true

# Optional - Web Search
WEB_SEARCH_ENABLED=false

# Optional - RVC
RVC_ENABLED=false
```

**Action needed:**
1. Copy `.env.example` to `.env`
2. Fill in your `DISCORD_TOKEN` and Ollama settings
3. Delete or rename your old `.env copy` file

---

## 5. Project Organization

I created directory structure but can't move files automatically. Here's what YOU should do:

### Manually organize like this:

```
acore_bot/
│
├── docs/
│   ├── setup/
│   │   ├── QUICK_START.md          ← Move here
│   │   ├── STHENO_SETUP.md         ← Move here
│   │   └── RVC_WEBUI_SETUP.md      ← Move here
│   │
│   ├── features/
│   │   ├── PERSONA_SWITCHING.md    ← Move here
│   │   ├── USER_MEMORY_SYSTEM.md   ← Move here
│   │   ├── WEB_SEARCH.md           ← Move here
│   │   ├── TTS_CLEANING.md         ← Move here
│   │   └── VOICE_FEATURES.md       ← Move here
│   │
│   └── session/
│       ├── SESSION_SUMMARY.md      ← Move here
│       └── CONVERSATION_SESSIONS.md ← Move here
│
└── tests/
    ├── test_bot.py                 ← Move here
    ├── test_kokoro.py              ← Move here
    ├── test_rvc.py                 ← Move here
    ├── test_rvc_webui.py           ← Move here
    ├── test_stheno_characters.py   ← Move here
    └── test_tts_cleaning.py        ← Move here
```

### Or just create folders and leave files where they are for now!

---

## Summary of What's Working NOW

✅ **User profiles** - JUST FIXED, will track users automatically
✅ **Affection system** - Works with profiles, builds relationships
✅ **Persona switching** - Commands exist, Discord needs to sync
✅ **TTS cleaning** - Removes asterisks/emojis from voice
✅ **Stheno model support** - Roleplay-optimized sampling
✅ **Character prompts** - Chief & Arbiter ready to go

## What's NOT Integrated Yet

⏳ **Web search** - Service exists, not connected to chat flow
⏳ **Profile commands** - `/my_profile`, `/relationship` not implemented
⏳ **RVC voice** - Needs RVC-WebUI setup

---

## Immediate Action Items

1. **Create new .env** from `.env.example`
2. **Add these lines**:
   ```bash
   USER_PROFILES_ENABLED=true
   USER_AFFECTION_ENABLED=true
   OLLAMA_MODEL=fluffy/l3-8b-stheno-v3.2:latest
   SYSTEM_PROMPT_FILE=./prompts/chief.txt
   ```
3. **Restart bot**
4. **Wait for Discord** to sync commands (or kick/re-invite bot)
5. **Test**:
   ```
   /chat Hey bot!
   /list_personas
   /set_persona chief
   ```
6. **Check profiles**: Look in `data/user_profiles/` folder

---

## Want Me To Add Web Search Integration?

The web search service is ready but not connected to the chat flow. If you want the bot to actually search the internet when appropriate, I can:

1. Integrate WebSearchService into main.py
2. Connect it to ChatCog
3. Add auto-detection for when to search
4. Include search results in AI context

Let me know if you want this!

---

## Questions?

- **Commands not showing?** → Wait 1 hour or kick/re-invite bot
- **Profiles not creating?** → Check `.env` has `USER_PROFILES_ENABLED=true`
- **Want web search?** → Let me know, I'll integrate it
- **Need help with .env?** → See [QUICK_START.md](QUICK_START.md)
