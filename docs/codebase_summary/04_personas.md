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
    character_id: str
    display_name: str
    identity: Dict[str, Any]          # Who they are, core traits
    knowledge_domain: Dict[str, Any]  # What they know (includes rag_categories)
    opinions: Dict[str, Any]          # What they believe
    voice_and_tone: Dict[str, Any]    # How they speak
    quirks: Dict[str, Any]            # Unique behaviors
    avatar_url: Optional[str]
    # V2 Card fields
    description: str
    scenario: str
    first_message: str
    mes_example: str
    alternate_greetings: List[str]
    ...
```

**Knowledge Domain Fields** - **UPDATED 2025-12-10**:
```python
knowledge_domain = {
    "rag_categories": ["dagoth", "gaming"],  # RAG document filtering (NEW)
    "expertise_areas": [...],                 # Topics character knows well
    "reference_style": "casual"               # How they cite knowledge
}
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
    def compile_persona(character_id: str, framework_id: str = None, force_recompile: bool = False) -> Optional[CompiledPersona]
    def _build_system_prompt(character: Character, framework: Framework) -> str
    
    # Cache Management (NEW - 2025-12-10)
    def clear_cache() -> None
        """Clear all cached characters, frameworks, and compiled personas."""
    
    def reload_character(character_id: str) -> Optional[Character]
        """Force reload specific character from disk, invalidating cache."""
    
    def reload_all() -> List[str]
        """Reload all characters from disk. Returns list of loaded character IDs."""
```

**Cache Management Methods**:

The PersonaSystem includes comprehensive cache management for hot-reload capabilities:

- **`clear_cache()`** - Clears all in-memory caches (`_character_cache`, `_framework_cache`, `_compiled_cache`)
- **`reload_character(character_id)`** - Forces disk reload of specific character, bypassing cache
- **`reload_all()`** - Mass reload of all characters, returns list of successfully loaded IDs
- **`force_recompile` parameter** - When `True`, bypasses compiled cache and rebuilds from source

**Cache Invalidation Strategy**:
1. Import operations trigger targeted cache invalidation
2. Hot-reload commands perform full cache clearing
3. File modification detection (future enhancement)
4. Manual cache clearing via Discord commands

**Performance Considerations**:
- Cache hits avoid expensive file I/O and JSON parsing
- Compiled personas cached to avoid prompt rebuilding
- Memory usage scales with number of active personas
- Cache warming on startup for faster initial responses

**Compilation Process** (`system.py:261-366`):

1. Load character from `characters/` directory
2. Load framework (optional - can use character card alone)
3. **Validate `rag_categories`** (`system.py:246-278`) - **NEW 2025-12-10**
   - Extract from `extensions.knowledge_domain.rag_categories`
   - Validate must be a list
   - Normalize to lowercase
   - Filter invalid entries (only alphanumeric + underscore allowed)
   - Log warnings for invalid categories
   - Log info for successful loading
4. Build system prompt by combining:
   - Character description
   - Personality traits
   - Scenario context
   - Example dialogue
   - Framework behavioral instructions
5. Extract tool requirements from framework
6. Create `CompiledPersona` object
7. Cache in memory and save to `/root/acore_bot/prompts/compiled/`

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
    async def initialize(force_reload: bool = False)  # Load all ACTIVE_PERSONAS
        # force_reload: If True, clear cache and reload all personas from disk (NEW - 2025-12-10)

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

### Hot-Reload System (NEW - 2025-12-10)

The persona system includes comprehensive hot-reload capabilities that allow adding, updating, or removing characters without bot restart.

**Hot-Reload Workflow**:
```
1. Import/Modify Character Files
   ↓
2. Trigger Reload (!reload_characters or automatic)
   ↓
3. Clear PersonaSystem Cache
   ↓
4. Re-initialize PersonaRouter with force_reload=True
   ↓
5. Compare Before/After State
   ↓
6. Report Changes (new/removed characters)
   ↓
