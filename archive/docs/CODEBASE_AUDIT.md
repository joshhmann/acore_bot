# Codebase Audit - What's Actually Used

**Date**: 2025-12-01
**Purpose**: Compare what exists in code vs what's actually loaded and used

---

## Services Analysis (48 total service files)

### ✅ Directly Loaded in main.py (26 services)

| Service | Line | Condition | Status |
|---------|------|-----------|--------|
| `metrics.py` | 116 | Always | ✅ Active |
| `ollama.py` | 140 | LLM_PROVIDER != openrouter | ✅ Active |
| `openrouter.py` | 122 | LLM_PROVIDER == openrouter | ✅ Active |
| `tts.py` | 151 | Always | ✅ Active |
| `rvc_unified.py` | 166 | RVC_ENABLED | ✅ Active (conditional) |
| `user_profiles.py` | 183 | USER_PROFILES_ENABLED | ✅ Active (conditional) |
| `rag.py` | 192 | RAG_ENABLED | ✅ Active (conditional) |
| `memory_manager.py` | 202 | MEMORY_CLEANUP_ENABLED | ✅ Active (conditional) |
| `conversation_summarizer.py` | 213 | CONVERSATION_SUMMARIZATION_ENABLED | ✅ Active (conditional) |
| `whisper_stt.py` | 244 | WHISPER_ENABLED | ✅ Active (conditional) |
| `parakeet_stt.py` | 230 | PARAKEET_ENABLED | ✅ Active (conditional) |
| `enhanced_voice_listener.py` | 270 | STT enabled | ✅ Active (conditional) |
| `web_dashboard.py` | 280 | Always | ✅ Active |
| `naturalness.py` | 285 | NATURALNESS_ENABLED | ✅ Active (conditional) |
| `reminders.py` | 291 | REMINDERS_ENABLED | ✅ Active (conditional) |
| `notes.py` | 297 | NOTES_ENABLED | ✅ Active (conditional) |
| `web_search.py` | 303 | WEB_SEARCH_ENABLED | ✅ Active (conditional) |
| `trivia.py` | 312 | TRIVIA_ENABLED | ✅ Active (conditional) |
| `conversation_manager.py` | 319 | Always | ✅ Active |
| `persona_system.py` | 330 | USE_PERSONA_SYSTEM | ✅ Active (conditional) |
| `enhanced_tools.py` | 331 | USE_PERSONA_SYSTEM | ✅ Active (conditional) |
| `ai_decision_engine.py` | 341 | USE_PERSONA_SYSTEM | ✅ Active (conditional) |
| `proactive_callbacks.py` | 353 | Always | ✅ Active |
| `curiosity_system.py` | 357 | Always | ✅ Active |
| `pattern_learner.py` | 363 | Always | ✅ Active |
| `ambient_mode.py` | 369 | AMBIENT_MODE_ENABLED | ✅ Active (conditional) |

### 🔧 Used Indirectly (7 services)

These are not imported in main.py but are used by other services:

| Service | Used By | Status |
|---------|---------|--------|
| `music_player.py` | `cogs/music.py` | ✅ Active |
| `kokoro_tts.py` | `services/tts.py` | ✅ Active |
| `supertonic_tts.py` | `services/tts.py` | ✅ Active |
| `kokoro_api_client.py` | `services/kokoro_tts.py` | ✅ Active |
| `rvc_http.py` | `services/rvc_unified.py` | ✅ Active |
| `proactive_engagement.py` | `services/ambient_mode.py` | ✅ Active |
| `agentic_tools.py` | `services/enhanced_tools.py` | ✅ Active |

### ⚠️ Exists But NOT Loaded (9 services)

Code exists but is never instantiated anywhere:

| Service | Status | Notes |
|---------|--------|-------|
| `mood_system.py` | ⚠️ Inactive | Complete implementation, just not loaded |
| `environmental_awareness.py` | ⚠️ Incomplete | File appears empty/incomplete |
| `self_awareness.py` | ⚠️ Inactive | Never imported or used |
| `rhythm_matching.py` | ⚠️ Inactive | Never imported or used |
| `response_optimizer.py` | ⚠️ Inactive | Never imported or used |
| `query_optimizer.py` | ⚠️ Inactive | Never imported or used |
| `message_batcher.py` | ⚠️ Inactive | Never imported or used |
| `streaming_tts.py` | ⚠️ Inactive | Never used (TTS uses kokoro directly) |
| `sound_effects.py` | ⚠️ Inactive | Never imported or used |

### ❓ Unclear Status (6 services)

