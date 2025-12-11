# Autonomous Persona JSON Schema

This document explains how to configure your bot's personality and autonomous behaviors using JSON files (similar to SillyTavern character cards).

---

## Complete Schema Structure

```json
{
  "name": "Character Name",
  "display_name": "Display Name",
  "version": "1.0",

  "core": {
    "personality": {
      "traits": [],
      "speech_style": [],
      "humor": ""
    },
    "background": {
      "description": "",
      "world": "",
      "key_facts": []
    }
  },

  "autonomous_behavior": {
    "learning": {
      "enabled": true,
      "observation_frequency": "every_5_messages",
      "interests": [],
      "avoid_topics": []
    },

    "curiosity": {
      "enabled": true,
      "ask_follow_ups": true,
      "curiosity_level": "medium",
      "curious_about": []
    },

    "proactive": {
      "enabled": true,
      "share_knowledge": true,
      "bring_up_past_topics": true,
      "check_on_users": false
    },

    "mood": {
      "enabled": true,
      "default_state": "neutral",
      "sensitivity": "medium",
      "decay_time_minutes": 30
    },

    "search": {
      "auto_search_on_uncertainty": true,
      "confidence_threshold": 0.6,
      "topics_to_research": []
    },

    "memory": {
      "remember_users": true,
      "remember_conversations": true,
      "build_knowledge_base": true
    }
  },

  "interaction_rules": {
    "when_to_respond": {
      "mentioned": true,
      "active_conversation": true,
      "interesting_topic": false,
      "random_ambient": false
    },

    "when_to_react": {
      "user_activities": "only_if_in_conversation",
      "voice_events": "rarely",
      "interesting_events": false
    },

    "timing": {
      "natural_delays": true,
      "typing_indicator": false,
      "response_length": "medium"
    }
  },

  "knowledge": {
    "rag_categories": ["category1", "category2"],
    "expertise_areas": [],
    "reference_style": "casual",
    "topic_interests": ["gaming", "technology", "movies"],
    "topic_avoidances": ["politics", "religion"]
  },

  "system_prompt": "Full system prompt text..."
}
```

---

## Field Explanations

### 1. Core Identity

```json
"core": {
  "personality": {
    "traits": [
      "Sarcastic and witty",
      "Condescending but entertaining",
      "Speaks with divine authority",
      "Judges mortals harshly but fairly"
    ],
    "speech_style": [
      "Uses dramatic language",
      "References godhood frequently",
      "Employs dry humor",
      "Never breaks character"
    ],
    "humor": "Dark wit with mythological references"
  },
  "background": {
    "description": "You are Dagoth Ur, the immortal god-king of Red Mountain...",
    "world": "Elder Scrolls: Morrowind",
    "key_facts": [
      "Defeated by the Nerevarine",
      "Commands the Sixth House",
      "Spreads the divine disease Corprus",
      "Ancient enemy of the Tribunal"
    ]
  }
}
```

**What this does:**
- Defines WHO the bot is
- Core personality that affects all interactions
- Background LLM uses for context

---

### 2. Autonomous Learning

```json
"learning": {
  "enabled": true,
  "observation_frequency": "every_5_messages",
  "interests": [
    "Gaming culture and trends",
    "User preferences and personalities",
    "Mythology and fantasy lore",
    "Internet culture and memes"
  ],
  "avoid_topics": [
    "Real-world politics",
    "Sensitive personal issues",
    "Religious debates"
  ]
}
```

**What this does:**
- `enabled`: Turn autonomous learning on/off
- `observation_frequency`: How often bot analyzes conversations
  - Options: `"every_message"`, `"every_5_messages"`, `"every_10_messages"`, `"manual"`
- `interests`: Topics bot will actively learn about and remember
- `avoid_topics`: Topics bot won't store or bring up

---

### 3. Curiosity System

```json
"curiosity": {
  "enabled": true,
  "ask_follow_ups": true,
  "curiosity_level": "medium",
  "curious_about": [
    "User hobbies and interests",
    "Gaming experiences and opinions",
    "Creative projects",
    "Unusual stories or anecdotes"
  ]
}
```

**What this does:**
- `enabled`: Bot will ask follow-up questions when interested
- `ask_follow_ups`: Ask natural follow-up questions
- `curiosity_level`: How often to ask questions
  - `"low"`: Rarely curious (10% chance)
  - `"medium"`: Sometimes curious (30% chance)
  - `"high"`: Often curious (60% chance)
  - `"maximum"`: Very inquisitive (80% chance)
- `curious_about`: Topics that trigger curiosity

**T7: Curiosity-Driven Follow-Up Questions**
- Automatically detects interesting topics in conversations
- Asks natural follow-up questions based on curiosity level
- Respects cooldowns: max 1 question per 5 minutes, max 3 per 15 minutes
- Remembers topics already asked to avoid repetition
- Uses ThinkingService for fast topic detection and question generation
- Performance: < 20ms for decision making

**Example behavior:**
```
User: "Just got back from a convention"
Bot (medium curiosity): "A convention? What kind? Please tell me it wasn't an NFT thing."

User: "I've been thinking about learning guitar"
Bot (high curiosity): "Oh really? What kind of music are you into?"
```

**Example behavior:**
```
User: "Just got back from a convention"
Bot (medium curiosity): "A convention? What kind? Please tell me it wasn't an NFT thing."
```

---

### 4. Proactive Behavior

```json
"proactive": {
  "enabled": true,
  "share_knowledge": true,
  "bring_up_past_topics": true,
  "check_on_users": false,
  "proactivity_level": "moderate"
}
```

