# L3-8B-Stheno-v3.2 Roleplay Model Setup

## What We've Configured

Your bot now supports **advanced roleplay sampling parameters** optimized for the L3-8B-Stheno-v3.2 model - a Llama 3 8B model fine-tuned for creative writing and character roleplay.

### Changes Made

#### 1. OllamaService Enhanced ([services/ollama.py](services/ollama.py))
Added roleplay-optimized sampling parameters:
- `temperature`: 1.17 (range 1.12-1.22 recommended for roleplay)
- `min_p`: 0.075 (controls token probability threshold)
- `top_k`: 50 (limits token selection pool)
- `repeat_penalty`: 1.1 (reduces repetition)

#### 2. Configuration Updated
**[.env.example](.env.example)** and **[config.py](config.py)** now include:
```bash
OLLAMA_MODEL=fluffy/l3-8b-stheno-v3.2:latest
OLLAMA_TEMPERATURE=1.17
OLLAMA_MIN_P=0.075
OLLAMA_TOP_K=50
OLLAMA_REPEAT_PENALTY=1.1
```

#### 3. Character Prompts Created
Using the roleplay system prompt format you provided:

**[prompts/chief.txt](prompts/chief.txt)** - Master Chief personality:
- ALL CAPS TYPING WITH MISSPELLINGS
- 1337 speak and gamer slang
- Chaotic, profane, immature humor
- Obsessed with pwning n00bs

**[prompts/arbiter.txt](prompts/arbiter.txt)** - The Arbiter personality:
- Sophisticated British English
- Dry, sarcastic wit
- Exasperated by Chief's antics
- Intelligent and articulate

**[prompts/arby.txt](prompts/arby.txt)** - Combined roleplay (existing):
- Both characters alternating
- Comedic tension between them

## How to Use

### 1. Start Ollama
```bash
ollama serve
```

### 2. Update Your .env File
```bash
# Copy from .env.example or edit directly
OLLAMA_MODEL=fluffy/l3-8b-stheno-v3.2:latest
OLLAMA_TEMPERATURE=1.17
OLLAMA_MIN_P=0.075
OLLAMA_TOP_K=50
OLLAMA_REPEAT_PENALTY=1.1

# Choose a character personality
SYSTEM_PROMPT_FILE=./prompts/chief.txt
# Or: ./prompts/arbiter.txt
# Or: ./prompts/arby.txt (both characters)
```

### 3. Test the Characters
```bash
# Test individual characters
.venv311\Scripts\python.exe test_stheno_characters.py
```

This will test:
- Master Chief responding to a Halo question
- Arbiter giving his opinion on Chief's skills
- Multi-turn conversation with Arbiter

### 4. Run Your Bot
```bash
.venv311\Scripts\python.exe main.py
```

Now when users chat with your bot:
- `/chat` commands will use the character personality
- Responses will be in-character (Chief's chaos or Arbiter's wit)
- Voice responses will use the matching TTS voice:
  - Chief: `KOKORO_VOICE_CHIEF=am_onyx` (aggressive US male)
  - Arbiter: `KOKORO_VOICE_ARBY=bm_george` (British male)

## Why This Model?

**L3-8B-Stheno-v3.2** advantages for Arby n Chief:
- ✅ Excellent at maintaining consistent character personalities
- ✅ Understands roleplay and creative writing
- ✅ Handles informal internet speak naturally
- ✅ Better at comedic timing and banter
- ✅ Can maintain distinct voices in multi-character scenarios
- ✅ More entertaining and engaging responses

## Sampler Settings Explained

### Temperature (1.17)
- Higher = more creative/random responses
- Range 1.12-1.22 recommended for roleplay
- Lower (0.7) = more predictable/factual

### Min-P (0.075)
- Filters out low-probability tokens
- Helps maintain coherence while allowing creativity
- Lower = more diverse vocabulary

### Top-K (50)
- Limits selection to top 50 most likely tokens
- Balances creativity with relevance
- Prevents completely random outputs

### Repeat Penalty (1.1)
- Discourages repeating same phrases
- Keeps dialogue fresh and natural
- 1.1 is mild (won't break natural repetition)

## Testing Examples

### Test Chief
```bash
User: "What's your favorite Halo weapon?"

Expected Chief response:
"DUDE TEH ENERGY SWORD IS SO FRIKEN AWESOME!!11 I JUST RUN AROUND SLICING N00BS IN HALF LOL!! SLICE SLICE B*TCH!! GET REKT!!! ALTHOUGH TEH ROCKET LAUNCHER IS PRETTY SICK 2 CUZ BIG EXPLOSIONS GO BOOM!!! HAHA!!"
```

### Test Arbiter
```bash
User: "What do you think of Master Chief?"

Expected Arbiter response:
"*Sighs heavily* Chief is... an acquired taste, shall we say. His intellectual capacity rivals that of a particularly dim houseplant, and his vocabulary consists primarily of profanity and gaming terminology. Yet despite his numerous shortcomings, there's an odd charm to his relentless enthusiasm. One learns to tolerate him, much like a persistent headache."
```

## Troubleshooting

### "Cannot connect to Ollama"
```bash
# Start Ollama server
ollama serve

# In another terminal, verify model exists
ollama list | grep stheno
```

### "Responses aren't in character"
- Check `SYSTEM_PROMPT_FILE` points to correct prompt
- Ensure temperature is 1.12+ for creative roleplay
- Try clearing chat history: `/clear_history`

### "Model is slow"
- This is an 8B parameter model (larger than llama3.2:3b)
- Requires ~5GB VRAM or will use CPU (slower)
- Consider using GPU if available
- Adjust `OLLAMA_MAX_TOKENS` to limit response length

## Next Steps

1. **Test both characters** to see which personality fits better
2. **Combine with RVC voice conversion** once RVC-WebUI is set up
3. **Create custom prompts** for other characters or moods
4. **Adjust sampler settings** if responses are too random or too conservative

## Credits

- Model: [Sao10K/L3-8B-Stheno-v3.2](https://huggingface.co/Sao10K/L3-8B-Stheno-v3.2)
- Ollama: [fluffy/l3-8b-stheno-v3.2](https://ollama.com/fluffy/l3-8b-stheno-v3.2)
- Characters: Arby n' The Chief by DigitalPh33r
