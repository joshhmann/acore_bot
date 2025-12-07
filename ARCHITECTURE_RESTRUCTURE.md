# System Architecture Restructure Progress

> **Goal**: Transform the monolithic Discord bot into a modular, service-oriented architecture - "SillyTavern for Discord"

---

## Vision

A Discord bot with:
- **Pluggable LLM backends** (Ollama, OpenRouter, KoboldAI, etc.)
- **External AI services** (TTS, STT, RVC) as separate API services
- **Character/persona system** with memory
- **Clean, maintainable codebase** with clear separation of concerns

---

## External Services Status

| Service | Type | Status | Port | Notes |
|---------|------|--------|------|-------|
| **Kokoro TTS** | External API | ✅ Running | 8880 | Pre-existing, uses `kokoro_api_client.py` |
| **Parakeet STT** | External API | ✅ Running | 8890 | NEW - Migrated from in-process model |
| **Ollama LLM** | External API | ✅ Running | 11434 | Pre-existing |
| **RVC WebUI** | External API | ✅ Running | 7865 | Pre-existing, uses `rvc_http.py` |
| **OpenRouter** | External API | ✅ Available | - | Cloud LLM alternative |

---

## Completed Work

### Phase 1: Parakeet STT Service Migration ✅
**Completed: 2024-12-06**

1. **Cloned parakeet-fastapi service** to `/root/parakeet-api`
   - Source: https://github.com/Shadowfita/parakeet-tdt-0.6b-v2-fastapi
   
2. **Created systemd service** `/etc/systemd/system/parakeet-api.service`
   ```bash
   systemctl enable parakeet-api
   systemctl start parakeet-api
   ```

3. **Created API client** `services/parakeet_api_client.py`
   - `ParakeetAPIClient` - Low-level HTTP client
   - `ParakeetAPIService` - High-level service matching old interface

4. **Updated main.py** to use `ParakeetAPIService` instead of loading model in-process