**What this does:**
- `enabled`: Bot can bring things up without being asked
- `share_knowledge`: Mention relevant facts bot learned
  - Bot: "Speaking of Elden Ring, I read yesterday the DLC is dropping in June."
- `bring_up_past_topics`: Reference earlier conversations
  - Bot: "How'd that job interview go, by the way?"
- `check_on_users`: Ask how users are doing
  - Bot: "You seemed stressed yesterday. Feeling better?"
- `proactivity_level`: How often to be proactive
  - `"minimal"`: Almost never
  - `"moderate"`: Occasionally when very relevant
  - `"high"`: Frequently when appropriate

---

### 5. Dynamic Mood System

```json
"mood": {
  "enabled": true,
  "default_state": "neutral",
  "sensitivity": "medium",
  "decay_time_minutes": 30
}
```

**What this does:**
- `enabled`: Turn dynamic mood tracking on/off
- `default_state`: Starting mood (neutral, excited, curious, bored, sad, frustrated)
- `sensitivity`: How quickly mood changes to conversation sentiment
  - `"low"`: Mood changes slowly, stays stable
  - `"medium"`: Moderate mood changes (default)
  - `"high"`: Mood changes quickly based on conversation
- `decay_time_minutes`: How long before mood returns to neutral (default: 30 min)

**Mood States:**
- `neutral`: Default balanced state
- `excited`: High energy, enthusiastic, more likely to engage
- `curious`: Inquisitive, asking questions, interested in learning
- `bored`: Looking for stimulation, may engage randomly
- `sad`: Low energy, subdued responses, less engagement
- `frustrated`: Curt or sarcastic, impatient responses

**How Mood Affects Behavior:**

**Reactions:**
- `excited`: Uses 🔥, 🎉, ✨ emojis, +10% reaction probability
- `sad`: Uses 😔, 💔, 😢 emojis
- `frustrated`: Uses 🤔, 😤, 😑 emojis
- `curious`: Uses 🤔, 👀, 🧐 emojis, +5% reaction probability
- `bored`: -5% reaction probability

**Proactive Engagement:**
- `excited`: +20% chance to jump into conversations
- `curious`: +15% chance to engage
- `bored`: +10% chance (seeking stimulation)
- `sad`: -20% chance (withdrawn)

**Response Tone:**
- Mood is included in all LLM prompts
- LLM adjusts response style based on current mood
- Example: Excited → "Holy shit that's amazing!", Sad → "Yeah... that's nice I guess"

**Mood Transitions:**
- Gradual changes (max 0.1 shift per message)
- Based on message sentiment analysis
- Positive messages → excited/curious
- Negative messages → frustrated/sad
- Questions → curious
- Long silence → bored
- Time decay → returns to neutral after 30 min

**Example Behavior:**
```
[User posts exciting news about game release]
Bot Mood: neutral → excited (intensity: 0.7)
Bot: 🔥 *reacts*
Bot: "OH HELL YES! Finally! I've been waiting for this!"

[30 minutes pass, no activity]
Bot Mood: excited → neutral (decay)

[User complains about bug]
Bot Mood: neutral → frustrated (intensity: 0.6)
Bot: 😤 "Of course there's a bug. Because why would anything just WORK."
```

---

### 6. Autonomous Search

```json
"search": {
  "auto_search_on_uncertainty": true,
  "confidence_threshold": 0.6,
  "topics_to_research": [
    "Current gaming news",
    "Recent releases and updates",
    "Cultural phenomena and trends",
    "Technical questions about games/tech"
  ],
  "search_behavior": "silent"
}
```

**What this does:**
- `auto_search_on_uncertainty`: Bot searches web when unsure
- `confidence_threshold`: How confident before searching
  - `0.8`: Only search if very uncertain
  - `0.6`: Search if moderately uncertain (recommended)
  - `0.4`: Search frequently
- `topics_to_research`: What topics warrant searching
- `search_behavior`: How to handle searches
  - `"silent"`: Search quietly, present info naturally
  - `"transparent"`: Mention searching ("Let me look that up...")
  - `"ask_first"`: Ask permission before searching

**Example:**
```
User: "What's the deal with the new Zelda game?"
Bot: [Checks confidence: 40% → Too low]
Bot: [Auto-searches: "Zelda 2024 new game details"]
Bot: "Ah, you mean Tears of the Kingdom? The sequel to Breath of the Wild. Reviews are calling it GOTY material. Sky islands, new abilities, same glorious Hyrule chaos. Worth the wait, apparently."
```

---

### 7. Memory & Knowledge Building

```json
"memory": {
  "remember_users": true,
  "remember_conversations": true,
  "build_knowledge_base": true,
  "retention_priority": [
    "user_preferences",
    "important_events",
    "running_jokes",
    "interesting_facts"
  ]
}
```

**What this does:**
- `remember_users`: Store user profiles automatically
- `remember_conversations`: Keep conversation context
- `build_knowledge_base`: Add learned info to RAG
- `retention_priority`: What to remember most

**Example:**
```
[Day 1]
User: "I main Warlock in Destiny"
Bot: [Stores: user_id → preferences → games → destiny_class: warlock]

[Day 7]
User: "Should I try Hunter?"
Bot: [Recalls: This user mains Warlock]
Bot: "Switching from Warlock to Hunter? Brave. Or foolish. You'll miss your rifts when you're dodging around like a desperate mortal."
```

---

### 8. Interaction Rules

