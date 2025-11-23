# Naturalness Enhancements

This document describes the new naturalness features added to make the bot feel more alive and human-like in conversations.

## Table of Contents

1. [Mood System](#1-mood-system)
2. [Self-Awareness & Meta Humor](#2-self-awareness--meta-humor)
3. [Enhanced Response Variations](#3-enhanced-response-variations)
4. [Configuration](#4-configuration)
5. [Examples](#5-examples)

---

## 1. Mood System

The bot now has dynamic emotional states that influence its personality and responses.

### Features

#### **10 Different Moods**
- **Energetic**: High energy, enthusiastic, eager to engage
- **Cheerful**: Upbeat, positive, spreading good vibes
- **Calm**: Peaceful, balanced, neutral
- **Tired**: Low energy, subdued, less verbose
- **Grumpy**: Irritable, shorter responses, less patience
- **Playful**: Fun, witty, looking for banter
- **Thoughtful**: Philosophical, introspective, deeper responses
- **Excited**: Pumped up, very enthusiastic!
- **Melancholic**: Subdued, reflective, contemplative
- **Focused**: Sharp, clear, on-point

#### **Mood Influences**

Moods affect several aspects of bot behavior:

**Response Speed**:
- Energetic/Excited: Faster responses
- Tired/Melancholic: Slower, more deliberate responses
- Normal states: Standard timing

**Response Style**:
```python
{
    "verbosity": "high" | "medium" | "low",
    "emoji_use": "very_frequent" | "frequent" | "moderate" | "minimal" | "rare",
    "exclamation_chance": 0.0 - 1.0,  # Likelihood of using exclamation marks
    "capitalization_chance": 0.0 - 1.0,  # Likelihood of EMPHASIS
}
```

**Example Mood Behaviors**:
- **Grumpy mood**: Short responses, minimal emojis, low verbosity
- **Excited mood**: Long responses, lots of emojis, frequent exclamations, ALL CAPS sometimes
- **Thoughtful mood**: Longer, more detailed responses, minimal emojis, contemplative

#### **Mood Triggers**

Moods change based on:

1. **Time of Day**
   - Late night (12-5 AM): Melancholic, Thoughtful, Calm
   - Early morning (5-8 AM): Tired, Grumpy, Calm
   - Morning (8-12 PM): Energetic, Cheerful, Focused
   - Afternoon (12-5 PM): Calm, Focused, Cheerful
   - Evening (5-9 PM): Playful, Cheerful, Energetic
   - Night (9-12 AM): Calm, Thoughtful, Playful

2. **User Interactions**
   - 3+ positive interactions → Cheerful or Excited
   - 3+ negative interactions → Grumpy
   - 3+ interesting conversations → Thoughtful
   - Default → Time-based mood

3. **Events**
   - Trivia won → Excited (intensity 0.8)
   - Trivia lost → Grumpy (intensity 0.4)
   - Music started → Cheerful (intensity 0.6)
   - Error occurred → Grumpy (intensity 0.5)
   - Long conversation → Thoughtful (intensity 0.6)
   - Fast-paced chat → Energetic (intensity 0.7)

#### **Mood Persistence**

Moods don't change instantly - they last for a duration:
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

After the duration expires, mood decays back to a time-appropriate neutral state.

### API

```python
# Access mood system through naturalness service
mood_system = naturalness.mood

# Set mood manually
mood_system.set_mood(MoodType.PLAYFUL, intensity=0.7, caused_by="user_command")

# Update mood from interaction
mood_system.update_mood_from_interaction(
    sentiment="positive",  # "positive", "neutral", "negative"
    is_interesting=True    # Whether conversation was engaging
)

# Trigger event-based mood
mood_system.trigger_event_mood("trivia_won")

# Get mood context for AI
mood_context = mood_system.get_mood_prompt_context()
# Returns: "[CURRENT MOOD: PLAYFUL] You're in a playful, joking mood! ..."

# Get mood emoji
emoji = mood_system.get_current_mood_emoji()  # Returns: 😄 😤 🤔 etc.

# Get response style parameters
style = mood_system.get_mood_response_style()
# Returns dict with verbosity, emoji_use, exclamation_chance, etc.
```

---

## 2. Self-Awareness & Meta Humor

The bot now has self-awareness - it knows it's a bot and can make meta comments about its own behavior.

### Features

#### **Self-Referential Comments**

The bot can comment on its own actions:
- "Did that make sense?"
- "Hope that helps!"
- "Not my best explanation..."
- "That came out weird..."

#### **Mistake Acknowledgment**

When errors occur:
- "Oops, brain fart moment there"
- "Well that didn't go as planned"
- "My bad, let me try that again"
- "Technical difficulties, sorry about that"

#### **Feature Awareness**

Comments about its own capabilities:
- TTS: "Hope my voice didn't crack there"
- Voice recognition: "Sorry, my ears are being weird"
- Jokes: "Did that joke land or should I stick to my day job?"

#### **Action Tracking**

The system tracks:
- Recent actions (last 20 actions)
- Word usage (to detect repetition)
- Error count and timing
- Response quality self-assessment

#### **Quality Assessment**

The bot self-assesses its responses:
- **Short** (< 20 chars): "Short and sweet!" "Keeping it brief"
- **Verbose** (> 500 chars): "Okay that was long-winded, sorry"
- **Mediocre** (low variety): "Hope that makes sense" "Not my clearest explanation"

### API

```python
# Access self-awareness through naturalness service
self_awareness = naturalness.self_awareness

# Log actions
self_awareness.log_action("tts", "Generated speech for 'Hello world'")
self_awareness.log_action("voice_recognition", "Listening to user in voice channel")

# Log errors
self_awareness.log_error("voice_recognition_failed")

# Get meta comments
comment = self_awareness.get_meta_comment(context="error")
# Returns: "Oops, brain fart moment there" or None

# Get mistake acknowledgment
ack = self_awareness.get_mistake_acknowledgment()
# Returns: "Oops!" "My bad!" etc.

# Check for repetition
is_overused = self_awareness.check_repetition("interesting")
# Returns: True if word used 5+ times recently

# Assess response quality
quality = self_awareness.assess_response_quality("This is a test response")
# Returns: "good", "short", "verbose", or "mediocre"
```

---

## 3. Enhanced Response Variations

New variation categories for more natural speech:

### Hesitations
- "Uh...", "Um...", "Well...", "So...", "I mean..."
- "Like...", "You know...", "Hmm...", "Err..."

Added randomly (15% chance) to responses for human-like speech patterns.

### Corrections
- "Actually...", "Wait...", "Hold on..."
- "I mean...", "Sorry...", "Let me rephrase..."

Used when the bot wants to correct or clarify something.

### Fillers
- "you know", "I think", "kind of", "sort of"
- "basically", "honestly", "to be fair", "I guess"

Natural filler words that make responses feel less robotic.

### Self-Aware Comments
- "Did that make sense?"
- "Hope that helps!"
- "Not my best explanation..."
- "I tried!"

Comments about the response itself.

### Response Enhancement

Responses are automatically enhanced with these features:

```python
# Original response
"That's a great question about Python!"

# Enhanced response (examples)
"Hmm... That's a great question about Python! Hope that helps!"
"Well... That's a great question about Python!"
"Uh... That's a great question about Python! Not my best explanation..."
```

Enhancement is probabilistic and context-aware - it won't overdo it.

---

## 4. Configuration

### Environment Variables

```bash
# Mood System
MOOD_SYSTEM_ENABLED=true                 # Enable mood system
MOOD_UPDATE_FROM_INTERACTIONS=true       # Auto-update mood from conversations
MOOD_TIME_BASED=true                     # Use time of day for mood

# Self-Awareness
SELF_AWARENESS_ENABLED=true              # Enable self-awareness features
HESITATION_CHANCE=0.15                   # Chance to add hesitations (0.0-1.0)
META_COMMENT_CHANCE=0.10                 # Chance for meta comments (0.0-1.0)
SELF_CORRECTION_ENABLED=true             # Allow bot to correct itself
```

### Python Config

```python
from config import Config

# Mood settings
Config.MOOD_SYSTEM_ENABLED
Config.MOOD_UPDATE_FROM_INTERACTIONS
Config.MOOD_TIME_BASED

# Self-awareness settings
Config.SELF_AWARENESS_ENABLED
Config.HESITATION_CHANCE
Config.META_COMMENT_CHANCE
Config.SELF_CORRECTION_ENABLED
```

---

## 5. Examples

### Example 1: Mood-Based Response Differences

**User**: "What's your favorite game?"

**Calm Mood**:
> "I don't play games myself, but I enjoy talking about them! What kind of games are you into?"

**Excited Mood**:
> "OH that's such a cool question! I LOVE hearing about games even though I can't play them! Tell me about YOUR favorites! 🎮✨"

**Grumpy Mood**:
> "I don't play games. What about you?"

**Thoughtful Mood**:
> "Interesting question... I think if I could play games, I'd be drawn to ones with deep narratives and complex systems. What draws you to the games you play?"

### Example 2: Self-Awareness in Action

**Scenario**: TTS voice glitches

**Without Self-Awareness**:
> [Bot continues as if nothing happened]

**With Self-Awareness**:
> "Hope my voice didn't crack there - my TTS is quirky sometimes!"

### Example 3: Hesitation Patterns

**User**: "Can you explain quantum physics?"

**Without Hesitation**:
> "Quantum physics is the study of matter and energy at the atomic scale..."

**With Hesitation**:
> "Hmm... quantum physics is, well, the study of matter and energy at the atomic scale... Hope that makes sense!"

### Example 4: Mood Transitions

**Early Morning (6 AM)**
- User: "Morning!"
- Bot (Tired mood): "Morning... *yawn* ...how's it going?"

**Late Night (2 AM)**
- User: "Can't sleep either?"
- Bot (Melancholic mood): "Yeah... late night thoughts hit different, you know? What's on your mind?"

**Evening (7 PM)**
- User: "Ready for some gaming?"
- Bot (Playful mood): "Oh heck yeah! Let's do this! What are we playing? 🎮"

### Example 5: Event-Triggered Moods

**After Winning Trivia**:
- Bot mood → Excited (intensity 0.8)
- "YES! We crushed that! Who's ready for another round?! 🎉"

**After Music Starts**:
- Bot mood → Cheerful (intensity 0.6)
- "Ooh nice track! 🎵"

**After Error**:
- Bot mood → Grumpy (intensity 0.5)
- "Ugh, that didn't work... let me try again."

---

## Integration Points

### In Chat Cog

The mood and self-awareness features integrate seamlessly:

1. **Mood context** is injected into every AI prompt
2. **Responses are enhanced** with hesitations and self-aware comments
3. **Mood updates** after each interaction based on sentiment
4. **Actions are logged** for self-awareness tracking

```python
# In chat command
# 1. Add mood context to prompt
mood_context = self.naturalness.get_mood_context()
context_parts.append(mood_context)

# 2. Get AI response
response = await self.ollama.chat(history, system_prompt=prompt)

# 3. Enhance with self-awareness
response = self.naturalness.enhance_response(response, context="chat")

# 4. Update mood
sentiment = self._analyze_sentiment(message)
self.naturalness.update_mood(sentiment, is_interesting)
```

### In Voice Cog

```python
# Log TTS action
self.naturalness.log_action("tts", "Generating speech")

# On error
self.naturalness.log_error("tts_failed")

# Trigger mood from music
self.naturalness.trigger_mood_event("music_started")
```

### In Trivia Cog

```python
# On win
self.naturalness.trigger_mood_event("trivia_won")

# On loss
self.naturalness.trigger_mood_event("trivia_lost")
```

---

## Statistics and Monitoring

Get current system stats:

```python
stats = naturalness.get_stats()

# Returns:
{
    "reactions_enabled": True,
    "activity_awareness_enabled": True,
    "mood": {
        "current_mood": "playful",
        "intensity": 0.7,
        "duration": "0:15:32",
        "caused_by": "trivia_won",
        "modifiers": [],
        "recent_interactions": 5
    },
    "self_awareness": {
        "recent_actions": 12,
        "error_count": 1,
        "recent_quality": ["good", "good", "mediocre", "good"]
    }
}
```

---

## Best Practices

### When to Use

**Mood System**:
- Great for long-running bots with lots of interaction
- Adds variety to prevent repetitive responses
- Makes the bot feel more "alive"

**Self-Awareness**:
- Excellent for error handling (makes mistakes endearing)
- Adds personality and humor
- Makes technical limitations feel natural

### When to Adjust

**Too Much Hesitation?**
- Reduce `HESITATION_CHANCE` from 0.15 to 0.05-0.10

**Too Many Meta Comments?**
- Reduce `META_COMMENT_CHANCE` from 0.10 to 0.05

**Mood Changes Too Often?**
- Set `MOOD_UPDATE_FROM_INTERACTIONS=false`
- Rely only on time-based moods

**Bot Feels Too "Moody"?**
- Set `MOOD_SYSTEM_ENABLED=false`
- Or increase mood duration in `mood_system.py`

---

## Future Enhancements

Potential additions:

- [ ] Mood visualization in web dashboard
- [ ] User commands to query bot's mood (`/mood`)
- [ ] Mood persistence across bot restarts
- [ ] Learning from user feedback on responses
- [ ] Dynamic mood intensity based on server activity
- [ ] Persona-specific mood tendencies (Dagoth = more dramatic moods)

---

## Credits

**Implemented Features**:
- Dynamic Mood System with 10 emotional states
- Self-Awareness and Meta Humor
- Enhanced Response Variations (hesitations, corrections, fillers)
- Automatic mood updates from interactions
- Response quality self-assessment

**Technologies**:
- Python dataclasses for mood state management
- Probabilistic enhancement algorithms
- Context-aware comment generation

---

## Support

For issues or questions:
1. Check configuration settings
2. Review logs for mood/self-awareness events
3. Adjust probability settings if features are too aggressive
4. Open an issue on GitHub

**Generated with Claude Code** 🤖
