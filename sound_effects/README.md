# Sound Effects System

This directory contains sound effect files and configuration for the bot's reaction sounds.

## How It Works

When someone speaks in voice chat, the bot listens for trigger words and plays matching sound effects. For example:
- Someone says "**bruh**" → plays `bruh.mp3`
- Someone says "**I whiffed**" → plays `pipes_falling.mp3`
- Someone says "**nailed it!**" → plays `perfect.mp3`

## Adding Sound Effects

### 1. Add Your Sound File

Place your sound file (MP3, WAV, OGG) in this directory:
```
sound_effects/
  your_sound.mp3
```

**Recommended specs:**
- Format: MP3 or WAV
- Duration: 1-5 seconds (keep it short!)
- Volume: Normalize to prevent ear-blasting

### 2. Edit config.json

Add an entry to the `effects` array in `config.json`:

```json
{
  "name": "Your Sound Name",
  "file": "your_sound.mp3",
  "triggers": ["trigger word", "another trigger", "phrase here"],
  "cooldown": 10,
  "volume": 0.5
}
```

**Settings:**
- `name`: Display name for the sound
- `file`: Filename in this directory
- `triggers`: Words/phrases that trigger this sound (case-insensitive)
- `cooldown`: Seconds before this sound can play again (prevents spam)
- `volume`: Volume level 0.0-1.0 (0.5 = 50%)

### 3. Reload

Use the slash command `/reload_sounds` in Discord, or restart the bot.

## Example Sounds to Add

Here are some popular sound effect ideas:

**Reactions:**
- `bruh.mp3` - For "bruh" moments
- `vine_boom.mp3` - Dramatic reveals
- `oh_no.mp3` - When something goes wrong
- `sad_trombone.mp3` - For failures

**Gaming:**
- `pipes_falling.mp3` - For whiffs/misses
- `perfect.mp3` - For clutch plays
- `airhorn.mp3` - For hype moments
- `gottem.mp3` - For pranks

**Memes:**
- `bonk.mp3` - Bonk sound
- `crickets.mp3` - Awkward silence
- `nani.mp3` - "NANI?!"
- `windows_xp.mp3` - Windows startup

## Finding Sound Effects

Good sources for sound effects:
- [Freesound.org](https://freesound.org/) - Free sound effects library
- [Myinstants.com](https://www.myinstants.com/) - Popular meme sounds
- YouTube (search "sound effect" + name, download with yt-dlp)

## Configuration Options

### Global Settings

In `config.json`:

```json
{
  "enabled": true,           // Enable/disable entire system
  "global_volume": 0.5,      // Master volume for all effects (0.0-1.0)
  "effects": [...]
}
```

### Disabling Temporarily

Set `"enabled": false` to disable all sound effects without removing them.

## Tips

1. **Keep sounds SHORT** - 1-3 seconds is ideal
2. **Use appropriate cooldowns** - Prevent spam (10-20 seconds)
3. **Balance volumes** - Some sounds are louder than others
4. **Test in voice** - Make sure it sounds good before unleashing on your server
5. **Don't overlap with commands** - Avoid triggers like "play", "skip" that are already commands

## Slash Commands

- `/reload_sounds` - Reload sound effects config
- `/list_sounds` - Show all available sounds and triggers
- `/toggle_sounds` - Enable/disable sound effects

## Technical Details

- Sound effects **WON'T** interrupt bot TTS
- Sound effects **WON'T** interrupt music (for now - future: mix them in)
- Each effect has individual cooldown tracking
- Trigger matching is case-insensitive and matches whole words
- Uses Discord FFmpeg audio for playback
