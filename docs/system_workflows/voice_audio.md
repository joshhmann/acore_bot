# Voice and Audio System Workflow

This document describes the complete voice and audio processing system in acore_bot, including speech-to-text (STT), text-to-speech (TTS), RVC voice cloning, and audio management workflows.

## Overview

The voice and audio system enables natural voice interactions with the bot through **speech recognition**, **voice synthesis**, and **voice cloning** capabilities. It supports multiple TTS engines, real-time voice activity detection, and persona-specific voice customization.

## Architecture

### Component Structure
```
cogs/voice/
├── main.py                 # Core VoiceCog and TTS/RVC coordination
├── commands.py            # Voice command implementations
├── manager.py             # Voice client management
└── __init__.py            # Voice cog initialization

services/voice/
├── tts.py                 # TTS service abstraction layer
├── rvc.py                 # RVC voice cloning service
├── listener.py            # Voice activity detection
├── streaming_tts.py       # Streaming TTS for real-time responses
├── commands.py            # Voice command parsing and execution
└── __init__.py            # Voice service initialization

services/clients/
├── tts_client.py          # Kokoro TTS API client
├── stt_client.py          # Speech-to-text client
└── rvc_client.py          # RVC processing client
```

### Service Dependencies
```
Voice System Dependencies:
├── Discord Voice Client   # Voice channel connections
├── TTS Engines           # Kokoro, Supertonic, API clients
├── RVC Service           # Voice cloning and conversion
├── STT Engines           # Whisper, Parakeet
├── Voice Activity Detection  # Automatic speech detection
├── Audio Processing      # FFmpeg integration
└── Sound Effects         # Environmental audio
```

## Voice Processing Flow

### 1. Voice Activity Detection
**File**: `services/voice/listener.py:45-178`

#### 1.1 Initialization
```python
class EnhancedVoiceListener:
    def __init__(self, bot, stt_client=None):
        self.bot = bot
        self.stt_client = stt_client  # Whisper or Parakeet
        self.energy_threshold = Config.VOICE_ENERGY_THRESHOLD  # Default: 500
        self.silence_threshold = Config.WHISPER_SILENCE_THRESHOLD  # Default: 1.0
        self.max_duration = Config.MAX_RECORDING_DURATION  # Default: 30s
        
        # VAD (Voice Activity Detection) settings
        self.trigger_words = Config.VOICE_BOT_TRIGGER_WORDS.split(",")  # "bot,assistant,hey"
        self.is_listening = False
        self.recording_task = None
```

#### 1.2 Voice Detection Pipeline
```python
async def start_listening(self, voice_client):
    """Start continuous voice activity detection."""
    self.is_listening = True
    self.recording_task = asyncio.create_task(self._listen_loop(voice_client))
    
async def _listen_loop(self, voice_client):
    """Main voice detection loop."""
    while self.is_listening:
        try:
            # 1. Receive audio frame
            audio_data = await voice_client.receive()
            
            # 2. Energy detection (VAD)
            if self._detect_voice_activity(audio_data):
                # 3. Start recording
                recording = await self._start_recording(voice_client)
                
                # 4. Process when silence detected
                transcription = await self._process_recording(recording)
                
                # 5. Trigger bot response if valid
                if transcription and self._should_respond(transcription):
                    await self._handle_voice_command(transcription, voice_client)
                    
        except Exception as e:
            logger.error(f"Voice listener error: {e}")
            await asyncio.sleep(1)  # Prevent tight error loops
```

#### 1.3 Speech-to-Text Processing
```python
async def _process_recording(self, audio_file: Path) -> Optional[str]:
    """Convert audio to text using configured STT engine."""
    try:
        if self.stt_client:
            # Use external STT client (Parakeet API or Whisper service)
            transcription = await self.stt_client.transcribe(audio_file)
        else:
            # Use local Whisper (if enabled)
            if Config.WHISPER_ENABLED:
                import whisper
                model = whisper.load_model(Config.WHISPER_MODEL_SIZE)
                result = model.transcribe(str(audio_file))
                transcription = result["text"].strip()
            else:
                transcription = None
        
        return transcription
        
    except Exception as e:
        logger.error(f"STT processing failed: {e}")
        return None
```

