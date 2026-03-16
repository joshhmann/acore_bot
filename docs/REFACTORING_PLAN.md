# Bot Refactoring Plan: SillyTavern-Style Bot with Dynamic Personas, Voice, and Memory

**Date**: 2026-01-10
**Last Updated**: 2026-03-14
**Status**: Draft
**Version**: 1.0

---

## 1. EXECUTIVE SUMMARY

### What We're Building

A **hybrid AI bot** that combines:
- **SillyTavern-like immersive roleplay** with dynamic character personalities
- **AI assistant utility** for task completion and information retrieval
- **Advanced voice capabilities** for character-specific voice conversations
- **Sophisticated memory systems** for context retention and user learning

### Why This Approach

**SillyTavern Success Factors**:
- Rich character definitions create engaging roleplay experiences
- World info/lorebook provides contextual knowledge
- Group chat with natural conversation flow
- Token budget management prevents context overflow

**AI Assistant Best Practices**:
- Context retention across multi-turn conversations
- User profile learning for personalization
- Web search integration for real-time information
- Memory systems (short-term, long-term, per-user)

**Our Bot's Unique Value**:
- Combines SillyTavern's roleplay immersion with ChatGPT-like assistant utility
- Character-specific voices via RVC (Real-time Voice Conversion)
- Real-time analytics dashboard (most bots lack this)
- Multi-persona system with intelligent routing
- Semantic lorebook matching for context-aware knowledge

### Key Differentiators from Standard Bots

| Feature | Standard ChatGPT Clone | SillyTavern | Our Bot (Proposed) |
|----------|----------------------|---------------|---------------------|
| **Roleplay** | ❌ Basic persona | ✅ Deep immersion | ✅ Rich + Dynamic |
| **Multi-Persona** | ❌ Single persona | ✅ Manual swap | ✅ Intelligent routing |
| **Voice** | ❌ Text-only | ❌ External only | ✅ TTS + RVC built-in |
| **Memory** | ⚠️ Conversation only | ⚠️ Simple history | ✅ Profiles + RAG + Semantic |
| **Web Search** | ✅ Built-in | ❌ Plugins required | ✅ Native integration |
| **Analytics** | ❌ None | ❌ Basic logs | ✅ Real-time dashboard |
| **Character Cards** | ❌ Hardcoded prompts | ✅ V2 format | ✅ V2 + <START> examples |
| **Mode Switching** | ❌ None | ❌ N/A | ✅ Roleplay ↔ Assistant |

---

## 2. CURRENT STATE ANALYSIS

### What Features Currently Exist

**Core Systems** (21 services across architecture):
1. ✅ **Multi-Persona System** - Router with intelligent character selection
2. ✅ **Behavior Engine** - Reactions, proactive engagement, mood tracking
3. ✅ **Voice Features** - TTS (Kokoro/Supertonic), STT (Whisper/Parakeet), RVC voice conversion
4. ✅ **Memory Systems** - User profiles, conversation history, RAG, long-term memory
5. ✅ **Web Search** - DuckDuckGo integration for real-time information
6. ✅ **Analytics Dashboard** - Real-time metrics via WebSocket (FastAPI + Chart.js)
7. ✅ **Character Cards** - JSON format with SillyTavern V2 fields
8. ✅ **Thinking Model** - Separate fast LLM for decisions (spam detection, routing)

**Extra Features** (beyond core roleplay + assistant):
9. ⚠️ **Music System** - YouTube playback with queue management (~300 lines)
10. ⚠️ **Reminders** - Time-based notification system (~200 lines)
11. ⚠️ **Notes** - Personal note-taking (~150 lines)
12. ⚠️ **Event Listeners** - Voice/game/activity reactions (~230 lines)
13. ⚠️ **Persona Evolution** - Character progression at milestones (~200 lines)
14. ⚠️ **Persona Relationships** - Character affinity tracking (~300 lines)
15. ⚠️ **Semantic Lorebook** - Vector-based world info (~400 lines)
16. ⚠️ **MCP Integration** - Model Context Protocol (archived, ~150 lines)
17. ⚠️ **Deprecated Services** - Old implementations (~500 lines)

**Total Extra Code**: ~2,680 lines across 19 files

### Bug Findings

#### Critical Bug #1: Truncated config.py
**Issue**: `config.py` file was corrupted to 24 lines, missing entire `Config` class definition
**Impact**: All configuration defaults → bot falls back to incorrect values
**Status**: ✅ Fixed (restored from git)

#### Critical Bug #2: Name Trigger Bypasses Channel Restrictions
**Location**: `cogs/chat/message_handler.py` line 364
**Issue**: Persona mentions work in ANY channel without checking `AMBIENT_CHANNELS` or `AUTO_REPLY_CHANNELS`

**Current Code**:
```python
if any(name in content_lower for name in bot_names):
    should_respond = True  # <-- NO CHANNEL CHECK
    response_reason = "name_trigger"
```

**Impact**: Bot responds to persona mentions in restricted channels, violating channel permissions

#### Bug #3: AUTO_REPLY_CHANNELS Not Implemented
**Location**: Defined in `config.py` but never used in `message_handler.py`
**Impact**: Configured channels don't work, configuration is ignored

#### Bug #4: AMBIENT_CHANNELS Empty Behavior
**Issue**: When `AMBIENT_CHANNELS = []`, code skips ambient checks
**Config Comment**: `# Channel IDs for ambient messages (empty = all channels)`
**Code Behavior**: `Config.AMBIENT_CHANNELS` evaluates to `False` (empty list is falsy), skips entire block
**Impact**: Confusing behavior - users expect empty to mean "all channels" but it means "none"

