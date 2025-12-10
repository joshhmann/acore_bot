# Persona/Character System

## Overview

The persona system is the core identity layer of the bot, providing character-driven AI personalities through a two-layer architecture: **Frameworks** (behavioral patterns) + **Characters** (identities). This system enables multi-character conversations with unique personalities, relationships, and autonomous behaviors.

## Architecture: Two-Layer System

### Layer 1: Frameworks (Behavioral Templates)

Frameworks define **HOW** a character behaves (behavioral patterns, decision-making rules, tool usage).

**Location**: `/root/acore_bot/prompts/frameworks/*.json`

**Available Frameworks**:
- `assistant.json` - Professional helper (ChatGPT-like)
- `caring.json` - Empathetic and supportive
- `chaotic.json` - Unpredictable and energetic
- `neuro.json` - Entertainment-focused, short responses

**Framework Structure** (see `/root/acore_bot/services/persona/system.py:15-27`):
```python
@dataclass
class Framework:
    framework_id: str                      # e.g. "neuro"
    name: str                              # Display name
    purpose: str                           # "Entertainment", "Assistant", etc.
    behavioral_patterns: Dict[str, Any]    # How to behave
    tool_requirements: Dict[str, List[str]] # Required/optional tools
    decision_making: Dict[str, Any]        # When to respond, when to use tools
    context_requirements: Dict[str, Any]   # What context is needed
    interaction_style: Dict[str, Any]      # Tone, formality, length
    anti_hallucination: Dict[str, Any]     # Fact-checking rules
    prompt_template: str                   # Injected into system prompt
```

**Example - Neuro Framework** (`/root/acore_bot/prompts/frameworks/neuro.json`):
```json
{
  "framework_id": "neuro",
  "name": "Neuro-sama Framework",
  "purpose": "Entertainment",
  "prompt_template": "Be funny and cute.\n\n=== RESPONSE LENGTH ===\nKeep responses SHORT (1-3 sentences)..."
}
```

### Layer 2: Characters (Identities)

Characters define **WHO** the bot is (personality, backstory, opinions, voice).

**Location**: `/root/acore_bot/prompts/characters/*.json` (or `.png` for V2 cards)

**Character Card Format**: Character Card V2 Spec (SillyTavern compatible)

**Character Structure** (see `/root/acore_bot/services/persona/system.py:29-52`):
```python
@dataclass
class Character:
    character_id: str                   # Filename stem
    display_name: str                   # "Dagoth Ur", "Scav", etc.

    # Legacy structured fields (custom format)
    identity: Dict[str, Any]            # Who, core traits, description
    knowledge_domain: Dict[str, Any]    # Expertise areas
    opinions: Dict[str, Any]            # Loves, hates, hot takes
    voice_and_tone: Dict[str, Any]      # Speaking style
    quirks: Dict[str, Any]              # Catchphrases, habits

    # V2 Character Card fields (SillyTavern standard)
    description: str                    # Character description
    scenario: str                       # Current situation
    first_message: str                  # Greeting
    mes_example: str                    # Example dialogue
    alternate_greetings: List[str]      # Alternative greetings
    creator_notes: str                  # Author notes
    tags: List[str]                     # Categorization
    system_prompt_override: str         # Embedded system prompt

    # Visuals
    avatar_url: Optional[str]           # Profile picture URL
```

**Example Character - Dagoth Ur** (`/root/acore_bot/prompts/characters/dagoth_ur.json`):
```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Dagoth Ur",
    "description": "Who: Dagoth Ur, immortal god-king of Red Mountain...",
    "personality": "Core Traits:\n- Divine superiority complex\n- Grandiose and dramatic...",
    "scenario": "Chatting on Discord.",
    "first_mes": "Welcome, mortal.",
    "alternate_greetings": [
      "How delightfully disappointing.",
      "Even as an AI, I remain superior."
    ],
    "avatar_url": "https://i.redd.it/snhnfjh9whga1.png"
  }
}
```

## Active Personas (9 Characters)

**Configuration**: `/root/acore_bot/config.py:79-89`

```python
ACTIVE_PERSONAS = [
    "dagoth_ur.json",    # Grandiose Elder Scrolls god-king
    "scav.json",         # Drunk Tarkov scavenger
    "zenos.json",        # FFXIV antagonist
    "maury.json",        # Talk show host
    "hal9000.json",      # 2001: A Space Odyssey AI
    "toad.json",         # Mario's panicky mushroom
    "jc.json",           # Deus Ex protagonist
    "toadette.json",     # Toad's counterpart
    "joseph_stalin.json" # Historical figure
]
```

All character files are stored in `/root/acore_bot/prompts/characters/`.

## Core Services

### 1. PersonaSystem - Loader and Compiler

**Location**: `/root/acore_bot/services/persona/system.py`

