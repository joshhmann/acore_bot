# User Profile Auto-Learning System

## Overview

The bot now automatically learns about users through conversations using AI-powered extraction. After each chat interaction, the bot analyzes the conversation and extracts information to build a comprehensive profile.

## How It Works

### 1. Automatic Extraction
After each `/chat` interaction, the bot:
1. Sends the conversation to the AI with a special extraction prompt
2. AI analyzes the user's message and extracts:
   - **Traits**: Personality characteristics (funny, sarcastic, friendly, analytical)
   - **Interests**: Topics they care about (gaming, Halo, anime, coding)
   - **Facts**: Specific information (favorite game, location, preferences)
   - **Preferences**: Key-value pairs (favorite_color: blue, timezone: PST)

### 2. Profile Building
- Information is automatically added to the user's profile JSON file
- Duplicates are avoided (case-insensitive matching)
- Facts include timestamps for context
- Profiles persist across channels and sessions

### 3. Context Injection
- On each interaction, the bot loads the user's profile
- Profile info is injected into the system prompt
- Bot "remembers" users and can reference their traits/interests

## Example

**Conversation:**
```
User: "I love playing Halo 3, it's my favorite game!"
Bot: "Yo bro! Halo 3 is sick! Best campaign in the series!"
```

**Profile Updated:**
```json
{
  "user_id": 123456789,
  "username": "CoolGamer",
  "interaction_count": 5,
  "traits": [],
  "interests": ["Halo", "Halo 3", "gaming"],
  "facts": [
    {
      "fact": "Favorite game is Halo 3",
      "timestamp": "2025-10-26T16:20:00",
      "source": "conversation"
    }
  ],
  "preferences": {
    "favorite_game": "Halo 3"
  }
}
```

**Next Conversation:**
```
User: "What should I play tonight?"
Bot: "Bro you should totally play some Halo 3! You love that game!"
```

## Configuration

### Enable/Disable Auto-Learning

In your `.env` file:

```env
# User Profiles
USER_PROFILES_ENABLED=true
USER_PROFILES_AUTO_LEARN=true  # Enable AI-powered learning
USER_CONTEXT_IN_CHAT=true      # Include profile info in chat context
```

### Settings

- `USER_PROFILES_ENABLED`: Master switch for user profiles
- `USER_PROFILES_AUTO_LEARN`: Enable/disable automatic AI extraction
- `USER_CONTEXT_IN_CHAT`: Include profile context in bot's prompt
- `USER_PROFILES_PATH`: Directory where profile JSON files are stored

## Profile Storage

Profiles are stored in `data/user_profiles/user_[discord_id].json`

Example profile structure:
```json
{
  "user_id": 123456789,
  "username": "JohnDoe",
  "created_at": "2025-10-26T14:00:00",
  "last_updated": "2025-10-26T16:30:00",
  "interaction_count": 15,
  "traits": ["funny", "sarcastic", "tech-savvy"],
  "interests": ["gaming", "Halo", "programming", "Discord bots"],
  "facts": [
    {
      "fact": "Works as a software developer",
      "timestamp": "2025-10-26T15:00:00",
      "source": "conversation"
    },
    {
      "fact": "Prefers Python over JavaScript",
      "timestamp": "2025-10-26T16:00:00",
      "source": "conversation"
    }
  ],
  "preferences": {
    "favorite_language": "Python",
    "favorite_game": "Halo 3",
    "coding_editor": "VS Code"
  },
  "memorable_quotes": [],
  "relationships": {}
}
```

## Manual Profile Management

You can also manually add information to profiles using the service:

```python
# Add a trait
await user_profiles.add_trait(user_id, "helpful")

# Add an interest
await user_profiles.add_interest(user_id, "machine learning")

# Add a fact
await user_profiles.add_fact(user_id, "Lives in California")

# Set a preference
await user_profiles.set_preference(user_id, "timezone", "PST")
```

## Technical Details

### AI Extraction Process

1. **Low Temperature**: Uses temperature=0.3 for consistent extraction
2. **Structured Prompt**: Asks AI to return only valid JSON
3. **Conservative Extraction**: Only extracts clearly stated information
4. **Duplicate Prevention**: Checks for existing traits/interests before adding

### Performance

- Extraction happens asynchronously after responding to user
- Minimal impact on response time
- Uses same Ollama instance (no additional API costs)
- Failed extractions are logged but don't affect chat

### Privacy

- Profiles are stored locally only
- No external services used
- Can be disabled per-user or globally
- Users can request profile deletion (manual process)

## Future Enhancements

Potential improvements:
- [ ] Affection/relationship scores
- [ ] Personality analysis over time
- [ ] User similarity matching
- [ ] Commands to view your own profile (`/my_profile`)
- [ ] Privacy controls per user
- [ ] Export/import profiles
- [ ] Profile analytics dashboard