### Current Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Discord Bot Client                    │
│                 (discord.py)                          │
└────────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼────┐ ┌──▼──────┐ ┌──▼───────────┐
    │ ChatCog  │ │VoiceCog  │ │EventListeners  │
    │          │ │          │ │              │
    │Router    │ │TTS/STT   │ │Reactions      │
    │History   │ │RVC       │ │              │
    └────┬─────┘ └────┬─────┘ └───────────────┘
         │            │
    ┌────┴────┐ ┌────┴─────┐
    │Services  │ │Analytics  │
    │          │ │Dashboard │
    │21 total  │ │          │
    └───────────┘ └───────────┘
```

**Service Categories**:
- **Persona Services** (6): Router, Behavior, Evolution, Relationships, Lorebook, Loader
- **Memory Services** (4): RAG, Long-term, Profiles, Context Router
- **Voice Services** (4): TTS, RVC, STT, Streaming
- **Discord Services** (3): Music, Reminders, Notes
- **Core Services** (4): Factory, Metrics, Health, Rate Limiter

---

## 3. PROPOSED ARCHITECTURE

### Core Features to Keep

#### 1. Persona System ✅ KEEP
**What It Does**: Manages 10+ AI characters with intelligent routing
**Why Essential**: Core to roleplay experience, SillyTavern's primary feature
**Components**:
- PersonaRouter - Character selection logic
- PersonaSystem - Card loading and compilation
- BehaviorEngine - Reactions, proactive messages, mood
**No Changes Needed**: Already excellent

#### 2. Character Cards ✅ KEEP + ENHANCE
**What It Does**: JSON-based character definitions (SillyTavern V2 format)
**Why Essential**: Rich personality definitions enable immersive roleplay
**Enhancements Needed**:
- Add `<START>` example message support (teaches writing style)
- Add token budget warnings
**Current Fields**:
```json
{
  "spec": "chara_card_v2",
  "data": {
    "name": "Character Name",
    "description": "Core personality, background, world",
    "personality": "Detailed traits",
    "scenario": "Context and circumstances",
    "first_mes": "Initial greeting (CRITICAL for tone)",
    "mes_example": "", // ADD THIS
    "alternate_greetings": []
  }
}
```

#### 3. Voice Features ✅ KEEP
**What It Does**: TTS, STT, and RVC for character-specific voices
**Why Essential**: Immersive voice conversations, competitive advantage over text-only bots
**Components**:
- TTS Service (Kokoro/Supertonic)
- RVC Client (voice conversion)
- STT Listener (Whisper/Parakeet)
**No Changes Needed**: Already comprehensive

#### 4. Memory Systems ✅ KEEP
**What It Does**: User profiles, conversation history, RAG knowledge base
**Why Essential**: Context retention, personalization, long-term learning
**Components**:
- UserProfiles - User preferences and affection
- Conversation History - Multi-turn context
- RAG Service - Semantic knowledge retrieval
- Long-term Memory - Summarization
**No Changes Needed**: Already sophisticated

#### 5. Web Search ✅ KEEP
**What It Does**: Real-time web search integration for current information
**Why Essential**: Makes bot useful as an assistant, reduces hallucinations
**No Changes Needed**: Native integration already works

#### 6. Analytics Dashboard ✅ KEEP
**What It Does**: Real-time web monitoring with metrics and charts
**Why Essential**: Production monitoring, debugging, performance tracking
**No Changes Needed**: Cutting-edge feature already implemented

#### 7. Behavior Engine ✅ KEEP (SIMPLIFIED)
**What It Does**: Reactions, proactive engagement, mood tracking
**Why Essential**: Makes personas feel alive, proactive interactions
**Simplifications Needed**:
- Remove Persona Evolution dependencies
- Remove Persona Relationships dependencies
- Keep: Reactions, proactive messages, mood (optional)

### Features to Remove

#### 1. Music System ❌ REMOVE
**Files**: `cogs/music.py`, `services/discord/music.py`
**Lines**: ~300 lines
**Rationale**: Not chat/assistant related, separate feature domain
**Impact**: Voice channels work for TTS/STT, just no music playback
**Removal Strategy**:
- Delete Cog registration
- Delete service files
- Remove `/play`, `/skip`, `/stop`, `/pause`, `/queue`, `/volume`, `/shuffle`, `/loop` commands

#### 2. Reminders ❌ REMOVE
**Files**: `cogs/reminders.py`, `services/discord/reminders.py`
**Lines**: ~200 lines
**Rationale**: Utility feature, not core to persona/assistant functionality
**Impact**: Users lose reminder capability (minimal impact on chat experience)
**Removal Strategy**:
- Delete Cog registration
- Delete service file
- Remove background task

#### 3. Notes ❌ REMOVE
**Files**: `cogs/notes.py`, `services/discord/notes.py`
**Lines**: ~150 lines
**Rationale**: Personal productivity feature, not roleplay or assistant-related
**Impact**: Users can't save notes through bot
**Removal Strategy**:
- Delete Cog registration
- Delete service file
- Remove `/note`, `/notes`, `/delnote`, `/clearnotes` commands

#### 4. Event Listeners ❌ REMOVE
**Files**: `cogs/event_listeners.py`
**Lines**: ~230 lines
**Rationale**: Flavor feature (reactions to voice joins, game activity), not core
**Impact**: Bot feels less "alive" but chat unaffected
**Removal Strategy**:
- Delete Cog registration
- Remove natural reactions to Discord events

#### 5. Persona Evolution ❌ REMOVE
**Files**: `services/persona/evolution.py`
**Lines**: ~200 lines
**Rationale**: Advanced feature, adds complexity, characters already dynamic
**Impact**: Characters stay static, no milestone progression
**Removal Strategy**:
- Delete service file
- Remove from BehaviorEngine dependencies
- Remove evolution tracking from persona data

#### 6. Persona Relationships ❌ REMOVE
**Files**: `services/persona/relationships.py`
**Lines**: ~300 lines
**Rationale**: Not essential for single-user or focused roleplay, complexity
**Impact**: Characters don't build relationships with each other
**Removal Strategy**:
- Delete service file
- Remove from BehaviorEngine dependencies
- Remove banter logic from message handler

#### 7. MCP Integration ❌ DELETE
**Files**: `cogs/mcp_commands.py`, `services/mcp/`
**Lines**: ~150 lines
**Rationale**: Dead/archived code, not implemented
**Impact**: No impact (already inactive)
**Removal Strategy**:
- Delete Cog registration
- Delete entire `services/mcp/` directory

#### 8. Deprecated Services ❌ DELETE
**Files**: `services/deprecated/` (4+ files)
**Lines**: ~500 lines
**Rationale**: Old implementations, superseded by current code
**Files to Remove**:
- `whisper_stt.py`
- `transcription_fixer.py`
- `response_handler.py`
- `ai_decision_engine.py`

### New Features to Add

#### 1. <START> Example Message Support 🔧 ADD
**Location**: Character card JSON format
**Rationale**: Teaches LLM character's writing style, proven effective in SillyTavern
**Implementation**:
```json
{
  "mes_example": "<START>\nUser: Hello!\nChar: *waves enthusiastically* Welcome to my domain!\nUser: How are you?\nChar: Curious about mortals as always."
}
```
**Processing**:
```python
# In persona loader
def extract_examples(card_data):
    examples = card_data.get("mes_example", "")
    if "<START>" in examples:
        return parse_examples(examples)
    return []
