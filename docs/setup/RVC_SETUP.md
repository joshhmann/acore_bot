# RVC (Voice Conversion) Setup Guide

## Current Status

RVC integration is currently **challenging** with Python 3.13 due to dependency conflicts:

- `rvc-inferpy`: Requires `faiss-cpu` 1.7.3, which isn't available for Python 3.13
- `rvc-python`: Has build dependency issues with Python 3.13
- Most RVC libraries target Python 3.9-3.12

## Options for RVC Integration

### Option 1: Use Python 3.12 Environment (Recommended)

Create a separate Python 3.12 environment for RVC:

```bash
# Install pyenv or use conda
conda create -n rvc python=3.12
conda activate rvc
pip install rvc-inferpy
```

Then call RVC as a subprocess from your main bot.

### Option 2: Use RVC WebUI API

The official [RVC-WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) provides a web interface and API:

1. Clone and run RVC-WebUI separately
2. Make HTTP requests to the API endpoint
3. No Python version conflicts

### Option 3: Use Alternative Voice Changers

- **so-vits-svc**: Similar quality, better Python 3.13 support
- **Bark AI**: Text-to-speech with voice cloning
- **Tortoise TTS**: High-quality voice cloning

## What You Need for RVC

1. **Voice Models**: `.pth` files trained on target voices
   - Can find pre-trained models on HuggingFace
   - Or train your own with RVC-WebUI

2. **Index Files**: `.index` files for feature retrieval
   - Generated during training
   - Improves voice quality

3. **Model Storage**: Place in `./data/voice_models/`

## For Arby n the Chief

Since you want Arby and Chief voices, you'd need to:

1. Find/create voice models for these characters
2. Train RVC models on voice samples
3. Use TTS (Edge/Kokoro) → RVC pipeline

**Alternative**: Just use Kokoro TTS voices directly! The quality is already quite good, and you can:
- Use `am_onyx` or `am_adam` for Chief (deep, aggressive)
- Use `bm_george` or `bm_lewis` for Arby (British, sophisticated)

## Current Implementation

The bot has RVC placeholder code in [services/rvc.py](services/rvc.py:1) that passes audio through unchanged. This allows the bot to work without RVC while keeping the architecture ready for future integration.

To enable RVC when available:
1. Add `.pth` model files to `./data/voice_models/`
2. Implement the actual inference in `rvc.py`
3. Set `RVC_ENABLED=true` in `.env`
