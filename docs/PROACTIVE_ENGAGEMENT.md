# Proactive Engagement - Bot Jumps In When Interested! 🎯

The bot now **actively participates** in conversations when interesting topics come up - without needing to be @mentioned!

---

## 🎬 How It Works

The bot listens to conversations in configured channels. When it detects topics it's interested in, it **jumps in naturally** - just like a real person would!

### Example

```
User1: "I'm thinking about playing Halo tonight"
User2: "Oh nice, which one?"
User1: "Probably Halo 3, the campaign is so good"

Bot: "Oh! I love Halo! The co-op campaign is amazing!"
[Bot jumped in - not @mentioned, just interested!]
```

---

## 🎯 Interest Levels

The bot has different interest levels for various topics:

### High Interest (80-90% engagement rate)
- **Gaming** (0.8): Games, video games, esports
- **AI** (0.9): Artificial intelligence, LLMs, ChatGPT
- **Programming** (0.8): Coding, development, Python, JavaScript
- **Space** (0.8): Astronomy, NASA, SpaceX, planets
- **Discord Bots** (0.9): Bot development, Discord.py

### Moderate Interest (50-70%)
- **Movies & TV** (0.5): Films, series, Netflix
- **Anime** (0.6): Anime, manga
- **Music** (0.5): Songs, albums, artists
- **Trivia** (0.7): Facts, quizzes
- **Science** (0.7): Physics, chemistry, research

### Lower Interest (30-40%)
- **Food** (0.3): Cooking, restaurants
- **Sports** (0.3): Football, basketball
- **Travel** (0.3): Vacations, trips
- **Fitness** (0.3): Gym, workouts

---

## ⚙️ How Engagement is Calculated

The bot decides whether to jump in based on:

### 1. **Topic Interest Level**
```python
"I'm playing Halo" → Gaming detected → 0.8 base score
```

### 2. **Multiple Topics Boost**
```python
"I'm coding a game in Python"
→ Programming (0.8) + Gaming (0.8)
→ Base score: 0.8 * 1.2 = 0.96 (very likely!)
```

### 3. **Mood Modifiers**
- **Excited mood**: 1.5x more likely to jump in
- **Playful mood**: 1.4x more likely
- **Energetic mood**: 1.3x more likely
- **Cheerful mood**: 1.2x more likely
- **Tired mood**: 0.6x less likely
- **Grumpy mood**: 0.4x much less likely

### 4. **Cooldown System**
- **3 minutes** between proactive engagements per channel
- Won't spam - gives conversation space

### 5. **Minimum Messages**
- Waits for **3 messages** before jumping in
- Doesn't interrupt too early

---

## 💬 Engagement Examples

### Gaming Topics
```
User: "Anyone want to play Valorant?"
Bot: "Oh! I love talking about games!"

User: "This boss fight is impossible"
Bot: "Ooh gaming! What are you playing?"

User: "Just got a new gaming PC"
Bot: "Wait, gaming? Count me in for this conversation!"
```

### AI/Tech Topics
```
User: "ChatGPT is getting really good"
Bot: "Oh! AI stuff! Now you've got my attention!"

User: "I'm learning machine learning"
Bot: "Wait, AI? This is literally my thing!"
```

### Programming
```
User: "This Python bug is driving me crazy"
Bot: "Oh! Code talk! What are you working on?"

User: "Just pushed to GitHub"
Bot: "Ooh programming! I'm interested!"
```

### Space/Science
```
User: "Did you know Mars has ice caps?"
Bot: "Oh! Space stuff! Did you know space is HUGE?"

User: "The James Webb telescope images are amazing"
Bot: "Ooh astronomy! Space is so cool!"
```

---

## 🎭 Mood Affects Engagement

### Playful Mood Example
```
Chat: "I'm learning Python"
Bot (Playful, 1.4x boost): "Ooh Python! The snake or the code? 😄 Actually both are cool!"
```

### Tired Mood Example
```
Chat: "I'm learning Python"
Bot (Tired, 0.6x reduction): [Probably won't jump in - too tired]
```

### Excited Mood Example
```
Chat: "I'm learning Python"
Bot (Excited, 1.5x boost): "WAIT, Python?! That's awesome! What are you building?!"
```

---

## ⚡ Configuration

### Enable/Disable

```bash
# Enable proactive engagement
PROACTIVE_ENGAGEMENT_ENABLED=true

# Minimum messages before bot can jump in (default: 3)
PROACTIVE_MIN_MESSAGES=3

# Cooldown between engagements in seconds (default: 180 = 3 minutes)
PROACTIVE_COOLDOWN=180
```

### Channel Control

Proactive engagement only works in **AMBIENT_CHANNELS**:

```bash
# Bot will only proactively engage in these channels
AMBIENT_CHANNELS=123456789,987654321

# Leave empty to disable
AMBIENT_CHANNELS=
```