```

#### 2. Token Budget Visual Warnings 🔧 ADD
**Location**: Context building in `cogs/chat/helpers.py`
**Rationale**: Prevents context overflow, matches SillyTavern feature
**Implementation**:
```python
def build_context(messages, system_prompt, max_tokens=4096):
    context = [system_prompt] + messages
    tokens = count_tokens(context)

    # Visual warnings
    if tokens > max_tokens * 0.5:
        logger.warning(f"⚠️ 50% token budget used: {tokens}/{max_tokens}")
    if tokens > max_tokens * 0.75:
        logger.warning(f"🔴 75% token budget used: {tokens}/{max_tokens}")
    if tokens > max_tokens * 0.9:
        logger.error(f"🔴 CRITICAL: {tokens}/{max_tokens} tokens used!")

    return truncate_context(context, max_tokens)
```

#### 3. Assistant Mode Toggle 🔧 ADD
**Location**: New command in `cogs/chat/commands.py`
**Rationale**: Allows switching between immersive roleplay and helpful assistant
**Implementation**:
```python
@app_commands.command(name="mode")
async def set_mode(interaction: discord.Interaction, mode: str):
    """Switch between roleplay and assistant modes."""
    modes = ["roleplay", "assistant", "hybrid"]
    if mode not in modes:
        await interaction.response.send_message(
            f"Available modes: {', '.join(modes)}",
            ephemeral=True
        )
        return

    # Update BehaviorEngine state
    behavior_engine.set_mode(mode)

    await interaction.response.send_message(
        f"🎭 Mode set to: {mode}\n"
        f"{'• Immersive roleplay - full character immersion' if mode == 'roleplay' else ''}"
        f"{'• Helpful assistant - direct, task-focused' if mode == 'assistant' else ''}"
        f"{'• Hybrid - context-aware blending' if mode == 'hybrid' else ''}",
        ephemeral=True
    )
```

**Mode Behavior**:
```python
class BehaviorEngine:
    def __init__(self):
        self.mode = "roleplay"  # default

    def set_mode(self, mode: str):
        self.mode = mode

    async def generate_response(self, message):
        if self.mode == "roleplay":
            system_prompt = get_character_system_prompt()
        elif self.mode == "assistant":
            system_prompt = get_assistant_system_prompt()
        elif self.mode == "hybrid":
            system_prompt = blend_prompts()

        return await llm.generate(system_prompt, message)
