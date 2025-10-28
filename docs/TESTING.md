# Testing Guide for Discord Bot

## Quick Start

### Prerequisites
1. **Ollama**: Start Ollama server
   ```bash
   ollama serve
   ollama pull llama3.2
   ```

2. **Discord Token**: Set in `.env`
   ```env
   DISCORD_TOKEN=your_actual_token_here
   ```

3. **Dependencies**: Install with uv
   ```bash
   uv sync
   ```

## Running Tests

### Full Test Suite
```bash
uv run python test_bot.py
```

This comprehensive test will check:
- ✅ Ollama connection and health
- ✅ Model availability
- ✅ TTS voice generation
- ✅ RVC voice conversion
- ✅ Full integration pipeline

### Test Results Interpretation

#### ✅ Ollama Test
- **Passed**: Ollama is running and accessible
- **Failed**:
  - Make sure Ollama is running: `ollama serve`
  - Check `OLLAMA_HOST` in `.env` (default: http://localhost:11434)
  - Verify you have models: `ollama list`

#### ✅ TTS Test
- **Passed**: Edge TTS is working and generating audio
- Generates test file: `data/temp/test_tts.mp3`
- You can play this file to verify voice quality
- Lists all available voices (584 total, 140 English)

#### ✅ RVC Test
- **Passed**: RVC service is functional (currently placeholder)
- Place `.pth` model files in `data/voice_models/` for actual voice conversion
- Without models, audio passes through unchanged

#### ✅ Integration Test
- **Passed**: Full TTS + RVC pipeline works
- Generates: `data/temp/integration_tts.mp3` and `data/temp/integration_rvc.mp3`

## Testing Individual Services

### Test Ollama Only
```bash
uv run python -c "
import asyncio
from services.ollama import OllamaService
from config import Config

async def test():
    ollama = OllamaService(Config.OLLAMA_HOST, Config.OLLAMA_MODEL)
    await ollama.initialize()
    response = await ollama.generate('Say hello!')
    print(f'Response: {response}')
    await ollama.close()

asyncio.run(test())
"
```

### Test TTS Only
```bash
uv run python -c "
import asyncio
from pathlib import Path
from services.tts import TTSService

async def test():
    tts = TTSService()
    await tts.generate('Hello world!', Path('test.mp3'))
    print('Generated test.mp3')

asyncio.run(test())
"
```

## Running the Bot

### Start Bot (Development)
```bash
uv run python main.py
```

### Check Bot Status
The bot will log:
- Connected Discord servers
- Ollama connection status
- Loaded cogs (ChatCog, VoiceCog)
- Available commands synced

## Common Issues

### "Ollama is not reachable"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Pull a model if needed
ollama pull llama3.2
```

### "Invalid Discord token"
- Check `.env` file has valid `DISCORD_TOKEN`
- Generate new token at https://discord.com/developers/applications
- Ensure token has no extra spaces or quotes

### "Voice commands not working"
- Install FFmpeg: https://ffmpeg.org/download.html
- Add FFmpeg to PATH
- Grant bot "Connect" and "Speak" permissions in Discord

### "No RVC models found"
This is normal! RVC is optional:
1. Download `.pth` model files from RVC-Project
2. Place in `data/voice_models/`
3. Or set `RVC_ENABLED=false` in `.env`

## Test Audio Files

After running tests, check these files:
- `data/temp/test_tts.mp3` - Basic TTS test
- `data/temp/test_rvc.mp3` - RVC conversion test
- `data/temp/integration_tts.mp3` - Integration TTS
- `data/temp/integration_rvc.mp3` - Integration RVC

Play these files to verify audio quality.

## Performance Notes

### Using uv (Recommended)
- **Fast**: Up to 10-100x faster than pip
- **Reliable**: Consistent dependency resolution
- **Modern**: Built-in virtual environment management

### Commands with uv
```bash
# Install dependencies
uv sync

# Run scripts
uv run python main.py
uv run python test_bot.py

# Add new dependency
uv add package-name

# Update dependencies
uv lock --upgrade
```

## Next Steps

1. ✅ **Tests Pass**: Run the bot with `uv run python main.py`
2. ✅ **Configure Discord**: Set up bot permissions and invite
3. ✅ **Test Commands**: Try `/chat`, `/speak`, etc. in Discord
4. ⚠️ **Add RVC Models**: (Optional) For voice conversion
5. ⚠️ **Deploy**: (Optional) Host on a server for 24/7 uptime

## Discord Commands to Test

Once bot is running:

```
# Chat commands
/chat Hello, how are you?
/ask What is Python?
/models
/status

# Voice commands (in a voice channel)
/join
/speak text:Hello, this is a test!
/voices
/leave

# Advanced
/speak_as voice_model:modelname text:Hello!
```

## Monitoring

Watch the console output for:
- Successful command execution
- Ollama API calls
- TTS generation progress
- Error messages

Check `bot.log` for detailed logging.