**Responsibilities**:
- Load frameworks from JSON
- Load characters from JSON or PNG (V2 cards with embedded metadata)
- Compile Framework + Character into a complete system prompt
- Cache compiled personas
- Save compiled versions to disk

**Key Methods**:

```python
class PersonaSystem:
    def load_framework(framework_id: str) -> Optional[Framework]
    def load_character(character_id: str) -> Optional[Character]
    def compile_persona(character_id: str, framework_id: str = None) -> Optional[CompiledPersona]
    def _build_system_prompt(character: Character, framework: Framework) -> str
```

**Compilation Process** (`system.py:261-366`):

1. Load character from `characters/` directory
2. Load framework (optional - can use character card alone)
3. Build system prompt by combining:
   - Character description
   - Personality traits
   - Scenario context
   - Example dialogue
   - Framework behavioral instructions
4. Extract tool requirements from framework
5. Create `CompiledPersona` object
6. Cache in memory and save to `/root/acore_bot/prompts/compiled/`

**Compiled Persona Structure** (`system.py:54-63`):
```python
@dataclass
class CompiledPersona:
    persona_id: str              # "dagoth_ur_neuro"
    character: Character         # Character object
    framework: Framework         # Framework object
    system_prompt: str           # Complete prompt for LLM
    tools_required: List[str]    # Tools this persona needs
    config: Dict[str, Any]       # Combined configuration
```

**Example Compiled Persona** (`/root/acore_bot/prompts/compiled/dagoth_ur_neuro.json`):
```json
{
  "persona_id": "dagoth_ur_neuro",
  "character_id": "dagoth_ur",
  "framework_id": "neuro",
  "system_prompt": "You are Dagoth Ur.\n...[full prompt]...",
  "tools_required": [],
  "config": {
    "character": "dagoth_ur",
    "framework": "neuro"
  }
}
```

### 2. PersonaRouter - Multi-Character Selection

**Location**: `/root/acore_bot/services/persona/router.py`

**Purpose**: Manages multiple active personas and intelligently routes messages to the most appropriate character.

**Selection Algorithm** (`router.py:82-138`):

```
Priority Order:
1. Explicit Mention   - "Hey Dagoth, ..." → Dagoth Ur responds
2. First Name Match   - "Dagoth is cool" → Dagoth Ur responds
3. Sticky Context     - Last responder in channel (5min window)
4. Random Selection   - First message or no context
```

**Implementation Details**:

```python
class PersonaRouter:
    def __init__(self, profiles_dir: str)
    async def initialize()  # Load all ACTIVE_PERSONAS

    def select_persona(message_content: str, channel_id: int) -> Optional[CompiledPersona]
        # Phase 1: Full name match (sorted by length to prefer "Dagoth Ur" over "Dagoth")
        # Phase 2: First name match (min 3 chars to avoid false positives)
        # Phase 3: Sticky - return last responder if < 5 minutes ago
        # Phase 4: Random selection

    def record_response(channel_id: int, persona: CompiledPersona)
        # Track who responded for sticky routing

    def get_persona_by_name(name: str) -> Optional[CompiledPersona]
        # Fuzzy search by name
```

**Sticky Routing** (`router.py:123-131`):
- Tracks last responder per channel
- 5-minute timeout window
- Prevents persona-hopping mid-conversation
- Resets after silence

### 3. BehaviorEngine - Unified AI Brain

**Location**: `/root/acore_bot/services/persona/behavior.py` (361 lines)

**Revolutionary Consolidation**: Replaces 7 legacy systems with one unified engine:

**Replaced Systems**:
1. NaturalnessEnhancer (reactions, varied responses)
2. AmbientMode (lull detection, ambient thoughts)
3. ProactiveEngagement (jump into conversations)
4. MoodSystem (emotional state tracking)
5. EnvironmentalAwareness (voice channel events)
6. ProactiveCallbacksSystem (reference past topics)
7. CuriositySystem (topic interest detection)

**Core Features**:

#### A. Reaction System
```python
async def _decide_reaction(message: discord.Message) -> Optional[str]
    # 15% chance to add emoji reaction
    # Keyword-based: "lol" → 😂, "cool" → 🔥, "?" → 🤔
```

#### B. Proactive Engagement
```python
async def _decide_proactive_engagement(message, state) -> Optional[str]
    # Jump into conversations without being mentioned
    # Uses LLM to check: "Would [Character] be interested in this topic?"
    # Respects cooldown (configurable via Config.PROACTIVE_COOLDOWN)
```

#### C. Ambient Mode (Anti-Spam with AI-First Prevention)
```python
async def _check_ambient_triggers(channel_id, state)
    # Trigger conditions:
    # - 1-8 hours of silence
    # - 6+ hours since last ambient message
    # - 1/6 probability (16.7%)

    # AI SPAM PREVENTION (router.py:181-223):
    # Before sending, asks thinking model:
    # "Should I send a message or would that be annoying?"
    # Analyzes last 6 messages for bot spam patterns
    # Blocks if no human engagement detected
```

