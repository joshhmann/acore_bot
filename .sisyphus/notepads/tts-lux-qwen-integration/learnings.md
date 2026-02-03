
## LuxTTSClient Implementation Learnings - Sun Feb  1 08:48:50 PM PST 2026

### Pattern: OpenAI-Compatible TTS Client

**File:** `services/clients/luxtts_client.py`

#### Key Design Decisions
1. **Followed KokoroAPIClient pattern exactly** - Session management, method signatures, error handling
2. **API URL defaults to port 9999** - LuxTTS default differs from Kokoro (8880)
3. **Model name hardcoded to 'luxtts'** - Required by API spec, not configurable
4. **response_format='wav'** - Hardcoded for Discord compatibility
5. **get_voices() fetches from API** - Unlike Kokoro's hardcoded list, LuxTTS requires dynamic voice discovery

#### LuxTTS API Specifics
- **POST /v1/audio/speech**: Requires {model: 'luxtts', input, voice, response_format, speed}
- **GET /health**: Returns {status: 'healthy', model, device, voices_count}
- **GET /v1/voices**: Returns {voices: [{voice_id, name}]}
- **Voice requirement**: Must upload voice samples first - no built-in voices

#### Error Handling Pattern
- Health check: Return False on errors (logging at debug/warning)
- Voices fetch: Return empty list on errors (logging at debug/warning)
- Generate: Raise RuntimeError with wrapped exception

#### Session Management
- Lazy initialization via _get_session()
- Explicit close() for cleanup
- Reuse across multiple API calls

#### Verification
- Syntax check passed: `python3 -m py_compile`
- No LSP errors in luxtts_client.py
