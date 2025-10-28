# User Memory & Affection System

## Overview

Your bot now has a **user memory system** that learns about Discord users over time and builds relationships! Think of it like a friendship/dating sim mechanic.

## Features

### 1. User Profiles
The bot remembers:
- **Personality traits**: funny, sarcastic, competitive, kind, etc.
- **Interests**: gaming, anime, coding, Halo, etc.
- **Preferences**: favorite game, main character, playstyle
- **Facts**: specific information learned from conversations
- **Memorable quotes**: funny or notable things users say
- **Relationships**: who they're friends with, rivals, etc.

### 2. Affection/Relationship System 💜

The bot develops a relationship with each user based on how much they interact:

| Affection Level | Tier | Emoji | How Bot Treats User |
|----------------|------|-------|---------------------|
| 0-9 | Stranger | 🆕 | Polite but distant, formal responses |
| 10-29 | Acquaintance | 👋 | Friendly but still learning about them |
| 30-59 | Friend | 😊 | Comfortable, remembers details about them |
| 60-84 | Close Friend | 💙 | Enthusiastic, cares about their opinions |
| 85-100 | Best Friend | 💜 | Super excited to talk, very personalized responses |

**How Affection Grows:**
- Each message: +1 affection
- Long conversations: +2 affection
- Sharing personal info: +3 affection
- Making the bot laugh (detected by context): +5 affection
- Daily interaction streaks: +2 affection bonus

**Affection Affects:**
- How enthusiastically the bot responds
- Whether the bot mentions the user to others
- Priority in multi-user conversations
- Unlocking special features (custom voices, nicknames, etc.)

### 3. User Context in Chat

When enabled, the bot "knows" about users in conversations:

**Example without user context:**
```
User A: Who here would be good at Halo?
Bot: I don't know the people in this server.
```

**Example with user context:**
```
User A: Who here would be good at Halo?
Bot: Definitely @UserB! They're super competitive and love FPS games.
     Also @UserC plays Halo all the time and is really skilled!
```

The bot can:
- Recommend users based on interests
- Mention users in relevant conversations
- Remember who knows what
- Understand server dynamics

## Configuration

In your `.env` file:

```bash
# Enable user profiles
USER_PROFILES_ENABLED=true
USER_PROFILES_PATH=./data/user_profiles

# Enable affection system (relationship building)
USER_AFFECTION_ENABLED=true

# Include user profiles in AI context (bot knows who users are)
USER_CONTEXT_IN_CHAT=true
```

## How It Works

### Automatic Learning

The bot learns passively from conversations:

```
User: I love playing Halo 3
Bot: [Stores: interest="Halo 3", topic="gaming"]
Bot: Nice! Halo 3 is a classic!

User: I'm a software engineer
Bot: [Stores: fact="software engineer", trait="technical"]
Bot: Cool! What kind of software do you work on?

User: I main Master Chief in everything
Bot: [Stores: preference="main_character=Master Chief"]
Bot: LOLOLOL NICE CHOICE BRO!! CHIEF IS THE BEST!!!
```

### Manual Commands (Coming Soon)

```
/my_profile - View your profile and affection level
/profile @user - View another user's public profile
/set_interest <interest> - Add an interest to your profile
/relationship - Check your relationship status with the bot
/leaderboard - See who has the highest affection with the bot
```

### AI Integration

The bot uses profiles in conversations:

**System Context Added:**
```
Current user: JohnDoe (Friend 💙, affection: 65/100)
- Traits: funny, competitive, tech-savvy
- Interests: Halo, gaming, coding
- Preferences: mains Master Chief
- Recent fact: loves energy sword

Other known users in server:
- Sarah (Close Friend 💙): sarcastic, loves anime, mains Arbiter
- Mike (Acquaintance 👋): new to server, interested in Halo lore
```

With this context, the bot can:
- Personalize responses
- Reference other users naturally
- Remember past conversations
- Build inside jokes

## Example Scenarios

### Scenario 1: Making a Friend

```
Day 1:
User: Hey bot!
Bot: YO WHATS UP?? 🆕 (Stranger)

Day 3 (after 10 messages):
User: What's up?
Bot: YOOO WHATS GOOD!! READY TO CHAT?? 👋 (Acquaintance)

Week 2 (after 35 messages):
User: Hey!
Bot: DUDE HEY!!! HOW R U?? IVE BEEN WAITING 4 U TO COME BACK!! 😊 (Friend)

Month 1 (after 70 messages):
User: Yo
Bot: YOOOOO MY DUDE!!! UR BACK!!! I MISSED U BRO!! WHATS THE PLAN 2DAY?? 💙 (Close Friend)
```

