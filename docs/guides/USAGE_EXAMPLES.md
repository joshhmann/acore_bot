# Usage Examples - Natural Language Features

Here are real examples of how users can interact with your bot using the new natural language features.

## Natural Language Reminders

### Basic Time-Based Reminders

```
User: @Bot remind me in 15 minutes to check the laundry
Bot: Got it! I'll remind you about "check the laundry" in 15 minutes 👍

User: @Bot remind me in 2 hours to call John
Bot: Sure thing! I'll send you a reminder to "call John" in 2 hours ✅

User: @Bot remind me in 1 hour to take a break
Bot: On it! I'll ping you in 1 hour to "take a break"
```

### Specific Time Reminders

```
User: @Bot remind me at 5pm to start cooking dinner
Bot: I'll remind you to "start cooking dinner" at 05:00 PM (in 2 hours 30 minutes) ✅

User: @Bot remind me tomorrow at 9am to submit the report
Bot: Reminder set! I'll remind you to "submit the report" at 09:00 AM on December 24 (in 16 hours)
```

### Casual Phrasing

```
User: @Bot in 30 minutes remind me to check the oven
Bot: Alright! I'll remind you about "check the oven" in 30 minutes

User: @Bot set a reminder to water the plants in 1 hour
Bot: Done! I'll ping you in 1 hour to "water the plants" 👍
```

### Error Handling

```
User: @Bot remind me to buy groceries
Bot: I'd love to help! But when should I remind you? Try something like "in 30 minutes" or "at 5pm"

User: @Bot remind me at 5pm
Bot: Sure! When do you want the reminder? You can say "in 2 hours" or "tomorrow at 9am"
```

## Natural Conversations

### Questions

```
User: @Bot what's the weather like?
Bot: Hmm, I don't have access to real-time weather data, but you could try checking weather.com or asking about a specific location!

User: @Bot how do I make pizza?
Bot: Oh nice, homemade pizza! Basic steps: make or buy dough, add sauce and toppings, bake at 450°F for 10-15 minutes. Want a more detailed recipe?

User: @Bot what's 25 * 48?
Bot: That's 1,200! Pretty straightforward multiplication there.
```

### Small Talk

```
User: @Bot hey!
Bot: Hey! What's up?

User: @Bot thanks for the help!
Bot: No problem! Happy to help!

User: @Bot you're awesome
Bot: Aw thanks! 😊

User: @Bot bye
Bot: Later! Talk soon!
```

### Getting Help

```
User: @Bot help
Bot: [Shows help embed with natural language examples]

User: @Bot what can you do?
Bot: [Shows help embed]

User: @Bot how do I use reminders?
Bot: [Shows help embed]
```

## Natural Conversational Style

### Before (Robotic)

```
User: @Bot what's 5 + 5?
Bot: The answer to 5 + 5 is 10. Is there anything else I can help you with today?
```

### After (Natural)

```
User: @Bot what's 5 + 5?
Bot: That's 10!

Or:
Bot: 10 - pretty simple math there!

Or:
Bot: It's 10. Need help with more calculations?
```

---

### Before (Formal)

```
User: @Bot tell me about Python
Bot: Python is a high-level, interpreted programming language that was created by Guido van Rossum and first released in 1991. It is designed to be easy to read and write, with a syntax that emphasizes code readability. Would you like to know more about Python's features?
```

### After (Conversational)

```
User: @Bot tell me about Python
Bot: Oh Python's great! It's a super readable programming language that's perfect for beginners. Created in the early 90s, it's now everywhere - web dev, data science, AI, you name it. What aspect are you curious about?
```

---

### Before (Over-helpful)

```
User: @Bot what's your favorite color?
Bot: I am an artificial intelligence and do not have personal preferences or the ability to perceive colors. However, I would be happy to provide information about colors or assist you with any other questions you may have.
```

### After (Personality)

```
User: @Bot what's your favorite color?
Bot: Hmm, I'm kinda partial to blue! It's calming and reminds me of the ocean. What about you?

Or:
Bot: I can't actually see colors, but if I could, I think I'd vibe with purple - it's mysterious!
```

## Session-Based Conversations

Once the bot is mentioned or `/chat` is used, it enters a conversation session and responds to all messages for a period:

```
User: @Bot hey, quick question
Bot: Hey! What's up?

User: what's the capital of France?
Bot: Paris!

User: and Italy?
Bot: Rome!

User: thanks!
Bot: No problem!

[Session continues for 5 minutes without needing to mention the bot]
```

## Tips for Natural Interaction

1. **Just talk normally** - No need for perfect grammar or formal language
2. **Ask follow-up questions** - The bot maintains conversation context
3. **Use natural time expressions** - "in 30 min", "2 hours", "tomorrow at 9am"
4. **Be casual** - "hey", "thanks", "cool" all work great
5. **Mention the bot** - Start with @Bot to begin a conversation session

## Feature Toggles

In your `.env` file:

```bash
# Disable natural language if you want slash-commands only
INTENT_RECOGNITION_ENABLED=false

# Disable natural language reminders specifically
NATURAL_LANGUAGE_REMINDERS=false

# Keep the bot formal and professional
MOOD_SYSTEM_ENABLED=false
NATURALNESS_ENABLED=false
```