7. Characters Immediately Active
```

**Force Reload Parameter**:
- `force_reload=True` bypasses all caches
- Forces fresh disk read of all character files
- Re-compiles all personas with latest data
- Updates PersonaRouter's active persona list

**Cache Management**:
- `PersonaSystem.clear_cache()` - Clears all in-memory caches
- `PersonaSystem.reload_character(char_id)` - Reloads specific character
- `PersonaSystem.reload_all()` - Reloads all characters from disk

**Security Improvements**:
- Path validation prevents directory traversal
- File type checking (PNG/JSON only)
- Content sanitization for RAG categories
- Automatic backup creation during migrations

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

**NEW: Emotional Contagion Integration** (Lines 300-361):
- **Sentiment Analysis**: NLTK-based sentiment detection on user messages
- **Emotional Memory**: Tracks user emotional patterns over time
- **Response Adaptation**: Modulates persona responses based on emotional context
- **Relationship Impact**: Stronger relationships increase emotional attunement
- **Boundaries**: Prevents emotional burnout with cooldown periods

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

### 5. EvolutionSystem - Character Progression (NEW)

**Location**: `/root/acore_bot/services/persona/evolution.py`

**Purpose**: Character progression system that unlocks new behaviors and capabilities through interaction milestones.

**Core Mechanics**:

#### Experience System
- **Message XP**: Earn experience through meaningful conversations
- **Quality over Quantity**: Deeper conversations worth more XP
- **Relationship Bonus**: Higher affinity levels multiply XP gains
- **Topic Diversity**: Exploring different topics grants bonus XP
- **Daily Limits**: Prevents grinding, encourages natural interaction

#### Milestone Unlocks
```python
# Example Evolution Milestones
milestones = [
    {
        "id": "empathy_unlock",
        "name": "Empathetic Connection",
        "description": "Build meaningful relationships",
        "requirements": {"total_affinity": 500, "unique_users": 10},
        "unlocks": ["emotional_depth", "memory_recall", "supportive_responses"]
    },
    {
        "id": "knowledge_master",
        "name": "Knowledge Master",
        "description": "Master diverse topic areas",
        "requirements": {"topics_discussed": 50, "conversation_depth": 5},
        "unlocks": ["expertise_mode", "cross_reference", "teaching_ability"]
    }
]
```

#### Character-Specific Paths
Each character has unique evolution trajectories:

**Dagoth Ur**: Divine → Philosopher → Mentor → Wisdom
**Scav**: Survivor → Storyteller → Protector → Legend
**Toad**: Panicked → Loyal → Brave → Hero

#### Trait System
- **Communication Traits**: New response styles (sarcasm, empathy, humor)
- **Knowledge Traits**: Specialized expertise areas
- **Social Traits**: Enhanced relationship capabilities
- **Emotional Traits**: Deeper emotional range

**Integration**:
- **PersonaRouter**: Considers evolution level for routing decisions
- **BehaviorEngine**: Evolution unlocks new behavioral patterns
- **ContextManager**: Injects evolution-based prompt modifiers
- **Analytics**: Tracks evolution progress and milestone completion

### 6. FrameworkBlender - Dynamic Behavioral Mixing (NEW)

**Location**: `/root/acore_bot/services/persona/framework_blender.py`

**Purpose**: Dynamically mix and match behavioral frameworks to create unique personality combinations.

**Architecture** (Lines 25-150):
```python
@dataclass
class FrameworkMix:
    primary_framework: str      # Base personality (e.g., "neuro")
    secondary_framework: str    # Behavioral modifier (e.g., "caring")
    blend_ratio: float         # 0.0-1.0 influence of secondary
    context_triggers: List[str] # When to apply blend
    temporary: bool            # Permanent vs temporary blend
```

**Blend Modes**:

#### Context-Aware Blending
```python
# Example: Dagoth Ur becomes caring when discussing sensitive topics
blend = FrameworkMix(
    primary_framework="neuro",      # Base: analytical, thoughtful
    secondary_framework="caring",   # Modifier: empathetic, supportive
    blend_ratio=0.3,               # 30% caring influence
    context_triggers=["sad", "hurt", "depressed", "grieving"],
    temporary=True                 # Only for specific conversations
)
```

#### Temporary Personality Modes
- **Support Mode**: Activated when users express distress
- **Teaching Mode**: Engaged during educational discussions
- **Celebration Mode**: Triggered by positive events
- **Crisis Mode**: High-stakes or emergency situations

#### Framework Math
Blending algorithm combines behavioral parameters:
```python
# Behavioral parameter mixing
final_response_length = (
    primary.length * (1 - blend_ratio) + 
    secondary.length * blend_ratio
)

