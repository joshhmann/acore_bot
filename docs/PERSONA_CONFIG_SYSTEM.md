# Persona Configuration System

## Overview

Each persona now has a **JSON configuration file** that defines not just the prompt, but also voice settings, RVC models, behavior, and more!

## Structure

```
prompts/
├── chief.txt          # The actual prompt text
├── chief.json         # Configuration for Master Chief
├── arbiter.txt        # Prompt text
├── arbiter.json       # Configuration for Arbiter
├── gothmommy.txt      # Prompt text
└── gothmommy.json     # Configuration for Goth Mommy
```

## JSON Config Format

```json
{
  "name": "chief",
  "display_name": "Master Chief",
  "description": "Master Chief from Arby n' The Chief - chaotic gamer",
  "prompt_file": "chief.txt",

  "voice": {
    "kokoro_voice": "am_onyx",
    "kokoro_speed": 1.1,
    "edge_voice": "en-US-GuyNeural",
    "edge_rate": "+20%",
    "edge_volume": "+10%"
  },

  "rvc": {
    "enabled": false,
    "model": null,
    "pitch_shift": 0
  },

  "behavior": {
    "clear_history_on_switch": true,
    "auto_reply_enabled": true,
    "affection_multiplier": 1.5
  },

  "tags": ["gaming", "halo", "comedy", "chaotic"]
}
```

## Configuration Fields

### Basic Info
- **name**: Internal persona identifier (lowercase, no spaces)
- **display_name**: Pretty name shown to users
- **description**: Brief description of the persona
- **prompt_file**: Which .txt file contains the prompt

### Voice Settings
Controls both Kokoro and Edge TTS:

**Kokoro (local):**
- `kokoro_voice`: Voice name (e.g., "am_onyx", "af_bella")
- `kokoro_speed`: Speech speed multiplier (0.5-2.0, default 1.0)

**Edge (cloud):**
- `edge_voice`: Voice name (e.g., "en-US-GuyNeural")
- `edge_rate`: Speed adjustment (e.g., "+20%", "-10%")
- `edge_volume`: Volume adjustment (e.g., "+10%", "-5%")

### RVC Settings
Voice conversion using RVC models:

- `enabled`: Whether to use RVC for this persona
- `model`: RVC model name (e.g., "GOTHMOMMY")
- `pitch_shift`: Pitch adjustment in semitones (-12 to +12)

### Behavior Settings
How the persona behaves:

- `clear_history_on_switch`: Clear chat history when switching to this persona
- `auto_reply_enabled`: Whether auto-reply works with this persona
- `affection_multiplier`: How fast users gain affection (1.0 = normal, 2.0 = twice as fast)

### Tags
Array of searchable tags for filtering personas:
- Examples: `["gaming", "halo", "comedy"]`
- Used for filtering: Find all "gaming" personas

## Creating a New Persona

### Step 1: Write the Prompt

Create `prompts/yourpersona.txt`:
```txt
You are an expert actor that can fully immerse yourself into any role...
[Your character description]
```

### Step 2: Create Config File

Create `prompts/yourpersona.json`:
```json
{
  "name": "yourpersona",
  "display_name": "Your Persona",
  "description": "A brief description",
  "prompt_file": "yourpersona.txt",

  "voice": {
    "kokoro_voice": "am_adam",
    "kokoro_speed": 1.0,
    "edge_voice": "en-US-AriaNeural",
    "edge_rate": "+0%",
    "edge_volume": "+0%"
  },

  "rvc": {
    "enabled": false,
    "model": null,
    "pitch_shift": 0
  },

  "behavior": {
    "clear_history_on_switch": true,
    "auto_reply_enabled": true,
    "affection_multiplier": 1.0
  },

  "tags": ["custom"]
}
```

### Step 3: Use It!

```
/set_persona yourpersona
```

Bot automatically:
- Loads your prompt
- Switches to your chosen voice
- Applies your settings
- Shows confirmation with all details

## Example Personas

### Master Chief (Aggressive Gamer)

```json
{
  "name": "chief",
  "voice": {
    "kokoro_voice": "am_onyx",     // Deep, aggressive
    "kokoro_speed": 1.1            // Slightly faster (energetic)
  },
  "behavior": {
    "affection_multiplier": 1.5    // Builds friendships fast
  },
  "tags": ["gaming", "halo", "chaotic"]
}
```

### The Arbiter (Sophisticated British)

```json
{
  "name": "arbiter",
  "voice": {
    "kokoro_voice": "am_adam",     // Calm, proper
    "kokoro_speed": 0.95           // Slightly slower (deliberate)
  },
  "behavior": {
    "affection_multiplier": 1.0    // Normal affection rate
  },
  "tags": ["halo", "british", "sophisticated"]
}
```

### Goth Mommy (With RVC)

```json
{
  "name": "gothmommy",
  "voice": {
    "kokoro_voice": "af_bella",    // Sultry female base
    "kokoro_speed": 0.9            // Slower, more sultry
  },
  "rvc": {
    "enabled": true,
    "model": "GOTHMOMMY",          // Custom trained voice
    "pitch_shift": 0
  },
  "behavior": {
    "affection_multiplier": 2.0    // Builds affection quickly
  },
  "tags": ["goth", "caring", "sultry"]
}
```