### 2. Text-to-Speech Generation
**File**: `services/voice/tts.py:33-156`

#### 2.1 TTS Service Initialization
```python
class TTSService(TTSInterface):
    def __init__(self, engine="kokoro_api", **kwargs):
        self.engine = engine.lower()
        
        # Initialize based on engine type
        if self.engine == "kokoro_api":
            self.kokoro_api = KokoroAPIClient(
                api_url=kwargs.get('kokoro_api_url', 'http://localhost:8880'),
                default_voice=kwargs.get('kokoro_voice', 'am_adam'),
                speed=kwargs.get('kokoro_speed', 1.0)
            )
        elif self.engine == "kokoro":
            self.kokoro = KokoroTTSService(
                default_voice=kwargs.get('kokoro_voice', 'am_adam'),
                speed=kwargs.get('kokoro_speed', 1.0)
            )
        elif self.engine == "supertonic":
            self.supertonic = SupertonicTTSService(
                voice=kwargs.get('supertonic_voice', 'M1'),
                steps=kwargs.get('supertonic_steps', 5),
                speed=kwargs.get('supertonic_speed', 1.05)
            )
```

#### 2.2 TTS Generation Pipeline
```python
async def generate_speech(
    self, 
    text: str, 
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    output_file: Optional[Path] = None
) -> Path:
    """Generate speech from text using configured TTS engine."""
    
    # 1. Clean text for TTS
    clean_text = clean_text_for_tts(text)
    
    # 2. Determine output path
    if not output_file:
        output_file = Config.TEMP_DIR / f"tts_{uuid.uuid4().hex}.wav"
    
    # 3. Generate based on engine
    if self.engine == "kokoro_api":
        audio_data = await self.kokoro_api.synthesize(
            text=clean_text,
            voice=voice or self.kokoro_voice,
            speed=speed or self.kokoro_speed
        )
        with open(output_file, 'wb') as f:
            f.write(audio_data)
            
    elif self.engine == "kokoro":
        audio_data = await self.kokoro.synthesize(
            text=clean_text,
            voice=voice or self.kokoro_voice,
            speed=speed or self.kokoro_speed
        )
        with open(output_file, 'wb') as f:
            f.write(audio_data)
            
    elif self.engine == "supertonic":
        audio_data = await self.supertonic.synthesize(
            text=clean_text,
            voice=voice or self.supertonic_voice,
            steps=self.supertonic_steps,
            speed=speed or self.supertonic_speed
        )
        with open(output_file, 'wb') as f:
            f.write(audio_data)
    
    return output_file
```

#### 2.3 Streaming TTS
**File**: `services/voice/streaming_tts.py:23-89`
```python
class StreamingTTSService:
    """Real-time TTS for streaming responses."""
    
    async def process_stream(self, text_stream, voice_client, speed=1.0):
        """Process streaming text to audio in real-time."""
        
        audio_buffer = []
        text_accumulator = ""
        
        async for text_chunk in text_stream:
            text_accumulator += text_chunk
            
            # Generate TTS for accumulated text
            if len(text_accumulator.strip()) > 20:  # Minimum chunk size
                try:
                    audio_file = await self.tts_service.generate_speech(
                        text=text_accumulator,
                        speed=speed
                    )
                    
                    # Queue audio for playback
                    await self._queue_audio(voice_client, audio_file)
                    
                    text_accumulator = ""  # Reset accumulator
                    
                except Exception as e:
                    logger.error(f"Streaming TTS error: {e}")
        
        # Process remaining text
        if text_accumulator.strip():
            final_audio = await self.tts_service.generate_speech(
                text=text_accumulator,
                speed=speed
            )
            await self._queue_audio(voice_client, final_audio)
```

### 3. RVC Voice Cloning
**File**: `services/voice/rvc.py:45-167`