#### D. Environmental Awareness
```python
async def handle_voice_update(member, before, after)
    # Detects: joins, leaves, stream starts
    # 30% chance to comment in text channel
```

**Behavioral State Tracking** (`behavior.py:23-41`):
```python
@dataclass
class BehaviorState:
    last_message_time: datetime
    last_bot_message_time: datetime
    message_count: int
    recent_topics: deque           # Last 10 topics
    recent_users: Set[str]
    last_ambient_trigger: datetime
    last_proactive_trigger: datetime
    short_term_memories: List[Dict]
```

**Configuration** (`behavior.py:74-80`):
```python
self.reaction_chance = 0.15               # 15% reaction probability
self.ambient_interval_min = 600           # 10 min minimum between ambient
self.ambient_chance = 0.3                 # 30% chance during lull
self.proactive_enabled = Config.PROACTIVE_ENGAGEMENT_ENABLED
self.proactive_cooldown = Config.PROACTIVE_COOLDOWN
```

### 4. PersonaRelationships - Inter-Character Affinity

**Location**: `/root/acore_bot/services/persona/relationships.py`

**Purpose**: Tracks relationship strength between personas to enable banter and callbacks.

**Relationship Stages** (`relationships.py:15-21`):
```python
RELATIONSHIP_STAGES = {
    0:  "strangers",      # Never met
    20: "acquaintances",  # Talked a few times
    40: "frenemies",      # Love-hate dynamic
    60: "friends",        # Enjoy each other
    80: "besties"         # Inside jokes welcome
}
```

**Affinity System**:
- Range: 0-100
- Default change: +2 per interaction
- Affects banter probability: 5% (strangers) → 20% (besties)

**Key Methods**:
```python
class PersonaRelationships:
    def get_affinity(persona_a, persona_b) -> int
    def get_banter_chance(persona_a, persona_b) -> float
        # Formula: 0.05 + (affinity/100) * 0.15
        # Result: 5% to 20% chance

    async def record_interaction(speaker, responder, affinity_change=2, memory=None)
        # Update affinity, stage, interaction count
        # Store shared memories (last 10)

    def get_relationship_context(persona_a, persona_b) -> str
        # Returns context for LLM prompts:
        # "Your relationship with Scav: friends (talked 42 times). You enjoy their company."
```

**Persistence**: Stored in `/root/acore_bot/data/persona_relationships.json`

### 5. LorebookService - World Knowledge Injection

**Location**: `/root/acore_bot/services/persona/lorebook.py`

**Purpose**: Dynamically inject world information based on conversation keywords (SillyTavern-compatible).

**Lorebook Entry Structure** (`lorebook.py:13-26`):
```python
@dataclass
class LoreEntry:
    uid: str
    keys: List[str]      # Trigger keywords
    content: str         # Lore text to inject
    order: int           # Insertion priority (lower = earlier)
    enabled: bool
    case_sensitive: bool
    constant: bool       # Always include
    position: str        # "before_char" or "after_char"
```

**Trigger System**:
```python
def scan_for_triggers(text: str, lorebook_names: List[str]) -> List[LoreEntry]
    # Scans message + recent history
    # Returns matching entries sorted by order
    # Deduplicates by UID
```

**Storage**: `/root/acore_bot/data/lorebooks/*.json`

## Persona Selection Flow

**Full Pipeline** (from user message to response):

```
1. Message arrives in Discord
   ↓
2. PersonaRouter.select_persona(message, channel_id)
   ↓
3. Selection Algorithm:
   - Check for name mentions → Explicit match
   - Check sticky context → Last responder
   - Fallback → Random selection
   ↓
4. BehaviorEngine.handle_message(message)
   - Decide reaction emoji (15% chance)
   - Decide proactive engagement
   - Check relationship affinity with other active personas
   ↓
5. ContextManager builds conversation history
   ↓
6. LorebookService scans for keyword triggers
   ↓
7. Compile final prompt:
   - Persona system prompt
   - Relationship context (if multi-persona banter)
   - Lorebook entries
   - Conversation history
   ↓
8. Send to LLM (Ollama/OpenRouter)
   ↓
9. BehaviorEngine post-processing:
   - Add reactions
   - Record response for sticky routing
   - Update relationship affinity
```

## Character Card Format (V2 Spec)

**Supported Formats**:
1. **JSON** - Direct V2 structure
2. **PNG** - V2 card with base64-encoded metadata (SillyTavern export)