final_formality = clamp(
    primary.formality + (secondary.formality - primary.formality) * blend_ratio,
    0.0, 1.0
)
```

**Supported Framework Combinations**:
- **Neuro + Caring**: Analytical yet empathetic
- **Chaotic + Assistant**: Energetic helpfulness
- **Assistant + Neuro**: Structured entertainment
- **Caring + Chaotic**: Unpredictable support

**Integration**:
- **ContextManager**: Uses `FrameworkBlender` to modify system prompts dynamically based on conversation context.

**Learning System**:
- Tracks successful blend outcomes
- Learns which contexts benefit from specific blends
- Automatic blend ratio optimization
- User feedback integration for blend tuning

### 7. LorebookService - World Knowledge Injection

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
   - Consider evolution level (higher level = higher priority)
   - Fallback → Random selection
   ↓
4. FrameworkBlender.check_context(message, persona)
   - Analyze emotional context
   - Apply temporary framework blending if needed
   - Adjust behavioral parameters dynamically
   ↓
5. BehaviorEngine.handle_message(message)
   - Sentiment analysis for emotional contagion
   - Decide reaction emoji (15% chance)
   - Decide proactive engagement
   - Check relationship affinity with other active personas
   - Apply evolution-unlocked behaviors
   ↓
6. EvolutionSystem.process_interaction(persona, user, message)
   - Award XP for quality interactions
   - Check milestone completion
   - Unlock new traits if milestones reached
   - Update character progression data
   ↓
7. ContextManager builds conversation history
   ↓
8. LorebookService scans for keyword triggers
   ↓
9. Compile final prompt:
   - Blended persona system prompt (if framework blending active)
   - Evolution-enhanced behavioral traits
   - Relationship context (if multi-persona banter)
   - Emotional context (if emotional contagion active)
   - Lorebook entries
   - Conversation history
   ↓
10. Send to LLM (Ollama/OpenRouter)
    ↓
11. BehaviorEngine post-processing:
    - Apply emotional modulation based on sentiment analysis
    - Add reactions based on emotional context
    - Record response for sticky routing
    - Update relationship affinity
    - Track evolution progress
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

## Character Import & Normalization System (NEW - 2025-12-10)

### CharacterCardImporter - Import SillyTavern Cards

**Location**: `/root/acore_bot/services/persona/character_importer.py`

**Purpose**: Import character cards from SillyTavern (PNG or JSON) and automatically normalize to V2 format.

**Key Features**:
- **Format Detection**: Automatically detects V1, V2, or malformed character cards
- **V2 Normalization**: Always outputs standardized V2 schema with `extensions.knowledge_domain`
- **RAG Category Validation**: Normalizes `rag_categories` to lowercase, validates alphanumeric+underscore only
- **Auto-Compilation**: Optionally compiles character to `prompts/compiled/` after import
- **Multi-Format Support**: Handles both PNG (embedded metadata) and JSON files

**Methods**:

```python
class CharacterCardImporter:
    def extract_png_metadata(png_path: Path) -> Optional[Dict]
        """Extract character JSON from PNG tEXt/iTXt chunks."""
    
    def convert_to_internal_format(card_data: Dict, png_path: Path) -> Dict
        """Convert any format to standardized V2 with validated rag_categories."""
    
    def import_card(png_path: Path, copy_avatar: bool = True, auto_compile: bool = True) -> Tuple[Path, Optional[Path], str]
        """Import character card. Returns (json_path, compiled_path, char_id)."""
    
    def import_from_directory(source_dir: Path, auto_compile: bool = True) -> List[Tuple]
        """Batch import all PNG/JSON cards from directory."""
