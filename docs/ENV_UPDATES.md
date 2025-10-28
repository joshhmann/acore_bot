# Environment Configuration Updates

## New Settings Added

Your `.env.example` has been updated with Kokoro TTS support. Here's what you need to add to your actual `.env` file:

## Add These Lines to Your `.env` File:

```bash
# TTS Engine Selection
TTS_ENGINE=kokoro  # Options: "edge" (cloud) or "kokoro" (local)

# Kokoro TTS Settings
KOKORO_VOICE=am_adam
KOKORO_SPEED=1.0

# Character-specific voices (optional - for multiple personalities)
KOKORO_VOICE_CHIEF=am_onyx    # Deep, aggressive voice for Chief
KOKORO_VOICE_ARBY=bm_george   # British, sophisticated voice for Arby

# RVC Device (if using RVC)
RVC_DEVICE=cpu  # Use "cuda:0" if you have a GPU
```

## Quick Setup Options

### Option 1: Use Kokoro TTS (Recommended)
```bash
TTS_ENGINE=kokoro
KOKORO_VOICE=am_adam
RVC_ENABLED=false
```

### Option 2: Use Edge TTS
```bash
TTS_ENGINE=edge
DEFAULT_TTS_VOICE=en-US-GuyNeural
RVC_ENABLED=false
```

### Option 3: Use Kokoro + RVC (Best Quality)
```bash
TTS_ENGINE=kokoro
KOKORO_VOICE=am_adam
RVC_ENABLED=true
DEFAULT_RVC_MODEL=your_model_name
RVC_DEVICE=cpu
```

## Available Kokoro Voices

### US English Male Voices:
- `am_adam` - Deep, clear
- `am_eric` - Standard male
- `am_liam` - Natural sounding
- `am_michael` - Smooth voice
- `am_onyx` - **Deep, powerful (good for Chief!)**

### British English Male Voices:
- `bm_george` - **Sophisticated (perfect for Arby!)**
- `bm_lewis` - Refined British accent
- `bm_daniel` - Clear British voice
- `bm_fable` - Storyteller voice

### Female Voices:
- `af_sarah`, `af_nova`, `af_bella`, `af_jessica` (US)
- `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily` (British)

To see all 50 voices:
```bash
.venv311\Scripts\python.exe -c "from kokoro_onnx import Kokoro; k=Kokoro('kokoro-v1.0.onnx','voices-v1.0.bin'); print('\n'.join(k.get_voices()))"
```

## Character-Specific Voice Configuration

If you want different voices for different characters (like Arby n the Chief), you can use:

```bash
# In your .env file:
KOKORO_VOICE_CHIEF=am_onyx
KOKORO_VOICE_ARBY=bm_george
```

Then in your bot code, you can switch voices based on which character is speaking!

## Testing Your Configuration

After updating your `.env`, test with:

```bash
# Test Kokoro TTS
.venv311\Scripts\python.exe test_kokoro.py

# Test with your bot configuration
.venv311\Scripts\python.exe main.py
```

## Notes

- **Kokoro** = Local, high quality, no internet needed, 50 voices
- **Edge TTS** = Cloud-based, hundreds of voices, requires internet
- **RVC** = Voice conversion, needs models, highest quality but slower
- Change `TTS_ENGINE` anytime to switch between Edge and Kokoro!
