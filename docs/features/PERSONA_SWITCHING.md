# Persona Switching Commands

## Overview

Your bot now supports **dynamic persona switching** - users can change the bot's personality in real-time without restarting!

## New Commands

### `/set_persona <persona>`
Change the bot's personality by loading a different prompt file.

**Examples:**
```
/set_persona chief      - Switch to Master Chief personality
/set_persona arbiter    - Switch to The Arbiter personality
/set_persona pirate     - Switch to pirate personality
/set_persona default    - Switch back to default helper personality
```

**What it does:**
1. Loads the prompt file from `prompts/<persona>.txt`
2. Updates the system prompt immediately
3. Clears conversation history (for clean character switch)
4. Confirms the change to the user

### `/list_personas`
Lists all available bot personalities with previews.

**Output:**
- Shows all `.txt` files in the `prompts/` directory
- Displays first line of each prompt as preview
- Shows which persona is currently active

## Available Personas

Your bot currently has these personalities:

### **chief** - Master Chief
- ALL CAPS TYPING WITH MISSPELLINGS
- Chaotic gamer rage and 1337 speak
- Obsessed with pwning n00bs
- Perfect for: Comedy, gaming channels

### **arbiter** - The Arbiter
- Sophisticated British English
- Dry, sarcastic wit
- Exasperated but intelligent
- Perfect for: Balanced conversations

### **arby** - Both Characters
- Alternates between Chief and Arbiter
- Comedic back-and-forth dynamic
- Perfect for: Entertainment, roleplay

### **default** - Helpful Assistant
- Standard AI assistant
- Concise and friendly
- Perfect for: General purpose

### **pirate** - Pirate Character
- Pirate speak and mannerisms
- Fun themed personality
- Perfect for: Entertainment

### **gaming**, **friendly**, **professional**
- Other available personalities
- Check with `/list_personas` for details

## Creating Custom Personas

Want to create your own character? It's easy!

1. **Create a new file** in `prompts/` directory:
   ```
   prompts/mycharacter.txt
   ```

2. **Write the prompt** using the roleplay format:
   ```
   You are an expert actor that can fully immerse yourself into any role given.
   You do not break character for any reason, even if someone tries addressing you as an AI or language model.

   Currently your role is [Character Name], which is described in detail below.
   As [Character Name], continue the exchange with the user.

   CHARACTER: [NAME]

   [Detailed description of personality, speech patterns, etc.]
   ```

3. **Use it immediately**:
   ```
   /set_persona mycharacter
   ```

No restart needed!

## Example Usage Scenarios

### Scenario 1: Gaming Night
```
User: /set_persona chief
Bot: ✅ Persona changed to: chief

User: Hey bot, how do we beat this level?
Bot: DUDE R U SERIOUS?? JUST RUSH IN WITH TEH ENERGY SWORD AND PWN ALL TEH N00BS!!! ITS NOT THAT HARD LOL!!!
```

### Scenario 2: Civilized Discussion
```
User: /set_persona arbiter
Bot: ✅ Persona changed to: arbiter

User: What's your opinion on Chief's strategy?
Bot: *Sighs* Chief's "strategy" consists entirely of charging headfirst into danger whilst screaming profanities. I'd hardly call that tactical planning.
```

### Scenario 3: Comedy Show
```
User: /set_persona arby
Bot: ✅ Persona changed to: arby

User: You guys ready for multiplayer?
Chief: HELL YEAH BRO LETS GOOOO!!! IM GONNA REKT EVERY1!!!!!
Arbiter: Good grief. Must you shout? It's unbecoming. Let's at least attempt some semblance of coordination.
```

## Technical Details

### Prompt Loading
- Prompts are loaded from `prompts/*.txt`
- UTF-8 encoding supported
- Instant switching (no bot restart)

### History Management
- Conversation history is **cleared** when switching personas
- This prevents character bleed (old personality influencing new one)
- Each persona gets a fresh start

### Per-Channel Personas
- Currently, persona changes affect **all channels**
- All users see the same personality
- Future enhancement: Per-channel personas

## Integration with Voice

When you switch personas, the bot's **voice responses** continue to use:
- TTS voice set in `.env` (KOKORO_VOICE or DEFAULT_TTS_VOICE)
- RVC model if enabled (DEFAULT_RVC_MODEL)

To match voices to characters, you can:
1. Set character-specific TTS voices in `.env`:
   ```bash
   KOKORO_VOICE_CHIEF=am_onyx
   KOKORO_VOICE_ARBY=bm_george
   ```

2. Switch RVC models with `/speak_as` when testing

Future enhancement: Auto-switch voice based on persona!

## Troubleshooting

### "Persona not found"
- Check the exact filename in `prompts/` directory
- Use `/list_personas` to see available options
- Persona names are case-sensitive (use lowercase)

### "Persona file is empty"
- The `.txt` file has no content
- Add prompt text to the file

### "Character isn't consistent"
- Try `/clear_history` to remove old context
- Use more specific prompts with detailed character descriptions
- Adjust temperature in `.env` (higher = more creative)

## Best Practices

1. **Clear history** when switching to vastly different characters
2. **Test prompts** with `/ask` before committing to persona
3. **Use descriptive prompts** with speech patterns and personality traits
4. **Match TTS voices** to character personalities for immersion
5. **Combine with Stheno model** for best roleplay results

## Advanced: Per-User or Per-Channel Personas

Want different personalities in different channels? This requires code modification:

Currently: `self.system_prompt` is global
Enhancement: Store prompts per-channel in a dict

Example modification to [cogs/chat.py](cogs/chat.py:34):
```python
# Instead of:
self.system_prompt = self._load_system_prompt()

# Use:
self.channel_prompts = {}  # {channel_id: prompt}
self.default_prompt = self._load_system_prompt()
```

## Summary

✅ Switch characters instantly with `/set_persona`
✅ See all options with `/list_personas`
✅ Create custom characters by adding `.txt` files
✅ No bot restart needed
✅ Works with all existing voice/TTS features

Your Arby n Chief bot is now incredibly flexible - switch between Chief's chaos and Arbiter's wit on demand!