```

---

## 4. FEATURE MATRIX

| Feature | Current State | Decision | Rationale |
|----------|---------------|----------|-----------|
| **Persona System** | ✅ Implemented | KEEP | Core to roleplay, SillyTavern's primary feature |
| **Persona Router** | ✅ Implemented | KEEP | Intelligent character selection, excellent |
| **Behavior Engine** | ✅ Implemented | KEEP (SIMPLIFY) | Reactions/proactive make it feel alive |
| **Mood System** | ✅ Implemented | OPTION | Can simplify, not essential |
| **Curiosity** | ✅ Implemented | KEEP | Engaging, playful, good for assistant |
| **Voice (TTS)** | ✅ Implemented | KEEP | Immersive, competitive advantage |
| **Voice (STT)** | ✅ Implemented | KEEP | Voice input capability |
| **Voice (RVC)** | ✅ Implemented | KEEP | Character-specific voices, unique |
| **Memory (Profiles)** | ✅ Implemented | KEEP | User learning, personalization |
| **Memory (History)** | ✅ Implemented | KEEP | Context retention, essential |
| **Memory (RAG)** | ✅ Implemented | KEEP | Knowledge base, reduces hallucinations |
| **Memory (Long-term)** | ✅ Implemented | KEEP | Summarization, persistent memory |
| **Web Search** | ✅ Implemented | KEEP | Makes bot useful as assistant |
| **Analytics Dashboard** | ✅ Implemented | KEEP | Production monitoring, essential |
| **Character Cards** | ✅ Implemented | KEEP + ENHANCE | Rich definitions, add <START> examples |
| **Scenario/First Message** | ✅ Implemented | KEEP | Sets tone and context |
| **Alternative Greetings** | ✅ Implemented | KEEP | Variety, replay value |
| **Token Warnings** | ❌ None | ADD | Prevents context overflow |
| **Assistant Mode Toggle** | ❌ None | ADD | Enables roleplay ↔ assistant switching |
| **<START> Examples** | ❌ None | ADD | Teaches writing style |
| **Semantic Lorebook** | ✅ Implemented | OPTION | Advanced, can keep or simplify |
| **Music** | ✅ Implemented | REMOVE | Not chat/assistant related |
| **Reminders** | ✅ Implemented | REMOVE | Utility feature, not core |
| **Notes** | ✅ Implemented | REMOVE | Personal productivity, not roleplay |
| **Event Listeners** | ✅ Implemented | REMOVE | Flavor, not core to chat |
| **Persona Evolution** | ✅ Implemented | REMOVE | Complexity without value |
| **Persona Relationships** | ✅ Implemented | REMOVE | Not essential for assistant |
| **MCP Integration** | ⚠️ Archived | DELETE | Dead code |
| **Deprecated Services** | ✅ Exists | DELETE | Cleanup, old code |

---

## 5. IMPLEMENTATION PLAN

### Phase 1: Feature Removal (Week 1)
**Goal**: Remove unnecessary features, simplify codebase

**Tasks**:
1. Delete `cogs/music.py` and `services/discord/music.py` (~300 lines)
2. Delete `cogs/reminders.py` and `services/discord/reminders.py` (~200 lines)
3. Delete `cogs/notes.py` and `services/discord/notes.py` (~150 lines)
4. Delete `cogs/event_listeners.py` (~230 lines)
5. Delete `services/persona/evolution.py` (~200 lines)
6. Delete `services/persona/relationships.py` (~300 lines)
7. Delete `cogs/mcp_commands.py` and `services/mcp/` (~150 lines)
8. Delete `services/deprecated/` directory (~500 lines)

**Total Removal**: ~2,030 lines

**Testing After Removal**:
- Verify bot starts without errors
- Test core chat functionality
- Test voice features
- Test persona switching

### Phase 2: Bug Fixes (Week 1-2)
**Goal**: Fix channel restrictions and configuration

**Tasks**:
1. Add `NAME_TRIGGER_CHANNELS` to `config.py`:
```python
# Name Trigger Channels (channels where mentioning persona names works)
# Empty = allow all channels (default)
# Example: NAME_TRIGGER_CHANNELS=123456789,987654321
NAME_TRIGGER_CHANNELS: List[int] = [
    int(x.strip())
    for x in os.getenv("NAME_TRIGGER_CHANNELS", "").split(",")
    if x.strip()
]
```

2. Implement channel check in `message_handler.py` (line 364):
```python
if any(name in content_lower for name in bot_names):
    # Check channel restrictions
    if Config.NAME_TRIGGER_CHANNELS:
        if message.channel.id in Config.NAME_TRIGGER_CHANNELS:
            should_respond = True
            response_reason = "name_trigger"
        else:
            logger.debug(
                f"Name trigger blocked - channel {message.channel.id} not in NAME_TRIGGER_CHANNELS"
            )
    else:
        # No restriction, allow all channels
        should_respond = True
        response_reason = "name_trigger"
```

3. Implement `AUTO_REPLY_CHANNELS` filtering in `message_handler.py`:
```python
# Add near line 546 (ambient check)
if not should_respond and Config.AUTO_REPLY_ENABLED:
    if Config.AUTO_REPLY_CHANNELS:
        if message.channel.id in Config.AUTO_REPLY_CHANNELS:
            if random.random() < Config.GLOBAL_RESPONSE_CHANCE:
                should_respond = True
                response_reason = "auto_reply_channel"
    else:
        # No restriction, allow all channels
        if random.random() < Config.GLOBAL_RESPONSE_CHANCE:
            should_respond = True
            response_reason = "auto_reply_global"
```

4. Fix `AMBIENT_CHANNELS` empty behavior:
```python
# Change from:
if Config.AMBIENT_CHANNELS and not is_persona_message:
    if message.channel.id in Config.AMBIENT_CHANNELS:

# To:
if not is_persona_message:
    if not Config.AMBIENT_CHANNELS or message.channel.id in Config.AMBIENT_CHANNELS:
        # Empty list means all channels