5. **Added config** `PARAKEET_API_URL` (default: http://localhost:8890)

6. **Verified** - Round-trip test: TTS → audio file → STT → text ✅

**Benefits achieved:**
- ~2.5GB VRAM freed from bot process
- Bot can restart without reloading STT model
- STT service can be updated independently

### Phase 2-3: Cleanup & Reorganization ✅
- Moved API clients to `services/clients/` directory
- Archived old planning docs to `archive/docs/`

### Phase 4: AI-First Cleanup ✅
**Completed: 2024-12-06**

**Deprecated 12 files, ~5,642 lines total:**
| File | Lines | Reason |
|------|-------|--------|
| `services/web_dashboard.py` | 2,009 | Unused |
| `services/intent_recognition.py` | 720 | Replaced by LLM tool calling |
| `services/trivia.py` | 473 | Not core |
| `services/intent_handler.py` | 328 | Part of intent system |
| `services/custom_intents.py` | 368 | Part of intent system |
| `services/parakeet_stt.py` | 238 | Replaced by API |
| `services/kokoro_tts.py` | 222 | Using Kokoro API |
| `services/supertonic_tts.py` | 195 | Unused alternative |
| `cogs/trivia.py` | 398 | Not core |
| `cogs/game_helper.py` | 165 | Not core |
| `cogs/games.py` | 95 | Not core |
| `cogs/intent_commands.py` | 376 | Part of intent system |

**Key change:** Bot is now **AI-first** - the LLM handles intents via tool calling instead of hardcoded regex patterns.

---

## Current Codebase Structure

```
acore_bot/
├── main.py                     # Bot entry point (733 lines - needs slimming)
├── config.py                   # All configuration
│
├── services/                   # 45+ files - NEEDS CLEANUP
│   ├── parakeet_api_client.py  # NEW - STT API client
│   ├── parakeet_stt.py         # LEGACY - In-process model (can remove)
│   ├── kokoro_api_client.py    # TTS API client
│   ├── ollama.py               # LLM client
│   ├── openrouter.py           # LLM client (cloud)
│   ├── rvc_http.py             # RVC API client
│   ├── tts.py                  # TTS orchestrator
│   ├── enhanced_voice_listener.py
│   ├── rag.py
│   ├── user_profiles.py
│   ├── ambient_mode.py
│   ├── ... (35+ more)
│
├── cogs/                       # Discord commands
│   ├── chat/                   # Chat cog (refactored)
│   ├── voice/                  # Voice cog (partially refactored)
│   ├── music.py
│   └── ... (others)
│
└── utils/                      # Helpers
```

---

## Next Steps (Priority Order)

### Phase 2: Cleanup Legacy Code ✅
- [x] Move `services/parakeet_stt.py` to deprecated/ (replaced by API client)
- [x] Archive old planning docs to archive/docs/
- [ ] Remove `services/whisper_stt.py` if not used (still in use as fallback)

### Phase 3: Reorganize Services Directory ✅
Created `services/clients/` for external API clients:
```
services/clients/
├── __init__.py
├── stt_client.py     # Parakeet API (was parakeet_api_client.py)
├── tts_client.py     # Kokoro API (was kokoro_api_client.py)
└── rvc_client.py     # RVC WebUI (was rvc_http.py)
```

### Phase 4: Slim Down main.py
- [ ] Move service initialization to factory functions
- [ ] Create proper dependency injection
- [ ] Target: ~200 lines

### Phase 5: Complete Voice Cog Refactor
- [x] Extract VoiceManager
- [ ] Extract Voice Commands
- [ ] Extract Listening Handler
- [ ] Extract TTS Handler

---

## Service Dependencies

```
┌─────────────────────────────────────────────────────┐
│                  External Services                   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │ Kokoro │ │Parakeet│ │ Ollama │ │  RVC   │       │
│  │  :8880 │ │  :8890 │ │ :11434 │ │ :7865  │       │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘       │
└──────┼──────────┼──────────┼──────────┼────────────┘
       │          │          │          │
       └──────────┴────┬─────┴──────────┘
                       │ HTTP APIs
             ┌─────────┴─────────┐
             │   Discord Bot     │
             │   (acore_bot)     │
             │                   │
             │  ┌─────────────┐  │
             │  │ API Clients │  │
             │  └──────┬──────┘  │
             │         │         │
             │  ┌──────┴──────┐  │
             │  │  Features   │  │
             │  │ RAG,Persona │  │
             │  │ Memory,etc  │  │
             │  └──────┬──────┘  │
             │         │         │
             │  ┌──────┴──────┐  │
             │  │    Cogs     │  │
             │  │ Commands    │  │
             │  └─────────────┘  │
             └───────────────────┘
```

---

## Commands Reference

```bash
# Check service status
systemctl status parakeet-api
systemctl status discordbot

# Restart services
systemctl restart parakeet-api
systemctl restart discordbot

# View logs
journalctl -u parakeet-api -f
journalctl -u discordbot -f

# Test Parakeet API
curl http://localhost:8890/healthz
curl -X POST http://localhost:8890/transcribe -F "file=@audio.wav"

# VRAM usage
nvidia-smi
```

---

## Session Log

### 2024-12-06 (Session 2)
- **Phase 2: Cleanup** - Moved legacy parakeet_stt.py to deprecated/, archived old docs
- **Phase 3: Reorganize** - Created `services/clients/` directory with API clients
- Moved `parakeet_api_client.py` → `clients/stt_client.py`
- Moved `kokoro_api_client.py` → `clients/tts_client.py`
- Moved `rvc_http.py` → `clients/rvc_client.py`
- Updated all imports, bot running successfully ✅

### 2024-12-06 (Session 1)
- Discussed architecture vision ("SillyTavern for Discord")
- Set up Parakeet STT as external API service
- Created `parakeet_api_client.py`
- Updated bot to use API client
- Verified with round-trip TTS→STT test ✅

---

*Last updated: 2024-12-06 22:10*
