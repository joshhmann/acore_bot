# Test Scripts

This directory contains test scripts for various bot components.

## Running Tests

Make sure the bot is configured (`.env` file exists) and dependencies are installed.

### Full Integration Test
```bash
python tests/test_bot.py
```
Tests: Ollama, TTS, RVC, full pipeline

### Individual Component Tests

**Ollama/Chat:**
```bash
python tests/check_bot_status.py
```

**Kokoro TTS:**
```bash
python tests/test_kokoro.py
```

**RVC Voice Conversion:**
```bash
python tests/test_rvc_http.py
```

**User Profiles:**
```bash
python tests/test_profile_learning.py
```

## Test Files

- `test_bot.py` - Full integration test
- `check_bot_status.py` - Service health checks
- `check_commands.py` - Command registration test
- `test_kokoro.py` - Kokoro TTS test
- `test_rvc_http.py` - RVC HTTP client test
- `test_rvc_*.py` - Various RVC implementation tests
- `test_profile_learning.py` - User profile system test

## Requirements

- Bot configuration in `.env`
- Ollama running (`ollama serve`)
- RVC-WebUI running (for RVC tests)
- Models downloaded (auto-download on first run)

## Notes

- Tests create temporary files in project root
- Test outputs are `.gitignore`d
- Some tests require external services (Ollama, RVC-WebUI)
