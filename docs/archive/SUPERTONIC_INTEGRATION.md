# Supertonic TTS Integration

## Overview

Supertonic TTS has been successfully integrated as an alternative TTS engine alongside Edge TTS and Kokoro TTS. Supertonic offers **ultra-fast speech synthesis** (167x real-time speed) with high quality output.

## Features

- **Ultra-Fast**: 167x real-time synthesis speed on CPU
- **High Quality**: 66M parameter model with configurable denoising steps
- **Multiple Voices**: 4 built-in voices (M1, M2, F1, F2)
- **Voice Aliases**: Easy-to-use aliases like "male", "female", "man", "woman"
- **Configurable**: Adjust quality (steps) and speech speed

## Installation

### Dependencies
All required dependencies are already installed:
- `onnxruntime` - ONNX inference runtime
- `soundfile` - Audio file I/O
- `librosa` - Audio processing
- `numpy` - Array operations

### Models
Models are installed at `/root/supertonic/assets/`:
- ONNX models: `onnx/` directory
- Voice styles: `voice_styles/` directory (M1.json, M2.json, F1.json, F2.json)
- Total size: ~251MB

## Configuration

### Enable Supertonic TTS

Update `.env` file:
```bash
# Switch to Supertonic TTS
TTS_ENGINE=supertonic

# Supertonic settings
SUPERTONIC_VOICE=M1  # M1, M2, F1, F2, or aliases: male, female, man, woman
SUPERTONIC_STEPS=5   # Denoising steps (1-20, higher = better quality)
SUPERTONIC_SPEED=1.05  # Speech speed multiplier (0.5-2.0)
```

### Available Voices

| Voice | Description | Alias |
|-------|-------------|-------|
| M1 | Male voice 1 (default) | male, male1, man, default |
| M2 | Male voice 2 | male2 |
| F1 | Female voice 1 (default) | female, female1, woman |
| F2 | Female voice 2 | female2 |

### Quality vs Speed

**Denoising Steps** (SUPERTONIC_STEPS):
- `3` - Fastest, lower quality
- `5` - Recommended balance (default)
- `10` - Higher quality, slower
- `15-20` - Best quality, slowest

**Speech Speed** (SUPERTONIC_SPEED):
- `0.8-0.9` - Slower, more deliberate
- `1.0` - Normal speed
- `1.05` - Slightly faster (default)
- `1.2-1.5` - Faster speech

## Usage

### In Discord Bot

Once configured, Supertonic will be used automatically for all TTS:
```
@Bot speak Hello! This is Supertonic TTS.
```

### Programmatic Usage

```python
from services.supertonic_tts import SupertonicTTSService

# Create service
tts = SupertonicTTSService(
    default_voice="M1",
    default_steps=5,
    default_speed=1.05
)

# Generate speech
output_path = tts.generate(
    text="Welcome to Morrowind!",
    voice="M1",  # or "male", "female", etc.
    steps=5,
    speed=1.05,
    output_path="/tmp/speech.wav"
)
```

### Testing

Run the test script:
```bash
uv run python test_supertonic.py
```

Expected output:
```
✓ Supertonic TTS available
✓ Available voices: {...}
✓ Speech generated successfully!
✓ File exists (818276 bytes)
```

## Technical Details

### Service Architecture

**File**: `services/supertonic_tts.py`

Key features:
- Lazy model loading (loads on first use)
- Voice style caching (reuses loaded styles)
- Support for custom voice style JSON files
- Automatic audio trimming to duration
- 24kHz WAV output (16-bit PCM)

### Integration Points

1. **TTS Service** (`services/tts.py`):
   - Added Supertonic as third engine option
   - Async wrapper for sync generate method
   - Automatic fallback to Edge TTS on errors

2. **Configuration** (`config.py`):
   - `SUPERTONIC_VOICE` - Default voice
   - `SUPERTONIC_STEPS` - Quality setting
   - `SUPERTONIC_SPEED` - Speed multiplier

3. **Main Bot** (`main.py`):
   - Passes Supertonic config to TTS service
   - Initialized alongside Kokoro TTS

## Performance

**Benchmarks** (on CPU):
- Model load time: ~2-3 seconds
- Speech generation: 167x real-time
- Example: 9.28s audio generated in ~0.06s

**Memory Usage**:
- Model: ~250MB ONNX models
- Runtime: ~100-200MB during inference

## Comparison with Other Engines

| Feature | Edge TTS | Kokoro TTS | Supertonic TTS |
|---------|----------|------------|----------------|
| Speed | Slow (cloud) | Fast (local) | Ultra-fast (local) |
| Quality | High | Very High | High |
| Voices | 400+ | 100+ | 4 |
| Voice cloning | No | Yes | No |
| Offline | No | Yes | Yes |
| GPU required | No | No (optional) | No (optional) |

## Troubleshooting

### pthread_setaffinity_np warnings
These warnings from ONNXRuntime are harmless:
```
[E:onnxruntime:Default, env.cc:226 ThreadMain] pthread_setaffinity_np failed
```
They don't affect functionality.

### "Format not recognised" error
Fixed in current implementation - audio is trimmed before saving.

### Voice not found
Check voice name:
- Use exact names: M1, M2, F1, F2
- Or use aliases: male, female, man, woman
- Case-insensitive

### Slow generation
Increase speed or decrease steps:
```bash
SUPERTONIC_STEPS=3
SUPERTONIC_SPEED=1.2
```

## Files Modified

1. `services/supertonic_tts.py` - New service (220 lines)
2. `services/tts.py` - Added Supertonic support
3. `config.py` - Added Supertonic config options
4. `main.py` - Pass Supertonic params to TTS service
5. `.env.example` - Documented Supertonic options
6. `test_supertonic.py` - Test script

## Next Steps

To switch the bot to Supertonic TTS:

1. Edit `.env`:
   ```bash
   TTS_ENGINE=supertonic
   ```

2. Restart the bot:
   ```bash
   systemctl restart discordbot
   ```

3. Verify in logs:
   ```bash
   journalctl -u discordbot -f | grep -i supertonic
   ```

Expected log message:
```
INFO - Supertonic TTS initialized (voice: M1, steps: 5, speed: 1.05)
```

## Credits

- **Supertonic**: [Supertone Inc.](https://github.com/supertone-inc/supertonic)
- **Models**: Hosted on [Hugging Face](https://huggingface.co/Supertone/supertonic)
- **License**: Check Supertonic repository for details

---

**Status**: ✅ Fully integrated and tested
**Date**: 2025-11-23
**Version**: 1.0
