# Advanced Naturalness Features

Complete guide to Environmental Awareness, Conversational Rhythm Matching, and Conversational Callbacks.

## Table of Contents

1. [Environmental Awareness](#1-environmental-awareness)
2. [Conversational Rhythm Matching](#2-conversational-rhythm-matching)
3. [Conversational Callbacks](#3-conversational-callbacks)
4. [Integration Examples](#4-integration-examples)
5. [Configuration](#5-configuration)

---

## 1. Environmental Awareness

The bot now notices and comments on changes in its environment, especially voice channel activity.

### Features

#### **Voice Channel Monitoring**

The bot tracks who's in voice channels and can comment on:

**User Joins Voice** (30% chance):
- "Oh hey Sarah, you just hopped in! 👋"
- "Sarah joined! What's up?"
- "Hey Sarah! 🎧"
- "Oh nice, Sarah is here!"

**User Leaves Voice** (15% chance):
- "Later Sarah!"
- "Bye Sarah! 👋"
- "See ya Sarah!"

**User Switches Channels** (5% chance):
- "Sarah moved to Gaming Voice"
- "Oh, Sarah switched channels"

**User Unmutes** (3% chance):
- "Oh, Sarah is back!"
- "Unmuted! What's up Sarah?"

**Gathering Detection**:
When 3+ people gather in voice (20% chance):
- "Ooh, looks like the whole squad is in voice!"
- "Party in voice channel! 🎉"
- "Everyone's gathering in voice!"

#### **Voice Context in Chat**

The bot is aware of voice activity when responding to chat:

```
User: "Anyone want to play?"
Bot sees: [Voice activity: Jake, Sarah, Mike in Gaming]
Bot: "Looks like Jake, Sarah, and Mike are already in voice - want to join them?"
```

#### **Cooldown System**

To prevent spam, comments have cooldowns:
- Join/leave comments: 2 minutes per user
- Audio change comments: 5 minutes per user
- Gathering comments: 10 minutes per channel

### API

```python
# Access through naturalness service
environmental = naturalness.environmental

# Handle voice state update
comment = await environmental.on_voice_state_update(member, before, after)

# Get voice channel state
state = environmental.detect_voice_channel_state(guild)
# Returns:
{
    "total_users": 3,
    "active_channels": 1,
    "channels": [
        {
            "name": "Gaming",
            "users": 3,
            "members": ["Jake", "Sarah", "Mike"]
        }
    ]
}

# Get voice context for AI
context = environmental.get_voice_context(guild)
# Returns: "[Voice activity: Jake, Sarah, Mike in Gaming]"
```

---

## 2. Conversational Rhythm Matching

The bot adapts its response style to match the pace and energy of the conversation.

### Features

#### **Rhythm Analysis**

The bot analyzes:
- **Message rate** (messages per minute)
- **Average message length**
- **Recent activity** (last 30 seconds)
- **Energy level** (high/moderate/low/idle)

#### **Pace Detection**

**Very Fast** (6+ messages/min):
- Keep responses SHORT (max 100 chars)
- 1 sentence max
- Use abbreviations
- Fast response speed

**Fast** (3-6 messages/min):
- Concise responses (max 150 chars)
- 1-2 sentences
- Quick, snappy replies

**Moderate** (1-3 messages/min):
- Normal responses (max 300 chars)
- 2-3 sentences

**Slow** (0.5-1 messages/min):
- More detailed (max 400 chars)
- 3-4 sentences
- Take your time

**Very Slow** (<0.5 messages/min):
- Thoughtful, detailed responses (max 500 chars)
- Feel free to elaborate

#### **Energy Matching**

**High Energy** (5+ messages in last 30s):
- Match the excitement!
- Use emojis
- Fast responses

**Moderate Energy** (3-4 messages):
- Normal energy level
- Balanced tone

**Low Energy** (1-2 messages):
- Calmer, more relaxed
- Less exclamatory

**Idle** (0 messages):
- Gentle, relaxed tone
- No pressure

#### **Automatic Style Adjustment**

The bot injects style guidance into prompts based on rhythm:

```
[CHAT PACE: VERY FAST - Keep responses SHORT (max 100 chars).
Chat is moving quickly - be brief and punchy. 1 sentence max.]
[Energy is HIGH - match the excitement!]
```

### API

```python
# Access through naturalness service
rhythm = naturalness.rhythm

# Track messages
rhythm.track_message(channel_id, message_length=45)

# Analyze rhythm
analysis = rhythm.analyze_rhythm(channel_id)
# Returns:
{
    "pace": "fast",
    "verbosity": "moderate",
    "energy": "high",
    "messages_per_minute": 4.5,
    "avg_message_length": 67,
    "recent_activity": 6
}

# Get recommended style
style = rhythm.get_recommended_style(channel_id)
# Returns:
{
    "max_length": 150,
    "min_length": 30,
    "sentences": 1,
    "use_emojis": True,
    "use_abbreviations": False,
    "response_speed": "fast"
}

# Get style prompt for AI
prompt = rhythm.get_style_prompt(channel_id)

# Check if conversation is fast-paced
is_fast = rhythm.is_conversation_fast_paced(channel_id)

# Check if conversation is energetic
is_energetic = rhythm.is_conversation_energetic(channel_id)
```

---

## 3. Conversational Callbacks

The bot remembers and references past conversation topics naturally.

### Features

#### **Topic Extraction**

The bot automatically extracts topics from messages:

Tracked topics:
- Gaming
- Food
- Coding
- Music
- Movies/TV
- Work
- Exercise
- Travel
- Weather

Example:
```
User: "I'm going to play some Halo later"
Bot extracts: ["gaming"]
Bot tracks: {topic: "gaming", user: "Jake", time: now, snippet: "..."}
```

#### **Callback Opportunities**

When a topic is mentioned again later (5 mins - 24 hours), the bot can reference it:

**Earlier Today**:
```
User (10 AM): "I need to fix this Python bug"
User (3 PM): "Finally got some time to code"
Bot: "Oh yeah! How's that Python bug going? Get it sorted?"
```

**Natural Callbacks** (20% chance when topic matches):
```
[CALLBACK OPPORTUNITY: Jake mentioned gaming earlier.
You could naturally reference that if relevant.]
```

The AI then decides whether to use it:
- "Speaking of gaming earlier, did you end up playing Halo?"
- "Oh nice! Coding time - like you mentioned this morning"

#### **Follow-up Questions**

The bot can proactively ask about past topics (10% chance):

**Gaming**:
- "How did that gaming session go, Jake?"
- "Did you end up playing that game, Jake?"

**Food**:
- "Did you get that food you wanted, Jake?"
- "How was the food, Jake?"

**Work**:
- "How's work going, Jake?"
- "Did that work thing get sorted out, Jake?"

**Coding**:
- "Did you fix that bug, Jake?"
- "How's the coding going, Jake?"

#### **Recent Context**

The bot includes recent topics in its context:

```
[Recent conversation topics: gaming, food, coding]
```

This helps the AI be aware of what's been discussed.

#### **RAG Integration**

If conversation summarizer is enabled, callbacks can also reference:
- Conversations from days/weeks ago
- Stored memories in RAG
- Past discussions from conversation summaries

```
[PAST CONVERSATIONS: You might recall:
- Last week discussed Halo co-op plans with Jake
- Previous conversation about Python debugging tips]
```

### API

```python
# Initialize
from services.conversational_callbacks import ConversationalCallbacks

callbacks = ConversationalCallbacks(history_manager, summarizer)

# Track topics
await callbacks.track_conversation_topic(
    channel_id=123,
    message="I'm playing Halo",
    user_name="Jake"
)

# Check for callback opportunity
callback_prompt = await callbacks.get_callback_opportunity(
    channel_id=123,
    current_message="Want to game?"
)
# Returns: "[CALLBACK OPPORTUNITY: Jake mentioned gaming earlier...]" or None

# Get recent context
context = await callbacks.get_recent_context(channel_id=123, max_topics=5)
# Returns: "[Recent conversation topics: gaming, food]"

# Find related memories from RAG
memories = await callbacks.find_related_memories(
    current_message="How do I fix this bug?",
    channel_id=123
)
# Returns: "[PAST CONVERSATIONS: You might recall: - ...]" or None

# Check if bot should ask follow-up
followup = await callbacks.should_ask_followup(channel_id=123)
# Returns: "How did that gaming session go, Jake?" or None

# Get conversation continuity context
continuity = callbacks.get_conversation_continuity_context(channel_id=123)
# Returns: "[Ongoing conversation - context is fresh]"
```

---

## 4. Integration Examples

### Full Chat Flow

```python
async def chat(interaction, message):
    channel_id = interaction.channel_id
    user_name = str(interaction.user.name)

    # 1. Track message rhythm
    naturalness.track_message_rhythm(channel_id, len(message))

    # 2. Track conversation topics
    await callbacks.track_conversation_topic(channel_id, message, user_name)

    # 3. Build context parts
    context_parts = []

    # Add rhythm-based style
    rhythm_prompt = naturalness.get_rhythm_style_prompt(channel_id)
    if rhythm_prompt:
        context_parts.append(rhythm_prompt)

    # Add callback opportunities
    callback_prompt = await callbacks.get_callback_opportunity(channel_id, message)
    if callback_prompt:
        context_parts.append(callback_prompt)

    # Add recent topics
    recent_context = await callbacks.get_recent_context(channel_id)
    if recent_context:
        context_parts.append(recent_context)

    # Add voice context
    if interaction.guild:
        voice_context = naturalness.get_voice_context(interaction.guild)
        if voice_context:
            context_parts.append(voice_context)

    # 4. Generate response with context
    full_prompt = "\n".join(context_parts) + "\n\n" + system_prompt
    response = await ollama.chat(history, system_prompt=full_prompt)
```

### Voice Event Handling

```python
# In main.py
async def on_voice_state_update(self, member, before, after):
    # Get environmental comment
    comment = await self.naturalness.on_voice_state_update(member, before, after)

    if comment:
        # Send to appropriate channel
        channel = guild.system_channel
        await channel.send(comment)
```

---

## 5. Configuration

### Environment Variables

No additional config needed! These features use existing settings:

```bash
# Existing settings that affect new features
NATURALNESS_ENABLED=true
AMBIENT_CHANNELS=123456789  # Where to send voice comments
```

### Python Config

All features are automatically enabled when `NATURALNESS_ENABLED=true`.

---

## Examples in Action

### Example 1: Fast-Paced Chat

```
10:00 AM - Jake: "yo"
10:00 AM - Sarah: "hey"
10:00 AM - Mike: "sup"
10:00 AM - Jake: "game?"
10:00 AM - Sarah: "yeah"

Bot detects: Very fast pace (6 msgs/min), high energy

User: "what should we play?"
Bot: "Halo! 🎮" [Short, 1 sentence, emoji]
```

### Example 2: Slow Thoughtful Chat

```
3:00 PM - Jake: "I'm thinking about learning Rust"
[15 minutes pass]
3:15 PM - Sarah: "Rust is great for systems programming"
[20 minutes pass]

Bot detects: Very slow pace, moderate energy

3:35 PM - Jake: "What makes Rust good?"
Bot: "Rust is excellent for systems programming because of its memory safety guarantees without garbage collection. It's particularly well-suited for performance-critical applications, and the compiler catches a lot of bugs at compile-time rather than runtime. The learning curve is steep, but the language forces you to write safe, concurrent code from the start." [Detailed, multiple sentences]
```

### Example 3: Conversation Callbacks

```
Morning:
10:00 AM - Jake: "I need to fix this Python asyncio bug"
Bot: "Good luck with that! Asyncio can be tricky"

Afternoon:
3:00 PM - Jake: "Finally have time to code"
Bot: "Oh nice! How's that Python asyncio bug going? Get it sorted?"
[Callback to morning conversation]
```

### Example 4: Voice + Chat Integration

```
[Jake joins voice channel "Gaming"]
Bot in chat: "Oh hey Jake, you just hopped in! 👋"

[Sarah and Mike join]
Bot in chat: "Ooh, looks like the whole squad is in voice!"

User in chat: "Want to do a raid?"
Bot sees: [Voice activity: Jake, Sarah, Mike in Gaming]
Bot: "Perfect timing! Everyone's already in voice - let's do it! 🎮"
```

### Example 5: Rhythm + Mood + Callbacks Combined

```
Scenario: Fast-paced evening chat, bot is in Playful mood, gaming was discussed earlier

Detection:
- Rhythm: Fast pace (4 msgs/min), high energy
- Mood: Playful (from evening time + positive interactions)
- Callback: Gaming mentioned 2 hours ago

User: "what game?"
Bot receives context:
- [CHAT PACE: FAST - Keep responses concise (max 150 chars)]
- [CURRENT MOOD: PLAYFUL] You're in a playful, joking mood!
- [CALLBACK OPPORTUNITY: Jake mentioned gaming earlier]
- [Energy is HIGH - match the excitement!]

Bot: "Halo! You mentioned it earlier - still down? 🎮"
[Short, playful, references callback, matches energy]
```

---

## Statistics and Monitoring

```python
# Get all naturalness stats
stats = naturalness.get_stats()

# Returns:
{
    "reactions_enabled": True,
    "activity_awareness_enabled": True,
    "mood": {...},
    "self_awareness": {...},
    "environmental": {
        "tracked_guilds": 1,
        "total_voice_users": 3,
        "recent_comments": 5
    },
    "rhythm": {
        "tracked_channels": 2,
        "total_messages_tracked": 45
    }
}

# Get callback stats
callback_stats = callbacks.get_stats()
# Returns:
{
    "tracked_channels": 2,
    "total_topics_tracked": 23
}
```

---

## Best Practices

### Environmental Awareness

**Do**:
- Use in servers where voice activity is common
- Great for gaming communities
- Adds life to voice channels

**Don't**:
- Set cooldowns too low (will spam)
- Enable in very large servers without testing

### Rhythm Matching

**Do**:
- Improves chat flow significantly
- Makes bot feel more responsive
- Adapts to user preferences automatically

**Don't**:
- Ignore completely - it auto-adjusts!
- Override in all cases - let it adapt

### Conversational Callbacks

**Do**:
- Builds relationships over time
- Makes conversations feel continuous
- Great for regular users

**Don't**:
- Expect instant results - needs conversation history
- Use aggressively - 20% callback chance is good

---

## Troubleshooting

### "Bot never comments on voice"
- Check `AMBIENT_CHANNELS` is configured
- Ensure `NATURALNESS_ENABLED=true`
- Check bot has permission to send messages in target channel
- Remember: Comments are probabilistic (30% chance on join)

### "Responses don't match chat pace"
- Rhythm matching needs at least 2-3 messages to analyze
- Check that naturalness service is initialized
- Verify rhythm tracking is being called

### "No callbacks happening"
- Callbacks need 5+ minutes between topic mentions
- Only 20% chance when opportunity exists
- Requires message history to extract topics
- Check that callbacks service is initialized

---

## Future Enhancements

Potential additions:
- [ ] Configurable callback frequency
- [ ] More sophisticated topic extraction (NLP/ML)
- [ ] Voice channel activity patterns (detect gaming sessions)
- [ ] Time-based rhythms (mornings vs evenings)
- [ ] User-specific rhythm preferences
- [ ] Cross-channel topic tracking

---

## Credits

**Implemented Features**:
- Environmental Awareness (voice channel monitoring)
- Conversational Rhythm Matching (adaptive response styles)
- Conversational Callbacks (topic tracking and references)

**Technologies**:
- Discord.py voice state events
- Statistical analysis for rhythm detection
- Keyword extraction for topic tracking
- Probabilistic callback triggering

---

**Generated with Claude Code** 🤖