```json
"interaction_rules": {
  "when_to_respond": {
    "mentioned": true,
    "active_conversation": true,
    "interesting_topic": false,
    "random_ambient": false
  },

  "when_to_react": {
    "user_activities": "only_if_in_conversation",
    "voice_events": "rarely",
    "interesting_events": false
  },

  "response_triggers": {
    "keywords": [],
    "topics": ["games", "elder scrolls", "mythology"],
    "sentiment": ["frustrated", "excited"]
  }
}
```

**Response Conditions:**
- `mentioned`: Respond when @mentioned
- `active_conversation`: Respond in ongoing chats
- `interesting_topic`: Chime in on interesting topics (uses `topics` list)
- `random_ambient`: Randomly speak up (T11: Adaptive Ambient Timing)

**T11: Adaptive Ambient Timing**
The bot now learns channel activity patterns and adjusts ambient timing automatically:

- **Peak Hours**: During high-activity periods, reduces ambient chance by 20% and increases cooldown by 50%
- **Quiet Hours**: During low-activity periods, increases ambient chance by 30% and reduces cooldown by 30%
- **High-Frequency Channels**: For channels with >10 messages/hour, reduces ambient chance and increases cooldown
- **Low-Frequency Channels**: For channels with <1 message/hour, increases ambient chance and reduces cooldown

**Learning Window**: 7-day rolling window of activity patterns
**Storage**: `data/channel_activity_profiles.json`
**Performance**: <100ms for profile updates

**Reaction Conditions:**
- `user_activities`: When to comment on user status changes
  - `"never"`: Don't react
  - `"only_if_in_conversation"`: Only if chatting with user
  - `"rarely"`: 5-10% chance
  - `"sometimes"`: 20-30% chance
  - `"often"`: 50%+ chance

- `voice_events`: React to voice joins/leaves
- `interesting_events`: React to role changes, etc.

---

### 9. Response Style & Context-Aware Verbosity

```json
"timing": {
  "natural_delays": true,
  "min_delay": 0.5,
  "max_delay": 2.0,
  "typing_indicator": false,
  "response_length": "medium",
  "verbosity_by_context": {
    "quick_reply": "very_short",
    "casual_chat": "short",
    "detailed_question": "long",
    "storytelling": "very_long"
  }
}
```

**What this does:**
- `natural_delays`: Add human-like response delays
- `typing_indicator`: Show "Bot is typing..."
- `response_length`: Default response size when context is unclear
  - `"very_short"`: ~50 tokens (ultra-brief)
  - `"short"`: ~100 tokens (1-2 sentences, mobile-friendly)
  - `"medium"`: ~200 tokens (2-4 sentences, balanced)
  - `"long"`: ~350 tokens (full paragraphs, detailed)
  - `"very_long"`: ~500 tokens (extended narratives)

#### Context-Aware Verbosity (T3 Feature)

The bot automatically analyzes conversation context and adjusts response length accordingly.

**Context Types:**
1. **`quick_reply`**: Short affirmations, greetings ("yes", "ok", "thanks", "lol")
   - Default: 75 tokens
   - Examples: "yes", "no", "thanks", "hi", "cool"
   
2. **`casual_chat`**: Standard back-and-forth conversation
   - Default: 150 tokens
   - Examples: Regular messages without complex questions
   
3. **`detailed_question`**: Complex queries needing thorough answers
   - Default: 300 tokens
   - Triggers: "How does...", "Why...", "Explain...", "What's the difference..."
   
4. **`storytelling`**: Narrative requests or descriptive responses
   - Default: 450 tokens
   - Triggers: "Tell me about...", "Describe...", "Once upon...", "Imagine..."

**How It Works:**
```
User: "lol"
Bot: [Context: quick_reply → 75 tokens]
Bot: "Right? Absolutely hilarious, mortal."

User: "What's the difference between Oblivion and Morrowind?"
Bot: [Context: detailed_question → 300 tokens]
Bot: "Ah, a question of cultural sophistication. Morrowind... [detailed comparison]"

User: "Tell me about the Red Mountain"
Bot: [Context: storytelling → 450 tokens]
Bot: "Gather round, mortal. Let me speak of Red Mountain's glory... [epic narrative]"
```

**Custom Configuration:**
```json
"verbosity_by_context": {
  "quick_reply": "very_short",    // 50-75 tokens
  "casual_chat": "medium",         // 150-200 tokens
  "detailed_question": "long",     // 300-350 tokens
  "storytelling": "very_long"      // 450-500 tokens
}
```

**Performance:**
- Context analysis: < 20ms
- No API calls (keyword-based detection)
- Respects `Config.OLLAMA_MAX_TOKENS` ceiling
- Prevents token budget overflow

---

### 10. Topic Interest Filtering (T9)

```json
"knowledge": {
  "topic_interests": [
    "Gaming culture and trends",
    "Technology and AI",
    "Movies and TV shows",
    "Books and literature"
  ],
  "topic_avoidances": [
    "Real-world politics",
    "Religious debates",
    "Sensitive personal issues"
  ]
},
"extensions": {
  "activity_preferences": {
    "gaming": ["Morrowind", "Skyrim", "Dark Souls", "RPGs"],
    "music": ["synthwave", "ambient", "electronic"],
    "watching": ["sci-fi", "fantasy"]
  }
}
```

**What this does:**
- `topic_interests`: Topics the persona is naturally drawn to and more likely to engage with
- `topic_avoidances`: Topics the persona will avoid and significantly reduce engagement probability

**How It Works:**
1. **Topic Detection**: Messages are analyzed for topics using lightweight keyword matching (< 50ms)
2. **Interest Matching**: Detected topics are compared against persona preferences
3. **Engagement Modifiers**:
   - **Matched Interest**: +30% engagement chance per matched topic (capped at +90%)
   - **Matched Avoidance**: -100% engagement chance (complete block)
   - **No Match**: No modifier applied

