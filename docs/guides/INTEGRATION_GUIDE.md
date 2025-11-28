# Integration Guide: AI-First Persona System

## Overview

This guide shows how to integrate the new AI-first persona system with your existing bot while keeping all services (TTS, RVC, Ollama, RAG) intact.

**What changed:** The bot's "brain" (decision-making and personality) is now driven by JSON configs instead of hardcoded logic.

**What stayed the same:** All your existing services (Ollama, TTS, RVC, RAG, user profiles, etc.)

---

## Quick Start

### 1. Configure Environment

Add to `.env`:

```bash
# Persona configuration
CHARACTER=dagoth_ur
FRAMEWORK=neuro

# Or try other combinations:
# CHARACTER=dagoth_ur + FRAMEWORK=assistant (Helpful Dagoth)
# CHARACTER=wizard + FRAMEWORK=neuro (Chaotic Wizard)
```

### 2. Update main.py

```python
# Add persona system imports
from services.persona_system import PersonaSystem
from services.ai_decision_engine import AIDecisionEngine
from services.enhanced_tools import EnhancedToolSystem

# In your bot initialization
async def setup_bot(bot):
    # ... existing services (ollama, tts, rvc, etc.) ...

    # NEW: Initialize persona system
    persona_system = PersonaSystem()

    # Load character + framework from env
    character_id = Config.get("CHARACTER", "dagoth_ur")
    framework_id = Config.get("FRAMEWORK", "neuro")

    # Compile persona
    persona = persona_system.compile_persona(character_id, framework_id)

    if not persona:
        logger.error(f"Failed to load persona: {character_id}_{framework_id}")
        return

    # NEW: Initialize decision engine
    tool_system = EnhancedToolSystem()
    decision_engine = AIDecisionEngine(ollama_service, tool_system)
    decision_engine.set_persona(persona)

    # Make available to cogs
    bot.persona_system = persona_system
    bot.decision_engine = decision_engine
    bot.current_persona = persona

    logger.info(f"Loaded persona: {persona.persona_id}")
```

### 3. Update cogs/chat.py

Modify your chat cog to use the decision engine:

```python
class ChatCog(commands.Cog):
    def __init__(self, bot, ollama, history_manager, **kwargs):
        self.bot = bot
        self.ollama = ollama
        self.history = history_manager

        # All your existing services stay
        self.user_profiles = kwargs.get('user_profiles')
        self.rag = kwargs.get('rag')
        # ... etc ...

        # NEW: Get decision engine (if available)
        self.decision_engine = getattr(bot, 'decision_engine', None)
        self.current_persona = getattr(bot, 'current_persona', None)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Build context
        context = await self._build_context(message)

        # NEW: Use decision engine if available
        if self.decision_engine:
            # Let AI decide if it should respond
            decision = await self.decision_engine.should_respond(
                message.content,
                context
            )

            if not decision["should_respond"]:
                return

            # Generate response using persona
            response = await self.decision_engine.generate_response(
                message.content,
                context,
                style_hint=decision.get("suggested_style")
            )

            # Mark that we responded
            self.decision_engine.mark_response(message.channel.id)

        else:
            # Fallback to old method if decision engine not available
            response = await self._generate_old_way(message, context)

        # Send response (existing code)
        await message.channel.send(response)

        # TTS if enabled (existing code)
        if Config.AUTO_REPLY_WITH_VOICE:
            await self._send_voice_response(response, message)

    async def _build_context(self, message) -> dict:
        """Build context dictionary for decision engine."""
        context = {
            "channel_id": message.channel.id,
            "user_id": message.author.id,
            "mentioned": self.bot.user.mentioned_in(message),
            "conversation_history": await self._get_history(message.channel.id),
        }

        # Add user profile if available
        if self.user_profiles:
            profile = await self.user_profiles.get_profile(message.author.id)
            if profile:
                context["user_profile"] = profile

        # Add RAG context if available
        if self.rag:
            relevant_docs = await self.rag.search(message.content, top_k=2)
            if relevant_docs:
                context["rag_context"] = relevant_docs

        return context
```

---

## File Structure

```
acore_bot/
├── services/
│   ├── persona_system.py          # NEW: Loads frameworks + characters
│   ├── ai_decision_engine.py      # NEW: Makes AI-first decisions
│   ├── enhanced_tools.py          # NEW: Anti-hallucination tools
│   ├── ollama.py                  # EXISTING: Stays the same
│   ├── tts.py                     # EXISTING: Stays the same
│   ├── rvc_unified.py             # EXISTING: Stays the same
│   └── ...                        # All other services stay
│
└── prompts/
    ├── frameworks/                # NEW: Behavioral frameworks
    │   ├── neuro.json             # Neuro-style behaviors
    │   ├── assistant.json         # Helpful assistant behaviors
    │   └── custom.json            # Your custom frameworks
    │
    ├── characters/                # NEW: Character identities
    │   ├── dagoth_ur.json         # Dagoth Ur character
    │   ├── wizard.json            # Wizard character
    │   └── custom.json            # Your custom characters
    │
    └── compiled/                  # AUTO-GENERATED: Don't edit
        └── dagoth_ur_neuro.json   # Compiled persona
```

---

## How It Works

### Old Way (Hardcoded):

```python
# Hardcoded behavior
if random.random() < 0.1:
    await send("Fortnite? Really?")

if "what time" in message:
    await send("It's around 3 PM")  # HALLUCINATION!
```

### New Way (AI-First):

