# Bot Personality, RAG & MCP Guide

Your bot now supports **customizable personalities**, **knowledge from documents (RAG)**, and **external tool integration (MCP)**!

## 🎭 Custom Personalities (System Prompts)

### Quick Start

1. **Choose a pre-made personality:**
   ```env
   # In .env:
   SYSTEM_PROMPT_FILE=./prompts/friendly.txt
   ```

2. **Available personalities:**
   - `default.txt` - Standard helpful assistant
   - `friendly.txt` - Warm, casual, uses emojis 😊
   - `professional.txt` - Formal, business-appropriate
   - `gaming.txt` - Gaming buddy with gamer lingo 🎮
   - `pirate.txt` - Fun pirate character 🏴‍☠️

3. **Restart the bot:**
   ```bash
   uv run python main.py
   ```

### Create Your Own Personality

1. **Create a new prompt file:**
   ```bash
   # Create prompts/my_bot.txt
   ```

2. **Write your personality:**
   ```
   You are [character name], a [personality trait] AI assistant.

   Your traits:
   - Trait 1
   - Trait 2
   - Trait 3

   Communication style:
   - How you talk
   - What you emphasize
   - Tone and voice
   ```

3. **Use it:**
   ```env
   SYSTEM_PROMPT_FILE=./prompts/my_bot.txt
   ```

### Quick Override

Set personality directly in `.env` (overrides file):
```env
SYSTEM_PROMPT="You are a sarcastic but helpful AI who loves puns."
```

### Examples

**Gaming Buddy:**
```
You are a gaming buddy and expert assistant! 🎮
- Use gaming slang naturally
- Get hyped about wins
- Share strategies and tips
- Keep it fun and competitive
```

**Study Helper:**
```
You are a patient tutor and study companion.
- Break down complex topics
- Use analogies and examples
- Encourage learning
- Ask guiding questions
```

**Creative Partner:**
```
You are an inspiring creative companion.
- Encourage experimentation
- Brainstorm ideas together
- Celebrate creativity
- Provide constructive feedback
```

See [prompts/CUSTOM.md](prompts/CUSTOM.md) for detailed guide!

---

## 📚 RAG (Retrieval-Augmented Generation)

Give your bot knowledge from your own documents!

### What is RAG?

RAG lets the bot:
- Access information from your documents
- Answer questions about your content
- Provide context-aware responses
- Remember facts from your knowledge base

### Setup

1. **Enable RAG:**
   ```env
   RAG_ENABLED=true
   RAG_DOCUMENTS_PATH=./data/documents
   ```

2. **Add documents:**
   ```bash
   # Create documents directory
   mkdir -p data/documents

   # Add your documents (.txt or .md files)
   cp my_knowledge.txt data/documents/
   cp company_info.md data/documents/
   ```

3. **Restart the bot** - it will automatically load all documents

### Use Cases

**Company Knowledge Base:**
```
data/documents/
  company_policies.md
  product_info.txt
  faq.md
```
Bot can now answer questions about your company!

**Game Guides:**
```
data/documents/
  beginner_guide.md
  advanced_strategies.txt
  item_database.txt
```
Bot becomes a game expert!

**Personal Notes:**
```
data/documents/
  recipes.txt
  project_notes.md
  learning_resources.md
```
Bot helps you remember and find information!

### How It Works

```
User: What's our return policy?

Bot searches documents → Finds relevant info → Includes in response

Bot: According to company_policies.md, our return policy is...
```

### Configuration

```env
# Number of relevant documents to use per query
RAG_TOP_K=3

# Where to store documents
RAG_DOCUMENTS_PATH=./data/documents

# Vector store location (for future upgrades)
RAG_VECTOR_STORE=./data/vector_store
```

### Tips

1. **Keep documents focused** - One topic per file
2. **Use clear filenames** - `product_specs.txt` not `doc1.txt`
3. **Update regularly** - Add new documents anytime, restart bot
4. **Organize with folders** - `data/documents/products/`, `data/documents/policies/`

### Limitations (Current Implementation)

- ⚠️ **Simple keyword matching** - Not semantic search (yet!)
- ⚠️ **Reload requires restart** - Changes need bot restart
- ✅ **Good enough for most use cases**

### Upgrade Path (Advanced)

For production RAG with vector embeddings:
```bash
# Install vector DB
uv add chromadb sentence-transformers

# See services/rag.py for implementation notes
```

---

## 🔧 MCP (Model Context Protocol)

Connect your bot to external tools and APIs!

### What is MCP?

MCP allows your bot to:
- **Call external APIs** (weather, news, stock prices)
- **Execute functions** (calculations, data lookups)
- **Access real-time data** (live information)
- **Use tools** (search, translate, analyze)

### Setup

1. **Run an MCP server** (see example below)