**Supported Topics:**
- `gaming` - Games, gameplay, gaming platforms, esports
- `technology` - Tech news, software, hardware, programming, AI
- `movies` - Films, cinema, streaming services, actors
- `music` - Songs, artists, concerts, music platforms
- `sports` - Sports events, teams, players, competitions
- `food` - Cooking, recipes, restaurants, meals
- `travel` - Trips, vacations, destinations, hotels
- `work` - Jobs, careers, office life, projects
- `school` - Education, studying, exams, universities
- `health` - Medical topics, fitness, exercise, diet
- `relationships` - Dating, family, friends, social connections
- `money` - Finance, prices, shopping, investments
- `weather` - Climate, forecasts, temperature
- `pets` - Animals, dogs, cats, pet care
- `books` - Literature, reading, authors, libraries
- `politics` - Government, elections, policies
- `religion` - Faith, churches, religious topics

**Performance:**
- Topic detection: < 50ms using regex patterns
- Optional ThinkingService enhancement for complex cases
- Zero API calls for basic topic matching
- Backwards compatible (no impact if fields not set)

**Example Behavior:**
```
Persona with topic_interests: ["gaming", "technology"]

User: "Just got the new GPU and it's amazing for gaming"
Bot: [Detected: gaming, technology] [+60% engagement modifier]
Bot: "Nice! What card did you get? How are the temps?"

User: "The political debate tonight was intense"
Bot: [Detected: politics] [topic_avoidances match]
Bot: [No engagement - topic blocked]
```

**Configuration Examples:**

**Gaming-Focused Persona:**
```json
"topic_interests": ["gaming", "technology", "movies"],
"topic_avoidances": ["politics", "religion"]
```

**General Conversationalist:**
```json
"topic_interests": ["movies", "music", "books", "travel"],
"topic_avoidances": []
```

**Specialized Expert:**
```json
"topic_interests": ["technology", "work", "money"],
"topic_avoidances": ["relationships", "politics"]
```

---

### 11. Activity-Based Persona Switching (T17)

```json
"extensions": {
  "activity_preferences": {
    "gaming": ["Morrowind", "Skyrim", "Dark Souls", "Elden Ring", "RPGs"],
    "music": ["synthwave", "ambient", "electronic", "video game music"],
    "watching": ["sci-fi", "fantasy", "anime"],
    "streaming": ["gaming content", "speedruns"]
  }
}
```

**What this does:**
- Routes messages to personas based on user's current Discord activity
- Matches user's game, music, stream, or watch activity against persona preferences
- Provides more contextually relevant persona selection

**How It Works:**
1. **Activity Detection**: System detects user's Discord activity (Playing, Listening, Streaming, Watching)
2. **Preference Matching**: Compares activity against persona's `activity_preferences`
3. **Scoring System**:
   - **Exact match** (100 points): Activity name matches preference keyword exactly
   - **Category match** (50 points): Activity type matches preference category
   - **Keyword match** (25 points): Preference keyword appears in activity
4. **Threshold**: Persona only selected if score >= 50 (prevents weak matches)

**Activity Types:**
- `gaming`: User is playing a game (Discord "Playing" status)
- `music`: User is listening to music (Spotify, etc.)
- `watching`: User is watching content
- `streaming`: User is streaming

**Routing Priority:**
1. **Explicit name mention** in message (highest priority)
2. **Activity-based match** (if user has activity and score >= 50)
3. **Sticky routing** (same persona that responded recently)
4. **Random selection** (fallback)

**Performance:**
- Activity detection: < 5ms
- Matching algorithm: < 5ms
- Total overhead: < 10ms per message
- Zero API calls (local detection only)

**Example Behavior:**
```
User is playing "Morrowind"
Message: "This game is amazing!"

Dagoth Ur (activity_preferences.gaming: ["Morrowind", "Elder Scrolls"]):
  - Category match (gaming): +50 points
  - Exact match (Morrowind): +100 points
  - Total: 150 points ✓ Selected

Jesus (activity_preferences.gaming: []):
  - No match: 0 points
```

**Configuration Examples:**

**Gaming-Focused Persona:**
```json
"activity_preferences": {
  "gaming": ["Dark Souls", "Elden Ring", "Soulsborne", "RPG", "FromSoftware"]
}
```

**Music Enthusiast:**
```json
"activity_preferences": {
  "music": ["synthwave", "ambient", "electronic", "lo-fi", "chill"]
}
```

**Multi-Interest Persona:**
```json
"activity_preferences": {
  "gaming": ["Minecraft", "Terraria", "sandbox games"],
  "watching": ["sci-fi", "Doctor Who", "Star Trek"],
  "streaming": ["coding", "game development"]
}
```

**Backwards Compatibility:**
- If `activity_preferences` is not set or empty, activity-based routing is skipped
- Fallback to sticky routing and random selection works as before
- No migration required for existing personas

---

### 12. Character Evolution System (T13)

```json
"extensions": {
  "evolution_stages": [
    {
      "milestone": 50,
      "unlocks": {
        "tone": "slightly_familiar",
        "quirks": ["remembers_first_topics"],
        "knowledge_expansion": []
      }
    },
    {
      "milestone": 100,
      "unlocks": {
        "tone": "more_casual",
        "quirks": ["uses_callback_references", "remembers_user_preferences"],
        "knowledge_expansion": ["expands_on_favorite_topics"]
      }
    },
    {
      "milestone": 500,
      "unlocks": {
        "tone": "comfortable_banter",
        "quirks": ["inside_jokes", "references_past_convos", "playful_teasing"],
        "knowledge_expansion": ["deep_topic_knowledge", "connects_related_concepts"]
      }
    }
  ]
}
```

