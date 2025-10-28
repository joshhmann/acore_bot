# Conversation Sessions Guide

## Overview

The bot now supports **conversation sessions** - a natural way to chat where the bot stays engaged with you for a period of time, then goes quiet until you call it again.

## How It Works

### Starting a Session

Start a conversation in **two ways**:

1. **@Mention the bot**
   ```
   You: @BotName hello!
   Bot: Hello! How can I help you?
   [Session starts - 5 minute timer begins]
   ```

2. **Use `/chat` command**
   ```
   You: /chat message:hello
   Bot: Hello! How can I help you?
   [Session starts - 5 minute timer begins]
   ```

### During an Active Session

Once started, **you don't need to @mention anymore!** Just chat normally:

```
You: @BotName what's the weather?
Bot: [Responds - Session started, timer at 5:00]

You: and what about tomorrow?
Bot: [Responds - Timer reset to 5:00]

You: thanks!
Bot: [Responds - Timer reset to 5:00]

[You wait 6 minutes without talking...]

You: hello?
[No response - session timed out]

You: @BotName hello?
Bot: [Responds - New session started!]
```

### Timer Behavior

- **Default timeout:** 5 minutes (300 seconds)
- **Timer resets** every time you send a message during an active session
- **Configurable** via `CONVERSATION_TIMEOUT` in `.env`

## Configuration

In your `.env` file:

```env
# Enable conversation sessions
AUTO_REPLY_ENABLED=true

# Optional: Restrict to specific channels
AUTO_REPLY_CHANNELS=1234567890

# Conversation timeout (seconds)
CONVERSATION_TIMEOUT=300  # 5 minutes

# Enable voice responses
AUTO_REPLY_WITH_VOICE=true
```

### Timeout Examples

```env
CONVERSATION_TIMEOUT=60    # 1 minute (quick chats)
CONVERSATION_TIMEOUT=300   # 5 minutes (default)
CONVERSATION_TIMEOUT=600   # 10 minutes (longer conversations)
CONVERSATION_TIMEOUT=1800  # 30 minutes (very long sessions)
```

## Commands

### `/chat` - Start Session & Chat
Starts a new conversation session and sends a message.
```
/chat message:Tell me a joke
```

### `/end_session` - Manually End Session
End the current session without waiting for timeout.
```
/end_session
```
Response: "Conversation session ended. Use @mention or /chat to start a new session."

### Other Commands (Don't Start Sessions)
These commands work but **don't start conversation sessions**:
- `/ask` - One-off question (no session)
- `/speak` - TTS only (no session)
- `/status`, `/models`, etc. - Info commands

## Use Cases

### 🎮 Gaming Session
```
[5:00 PM] You: @BotName join us in voice
[5:00 PM] Bot: I've joined the voice channel!
[Session active]

[5:02 PM] You: what's the build for mage?
[5:02 PM] Bot: [Explains mage build] 🔊

[5:05 PM] You: and for warrior?
[5:05 PM] Bot: [Explains warrior build] 🔊

[5:15 PM] Session times out after 10 minutes of silence
```

### 💬 Quick Q&A
```
You: @BotName quick question
Bot: Sure, what do you need?

You: what is 25 * 4?
Bot: 100

You: thanks!
Bot: You're welcome!

[5 minutes later - session expires]
```

### 📚 Learning/Research
```
You: /chat message:Explain Python decorators
Bot: [Detailed explanation]
[Session active - 5 min timer]

You: can you give an example?
Bot: [Code example]
[Timer reset to 5 min]

You: what about class decorators?
Bot: [Explains class decorators]
[Timer reset to 5 min]

[Continue asking questions without @mentioning each time]
```

## Behavior Examples

### Example 1: Normal Flow
```
[3:00 PM] You: @BotName hello           <- Starts session
[3:00 PM] Bot: Hi there!

[3:01 PM] You: what time is it?         <- No @ needed
[3:01 PM] Bot: It's 3:01 PM

[3:02 PM] You: thanks                   <- No @ needed
[3:02 PM] Bot: You're welcome!

[3:08 PM] You: are you there?           <- 6 min later, session expired
[3:08 PM] [No response]

[3:08 PM] You: @BotName are you there?  <- Restart with @
[3:08 PM] Bot: Yes, I'm here!           <- New session starts
```