```

### Phase 3: Enhancements (Week 2-3)
**Goal**: Add SillyTavern-inspired features

**Tasks**:
1. Add `<START>` example message support:
   - Update `PersonaSystem.load_character()` to parse examples
   - Add examples to context building
   - Test with example characters

2. Add token budget warnings:
   - Implement `count_tokens()` function
   - Add visual warnings in `build_context()`
   - Test with various context sizes

3. Add `/mode` command:
   - Create command in `cogs/chat/commands.py`
   - Implement mode switching in `BehaviorEngine`
   - Update context building per mode

4. Update documentation:
   - Document character card format with `<START>` examples
   - Explain mode switching behavior
   - Update config variable documentation

### Phase 4: Testing and Validation (Week 4)
**Goal**: Ensure all changes work correctly

**Tasks**:
1. Unit tests:
   - Test channel restriction logic
   - Test token counting
   - Test mode switching

2. Integration tests:
   - Test full conversation flow with each persona
   - Test voice features
   - Test memory systems

3. User acceptance testing:
   - Deploy to staging server
   - Gather feedback on mode switching
   - Verify character behavior consistency

4. Performance testing:
   - Measure response latency (<5ms target)
   - Check memory usage
   - Verify dashboard metrics

---

## 6. TECHNICAL DETAILS

### Character Card Format with <START> Examples

**Standard Format**:
```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Character Name",
    "display_name": "Display Name",
    "description": "Detailed description for AI",
    "personality": "Core traits, quirks, opinions",
    "scenario": "Context and circumstances for dialogue",
    "first_mes": "Initial greeting message (sets tone)",
    "mes_example": "<START>\nUser: What's your name?\nChar: My name is X.\nUser: Tell me about yourself.\nChar: *describes self*",
    "alternate_greetings": ["Alternative 1", "Alternative 2"],
    "creator_notes": "Usage tips and guidelines",
    "system_prompt": "",
    "post_history_instructions": "",
    "tags": ["tag1", "tag2"],
    "creator": "Author Name",
    "character_version": "1.0"
  }
}
```

**Parsing <START> Examples**:
```python
def parse_examples(mes_example: str) -> list:
    """Parse <START> tagged examples from character card."""
    examples = []

    # Split by <START> tags
    pattern = r'<START>(.*?)(?=<START>|$)'
    matches = re.findall(pattern, mes_example, re.DOTALL)

    for match in matches:
        example_text = match.strip()

        # Parse user/character dialogue
        lines = example_text.split('\n')
        dialogue = []

        for line in lines:
            line = line.strip()
            if line.startswith('User:'):
                dialogue.append({'role': 'user', 'content': line[5:].strip()})
            elif line.startswith('Char:'):
                dialogue.append({'role': 'assistant', 'content': line[5:].strip()})
            elif line.startswith('*'):
                # Action/narration
                dialogue.append({'role': 'system', 'content': line})

        if dialogue:
            examples.append(dialogue)

    return examples

# Context Building with Examples
def build_context(character, examples, conversation_history):
    messages = []

    # System prompt
    messages.append({
        'role': 'system',
        'content': character.description + '\n\n' + character.personality
    })

    # Add examples
    for example in examples:
        messages.extend(example)

    # Add conversation history
    messages.extend(conversation_history)

    return messages
```

### Channel Restriction Implementation

**Full Implementation**:
```python
# In cogs/chat/message_handler.py, check_and_handle_message()

# 3. Name trigger (ALWAYS respond) - WITH CHANNEL CHECK
if not should_respond:
    # Build list of all recognizable names
    bot_names = [self.cog.bot.user.name.lower(), "bot", "computer", "assistant"]

    # Add persona names
    for p in self.cog.persona_router.get_all_personas():
        p_name = p.character.display_name
        if p_name:
            bot_names.append(p_name.lower())

    # Check if any character name is mentioned
    if any(name in content_lower for name in bot_names):
        # NEW: Check channel restrictions
        allowed_channels = Config.NAME_TRIGGER_CHANNELS

        if allowed_channels and message.channel.id not in allowed_channels:
            logger.debug(
                f"Name trigger blocked - channel {message.channel.id} not in NAME_TRIGGER_CHANNELS"
            )
        else:
            should_respond = True
            response_reason = "name_trigger"
            suggested_style = "direct"
```

**Configuration** (.env.example):
```bash
# Name Trigger Channels (comma-separated channel IDs)
# Empty = allow persona name mentions in all channels (default)
# Set specific channels to restrict where bot responds to persona mentions
NAME_TRIGGER_CHANNELS=

# Auto Reply Channels (comma-separated channel IDs)
# Empty = auto-reply in all channels
# Set specific channels to enable ambient/proactive responses
AUTO_REPLY_CHANNELS=

# Ambient Channels (comma-separated channel IDs)
# Empty = ambient mode in all channels (FIXED from current behavior)
AMBIENT_CHANNELS=
```

### Assistant Mode Switching Logic

**Implementation**:
```python
# In services/persona/behavior.py

class BehaviorEngine:
    """Behavior engine with mode switching support."""

    MODES = {
        'roleplay': {
            'system_prompt_prefix': 'character_only',
            'response_style': 'immersive',
            'use_examples': True,
            'use_lorebook': True
        },
        'assistant': {
            'system_prompt_prefix': 'helpful_assistant',
            'response_style': 'direct',
            'use_examples': False,
            'use_lorebook': False
        },
        'hybrid': {
            'system_prompt_prefix': 'blend_character_assistant',
            'response_style': 'adaptive',
            'use_examples': True,
            'use_lorebook': True
        }
    }

    def __init__(self):
        self.mode = 'roleplay'  # Default mode
        self.states = {}  # channel_id -> BehaviorState

    def set_mode(self, mode: str) -> bool:
        """Switch behavior mode."""
        if mode not in self.MODES:
            logger.warning(f"Invalid mode: {mode}")
            return False

        old_mode = self.mode
        self.mode = mode

        logger.info(
            f"Behavior mode switched: {old_mode} -> {mode}"
        )

        # Update existing states with new mode
        for channel_id, state in self.states.items():
            state.mode = mode

        return True

    async def build_system_prompt(self, persona, channel_id: int) -> str:
        """Build system prompt based on current mode."""
        mode_config = self.MODES[self.mode]

        if self.mode == 'roleplay':
            # Full character immersion
            prompt = f"{persona.description}\n\n"
            prompt += f"Personality: {persona.personality}\n"
            prompt += f"Scenario: {persona.scenario}\n"

            # Add examples
            if mode_config['use_examples'] and persona.examples:
                prompt += "\n\nExamples of how you speak:\n"
                for example in persona.examples:
                    prompt += f"{example}\n"

            # Add lorebook
            if mode_config['use_lorebook'] and self.lorebook:
                lore_entries = await self.lorebook.get_entries(channel_id)
                if lore_entries:
                    prompt += f"\n\nWorld Info:\n{lore_entries}\n"

        elif self.mode == 'assistant':
            # Helpful assistant, less roleplay
            prompt = """You are a helpful AI assistant.

            Be direct, concise, and task-focused.
            Minimize roleplay and character immersion.
            Provide accurate, factual information.

            If asked about a specific persona, briefly acknowledge them
            but focus on being helpful."""

        elif self.mode == 'hybrid':
            # Blend character and assistant
            prompt = f"""You are {persona.name}.

            {persona.description}

            {persona.personality}

            Balance being in-character with being helpful.
            Stay true to your personality, but prioritize assisting the user.
            Use examples from your character's speaking style."""

        return prompt