#### 3.1 RVC Service Architecture
```python
class UnifiedRVCService:
    """RVC voice conversion service supporting multiple backends."""
    
    def __init__(self, mode="webui"):
        self.mode = mode  # "webui" or "inferpy"
        self.rvc_webui_url = Config.RVC_WEBUI_URL
        self.default_model = Config.DEFAULT_RVC_MODEL
        self.device = Config.RVC_DEVICE
        
        # RVC processing parameters
        self.pitch_shift = Config.RVC_PITCH_SHIFT
        self.protect = Config.RVC_PROTECT
        self.index_rate = Config.RVC_INDEX_RATE
        
        # Available models cache
        self.available_models = []
        self.model_cache = {}
```

#### 3.2 Voice Cloning Pipeline
```python
async def convert_voice(
    self,
    input_audio: Path,
    model_name: str,
    pitch_shift: Optional[int] = None,
    output_file: Optional[Path] = None
) -> Path:
    """Convert audio using RVC model."""
    
    # 1. Determine output path
    if not output_file:
        output_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4().hex}.wav"
    
    # 2. Process based on mode
    if self.mode == "webui":
        result = await self._rvc_webui_convert(
            input_audio=input_audio,
            model_name=model_name,
            pitch_shift=pitch_shift or self.pitch_shift,
            protect=self.protect,
            index_rate=self.index_rate,
            output_file=output_file
        )
    elif self.mode == "inferpy":
        result = await self._rvc_inferpy_convert(
            input_audio=input_audio,
            model_name=model_name,
            pitch_shift=pitch_shift or self.pitch_shift,
            output_file=output_file
        )
    
    return output_file

async def _rvc_webui_convert(self, input_audio, model_name, **kwargs):
    """Convert using RVC WebUI API."""
    import aiohttp
    import aiofiles
    
    async with aiohttp.ClientSession() as session:
        # 1. Upload input audio
        async with aiofiles.open(input_audio, 'rb') as f:
            audio_data = await f.read()
        
        # 2. Prepare form data
        data = aiohttp.FormData()
        data.add_field('audio', audio_data, filename='input.wav')
        data.add_field('model', model_name)
        data.add_field('pitch_shift', str(kwargs.get('pitch_shift', 0)))
        data.add_field('protect', str(kwargs.get('protect', 0.33)))
        data.add_field('index_rate', str(kwargs.get('index_rate', 0.75)))
        
        # 3. Send conversion request
        async with session.post(f"{self.rvc_webui_url}/convert", data=data) as response:
            if response.status == 200:
                converted_audio = await response.read()
                with open(kwargs.get('output_file'), 'wb') as f:
                    f.write(converted_audio)
            else:
                raise RuntimeError(f"RVC conversion failed: {response.status}")
```

### 4. Voice Command Processing
**File**: `services/voice/commands.py:34-156`

#### 4.1 Command Parser
```python
class VoiceCommandParser:
    """Parses and validates voice commands."""
    
    def __init__(self):
        self.command_patterns = {
            CommandType.SPEAK: r"^(say|speak|talk) (.+)",
            CommandType.CHANGE_VOICE: r"^(change|switch|use) voice (\w+)",
            CommandType.SET_SPEED: r"^(set|change) speed (\d+\.?\d*)",
            CommandType.ENABLE_RVC: r"^(enable|turn on) rvc (\w+)",
            CommandType.DISABLE_RVC: r"^(disable|turn off) rvc",
            CommandType.VOICE_LIST: r"^(list|show) voices?",
            CommandType.VOICE_INFO: r"^(what|which) voice",
        }
    
    def parse_command(self, text: str) -> Optional[VoiceCommand]:
        """Parse voice command from text."""
        text_lower = text.lower().strip()
        
        for command_type, pattern in self.command_patterns.items():
            match = re.match(pattern, text_lower)
            if match:
                if command_type == CommandType.SPEAK:
                    return VoiceCommand(
                        type=command_type,
                        text_to_speak=match.group(2).strip()
                    )
                elif command_type == CommandType.CHANGE_VOICE:
                    return VoiceCommand(
                        type=command_type,
                        voice_name=match.group(2)
                    )
                # ... other command types
        
        return None  # Not a voice command
```