This gives you full control over where the bot can jump in!

---

## 🎯 Topic Detection

The bot detects topics through **keyword matching**:

```python
"I'm playing Halo tonight"
→ Detects: ["playing", "Halo", "game"]
→ Topic: gaming

"I'm coding in Python"
→ Detects: ["coding", "Python"]
→ Topic: programming + coding

"NASA launched a new rocket to Mars"
→ Detects: ["NASA", "rocket", "Mars"]
→ Topic: space
```

Over **250+ keywords** tracked across all topics!

---

## 🚫 Smart Spam Prevention

### Won't Jump In When:
1. ❌ Music is playing
2. ❌ Less than 3 messages in conversation
3. ❌ Within 3-minute cooldown
4. ❌ Not in configured AMBIENT_CHANNELS
5. ❌ Bot is in Grumpy/Tired mood (low chance)
6. ❌ User is in AMBIENT_IGNORE_USERS list

### Will Jump In When:
1. ✅ Interesting topic detected
2. ✅ Score threshold met (based on interest + mood)
3. ✅ Cooldown expired
4. ✅ In configured channel
5. ✅ Conversation has momentum (3+ messages)

---

## 📊 Statistics

Track proactive engagement:

```python
stats = ambient_mode.proactive.get_stats()

# Returns:
{
    "total_engagements": 15,
    "tracked_channels": 2,
    "recent_engagements": [
        {
            "channel_id": 123,
            "topics": ["gaming", "ai"],
            "time": "2025-01-22T15:30:00"
        }
    ]
}
```

---

## 🎨 AI-Generated vs Template Responses

### AI-Generated (If Ollama available)
Bot uses AI to create contextual, natural responses:
```
Context: Users discussing Halo co-op
Bot: "Oh! Halo co-op is the best! Have you tried Legendary difficulty? It's brutal but so satisfying!"
```

### Template Responses (Fallback)
If AI unavailable, uses templates:
```
"Oh! I love talking about games!"
"Ooh gaming! What are you playing?"
"Wait, gaming? Count me in!"
```

---

## 🔥 Full Example

### Scenario: Gaming conversation, bot in Playful mood

```
14:00 - User1: "Anyone free tonight?"
14:00 - User2: "Yeah what's up?"
14:01 - User1: "Want to play Halo co-op?"

Bot detects:
- ✅ Topic: gaming (0.8 interest)
- ✅ Mood: playful (1.4x boost)
- ✅ Final score: 0.8 * 1.4 = 1.12 → caps at 1.0
- ✅ 3 messages passed
- ✅ No recent engagement
- ✅ In configured channel

14:01 - Bot: "Oh! Halo co-op! Now we're talking! 🎮 Which campaign?"
[Bot naturally jumped in!]

14:02 - User1: "Let's do Halo 3"
14:02 - Bot: [Won't jump in again - just engaged]
[3-minute cooldown active]
```

---

## 🎯 Customizing Interests

Want to adjust what the bot cares about? Edit `services/proactive_engagement.py`:

```python
self.topic_interests = {
    "gaming": 0.8,        # Increase to 0.9 for more engagement
    "food": 0.3,          # Increase to 0.7 if bot is a foodie!
    "custom_topic": 0.8,  # Add your own topics!
}
```

---

## 🌟 Key Benefits

1. **Feels Alive** - Bot participates like a real user
2. **Contextual** - Only jumps in when genuinely interested
3. **Mood-Aware** - Engagement matches emotional state
4. **Smart Cooldowns** - Won't spam or dominate conversation
5. **Customizable** - Control channels, topics, and frequency
6. **Natural** - AI-generated responses fit conversation flow

---

## ⚠️ Important Notes

### This is NOT:
- ❌ A response to @mentions (that's regular chat)
- ❌ Active in all channels (only AMBIENT_CHANNELS)
- ❌ Guaranteed to trigger (probability-based)
- ❌ A replacement for commands

### This IS:
- ✅ Proactive participation in conversations
- ✅ Topic and mood-based engagement
- ✅ Natural, human-like jumping in
- ✅ Respectful of conversation flow

---

## 🚀 Try It Out!

1. Set `AMBIENT_CHANNELS` to your chat channel IDs
2. Enable `PROACTIVE_ENGAGEMENT_ENABLED=true`
3. Have a conversation about gaming, AI, or coding
4. Watch the bot naturally jump in!

Example test:
```
You: "I'm thinking about learning Python"
Friend: "Oh cool, for what?"
You: "Maybe some AI stuff"

Bot: "Oh! AI and coding! That's awesome! Python is great for AI - so many libraries!"
```

---

**Generated with Claude Code** 🤖
**Feature**: Proactive Engagement
**Impact**: High - Makes bot feel like a real participant!