```

### Token Budget Monitoring

**Implementation**:
```python
# In utils/token_counter.py (new file)

import tiktoken  # or use model-specific tokenizer

def count_tokens(messages: list) -> int:
    """Count tokens in message list."""
    encoding = tiktoken.encoding_for_model("gpt-4")  # Or appropriate model

    total_tokens = 0
    for message in messages:
        if isinstance(message, str):
            total_tokens += len(encoding.encode(message))
        elif isinstance(message, dict):
            content = message.get('content', '')
            total_tokens += len(encoding.encode(content))

    return total_tokens

def check_token_budget(
    tokens: int,
    max_tokens: int,
    context_name: str = "Context"
) -> dict:
    """Check token budget and return warnings."""
    warnings = []

    usage_pct = tokens / max_tokens

    if usage_pct > 0.5:
        warnings.append({
            'level': 'warning',
            'message': f"⚠️ 50% token budget used in {context_name}: {tokens}/{max_tokens} ({usage_pct:.1%})",
            'usage_pct': usage_pct
        })

    if usage_pct > 0.75:
        warnings.append({
            'level': 'error',
            'message': f"🔴 75% token budget used in {context_name}: {tokens}/{max_tokens} ({usage_pct:.1%})",
            'usage_pct': usage_pct
        })

    if usage_pct > 0.9:
        warnings.append({
            'level': 'critical',
            'message': f"🔴 CRITICAL: {tokens}/{max_tokens} tokens used in {context_name} ({usage_pct:.1%})!",
            'usage_pct': usage_pct
        })

    return {
        'tokens': tokens,
        'max_tokens': max_tokens,
        'usage_pct': usage_pct,
        'warnings': warnings
    }
```

**Usage in Chat System**:
```python
# In cogs/chat/helpers.py

from utils.token_counter import count_tokens, check_token_budget

def build_conversation_context(
    messages: list,
    system_prompt: str,
    persona,
    max_tokens: int = 4096
) -> dict:
    """Build conversation context with token budget monitoring."""

    # Build full context
    context_messages = [system_prompt] + messages

    # Count tokens
    token_count = count_tokens(context_messages)

    # Check budget
    budget = check_token_budget(
        token_count,
        max_tokens,
        context_name=f"{persona.name} chat"
    )

    # Log warnings
    for warning in budget['warnings']:
        level = warning['level']
        logger.log(logging.WARNING if level == 'warning' else logging.ERROR, warning['message'])

    # Truncate if necessary
    if budget['usage_pct'] > 1.0:
        # Need to truncate
        keep_pct = 0.9  # Keep 90% of max
        max_allowed = int(max_tokens * keep_pct)
        context_messages = truncate_to_tokens(context_messages, max_allowed)

        logger.warning(
            f"Truncated context to {max_allowed} tokens ({keep_pct:.0%})"
        )

    return {
        'messages': context_messages,
        'token_count': token_count,
        'max_tokens': max_tokens,
        'usage_pct': budget['usage_pct']
    }
```

---

## 7. EXPECTED OUTCOMES

### What Bot Will Do After Changes

**Core Roleplay Capabilities** (SillyTavern-like):
- ✅ Rich character definitions with scenario, personality, examples
- ✅ Multiple dynamic personas with intelligent routing
- ✅ Character-specific voices via RVC
- ✅ Natural conversation flow with behavior engine
- ✅ World info/lorebook for contextual knowledge
- ✅ Unique avatars via webhook spoofing

**AI Assistant Utility**:
- ✅ Web search for real-time information
- ✅ User profile learning and personalization
- ✅ Knowledge base (RAG) for accuracy
- ✅ Task-focused mode switch when needed
- ✅ Direct, helpful answers in assistant mode

**Playful + Useful Balance**:
- **Roleplay Mode**: Full character immersion, playful, in-character
- **Assistant Mode**: Helpful, direct answers, less roleplay
- **Hybrid Mode**: Context-aware blending, adaptive responses
- **Mode Switching**: User-controlled via `/mode` command

### User Experience Improvements

1. **Clearer Intent**:
   - Users know which mode is active
   - Roleplay vs utility clearly separated
   - Less confusion about bot's purpose

2. **Better Character Quality**:
   - `<START>` examples teach writing style
   - Token warnings prevent context overflow
   - Consistent behavior across conversations

3. **Controlled Behavior**:
   - Channel restrictions work correctly
   - Auto-reply only in configured channels
   - Persona mentions respect channel limits

4. **Simpler Configuration**:
   - Fewer features to configure
   - Clearer channel restriction options
   - Mode switching for quick changes

### Performance Improvements

1. **Reduced Codebase**:
   - ~2,030 lines of unused code removed
   - Faster startup time
   - Simpler maintenance

2. **Better Performance**:
   - Token budget monitoring prevents context overflow
   - Simplified behavior engine (no evolution/relationships)
   - Fewer background services running

3. **Cleaner Architecture**:
   - Clear separation: roleplay vs assistant
   - Focused service boundaries
   - Easier to extend

---

## 8. MIGRATION GUIDE

### Changes for Existing Users

#### Configuration Changes

**New Environment Variables** (.env):
```bash
# NEW: Name Trigger Channels
# Channels where persona name mentions work
NAME_TRIGGER_CHANNELS=