#### 4.2 Command Execution
```python
async def execute_voice_command(self, command: VoiceCommand, voice_client=None):
    """Execute parsed voice command."""
    
    if command.type == CommandType.SPEAK:
        # Generate TTS and play
        audio_file = await self.tts_service.generate_speech(
            text=command.text_to_speak
        )
        if voice_client:
            await self._play_audio(voice_client, audio_file)
            
    elif command.type == CommandType.CHANGE_VOICE:
        # Change TTS voice
        if command.voice_name in self.tts_service.get_available_voices():
            self.tts_service.set_voice(command.voice_name)
            return f"Voice changed to {command.voice_name}"
        else:
            return "Voice not found"
            
    elif command.type == CommandType.ENABLE_RVC:
        # Enable RVC with specific model
        if command.voice_name in self.rvc_service.get_available_models():
            self.rvc_enabled = True
            self.current_rvc_model = command.voice_name
            return f"RVC enabled with model {command.voice_name}"
        else:
            return "RVC model not found"
```

### 5. Voice Client Management
**File**: `cogs/voice/manager.py:23-89`

#### 5.1 Voice Client Lifecycle
```python
class VoiceManager:
    """Manages Discord voice client connections."""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}  # guild_id -> voice_client
        self.audio_queues = {}  # guild_id -> asyncio.Queue
        
    async def connect_to_channel(self, channel: discord.VoiceChannel):
        """Connect to voice channel."""
        try:
            voice_client = await channel.connect()
            self.voice_clients[channel.guild.id] = voice_client
            self.audio_queues[channel.guild.id] = asyncio.Queue()
            
            # Start audio playback task
            asyncio.create_task(self._playback_loop(channel.guild.id))
            
            return voice_client
            
        except Exception as e:
            logger.error(f"Failed to connect to voice channel: {e}")
            raise
    
    async def _playback_loop(self, guild_id: int):
        """Continuous audio playback loop."""
        voice_client = self.voice_clients.get(guild_id)
        audio_queue = self.audio_queues.get(guild_id)
        
        while voice_client and voice_client.is_connected():
            try:
                # Get next audio file from queue
                audio_file = await asyncio.wait_for(
                    audio_queue.get(), 
                    timeout=1.0
                )
                
                # Play audio with proper FFmpeg options
                audio_source = discord.FFmpegPCMAudio(
                    str(audio_file),
                    options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo"
                )
                
                voice_client.play(audio_source)
                
                # Wait for playback to finish
                while voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                # Cleanup audio file
                audio_file.unlink(missing_ok=True)
                
            except asyncio.TimeoutError:
                continue  # No audio to play
            except Exception as e:
                logger.error(f"Audio playback error: {e}")
```

## Integration Points

### With Chat System
- **Auto Voice Replies**: Chat responses automatically converted to speech
- **Persona-Specific Voices**: Each character uses customized TTS/RVC settings
- **Voice Command Processing**: Natural language voice commands integrated with chat

### With Music System
- **Audio Channel Management**: Shared voice client connections
- **Queue Coordination**: TTS and music playback properly sequenced
- **Audio Format Standardization**: FFmpeg processing for all audio

### With Persona System
```python
# Persona-specific voice configuration
def get_persona_voice_config(self, persona_name: str) -> Dict:
    """Get voice settings for specific persona."""
    persona_configs = {
        "dagoth_ur": {
            "tts_voice": "am_onyx",
            "rvc_model": "GOTHMOMMY",
            "pitch_shift": -5,
            "speed": 0.9
        },
        "chief": {
            "tts_voice": "am_michael", 
            "rvc_model": "HALO_CHIEF",
            "pitch_shift": 0,
            "speed": 1.0
        }
    }
    return persona_configs.get(persona_name, {})
```

## Configuration