**V2 Spec Structure**:
```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Character Name",
    "description": "Physical description and background",
    "personality": "Personality traits and behaviors",
    "scenario": "Current situation/context",
    "first_mes": "Default greeting",
    "mes_example": "Example dialogue exchanges",
    "alternate_greetings": ["Alt 1", "Alt 2"],
    "system_prompt": "Optional embedded system prompt",
    "avatar_url": "https://example.com/avatar.png",
    "creator_notes": "Author commentary",
    "tags": ["tag1", "tag2"],
    "creator": "Author name",
    "character_version": "1.0"
  }
}
```

**PNG Character Cards** (`system.py:190-217`):
- Metadata stored in 'chara' PNG chunk
- Base64-encoded JSON
- Automatically decoded by PersonaSystem
- Example: `joseph_stalin.png` (1.4MB character card)

## Example: Creating a New Character

**Step 1**: Create character JSON file
```bash
/root/acore_bot/prompts/characters/my_character.json
```

**Step 2**: Use V2 format
```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "My Character",
    "description": "A cool character who...",
    "personality": "Friendly, sarcastic, knowledgeable about...",
    "scenario": "Hanging out in Discord",
    "first_mes": "Hey there!",
    "avatar_url": "https://example.com/avatar.png"
  }
}
```

**Step 3**: Add to active roster
```python
# config.py
ACTIVE_PERSONAS = [
    "dagoth_ur.json",
    "my_character.json",  # Add here
    ...
]
```

**Step 4**: Restart bot
```bash
uv run python main.py
```

**Step 5**: PersonaRouter loads automatically
- Character is compiled with default framework (or specified framework)
- Available for routing based on name mentions
- Can build relationships with other personas

## Example: Compiled Persona Output

**Input**:
- Character: `dagoth_ur.json`
- Framework: `neuro.json`

**Output**: `/root/acore_bot/prompts/compiled/dagoth_ur_neuro.json`

```json
{
  "persona_id": "dagoth_ur_neuro",
  "character_id": "dagoth_ur",
  "character_name": "Dagoth Ur",
  "framework_id": "neuro",
  "framework_name": "Neuro-sama Framework",
  "system_prompt": "You are Dagoth Ur.\nWho: Dagoth Ur, immortal god-king...\n\n=== PERSONALITY ===\nCore Traits:\n- Divine superiority complex...\n\n=== INSTRUCTIONS ===\nBe funny and cute.\n\nKeep responses SHORT (1-3 sentences)...",
  "tools_required": [],
  "config": {
    "character": "dagoth_ur",
    "framework": "neuro",
    "behavioral_patterns": {},
    "decision_making": {}
  },
  "compiled_at": "1765271925.5612376"
}
```

## Key File Paths

```
/root/acore_bot/
├── prompts/
│   ├── frameworks/              # Behavioral templates
│   │   ├── assistant.json
│   │   ├── caring.json
│   │   ├── chaotic.json
│   │   └── neuro.json
│   ├── characters/              # Character identities (JSON/PNG)
│   │   ├── dagoth_ur.json
│   │   ├── scav.json
│   │   ├── hal9000.json
│   │   ├── toad.json
│   │   ├── joseph_stalin.json
│   │   └── joseph_stalin.png   # V2 card with embedded metadata
│   └── compiled/                # Generated compiled personas
│       ├── dagoth_ur_neuro.json
│       ├── scav.json
│       └── hal9000.json
├── services/persona/
│   ├── system.py               # PersonaSystem (510 lines)
│   ├── router.py               # PersonaRouter (167 lines)
│   ├── behavior.py             # BehaviorEngine (361 lines)
│   ├── relationships.py        # PersonaRelationships (258 lines)
│   └── lorebook.py             # LorebookService (232 lines)
├── config.py                   # ACTIVE_PERSONAS configuration
└── data/
    ├── persona_relationships.json  # Relationship state
    └── lorebooks/              # World knowledge files
```

## Design Principles

1. **Modularity**: Frameworks and characters are separate, combinable
2. **SillyTavern Compatibility**: Supports V2 character card spec
3. **Multi-Persona**: 9+ characters can coexist and interact
4. **AI-First**: LLM makes routing decisions (spam prevention, interest checks)
5. **Relationship Memory**: Personas remember past interactions
6. **Autonomous Behavior**: Proactive engagement, ambient thoughts, reactions
7. **Dynamic Context**: Lorebooks inject relevant world info
8. **Anti-Spam**: AI evaluates whether to speak to avoid annoyance

## Summary

The persona system transforms the bot from a single personality into a **multi-character AI ensemble**. The two-layer architecture (Framework + Character) provides flexibility, while PersonaRouter enables intelligent message routing. BehaviorEngine (361 lines) consolidates 7 legacy systems into a unified autonomous brain. PersonaRelationships enables inter-character dynamics, and LorebookService provides contextual world knowledge.

**Result**: 9+ distinct AI personalities that can recognize their names, remember relationships, proactively engage in conversations, and avoid spam through AI-driven decision-making.
