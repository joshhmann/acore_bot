# Natural Language Features

This document describes the new natural language understanding features added to the bot.

## Overview

The bot can now understand and respond to natural language commands without requiring slash commands. It also speaks more naturally and conversationally.

## Features

### 1. Natural Language Reminders

Users can set reminders using natural language instead of slash commands.

**Examples:**
- "remind me in 30 minutes to check the oven"
- "remind me at 5pm to call mom"
- "in 2 hours remind me to take a break"
- "remind me tomorrow at 9am to submit the report"
- "set a reminder to water the plants in 1 hour"

The bot will:
- Parse the time expression automatically
- Extract the reminder message
- Respond with a natural confirmation like "Got it! I'll remind you about 'check the oven' in 30 minutes ✅"

### 2. Intent Recognition

The bot detects what users want from their messages:

- **Reminders**: Automatically detected from phrases like "remind me"
- **Questions**: Identifies when users are asking questions (ends with ?, starts with what/when/how, etc.)
- **Small talk**: Handles greetings, farewells, thanks without needing AI
- **Help requests**: Provides quick help when users ask "what can you do" or "help"

### 3. Natural Conversational Style

The bot now speaks more naturally with:

- **Contractions**: "I'm", "you're", "don't", "can't"
- **Genuine reactions**: "Oh nice!", "Hmm interesting", "Wait really?"
- **Informal language**: "yeah", "nah", "totally", "pretty much"
- **Varied responses**: No more robotic "Let me know if you need anything else!"
- **Personality**: Shows more character and emotion
- **Natural flow**: Asks follow-up questions, admits uncertainty

## Configuration

Add these to your `.env` file:

```bash
# Enable intent recognition for natural language commands
INTENT_RECOGNITION_ENABLED=true

# Enable natural language reminders (requires REMINDERS_ENABLED=true)
NATURAL_LANGUAGE_REMINDERS=true
```

## Usage Examples

### Setting Reminders Naturally

**User:** "remind me in 15 minutes to check the laundry"

**Bot:** "Sure thing! I'll remind you about 'check the laundry' in 15 minutes 👍"

---

**User:** "can you remind me at 6pm to start dinner"

**Bot:** "On it! I'll send you a reminder to 'start dinner' at 06:00 PM (in 2 hours) ✅"

### Asking Questions

**User:** "@Bot what's the weather like?"

**Bot:** *Uses AI to answer naturally, with personality*

### Getting Help

**User:** "@Bot help"

**Bot:** *Shows quick help embed with natural language examples*

### Small Talk

**User:** "@Bot hey!"

**Bot:** "Hey! What's up?"

**User:** "thanks!"

**Bot:** "No problem!"

## How It Works

1. **Message received** → Bot checks if it's mentioned or in an active session
2. **Intent detection** → Analyzes the message for reminders, questions, help, etc.
3. **Intent handling** → Handles simple intents directly (reminders, small talk, help)
4. **AI response** → For complex questions, passes to AI with enhanced conversational guidelines
5. **Natural confirmation** → Responds naturally without being robotic

## Benefits

- **More intuitive**: Users don't need to remember slash commands
- **More engaging**: Bot feels more alive and present
- **Faster**: Simple intents handled immediately without AI processing
- **More natural**: Conversations flow like talking to a real person

## Technical Details

### Intent Recognition Service

Located in: `services/intent_recognition.py`

- Uses regex patterns to detect intents
- Confidence scoring for ambiguous cases
- Extensible for adding new intent types

### Conversational Responder

Generates natural, varied responses:
- Random acknowledgments: "Got it!", "Sure thing!", "On it!"
- Varied confirmations to avoid repetition
- Context-aware responses

### Integration

- Integrated into `ChatCog.on_message()`
- Checks intents before AI processing
- Respects configuration flags
- Falls back to AI for complex cases

## Future Enhancements

Possible additions:
- More intent types (trivia questions, music requests, etc.)
- Learning from user patterns
- Multi-turn intent conversations
- Intent confidence thresholds
- Custom intent definitions per server
