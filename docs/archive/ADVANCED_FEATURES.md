

# Advanced Natural Language Features

This document describes the advanced AI-powered features that make your bot incredibly intelligent and adaptive.

## 🚀 Overview

We've implemented a comprehensive suite of advanced features:

1. **Extended Intent Recognition** - Math, trivia, music, time, search, weather, translation
2. **Multi-Turn Conversations** - Guided wizards for complex tasks
3. **Pattern Learning** - Bot learns from successful interactions
4. **Custom Intents** - Per-server custom command definitions

## 📊 Feature Breakdown

### 1. Extended Intent Types

The bot now understands many more types of requests automatically!

#### Math Calculations
```
User: @Bot what's 25 * 48?
Bot: That's 1200!

User: @Bot 100 / 5
Bot: 20 🔢

User: @Bot square root of 144
Bot: The square root of 144 is 12
```

**Supported operations:**
- Basic arithmetic: `+`, `-`, `*`, `/`, `×`, `÷`
- Square roots: "square root of X"
- Powers: "X squared", "X cubed"

#### Time & Date Queries
```
User: @Bot what time is it?
Bot: It's 03:45 PM!

User: @Bot what's the date?
Bot: It's Sunday, November 23, 2025
```

#### Trivia
```
User: @Bot let's play trivia
Bot: Let's play trivia! Starting a game...
```

#### Music Requests
```
User: @Bot play some music
Bot: Music commands work in voice channels! Try joining a voice channel and using /play or /join first.
```

#### Search, Weather, Translation
These intents are detected and passed to the AI with appropriate context:
- "search for X"
- "what's the weather in Paris?"
- "translate hello to Spanish"

### 2. Multi-Turn Conversations 🔄

Complex tasks that require multiple steps are now handled with guided conversations!

#### Example: Server Setup Wizard

```
User: @Bot start server setup
Bot: Let's set up your server! First, what's your preferred prefix for commands? (e.g., !, ?, .)

User: !
Bot: **Step 2/3**
Great! Now, which channel should I use for announcements? (mention the channel or say 'skip')

User: #announcements
Bot: **Step 3/3**
Should I enable auto-replies in conversation? (yes/no)

User: yes
Bot: All done! ✅
```

#### Built-in Conversation Templates

**Server Setup** (`server_setup`)
- Configure command prefix
- Set announcement channel
- Enable/disable features

**Create Persona** (`create_persona`)
- Name your persona
- Set display name
- Write description
- Define personality with system prompt

**Reminder Series** (`reminder_series`)
- Set recurring reminder task
- Choose frequency (daily/weekly/hourly)
- Set number of occurrences

#### Using Multi-Turn Conversations

Conversations are triggered automatically or via commands. To start manually:

```python
# In code or via slash command
conversation = await bot.conversation_manager.start_conversation(
    user_id=user.id,
    channel_id=channel.id,
    conversation_type='create_persona'
)
```

**Features:**
- Input validation at each step
- Max retry attempts (default: 3)
- Timeout handling (default: 5 minutes per step)
- Cancel anytime with "cancel", "quit", or "exit"
- Step progress indicators

### 3. Pattern Learning 🧠

The bot learns from interactions to improve over time!

#### How It Works

**Success Learning:**
When an intent is successfully recognized and handled, the bot learns the pattern:
```
User: remind me in 30m to check dinner
Bot: [Creates reminder successfully]
→ Pattern learned: "remind me in \d+m to (.+)" for reminder intent
```

**Failure Learning:**
When an intent fails, it tracks the failure rate to identify problems.

**User Corrections:**
Users can correct the bot:
```
User: that should have been a reminder
→ Bot learns the previous message should trigger reminder intent
```

**Continuous Improvement:**
- Patterns gain confidence with successful usage
- Low-performing intents are identified
- Suggestions provided for pattern improvements

#### Pattern Learning Stats

```python
stats = bot.intent_recognition.get_stats()
# {
#     'pattern_learning': {
#         'total_patterns': 47,
#         'intent_types_learned': 8,
#         'user_corrections': 12,
#         'top_performing': [...]
#     }
# }
```

### 4. Custom Intents Per Server 🎯

Server admins can define custom intents specific to their community!

#### Creating Custom Intents

**Example 1: Server Rules**
```python
bot.intent_recognition.custom_intents.add_intent(
    server_id=123456789,
    intent_id='server_rules',
    name='Server Rules',
    patterns=[
        r'what\s+(?:are\s+)?(?:the\s+)?rules',
        r'show\s+(?:me\s+)?(?:the\s+)?rules',
    ],
    response_template="Check out our rules in #rules-and-info!",
    response_type='text'
)
```

**Example 2: Support Tickets**
```python
bot.intent_recognition.custom_intents.add_intent(
    server_id=123456789,
    intent_id='support',
    name='Support Ticket',
    patterns=[
        r'(?:open|create)\s+ticket',
        r'i\s+need\s+help',
    ],
    response_template="I'll help you! Please use /ticket or DM a moderator.",
    response_type='text',
    metadata={'category': 'support'}
)
```

**Example 3: Applications**
```python
bot.intent_recognition.custom_intents.add_intent(
    server_id=123456789,
    intent_id='apply',
    name='Application Info',
    patterns=[
        r'how\s+(?:do\s+i|can\s+i)\s+apply',
        r'application\s+process',
    ],
    response_template="Visit #applications to apply! Good luck! 🍀",
    response_type='text'
)
```

#### Response Types

**Text Response:**
```python
response_type='text'
response_template="Your text here"
```