Need to verify if these are used:

| Service | Potentially Used By | Need to Check |
|---------|---------------------|---------------|
| `voice_commands.py` | Voice cogs? | Yes |
| `intent_recognition.py` | Voice/chat cogs? | Yes |
| `intent_handler.py` | Intent commands? | Yes |
| `custom_intents.py` | Intent commands? | Yes |
| `transcription_fixer.py` | STT services? | Yes |
| `conversational_callbacks.py` | Old version of proactive_callbacks? | Yes |

---

## Cogs Analysis (17 cog files)

### ✅ Loaded Cogs (16 active)

| Cog | Type | Line | Status |
|-----|------|------|--------|
| `chat.py` | Main | 413 | ✅ Active |
| `voice.py` | Main | 434 | ✅ Active |
| `music.py` | Main | 444 | ✅ Active |
| `reminders.py` | Main | 449 | ✅ Active (conditional) |
| `notes.py` | Main | 454 | ✅ Active (conditional) |
| `trivia.py` | Main | 459 | ✅ Active (conditional) |
| `memory_commands.py` | Extension | 464 | ✅ Active |
| `character_commands.py` | Extension | 466 | ✅ Active |
| `profile_commands.py` | Extension | 467 | ✅ Active |
| `search_commands.py` | Extension | 468 | ✅ Active |
| `intent_commands.py` | Extension | 469 | ✅ Active |
| `game_helper.py` | Extension | 472 | ✅ Active |
| `games.py` | Extension | 473 | ✅ Active |
| `help.py` | Extension | 474 | ✅ Active |
| `event_listeners.py` | Main | 478 | ✅ Active |
| `system.py` | Extension | 482 | ✅ Active |

### ❌ Not Loaded (1 cog)

| Cog | Status | Notes |
|-----|--------|-------|
| `persona_commands.py` | ❌ Deprecated | Commented out in main.py line 465 |

---

## Duplicate/Overlapping Functionality

### Identified Duplicates

**1. Proactive Systems (2 implementations)**
- `services/proactive_callbacks.py` - ✅ Used (main.py:353)
- `services/proactive_engagement.py` - ✅ Used by ambient_mode
- **Analysis**: Both are active but serve different purposes
  - `proactive_callbacks`: Remembers and references past topics
  - `proactive_engagement`: Decides when to jump into conversations
- **Recommendation**: Keep both, they complement each other

**2. Intent Systems (3 files)**
- `services/intent_recognition.py` - ❓ Status unclear
- `services/intent_handler.py` - ❓ Status unclear
- `services/custom_intents.py` - ❓ Status unclear
- **Need to check**: Which are actually used and if they duplicate

**3. Tool Systems (2 implementations)**
- `services/agentic_tools.py` - Used by enhanced_tools
- `services/enhanced_tools.py` - Loaded in main.py
- **Analysis**: Likely layered (enhanced wraps agentic)
- **Recommendation**: Check if this is intentional or duplicate

**4. STT Engines (2 implementations)**
- `services/whisper_stt.py` - ✅ Active
- `services/parakeet_stt.py` - ✅ Active
- **Analysis**: Alternatives, only one loaded at runtime
- **Recommendation**: Keep both for flexibility

**5. TTS Engines (3 implementations)**
- `services/kokoro_tts.py` - Used by tts.py
- `services/supertonic_tts.py` - Used by tts.py
- Edge TTS (in `services/tts.py`)
- **Analysis**: Alternatives, selected by TTS_ENGINE config
- **Recommendation**: Keep all, provides flexibility

---

## Dead Code Analysis

### Services That Can Be Deleted

**Definitely Dead (never used anywhere):**
1. `services/message_batcher.py` - ❌ Never imported
2. `services/streaming_tts.py` - ❌ Never imported (TTS uses kokoro directly)
3. `services/sound_effects.py` - ❌ Never imported

**Probably Old/Deprecated:**
4. `services/conversational_callbacks.py` - Likely replaced by proactive_callbacks

**Should Be Deleted or Activated:**
5. `services/mood_system.py` - Good code but not loaded
6. `services/environmental_awareness.py` - Incomplete implementation
7. `services/self_awareness.py` - Never used
8. `services/rhythm_matching.py` - Never used
9. `services/response_optimizer.py` - Never used
10. `services/query_optimizer.py` - Never used

### Cogs That Can Be Deleted

1. `cogs/persona_commands.py` - ❌ Deprecated (replaced by character_commands)

---

## Missing Features vs Documentation

