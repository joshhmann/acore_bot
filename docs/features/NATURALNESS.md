# Naturalness Features

Complete guide to all features that make the bot feel more natural and human-like.

## Table of Contents

1. [Mood System](#mood-system)
2. [Self-Awareness](#self-awareness)
3. [Environmental Awareness](#environmental-awareness)
4. [Rhythm Matching](#rhythm-matching)
5. [Conversational Callbacks](#conversational-callbacks)
6. [Response Variations](#response-variations)
7. [Configuration](#configuration)

---

## Mood System

**Status**: ⚠️ Code exists but not loaded/active
**Files**: `services/mood_system.py`

### Overview
The bot has dynamic emotional states that change based on time, interactions, and events.

### 10 Mood Types
- **Energetic** ⚡ - High energy, enthusiastic
- **Cheerful** 😊 - Upbeat, positive
- **Calm** 😌 - Peaceful, balanced
- **Tired** 😴 - Low energy, subdued
- **Grumpy** 😤 - Irritable, short responses
- **Playful** 😄 - Fun, witty
- **Thoughtful** 🤔 - Philosophical, introspective
- **Excited** 🤩 - Pumped up!
- **Melancholic** 😔 - Subdued, reflective
- **Focused** 🎯 - Sharp, on-point

### Mood Triggers
- **Time of day**: Grumpy in morning, energetic midday, melancholic late night
- **User interactions**: Positive → Cheerful, Negative → Grumpy
- **Events**: Trivia won → Excited, Error → Grumpy, Music → Cheerful

### What It Affects
- Response verbosity (short vs long)
- Emoji usage
- Exclamation marks
- Response speed/timing
- Overall tone

### Mood Duration
- Energetic: 30 minutes
- Cheerful: 45 minutes
- Calm: 2 hours
- Tired: 20 minutes
- Grumpy: 15 minutes
- Playful: 30 minutes
- Thoughtful: 40 minutes
- Excited: 20 minutes
- Melancholic: 25 minutes
- Focused: 35 minutes

### API
```python
from services.mood_system import MoodSystem, MoodType

mood_system = MoodSystem()

# Set mood based on event
mood_system.update_from_event("trivia_won")  # → Excited

# Get current mood
mood = mood_system.get_current_mood()
print(f"{mood.mood.value} (intensity: {mood.intensity})")

# Get style guide for responses
style = mood_system.get_style_guide()
# {
#   "verbosity": "high",
#   "emoji_use": "very_frequent",
#   "exclamation_chance": 0.7,
#   "capitalization_chance": 0.3
# }
```

---

## Self-Awareness

**Status**: ✅ Implemented
**Files**: `services/self_awareness.py`

### Overview
The bot knows it's a bot and can make self-referential comments.

### Features
- **Mistake acknowledgment**: "Oops!" "My bad!" when errors occur
- **Self-referential comments**: "Did that make sense?" "Hope that helps!"
- **Feature awareness**: Comments on its TTS, voice recognition
- **Quality self-assessment**: Knows when responses are too long/short
- **Repetition detection**: Notices when it uses words too much

### Example Comments
- "Did that joke land or should I stick to my day job?"
- "Hope my voice didn't crack there"
- "My ears are being weird today"
- "Oops, brain fart moment there"
- "That came out weird..."

---

## Environmental Awareness

**Status**: ⚠️ Code exists but appears incomplete
**Files**: `services/environmental_awareness.py`

### Overview
The bot notices and comments on changes in voice channels.

### Voice Events Detected
- **User joins voice** (30% chance): "Oh hey Sarah, you just hopped in! 👋"
- **User leaves voice** (15% chance): "Later Sarah!"
- **User switches channels** (5% chance): "Sarah moved to Gaming"
- **User unmutes** (3% chance): "Oh, Sarah is back!"
- **Gathering** (3+ people, 20% chance): "Ooh, looks like the whole squad is in voice!"

### Voice Context in Chat
```
User: "Anyone want to play?"
Bot sees: [Voice activity: Jake, Sarah, Mike in Gaming]
Bot: "Looks like Jake, Sarah, and Mike are already in voice - want to join them?"
```

### Cooldown System
To prevent spam:
- Join/leave comments: 2 minutes per user
- Audio change comments: 5 minutes per user
- Gathering comments: 10 minutes per channel

---

## Rhythm Matching

**Status**: ✅ Implemented
**Files**: `services/rhythm_matching.py`

### Overview
The bot adapts its response style to match the pace and energy of the conversation.

### Detects Conversational Patterns
- **Fast-paced**: Short messages, rapid replies → Bot matches with concise responses
- **Thoughtful**: Long messages, slower pace → Bot gives detailed responses
- **Energetic**: Multiple people, quick exchanges → Bot is more energetic
- **Chill**: Slow, relaxed conversation → Bot is calm and casual

### Response Adaptation
```python
# Fast-paced conversation
User: "lol"
User: "that's hilarious"
User: "wait what"
Bot: "Haha yeah! 😄"  # Short, quick response

# Thoughtful conversation
User: "I've been thinking about the nature of consciousness..."
Bot: "That's a really interesting question. Let me share my thoughts..."  # Long, detailed
```

---

## Conversational Callbacks

**Status**: ✅ Implemented
**Files**: `services/proactive_callbacks.py`

### Overview
The bot remembers past topics and brings them up naturally later.

### Features
- Remembers interesting topics from past conversations
- Brings up topics when relevant (15% chance during ambient responses)
- Creates natural conversation continuity
- "Hey, remember we were talking about Python yesterday? I thought of something..."

### How It Works
1. Bot identifies interesting topics during conversations
2. Stores topics with context and timestamp
3. During lull periods, may reference past topics
4. Creates feeling of ongoing relationship

### Example
```
Day 1:
User: "I'm learning React"
Bot: "Nice! React is great for building UIs"

Day 2 (ambient mode):
Bot: "Hey, how's the React learning going? Did you get that component working?"
```

---

## Response Variations

**Status**: ✅ Implemented
**Files**: `services/naturalness.py`

### Overview
Adds natural human-like speech patterns to responses.

### Patterns Added
- **Hesitations** (15% chance): "Uh...", "Well...", "Hmm..."
- **Corrections**: "Actually...", "Wait...", "Let me rephrase..."
- **Fillers**: "you know", "I think", "kind of", "basically"
- **Self-aware endings**: "Hope that makes sense!", "Not my best explanation..."

### Before/After
**Before**: "That's a great question about Python!"
**After**: "Hmm... That's a great question about Python! Hope that helps!"

---

## Configuration

### Environment Variables

```bash
# Mood System (currently disabled)
MOOD_SYSTEM_ENABLED=false

# Environmental Awareness (status unclear)
ENVIRONMENTAL_AWARENESS_ENABLED=true

# Proactive Engagement
PROACTIVE_ENGAGEMENT_ENABLED=true
PROACTIVE_CALLBACK_CHANCE=0.15

# Naturalness (response variations)
NATURALNESS_ENABLED=true
HESITATION_CHANCE=0.15
FILLER_CHANCE=0.10
```

### Config.py Settings

```python
# Ambient mode and proactive features
AMBIENT_MODE_ENABLED = True
AMBIENT_MODE_COOLDOWN_MINUTES = 30
AMBIENT_MODE_LULL_THRESHOLD_MINUTES = 15

# Response timing
NATURAL_TYPING_DELAY_ENABLED = True
MIN_TYPING_DELAY = 0.5
MAX_TYPING_DELAY = 2.0
```

---

## Integration Example

```python
# In your bot's message handler
from services.naturalness import NaturalnessService
from services.rhythm_matching import RhythmMatcher
from services.proactive_callbacks import ProactiveCallbacksSystem

# Initialize services
naturalness = NaturalnessService()
rhythm = RhythmMatcher()
callbacks = ProactiveCallbacksSystem()

# Generate response
response = await ollama.chat(prompt, history)

# Add naturalness patterns
response = naturalness.add_natural_patterns(response)

# Match conversational rhythm
style = rhythm.get_conversation_style(recent_messages)
response = rhythm.adapt_response(response, style)

# Check for callbacks (ambient mode)
if should_do_callback():
    callback = await callbacks.get_relevant_callback(context)
    if callback:
        response = callback

return response
```

---

## Future Enhancements

Potential improvements:
- [ ] Activate mood system (currently not loaded)
- [ ] Fix/complete environmental awareness
- [ ] Mood visualization in web dashboard
- [ ] User commands to query bot's mood (`/mood`)
- [ ] Mood persistence across bot restarts
- [ ] Learning from user feedback on responses
- [ ] Persona-specific mood tendencies
- [ ] Voice tone changes based on mood