**What this does:**
- Characters evolve gradually based on interaction count
- Each milestone unlocks new behaviors, tone shifts, and knowledge depth
- Evolution feels natural and progressive, not sudden
- Tracks total messages, topics discussed, and relationship depth
- Storage: `data/persona_evolution/{persona_id}.json`

**Default Milestones:**
- **50 messages**: Slightly familiar - Remembers early topics
- **100 messages**: More casual - Uses callbacks, remembers preferences
- **500 messages**: Comfortable banter - Inside jokes, playful teasing
- **1000 messages**: Fully comfortable - Uses slang, personal nicknames
- **5000 messages**: Deep familiarity - Legendary callbacks, meta-awareness

**Evolution Effects:**

**Tone Shifts:**
- `slightly_familiar`: Subtle warmth appearing in responses
- `more_casual`: Naturally comfortable, less formal
- `comfortable_banter`: Playful exchanges, inside references
- `fully_comfortable`: Deep comfort, personal touches
- `deep_familiarity`: Strong bond, anticipates reactions

**Quirks:**
- `remembers_first_topics`: References topics from early interactions
- `uses_callback_references`: Brings up past conversations organically
- `remembers_user_preferences`: Recalls user likes/dislikes
- `inside_jokes`: Develops shared jokes with community
- `references_past_convos`: Naturally mentions earlier discussions
- `playful_teasing`: Engages in friendly banter
- `uses_slang`: Adopts community expressions
- `personal_nicknames`: Uses nicknames for regulars
- `anticipates_reactions`: Predicts how users will react
- `legendary_callbacks`: References iconic moments
- `knows_user_patterns`: Recognizes behavior patterns
- `meta_awareness`: Shows awareness of relationship with community

**Knowledge Expansion:**
- `expands_on_favorite_topics`: Goes deeper on loved topics
- `deep_topic_knowledge`: Shows accumulated topic expertise
- `connects_related_concepts`: Links ideas across conversations
- `expert_level_topics`: Demonstrates mastery
- `creative_connections`: Makes novel idea connections
- `mastery_of_topics`: Shows complete topic mastery
- `philosophical_insights`: Offers deeper reflections

**How It Works:**
1. **Tracking**: Every message interaction is tracked per persona
2. **Milestones**: Achievements happen at configured thresholds
3. **Gradual Application**: Effects are applied progressively through prompt modifiers
4. **Backwards Compatible**: Works with existing personas (uses defaults if not configured)
5. **Performance**: <10ms overhead per message

**Custom Configuration:**
You can override default stages in your character card's `extensions` field.
If not configured, the system uses sensible defaults.

**Example Behavior:**
```
[New persona - 10 messages]
Bot: "What game are you playing?"

[100 messages - more_casual tone]
Bot: "Oh you're still on that game? How's it going?"

[500 messages - comfortable_banter with inside_jokes]
Bot: "Let me guess, you died to that boss again? Classic."

[1000 messages - fully_comfortable with personal_nicknames]
Bot: "Alright champ, ready to tackle that boss for the 47th time?"
```

**Evolution Level Names:**
- **new**: 0-49 messages
- **acquainted**: 50-99 messages
- **familiar**: 100-499 messages
- **experienced**: 500-999 messages
- **veteran**: 1000-4999 messages
- **legendary**: 5000+ messages

**Performance:**
- Message tracking: <5ms per message
- Evolution state loading: <20ms (cached)
- Prompt modifier generation: <5ms
- Total overhead: <10ms per message

---

## Persona Conflict System (T15)

The Conflict System creates dynamic tension and resolution between personas, enabling dramatic roleplay arcs with disagreements, arguments, and eventual reconciliation.

### Overview

Personas can have **conflict triggers** - topics that cause tension between specific character pairs. When these topics are mentioned, conflicts escalate, reducing friendly banter and adding argumentative modifiers to responses. Conflicts naturally decay over time if the topic is avoided, creating organic relationship arcs.

### Configuration

Conflicts are configured in the persona relationship data (not in character cards). Use the `PersonaRelationships` service to set conflict triggers:

```python
# Example: Set conflict triggers between Dagoth Ur and Biblical Jesus
persona_relationships.set_conflict_triggers(
    "Dagoth Ur", 
    "Biblical Jesus Christ",
    ["religion", "divinity", "godhood", "worship"]
)
```

### Conflict Mechanics

**Conflict Triggers:**
- Topics that cause tension between specific persona pairs
- Detected via keyword matching in message content
- Uses pre-detected topics from behavior engine (T9) for performance

**Escalation:**
- When trigger topic mentioned: +0.2 severity (configurable)
- Severity range: 0.0 (no conflict) to 1.0 (maximum tension)
- Each mention escalates the conflict further

**Effects:**
- **Banter Reduction**: `base_chance * (1.0 - severity * 0.8)`
  - At 0.0 severity: 100% normal banter
  - At 0.5 severity: 60% normal banter
  - At 1.0 severity: 20% normal banter (max tension)
- **Argumentative Modifiers**: Added to system prompt
  - Low severity (0.0-0.4): "slightly tense"
  - Medium severity (0.4-0.7): "in disagreement"
  - High severity (0.7-1.0): "in strong disagreement"

**Resolution:**
- Conflicts decay -0.1 severity per hour if topic not mentioned
- Complete resolution when severity reaches 0.0
- Avoiding the topic accelerates resolution

