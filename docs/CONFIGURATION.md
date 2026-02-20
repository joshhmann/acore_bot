# Acore Framework Configuration Guide

Complete guide for configuring the Acore Bot framework.

## Table of Contents

- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Adapter Configuration](#adapter-configuration)
- [Feature Toggles](#feature-toggles)
- [Persona Configuration](#persona-configuration)
- [Example Configurations](#example-configurations)
- [Security Best Practices](#security-best-practices)

---

## Quick Start

Minimum configuration to get started:

```bash
# Discord (required for Discord adapter)
DISCORD_TOKEN=your_discord_bot_token_here

# LLM Provider (choose one)
# Option 1: OpenRouter
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key_here

# Option 2: Ollama
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434

# Personas (comma-separated list of JSON files)
ACTIVE_PERSONAS=dagoth_ur.json,scav.json,toad.json
```

---

## Environment Variables

### Discord Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DISCORD_TOKEN` | Discord bot token | - | Yes (for Discord) |
| `DISCORD_PREFIX` | Command prefix | `!` | No |
| `ACORE_DISCORD_ENABLED` | Enable Discord adapter | `true` | No |

### LLM Configuration

#### OpenRouter

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LLM_PROVIDER` | Set to `openrouter` | - | Yes |
| `OPENROUTER_API_KEY` | OpenRouter API key | - | Yes |
| `OPENROUTER_MODEL` | Model identifier | `x-ai/grok-3-fast` | No |

#### Ollama

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LLM_PROVIDER` | Set to `ollama` | - | Yes |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` | No |
| `OLLAMA_MODEL` | Model name | `llama3.2` | No |

#### Thinking Model

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `THINKING_MODEL_PROVIDER` | Provider for thinking | `openrouter` | No |
| `THINKING_MODEL` | Cheap model for decisions | `meta-llama/llama-3.2-1b-instruct` | No |

### Adapter Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ACORE_DISCORD_ENABLED` | Enable Discord adapter | `true` | No |
| `ACORE_CLI_ENABLED` | Enable CLI adapter | `false` | No |

---

## Adapter Configuration

### Discord Adapter

The Discord adapter connects to Discord and handles all Discord-specific functionality.

```python
# In your launcher or main.py
from adapters.discord.adapter import DiscordInputAdapter
from adapters.discord.output import DiscordOutputAdapter

discord_input = DiscordInputAdapter(
    token="your_token_here",
    command_prefix="!",
    intents=None  # Uses default intents
)
```

**Intents Configuration:**

```python
import discord

intents = discord.Intents.default()
intents.message_content = True  # Required for reading messages
intents.voice_states = True     # Required for voice features
intents.presences = True        # Required for presence tracking
intents.members = True          # Required for member tracking

discord_input = DiscordInputAdapter(
    token="your_token",
    intents=intents
)
```

### CLI Adapter

The CLI adapter provides a command-line interface for interacting with personas.

```bash
# Enable CLI adapter
export ACORE_CLI_ENABLED=true

# Run CLI
python -m adapters.cli
```

**Message Format:**
```
@persona_name Your message here
```

Example:
```
@dagoth_ur Hello, how are you?
```

---

## Feature Toggles

### Core Features

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_PERSONA_SYSTEM` | Enable persona system | `true` |
| `PROACTIVE_ENGAGEMENT_ENABLED` | Enable proactive messages | `true` |
| `RAG_ENABLED` | Enable vector search | `true` |
| `USER_PROFILES_AUTO_LEARN` | Auto-learn user facts | `true` |

### Voice Features

| Variable | Description | Default |
|----------|-------------|---------|
| `TTS_ENABLED` | Enable text-to-speech | `false` |
| `RVC_ENABLED` | Enable voice conversion | `false` |
| `STT_ENABLED` | Enable speech-to-text | `false` |

### Analytics

| Variable | Description | Default |
|----------|-------------|---------|
| `ANALYTICS_DASHBOARD_ENABLED` | Enable web dashboard | `false` |
| `ANALYTICS_DASHBOARD_PORT` | Dashboard port | `8080` |
| `ANALYTICS_API_KEY` | API key for dashboard | - |

---

## Persona Configuration

### Active Personas

Set which personas are active:

```bash
ACTIVE_PERSONAS=dagoth_ur.json,scav.json,toad.json,maury.json
```

Persona files are stored in `prompts/characters/`.

### Persona JSON Format

```json
{
  "id": "character_name",
  "display_name": "Display Name",
  "description": "Character description",
  "personality": "Character personality traits",
  "scenario": "Character scenario/context",
  "first_message": "Hello! I'm {{char}}.",
  "avatar_url": "https://example.com/avatar.png",
  "framework": "neuro"
}
```

---

## Example Configurations

### Minimal Discord Bot

```bash
# .env
DISCORD_TOKEN=your_token_here
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
ACTIVE_PERSONAS=dagoth_ur.json
```

### Multi-Platform (Discord + CLI)

```bash
# .env
DISCORD_TOKEN=your_token_here
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
ACTIVE_PERSONAS=dagoth_ur.json,scav.json

# Adapters
ACORE_DISCORD_ENABLED=true
ACORE_CLI_ENABLED=true
```

### Local Development (Ollama)

```bash
# .env
DISCORD_TOKEN=your_token_here
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
THINKING_MODEL=llama3.2
ACTIVE_PERSONAS=dagoth_ur.json
PROACTIVE_ENGAGEMENT_ENABLED=false
RAG_ENABLED=false
```

### Production with Analytics

```bash
# .env
DISCORD_TOKEN=your_token_here
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
ACTIVE_PERSONAS=dagoth_ur.json,scav.json,toad.json,maury.json,hal9000.json,zenos.json

# Features
USE_PERSONA_SYSTEM=true
PROACTIVE_ENGAGEMENT_ENABLED=true
RAG_ENABLED=true
USER_PROFILES_AUTO_LEARN=true

# Analytics
ANALYTICS_DASHBOARD_ENABLED=true
ANALYTICS_DASHBOARD_PORT=8080
ANALYTICS_API_KEY=your_secure_random_key_here
```

---

## Security Best Practices

### 1. Never Commit Secrets

Add to `.gitignore`:
```
.env
.env.local
*.key
*.pem
```

### 2. Use Environment Variables

❌ **Don't hardcode tokens:**
```python
token = "abc123"  # Bad!
```

✅ **Use environment variables:**
```python
import os
token = os.environ["DISCORD_TOKEN"]  # Good!
```

### 3. Rotate Tokens Regularly

- Discord bot tokens: Rotate monthly
- API keys: Rotate quarterly
- Use a secrets manager in production

### 4. Restrict Token Permissions

- Only enable necessary Discord intents
- Use minimal required API scopes
- Create separate tokens for dev/prod

### 5. Validate Configuration

```python
import os

required_vars = ["DISCORD_TOKEN", "OPENROUTER_API_KEY"]
missing = [var for var in required_vars if not os.environ.get(var)]

if missing:
    raise ValueError(f"Missing required environment variables: {missing}")
```

---

## Configuration Loading Order

1. **Environment variables** (highest priority)
2. **`.env` file** (if python-dotenv is installed)
3. **Configuration file** (config.json if present)
4. **Default values** (lowest priority)

---

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
