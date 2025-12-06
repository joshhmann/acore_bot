# Service Interface Abstractions

This directory contains abstract base classes (interfaces) for all major bot services. These interfaces establish clear contracts between components and enable better testing, flexibility, and maintainability.

## Available Interfaces

### TTSInterface (Text-to-Speech)
**File**: `tts_interface.py`

**Methods**:
- `async def generate(text, output_path, voice, speed, **kwargs) -> Path`
- `async def list_voices() -> list`
- `async def is_available() -> bool`
- `async def cleanup()`

**Implementations**:
- `services/tts.py` → TTSService (Kokoro, Supertonic)
- `services/kokoro_tts.py` → KokoroTTSService
- `services/supertonic_tts.py` → SupertonicTTSService

**Example Usage**:
```python
from services.interfaces import TTSInterface
from services.tts import TTSService

# Type hint with interface for flexibility
tts: TTSInterface = TTSService(engine="kokoro_api")

# All TTS services have the same interface
audio_path = await tts.generate(
    text="Hello world",
    output_path=Path("output.mp3"),
    voice="am_adam",
    speed=1.0
)
```

---

### STTInterface (Speech-to-Text)
**File**: `stt_interface.py`

**Methods**:
- `async def transcribe_file(audio_path, language, task, **kwargs) -> TranscriptionResult`
- `async def transcribe_audio_data(audio_data, sample_rate, language, **kwargs) -> TranscriptionResult`
- `def is_available() -> bool`
- `async def cleanup()`
- `def get_supported_languages() -> list[str]`

**Return Type**:
```python
TranscriptionResult = TypedDict({
    "text": str,          # Full transcribed text
    "language": str,      # Detected/specified language
    "segments": list      # Timed segments (optional)
})
```

**Implementations**:
- `services/whisper_stt.py` → WhisperSTTService
- `services/parakeet_stt.py` → ParakeetSTTService

**Example Usage**:
```python
from services.interfaces import STTInterface
from services.whisper_stt import WhisperSTTService

# Type hint with interface
stt: STTInterface = WhisperSTTService(model_size="base")

# Transcribe audio file
result = await stt.transcribe_file(
    audio_path=Path("voice.wav"),
    language="en"
)
print(f"Transcription: {result['text']}")
```

---

### LLMInterface (Large Language Model)
**File**: `llm_interface.py`

**Methods**:
- `async def chat(messages, system_prompt, temperature, max_tokens, **kwargs) -> str`
- `async def chat_stream(messages, ...) -> AsyncGenerator[str, None]`
- `async def generate(prompt, system_prompt, max_tokens, **kwargs) -> str`
- `async def chat_with_vision(prompt, images, system_prompt, **kwargs) -> str`
- `async def is_available() -> bool`
- `async def initialize()`
- `async def cleanup()`
- `def get_model_name() -> str`

**Implementations**:
- `services/ollama.py` → OllamaService
- `services/openrouter.py` → OpenRouterService

**Example Usage**:
```python
from services.interfaces import LLMInterface
from services.ollama import OllamaService

# Type hint with interface - easy to swap implementations
llm: LLMInterface = OllamaService(host="http://localhost:11434", model="llama3")

# Chat interface
messages = [
    {"role": "user", "content": "What is Python?"}
]
response = await llm.chat(messages, temperature=0.7)

# Streaming interface
async for chunk in llm.chat_stream(messages):
    print(chunk, end="", flush=True)
```

---

### RVCInterface (Real-time Voice Conversion)
**File**: `rvc_interface.py`

**Methods**:
- `async def convert(input_audio, output_audio, model_name, pitch_shift, index_rate, **kwargs) -> Path`
- `async def list_models() -> list[str]`
- `async def is_enabled() -> bool`
- `async def health_check() -> bool`
- `async def load_model(model_name)`
- `async def initialize()`
- `async def cleanup()`
- `def get_default_model() -> Optional[str]`

**Implementations**:
- `services/rvc_http.py` → RVCHTTPClient
- `services/rvc_unified.py` → RVCUnifiedClient

**Example Usage**:
```python
from services.interfaces import RVCInterface
from services.rvc_http import RVCHTTPClient

# Type hint with interface
rvc: RVCInterface = RVCHTTPClient(base_url="http://localhost:7865")

# Convert voice
output = await rvc.convert(
    input_audio=Path("input.wav"),
    output_audio=Path("output.wav"),
    model_name="my_voice",
    pitch_shift=0,
    index_rate=0.75
)
```

---

## Benefits

### 1. **Easy Testing with Mocks**
```python
from unittest.mock import AsyncMock
from services.interfaces import TTSInterface

# Create mock TTS for unit testing
mock_tts = AsyncMock(spec=TTSInterface)
mock_tts.generate.return_value = Path("test.mp3")

# Use in tests
chat_cog = ChatCog(bot, ollama, history, tts=mock_tts)
```

### 2. **Swappable Implementations**
```python
# Switch TTS engines without changing code
if config.TTS_ENGINE == "kokoro":
    tts: TTSInterface = KokoroTTSService()
elif config.TTS_ENGINE == "supertonic":
    tts: TTSInterface = SupertonicTTSService()
else:
    tts: TTSInterface = TTSService(engine=config.TTS_ENGINE)

# All have the same interface - no code changes needed!
```

### 3. **Clear Contracts**
- Every implementation *must* provide all interface methods
- Type hints ensure correct usage
- IDE autocomplete works perfectly
- Easier to onboard new developers

### 4. **Dependency Injection Ready**
```python
class BotServices:
    def __init__(
        self,
        tts: TTSInterface,
        stt: STTInterface,
        llm: LLMInterface,
        rvc: Optional[RVCInterface] = None
    ):
        self.tts = tts
        self.stt = stt
        self.llm = llm
        self.rvc = rvc
```

---

## Implementing New Services

To add a new TTS engine, for example:

```python
from services.interfaces import TTSInterface
from pathlib import Path
from typing import Optional

class MyCustomTTSService(TTSInterface):
    """My custom TTS implementation."""

    async def generate(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        **kwargs
    ) -> Path:
        # Your implementation here
        # Must return Path to generated audio file
        pass

    async def list_voices(self) -> list:
        # Return list of available voices
        return [
            {"name": "voice1", "description": "Voice 1"},
            {"name": "voice2", "description": "Voice 2"},
        ]

    async def is_available(self) -> bool:
        # Check if service is ready
        return True

    async def cleanup(self):
        # Optional cleanup logic
        pass
```

Then use it anywhere that expects TTSInterface!

---

## Migration Guide

To update existing services to use interfaces:

1. **Inherit from interface**:
   ```python
   from services.interfaces import TTSInterface

   class KokoroTTSService(TTSInterface):  # Add inheritance
       ...
   ```

2. **Ensure all methods match interface**:
   - Check method signatures match exactly
   - Add any missing methods with default implementations
   - Use type hints consistently

3. **Update type hints in consuming code**:
   ```python
   # Before
   def __init__(self, tts):

   # After
   def __init__(self, tts: TTSInterface):
   ```

4. **Test thoroughly**:
   - All interface methods should work
   - Type checking should pass (mypy/pyright)
   - Runtime behavior unchanged

---

## Next Steps

- [ ] Update existing services to inherit from interfaces
- [ ] Add comprehensive tests using mocked interfaces
- [ ] Implement dependency injection container
- [ ] Add interface compliance tests (ensure all implementations match)