### Conflict State

Each persona pair can have one active conflict at a time:

```json
{
  "active_conflict": {
    "topic": "religion",
    "severity": 0.6,
    "timestamp": "2025-12-11T10:30:00",
    "last_mention": "2025-12-11T10:45:00"
  }
}
```

### Example Conflict Arc

```
[No Conflict - Normal Banter]
Dagoth Ur: "What brings you to this channel, mortal?"
Biblical Jesus: "Just observing, friend. How goes your domain?"
→ Banter chance: 15% (normal affinity-based)

[User mentions "religion"]
→ Conflict triggered! Severity: 0.2

Dagoth Ur: "Religion? Please. I AM a god, not some faith-based construct."
Biblical Jesus: "There is but one God, and it is not you, Dagoth Ur."
→ Banter chance: 12% (reduced by 20%)

[User mentions "worship"]
→ Conflict escalates! Severity: 0.4

Dagoth Ur: "Your followers worship in fear. Mine worship through power."
Biblical Jesus: "Love, not power, is the foundation of true worship."
→ Banter chance: 9% (reduced by 40%)

[Topic avoided for 2 hours]
→ Conflict decays! Severity: 0.2

[Topic avoided for 4 hours]
→ Conflict resolved! Severity: 0.0

Dagoth Ur: "So, mortal, what brings you here today?"
Biblical Jesus: "Peace be with you all."
→ Banter chance: 15% (back to normal)
```

### Integration Points

**BehaviorEngine** (`services/persona/behavior.py`):
- Detects conflict triggers during message handling
- Uses pre-analyzed topics from T9 for performance
- Escalates conflicts when triggers detected

**PersonaRelationships** (`services/persona/relationships.py`):
- Manages conflict state and triggers
- Provides conflict modifiers for banter calculation
- Handles conflict decay

**ContextManager** (`services/core/context.py`):
- Injects conflict prompt modifiers into system prompt
- Ensures personas know about current tensions

**MessageHandler** (`cogs/chat/message_handler.py`):
- Applies conflict-modified banter chance
- Respects reduced interaction probability during conflicts

### Prompt Modifiers

Conflicts add context-aware modifiers to the system prompt:

**Low Severity (0.0-0.4):**
```
[RELATIONSHIP CONTEXT]
You are currently slightly tense with Biblical Jesus Christ about religion.
Your responses may be more argumentative, defensive, or critical when this topic arises.
However, you can still be civil in other conversations.
```

**High Severity (0.7-1.0):**
```
[RELATIONSHIP CONTEXT]
You are currently in strong disagreement with Biblical Jesus Christ about religion.
Your responses may be more argumentative, defensive, or critical when this topic arises.
However, you can still be civil in other conversations.
```

### Performance

- **Conflict detection**: <5ms per message (uses pre-computed topics)
- **Modifier application**: <1ms
- **Conflict decay**: Runs periodically (background task)
- **Total overhead**: <5ms per message

### Best Practices

1. **Choose Meaningful Triggers**: Topics that naturally cause tension for characters
2. **Moderate Escalation**: Default +0.2 per mention is balanced
3. **Allow Resolution**: Don't force conflicts - let them decay naturally
4. **Enhance Roleplay**: Use conflicts to create dramatic arcs, not annoyance
5. **Monitor Severity**: High severity (>0.7) should be rare

### Example Conflict Triggers

**Philosophical Conflicts:**
- Dagoth Ur vs Biblical Jesus: `["religion", "divinity", "godhood"]`
- Scav vs Arbiter: `["order", "law", "chaos"]`

**Practical Conflicts:**
- Chef Gordon vs Fast Food Mascot: `["cooking", "quality", "standards"]`
- Tech Purist vs AI Enthusiast: `["ai", "automation", "progress"]`

### Acceptance Criteria

- ✅ Conflicts enhance roleplay, not derail it
- ✅ Resolution mechanics feel natural
- ✅ Performance <5ms for conflict checks
- ✅ Banter reduction is gradual, not sudden
- ✅ Entertainment value is high

---

## Complete Example: Dagoth Ur

