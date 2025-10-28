# Voice Setup Summary

## What We've Done

### 1. Installed Kokoro TTS
- ✅ Installed `kokoro-onnx` package
- ✅ Downloaded model files (335MB):
  - `kokoro-v1.0.onnx` (310MB)
  - `voices-v1.0.bin` (25MB)
- ✅ Created Kokoro TTS service at [services/kokoro_tts.py](services/kokoro_tts.py)

### 2. Generated Voice Test Samples

#### Edge TTS Samples (cloud-based, MP3):
**Chief voices:**
- [test_chief_guy.mp3](test_chief_guy.mp3) - Deep, masculine
- [test_chief_christopher.mp3](test_chief_christopher.mp3) - Solid male
- [test_chief_eric.mp3](test_chief_eric.mp3) - Younger sounding

**Arby voices:**
- [test_arby_ryan.mp3](test_arby_ryan.mp3) - British (sophisticated)
- [test_arby_davis.mp3](test_arby_davis.mp3) - Calm US male
- [test_arby_tony.mp3](test_arby_tony.mp3) - Professional US male

#### Kokoro TTS Samples (local, WAV, higher quality):
**Chief voices:**
- [test_kokoro_chief_am_adam.wav](test_kokoro_chief_am_adam.wav) - Deep male
- [test_kokoro_chief_am_eric.wav](test_kokoro_chief_am_eric.wav) - Standard male
- [test_kokoro_chief_am_liam.wav](test_kokoro_chief_am_liam.wav) - Male option
- [test_kokoro_chief_am_michael.wav](test_kokoro_chief_am_michael.wav) - Male voice
- [test_kokoro_chief_am_onyx.wav](test_kokoro_chief_am_onyx.wav) - Male voice

**Arby voices:**
- [test_kokoro_arby_bm_george.wav](test_kokoro_arby_bm_george.wav) - British (sophisticated)
- [test_kokoro_arby_bm_lewis.wav](test_kokoro_arby_bm_lewis.wav) - British (refined)
- [test_kokoro_arby_bm_daniel.wav](test_kokoro_arby_bm_daniel.wav) - British
- [test_kokoro_arby_am_adam.wav](test_kokoro_arby_am_adam.wav) - Deep US male

## Voice Recommendations

### For Arby n the Chief:

**Master Chief (aggressive, caps, internet speak):**
- **Kokoro**: `am_onyx` or `am_adam` (deep, powerful)
- **Edge TTS**: `en-US-GuyNeural` (deep, aggressive)

**The Arbiter (calm, proper, intelligent):**
- **Kokoro**: `bm_george` or `bm_lewis` (British, sophisticated)
- **Edge TTS**: `en-GB-RyanNeural` (British, refined)

## Next Steps

### To Use Kokoro TTS in Your Bot:

1. **Update config** to support Kokoro:
```python
# In config.py
TTS_ENGINE: str = os.getenv("TTS_ENGINE", "edge")  # "edge" or "kokoro"
KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "am_adam")
```

2. **Update .env file**:
```bash
TTS_ENGINE=kokoro
KOKORO_VOICE=am_adam
```

3. **Integrate into bot** - modify [services/tts.py](services/tts.py) to use KokoroTTSService

### For Arby n Chief Specifically:

1. **Create character-specific prompts** in `prompts/`:
   - `prompts/chief.txt` - Master Chief personality
   - `prompts/arby.txt` - Arbiter personality (already exists!)

2. **Map characters to voices**:
```python
CHARACTER_VOICES = {
    "chief": "am_onyx",    # Deep, aggressive
    "arby": "bm_george",   # British, sophisticated
}
```

3. **Listen to test files** and pick your favorites!

## RVC (Voice Conversion) Status

See [RVC_SETUP.md](RVC_SETUP.md) for details.

**TL;DR**: RVC has dependency issues with Python 3.13. Recommended alternatives:
- Use Kokoro TTS directly (already high quality)
- Set up RVC in Python 3.12 environment
- Use RVC-WebUI API separately

## Available Kokoro Voices

Kokoro has **50 voices** across multiple languages:
- **US English**: 19 voices (11 female, 8 male)
- **British English**: 8 voices (4 female, 4 male)
- Plus French, Italian, Japanese, Mandarin, Portuguese

Run `python -c "from kokoro_onnx import Kokoro; k = Kokoro('kokoro-v1.0.onnx', 'voices-v1.0.bin'); print('\n'.join(k.get_voices()))"` to see all voices.