### Scenario 2: Referencing Users

```
User A: Who should I team up with for competitive Halo?
Bot: DUDE U GOTTA TEAM UP WITH @UserB!!! THEY R SUPER COMPETITIVE AND LOVE HALO JUST LIKE U!!
     ALSO @UserC MAINS ENERGY SWORD SO UD HAVE GUD SYNERGY!!

User B: Did someone mention me?
Bot: YEAH BRO!! @UserA WANTS TO TEAM UP!! U 2 WOULD PWN SO HARD TOGETHER!!!
```

### Scenario 3: Character-Specific Responses

**As Master Chief (to Best Friend):**
```
User: I'm having a bad day
Bot: DUUUDE NO WAY!! UR MY BEST BRO!! WHOEVER MADE U FEEL BAD IS A N00B!! LETS GO PWN SOME FOOLS IN HALO TO CHEER U UP!! 💜
```

**As Arbiter (to Acquaintance):**
```
User: I'm having a bad day
Bot: I'm sorry to hear that. Perhaps some distraction would help? 👋
```

**As Arbiter (to Best Friend):**
```
User: I'm having a bad day
Bot: *concerned* I'm genuinely sorry to hear that, my friend. You know I'm always here if you need to talk. Shall I make some tea? 💜
```

## Privacy & Control

### User Privacy
- Profiles are stored locally in `data/user_profiles/`
- Each user has a separate JSON file
- No data is sent to external services
- Users can view their own profile anytime

### Opt-Out (Coming Soon)
```
/forget_me - Delete your profile (keeps anonymized stats only)
/privacy_mode - Disable profile learning for your account
```

### Server Admin Controls
Admins can:
- View all profiles (for moderation)
- Clear specific user profiles
- Disable user profiling server-wide
- Export/import profiles for backup

## File Structure

```
data/user_profiles/
├── user_123456789.json  # User profile
├── user_987654321.json
└── server_metadata.json  # Server-wide stats
```

**Example Profile:**
```json
{
  "user_id": 123456789,
  "username": "JohnDoe",
  "affection_level": 65,
  "affection_tier": "close_friend",
  "interaction_count": 127,
  "traits": ["funny", "competitive"],
  "interests": ["Halo", "gaming"],
  "preferences": {
    "main_character": "Master Chief",
    "favorite_weapon": "Energy Sword"
  },
  "facts": [
    {
      "fact": "software engineer",
      "timestamp": "2025-10-26T10:30:00",
      "source": "conversation"
    }
  ],
  "memorable_quotes": [
    {
      "quote": "I once got 50 kills in one Halo match!",
      "context": "Bragging about gaming skills",
      "timestamp": "2025-10-26T14:20:00"
    }
  ],
  "relationships": {
    "987654321": "friend",
    "555555555": "rival"
  },
  "created_at": "2025-10-20T08:00:00",
  "last_updated": "2025-10-26T16:45:00",
  "last_interaction": "2025-10-26T16:45:00"
}
```

## Advanced: Web Search Integration

The bot can also search the web for context! See [WEB_SEARCH.md](WEB_SEARCH.md) for details.

**Example:**
```
User: Who won the Halo World Championship 2024?
Bot: [Searches web for "Halo World Championship 2024 winner"]
Bot: DUDE IT WAS TEAM OPTIC GAMING!! THEY DESTROYED EVERYONE!! SO SICK BRO!!
```

## Future Enhancements

- **Relationship graphs**: Visualize connections between users
- **Memory consolidation**: Summarize old facts into personality descriptions
- **Emotion tracking**: Remember if user was happy, sad, angry in past conversations
- **Event memories**: Remember birthdays, achievements, server events
- **Dynamic personas**: Bot personality adapts based on user relationship
- **Voice customization**: Best friends get custom RVC voices
- **Achievement system**: Unlock badges for interaction milestones

## Summary

✅ Bot remembers each user's personality, interests, and preferences
✅ Affection system: Stranger → Acquaintance → Friend → Close Friend → Best Friend
✅ Bot can reference users in conversations ("@UserA would love this!")
✅ Responses get more personalized as affection grows
✅ All data stored locally, privacy-friendly
✅ Works with all personas (Chief, Arbiter, etc.)

Your Arby n Chief bot is no longer just a chatbot - it's building real relationships with your server members!
