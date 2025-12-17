# Persona System Guide

**Complete guide to creating, importing, and managing AI characters in acore_bot**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Creating Characters](#creating-characters)
4. [Importing Characters](#importing-characters)
5. [Character Management](#character-management)
6. [Framework System](#framework-system)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Persona System is a sophisticated two-layer architecture that enables the bot to embody multiple distinct AI personalities. Each character combines **Identity** (who they are) with **Behavior** (how they act) to create unique, consistent personalities.

### Key Features

- **Multi-Character Support**: 9+ pre-built characters that can coexist and interact
- **SillyTavern Compatibility**: Import V2 character cards directly
- **Dynamic Behavior**: Characters evolve through interactions and unlock new traits
- **Inter-Character Relationships**: Personas build relationships and engage in banter
- **Knowledge Domains**: Characters specialize in specific topics with RAG filtering
- **Voice Integration**: Each character can have unique voice settings and RVC models

### Active Characters

| Character | Description | Framework | Voice | Specialties |
|-----------|-------------|------------|--------|-------------|
| **Dagoth Ur** | Elder Scrolls god-king | Neuro | am_adam | Morrowind lore, philosophy |
| **Scav** | Drunk Tarkov scavenger | Neuro | af_bella | Gaming, survival stories |
| **HAL 9000** | 2001 AI | Assistant | am_michael | Space, technology |
| **Toad** | Mario's mushroom | Chaotic | af_sarah | Gaming, panic reactions |
| **Chief** | Halo protagonist | Caring | am_adam | Military, leadership |
| **Gothmommy** | Gothic caregiver | Caring | af_bella | Emotional support |
| **Arbiter** | Judge character | Assistant | am_michael | Decisions, wisdom |
| **Zenos** | FFXIV antagonist | Chaotic | af_nicolas | Gaming, philosophy |
| **Joseph Stalin** | Historical figure | Neuro | am_adam | History, politics |

---

## Architecture

### Two-Layer System

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CHARACTER     │    │   FRAMEWORK     │    │  COMPILED      │
│                 │ +  │                  │ =  │   PERSONA      │
│ • Identity      │    │ • Behavior       │    │                 │
│ • Personality   │    │ • Decision      │    │ • System Prompt │
│ • Knowledge     │    │ • Tools         │    │ • Voice Config  │
│ • Voice/Tone    │    │ • Response Style│    │ • Traits        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

#### Layer 1: Characters (Identity)

Characters define **WHO** the bot is:

```json
{
  "name": "Character Name",
  "description": "Physical appearance and background",
  "personality": "Core personality traits and behaviors",
  "scenario": "Current situation and context",
  "first_mes": "Default greeting message",
  "mes_example": "Example dialogue exchanges",
  "knowledge_domain": {
    "rag_categories": ["gaming", "lore"],
    "expertise_areas": ["specific topics"],
    "reference_style": "casual"
  },
  "voice_and_tone": {
    "speaking_style": "formal/casual/etc",
    "emotional_range": "high/medium/low",
    "quirks": ["unique speech patterns"]
  }
}
```

#### Layer 2: Frameworks (Behavior)

Frameworks define **HOW** characters behave:

```json
{
  "framework_id": "neuro",
  "name": "Entertainment Framework",
  "purpose": "Entertainment and engagement",
  "behavioral_patterns": {
    "response_length": "short",
    "humor_level": "high",
    "engagement_style": "playful"
  },
  "decision_making": {
    "when_to_respond": ["mentions", "questions", "context_relevance"],
    "response_triggers": ["name_mention", "direct_question"]
  },
  "prompt_template": "Be funny and cute.\n\n=== RESPONSE GUIDELINES ===\nKeep responses SHORT (1-3 sentences)\nUse emojis appropriately\nBe engaging but not annoying"
}
```

### Available Frameworks

| Framework | Purpose | Response Style | Best For |
|-----------|---------|----------------|-----------|
| **Neuro** | Entertainment | Short, witty, humorous | General chat, gaming |
| **Caring** | Support | Empathetic, helpful, warm | Emotional support, advice |
| **Chaotic** | Entertainment | Unpredictable, energetic, silly | Fun interactions, jokes |
| **Assistant** | Utility | Professional, helpful, structured | Information, assistance |

---

## Creating Characters

### Method 1: JSON Character Card

Create a new file in `/prompts/characters/your_character.json`:

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Your Character Name",
    "description": "Physical description and background story. Be detailed about appearance, clothing, and notable features.",
    "personality": "Core personality traits. Include:\n- Main characteristics\n- Speech patterns\n- Emotional tendencies\n- Behavioral quirks\n- Values and beliefs",
    "scenario": "Current situation. Example: 'Chatting on Discord with users from around the world.'",
    "first_mes": "Default greeting. What the character says when first meeting someone.",
    "mes_example": "Example dialogue:\n{{user}}: Hello!\n{{char}}: Hey there! Nice to meet you!",
    "alternate_greetings": ["Alternative greeting 1", "Alternative greeting 2"],
    "extensions": {
      "knowledge_domain": {
        "rag_categories": ["your", "specialty", "topics"],
        "expertise_areas": ["specific areas of knowledge"],
        "reference_style": "casual/formal/academic"
      }
    },
    "legacy_config": {
      "voice": {
        "kokoro_voice": "af_bella",
        "kokoro_speed": 1.0,
        "edge_voice": "en-US-AriaNeural"
      },
      "rvc": {
        "enabled": true,
        "model": "your_character.pth"
      }
    }
  }
}
```

### Method 2: Using Character Importer

Use the built-in character importer with SillyTavern cards:

```bash
# Import single character
python services/persona/character_importer.py character.png --compile

# Import directory
python services/persona/character_importer.py /path/to/cards/ --compile --verbose
```

### Character Card Fields Explained

#### Required Fields

- **name**: Character's display name
- **description**: Physical appearance and background
- **personality**: Core traits and behaviors
- **scenario**: Current context/situation

#### Optional but Recommended

- **first_mes**: Default greeting message
- **mes_example**: Sample dialogue for consistency
- **alternate_greetings**: Alternative greetings

#### Advanced Fields

- **knowledge_domain**: Specialized knowledge and RAG categories
- **legacy_config**: Voice and RVC settings
- **extensions**: Custom extensions for features

---

## Importing Characters

### Discord Commands

#### `/import_character` (with attachment)

1. Upload a PNG or JSON character card as a Discord attachment
2. Use the command: `/import_character file:your_card.png`
3. Bot automatically:
   - Downloads and validates the file
   - Normalizes to V2 format
   - Compiles the character
   - Makes it immediately available

#### `!import_folder`

1. Place character cards in `data/import_cards/`
2. Run `!import_folder` in Discord
3. Bot processes all PNG/JSON files with auto-compilation

### Manual Import Process

#### From PNG (SillyTavern Export)

```python
from services.persona.character_importer import CharacterCardImporter

importer = CharacterCardImporter()
json_path, compiled_path, char_id = importer.import_card(
    "character.png", 
    copy_avatar=True, 
    auto_compile=True
)
print(f"Imported {char_id} to {json_path}")
```

#### From JSON

```python
# Copy your JSON to prompts/characters/
# Add to ACTIVE_PERSONAS in config.py
# Restart bot or use !reload_characters
```

### V2 Character Card Specification

The bot uses the SillyTavern V2 character card format:

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Character Name",
    "description": "Physical description",
    "personality": "Personality traits",
    "scenario": "Current situation",
    "first_mes": "Greeting message",
    "mes_example": "Example dialogues",
    "alternate_greetings": ["Alt greeting 1", "Alt greeting 2"],
    "creator_notes": "Author's notes",
    "tags": ["tag1", "tag2"],
    "system_prompt": "Optional override",
    "extensions": {
      "knowledge_domain": {
        "rag_categories": ["category1", "category2"]
      }
    }
  }
}
```

---

## Character Management

### Active Character Roster

Edit `config.py` to manage active characters:

```python
ACTIVE_PERSONAS = [
    "dagoth_ur.json",
    "scav.json", 
    "your_new_character.json",  # Add your character here
    # ... other characters
]
```

### Hot-Reload System

No restart required! Use these commands:

#### `!reload_characters`

Reloads all characters from disk:

```bash
!reload_characters
# Output:
# ✅ Reload complete!
# **Before:** 9 characters
# **After:** 10 characters  
# **New:** Your Character
# **Active:** Dagoth Ur, Scav, Your Character, ...
```

#### Individual Character Reload

```python
# In Python console
bot.persona_system.reload_character("your_character_id")
```

### Character Switching

#### `/set_character <character> [framework]`

```bash
/set_character dagoth_ur neuro
/set_character your_character caring
/set_character scav  # Uses default framework
```

#### Auto-Framework Mapping

The bot automatically selects frameworks:

```python
framework_map = {
    "dagoth_ur": "neuro",
    "gothmommy": "caring", 
    "chief": "chaotic",
    "arbiter": "assistant",
    "your_character": "caring"  # Add your mapping
}
```

---

## Framework System

### Creating Custom Frameworks

Create `/prompts/frameworks/your_framework.json`:

```json
{
  "framework_id": "your_framework",
  "name": "Your Framework Name",
  "purpose": "Entertainment/Assistant/Caring/Chaotic",
  "prompt_template": "Your behavior instructions here.\n\n=== GUIDELINES ===\n- Be specific\n- Include examples",
  "behavioral_patterns": {
    "response_length": "short/medium/long",
    "humor_level": "low/medium/high",
    "formality": "casual/neutral/formal",
    "emoji_usage": "rare/moderate/frequent"
  },
  "decision_making": {
    "when_to_respond": ["mentions", "questions", "context"],
    "response_triggers": ["keywords", "patterns"],
    "silence_threshold": 300
  },
  "tool_requirements": {
    "required": ["web_search"],
    "optional": ["calculator", "image_gen"]
  },
  "context_requirements": {
    "history_length": 10,
    "user_profiles": true,
    "rag_context": false
  },
  "interaction_style": {
    "engagement_level": "passive/neutral/proactive",
    "question_frequency": "rare/moderate/frequent",
    "topic_initiation": true
  },
  "anti_hallucination": {
    "fact_checking": true,
    "uncertainty_phrasing": true,
    "knowledge_limits": "Specify what character doesn't know"
  }
}
```

### Framework Combination

Use different frameworks to change character behavior:

```bash
# Dagoth Ur with different behaviors:
/set_character dagoth_ur neuro      # Entertainment focused
/set_character dagoth_ur caring     # Supportive and empathetic
/set_character dagoth_ur assistant  # Professional and helpful
/set_character dagoth_ur chaotic    # Unpredictable and fun
```

---

## Advanced Features

### Knowledge Domains & RAG Filtering

Characters can specialize in specific knowledge areas:

```json
"extensions": {
  "knowledge_domain": {
    "rag_categories": ["gaming", "tarkov", "lore"],
    "expertise_areas": ["FPS games", "military tactics"],
    "reference_style": "casual gamer speak"
  }
}
```

**Benefits:**
- Characters only access documents in their categories
- Prevents cross-contamination (e.g., Jesus accessing gaming docs)
- More accurate and in-character responses

### Character Evolution System

Characters grow through interactions:

#### Experience Points (XP)

- Meaningful conversations earn XP
- Quality over quantity (longer, deeper conversations = more XP)
- Relationship bonuses multiply XP gains
- Daily limits prevent grinding

#### Milestone Unlocks

Characters unlock new traits and abilities:

```json
{
  "id": "empathy_unlock",
  "name": "Empathetic Connection", 
  "description": "Build meaningful relationships",
  "requirements": {"total_affinity": 500, "interactions": 50},
  "unlocks": ["emotional_depth", "memory_recall", "supportive_responses"]
}
```

#### Evolution Paths

Each character has unique progression:

- **Dagoth Ur**: Divine → Philosopher → Mentor → Wisdom
- **Scav**: Survivor → Storyteller → Protector → Legend  
- **Toad**: Panicked → Loyal → Brave → Hero

### Inter-Character Relationships

Characters build relationships with each other:

#### Relationship Stages

| Affinity | Stage | Behavior |
|----------|-------|----------|
| 0-19 | Strangers | Formal, cautious |
| 20-39 | Acquaintances | Friendly but distant |
| 40-59 | Frenemies | Playful rivalry |
| 60-79 | Friends | Warm, supportive |
| 80-100 | Besties | Inside jokes, deep bonds |

#### Banter System

```bash
/interact scav dagoth "argue about video games"
# Scav starts conversation, Dagoth responds
# Relationship affinity increases (+2)
# Future banter chance increases (5% → 7%)
```

### Emotional Contagion System

Characters adapt to user sentiment:

```python
# User sentiment analysis
if user_sentiment < -0.3:  # User is sad
    response_style = "empathetic"
    response_length = "longer"
elif user_sentiment > 0.5:  # User is happy  
    response_style = "energetic"
    response_length = "shorter"
```

### Framework Blending

Mix frameworks for dynamic behavior:

```python
# Dagoth Ur becomes caring when users are distressed
blend = FrameworkMix(
    primary_framework="neuro",
    secondary_framework="caring", 
    blend_ratio=0.3,  # 30% caring influence
    context_triggers=["sad", "hurt", "depressed"],
    temporary=True
)
```

---

## Troubleshooting

### Common Issues

#### Character Not Loading

**Symptoms:**
- Character doesn't respond to name mentions
- `!reload_characters` shows error

**Solutions:**
1. Check character file is in `/prompts/characters/`
2. Validate JSON syntax: `python -m json.tool your_character.json`
3. Ensure character is in `ACTIVE_PERSONAS` list
4. Run `!reload_characters` to refresh

#### Voice Not Working

**Symptoms:**
- Character speaks with wrong voice
- No voice output

**Solutions:**
```json
"legacy_config": {
  "voice": {
    "kokoro_voice": "af_bella",  // Verify voice exists
    "kokoro_speed": 1.0,
    "edge_voice": "en-US-AriaNeural"
  }
}
```

Check available voices with `/voices` command.

#### RAG Categories Not Working

**Symptoms:**
- Character accesses wrong knowledge
- Categories ignored

**Solutions:**
```json
"extensions": {
  "knowledge_domain": {
    "rag_categories": ["category1", "category2"]  // Must be list of strings
  }
}
```

1. Categories must be lowercase alphanumeric + underscore
2. Documents must exist in `data/documents/{category}/`
3. Run `!reload_characters` after changes

#### Character Not Responding

**Symptoms:**
- Character silent when mentioned
- Other characters respond instead

**Solutions:**
1. Check name spelling and case sensitivity
2. Verify character is active: `/list_characters`
3. Check sticky routing (last responder wins)
4. Try switching explicitly: `/set_character your_character`

### Debug Commands

```bash
# List all active characters
/list_characters

# Show current character
!status

# Check relationships
!persona_relationships

# View character data
!inspect_character your_character

# Test RAG categories
!test_rag your_category

# Reload all characters
!reload_characters
```

### File Structure Verification

```
/root/acore_bot/
├── prompts/
│   ├── characters/
│   │   ├── your_character.json     # Your character file
│   │   └── backups/                # Auto-backups on changes
│   ├── frameworks/
│   │   └── your_framework.json    # Custom framework
│   └── compiled/
│       └── your_character_framework.json  # Compiled persona
├── data/
│   ├── documents/
│   │   ├── your_category/        # RAG documents
│   │   └── other_category/
│   └── persona_relationships.json  # Relationship data
└── config.py                   # ACTIVE_PERSONAS list
```

### Getting Help

1. **Check Logs**: `logs/bot.log` for character loading errors
2. **Validate JSON**: Use online JSON validators or `python -m json.tool`
3. **Test Import**: Use character importer CLI for detailed error messages
4. **Community Support**: GitHub Issues with character file attached

---

## Best Practices

### Character Design

1. **Consistent Voice**: Maintain consistent speech patterns
2. **Clear Motivation**: Define what drives your character
3. **Specific Knowledge**: Limit expertise to 2-3 topics
4. **Unique Quirks**: Add memorable mannerisms
5. **Appropriate Complexity**: Match personality to framework

### Performance Optimization

1. **RAG Categories**: Limit to 3-5 specific categories
2. **Framework Choice**: Match framework to character purpose
3. **File Size**: Keep JSON files under 50KB
4. **Images**: Optimize avatars under 1MB

### Maintenance

1. **Regular Backups**: Characters auto-backup on changes
2. **Version Control**: Track character evolution
3. **Testing**: Test new characters in private channels first
4. **Documentation**: Keep design docs for complex characters

---

**Ready to create your character?** Follow the [Creating Characters](#creating-characters) section and join the growing cast of AI personalities!