# EXISTING (FIXED): Auto Reply Channels
# Now properly implemented in message handler
AUTO_REPLY_CHANNELS=

# EXISTING (FIXED): Ambient Channels
# Now empty = all channels (not none)
AMBIENT_CHANNELS=
```

#### Character Card Updates

**Adding <START> Examples**:
```json
{
  "data": {
    "name": "Dagoth Ur",
    "mes_example": "<START>\nUser: Greetings, mortal.\nChar: Welcome to my domain. What brings you here?",
    "mes_example": "<START>\nUser: What's your favorite game?\nChar: Morrowind, obviously. The only game that matters."
  }
}
```

**Migration Script** (optional):
```python
# scripts/migrate_character_examples.py

import json
from pathlib import Path

def add_example_fields(character_file: Path):
    """Add mes_example field to existing character cards."""

    with open(character_file, 'r') as f:
        card = json.load(f)

    if 'mes_example' not in card['data']:
        card['data']['mes_example'] = ""

        with open(character_file, 'w') as f:
            json.dump(card, f, indent=2)

        print(f"✅ Added mes_example field to {character_file.name}")

# Run on all characters
char_dir = Path("prompts/characters/")
for card_file in char_dir.glob("*.json"):
    add_example_fields(card_file)
```

#### Command Changes

**New Commands**:
- `/mode [roleplay|assistant|hybrid]` - Switch behavior mode

**Removed Commands**:
- `/play`, `/skip`, `/stop`, `/pause`, `/resume`, `/queue`, `/volume`, `/shuffle`, `/loop`, `/clear_queue`, `/remove` (Music)
- `/remind`, `/reminders`, `/cancel_reminder`, `/clear_reminders` (Reminders)
- `/note`, `/notes`, `/delnote`, `/clearnotes` (Notes)

#### Behavior Changes

**Persona Mention Restrictions**:
- Previously: Responded in all channels when persona name mentioned
- Now: Respects `NAME_TRIGGER_CHANNELS` configuration

**Ambient Channel Behavior**:
- Previously: Empty `AMBIENT_CHANNELS` = no ambient mode
- Now: Empty `AMBIENT_CHANNELS` = all channels

**Mode Switching**:
- Previously: Single roleplay mode only
- Now: Three modes (roleplay, assistant, hybrid) with `/mode` command

### How to Update Character Cards

**Step 1: Open Character File**
```bash
# Example: Edit Dagoth Ur
vim prompts/characters/dagoth_ur.json
```

**Step 2: Add mes_example Field**
```json
{
  "spec": "chara_card_v2",
  "data": {
    "name": "Dagoth Ur",
    // ... existing fields ...

    // ADD THIS FIELD:
    "mes_example": "<START>\nUser: Hello!\nChar: Welcome, mortal."
  }
}
```

**Step 3: Test Character**
```python
# Reload character in Discord
/reload_characters

# Test the character
"Dagoth, tell me about yourself"
```

**Tips for Good Examples**:
- Show 3-5 example conversations
- Include user questions and character responses
- Demonstrate speaking style (tone, quirks, vocabulary)
- Include narration/actions in asterisks (*)
- Keep examples concise (2-3 lines each)

### Deployment Checklist

**Pre-Deployment**:
- [ ] Backup current configuration and character files
- [ ] Review and update .env with new variables
- [ ] Test changes on development/staging server
- [ ] Update user documentation

**Deployment**:
- [ ] Pull latest code
- [ ] Run dependency sync: `uv sync`
- [ ] Restart bot service
- [ ] Monitor logs for errors
- [ ] Verify all personas load correctly

**Post-Deployment**:
- [ ] Test persona mentions in various channels
- [ ] Test `/mode` command switching
- [ ] Verify voice features work
- [ ] Check analytics dashboard metrics
- [ ] Gather user feedback

---

## 9. CONCLUSION

This refactoring plan transforms the bot from a **feature-rich but unfocused** system into a **specialized hybrid AI assistant**:

- **SillyTavern-like roleplay**: Rich characters, dynamic personas, immersive experience
- **AI assistant utility**: Web search, memory, task-focused mode
- **Advanced features**: Voice with RVC, analytics dashboard, semantic lorebook
- **Simplified codebase**: ~2,030 lines removed, focused architecture

The bot will be **production-ready** with clear separation between roleplay and assistant capabilities, allowing users to switch modes based on their needs while maintaining the immersive character experience that makes SillyTavern successful.

---

**Next Steps**:
1. Review and approve this plan
2. Begin Phase 1 (feature removal)
3. Implement bug fixes (Phase 2)
4. Add enhancements (Phase 3)
5. Deploy and monitor (Phase 4)

**Questions or concerns? Discuss in project planning session.**

---

## Discord Migration Closeout Evidence (2026-03-14)

**Note**: This document is a historical refactoring plan. The Discord migration closeout
has been completed under strict quarantine policy. Legacy Discord surfaces remain
opt-in only (`DISCORD_LEGACY_*` flags) while the maintained Discord path is now
runtime-first.

```bash
# Test command
$ uv run pytest tests/unit/test_discord_*.py -q --tb=no