**Embed Response:**
```python
response_type='embed'
response_template="Embed description"
# Shows as a rich embed with the intent name as title
```

**Pattern Groups:**
Use capture groups in patterns and reference them in responses:
```python
patterns=[r'welcome\s+(\w+)']
response_template="Welcome {1} to the server! 🎉"
# {1} will be replaced with the captured name
```

#### Managing Custom Intents

**List Intents:**
```python
intents = bot.intent_recognition.custom_intents.list_intents(server_id=123456)
```

**Remove Intent:**
```python
success = bot.intent_recognition.custom_intents.remove_intent(
    server_id=123456,
    intent_id='server_rules'
)
```

**Get Stats:**
```python
stats = bot.intent_recognition.custom_intents.get_stats(server_id=123456)
# {
#     'server_id': 123456,
#     'custom_intents': 5,
#     'global_intents': 3,
#     'total_available': 8
# }
```

## 🎮 Usage Examples

### Math
```
@Bot 15 + 27
@Bot what's 100 / 4?
@Bot calculate 50 * 3
@Bot square root of 81
@Bot 5 squared
```

### Time
```
@Bot what time is it?
@Bot what's the date?
@Bot tell me the current time
```

### Multi-Turn Setup
```
@Bot help me set up the server
→ Starts server_setup conversation

@Bot create a new persona
→ Starts create_persona wizard

@Bot setup recurring reminders
→ Starts reminder_series conversation
```

### Custom Intents (After Setup)
```
@Bot what are the rules?
→ [Your custom rules response]

@Bot I need help
→ [Your custom support response]

@Bot how do I apply?
→ [Your custom application info]
```

## ⚙️ Configuration

Add these to your `.env`:

```bash
# Intent Recognition (already enabled by default)
INTENT_RECOGNITION_ENABLED=true
NATURAL_LANGUAGE_REMINDERS=true

# Pattern Learning (enabled by default)
PATTERN_LEARNING_ENABLED=true

# Custom Intents (enabled by default)
CUSTOM_INTENTS_ENABLED=true
```

## 📈 Monitoring & Stats

### Intent Recognition Stats
```python
stats = bot.intent_recognition.get_stats()
```

Returns:
- Total intents detected
- Breakdown by type
- Pattern learning statistics
- Custom intents per server

### Conversation Manager Stats
```python
stats = bot.conversation_manager.get_stats()
```

Returns:
- Active conversations
- Registered templates
- Template names

### Pattern Learner Suggestions
```python
suggestions = bot.intent_recognition.learner.suggest_improvements()
```

Returns actionable suggestions for improving intent recognition.

## 🔧 Advanced: Creating Custom Conversation Templates

```python
from services.conversation_manager import ConversationStep

# Define steps
steps = [
    ConversationStep(
        prompt="What's your favorite color?",
        validator=lambda x: len(x) > 0,
        error_message="Please enter a color."
    ),
    ConversationStep(
        prompt="Why do you like that color?",
        validator=lambda x: len(x) > 10,
        error_message="Please give a longer explanation (10+ characters)."
    ),
]

# Register template
bot.conversation_manager.register_template('favorite_color', steps)
```

## 🎯 Benefits

1. **Smarter Recognition**: Learns from every interaction
2. **Server-Specific**: Custom intents per community
3. **Guided Processes**: Multi-turn conversations for complex tasks
4. **Adaptive**: Gets better over time automatically
5. **Extensible**: Easy to add new conversation templates and intents

## 🚀 Future Enhancements

Potential additions:
- Machine learning-based intent classification
- Intent confidence thresholds per server
- A/B testing for intent patterns
- Intent analytics dashboard
- Voice-based intent recognition
- Multi-language intent support

## 📚 API Reference

### IntentRecognitionService

```python
# Detect intent
intent = service.detect_intent(message, bot_mentioned=True, server_id=123)

# Report success/failure
service.report_success(message, intent_type)
service.report_failure(message, intent_type)
service.report_correction(message, correct_intent)

# Get stats
stats = service.get_stats()
```

### MultiTurnConversationManager

```python
# Start conversation
conversation = await manager.start_conversation(
    user_id=user.id,
    channel_id=channel.id,
    conversation_type='server_setup'
)

# Process response
result = await manager.process_response(
    channel_id=channel.id,
    user_id=user.id,
    message="user response"
)

# Cancel conversation
success = manager.cancel_conversation(channel_id)
```

### PatternLearner

```python
# Learn from success
learner.learn_from_success(message, intent_type, confidence=0.9)

# Learn from failure
learner.learn_from_failure(message, attempted_intent)

# Learn from correction
learner.learn_from_correction(message, correct_intent)

# Check learned pattern
match = learner.check_learned_pattern(message)

# Get suggestions
suggestions = learner.suggest_improvements()
```

### CustomIntentManager

```python
# Add intent
success = manager.add_intent(
    server_id=123,
    intent_id='my_intent',
    name='My Intent',
    patterns=[r'pattern1', r'pattern2'],
    response_template="Response text"
)

# Remove intent
success = manager.remove_intent(server_id=123, intent_id='my_intent')

# Check custom intent
match = manager.check_custom_intent(server_id=123, message="user message")

# List intents
intents = manager.list_intents(server_id=123)
```

---

## 🎉 Summary

Your bot is now incredibly intelligent with:
- ✅ 10+ intent types automatically recognized
- ✅ Math calculations on the fly
- ✅ Multi-turn guided conversations
- ✅ Self-improving pattern learning
- ✅ Per-server custom intents
- ✅ Natural time/date responses
- ✅ And much more!

The bot will continue to get smarter as it learns from interactions. Enjoy! 🚀
