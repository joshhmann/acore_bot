# Voice Features Guide

## Overview

This Discord bot can **automatically speak AI responses in voice channels** when you chat with it in text channels. This creates a seamless hands-free experience.

## How It Works

### Setup (One Time)

1. **Start the bot**
   ```bash
   uv run python main.py
   ```

2. **Enable auto-reply** in `.env`:
   ```env
   AUTO_REPLY_ENABLED=true
   AUTO_REPLY_WITH_VOICE=true
   ```

3. **Invite bot** to your Discord server with proper permissions:
   - Send Messages
   - Read Message History
   - Connect (voice)
   - Speak (voice)

### Using Voice Features

#### Option 1: Auto Voice Responses (Recommended)

1. **Join a voice channel** on your Discord server
2. **Bot joins voice**: Use `/join` command in any text channel
3. **Chat normally**: Mention the bot in any text channel
   ```
   @BotName what is the capital of France?
   ```
4. **Bot responds twice**:
   - 📝 Text response in the text channel
   - 🔊 **Speaks the same response** in the voice channel

**That's it!** Now you can have conversations while doing other things.

#### Option 2: Manual TTS Commands

You can also use direct TTS commands:

```
/speak text:Hello, this is a test!
/speak_as voice_model:your_model text:Custom voice test
```

## Configuration Options

### Enable/Disable Features

In your `.env` file:

```env
# Enable bot mentions triggering responses
AUTO_REPLY_ENABLED=true

# Enable voice responses (requires bot in voice channel)
AUTO_REPLY_WITH_VOICE=true

# Restrict to specific text channels (optional)
AUTO_REPLY_CHANNELS=123456789,987654321

# Choose TTS voice
DEFAULT_TTS_VOICE=en-US-AriaNeural

# Speech rate and volume
TTS_RATE=+0%
TTS_VOLUME=+0%

# Enable RVC voice conversion (optional)
RVC_ENABLED=true
DEFAULT_RVC_MODEL=your_model
```

## Use Cases

### 🎮 Gaming
- Bot in voice channel while you game
- Ask questions in text channel
- Get spoken answers without leaving your game

### 🎧 Multitasking
- Listen to AI responses while working
- Hands-free information lookup
- Background assistance

### 👥 Group Chat
- Multiple users can chat with bot
- Everyone hears responses in voice
- More engaging group experience

### 🎙️ Content Creation
- Bot can narrate answers for streams
- Voice personality for your Discord server
- Custom voices with RVC

## Available Voices

The bot uses **Microsoft Edge TTS** with 584+ voices across many languages!

### List Available Voices

```
/list_tts_voices
/list_tts_voices language:en
/list_tts_voices language:es
```

### Popular English Voices

- `en-US-AriaNeural` - Female, friendly (default)
- `en-US-GuyNeural` - Male, professional
- `en-GB-RyanNeural` - Male, British
- `en-AU-NatashaNeural` - Female, Australian
- `en-IN-NeerjaNeural` - Female, Indian

### Change Voice

```
/set_voice voice:en-GB-RyanNeural
```

Or in `.env`:
```env
DEFAULT_TTS_VOICE=en-GB-RyanNeural
```

## Advanced: RVC Voice Conversion

**Note**: Currently RVC is a placeholder implementation.

To use actual voice conversion:
1. Download/train `.pth` RVC models
2. Place in `data/voice_models/`
3. Set `RVC_ENABLED=true` in `.env`
4. Implement actual RVC inference (see [services/rvc.py](services/rvc.py))

With RVC, you can:
- Clone specific voices
- Apply celebrity voices
- Create character voices
- Custom voice personalities

## Troubleshooting

### Bot not speaking in voice channel

**Check:**
1. Bot is connected: `/join`
2. You're in a voice channel
3. `AUTO_REPLY_WITH_VOICE=true` in `.env`
4. Bot has "Speak" permission
5. FFmpeg is installed

### Voice quality issues

**Try:**
1. Change voice: `/set_voice`
2. Adjust speech rate: `TTS_RATE=+10%`
3. Adjust volume: `TTS_VOLUME=+10%`

### Bot interrupts itself

The bot won't speak if already playing audio. Wait for current audio to finish.

### No text response

**Check:**
1. `AUTO_REPLY_ENABLED=true`
2. You mentioned the bot: `@BotName`
3. Channel is in `AUTO_REPLY_CHANNELS` (if set)
4. Ollama is running

## Example Workflow

```bash
# 1. Start Ollama
ollama serve
ollama pull llama3.2

# 2. Configure .env
AUTO_REPLY_ENABLED=true
AUTO_REPLY_WITH_VOICE=true

# 3. Start bot
uv run python main.py

# 4. In Discord:
# - Join a voice channel
# - Type: /join
# - Type: @BotName tell me a joke
# - Bot replies in text AND speaks in voice!
```

## Configuration Reference

| Setting | Values | Description |
|---------|--------|-------------|
| `AUTO_REPLY_ENABLED` | `true`/`false` | Enable bot mention responses |
| `AUTO_REPLY_WITH_VOICE` | `true`/`false` | Speak responses in voice |
| `AUTO_REPLY_CHANNELS` | Channel IDs | Restrict to specific channels |
| `DEFAULT_TTS_VOICE` | Voice name | TTS voice to use |
| `TTS_RATE` | `-50%` to `+100%` | Speech speed |
| `TTS_VOLUME` | `-50%` to `+100%` | Speech volume |
| `RVC_ENABLED` | `true`/`false` | Enable voice conversion |

## Tips

1. **Keep responses concise** - Long responses take time to speak
2. **Use quality voices** - Neural voices sound more natural
3. **Adjust rate** - Faster speech (`+25%`) for quick info
4. **Multiple bots** - Run different instances with different voices
5. **Channel separation** - Use `AUTO_REPLY_CHANNELS` to avoid spam

## Next Steps

- Experiment with different voices
- Train custom RVC models
- Set up multiple voice profiles
- Create voice-activated workflows
- Integrate with other Discord bots

Enjoy your voice-enabled AI assistant! 🎉
