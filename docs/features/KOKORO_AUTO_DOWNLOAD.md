# Kokoro TTS Auto-Download

The Kokoro TTS service now automatically downloads model files on first run.

## Overview

When you first run the bot with `TTS_ENGINE=kokoro`, the bot will automatically download the required model files (~336MB total) from the official Kokoro TTS releases.

## What Gets Downloaded

1. **kokoro-v1.0.onnx** (~311MB) - Main TTS model
2. **voices-v1.0.bin** (~25MB) - Voice data for 50+ voices

## How It Works

```python
# On initialization, KokoroTTSService checks if models exist
if not self.model_path.exists() or not self.voices_path.exists():
    logger.info("Kokoro model files not found, attempting to download...")
    self._download_models()
```

Models are downloaded from:
- https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
- https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin

## First Run Experience

```bash
$ python main.py
2025-10-27 20:00:00 | INFO | Kokoro model files not found, attempting to download...
2025-10-27 20:00:00 | INFO | Downloading Kokoro model (~311MB) to models/kokoro-v1.0.onnx...
2025-10-27 20:00:15 | INFO | Model downloaded successfully
2025-10-27 20:00:15 | INFO | Downloading Kokoro voices (~25MB) to models/voices-v1.0.bin...
2025-10-27 20:00:17 | INFO | Voices downloaded successfully
2025-10-27 20:00:17 | INFO | Kokoro TTS initialized with voice: am_adam
```

## Manual Download (Optional)

If you prefer to download models manually:

```bash
mkdir -p models
cd models
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
cd ..
```

## Fallback Behavior

If model download fails (network issues, disk space, etc.), the bot will:
1. Log an error message
2. Fall back to **Edge TTS** (cloud-based)
3. Continue operating normally with Edge TTS

```
2025-10-27 20:00:00 | ERROR | Failed to download Kokoro models: [error details]
2025-10-27 20:00:00 | WARNING | Kokoro TTS not available, falling back to Edge TTS
```

## Benefits

- **No manual setup** - Just install `kokoro-onnx` via pip and run
- **Consistent deployment** - Same experience on Windows, Linux, macOS
- **VM friendly** - Works seamlessly on cloud VMs
- **Graceful degradation** - Falls back to Edge TTS if download fails

## Technical Details

### Implementation

Located in [services/kokoro_tts.py](../../services/kokoro_tts.py):

```python
def _download_models(self) -> bool:
    """Download Kokoro model files if missing."""
    try:
        # Create models directory
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        # Download model file if missing
        if not self.model_path.exists():
            logger.info(f"Downloading Kokoro model (~311MB)...")
            urllib.request.urlretrieve(KOKORO_MODEL_URL, self.model_path)
            logger.info("Model downloaded successfully")

        # Download voices file if missing
        if not self.voices_path.exists():
            logger.info(f"Downloading Kokoro voices (~25MB)...")
            urllib.request.urlretrieve(VOICES_BIN_URL, self.voices_path)
            logger.info("Voices downloaded successfully")

        return True
    except Exception as e:
        logger.error(f"Failed to download Kokoro models: {e}")
        return False
```

### Default Paths

- Model: `models/kokoro-v1.0.onnx`
- Voices: `models/voices-v1.0.bin`

Can be customized via `config.py`:
```python
kokoro_tts = KokoroTTSService(
    model_path="custom/path/kokoro.onnx",
    voices_path="custom/path/voices.bin"
)
```

## Troubleshooting

### Download Fails

**Problem:** Network timeout or connection error
```
Failed to download Kokoro models: HTTP Error 403: Forbidden
```

**Solution:**
1. Check internet connection
2. Try manual download with `wget` or browser
3. Place files in `models/` directory
4. Bot will use Edge TTS as fallback in the meantime

### Disk Space

**Problem:** Not enough space for 336MB models
```
Failed to download Kokoro models: OSError: [Errno 28] No space left on device
```

**Solution:**
1. Free up disk space
2. Or use Edge TTS instead:
   ```env
   TTS_ENGINE=edge
   ```

### Permission Denied

**Problem:** Can't write to models directory
```
Failed to download Kokoro models: PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Fix directory permissions
sudo chown -R $USER:$USER models/
chmod 755 models/
```

## Configuration

In `.env`:
```env
# Use Kokoro TTS (will auto-download models)
TTS_ENGINE=kokoro

# Or use Edge TTS (no download needed)
TTS_ENGINE=edge

# Kokoro voice selection (50+ options)
KOKORO_VOICE=af_bella  # Female voice
```

See [VOICE_FEATURES.md](VOICE_FEATURES.md) for full voice list.

---

**Related:**
- [Voice Features](VOICE_FEATURES.md) - Complete voice system overview
- [VM Setup Guide](../setup/VM_SETUP.md) - Linux VM deployment
- [Deploy Guide](../../DEPLOY.md) - Quick deployment steps
