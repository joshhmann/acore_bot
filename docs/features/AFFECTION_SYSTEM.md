# Affection & Relationship System 💖

## Overview

Your bot now has a **dynamic affection system** like Neuro-sama! The bot develops real relationships with users, remembers what they say, and adjusts its personality based on how much it "likes" them.

## Features

### 1. **Affection Levels (0-100)**

The bot tracks how much it likes each user on a scale of 0-100:

- **0-19**: Stranger - Just met, polite but distant
- **20-39**: Acquaintance - Friendly, getting to know you
- **40-59**: Friend - Warm, playful, engaged
- **60-79**: Close Friend - Jokes around freely, shows genuine interest
- **80-100**: Best Friend - Super close, totally comfortable, inside jokes

### 2. **AI-Powered Sentiment Analysis**

After **every conversation**, the bot uses AI to analyze:
- **Sentiment**: Was the user positive, neutral, or negative?
- **Is Funny**: Did the user make a genuinely funny joke?
- **Is Interesting**: Was the conversation engaging?
- **Affection Change**: How much should affection increase/decrease (-5 to +5)

### 3. **Dynamic Personality**

The bot's personality **changes** based on affection level:

**Stranger (0-19):**
```
[Relationship: You just met CoolUser. Be polite but not overly familiar. You're a bit cautious around them.]
```

**Best Friend (80-100):**
```
[Relationship: CoolUser is your BEST FRIEND! You're super close, totally comfortable together, inside jokes are common. You genuinely enjoy talking to them.]
```

### 4. **Memorable Quotes**

The bot automatically saves funny, clever, or interesting things users say:

```json
{
  "memorable_quotes": [
    {
      "quote": "I'm not saying I'm Batman, but have you ever seen me and Batman in the same room?",
      "context": "Talking about secret identities...",
      "timestamp": "2025-10-26T16:45:00"
    }
  ]
}
```

### 5. **Interaction Tracking**

Every profile tracks:
- **Total messages** sent
- **Positive interactions** (friendly, appreciative)
- **Negative interactions** (rude, dismissive)
- **Last interaction** timestamp
- **Conversation quality** rolling average

## How It Works

### Affection Changes

**Positive Actions (+1 to +5):**
- Being friendly and engaging (+2)
- Making the bot laugh with a good joke (+3)
- Having interesting, thought-provoking conversations (+2)
- Appreciating the bot's responses (+1)

**Negative Actions (-1 to -5):**
- Being rude or dismissive (-2)
- Ignoring the bot (-1)
- Being mean or aggressive (-5)

**Neutral (+0):**
- Normal, everyday conversation
- Simple questions and answers

### Profile Structure

```json
{
  "user_id": 123456789,
  "username": "CoolGamer",
  "created_at": "2025-10-26T14:00:00",
  "interaction_count": 50,
  "traits": ["funny", "sarcastic", "tech-savvy"],
  "interests": ["gaming", "Halo", "Discord bots"],
  "facts": [
    {
      "fact": "Favorite game is Halo 3",
      "timestamp": "2025-10-26T15:00:00",
      "source": "conversation"
    }
  ],
  "affection": {
    "level": 65,
    "relationship_stage": "close_friend",
    "last_interaction": "2025-10-26T16:30:00",
    "positive_interactions": 40,
    "negative_interactions": 2,
    "conversation_quality": 8.5
  },
  "memorable_quotes": [
    {
      "quote": "I think Halo 3 is peak gaming, fight me",
      "context": "Discussing favorite games...",
      "timestamp": "2025-10-26T16:00:00"
    }
  ]
}
```

## Commands

### `/my_profile`
View your complete profile including:
- Message count and stats
- Personality traits
- Interests
- Preferences
- Affection level and relationship stage
- Last memorable quote

### `/relationship`
See detailed relationship status:
- Affection bar (visual indicator)
- Relationship stage description
- Positive/negative interaction counts
- How the bot feels about you

## Examples

### Example 1: Building a Friendship

**Day 1 - First Meeting:**
```
You: Hey what's up?
Bot: [Affection: 0, Stranger] Hey. Not much.
```

**After 10 friendly conversations:**
```
You: Yo what's good?
Bot: [Affection: 25, Acquaintance] Hey! Not much bro, just chillin. What about you?
```

**After 30 great conversations:**
```
You: YOOO
Bot: [Affection: 55, Friend] YOOO what's up dude!! Good to see you!
```

**After 50 amazing conversations:**
```
You: Wassup bestie
Bot: [Affection: 85, Best Friend] YOOO MY BOY!! Bro I was just thinking about you! What's good??
```

### Example 2: Memorable Moments

```
You: "I stayed up all night playing Halo and my mom thought I was studying lmao"
Bot: "HAHAHAHA that's hilarious bro! Classic gamer move!"

[Bot saves quote: "I stayed up all night playing Halo and my mom thought I was studying"]
[Affection +3 (funny)]
```

Later:
```
You: "I'm tired today"
Bot: "Bro didn't you stay up all night 'studying' aka playing Halo? LOL"
```

## Configuration

In your `.env`:

```env
# User Profiles
USER_PROFILES_ENABLED=true
USER_PROFILES_AUTO_LEARN=true
USER_AFFECTION_ENABLED=true      # Enable affection system
USER_CONTEXT_IN_CHAT=true
```

## Technical Details

### AI Sentiment Analysis

The bot uses a separate AI call after each chat to analyze sentiment:

```python
{
  "sentiment": "positive",      # positive, neutral, negative
  "is_funny": true,            # Did user make a joke?
  "is_interesting": true,       # Was conversation engaging?
  "affection_change": +3       # Suggested change (-5 to +5)
}
```

### Relationship Stages

Affection levels automatically determine relationship stage:

| Level | Stage | Bot Behavior |
|-------|-------|--------------|
| 0-19 | Stranger | Polite, cautious, formal |
| 20-39 | Acquaintance | Friendly, conversational |
| 40-59 | Friend | Warm, playful, engaged |
| 60-79 | Close Friend | Jokes freely, genuine interest |
| 80-100 | Best Friend | Super comfortable, inside jokes |

### Context Injection

The bot receives relationship context in every prompt:

```
[Current time: 04:30 PM, Sunday, October 26, 2025]
[User Info: User: CoolGamer
Personality: funny, sarcastic
Interests: Halo 3, gaming
Known facts: Favorite game is Halo 3]
[Relationship: CoolGamer is your close friend! You care about them, joke around freely, and show genuine interest. You appreciate their company.]
[Style: Match the conversation's energy...]

[PERSONA PROMPT GOES HERE]
```

## Performance

- **Minimal Latency**: Affection updates happen after responding (non-blocking)
- **Cached Profiles**: Profiles loaded once per session, then cached
- **Efficient AI Calls**: Uses low temperature (0.3) for consistent, fast extraction
- **No External APIs**: Everything runs locally through Ollama

## Privacy

- All profiles stored locally in `data/user_profiles/`
- No external services used
- Users can request profile deletion manually
- Profiles are per-Discord-ID, not username

## Future Enhancements

Potential features:
- [ ] Decay over time (affection slowly decreases if user doesn't chat)
- [ ] Special events (birthdays, anniversaries)
- [ ] User-to-user relationships (bot knows who's friends with who)
- [ ] Personality compatibility scores
- [ ] Achievement system (milestones like "First Friend", "100 Chats", etc.)
- [ ] Mood system (bot has good/bad days that affect responses)
- [ ] Voice tone changes based on affection (more enthusiastic for friends)

---

**You now have a Neuro-sama-style bot that builds real relationships with users! 🎉**
