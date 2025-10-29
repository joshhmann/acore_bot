# GPU Resource Usage Guide

## Current Implementation (Enhanced Voice Listener)

### Whisper STT (faster-whisper)

The main GPU consumer in the current implementation is **Whisper STT**. Here's the breakdown:

#### Model Size vs Resources

| Model | VRAM (GPU) | RAM (CPU) | Speed | Quality | Recommendation |
|-------|------------|-----------|-------|---------|----------------|
| **tiny** | ~1 GB | ~400 MB | Very Fast | Basic | Low-end GPU, real-time transcription |
| **base** | ~1 GB | ~500 MB | Fast | Good | **Recommended for most users** |
| **small** | ~2 GB | ~1 GB | Medium | Better | Mid-range GPU, better accuracy |
| **medium** | ~5 GB | ~2.5 GB | Slow | Great | High-end GPU, professional use |
| **large** | ~10 GB | ~5 GB | Very Slow | Best | Enterprise GPU (A100, RTX 4090) |

#### GPU vs CPU Mode

```env
# GPU mode (faster, uses VRAM)
WHISPER_DEVICE=cuda

# CPU mode (slower, uses RAM only)
WHISPER_DEVICE=cpu

# Auto-detect (uses GPU if available)
WHISPER_DEVICE=auto
```

**Performance Comparison:**
- **GPU (CUDA)**: ~0.5-2 seconds for 10s audio (base model)
- **CPU**: ~2-8 seconds for 10s audio (base model)

### Enhanced Voice Listener Components

These are **CPU-only** and use minimal resources:

| Component | GPU Usage | CPU Usage | Memory |
|-----------|-----------|-----------|--------|
| Energy-based VAD | None | ~1-2% | <10 MB |
| Silence detection | None | ~1-2% | <10 MB |
| Response trigger logic | None | <1% | <5 MB |
| Audio buffering | None | ~2-5% | ~50 MB |

**Total Current GPU Usage:**
- **With Whisper on GPU**: VRAM based on model (1-10 GB)
- **With Whisper on CPU**: 0 GB VRAM, but slower transcription

---

## Optional Enhancements

### 1. Advanced VAD (Voice Activity Detection)

#### Silero VAD
- **Type**: Neural network-based VAD
- **Model Size**: 2 MB (tiny!)
- **VRAM**: ~50-100 MB (if GPU enabled)
- **RAM**: ~100 MB (CPU mode)
- **Speed**: Very fast (~0.1ms per frame)
- **Benefit**: Much better speech detection than energy-based VAD

**Resource Impact**: ⭐ MINIMAL
```python
# Can run on CPU with negligible performance impact
# GPU acceleration optional but not necessary
```

#### WebRTC VAD
- **Type**: Traditional algorithm (not neural)
- **GPU Usage**: None (CPU only)
- **RAM**: ~10 MB
- **Speed**: Extremely fast
- **Benefit**: Fast, but less accurate than Silero

**Resource Impact**: ⭐ NEGLIGIBLE

**Recommendation**: Use **Silero VAD on CPU** - best balance of accuracy and resources.

---

### 2. Speaker Diarization (pyannote.audio)

This is the **biggest GPU consumer** among enhancements.

#### pyannote.audio Resource Requirements

| Configuration | VRAM | RAM | Speed (10s audio) | Quality |
|---------------|------|-----|-------------------|---------|
| **CPU only** | 0 GB | ~2 GB | ~20-40s | Good |
| **GPU (small)** | ~2 GB | ~1 GB | ~2-5s | Good |
| **GPU (standard)** | ~4 GB | ~1.5 GB | ~1-3s | Excellent |

**Real-Time Feasibility:**
- **CPU**: ❌ Too slow for real-time (20-40s processing for 10s audio)
- **GPU (6GB+)**: ✅ Near real-time (1-3s processing for 10s audio)

**Resource Impact**: ⚠️ SIGNIFICANT (requires good GPU for real-time use)

---

### 3. Full Chat Integration

- **Type**: Logic only (uses existing Ollama)
- **GPU Usage**: Depends on Ollama model
- **Resource Impact**: ⭐ MINIMAL (just routing to existing services)

---

## Total Resource Requirements by Configuration

### Configuration 1: Current (Basic)
```env
WHISPER_ENABLED=true
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=auto
```
**Resources:**
- VRAM: ~1 GB (GPU) or 0 GB (CPU)
- RAM: ~500 MB (GPU) or ~1 GB (CPU)
- GPU: Optional but recommended
- **Best for**: Most users, real-time transcription

---

### Configuration 2: Enhanced VAD (Silero)
```env
WHISPER_ENABLED=true
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=auto
# + Silero VAD on CPU
```
**Resources:**
- VRAM: ~1 GB (GPU) or 0 GB (CPU)
- RAM: ~600 MB (GPU) or ~1.1 GB (CPU)
- GPU: Optional but recommended
- **Best for**: Better speech detection with minimal overhead

---

### Configuration 3: Full Multi-Speaker (Diarization)
```env
WHISPER_ENABLED=true
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cuda
# + Silero VAD
# + pyannote.audio (GPU)
```
**Resources:**
- VRAM: ~5-6 GB total
  - Whisper base: ~1 GB
  - pyannote: ~4 GB
  - Silero: ~0.1 GB
- RAM: ~2 GB
- GPU: **REQUIRED** (min 6GB VRAM)
- **Best for**: Professional multi-speaker identification

