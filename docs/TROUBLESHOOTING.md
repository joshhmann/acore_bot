# TROUBLESHOOTING

A comprehensive guide to diagnosing and resolving common issues with acore_bot.

---

## Table of Contents

1. [Quick Diagnostic Commands](#quick-diagnostic-commands)
2. [Installation Issues](#installation-issues)
3. [Discord Connection Issues](#discord-connection-issues)
4. [Adapter Issues](#adapter-issues)
5. [Framework Issues](#framework-issues)
6. [LLM Issues](#llm-issues)
7. [Persona Issues](#persona-issues)
8. [Debugging Tips](#debugging-tips)
9. [Getting Help](#getting-help)

---

## Quick Diagnostic Commands

Run these commands to quickly assess your bot's health:

```bash
# Check bot process
ps aux | grep python

# View live logs
tail -f logs/bot.log

# Test Discord connectivity
curl -H "Authorization: Bot YOUR_TOKEN" https://discord.com/api/v10/users/@me

# Test Ollama connectivity
curl http://localhost:11434/api/tags

# Check system resources
free -h && df -h

# Run comprehensive diagnostic
python -c "from troubleshooting.diagnostics.bot_diagnostic import BotDiagnostic; import asyncio; asyncio.run(BotDiagnostic().run_full_diagnostic())"
```

---

## Installation Issues

### Dependency Conflicts

**Symptoms:**
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
Could not find a version that satisfies the requirement...
```

**Root Cause:**
Conflicting package versions between discord.py, aiohttp, or other dependencies.

**Solution Steps:**
1. Use `uv` (recommended):
   ```bash
   uv sync
   ```

2. Or create a fresh virtual environment:
   ```bash
   rm -rf .venv
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. For specific conflicts, check `pyproject.toml`:
   ```bash
   cat pyproject.toml | grep -A 20 "dependencies"
   ```

**Prevention:**
- Always use `uv sync` instead of manual pip installs
- Pin specific versions in `pyproject.toml`
- Use the provided lock file

---

### Python Version Issues

**Symptoms:**
```
SyntaxError: invalid syntax
TypeError: unsupported operand type(s)
AttributeError: module 'asyncio' has no attribute 'to_thread'
```

**Root Cause:**
Bot requires Python 3.11+. Older versions lack required async features.

**Solution Steps:**
1. Check your Python version:
   ```bash
   python --version
   ```

2. Install Python 3.11+ if needed:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.11 python3.11-venv

   # macOS
   brew install python@3.11
   ```

3. Recreate virtual environment with correct Python:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

**Prevention:**
- Check Python version before installing: `python --version`
- Use `python3.11` explicitly in commands

---

### Missing System Packages

**Symptoms:**
```
ModuleNotFoundError: No module named '_ctypes'
ImportError: libffi.so.8: cannot open shared object file
OSError: cannot load library 'libopus.so.0'
```

**Root Cause:**
Required system libraries (FFmpeg, libffi, libopus) not installed.

**Solution Steps:**
1. Install FFmpeg (required for voice):
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg

   # macOS
   brew install ffmpeg
   ```

2. Install other dependencies:
   ```bash
   # Ubuntu/Debian
   sudo apt install libffi-dev libopus0 libopus-dev

   # macOS
   brew install libffi opus
   ```

3. Verify FFmpeg installation:
   ```bash
   ffmpeg -version
   ```

**Prevention:**
- Run `scripts/setup.sh` for automated dependency installation
- Include system packages in deployment scripts

---

## Discord Connection Issues

### Bot Won't Connect

**Symptoms:**
```
INFO:discord.gateway:Shard ID None has connected to Gateway
# But then nothing happens
```

**Root Cause:**
Discord API connection blocked by firewall, proxy, or incorrect intents.

**Solution Steps:**
1. Check Discord API connectivity:
   ```bash
   curl https://discord.com/api/v10/gateway
   ```

2. Verify firewall settings:
   ```bash
   # Check if Discord ports are blocked
   nc -zv discord.com 443
   ```

3. Check intents in `main.py`:
   ```python
   intents = discord.Intents.default()
   intents.message_content = True  # REQUIRED
   intents.voice_states = True     # REQUIRED for voice
   ```

4. Enable Message Content Intent in Discord Developer Portal:
   - Go to https://discord.com/developers/applications
   - Select your bot
   - Bot > Privileged Gateway Intents
   - Enable "MESSAGE CONTENT INTENT"

**Prevention:**
- Document required firewall rules
- Use Docker with proper network config
- Enable all required intents before deployment

---

### Token Invalid Errors

**Symptoms:**
```
discord.errors.LoginFailure: Improper token has been passed.
HTTP 401: Unauthorized
```

**Root Cause:**
Discord token is invalid, expired, or incorrectly formatted in `.env`.

**Solution Steps:**
1. Verify token format in `.env`:
   ```bash
   cat .env | grep DISCORD_TOKEN
   # Should be: DISCORD_TOKEN=YOUR_TOKEN_HERE
   # No quotes, no spaces
   ```

2. Generate a new token:
   - Discord Developer Portal > Bot > Reset Token
   - Copy the new token immediately

3. Update `.env`:
   ```bash
   echo "DISCORD_TOKEN=YOUR_NEW_TOKEN" >> .env
   ```

4. Test token validity:
   ```bash
   curl -H "Authorization: Bot YOUR_TOKEN" \
        https://discord.com/api/v10/users/@me
   ```

**Prevention:**
- Never commit `.env` to git
- Use environment variables in production
- Rotate tokens periodically

---

### Intent Errors

**Symptoms:**
```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting privileged intents that have not been explicitly enabled...
 intents value 34319 exceeds max of 32767
```

**Root Cause:**
Privileged intents not enabled in Discord Developer Portal or exceeding bitfield limit.

**Solution Steps:**
1. Check current intents value in code:
   ```python
   # In main.py, calculate your intent value
   intents = discord.Intents.default()
   intents.message_content = True
   intents.members = True
   intents.presences = True
   print(intents.value)  # Should be <= 32767
   ```

2. Enable privileged intents in Developer Portal:
   - Go to Bot settings
   - Scroll to "Privileged Gateway Intents"
   - Enable: SERVER MEMBERS INTENT
   - Enable: MESSAGE CONTENT INTENT
   - Enable: PRESENCE INTENT (if needed)

3. If using `Intents.all()`, reduce to minimum required:
   ```python
   intents = discord.Intents.default()
   intents.message_content = True
   intents.voice_states = True
   intents.members = True
   intents.presences = True
   ```

**Prevention:**
- Only request intents you actually use
- Document required intents in setup guide

---

### Permission Issues

**Symptoms:**
```
discord.errors.Forbidden: 403 Forbidden (error code: 50013): Missing Permissions
 discord.ext.commands.errors.BotMissingPermissions: Bot missing permissions
```

**Root Cause:**
Bot lacks required permissions in the server or channel.

**Solution Steps:**
1. Check required permissions:
   ```python
   # In your bot code, check current permissions
   permissions = ctx.channel.permissions_for(ctx.guild.me)
   print(f"Send Messages: {permissions.send_messages}")
   print(f"Embed Links: {permissions.embed_links}")
   print(f"Read History: {permissions.read_message_history}")
   ```

2. Required permissions for acore_bot:
   - Send Messages
   - Embed Links
   - Read Message History
   - Add Reactions
   - Connect (for voice)
   - Speak (for voice)
   - Manage Webhooks (for persona spoofing)

3. Generate new invite link with correct permissions:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=277958189136&scope=bot%20applications.commands
   ```

4. Re-invite the bot with proper permissions.

**Prevention:**
- Use permission calculator: https://discordapi.com/permissions.html
- Document required permissions in bot description
- Check permissions programmatically before commands

---

## Adapter Issues

### CLI Adapter Not Reading Input

**Symptoms:**
```
Bot starts but doesn't respond to terminal input
No output when typing in CLI
```

**Root Cause:**
CLI adapter not properly initialized or event loop blocking.

**Solution Steps:**
1. Check if CLI adapter is loaded:
   ```bash
   grep -r "CLIAdapter\|cli_adapter" cogs/ adapters/
   ```

2. Verify CLI mode is enabled:
   ```bash
   cat .env | grep BOT_MODE
   # Should be: BOT_MODE=cli or BOT_MODE=hybrid
   ```

3. Run bot in CLI-only mode for testing:
   ```bash
   BOT_MODE=cli uv run python main.py
   ```

4. Check for blocking operations:
   ```python
   # Ensure input reading is async
   import asyncio
   user_input = await asyncio.get_event_loop().run_in_executor(
       None, input, "> "
   )
   ```

**Prevention:**
- Use async input libraries
- Test CLI mode separately from Discord

---

### Discord Adapter Not Receiving Messages

**Symptoms:**
```
No output in logs when messages are sent
on_message not triggering
```

**Root Cause:**
Message intent disabled, bot blocked, or cog not loaded.

**Solution Steps:**
1. Check if cogs are loaded:
   ```python
   # In on_ready
   print(f"Loaded cogs: {bot.cogs.keys()}")
   ```

2. Verify `on_message` is defined correctly:
   ```python
   async def on_message(self, message):
       if message.author.bot:
           return
       await self.process_commands(message)
       # Your handling logic here
   ```

3. Check for message content intent:
   ```python
   intents = discord.Intents.default()
   intents.message_content = True  # REQUIRED
   ```

4. Test with a simple ping:
   ```python
   @commands.Cog.listener()
   async def on_message(self, message):
       if message.content == "ping":
           await message.channel.send("pong")
   ```

**Prevention:**
- Always include message content intent check in startup
- Log all cog loading successes/failures

---

### Event Bus Not Working

**Symptoms:**
```
Events not being received by subscribers
Pub/sub pattern not functioning
```

**Root Cause:**
Event bus not initialized, subscribers not registered, or async issues.

**Solution Steps:**
1. Check event bus initialization:
   ```python
   from services.core.event_bus import EventBus
   
   event_bus = EventBus()
   await event_bus.start()
   ```

2. Verify subscriber registration:
   ```python
   @event_bus.subscribe("message_received")
   async def handle_message(data):
       print(f"Received: {data}")
   ```

3. Check if events are being published:
   ```python
   await event_bus.publish("message_received", {"content": "test"})
   ```

4. Add debug logging:
   ```python
   event_bus.add_listener(lambda e: print(f"Event: {e}"))
   ```

**Prevention:**
- Use type hints for event data
- Add event schema validation

---

## Framework Issues

### Core Types Import Errors

**Symptoms:**
```
ImportError: cannot import name 'Config' from 'config'
ModuleNotFoundError: No module named 'services.core'
```

**Root Cause:**
Python path issues, circular imports, or missing `__init__.py` files.

**Solution Steps:**
1. Check project structure:
   ```bash
   ls -la services/core/
   # Should see __init__.py
   ```

2. Verify imports use correct paths:
   ```python
   # Correct
   from config import Config
   from services.core.factory import ServiceFactory
   
   # Incorrect (missing dots)
   from .config import Config
   ```

3. Check for circular imports:
   ```bash
   grep -r "from services" --include="*.py" | head -20
   ```

4. Run from project root:
   ```bash
   cd /root/acore_bot
   uv run python main.py
   ```

**Prevention:**
- Always run from project root
- Use absolute imports
- Avoid circular dependencies

---

### Service Factory Issues

**Symptoms:**
```
AttributeError: 'ServiceFactory' object has no attribute 'create_services'
KeyError: 'ollama'
NoneType has no attribute 'chat'
```

**Root Cause:**
Services not properly initialized, dependencies missing, or factory not called.

**Solution Steps:**
1. Check factory initialization in `main.py`:
   ```python
   factory = ServiceFactory(self)
   self.services = factory.create_services()
   ```

2. Verify service creation:
   ```python
   print(f"Available services: {self.services.keys()}")
   print(f"Ollama service: {self.services.get('ollama')}")
   ```

3. Check service dependencies:
   ```python
   # In ServiceFactory, ensure order is correct
   self._init_core()      # First
   self._init_llm()       # After core
   self._init_memory()    # After LLM
   ```

4. Check for initialization errors:
   ```bash
   grep -i "error\|failed\|exception" logs/bot.log | head -20
   ```

**Prevention:**
- Add service dependency graph
- Log all service initialization steps
- Use dependency injection

---

### Event Emission Problems

**Symptoms:**
```
Events fire but handlers don't execute
Async event handlers block
```

**Root Cause:**
Event handlers not async, exceptions swallowed, or wrong event name.

**Solution Steps:**
1. Verify handler is async:
   ```python
   # Correct
   @event_bus.subscribe("test")
   async def handler(data):
       await asyncio.sleep(1)
   
   # Wrong (blocks event loop)
   @event_bus.subscribe("test")
   def handler(data):
       time.sleep(1)
   ```

2. Add error handling:
   ```python
   @event_bus.subscribe("test")
   async def handler(data):
       try:
           await process(data)
       except Exception as e:
           logger.error(f"Handler failed: {e}")
   ```

3. Check event name spelling:
   ```python
   # Published as
   await event_bus.publish("message_received", data)
   
   # Subscribed as
   @event_bus.subscribe("message_received")  # Must match exactly
   ```

**Prevention:**
- Use constants for event names
- Add handler timeout mechanisms

---

## LLM Issues

### OpenRouter Connection

**Symptoms:**
```
aiohttp.client_exceptions.ClientConnectorError: Cannot connect to host openrouter.ai:443
HTTP 401: Invalid API key
```

**Root Cause:**
API key invalid, network issues, or OpenRouter service down.

**Solution Steps:**
1. Verify API key in `.env`:
   ```bash
   cat .env | grep OPENROUTER_API_KEY
   ```

2. Test OpenRouter connectivity:
   ```bash
   curl https://openrouter.ai/api/v1/models \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

3. Check network/firewall:
   ```bash
   nc -zv openrouter.ai 443
   ```

4. Verify model availability:
   ```bash
   curl https://openrouter.ai/api/v1/models | jq '.data[].id'
   ```

5. Check rate limits:
   ```python
   # Add retry logic
   from tenacity import retry, stop_after_attempt
   
   @retry(stop=stop_after_attempt(3))
   async def call_openrouter():
       # API call here
   ```

**Prevention:**
- Use fallback providers
- Implement retry with exponential backoff
- Monitor API usage

---

### Ollama Not Responding

**Symptoms:**
```
Connection refused: localhost:11434
Ollama service timeout
Error: model not found
```

**Root Cause:**
Ollama not running, wrong host configuration, or model not pulled.

**Solution Steps:**
1. Check if Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   # Should return JSON with available models
   ```

2. Start Ollama if not running:
   ```bash
   ollama serve
   # Or as systemd service:
   sudo systemctl start ollama
   ```

3. Verify OLLAMA_HOST in `.env`:
   ```bash
   # For local
   OLLAMA_HOST=http://localhost:11434
   
   # For remote
   OLLAMA_HOST=http://your-server:11434
   ```

4. Pull required model:
   ```bash
   ollama pull llama3.2
   ```

5. Test model directly:
   ```bash
   ollama run llama3.2 "Hello"
   ```

6. Check Ollama logs:
   ```bash
   # systemd
   journalctl -u ollama -f
   
   # Direct
   ollama serve 2>&1 | tee ollama.log
   ```

**Prevention:**
- Use systemd for Ollama auto-start
- Add health check endpoint
- Pre-pull models in setup scripts

---

### Model Not Found Errors

**Symptoms:**
```
Error: model 'llama3.2' not found, try pulling it first
openai.NotFoundError: The model 'gpt-4' does not exist
```

**Root Cause:**
Model not available on provider, name mismatch, or quota exceeded.

**Solution Steps:**
1. List available Ollama models:
   ```bash
   ollama list
   ```

2. Pull the missing model:
   ```bash
   ollama pull llama3.2
   ```

3. For OpenRouter, verify model ID:
   ```bash
   curl https://openrouter.ai/api/v1/models | jq '.data[].id' | grep -i "llama"
   ```

4. Check if using correct provider:
   ```bash
   cat .env | grep LLM_PROVIDER
   # Should be: ollama or openrouter
   ```

5. Update `.env` with correct model:
   ```bash
   # For Ollama
   OLLAMA_MODEL=llama3.2
   
   # For OpenRouter
   OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct
   ```

**Prevention:**
- Document required models in README
- Add model availability check on startup

---

## Persona Issues

### Characters Not Loading

**Symptoms:**
```
No characters available
PersonaSystem initialized with 0 personas
Error loading character file
```

**Root Cause:**
Character files missing, wrong path, invalid JSON, or ACTIVE_PERSONAS not set.

**Solution Steps:**
1. Check character directory:
   ```bash
   ls -la prompts/characters/
   # Should see .json files
   ```

2. Verify ACTIVE_PERSONAS in `config.py`:
   ```python
   ACTIVE_PERSONAS = [
       "dagoth_ur.json",
       "scav.json",
       # ...
   ]
   ```

3. Validate JSON files:
   ```bash
   for f in prompts/characters/*.json; do
       python -m json.tool "$f" > /dev/null && echo "$f: valid" || echo "$f: INVALID"
   done
   ```

4. Check file permissions:
   ```bash
   ls -la prompts/characters/*.json
   # Should be readable by bot user
   ```

5. Manual reload:
   ```
   !reload_characters
   ```

**Prevention:**
- Validate JSON on import
- Add character load status logging
- Use JSON schemas

---

### Webhook Spoofing Not Working

**Symptoms:**
```
Bot responds with default username instead of character name
No avatar change
Webhook error: 403 Forbidden
```

**Root Cause:**
Missing webhook permissions, webhook creation failed, or webhook URL invalid.

**Solution Steps:**
1. Check bot permissions:
   - Manage Webhooks (required)
   - Manage Messages (for cleanup)

2. Verify webhook creation:
   ```python
   webhooks = await channel.webhooks()
   print(f"Existing webhooks: {len(webhooks)}")
   
   # Create webhook
   webhook = await channel.create_webhook(name="acore_bot")
   ```

3. Check webhook URL in persona:
   ```python
   # Persona should have webhook_url or use channel webhooks
   persona.webhook_url = webhook.url
   ```

4. Test webhook manually:
   ```bash
   curl -X POST "$WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{"content":"Test","username":"TestCharacter"}'
   ```

5. Regenerate invite with webhook permission:
   ```
   Permissions needed: 0x20000000 (Manage Webhooks)
   Full permissions: 277958189136
   ```

**Prevention:**
- Always check permissions before webhook operations
- Cache webhook objects
- Fallback to regular messages if webhooks fail

---

### Persona Switching Errors

**Symptoms:**
```
/set_character fails with "Character not found"
Persona doesn't change after command
Wrong persona responds
```

**Root Cause:**
Character not loaded, case sensitivity, or routing logic issue.

**Solution Steps:**
1. List available characters:
   ```
   /list_characters
   ```

2. Check exact character ID:
   ```bash
   grep '"id"' prompts/characters/*.json
   ```

3. Use correct case:
   ```
   # Correct
   /set_character dagoth_ur
   
   # Wrong
   /set_character Dagoth_Ur
   ```

4. Check persona system state:
   ```python
   persona_system = bot.services.get('persona_system')
   print(f"Loaded personas: {persona_system.personas.keys()}")
   ```

5. Reload characters:
   ```
   !reload_characters
   ```

**Prevention:**
- Normalize character IDs (lowercase, no spaces)
- Provide fuzzy matching
- Log persona routing decisions

---

## Debugging Tips

### Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG
LOG_TO_FILE=true
LOG_FILE_PATH=logs/debug.log
```

### Add Breakpoints

```python
import pdb; pdb.set_trace()  # Python debugger

# Or use logging
logger.debug(f"Variable value: {variable}")
```

### Monitor Resources

```bash
# Watch bot resource usage
watch -n 1 'ps aux | grep python'

# Monitor network connections
ss -tuln | grep :11434  # Ollama
ss -tuln | grep :8880   # TTS
```

### Test Components Isolated

```python
# Test LLM only
python -c "
from services.llm.ollama_service import OllamaService
import asyncio

async def test():
    service = OllamaService(host='http://localhost:11434')
    await service.initialize()
    result = await service.chat([{'role': 'user', 'content': 'hi'}])
    print(result)

asyncio.run(test())
"
```

### Check Environment

```python
# In Python shell
import os
print(f"OLLAMA_HOST: {os.getenv('OLLAMA_HOST')}")
print(f"DISCORD_TOKEN set: {bool(os.getenv('DISCORD_TOKEN'))}")
```

---

## Getting Help

### Gather Information

Before asking for help, collect:

1. **Bot version:**
   ```bash
   git log --oneline -1
   ```

2. **Python version:**
   ```bash
   python --version
   ```

3. **Relevant logs:**
   ```bash
   tail -n 100 logs/bot.log
   ```

4. **Config (sanitized):**
   ```bash
   cat .env | grep -v TOKEN | grep -v KEY
   ```

5. **System info:**
   ```bash
   uname -a
   free -h
   df -h
   ```

### Where to Ask

- **Discord:** Check the bot's support server
- **GitHub Issues:** For bugs and feature requests
- **Documentation:** Review relevant docs in `docs/`

### Good Bug Report Template

```
**Description:**
Clear description of the issue

**Steps to Reproduce:**
1. Step one
2. Step two

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Logs:**
```
Paste relevant log output
```

**Environment:**
- OS: Ubuntu 22.04
- Python: 3.11.4
- Bot commit: abc123
```

---

**Last Updated:** 2025-02-20
**Version:** 1.0
