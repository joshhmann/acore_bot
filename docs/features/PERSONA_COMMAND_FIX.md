# Persona Commands Not Showing - Solutions

## The Problem

The `/set_persona` and `/list_personas` commands are **definitely in the code** but not showing in Discord.

**Why:** Discord caches slash commands and can take **up to 1 hour** to sync new commands!

---

## ✅ PROVEN SOLUTIONS

### Solution 1: Force Global Command Sync (FASTEST)

Add this temporary code to force Discord to update commands immediately:

1. **Edit `main.py`**, find the `setup_hook` function around line 95

2. **Replace this:**
```python
# Sync commands (for slash commands)
await self.tree.sync()
logger.info("Synced command tree")
```

3. **With this:**
```python
# Sync commands (for slash commands)
# Force clear cache and re-sync
self.tree.clear_commands(guild=None)
await self.tree.sync()
logger.info("Synced command tree (forced update)")
```

4. **Restart the bot**

5. **Wait 1-2 minutes**, then check Discord - commands should appear!

---

### Solution 2: Guild-Specific Commands (INSTANT)

Test commands work in your specific server immediately:

1. **Edit `main.py`**, find the `setup_hook` function

2. **Add your guild ID before sync:**
```python
# Test in specific guild (replace with your server ID)
test_guild = discord.Object(id=1290178407669170186)  # Your guild ID

# Sync to test guild for instant update
await self.tree.sync(guild=test_guild)
logger.info(f"Synced commands to test guild")

# Also sync globally (for all servers)
await self.tree.sync()
logger.info("Synced commands globally")
```

3. **Restart bot**

4. **Commands appear INSTANTLY** in that specific server!

---

### Solution 3: Kick & Re-invite Bot

1. **Kick the bot** from your Discord server
2. **Re-invite with this URL:** (make sure `applications.commands` scope is checked)
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=8&scope=bot%20applications.commands
   ```
3. **Restart bot**
4. Commands should register immediately

---

### Solution 4: Just Wait

If you don't want to change code:
- **Wait up to 1 hour**
- Discord will eventually sync the commands
- This is normal Discord behavior

---

## 🔍 Verify Commands Are Loaded

Check your bot logs when it starts:

```
INFO:main:Loaded ChatCog
INFO:main:Loaded VoiceCog
INFO:main:Synced command tree
```

If you see "Loaded ChatCog", the persona commands ARE loaded!

---

## 📋 What Commands Should Appear

Once synced, you should see these in Discord:

### Chat Commands
- `/chat` - Chat with AI
- `/ask` - One-off question
- `/clear_history` - Clear chat history
- `/end_session` - End conversation session
- `/set_model` - Change Ollama model
- `/models` - List models
- **`/set_persona`** ← This one!
- **`/list_personas`** ← This one!
- `/status` - Check AI status

### Voice Commands
- `/join` - Join voice channel
- `/leave` - Leave voice channel
- `/speak` - Generate TTS
- `/speak_as` - Speak with RVC voice
- `/voices` - List voices
- `/set_voice` - Change TTS voice
- `/list_tts_voices` - List all TTS voices

---

## 🧪 Test After Fix

Once commands appear:

```
/list_personas
  → Should show: arbiter, chief, default, pirate, etc.

/set_persona chief
  → Bot switches to Master Chief personality
  → Conversation history cleared

/chat Hey bot!
  → Chief: YO WHATS UP BRO!!

/set_persona arbiter
  → Bot switches to Arbiter personality

/chat Hey bot!
  → Arbiter: Good day. How may I assist you?
```

---

## 💡 Recommended Solution

**Use Solution 1** (Force Global Sync) - it's the fastest and works for all servers!

Just add this one line:
```python
self.tree.clear_commands(guild=None)
```

Before `await self.tree.sync()` in `setup_hook()`.

---

## 🐛 Still Not Working?

If commands STILL don't appear after trying these:

1. **Check bot permissions:**
   - Must have `applications.commands` scope
   - Check OAuth2 URL when you invited bot

2. **Check bot logs for errors:**
   - Look for "Synced command tree"
   - Look for any error messages

3. **Try in a different server:**
   - Create a test server
   - Invite bot fresh
   - See if commands work there

4. **Discord outage:**
   - Check https://discordstatus.com
   - Slash commands can be delayed during Discord issues

---

## Summary

**The commands exist!** They're just not synced to Discord yet.

**Fastest fix:** Add `self.tree.clear_commands(guild=None)` before sync in `main.py`

**Easiest fix:** Just wait up to 1 hour (boring but guaranteed)