### Voice System Settings
```bash
# TTS Configuration
TTS_ENGINE=kokoro_api                        # kokoro, kokoro_api, supertonic
KOKORO_VOICE=am_adam                         # Default Kokoro voice
KOKORO_SPEED=1.0                             # Speech speed multiplier
KOKORO_API_URL=http://localhost:8880         # Kokoro FastAPI URL

# RVC Configuration
RVC_ENABLED=false                            # Enable voice cloning
RVC_MODE=webui                              # webui or inferpy
RVC_WEBUI_URL=http://localhost:7865         # RVC WebUI URL
DEFAULT_RVC_MODEL=GOTHMOMMY                 # Default RVC model
RVC_PITCH_SHIFT=0                           # Voice pitch adjustment
RVC_PROTECT=0.33                            # Voice protection factor
RVC_INDEX_RATE=0.75                         # Model influence

# STT Configuration
STT_ENGINE=whisper                           # whisper or parakeet
WHISPER_ENABLED=false                       # Enable Whisper STT
WHISPER_MODEL_SIZE=base                     # Model size: tiny, base, small, medium, large
WHISPER_SILENCE_THRESHOLD=1.0              # Silence detection threshold
MAX_RECORDING_DURATION=30                   # Max recording length in seconds

# Voice Activity Detection
VOICE_ENERGY_THRESHOLD=500                  # Audio energy threshold
VOICE_BOT_TRIGGER_WORDS=bot,assistant,hey   # Words that trigger bot response
```

## Performance Considerations

### 1. Audio Processing Optimization
- **Streaming TTS**: Real-time generation reduces response latency
- **Audio Caching**: Frequently used voice lines cached with TTL
- **Batch Processing**: Multiple audio files processed in parallel when possible

### 2. Resource Management
- **Voice Client Pooling**: Reuse connections to reduce overhead
- **Audio File Cleanup**: Automatic cleanup of temporary audio files
- **Memory Management**: Bounded audio queues to prevent memory leaks

### 3. Network Optimization
- **Connection Keep-Alive**: Persistent connections to TTS/RVC services
- **Request Batching**: Multiple TTS requests combined when possible
- **Compression**: Audio files compressed before transmission

## Security Considerations

### 1. Voice Data Privacy
- **Temporary Storage**: Audio files automatically deleted after processing
- **No Persistent Logging**: Voice data not stored in logs or databases
- **Access Control**: Voice commands only processed in authorized channels

### 2. Service Authentication
- **API Keys**: External TTS/STT services use authenticated endpoints
- **Local Processing**: Sensitive audio processed locally when possible
- **Network Isolation**: Voice services run in isolated network segments

## Common Issues and Troubleshooting

### 1. TTS Generation Failures
```bash
# Check TTS service availability
curl http://localhost:8880/voices  # Kokoro API
curl http://localhost:7865/models  # RVC WebUI

# Verify audio file permissions
ls -la ./data/temp/
chmod 755 ./data/temp/
```

### 2. Voice Connection Issues
```python
# Debug voice client state
voice_client = guild.voice_client
if voice_client:
    print(f"Connected: {voice_client.is_connected()}")
    print(f"Playing: {voice_client.is_playing()}")
else:
    print("No voice client connected")
```

### 3. RVC Processing Errors
- **Model Loading**: Verify RVC models are correctly installed
- **Memory Usage**: Monitor GPU/CPU usage during RVC processing
- **Audio Format**: Ensure input audio matches RVC expected format

### 4. STT Accuracy Issues
- **Audio Quality**: Check microphone quality and background noise
- **Model Selection**: Use appropriate Whisper model size for accuracy/latency tradeoff
- **Language Settings**: Verify language configuration matches speech

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `cogs/voice/main.py` | Core voice cog and TTS/RVC coordination |
| `cogs/voice/manager.py` | Voice client connection management |
| `services/voice/tts.py` | TTS service abstraction and engine selection |
| `services/voice/rvc.py` | RVC voice cloning service |
| `services/voice/listener.py` | Voice activity detection and STT processing |
| `services/voice/streaming_tts.py` | Real-time streaming TTS |
| `services/voice/commands.py` | Voice command parsing and execution |
| `services/clients/tts_client.py` | Kokoro TTS API client |
| `services/clients/rvc_client.py` | RVC processing API client |

---

**Last Updated**: 2025-12-16
**Version**: 1.0