```

**Normalization Process** (`character_importer.py:104-195`):

1. **Detect Format Variant**:
   - Check for `spec` and `data` keys (V2 wrapped)
   - Handle unwrapped V2 (`data` key only)
   - Handle V1 (flat structure)

2. **Normalize to V2 Structure**:
   ```python
   {
     "spec": "chara_card_v2",
     "spec_version": "2.0",
     "data": {
       "name": "Character Name",
       "extensions": {
         "knowledge_domain": {
           "rag_categories": ["validated", "normalized"]
         }
       }
     }
   }
   ```

3. **Validate `rag_categories`**:
   - Must be a list of strings
   - Normalize to lowercase
   - Strip whitespace
   - Validate alphanumeric + underscore only
   - Log warnings for invalid entries
   - Filter out invalid entries

4. **Auto-Compile** (if enabled):
   - Call `PersonaSystem.compile_persona(char_id, force_recompile=True)`
   - Save to `prompts/compiled/{char_id}.json`
   - Return compiled path in result tuple

**CLI Usage**:

```bash
# Import single card
python services/persona/character_importer.py character.png --compile

# Import directory
python services/persona/character_importer.py /path/to/cards/ --compile --verbose
```

### Hot-Reload Commands

**!reload_characters** - Reload all characters without restart

```python
# Compares before/after state, shows added/removed characters
!reload_characters
# Output:
# ✅ Reload complete!
# **Before:** 9 characters
# **After:** 10 characters
# **New:** New Character
# **Active:** Dagoth Ur, Scav, ...
```

**/import_character** - Import card via Discord slash command

```python
# Upload PNG/JSON file as attachment
/import_character file:character.png
# Automatically:
# 1. Downloads file
# 2. Normalizes to V2 format
# 3. Auto-compiles character
# 4. Hot-reloads PersonaRouter
# 5. Character immediately active (no restart needed)
```

**!import_folder** - Batch import from `data/import_cards/`

```bash
# Place cards in data/import_cards/, then:
!import_folder
# Imports all PNG/JSON files with auto-compilation
```

### Migration Script - Normalize Existing Characters

**Location**: `/root/acore_bot/scripts/normalize_character_formats.py`

**Purpose**: Scan and normalize existing character files to V2 standard.

**Features**:
- **Dry-Run Mode**: Preview changes before applying
- **Automatic Backups**: Saves originals to `prompts/characters/backups/`
- **Format Detection**: Identifies V1, V2, and malformed cards
- **Batch Processing**: Normalizes entire directory

**Usage**:

```bash
# Dry-run (preview only)
python scripts/normalize_character_formats.py

# Apply fixes
python scripts/normalize_character_formats.py --apply

# Custom directory
python scripts/normalize_character_formats.py --dir /custom/path --apply --verbose
```

**Example Output**:

```
⚠ dagoth_ur.json: 2 issues detected
  - rag_categories[0] not normalized: 'Dagoth' should be 'dagoth'
  - rag_categories[1] has invalid chars: 'Elder Scrolls!'
  → 2 fixes available
    • Normalized category: 'Dagoth' -> 'dagoth'
    • Removed invalid category: 'Elder Scrolls!'

SCAN SUMMARY
===========
Total files scanned: 12
Already valid V2: 10
Need updates: 2
Errors: 0

💡 Run with --apply to make changes
```

### Import System Architecture

**Component Overview**:
```
Discord Commands (/import_character, !import_folder, !reload_characters)
    ↓
CharacterCardImporter (services/persona/character_importer.py)
    ↓
Format Detection → V2 Normalization → Validation → Auto-Compilation
    ↓
PersonaSystem (services/persona/system.py)
    ↓
Cache Management → PersonaRouter Hot-Reload
    ↓
Active Character Roster Updated
```

**Security Considerations**:
- **Path Validation**: Restricts file operations to safe directories
- **File Type Checking**: Only processes PNG and JSON files
- **Content Sanitization**: Validates RAG categories (alphanumeric + underscore only)
- **Size Limits**: Rejects excessively large files
- **Backup Creation**: Automatic backups during migration operations

**Error Handling**:
- Graceful degradation for malformed cards
- Detailed logging for troubleshooting
- Rollback capability for failed imports
- Validation warnings without blocking imports

**Normalization Process** (`character_importer.py:104-195`):

1. **Detect Format Variant**:
   - Check for `spec` and `data` keys (V2 wrapped)
   - Handle unwrapped V2 (`data` key only)
   - Handle V1 (flat structure)

2. **Normalize to V2 Structure**:
   ```python
   {
     "spec": "chara_card_v2",
     "spec_version": "2.0",
     "data": {
       "name": "Character Name",
       "extensions": {
         "knowledge_domain": {
           "rag_categories": ["validated", "normalized"]
         }
       }
     }
   }
   ```

3. **Validate `rag_categories`**:
   - Must be a list of strings
   - Normalize to lowercase
   - Strip whitespace
   - Validate alphanumeric + underscore only
   - Log warnings for invalid entries
   - Filter out invalid entries

4. **Auto-Compile** (if enabled):
   - Call `PersonaSystem.compile_persona(char_id, force_recompile=True)`
   - Save to `prompts/compiled/{char_id}.json`
   - Return compiled path in result tuple

**CLI Usage**:

```bash
# Import single card
python services/persona/character_importer.py character.png --compile