---

## Hardware Recommendations

### Budget Setup (CPU Only)
```
CPU: Modern 4+ core
RAM: 8 GB
GPU: None
Config: Whisper base on CPU
Performance: 2-8s transcription for 10s audio
Cost: $0 additional
```

### Recommended Setup (Entry GPU)
```
CPU: Modern 4+ core
RAM: 8 GB
GPU: GTX 1660 / RTX 3050 (6GB VRAM)
Config: Whisper base on GPU + Silero VAD
Performance: 0.5-2s transcription for 10s audio
Cost: ~$200-300 for GPU
```

### Professional Setup (Multi-Speaker)
```
CPU: Modern 6+ core
RAM: 16 GB
GPU: RTX 3060 / RTX 4060 (12GB VRAM)
Config: Whisper small + pyannote + Silero
Performance: Real-time multi-speaker diarization
Cost: ~$400-600 for GPU
```

### Enterprise Setup (Best Quality)
```
CPU: Modern 8+ core
RAM: 32 GB
GPU: RTX 4090 / A100 (24GB+ VRAM)
Config: Whisper large + pyannote + Silero
Performance: Real-time, best quality
Cost: ~$1500-3000 for GPU
```

---

## Optimization Tips

### 1. Run Whisper on CPU if No GPU
```env
WHISPER_DEVICE=cpu
WHISPER_MODEL_SIZE=tiny  # Use tiny for faster CPU transcription
```

### 2. Use Smaller Whisper Model
```env
# For real-time on low-end GPU
WHISPER_MODEL_SIZE=tiny

# For good quality on mid-range GPU
WHISPER_MODEL_SIZE=base
```

### 3. Increase Silence Threshold
```env
# Wait longer before transcribing = fewer transcriptions = less GPU usage
WHISPER_SILENCE_THRESHOLD=3.0  # Default is 2.0
```

### 4. Model Caching
faster-whisper automatically caches models in `~/.cache/huggingface/`
- First load: Downloads model (~100 MB - 3 GB)
- Subsequent loads: Instant from cache

### 5. Batch Processing (Future Enhancement)
Instead of transcribing each utterance, batch multiple utterances:
- Pros: More efficient GPU usage
- Cons: Higher latency

---

## Comparison: This Bot vs Other Voice Bots

| Feature | This Bot | Discord Bots (Typical) | Zoom/Teams AI |
|---------|----------|----------------------|---------------|
| **STT Model** | Whisper (local) | Cloud API | Cloud API |
| **GPU Required** | Optional | No (cloud) | No (cloud) |
| **Privacy** | ✅ Local | ❌ Cloud | ❌ Cloud |
| **Cost** | Free | $$$$ API fees | $$$$$ |
| **Latency** | Low (local) | Medium (network) | Medium (network) |
| **Offline** | ✅ Yes | ❌ No | ❌ No |

---

## Current Implementation: What's Running Now?

Based on your current setup, the enhanced voice listener uses:

1. **Whisper STT (faster-whisper)**
   - GPU: ~1 GB VRAM (if CUDA enabled) or 0 GB (CPU mode)
   - Model: Configurable (default: base)

2. **Energy-based VAD** (Simple algorithm)
   - GPU: 0 GB
   - CPU: <2%

3. **Smart Response Logic** (Python code)
   - GPU: 0 GB
   - CPU: <1%

**Total Current Usage:**
- **VRAM**: ~1 GB (GPU mode) or 0 GB (CPU mode)
- **RAM**: ~500 MB (GPU) or ~1 GB (CPU)
- **CPU**: 5-10% during transcription
- **Disk**: ~200 MB for base model

---

## Should You Use GPU or CPU?

### Use GPU if:
- ✅ You have 4GB+ VRAM available
- ✅ You want real-time transcription (<1s delay)
- ✅ You have multiple users talking frequently
- ✅ You want to use medium/large models for better accuracy

### Use CPU if:
- ✅ No GPU available
- ✅ Infrequent voice usage (occasional transcriptions)
- ✅ 2-5s delay is acceptable
- ✅ Budget/energy conscious

### Pro Tip:
```env
# Let the bot decide based on hardware
WHISPER_DEVICE=auto
```
This auto-detects GPU and falls back to CPU if unavailable.

---

## Monitoring GPU Usage

### Check VRAM Usage (NVIDIA)
```bash
# Real-time monitoring
nvidia-smi -l 1

# Check bot's usage
nvidia-smi
```

### Check RAM Usage
```bash
# Linux
htop

# Docker
docker stats
```

### In Discord
Use `/stt_status` command to see current model and device being used.

---

## Summary

| Configuration | VRAM | RAM | Speed | Best For |
|---------------|------|-----|-------|----------|
| **Current (CPU)** | 0 GB | 1 GB | Medium | Budget, infrequent use |
| **Current (GPU base)** | 1 GB | 500 MB | Fast | **Recommended** |
| **+ Silero VAD** | +0.1 GB | +100 MB | Fast+ | Better speech detection |
| **+ Diarization** | +4 GB | +1 GB | Fast | Multi-speaker identification |

**Bottom Line:**
- **Current implementation**: Very light (1GB VRAM or CPU-only)
- **Recommended**: Use GPU with base model (~1GB VRAM)
- **Advanced features**: Speaker diarization needs 6GB+ VRAM
- **Budget option**: CPU-only works fine with 2-5s latency