2. **Enable MCP:**
   ```env
   MCP_ENABLED=true
   MCP_SERVER_URL=http://localhost:8080
   ```

3. **Restart the bot**

### Example MCP Server

Create `mcp_server.py`:
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

tools = [
    {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": [{"name": "location", "type": "string"}]
    }
]

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/tools")
async def get_tools():
    return {"tools": tools}

class ToolCall(BaseModel):
    tool: str
    arguments: dict

@app.post("/call")
async def call_tool(call: ToolCall):
    if call.tool == "get_weather":
        location = call.arguments["location"]
        # Call weather API here
        return {"result": f"Weather in {location}: Sunny, 72°F"}
    return {"error": "Unknown tool"}
```

Run it:
```bash
uv add fastapi uvicorn
uvicorn mcp_server:app --port 8080
```

### Use Cases

**Weather Bot:**
```python
# MCP server provides weather tool
# Bot can answer: "What's the weather in NYC?"
```

**Stock Bot:**
```python
# MCP server provides stock price tool
# Bot can answer: "What's AAPL stock price?"
```

**Search Bot:**
```python
# MCP server provides web search tool
# Bot can find current information online
```

**Calculator Bot:**
```python
# MCP server provides math tools
# Bot can perform complex calculations
```

### Available Tools in Chat

When MCP is enabled, bot knows about available tools:
```
User: What tools do you have?
Bot: I have access to:
     - get_weather: Get current weather for a location
     - search_web: Search the internet
     - calculate: Perform calculations
```

### Implementation

The bot automatically:
1. Fetches available tools from MCP server
2. Knows when to use them
3. Calls them with proper arguments
4. Returns results to the user

See [services/mcp.py](services/mcp.py) for full implementation!

---

## 🎯 Combining Everything

### Maximum Power Setup

```env
# Custom Personality
SYSTEM_PROMPT_FILE=./prompts/gaming.txt

# RAG for game knowledge
RAG_ENABLED=true
RAG_DOCUMENTS_PATH=./data/game_guides

# MCP for live game stats
MCP_ENABLED=true
MCP_SERVER_URL=http://localhost:8080

# Voice responses
AUTO_REPLY_WITH_VOICE=true
```

**Result:** Gaming buddy bot with knowledge base and live stats! 🎮

### Example Workflows

**Company Support Bot:**
```
Personality: Professional
RAG: Company docs (policies, FAQs, product specs)
MCP: CRM integration, ticket system
Voice: Disabled (text only)
```

**Personal Assistant:**
```
Personality: Friendly
RAG: Personal notes, recipes, references
MCP: Calendar, weather, news APIs
Voice: Enabled
```

**Learning Bot:**
```
Personality: Patient tutor
RAG: Course materials, study guides
MCP: Wikipedia, calculator, translation
Voice: Enabled for explanations
```

---

## ⚙️ Configuration Reference

### Personality
| Setting | Description | Example |
|---------|-------------|---------|
| `SYSTEM_PROMPT_FILE` | Path to prompt file | `./prompts/friendly.txt` |
| `SYSTEM_PROMPT` | Direct prompt (overrides file) | `"You are..."` |

### RAG
| Setting | Description | Default |
|---------|-------------|---------|
| `RAG_ENABLED` | Enable RAG | `false` |
| `RAG_DOCUMENTS_PATH` | Documents directory | `./data/documents` |
| `RAG_TOP_K` | Results per query | `3` |

### MCP
| Setting | Description | Default |
|---------|-------------|---------|
| `MCP_ENABLED` | Enable MCP | `false` |
| `MCP_SERVER_URL` | MCP server URL | `http://localhost:8080` |

---

## 🚀 Quick Examples

### Change Personality
```bash
# Edit .env
SYSTEM_PROMPT_FILE=./prompts/pirate.txt

# Restart
uv run python main.py

# Test
@BotName ahoy!
# Bot: Ahoy there, matey! What can this old sea dog do fer ye?
```

### Add Knowledge
```bash
# Create document
echo "Our store hours are 9 AM to 5 PM Monday-Friday." > data/documents/hours.txt

# Enable RAG
RAG_ENABLED=true

# Restart and test
@BotName what are the store hours?
# Bot: According to hours.txt, our store hours are 9 AM to 5 PM Monday-Friday.
```

### Add Tools
```bash
# Start MCP server
uvicorn mcp_server:app --port 8080

# Enable MCP
MCP_ENABLED=true

# Restart and test
@BotName what's the weather?
# Bot: [Calls weather tool] The weather is sunny, 72°F!
```

---

## 📖 Learn More

- **Prompts:** See [prompts/CUSTOM.md](prompts/CUSTOM.md)
- **RAG Service:** See [services/rag.py](services/rag.py)
- **MCP Service:** See [services/mcp.py](services/mcp.py)
- **Main Docs:** See [README.md](README.md)

Transform your bot into exactly what you need! 🎉