### Example 2: Rapid Conversation
```
You: @BotName let's chat
Bot: Sure! [Session: 5:00]

You: tell me about AI
Bot: [Response] [Session: 5:00 reset]

You: and machine learning?
Bot: [Response] [Session: 5:00 reset]

You: cool!
Bot: [Response] [Session: 5:00 reset]

[Every message resets the 5-minute timer]
```

### Example 3: Manual End
```
You: @BotName start
Bot: Started! [Session active]

You: actually never mind
[You use /end_session]

You: some other message
[No response - session ended]

You: @BotName now I'm ready
Bot: [Responds - new session]
```

## With Voice Features

When bot is in a voice channel:

```
1. Use /join to connect bot to voice
2. Start session: @BotName hello
3. Bot responds:
   - Text in chat
   - Speaks in voice 🔊
4. Continue chatting (no @ needed):
   You: tell me more
   Bot: [Text + Voice response] 🔊
5. Session expires after timeout
6. Restart with @mention
```

## Tips

### ⏱️ Choosing the Right Timeout

**Short (1-2 min):** Quick info lookup
```env
CONVERSATION_TIMEOUT=120
```

**Medium (5 min - default):** Normal conversations
```env
CONVERSATION_TIMEOUT=300
```

**Long (10-30 min):** Extended help sessions
```env
CONVERSATION_TIMEOUT=1800
```

### 🎯 Best Practices

1. **Start clearly:** Use @mention or `/chat` to begin
2. **Keep chatting:** Timer resets with each message
3. **End explicitly:** Use `/end_session` when done (optional)
4. **Check status:** No response? Session timed out - restart with @

### 🚫 Avoiding Spam

Sessions prevent the bot from:
- Responding to EVERY message (without @)
- Creating spam in busy channels
- Wasting API calls

Instead:
- Bot only responds when engaged
- Sessions auto-expire
- Users control when bot is active

## Advanced Configuration

### Per-Channel Sessions

Sessions are tracked **per channel**, so:
- Channel A can have active session
- Channel B has no session
- They don't interfere with each other

### Multiple Users

Currently, **one session per channel:**
- Anyone can start a session in a channel
- Once active, **everyone** in that channel can chat (no @ needed)
- Anyone can end it with `/end_session`

This is great for:
- Group discussions
- Team help sessions
- Collaborative learning

## Troubleshooting

### Bot Not Responding (No Session)
✅ **Solution:** Start session with @mention or `/chat`

### Bot Responding to Everything
❌ **Problem:** Sessions never expire
✅ **Check:** `CONVERSATION_TIMEOUT` in `.env` is set
✅ **Fix:** Manually use `/end_session`

### Session Expires Too Quickly
✅ **Increase timeout:**
```env
CONVERSATION_TIMEOUT=600  # 10 minutes
```

### Session Lasts Too Long
✅ **Decrease timeout:**
```env
CONVERSATION_TIMEOUT=180  # 3 minutes
```

## Logging

Bot logs session activity:
```
INFO - Started conversation session in channel 1234567890 for user 9876543210
INFO - Refreshed session in channel 1234567890
INFO - Session timed out in channel 1234567890 after 310s
INFO - Ended session in channel 1234567890
```

Check `bot.log` for session debugging.

## Summary

| Action | Starts Session | Continues Session | Resets Timer |
|--------|---------------|-------------------|--------------|
| `@BotName message` | ✅ Yes | ✅ Yes | ✅ Yes |
| `/chat message` | ✅ Yes | ✅ Yes | ✅ Yes |
| Regular message (during session) | ❌ No | ✅ Yes | ✅ Yes |
| Regular message (no session) | ❌ No | ❌ No | ❌ No |
| `/end_session` | ❌ No | Ends ❌ | ❌ No |
| `/ask question` | ❌ No | ❌ No | ❌ No |

**Key Point:** Once you start a session with @mention or `/chat`, just keep talking normally. The bot will respond to every message until the timeout expires!

Enjoy natural, flowing conversations with your AI assistant! 🤖💬