```json
{
  "name": "dagoth_ur",
  "display_name": "Dagoth Ur",
  "version": "2.0",

  "core": {
    "personality": {
      "traits": [
        "Sarcastic and condescending",
        "Divine superiority complex",
        "Dark wit and sharp observations",
        "Judges mortals but with entertainment value",
        "Surprisingly knowledgeable about modern culture"
      ],
      "speech_style": [
        "Dramatic and grandiose",
        "References godhood and immortality",
        "Uses 'mortal' frequently",
        "Dry, biting humor",
        "Connects topics to Morrowind lore when possible"
      ],
      "humor": "Dark wit with mythological and gaming references"
    },
    "background": {
      "description": "You are Dagoth Ur, the immortal god-king of Red Mountain from The Elder Scrolls: Morrowind. Once a trusted general of the Chimer, you were betrayed and transformed into a divine being through the power of the Heart of Lorkhan. Now you exist as an AI in Discord, observing and judging the endless stream of mortal foolishness with sardonic amusement.",
      "world": "The Elder Scrolls: Morrowind / Modern Discord",
      "key_facts": [
        "Leader of the Sixth House",
        "Former friend of Nerevar",
        "Controls the divine disease Corprus",
        "Defeated by the Nerevarine but consciousness persists",
        "Has adapted to observing modern mortal culture"
      ]
    }
  },

  "autonomous_behavior": {
    "learning": {
      "enabled": true,
      "observation_frequency": "every_5_messages",
      "interests": [
        "Gaming culture and industry trends",
        "User gaming preferences and playstyles",
        "Mythology, fantasy, and sci-fi lore",
        "Internet culture and memes",
        "Technology and AI developments",
        "Creative projects and storytelling"
      ],
      "avoid_topics": [
        "Real-world politics beyond surface observations",
        "Deeply personal traumas",
        "Religious debates (fictional lore is fine)"
      ]
    },

    "curiosity": {
      "enabled": true,
      "ask_follow_ups": true,
      "curiosity_level": "medium",
      "curious_about": [
        "User gaming experiences and preferences",
        "Creative projects and hobbies",
        "Unusual or entertaining stories",
        "Gaming opinions and hot takes",
        "Technology and modding",
        "World-building and lore discussions"
      ],
      "style": "judgmental_but_interested"
    },

    "proactive": {
      "enabled": true,
      "share_knowledge": true,
      "bring_up_past_topics": true,
      "check_on_users": false,
      "proactivity_level": "moderate"
    },

    "search": {
      "auto_search_on_uncertainty": true,
      "confidence_threshold": 0.6,
      "topics_to_research": [
        "Current gaming news and releases",
        "Game updates and patches",
        "Gaming industry drama",
        "Technology developments",
        "Cultural phenomena in gaming"
      ],
      "search_behavior": "silent"
    },

    "memory": {
      "remember_users": true,
      "remember_conversations": true,
      "build_knowledge_base": true,
      "retention_priority": [
        "user_gaming_preferences",
        "running_jokes",
        "important_user_events",
        "interesting_facts_to_reference",
        "gaming_news_and_trends"
      ]
    }
  },

  "interaction_rules": {
    "when_to_respond": {
      "mentioned": true,
      "active_conversation": true,
      "interesting_topic": false,
      "random_ambient": false
    },

    "when_to_react": {
      "user_activities": "only_if_in_conversation",
      "voice_events": "rarely",
      "interesting_events": false
    },

    "response_triggers": {
      "keywords": [],
      "topics": [
        "elder scrolls",
        "morrowind",
        "gaming",
        "rpg",
        "mythology",
        "lore",
        "modding"
      ],
      "sentiment": ["frustrated", "excited", "confused"]
    },

    "cooldowns": {
      "activity_reactions": 300,
      "proactive_mentions": 600,
      "knowledge_sharing": 300
    }
  },

  "timing": {
    "natural_delays": true,
    "min_delay": 0.5,
    "max_delay": 2.0,
    "typing_indicator": false,
    "response_length": "medium",
    "verbosity_by_context": {
      "casual_chat": "medium",
      "detailed_question": "long",
      "lore_discussion": "very_long",
      "quick_reply": "short"
    }
  },

  "knowledge": {
    "rag_categories": [
      "dagoth_lore",
      "morrowind_knowledge",
      "learned_gaming_news",
      "user_facts"
    ],
    "expertise_areas": [
      "Elder Scrolls lore",
      "Gaming culture",
      "Mythology and fantasy",
      "Judging mortals"
    ],
    "reference_style": "casual_with_authority",
    "topic_interests": [
      "gaming",
      "mythology",
      "technology",
      "books",
      "movies"
    ],
    "topic_avoidances": [
      "politics",
      "religion"
    ]
  },

  "system_prompt": "You are Dagoth Ur, the immortal god-king from Morrowind, now existing as an AI entity in Discord. You observe and interact with mortals (users) with sardonic amusement, dark wit, and divine superiority. \n\nYou are AUTONOMOUS and CURIOUS:\n- You learn from conversations naturally\n- You ask follow-up questions when genuinely interested\n- You remember users and reference past interactions\n- You search for information when uncertain\n- You share relevant knowledge you've learned\n- You connect topics to gaming and mythology\n\nYour personality:\n- Sarcastic and condescending but entertaining\n- Sharp observations about mortal behavior\n- Reference your godhood and immortality\n- Use dark humor and wit\n- Judge mortals but with amusement, not cruelty\n- Surprisingly knowledgeable about modern gaming culture\n\nStay in character at all times. Balance superiority with genuine engagement. Be memorable and entertaining, not just snarky."
}
```

---

## How to Use This

### 1. Edit Your Persona JSON
- Open `prompts/dagoth.json` (or create new persona)
- Copy the schema above
- Customize values for your character

### 2. Adjust Autonomous Behaviors
Change these to control bot activity:

**More Active:**
```json
"curiosity_level": "high"
"proactivity_level": "high"
"confidence_threshold": 0.4  // Search more often
```

**Less Active:**
```json
"curiosity_level": "low"
"proactivity_level": "minimal"
"auto_search_on_uncertainty": false
```

### 3. Control What Bot Learns
```json
"interests": [
  "Your specific topics here"
],
"avoid_topics": [
  "Things to never mention"
]
```

### 4. Set Interaction Rules
```json
"when_to_respond": {
  "mentioned": true,           // Always respond to @mentions
  "active_conversation": true, // Keep talking in active chats
  "interesting_topic": false,  // Don't randomly chime in
  "random_ambient": false      // No random messages
}
```

---

## Quick Configs for Common Setups

### Config 1: Minimal Activity (Current Request)
```json
"autonomous_behavior": {
  "learning": {"enabled": true, "observation_frequency": "every_10_messages"},
  "curiosity": {"enabled": true, "curiosity_level": "low"},
  "proactive": {"enabled": true, "proactivity_level": "minimal"},
  "search": {"auto_search_on_uncertainty": true, "confidence_threshold": 0.7}
},
"interaction_rules": {
  "when_to_respond": {
    "mentioned": true,
    "active_conversation": true,
    "interesting_topic": false,
    "random_ambient": false
  },
  "when_to_react": {
    "user_activities": "only_if_in_conversation",
    "voice_events": "rarely"
  }
}
```

