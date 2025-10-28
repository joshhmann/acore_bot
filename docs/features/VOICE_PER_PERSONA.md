# Voice Per Persona - Automatic Voice Switching

## Feature

When you switch personas with `/set_persona`, the bot **automatically switches its voice** to match the personality!

## Voice Mappings

| Persona | Voice | Description |
|---------|-------|-------------|
| **chief** | `am_onyx` | Master Chief - Aggressive, intense US male |
| **arbiter** | `am_adam` | The Arbiter - Calm, composed, proper |
| **arby** | `am_adam` | Both characters - Uses Arbiter's voice |
| **gothmommy** | `af_bella` | Goth Mommy - Bella's voice |
| **pirate** | `am_adam` | Pirate character - Adam |
| **default** | `af_sarah` | Default helper - Sarah |
| **friendly** | `af_nicole` | Friendly personality - Nicole |
| **professional** | `am_michael` | Professional - Michael |
| **gaming** | `am_eric` | Gaming personality - Eric |

## Usage Example

```
User: /set_persona chief
Bot: ✅ Persona changed to: chief
     Conversation history has been cleared.
     🎤 Voice switched to match personality!

[Bot now uses am_onyx voice - aggressive tone]

User: /speak YO DUDE WHATS UP!!
[Bot speaks in deep, aggressive am_onyx voice]

---

User: /set_persona arbiter
Bot: ✅ Persona changed to: arbiter
     🎤 Voice switched to match personality!

[Bot now uses am_adam voice - calm, proper tone]

User: /speak Good day, how may I assist you?
[Bot speaks in calm, composed am_adam voice]
```

## How It Works

1. **You run** `/set_persona <name>`
2. **Bot loads** the personality prompt from `prompts/<name>.txt`
3. **Bot automatically switches** TTS voice based on the mapping
4. **Bot confirms** the change with 🎤 emoji
5. **All future voice responses** use the new voice

## Adding Custom Voices

Want to create a new persona with a specific voice?

### 1. Create the Prompt File

Create `prompts/yourpersona.txt`:
```txt
You are an expert actor...
[Your character description]
```

### 2. Add Voice Mapping

Edit `cogs/chat.py`, find the `persona_voices` dict around line 358:

```python
persona_voices = {
    "chief": "am_onyx",
    "arbiter": "am_adam",
    # ... existing entries ...
    "yourpersona": "af_nicole",  # ← Add your mapping here
}
```

### 3. Use It

```
/set_persona yourpersona
```

Voice automatically switches!

## Available Kokoro Voices

### Male Voices (US)
- `am_adam` - Calm, neutral
- `am_eric` - Energetic
- `am_liam` - Young, friendly
- `am_michael` - Professional
- `am_onyx` - Deep, aggressive ⭐ (Master Chief)

### Male Voices (British)
- `bm_george` - Formal, proper ⭐ (Arbiter alternative)
- `bm_lewis` - Casual British
- `bm_daniel` - Young British

### Female Voices (US)
- `af_sarah` - Standard female ⭐ (Default)
- `af_nicole` - Friendly, warm ⭐ (Friendly persona)
- `af_bella` - Sultry, confident ⭐ (Goth Mommy)
- `af_sky` - Bright, cheerful
- `af_jessica` - Professional female

### Female Voices (British)
- `bf_emma` - British female
- `bf_alice` - Young British female

To see ALL voices:
```bash
.venv311\Scripts\python.exe -c "from kokoro_onnx import Kokoro; k=Kokoro('kokoro-v1.0.onnx','voices-v1.0.bin'); print('\n'.join(sorted(k.get_voices())))"
```

## Customizing Existing Personas

Edit the voice mapping in [cogs/chat.py](cogs/chat.py:358-368):

```python
# Example: Change Arbiter to use British voice
"arbiter": "bm_george",    # Instead of am_adam

# Example: Give Chief a different aggressive voice
"chief": "am_eric",        # Instead of am_onyx
```

## Combining with RVC

Once RVC is set up, you can layer voice conversion ON TOP of Kokoro voices:

1. **Kokoro generates** base voice (am_onyx, af_bella, etc.)
2. **RVC converts** to target voice (GOTHMOMMY model, etc.)
3. **Result:** Character-appropriate base + your custom trained voice

Example:
- Persona: gothmommy
- Kokoro voice: af_bella (sultry female base)
- RVC model: GOTHMOMMY (your trained voice)
- Final: Perfect Goth Mommy voice!

## Testing

Test voice switching:

```bash
# In Discord:
/join                    # Join voice channel
/set_persona chief       # Switch to Chief
/speak WHATS UP BRO!!    # Hear am_onyx voice
/set_persona arbiter     # Switch to Arbiter
/speak Good day.         # Hear am_adam voice
/set_persona gothmommy   # Switch to Goth Mommy
/speak Hello there.      # Hear af_bella voice
```

## Technical Details

**Where:** [cogs/chat.py](cogs/chat.py:354-373)

**How:** When `/set_persona` is called:
1. Loads prompt from file
2. Looks up persona name in `persona_voices` dict
3. Updates `voice_cog.tts.kokoro_voice`
4. Logs the change
5. Notifies user with 🎤 emoji

**Fallback:** If persona not in mapping, voice stays the same.

## Summary

✅ Automatic voice switching when changing personas
✅ 9 pre-mapped personas with matching voices
✅ Easy to add custom voice mappings
✅ Works with 50+ Kokoro voices
✅ Combines with RVC for custom voices

Now your characters **sound** as good as they **talk**! 🎭🎤