# Results summary
90 passed, 1 skipped in 1.35s

# Verification: Discord maintained path closed under quarantine criteria
# - Runtime-first boundary enforced (no legacy bypass in maintained path)
# - DISCORD_LEGACY_* flags remain opt-in only
# - Unit tests verify runtime-owned decision + response paths

# Governance verification
$ uv run pytest tests/unit/test_docs_governance.py -q
1 passed

$ uv run python scripts/check_docs_governance.py
FEATURES.md approved status labels: PASSED
FEATURES.md legacy legend removed: PASSED
STATUS.md canonical reference: PASSED
reports historical markers: PASSED
```

### 2026-03-15: Phase 3 Adapter-Contract Adoption Seed (Discord Facts)

Completed:

- adopted `core.interfaces.PlatformFacts` in maintained Discord on-message fact
  extraction (`MessageHandler`) as the normalized adapter fact carrier
- kept runtime ownership unchanged: adapter emits facts only, runtime still owns
  response decision policy
- added focused assertion coverage for stable fact fields
  (`channel_id`, `author_id`, `message_id`) in the maintained Discord runtime
  path tests

Result:

- Phase 3 adapter-contract adoption has started with non-breaking uptake in the
  maintained Discord path
- Discord fact extraction is now structurally aligned with the Adapter SDK
  contract while preserving existing runtime-first behavior

### 2026-03-15: Phase 3 Adapter-Contract Adoption (Web Event Ingress)

Completed:

- adopted `core.interfaces.PlatformFacts` in maintained web event ingress for:
  - HTTP `/api/runtime/event`
  - websocket `send_event` handling
- preserved existing runtime context flags by merging them on top of normalized
  web platform-fact flags
- added focused test assertions proving web runtime events now carry normalized
  fact flags (`is_direct_mention`, `author_is_bot`) alongside existing
  auth/client-scope flags

Result:

- maintained Discord and web adapters now share the same normalized adapter-fact
  carrier pattern before runtime decision handling
- Phase 3 adapter-contract uptake advanced without changing runtime policy
  ownership or breaking existing surfaces

### 2026-03-15: Phase 3 Shared Fact-Flag Helper Slice

Completed:

- introduced shared helper
  `core.interfaces.runtime_flags_from_platform_facts(...)`
- rewired maintained Discord and web ingress paths to use the shared helper
  instead of duplicating local fact-to-flag merge logic
- added contract tests verifying helper behavior for:
  - baseline fact flag serialization
  - extra flag merge precedence

Result:

- adapter contract adoption now has a shared conversion primitive across
  maintained surfaces
- reduced adapter duplication while preserving runtime-first ownership and
  existing behavior

### 2026-03-15: Phase 3 Shared Event-Builder Helper Slice

Completed:

- introduced shared helper
  `core.interfaces.build_runtime_event_from_facts(...)`
- rewired maintained web ingress event construction to use the shared helper for:
  - HTTP `/api/runtime/event`
  - websocket `send_event`
- added contract tests for shared event builder behavior:
  - default chat event construction
  - slash-command promotion to `command` kind/type
  - extra flag merge behavior

Result:

- Phase 3 adapter-contract adoption now covers both shared fact serialization
  and shared ingress event construction on maintained web paths
- reduced web adapter duplication while preserving runtime policy ownership and
  existing behavior

### 2026-03-15: Phase 3 Shared Event-Builder Adoption (Discord Chat)

Completed:

- rewired maintained Discord chat runtime-event construction to use
  `core.interfaces.build_runtime_event_from_facts(...)` in both maintained
  runtime response handlers:
  - slash/runtime chat response flow
  - on-message/runtime chat response flow
- preserved runtime metadata semantics (`response_reason`, `suggested_style`,
  and Discord surface markers) while removing inline Discord event construction
  duplication

Result:

- maintained Discord and maintained web ingress now share a single event
  construction primitive for adapter facts -> runtime events
- adapter-side duplication is reduced without changing runtime ownership of
  response policy

### 2026-03-15: Phase 3 Shared Event-Builder Adoption (CLI)

Completed:

- rewired maintained CLI runtime-event construction to use
  `core.interfaces.build_runtime_event_from_facts(...)` in:
  - interactive CLI message/command event routing (`adapters/cli/__main__.py`)
  - CLI play-mode LLM planner prompt event routing (`adapters/cli/play.py`)
- preserved existing CLI metadata semantics (profile flag forwarding and
  play-planner source/tool annotations) while removing inline event
  construction duplication

Result:

- maintained Discord, web, and CLI now converge on the same normalized adapter
  facts -> runtime event construction primitive
- adapter surfaces stay thinner while runtime ownership boundaries remain
  unchanged

### 2026-03-15: Phase 3 Runtime Context-Cache and API Controls

Completed:

- added runtime-owned session context-cache entries with TTL and bounded global
  / per-session limits in `GestaltRuntime`
- integrated cache use into maintained chat flows (`handle_event` + streaming)
  with `context_cache` trace spans (`cache_hit`, `cache_reason`,
  `tokens_saved_estimate`)
- added runtime snapshot/mutation APIs:
  - `get_context_cache_snapshot(...)`
  - `reset_context_cache(...)`
- exposed context-cache controls on maintained transports:
  - web: `POST /api/runtime/context`, `POST /api/runtime/context/reset`
  - stdio: `get_context`, `reset_context`
- added runtime operator commands:
  - `/context`
  - `/context reset`

Result:

- runtime now owns context-window reuse and cache lifecycle instead of leaving
  context optimization as adapter-side behavior
- maintained web and stdio surfaces now have parity for context-cache
  introspection and reset workflows
