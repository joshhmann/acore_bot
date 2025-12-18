# Voice & TTS System Guide

**Complete guide to audio engines, RVC voice conversion, and voice management in acore_bot**

---

## Table of Contents

1. [Overview](#overview)
2. [TTS Engines](#tts-engines)
3. [Voice Configuration](#voice-configuration)
4. [RVC Voice Conversion](#rvc-voice-conversion)
5. [Speech-to-Text (STT)](#speech-to-text-stt)
6. [Voice Commands](#voice-commands)
7. [Audio Management](#audio-management)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Voice & TTS System provides comprehensive audio capabilities including text-to-speech, voice conversion, speech recognition, and smart voice activity detection. The system supports multiple TTS engines, voice conversion models, and real-time voice interactions.

### Key Features

- **Multiple TTS Engines**: Kokoro (local/API), Edge TTS, Supertonic
- **RVC Voice Conversion**: Transform any voice into character voices
- **Speech-to-Text**: Whisper and Parakeet STT with voice activity detection
- **Smart Listening**: Automatic transcription and response triggers
- **Voice Commands**: Voice-activated bot control
- **Sentiment-Based Voice Modulation**: Dynamic voice pitch and speed based on emotion

### Audio Pipeline

```
Text Input
    ↓
TTS Engine (Kokoro/Edge/Supertonic)
    ↓
Audio Generation (.wav)
    ↓
RVC Conversion (Optional)
    ↓
Voice Channel Output
```

---

## TTS Engines

The bot supports three TTS engines with automatic fallback capabilities.

### 1. Kokoro TTS (Recommended)

**Local High-Quality Neural TTS**

#### Features
- **Multi-Voice Support**: 11+ built-in voices
- **Local Processing**: No internet required after model download
- **Fast Generation**: ~2-3 seconds for typical response
- **High Quality**: Natural, emotive speech synthesis

#### Installation

```bash
# Models auto-download on first use (~336MB)
# No manual installation required
```

#### Available Voices

| Voice ID | Gender | Accent | Best For |
|----------|--------|---------|-----------|
| `am_adam` | Male | American US | Narration, general purpose |
| `am_michael` | Male | American US | Professional, calm |
| `af_sarah` | Female | American US | Friendly, conversational |
| `af_bella` | Female | American US | Warm, caring |
| `af_nicolas` | Male | French | European accent |
| `af_skyler` | Female | American US | Youthful, energetic |
| `bm_lewis` | Male | British UK | Authoritative, formal |
| `bf_emma` | Female | British UK | Elegant, sophisticated |
| `bm_daniel` | Male | British UK | Gentle, storytelling |
| `af_sophie` | Female | French | Romantic, soft |

#### Configuration

```env
# Enable Kokoro TTS
TTS_ENGINE=kokoro

# Default voice settings
KOKORO_VOICE=am_adam
KOKORO_SPEED=1.0
KOKORO_PITCH=0
```

### 2. Kokoro API

**Remote TTS Service for Production**

#### Benefits
- **Lower CPU Usage**: Offloads TTS processing
- **Faster Response**: Optimized for production workloads
- **Scalability**: Handle multiple concurrent requests
- **Easy Setup**: No local model management

#### Setup

```env
# Enable Kokoro API
TTS_ENGINE=kokoro_api

# API Configuration  
KOKORO_API_URL=http://localhost:8880
KOKORO_API_KEY=your_api_key_here  # Optional
```

#### API Server Setup

```bash
# Clone Kokoro API server
git clone https://github.com/some-repo/kokoro-api
cd kokoro-api

# Install dependencies
pip install -r requirements.txt

# Start server
python app.py --host 0.0.0.0 --port 8880
```

### 3. Microsoft Edge TTS

**Cloud-Based Fallback**

#### Features
- **No Setup Required**: Works out of the box
- **Multiple Languages**: Extensive language support
- **Natural Quality**: Microsoft's production TTS
- **Reliable**: Microsoft's cloud infrastructure

#### Voice Options

```env
# Edge TTS Voices
EDGE_VOICE=en-US-AriaNeural     # Female, natural
EDGE_VOICE=en-US-GuyNeural       # Male, friendly
EDGE_VOICE=en-US-JennyNeural     # Female, warm
EDGE_VOICE=en-GB-SoniaNeural     # Female, British
EDGE_VOICE=en-GB-RyanNeural      # Male, British
```

#### Configuration

```env
# Enable Edge TTS
TTS_ENGINE=edge

# Voice Settings
EDGE_VOICE=en-US-AriaNeural
EDGE_RATE=+0%      # Speed adjustment (-50% to +100%)
EDGE_VOLUME=+0%     # Volume adjustment (-50% to +100%)
EDGE_PITCH=+0Hz     # Pitch adjustment (-50Hz to +50Hz)
```

### 4. Supertonic TTS

**High-Quality Local TTS**

#### Features
- **Premium Quality**: Advanced neural synthesis
- **Customizable**: Multiple denoising steps
- **Local Processing**: Privacy-focused
- **Large Model**: ~2GB model size

#### Configuration

```env
# Enable Supertonic
TTS_ENGINE=supertonic

# Generation Settings
SUPERTONIC_DENOISE_STEPS=5     # 1-10 steps
SUPERTONIC_VOICE=default         # Voice model
```

---

## Voice Configuration

### Per-Character Voice Settings

Each character can have custom voice configurations:

```json
"legacy_config": {
  "voice": {
    "kokoro_voice": "am_adam",
    "kokoro_speed": 1.0,
    "kokoro_pitch": 0,
    "edge_voice": "en-US-AriaNeural",
    "edge_rate": "+10%",
    "edge_volume": "+5%",
    "supertonic_voice": "default"
  },
  "rvc": {
    "enabled": true,
    "model": "dagoth_ur.pth",
    "pitch_shift": 0,
    "index_rate": 0.5,
    "protect": 0.33
  }
}
```

### Dynamic Voice Selection

The bot automatically selects voice based on:

1. **Character Legacy Config** (highest priority)
2. **Global Settings** (fallback)
3. **Engine Defaults** (last resort)

### Sentiment-Based Voice Modulation

Voice parameters adjust based on message sentiment:

```python
# Sentiment analysis affects voice
if sentiment > 0.5:        # Positive/happy
    kokoro_speed = 1.1       # Slightly faster
    edge_rate = "+10%"        # Slightly faster
elif sentiment < -0.3:      # Negative/sad
    kokoro_speed = 0.9       # Slightly slower
    edge_rate = "-10%"        # Slightly slower
```

### Voice Management Commands

#### `/voices` - List Voice Information

```bash
/voices
# Output:
# 🎤 Current TTS Engine: kokoro
# 🔊 Current Voice: am_adam
# 📝 Available Kokoro Voices:
#   am_adam (Male, US), af_bella (Female, US), bm_lewis (Male, UK)...
# 🔧 Available RVC Models:
#   dagoth_ur.pth, gothmommy.pth, scav.pth
```

#### `/set_voice <voice>` - Change Voice

```bash
/set_voice af_bella
# Output: ✅ Voice changed to af_bella (Female, US)
```

#### `/list_kokoro_voices` - Detailed Voice List

```bash
/list_kokoro_voices
# Output:
# 👨 Male Voices:
#   • am_adam (American US) - Professional, clear
#   • am_michael (American US) - Warm, friendly
#   • af_nicolas (French) - European accent
# 👩 Female Voices:
#   • af_bella (American US) - Warm, caring
#   • af_sarah (American US) - Friendly, conversational
#   • af_skyler (American US) - Youthful, energetic
# 🎩 British Voices:
#   • bm_lewis (British UK) - Authoritative, formal
#   • bf_emma (British UK) - Elegant, sophisticated
```

---

## RVC Voice Conversion

**Retrieval-based Voice Conversion** transforms any TTS output into character-specific voices.

### Architecture

```
TTS Output (Any Voice)
        ↓
RVC Model Processing
        ↓
Character Voice Output
```

### Setup Options

#### Option 1: Local RVC (In-Process)

```bash
# Install RVC dependencies
pip install faircrest torch torchvision

# Download RVC models
wget https://example.com/dagoth_ur.pth -O data/voice_models/
```

#### Option 2: RVC WebUI (Recommended)

##### WebUI Setup

```bash
# Clone RVC WebUI
git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
cd Retrieval-based-Voice-Conversion-WebUI

# Install dependencies
pip install -r requirements.txt

# Start WebUI
python infer-web.py --colab --api
```

##### Bot Configuration

```env
# Enable RVC
RVC_ENABLED=true
RVC_MODE=webui
RVC_WEBUI_URL=http://localhost:7865
RVC_DEFAULT_MODEL=dagoth_ur.pth
```

### RVC Model Management

#### Model Locations

```
data/voice_models/
├── dagoth_ur.pth        # Dagoth Ur voice model
├── gothmommy.pth        # Gothic mother voice
├── scav.pth            # Scavenger voice
└── custom_character.pth # Your custom model
```

#### Model Requirements

- **Format**: PyTorch (.pth) files
- **Training Data**: 10-30 minutes of target voice
- **Quality**: Clear audio, minimal background noise
- **Sample Rate**: 22050Hz or 44100Hz

#### Adding Custom Models

1. Train or download RVC model (.pth file)
2. Place in `data/voice_models/`
3. Update character config:
```json
"legacy_config": {
  "rvc": {
    "enabled": true,
    "model": "your_model.pth",
    "pitch_shift": 0,
    "index_rate": 0.5,
    "protect": 0.33
  }
}
```

### RVC Parameters

| Parameter | Range | Default | Description |
|-----------|--------|---------|-------------|
| `pitch_shift` | -12 to +12 | 0 | Voice pitch adjustment |
| `index_rate` | 0.0 to 1.0 | 0.5 | Voice similarity (higher = more similar) |
| `protect` | 0.0 to 0.5 | 0.33 | Breath sound protection |

#### Example Configurations

```json
// Deep voice (lower pitch)
"rvc": {
  "pitch_shift": -4,
  "index_rate": 0.7,
  "protect": 0.33
}

// High-pitched voice
"rvc": {
  "pitch_shift": +6,
  "index_rate": 0.8,
  "protect": 0.25
}

// Soft, gentle voice
"rvc": {
  "pitch_shift": 0,
  "index_rate": 0.3,
  "protect": 0.4
}
```

---

## Speech-to-Text (STT)

The bot supports multiple STT engines for voice recognition and transcription.

### 1. Whisper STT (Local)

#### Features
- **Offline Processing**: No internet required
- **Multiple Models**: tiny, base, small, medium, large
- **Language Detection**: Auto-detect or specify language
- **High Accuracy**: State-of-the-art speech recognition

#### Configuration

```env
# Enable Whisper
WHISPER_ENABLED=true

# Model Selection (tradeoff: speed vs accuracy)
WHISPER_MODEL=base           # Options: tiny, base, small, medium, large
WHISPER_DEVICE=cpu           # Options: cpu, cuda (GPU)
WHISPER_LANGUAGE=en          # Auto-detect if empty
WHISPER_SILENCE_THRESHOLD=2.0  # Seconds of silence before processing
```

#### Model Performance

| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|-----------|
| `tiny` | 39MB | Fastest | Good | Quick commands, short phrases |
| `base` | 74MB | Fast | Better | General use, balanced |
| `small` | 244MB | Medium | Good | Longer speech |
| `medium` | 769MB | Slow | Better | High accuracy needs |
| `large` | 1550MB | Slowest | Best | Critical applications |

### 2. Parakeet STT (Cloud)

#### Features
- **Cloud Processing**: Fast, reliable
- **High Accuracy**: Production-grade recognition
- **Real-time**: Stream processing support
- **Multiple Languages**: Extensive language support

#### Setup

```env
# Enable Parakeet
PARAKEET_ENABLED=true

# API Configuration
PARAKEET_API_URL=https://api.parakeet.stt
PARAKEET_API_KEY=your_api_key
PARAKEET_MODEL=whisper-v3  # Model selection
```

### Enhanced Voice Listener

**Smart voice activity detection with automatic transcription**

#### Features
- **Silence Detection**: Automatically detects when user stops speaking
- **Smart Triggers**: Recognizes questions, commands, and bot mentions
- **Music Command Support**: "Play X", "Skip", "Stop" commands
- **Continuous Listening**: Real-time audio buffering
- **Multi-language**: Supports multiple languages simultaneously

#### Usage

```bash
# Start smart listening
/listen

# Bot will:
# 1. Join voice channel
# 2. Start monitoring audio
# 3. Detect silence (2 seconds)
# 4. Transcribe speech
# 5. Respond to commands/questions

# Stop listening
/stop_listening
```

#### Listening Behavior

```python
# Voice flow detection
if "play" in transcription.lower():
    # Execute music command
elif bot_name in transcription:
    # Generate AI response
elif "?" in transcription:
    # Answer question
elif "stop" in transcription:
    # Stop listening
```

---

## Voice Commands

### Basic Voice Commands

#### `/join` - Join Voice Channel

```bash
/join
# Bot joins your current voice channel
# Automatically starts voice client
# Ready for TTS output and listening
```

#### `/leave` - Leave Voice Channel

```bash
/leave
# Bot disconnects from voice channel
# Cleans up audio resources
# Stops any ongoing playback
```

#### `/tts <text>` - Text-to-Speech

```bash
/tts Hello world! This is a test.
# Bot generates TTS and plays in voice channel
# Uses current character's voice settings
# Applies RVC if enabled
```

#### `/listen` - Start Smart Listening

```bash
/listen
# Bot starts voice activity detection
# Transcribes speech after silence
# Responds to questions and commands
# Shows transcription in chat
```

#### `/stop_listening` - Stop Listening

```bash
/stop_listening
# Bot stops voice monitoring
# Shows session duration
# Transcribes any remaining audio
```

### Advanced Voice Commands

#### `/stt_status` - STT System Status

```bash
/stt_status
# Output:
# 🔊 STT System Status
# ✅ Whisper STT: Enabled
# 📝 Model: base (74MB)
# 💻 Device: CPU
# 🌍 Language: Auto-detect
# 🤫 Silence Threshold: 2.0 seconds
# 🎧 Active Sessions: 1
```

#### Voice Activity Detection Settings

```env
# Voice Detection Configuration
VOICE_ACTIVITY_THRESHOLD=0.01    # Audio level threshold
VOICE_SILENCE_DURATION=2.0     # Seconds of silence
VOICE_MIN_SPEECH_DURATION=0.5   # Minimum speech length
VOICE_MAX_RECORDING_DURATION=30  # Max recording time
```

### Voice Command Processing

```python
# Command detection in voice transcription
async def process_voice_command(transcription, user, channel):
    text = transcription.lower()
    
    # Music commands
    if text.startswith("play "):
        song_name = text[5:].strip()
        await play_song(song_name, channel)
    elif text == "skip":
        await skip_song(channel)
    elif text == "stop":
        await stop_music(channel)
    
    # Bot interaction
    elif bot_name in text:
        await handle_chat_interaction(text, user, channel)
    
    # Questions
    elif text.endswith("?"):
        await answer_question(text, user, channel)
```

---

## Audio Management

### File Management

#### Temporary Files

```bash
# TTS and RVC create temporary files
/tmp/tts_*.wav          # TTS output
/tmp/rvc_*.wav          # RVC converted audio
/tmp/whisper_*.wav      # STT recordings

# Automatic cleanup after 24 hours
# Configurable via TEMP_RETENTION_HOURS
```

#### Audio Format Configuration

```env
# Audio Processing Settings
AUDIO_SAMPLE_RATE=44100     # Output sample rate
AUDIO_CHANNELS=2            # Stereo output
AUDIO_BITRATE=128k         # Audio bitrate
AUDIO_FORMAT=wav          # Output format (wav/mp3)
```

### Performance Optimization

#### GPU Acceleration

```env
# CUDA GPU Support
WHISPER_DEVICE=cuda        # Use GPU for Whisper
RVC_DEVICE=cuda            # Use GPU for RVC (if supported)
TORCH_CUDA_ARCH_LIST=8.6    # CUDA architecture (check with nvidia-smi)
```

#### Concurrent Processing

```env
# Concurrent Limits
MAX_CONCURRENT_TTS=3         # Max TTS generations
MAX_CONCURRENT_RVC=2         # Max RVC conversions
MAX_VOICE_SESSIONS=5          # Max voice channels
```

### Audio Quality Settings

#### TTS Quality vs Speed Tradeoffs

```env
# Kokoro Settings
KOKORO_VOICE_SPEED=1.0       # 0.5-2.0 (faster-slower)
KOKORO_DENOISE_STRENGTH=0.7  # 0.0-1.0 (noise reduction)

# RVC Settings  
RVC_DENOISE_STRENGTH=0.7     # 0.0-1.0
RVC_ROOM_NOISE=0.2           # 0.0-1.0
RVC_VOICE_LIMIT=1.0          # 0.0-1.0 (voice similarity)
```

---

## Troubleshooting

### Common Issues

#### TTS Not Working

**Symptoms:**
- No audio output
- Error messages about TTS generation
- Voice joins but doesn't speak

**Solutions:**

1. **Check TTS Engine:**
```bash
/voices
# Verify current TTS engine and voice
```

2. **Verify Dependencies:**
```bash
# Check FFmpeg installation
ffmpeg -version

# Install if missing:
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg  
# Windows: Download from ffmpeg.org
```

3. **Check Model Downloads:**
```bash
# Kokoro models auto-download to data/models/
# Verify files exist:
ls -la data/models/kokoro/
```

4. **Test with Simple Text:**
```bash
/tts hello
# If this works, issue is with longer text
```

#### RVC Not Working

**Symptoms:**
- TTS works but voice conversion doesn't
- Wrong voice output
- RVC errors in logs

**Solutions:**

1. **Check RVC Configuration:**
```env
RVC_ENABLED=true
RVC_MODE=webui
RVC_WEBUI_URL=http://localhost:7865
```

2. **Verify WebUI Connection:**
```bash
curl http://localhost:7865/info
# Should return RVC WebUI status
```

3. **Check Model Files:**
```bash
ls -la data/voice_models/
# Verify .pth model files exist
```

4. **Test RVC Directly:**
```bash
# Test RVC WebUI with sample audio
# Upload test.wav to WebUI interface
# Try conversion with selected model
```

#### STT/Listening Not Working

**Symptoms:**
- `/listen` command doesn't respond
- No transcriptions appearing
- Voice detection not triggering

**Solutions:**

1. **Check STT Configuration:**
```bash
/stt_status
# Verify Whisper model and device
```

2. **Check Permissions:**
```bash
# Bot needs voice channel permissions:
# - Connect
# - Speak  
# - Use Voice Activity
```

3. **Test Audio Input:**
```bash
# Check system microphone works
# Test with system voice recorder
```

4. **Adjust Sensitivity:**
```env
VOICE_ACTIVITY_THRESHOLD=0.05   # Lower if not detecting
VOICE_SILENCE_DURATION=1.5     # Shorter if too slow
```

#### Audio Quality Issues

**Symptoms:**
- Choppy or distorted audio
- Background noise
- Low volume

**Solutions:**

1. **Adjust Audio Settings:**
```env
AUDIO_SAMPLE_RATE=22050      # Try lower sample rate
AUDIO_BITRATE=64k           # Reduce bitrate
AUDIO_CHANNELS=1            # Try mono instead of stereo
```

2. **FFmpeg Optimization:**
```bash
# Add FFmpeg options for better quality
FFMPEG_OPTIONS="-vn -af aresample=22050,aformat=sample_fmts=s16:channel_layouts=mono"
```

3. **RVC Parameter Tuning:**
```json
"rvc": {
  "index_rate": 0.3,        # Reduce if robotic
  "protect": 0.4,           # Increase if breathy
  "pitch_shift": 0           # Adjust if pitch wrong
}
```

### Debug Commands

```bash
# System audio check
!test_audio
# Tests TTS generation and playback

# Voice session info
!voice_sessions
# Shows active voice connections

# Audio device info  
!audio_devices
# Lists available input/output devices

# Model status
!model_status
# Shows loaded TTS/STT models
```

### Performance Monitoring

```bash
# Audio metrics
/metrics
# Look for:
# - TTS generation time
# - RVC conversion time  
# - STT processing time
# - Audio buffer underruns

# Voice analytics
!voice_analytics
# Shows:
# - Most used voices
# - Average response times
# - Error rates
```

### Getting Help

1. **Check Logs**: `logs/bot.log` for voice-related errors
2. **Verify Configuration**: Use `/botstatus` to check system status
3. **Test Components**: Test TTS, RVC, and STT separately
4. **Community Support**: GitHub Issues with voice configuration details

---

## Best Practices

### Voice Configuration

1. **Match Voice to Character**: Select voices that fit character personality
2. **Consistent Settings**: Use similar voice parameters across similar characters  
3. **Test Thoroughly**: Test voice settings in various contexts
4. **Monitor Performance**: Track voice generation times and quality

### Performance Optimization

1. **Use Kokoro API**: For production deployments with high load
2. **GPU Acceleration**: Enable CUDA for Whisper and RVC when available
3. **Concurrent Limits**: Set reasonable limits for concurrent processing
4. **Cache Models**: Keep models in memory for faster generation

### Audio Quality

1. **High-Quality Source**: Use clean, high-quality RVC models
2. **Proper Settings**: Tune RVC parameters for each voice model
3. **Noise Reduction**: Use appropriate denoising settings
4. **Format Optimization**: Use appropriate sample rates and bitrates

---

**Ready to set up voice?** Follow the [TTS Engine Setup](#tts-engines) section and bring your characters to life with natural speech!