## Advanced Features

### Voice Speed Tuning

```json
"kokoro_speed": 1.2  // Chief: Fast, energetic
"kokoro_speed": 0.9  // Goth Mommy: Slow, sultry
"kokoro_speed": 0.95 // Arbiter: Slightly slow, deliberate
```

### Affection Multipliers

Control how fast users build relationships:

```json
"affection_multiplier": 0.5  // Hard to befriend (tsundere character)
"affection_multiplier": 1.0  // Normal rate
"affection_multiplier": 2.0  // Easy to befriend (friendly character)
```

### RVC Integration

Enable voice cloning for specific personas:

```json
"rvc": {
  "enabled": true,
  "model": "MY_MODEL",   // Must exist in data/voice_models/
  "pitch_shift": -2      // Lower pitch by 2 semitones
}
```

### Conditional History Clearing

```json
"clear_history_on_switch": false  // Keep history (for helper personas)
"clear_history_on_switch": true   // Clear history (for distinct characters)
```

## Backward Compatibility

**Legacy .txt files still work!**

If you have `prompts/oldpersona.txt` without a JSON config, the bot automatically creates a default config:

```json
{
  "name": "oldpersona",
  "display_name": "Oldpersona",
  "voice": { ...defaults... },
  "rvc": { "enabled": false },
  "behavior": { ...defaults... },
  "tags": []
}
```

You can then create the JSON later to customize it.

## Testing Your Config

### 1. Test Voice

```
/set_persona yourpersona
/join
/speak Test message
```

Listen to hear if voice matches your config.

### 2. Check Settings

```
/set_persona yourpersona
```

Bot response shows:
- ✅ Persona name
- 🎤 Voice settings applied
- 🔊 RVC model (if enabled)
- 🗑️ History cleared (if configured)
- 🏷️ Tags

### 3. Verify in Code

Check bot logs:
```
INFO:cogs.chat:Changed persona to: Master Chief
INFO:cogs.chat:Applied voice settings for chief
```

## Common Use Cases

### 1. Multiple Characters Same Universe

```json
// halo_chief.json
{"tags": ["halo", "unsc"], "affection_multiplier": 1.5}

// halo_arbiter.json
{"tags": ["halo", "covenant"], "affection_multiplier": 1.0}

// halo_cortana.json
{"tags": ["halo", "ai"], "affection_multiplier": 2.0}
```

Search: `/list_personas` filtered by "halo"

### 2. Gender-Specific Voices

```json
// assistant_male.json
{"voice": {"kokoro_voice": "am_michael"}}

// assistant_female.json
{"voice": {"kokoro_voice": "af_sarah"}}
```

### 3. Mood Variations

```json
// happy.json
{"voice": {"kokoro_speed": 1.2}, "affection_multiplier": 1.5}

// sad.json
{"voice": {"kokoro_speed": 0.8}, "affection_multiplier": 0.8}

// angry.json
{"voice": {"kokoro_speed": 1.3}, "affection_multiplier": 0.5}
```

## File Organization

```
prompts/
├── README.md          # This file
├── TEMPLATE.json      # Copy this for new personas
│
├── chief.txt          # Prompt text
├── chief.json         # Config
│
├── arbiter.txt
├── arbiter.json
│
├── gothmommy.txt
└── gothmommy.json
```

## Tips & Best Practices

1. **Match voice to personality**
   - Aggressive character → faster speed, deep voice
   - Calm character → slower speed, smooth voice

2. **Use affection multipliers wisely**
   - Friendly characters: 1.5-2.0
   - Normal: 1.0
   - Tsundere/cold: 0.5-0.8

3. **Tag everything**
   - Makes personas searchable
   - Group related personas
   - Filter by mood/genre

4. **Test before deploying**
   - Generate sample audio
   - Check RVC models work
   - Verify behavior settings

5. **Document in description**
   - Clear, one-line summary
   - Helps users choose persona

## Troubleshooting

### "Persona not found"
- Check JSON filename matches prompt filename
- Ensure `name` field matches filename
- Check for typos

### "Voice not changing"
- Verify `kokoro_voice` is valid voice name
- Check TTS engine setting (kokoro vs edge)
- Restart bot after changing configs

### "RVC not working"
- Ensure `rvc.enabled` is `true`
- Check model exists in `data/voice_models/`
- Verify RVC_ENABLED=true in `.env`

### "Settings not applying"
- Restart bot to reload configs
- Check JSON syntax (use validator)
- Look for errors in bot logs

## Summary

✅ JSON configs for complete persona customization
✅ Voice settings (Kokoro & Edge) per persona
✅ RVC model assignment per persona
✅ Behavior settings (history, affection, auto-reply)
✅ Tags for organization and filtering
✅ Backward compatible with legacy .txt files
✅ Hot-reloadable (no bot restart needed)

Create rich, fully-configured personas with just one JSON file!
