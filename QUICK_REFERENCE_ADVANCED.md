# Quick Reference - Advanced Features

## 🔢 Math Calculations

```
@Bot 25 * 48              → That's **1200**!
@Bot 100 / 5              → **20** 🔢
@Bot what's 15 + 27?      → **42**
@Bot square root of 144   → The square root of 144 is **12**
@Bot 5 squared            → 5 squared is **25**
```

## ⏰ Time & Date

```
@Bot what time is it?     → It's 03:45 PM!
@Bot what's the date?     → It's Sunday, November 23, 2025
```

## 🎯 Trivia

```
@Bot let's play trivia
@Bot start a trivia game
@Bot trivia time
```

## 💬 Multi-Turn Conversations

### Server Setup
```
@Bot start server setup
→ Guides you through setting up server preferences
```

### Create Persona
```
@Bot create a new persona
→ Walks you through creating a custom bot personality
```

### Reminder Series
```
@Bot setup recurring reminders
→ Creates a series of repeating reminders
```

**Cancel anytime:** Type `cancel`, `quit`, or `exit`

## 🎨 Custom Intents (Admin)

### Add Custom Intent (Python)
```python
bot.intent_recognition.custom_intents.add_intent(
    server_id=YOUR_SERVER_ID,
    intent_id='rules',
    name='Server Rules',
    patterns=[r'what\s+are\s+the\s+rules', r'show\s+rules'],
    response_template="Check #rules for our server rules!",
    response_type='text'
)
```

### Common Custom Intent Examples

**Server Rules:**
```python
patterns=[r'what\s+(?:are\s+)?(?:the\s+)?rules']
response="Check out #rules-and-info!"
```

**Support Tickets:**
```python
patterns=[r'(?:open|create)\s+ticket', r'i\s+need\s+help']
response="Use /ticket or DM a moderator for help!"
```

**Applications:**
```python
patterns=[r'how\s+(?:do\s+i|can\s+i)\s+apply']
response="Visit #applications to apply! 🎉"
```

## 📊 Statistics

### View Intent Stats
```python
# Get overall stats
stats = bot.intent_recognition.get_stats()

# Get pattern learning stats
learning_stats = bot.intent_recognition.learner.get_stats()

# Get custom intents for a server
custom_stats = bot.intent_recognition.custom_intents.get_stats(server_id=123)

# Get conversation stats
conv_stats = bot.conversation_manager.get_stats()
```

## 🧠 Pattern Learning

The bot automatically learns from successful interactions!

**View learned patterns:**
```python
top_patterns = bot.intent_recognition.learner.get_top_patterns('reminder', limit=10)
```

**Get improvement suggestions:**
```python
suggestions = bot.intent_recognition.learner.suggest_improvements()
for suggestion in suggestions:
    print(suggestion)
```

**Manually teach a pattern:**
```python
# When user says "This should have been a reminder"
bot.intent_recognition.report_correction(original_message, 'reminder')
```

## 🔧 Configuration

### .env Settings
```bash
# Intent Recognition
INTENT_RECOGNITION_ENABLED=true          # Master switch
NATURAL_LANGUAGE_REMINDERS=true         # Natural reminders
PATTERN_LEARNING_ENABLED=true           # Auto-learning (future)
CUSTOM_INTENTS_ENABLED=true             # Per-server intents (future)
```

## 💡 Tips

1. **Math**: Bot understands `*`, `/`, `+`, `-`, `×`, `÷`
2. **Time**: Ask naturally - "what time is it?" or "tell me the time"
3. **Conversations**: Bot remembers context within multi-turn flows
4. **Custom Intents**: Regex patterns supported, use capture groups with `{1}`, `{2}`, etc.
5. **Learning**: Bot gets smarter over time automatically!

## 🚨 Common Patterns

### Reminder Patterns
```python
r'remind\s+me\s+(?:to\s+)?(.+)'
r'in\s+\d+\s+(?:min|hour)s?\s+remind'
```

### Question Patterns
```python
r'\?$'  # Ends with ?
r'^(?:what|when|where|who|why|how)'
```

### Help Patterns
```python
r'help\s+(?:me\s+)?(?:with\s+)?'
r'what\s+can\s+you\s+do'
```

## 📱 Intent Priority Order

1. Custom Intents (server-specific overrides)
2. Learned Patterns (from successful interactions)
3. Math (quick calculations)
4. Time/Date (quick responses)
5. Reminders
6. Trivia
7. Music
8. Weather
9. Translation
10. Search
11. Help
12. Questions
13. Small Talk

## 🎯 Response Types for Custom Intents

**Text:**
```python
response_type='text'
response_template="Your text here"
```

**Embed:**
```python
response_type='embed'
response_template="Rich embed description"
```

**With Capture Groups:**
```python
patterns=[r'welcome\s+(\w+)']
response_template="Welcome {1} to our server! 🎉"
```

## 🔄 Multi-Turn Conversation Flow

```
1. Start conversation
   ↓
2. Bot asks first question (Step 1/N)
   ↓
3. User responds
   ↓
4. Bot validates input
   ↓
5. If valid → Next step
   If invalid → Retry (up to 3 times)
   ↓
6. Repeat until all steps complete
   ↓
7. Conversation completed! ✅
```

**Cancel anytime:** `cancel`, `quit`, `exit`, `stop`

## 📈 Performance

- Intent detection: <10ms (regex-based)
- Pattern learning: Minimal overhead
- Custom intents: O(1) lookup per server
- Multi-turn: Stateless, efficient

---

**Need more details?** Check `ADVANCED_FEATURES.md` for full documentation!
