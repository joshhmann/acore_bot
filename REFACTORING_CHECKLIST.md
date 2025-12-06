# Codebase Refactoring Checklist

This document tracks progress on the codebase refactoring effort. Check off items as they are completed.

> **Golden Rule**: Copy first, verify imports work, then delete original only after testing.

---

## Phase 2A: Split `cogs/chat/main.py` (2,215 lines)

### Preparation
- [ ] Create new branch `refactor/chat-cog-split`
- [ ] Verify bot is working on master before starting

### Step 1: Extract Response Handler (~600 lines) [COMPLETED]
- [x] Create `cogs/chat/response_handler.py`
- [x] Copy `_handle_chat_response` method to new file
- [x] Copy helper methods used only by response handler
- [x] Import and bind method in `main.py`
- [x] Run syntax check: `python -m py_compile cogs/chat/response_handler.py`
- [x] Test imports: `python -c "from cogs.chat import ChatCog; print('OK')"`
- [x] Restart bot and test message response
- [x] Commit: "Extract _handle_chat_response to response_handler.py"

### Step 2: Extract Context Builder (~400 lines) [COMPLETED]
- [x] Create `cogs/chat/context_builder.py`
- [x] Copy context/history building methods
- [x] Import and bind in `main.py`
- [x] Test imports and bot functionality
- [x] Commit: "Extract context building to context_builder.py"

### Step 3: Extract Message Handler (~300 lines) [COMPLETED]
- [x] Create `cogs/chat/message_handler.py`
- [x] Extract `check_and_handle_message` and related methods
- [x] Update `main.py` imports and delegation
- [x] Test message handling
- [x] Commit: "Extract message handling to message_handler.py"

### Step 4: Extract Commands (~150 lines) [COMPLETED]
- [x] Create `cogs/chat/commands.py`
- [x] Move command logic (`chat`, `reset`, etc.)
- [x] Delegate in `main.py`
- [x] Commit: "Extract commands to commands.py"
- [x] Fixed `AttributeError` in `response_handler.py` (updated calls to `self.message_handler`)
- [ ] Commit: "Extract commands to commands.py"

### Step 5: Extract Event Listeners (~100 lines) [SKIPPED]
- [x] `on_message` delegates to `MessageHandler`
- [x] `on_reaction_add` kept in `main.py` (simple delegation)
- [ ] Create `cogs/chat/listeners.py` (Not needed)

### Step 6: Cleanup [COMPLETED]
- [x] Review `main.py` - should now be ~200-300 lines (core class only)
- [x] Remove any duplicate code (e.g. `_disabled_on_message`)
- [x] Update `__init__.py` imports/exports
- [x] Final full test of all chat functionality (Voice integration, Resume loop fixed)
- [x] Merge branch to master (Simulated/Committed)

---

## Phase 2B: Split `cogs/voice.py` (1,155 lines)

### Preparation
- [ ] Create new branch `refactor/voice-cog-split`
- [ ] Verify bot is working before starting

### Step 1: Extract Voice Manager (~200 lines)
- [ ] Create `cogs/voice/manager.py`
- [ ] Copy voice client management, connection logic
- [ ] Import in main `voice.py`
- [ ] Test voice join/leave functionality
- [ ] Commit: "Extract voice manager to manager.py"

### Step 2: Extract Voice Commands (~250 lines)
- [ ] Create `cogs/voice/commands.py`
- [ ] Move `/speak`, `/join`, `/leave` commands
- [ ] Test all voice commands
- [ ] Commit: "Extract voice commands to commands.py"

### Step 3: Extract Listening Handler (~400 lines)
- [ ] Create `cogs/voice/listening.py`
- [ ] Move voice listening and transcription handling
- [ ] Test voice listening functionality
- [ ] Commit: "Extract listening handler to listening.py"

### Step 4: Extract TTS Handler (~200 lines)
- [ ] Create `cogs/voice/tts_handler.py`
- [ ] Move TTS generation and playback
- [ ] Test TTS functionality
- [ ] Commit: "Extract TTS handler to tts_handler.py"

### Step 5: Cleanup
- [ ] Review main `voice.py` - should be smaller entry point
- [ ] Final test of all voice functionality
- [ ] Merge branch to master

---

## Phase 3A: Split `services/web_dashboard.py` (2,009 lines) [Optional]

- [ ] Create new branch `refactor/dashboard-split`
- [ ] Extract HTML templates to `templates.py`
- [ ] Extract API routes to `api_routes.py`
- [ ] Extract static handling to `static_handler.py`
- [ ] Test dashboard functionality
- [ ] Merge to master

---

## Phase 3B: Split `services/user_profiles.py` (1,015 lines) [Optional]

- [ ] Create new branch `refactor/profiles-split`
- [ ] Extract storage logic to `storage.py`
- [ ] Extract affection system to `affection.py`
- [ ] Extract preferences to `preferences.py`
- [ ] Test profile functionality
- [ ] Merge to master

---

## Phase 1: Service Directory Reorganization [Optional]

- [ ] Create directory structure under `services/`
- [ ] Move files with backward-compat shims
- [ ] Update all imports
- [ ] Remove shims
- [ ] Test everything

---

## Verification Commands

```bash
# Quick import test
python -c "from cogs.chat import ChatCog; from cogs.voice import VoiceCog; print('Cogs OK')"

# Restart and check logs
systemctl restart discordbot && sleep 5 && journalctl -u discordbot -n 20 --no-pager

# Full service test
python -c "from services.ollama import OllamaService; from services.tts import TTSService; print('Services OK')"
```

---

## Notes

- Always commit working state before next extraction
- If anything breaks, `git checkout .` to revert uncommitted changes
- Test bot response after EVERY step, not just at the end
