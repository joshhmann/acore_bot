# Test Scripts

This directory contains test scripts for various bot components.

## Running Tests

Make sure the bot is configured (`.env` file exists) and dependencies are installed.

### Phase 2 Optimization Tests

**LLM Response Caching:**
```bash
uv run python tests/test_llm_cache.py
```
Tests LLM cache functionality, hit rates, TTL expiration, and LRU eviction.

**LLM Fallback System:**
```bash
uv run python tests/test_llm_fallback.py
```
Tests model fallback chain (Amazon Nova → Grok → Gemini).

**OpenRouter Integration:**
```bash
uv run python tests/test_openrouter.py          # Service-level test
uv run python tests/test_openrouter_raw.py     # Raw API test
```
Tests OpenRouter API integration and response format validation.

### Voice Pipeline Tests

**Full Voice Pipeline:**
```bash
uv run python tests/test_voice_pipeline.py
```
Tests: TTS (Kokoro), RVC conversion, STT (Whisper/Parakeet), voice commands.

**RVC Components:**
```bash
uv run python tests/test_rvc_client.py         # RVC client test
uv run python tests/test_bot_rvc_init.py       # RVC initialization test
```

### Integration Tests

**Full Pipeline:**
```bash
uv run python tests/test_full_pipeline.py
```
Tests the complete conversation pipeline end-to-end.

## Test Files

### Phase 2 Performance Tests
- `test_llm_cache.py` - LLM response caching (70% hit rate validation)
- `test_llm_fallback.py` - Model fallback system (free models only)
- `test_openrouter.py` - OpenRouter service test
- `test_openrouter_raw.py` - Raw OpenRouter API validation

### Voice & Audio Tests
- `test_voice_pipeline.py` - Complete voice pipeline (TTS → RVC → STT)
- `test_rvc_client.py` - RVC HTTP client
- `test_bot_rvc_init.py` - RVC initialization

### Integration Tests
- `test_full_pipeline.py` - End-to-end pipeline test

## Requirements

- Bot configuration in `.env`
- Ollama running (for local LLM tests)
- OpenRouter API key (for cloud LLM tests)
- Kokoro API running at `http://localhost:8880` (for TTS tests)
- RVC-WebUI running at `http://localhost:7865` (for voice conversion tests)

## Notes

- Tests are standalone and don't require Discord
- Most tests will auto-skip if required services are unavailable
- Tests create temporary files in project root (gitignored)
- Phase 2 optimizations tested: caching, fallback, rate limiting, async operations

## Additional Test Scripts

See `scripts/` directory for specialized tests:
- `scripts/test_optimizations.py` - Performance benchmarks
- `scripts/test_persona_system.py` - Persona system tests
- `scripts/test_pipeline_timing.py` - Pipeline timing analysis