# Import directory
python services/persona/character_importer.py /path/to/cards/ --compile --verbose
```

### Hot-Reload Commands

**!reload_characters** - Reload all characters without restart

```python
# Compares before/after state, shows added/removed characters
!reload_characters
# Output:
# ✅ Reload complete!
# **Before:** 9 characters
# **After:** 10 characters
# **New:** New Character
# **Active:** Dagoth Ur, Scav, ...
```

**/import_character** - Import card via Discord slash command

```python
# Upload PNG/JSON file as attachment
/import_character file:character.png
# Automatically:
# 1. Downloads file
# 2. Normalizes to V2 format
# 3. Auto-compiles character
# 4. Hot-reloads PersonaRouter
# 5. Character immediately active (no restart needed)
```

**!import_folder** - Batch import from `data/import_cards/`

```bash
# Place cards in data/import_cards/, then:
!import_folder
# Imports all PNG/JSON files with auto-compilation
```

### Migration Script - Normalize Existing Characters

**Location**: `/root/acore_bot/scripts/normalize_character_formats.py`

**Purpose**: Scan and normalize existing character files to V2 standard.

**Features**:
- **Dry-Run Mode**: Preview changes before applying
- **Automatic Backups**: Saves originals to `prompts/characters/backups/`
- **Format Detection**: Identifies V1, V2, and malformed cards
- **Batch Processing**: Normalizes entire directory

**Usage**:

```bash
# Dry-run (preview only)
python scripts/normalize_character_formats.py

# Apply fixes
python scripts/normalize_character_formats.py --apply

# Custom directory
python scripts/normalize_character_formats.py --dir /custom/path --apply --verbose
```

**Example Output**:

```
⚠ dagoth_ur.json: 2 issues detected
  - rag_categories[0] not normalized: 'Dagoth' should be 'dagoth'
  - rag_categories[1] has invalid chars: 'Elder Scrolls!'
  → 2 fixes available
    • Normalized category: 'Dagoth' -> 'dagoth'
    • Removed invalid category: 'Elder Scrolls!'

SCAN SUMMARY
============
Total files scanned: 12
Already valid V2: 10
Need updates: 2
Errors: 0

💡 Run with --apply to make changes
```

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
9. **Character Growth**: Evolution system enables character progression and development
10. **Emotional Intelligence**: Emotional contagion creates empathetic, context-aware responses
11. **Adaptive Behavior**: Framework blending allows dynamic personality mixing
12. **Data-Driven**: Analytics and metrics inform system improvements

## Summary

The persona system transforms the bot from a single personality into a **multi-character AI ensemble** with advanced emotional and evolutionary capabilities. The two-layer architecture (Framework + Character) provides flexibility, while PersonaRouter enables intelligent message routing. BehaviorEngine (361 lines) consolidates 7 legacy systems into a unified autonomous brain with emotional contagion. PersonaRelationships enables inter-character dynamics, EvolutionSystem provides character progression through interaction milestones, FrameworkBlender allows dynamic behavioral mixing, and LorebookService provides contextual world knowledge.

**Result**: 9+ distinct AI personalities that can recognize their names, remember relationships, proactively engage in conversations, grow through experience, adapt emotionally to user sentiment, and dynamically blend behaviors for context-appropriate responses.

**Result**: 9+ distinct AI personalities that can recognize their names, remember relationships, proactively engage in conversations, and avoid spam through AI-driven decision-making.
