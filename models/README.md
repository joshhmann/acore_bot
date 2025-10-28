# Model Files

This directory contains large model files for TTS and RVC.

## Required Models

These models are required for the bot to function and will be auto-downloaded on first use:

### Kokoro TTS
- `kokoro-v1.0.onnx` - Kokoro TTS model (~311MB)
- `voices-v1.0.bin` - Voice embeddings (~25MB)

### RVC (Voice Conversion)
- `hubert_base.pt` - Hubert voice encoder (~181MB)
- `rmvpe.pt` - RMVPE pitch extraction (~173MB)

## Download Instructions

If models are not present, they will be automatically downloaded when the bot starts.

Alternatively, download manually from:
- **Kokoro TTS**: [https://github.com/nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts)
- **Hubert/RMVPE**: Required by RVC-WebUI, download from RVC-WebUI repository

## Custom Voice Models

Place custom RVC voice models in the RVC-WebUI installation:
```
C:\Users\<USER>\Documents\Github\Retrieval-based-Voice-Conversion-WebUI\assets\weights\
```

## .gitignore

These large model files are excluded from git via `.gitignore`:
```
*.pt
*.pth
*.onnx
*.bin
*.index
```