### Features in FEATURES.md but NOT in Code

None found - documentation was accurate!

### Features in Code but NOT in FEATURES.md

Found and documented in FEATURES.md:
- ✅ Game Helper
- ✅ Notes System
- ✅ Curiosity System
- ✅ Pattern Learner

---

## Consolidation Opportunities

### 1. Intent System Consolidation

**Current situation:**
- `services/intent_recognition.py` - 239 lines
- `services/intent_handler.py` - Status unknown
- `services/custom_intents.py` - Status unknown
- `cogs/intent_commands.py` - Manages custom intents

**Recommendation:**
- Audit which are actually used
- Consolidate into single intent system
- Remove duplicates

### 2. Naturalness Features

**Current situation:**
- `services/naturalness.py` - Active
- `services/mood_system.py` - NOT active
- `services/environmental_awareness.py` - Incomplete
- `services/self_awareness.py` - NOT active
- `services/rhythm_matching.py` - NOT active
- `services/response_optimizer.py` - NOT active

**Recommendation:**
- Either activate or delete mood_system
- Delete or complete environmental_awareness
- Consolidate naturalness features into naturalness.py
- Delete unused services

### 3. TTS/Audio Pipeline

**Current situation:**
- `services/tts.py` - Main service, wraps others
- `services/kokoro_tts.py` - Used by tts.py
- `services/supertonic_tts.py` - Used by tts.py
- `services/streaming_tts.py` - NOT used
- `services/kokoro_api_client.py` - Used by kokoro_tts
- `services/sound_effects.py` - NOT used

**Recommendation:**
- Delete streaming_tts.py (dead code)
- Delete or activate sound_effects.py
- Keep current structure for TTS (it's clean)

---

## Recommendations Summary

### 🔥 High Priority - Delete Dead Code

**Services to Delete (8 files):**
1. `services/message_batcher.py` - Dead
2. `services/streaming_tts.py` - Dead
3. `services/sound_effects.py` - Dead
4. `services/conversational_callbacks.py` - Likely old version
5. `services/query_optimizer.py` - Never used
6. `services/response_optimizer.py` - Never used
7. `services/self_awareness.py` - Never used
8. `services/rhythm_matching.py` - Never used

**Cogs to Delete (1 file):**
1. `archive/cogs/persona_commands.py` - Already deprecated

**Potential savings: 9 files**

### ⚡ Medium Priority - Activate or Delete

**Either activate these in main.py OR delete them:**
1. `services/mood_system.py` - Complete code, just not loaded
2. `services/environmental_awareness.py` - Incomplete, fix or delete

**Decision needed: 2 files**

### 🔍 Low Priority - Investigate

**Check if these are actually used:**
1. `services/voice_commands.py`
2. `services/intent_recognition.py`
3. `services/intent_handler.py`
4. `services/custom_intents.py`
5. `services/transcription_fixer.py`

**Need investigation: 5 files**

---

## Next Steps

### Phase 1: Quick Wins (Delete Dead Code)
- [ ] Delete 8 confirmed dead services
- [ ] Delete deprecated persona_commands cog
- [ ] Test that nothing breaks
- [ ] Commit changes

### Phase 2: Investigation
- [ ] Check if "unclear status" services are used
- [ ] Grep codebase for imports of each
- [ ] Delete additional unused code

### Phase 3: Consolidation
- [ ] Decide: Activate or delete mood_system
- [ ] Fix or delete environmental_awareness
- [ ] Consolidate intent system if duplicates found
- [ ] Update documentation

### Phase 4: Verification
- [ ] Run full bot test
- [ ] Verify all features still work
- [ ] Update FEATURES.md with final status

---

## Metrics

### Current State
- **Services**: 48 files
- **Actually used**: 33 files (69%)
- **Dead code**: 9 files (19%)
- **Unclear**: 6 files (12%)

### After Cleanup (Projected)
- **Services**: 39-43 files (depends on investigation)
- **Reduction**: 5-9 files (10-19%)

### Cogs
- **Current**: 17 files
- **Actually used**: 16 files
- **Deprecated**: 1 file

---

## Conclusion

The codebase is in **pretty good shape** overall:
- 69% of services are actively used
- Most "dead" code is small/isolated
- No major duplicate functionality found
- Documentation matches reality well

**Main issues:**
1. Several inactive naturalness features (mood, env awareness, etc.)
2. Some dead services that can be deleted
3. Intent system needs investigation for duplicates

**After cleanup**: Should reduce to ~40 service files (down from 48), making the codebase leaner and easier to maintain.