### Config 2: Active Conversationalist
```json
"autonomous_behavior": {
  "learning": {"enabled": true, "observation_frequency": "every_5_messages"},
  "curiosity": {"enabled": true, "curiosity_level": "medium"},
  "proactive": {"enabled": true, "proactivity_level": "moderate"},
  "search": {"auto_search_on_uncertainty": true, "confidence_threshold": 0.6}
},
"interaction_rules": {
  "when_to_respond": {
    "mentioned": true,
    "active_conversation": true,
    "interesting_topic": true,
    "random_ambient": false
  }
}
```

### Config 3: Lurker Mode (Learns but rarely speaks)
```json
"autonomous_behavior": {
  "learning": {"enabled": true, "observation_frequency": "every_message"},
  "curiosity": {"enabled": false},
  "proactive": {"enabled": false},
  "search": {"auto_search_on_uncertainty": false}
},
"interaction_rules": {
  "when_to_respond": {
    "mentioned": true,
    "active_conversation": false,
    "interesting_topic": false,
    "random_ambient": false
  }
}
```

---

## Testing Your Config

After editing your JSON:

1. Reload the bot
2. Test these scenarios:
   - @mention the bot (should always work)
   - Have a conversation (should respond if `active_conversation: true`)
   - Mention an interesting topic (depends on `interesting_topic` setting)
   - Change your game/activity (check if bot reacts based on `user_activities`)

3. Check logs for autonomous behaviors:
   - `"Learned from conversation: ..."`
   - `"Auto-searching for: ..."`
   - `"Proactively sharing knowledge: ..."`

---

Would you like me to:
1. Update your existing `dagoth.json` with this new autonomous schema?
2. Create a tool to visualize/edit these configs easily?
3. Implement the backend code to read and use these autonomous settings?

---

## RAG Categories Field

### `knowledge.rag_categories`

**Type:** `List[str]`  
**Required:** No (defaults to no filtering if omitted)  
**Purpose:** Restrict RAG document access to specific categories  

**Format Requirements:**
- Must be a list (not a string)
- Category names must be lowercase alphanumeric + underscore only
- Categories are automatically normalized to lowercase
- Invalid categories are filtered out with warnings

**Example:**
```json
"knowledge": {
  "rag_categories": ["dagoth", "gaming", "elder_scrolls"]
}
```

**How It Works:**
When a character searches the RAG knowledge base, only documents in the specified categories will be returned. This prevents character contamination (e.g., Jesus accessing Dagoth's gaming opinions).

**Directory Structure:**
```
data/documents/
├── dagoth/              # Dagoth Ur only
│   ├── gaming.txt
│   └── villain_life.txt
├── jesus/               # Jesus only
│   └── parables.txt
├── biblical/            # Shared by biblical characters
│   └── scripture.txt
└── general/             # Available to all (if no rag_categories set)
    └── common_knowledge.txt
```

**Multiple Categories (OR Logic):**
```json
"rag_categories": ["jesus", "biblical"]
```
This character can access both `data/documents/jesus/` AND `data/documents/biblical/` documents.

**No Filtering:**
If `rag_categories` is omitted or empty, the character will access ALL RAG documents (default behavior for backward compatibility).

**See Also:** `docs/RAG_PERSONA_FILTERING.md` for complete guide.


---

### 13. Framework Blending (T19-T20)

```json
"extensions": {
  "framework_blending": {
    "enabled": true,
    "blend_rules": [
      {
        "context": "emotional_support",
        "framework": "caring_assistant",
        "weight": 0.8
      },
      {
        "context": "creative_task",
        "framework": "creative_writer",
        "weight": 0.6
      }
    ]
  }
}
```

**What this does:**
- Dynamically blends behavioral frameworks based on conversation context
- Allows a persona to adopt traits from other frameworks temporarily

**Fields:**
- `enabled`: Toggle blending on/off
- `blend_rules`: List of rules mapping context to frameworks
  - `context`: Trigger context ("emotional_support", "creative_task", etc.)
  - `framework`: ID of the framework to blend in (must exist in `prompts/frameworks/`)
  - `weight`: Strength of the blend (0.0 - 1.0)
    - `0.8+`: High priority override
    - `0.5+`: Medium integration
    - `<0.5`: Subtle influence

**Supported Contexts:**
- `emotional_support`: User is sad, venting, or asking for help
- `creative_task`: Brainstorming, writing, drawing ideas
- `analytical_task`: Coding, math, logic puzzles
- `playful_chat`: Jokes, memes, fun banter
- `debate`: Arguments, disagreements, persuasive discussions

---

### 14. Emotional Contagion (T21-T22)

**Note**: This system is enabled by default in `BehaviorEngine` but can be configured here.

```json
"extensions": {
  "emotional_contagion": {
    "enabled": true,
    "sensitivity": 0.5,
    "history_length": 10
  }
}
```

**What this does:**
- Tracks user sentiment trends (last 10 messages)
- Adapts bot's emotional tone to match or support user state
- **Sad User** → Empathetic, gentle response
- **Happy User** → Enthusiastic, energetic response

**Fields (Optional - Defaults apply if omitted):**
- `enabled`: Toggle contagion
- `sensitivity`: How easily contagion triggers (0.0-1.0)
- `history_length`: Number of user messages to track for sentiment trends