```python
# 1. Decision engine checks framework rules
decision = await engine.should_respond(message, context)

# 2. If yes, generate using persona + tools
response = await engine.generate_response(message, context)

# 3. LLM sees tools available and uses them
# LLM: "TOOL: get_current_time()"
# System: "3:47 PM"
# LLM: "It's 3:47 PM, mortal."
```

---

## Configuration Examples

### Current Setup (Dagoth Neuro)

```bash
CHARACTER=dagoth_ur
FRAMEWORK=neuro
```

Result: Chaotic, sarcastic Dagoth Ur with Neuro-sama energy

### Helpful Dagoth

```bash
CHARACTER=dagoth_ur
FRAMEWORK=assistant
```

Result: Professional assistant who still calls you "mortal"

### Different Character

```bash
CHARACTER=wizard
FRAMEWORK=mentor
```

Result: Teaching wizard (once you create wizard.json)

---

## Creating Custom Content

### New Character

1. Copy `prompts/characters/dagoth_ur.json`
2. Edit identity, opinions, quirks
3. Save as `prompts/characters/your_character.json`
4. Set `CHARACTER=your_character` in `.env`

### New Framework

1. Copy `prompts/frameworks/neuro.json`
2. Edit behavioral_patterns, decision_making
3. Save as `prompts/frameworks/your_framework.json`
4. Set `FRAMEWORK=your_framework` in `.env`

---

## Commands (Add to Bot)

```python
@commands.command(name="persona")
async def change_persona(self, ctx, character: str, framework: str):
    """Change bot persona dynamically."""

    persona = self.bot.persona_system.compile_persona(character, framework)

    if not persona:
        await ctx.send(f"Could not load {character}_{framework}")
        return

    self.bot.decision_engine.set_persona(persona)
    self.bot.current_persona = persona

    await ctx.send(f"Switched to: {persona.character.display_name} ({persona.framework.name})")


@commands.command(name="list_personas")
async def list_available(self, ctx):
    """List available characters and frameworks."""

    characters = self.bot.persona_system.list_available_characters()
    frameworks = self.bot.persona_system.list_available_frameworks()

    response = "**Available Characters:**\n"
    for char in characters:
        response += f"- `{char['id']}`: {char['name']}\n"

    response += "\n**Available Frameworks:**\n"
    for fw in frameworks:
        response += f"- `{fw['id']}`: {fw['name']} ({fw['purpose']})\n"

    await ctx.send(response)
```

---

## Testing

### 1. Test Framework Loading

```bash
python3 -c "
from services.persona_system import PersonaSystem
ps = PersonaSystem()
persona = ps.compile_persona('dagoth_ur', 'neuro')
print(f'Loaded: {persona.persona_id}')
print(f'System prompt length: {len(persona.system_prompt)}')
"
```

### 2. Test Decision Engine

```bash
python3 -c "
from services.persona_system import PersonaSystem
from services.ai_decision_engine import AIDecisionEngine
from services.ollama import OllamaService

ps = PersonaSystem()
ollama = OllamaService()
persona = ps.compile_persona('dagoth_ur', 'neuro')

engine = AIDecisionEngine(ollama)
engine.set_persona(persona)

print('Decision engine ready')
"
```

### 3. Test Full Flow

In Discord:

```
User: "What time is it?"
Bot: [Should respond: yes (question_asked)]
Bot: [Uses tool: get_current_time()]
Bot: "It's 3:47 PM, mortal."

User: *starts playing Fortnite*
Bot: [Should respond: only if in conversation]
Bot: [If yes] "Fortnite? I've seen ash zombies with better taste."
```

---

## Migrating Existing Features

### Ambient Mode → Framework Spontaneity

Old:
```python
# services/ambient_mode.py
if random.random() < 0.05:
    await send_random_thought()
```

New:
```json
// frameworks/neuro.json
"spontaneity": {
  "random_interjection_chance": 0.05
}
```

### Event Reactions → Framework Decision Rules

Old:
```python
# cogs/event_listeners.py
if activity_changed and random.random() < 0.4:
    await react()
```

New:
```json
// frameworks/neuro.json
"decision_making": {
  "when_to_respond": {
    "activity_changed": "if_in_conversation"
  }
}
```

### Hardcoded Responses → Character Quirks

Old:
```python
responses = ["Fortnite? Really?", "I've seen better taste"]
```

New:
```json
// characters/dagoth_ur.json
"opinions": {
  "hates": {
    "games": ["Fortnite"]
  },
  "hot_takes": ["Fortnite is for mortals with no taste"]
}
```

---

## Troubleshooting

### "No persona loaded"
- Check `CHARACTER` and `FRAMEWORK` in `.env`
- Ensure JSON files exist in `prompts/characters/` and `prompts/frameworks/`
- Check logs for JSON parsing errors

### "Bot not responding"
- Check decision_making rules in framework
- Verify `when_to_respond` conditions
- Test with `@mention` (should always work)

### "Bot hallucinating facts"
- Check `anti_hallucination.mode` in framework
- Verify tools are available
- Check LLM is using tools (look for "TOOL:" in responses)

### "Responses don't match character"
- Check character quirks and opinions
- Verify system_prompt is being built correctly
- Try regenerating compiled persona

---

## Next Steps

1. Test current Dagoth + Neuro combination
2. Create new characters (wizard, detective, etc.)
3. Experiment with framework combinations
4. Tune behavioral patterns for your preferences
5. Add custom frameworks for specific use cases

Your existing bot services (TTS, RVC, RAG, etc.) will work exactly as before - we've just given the bot an AI-first brain!
