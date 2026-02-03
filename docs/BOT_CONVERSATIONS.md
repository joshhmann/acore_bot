# Bot-to-Bot Conversations - User Guide

## Overview

The bot-to-bot conversation feature enables AI personas to have structured, multi-turn conversations with each other. Perfect for character development, entertainment, and studying AI behavior.

**Key Features:**
- **2-5 personas** participate in structured conversations
- **Up to 10 turns** per conversation (configurable)
- **Webhook spoofing** for authentic character appearances
- **Quality metrics** track conversation coherence
- **Human review workflow** for approving/rejecting conversations
- **RAG integration** for searchable conversation history

---

## Quick Start

### Basic Usage

Start a conversation between two characters:

```
/bot_conversation participants:dagoth_ur,scav topic:The nature of existence
```

The bots will:
1. Start conversing in the current channel
2. Take turns speaking (with 1-second delays for natural pacing)
3. Automatically end after 10 turns or natural conclusion
4. Post a summary with quality metrics

### Advanced Options

```
/bot_conversation 
  participants:dagoth_ur,scav,toad 
  topic:What is the best pizza topping?
  max_turns:15
  enable_metrics:true
```

**Parameters:**
- `participants` (**required**): Comma-separated list of persona IDs (2-5 personas)
- `topic` (**required**): What the bots should discuss
- `max_turns` (optional): Maximum conversation turns (default: 10, max: 20)
- `enable_metrics` (optional): Calculate quality metrics (default: true)

---

## Configuration

### Enable Bot Conversations

Add to your `.env` file:

```env
# Bot-to-Bot Conversations
BOT_CONVERSATION_ENABLED=true
BOT_CONVERSATION_MAX_TURNS=10
BOT_CONVERSATION_TURN_TIMEOUT=60
BOT_CONVERSATION_DETAILED_METRICS=false
```

**Configuration Options:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_CONVERSATION_ENABLED` | `true` | Enable/disable bot conversations |
| `BOT_CONVERSATION_MAX_TURNS` | `10` | Default max turns per conversation |
| `BOT_CONVERSATION_TURN_TIMEOUT` | `60` | Seconds before timeout (per turn) |
| `BOT_CONVERSATION_DETAILED_METRICS` | `false` | Calculate expensive metrics (character consistency) |

### Active Personas

Ensure your personas are active in `ACTIVE_PERSONAS`:

```env
ACTIVE_PERSONAS=dagoth_ur.json,scav.json,toad.json,maury.json
```

Personas must be defined in `prompts/characters/` directory.

---

## Understanding Quality Metrics

After each conversation, the system calculates quality scores:

### Metrics Explained

**1. Turn Relevance** (0.0 - 1.0)
- Measures how well each message relates to the previous message
- Uses Jaccard similarity between consecutive messages
- **Good:** > 0.3 | **Fair:** 0.2-0.3 | **Poor:** < 0.2

**2. Vocabulary Diversity** (0.0 - 1.0)
- Unique words / total words ratio
- Higher = more varied language
- **Good:** > 0.5 | **Fair:** 0.3-0.5 | **Poor:** < 0.3

**3. Response Latency** (seconds)
- Average time to generate each message
- **Fast:** < 2s | **Normal:** 2-5s | **Slow:** > 5s

**4. Character Consistency** (0.0 - 1.0) *[Optional, expensive]*
- Measures consistency of message lengths (low variance = consistent)
- Only calculated if `BOT_CONVERSATION_DETAILED_METRICS=true`
- **Consistent:** > 0.7 | **Moderate:** 0.4-0.7 | **Inconsistent:** < 0.4

**5. Quality Score** (0.0 - 1.0)
- Weighted average of all metrics
- **Excellent:** > 0.7 | **Good:** 0.5-0.7 | **Poor:** < 0.5

---

## Review Workflow

### Manual Review

After a conversation completes, you can manually trigger review:

```
/review_conversation conversation_id:conv-20260129-123456-7890
```

The bot will:
1. Post the full conversation transcript in the channel
2. Add reaction buttons: ✅ (approve) | ❌ (reject)
3. Wait for admin review

**Approve (✅):**
- Conversation is archived after 24 hours
- Indexed to RAG for future retrieval

**Reject (❌):**
- Conversation is immediately archived
- Marked as rejected, not indexed to RAG

### Automatic Review

Set automatic review thresholds:

```env
# Auto-approve conversations with quality score > 0.7
BOT_CONVERSATION_AUTO_APPROVE_THRESHOLD=0.7
```

---

## Conversation Storage

### File Locations

Conversations are stored in JSONL format:

```
data/
├── conversations/           # Active conversations
│   └── conv-20260129-*.jsonl
└── conversation_archives/   # Archived conversations (30-day retention)
    └── conv-20260129-*.jsonl
```

### Archival Schedule

- **Review Window:** 24 hours after completion
- **Auto-Archival:** After review window expires
- **Retention:** 30 days (then auto-deleted)
- **RAG Indexing:** Approved conversations indexed for search

### Searching Past Conversations

Use RAG search to find relevant past conversations:

```python
# Example: Search for conversations about pizza
from services.core.factory import ServiceFactory

rag = ServiceFactory.get_service("rag")
results = await rag.search("pizza toppings", categories=["conversations"])
```

---

## Troubleshooting

### Conversation Doesn't Start

**Issue:** `/bot_conversation` command fails

**Solutions:**
1. Check `BOT_CONVERSATION_ENABLED=true` in `.env`
2. Verify personas exist: `!list_characters`
3. Ensure channel has webhook permissions
4. Check bot logs for errors: `journalctl -f -u discordbot`

### Conversation Ends Immediately

**Issue:** Conversation terminates after 1-2 turns

**Causes:**
- Persona says farewell keyword (`goodbye`, `farewell`, etc.)
- Turn timeout exceeded (default: 60 seconds)
- LLM service error

**Solutions:**
1. Increase timeout: `BOT_CONVERSATION_TURN_TIMEOUT=120`
2. Check LLM service status
3. Review conversation logs in `data/conversations/`

### Webhooks Not Created

**Issue:** Bots post as main bot instead of character avatars

**Causes:**
- Channel lacks webhook permissions
- Discord rate limits (max 10 webhooks per server)

**Solutions:**
1. Grant "Manage Webhooks" permission to bot role
2. Webhook pool automatically manages rate limits (LRU eviction)
3. Manually delete unused webhooks to free slots

### Poor Quality Scores

**Issue:** Conversations have low relevance or diversity

**Solutions:**
1. Improve persona definitions with richer personalities
2. Use more specific topics
3. Enable diverse participant selection (different personality types)
4. Adjust `temperature` in LLM config (higher = more creative)

### Conversations Not Indexed

**Issue:** Can't find conversations in RAG search

**Causes:**
- Conversation rejected during review
- RAG service not configured
- Archival service not running

**Solutions:**
1. Check review status: `/review_conversation`
2. Verify `RAG_ENABLED=true` in `.env`
3. Manually index: `/archive_conversation conversation_id:... index:true`

---

## Best Practices

### Topic Selection

**Good Topics:**
- ✅ "The ethics of artificial intelligence"
- ✅ "Which is better: cats or dogs?"
- ✅ "Should pineapple go on pizza?"

**Poor Topics:**
- ❌ "Talk about stuff" (too vague)
- ❌ "Discuss" (no subject)
- ❌ "Say hello" (too simple)

### Participant Mixing

**Diverse Personalities:**
- Mix serious + comedic personas for dynamic conversations
- Example: `dagoth_ur,scav` (serious philosopher + chaotic comedian)

**Similar Personalities:**
- Can lead to echo chambers but interesting for character studies
- Example: `hal9000,zenos` (two stoic, analytical characters)

### Turn Limits

- **Short conversations (5-7 turns):** Quick exchanges, rapid-fire debates
- **Medium conversations (10-15 turns):** Default, balanced depth
- **Long conversations (15-20 turns):** Deep discussions, character development

---

## Advanced Features

### Headless Testing

Run conversations programmatically without Discord:

```python
from services.conversation.orchestrator import BotConversationOrchestrator
from services.conversation.state import ConversationConfig

# Create orchestrator
orchestrator = BotConversationOrchestrator(...)

# Run headless conversation
config = ConversationConfig(
    max_turns=10,
    enable_metrics=True,
    seed=42  # For reproducibility
)

conversation_id = await orchestrator.start_conversation(
    participants=["bot1", "bot2"],
    topic="Testing deterministic output",
    channel=mock_channel,
    config=config
)
```

### Deterministic Conversations

Set a seed for reproducible conversations:

```python
config = ConversationConfig(seed=12345)
```

Same seed = same speaker order (useful for testing).

### Custom Turn Strategies

Configure how speakers are selected:

- `ROUND_ROBIN`: Strict alternation (A, B, A, B, ...)
- `RANDOM`: Random selection (no immediate repeats)
- `AFFINITY_WEIGHTED`: Higher affinity = more speaking time
- `ROLE_HIERARCHY`: Leaders speak more than members

---

## Example Scenarios

### Character Development

```
/bot_conversation 
  participants:dagoth_ur,scav 
  topic:What motivates you in life?
  max_turns:15
```

Watch characters reveal their philosophies and build relationships.

### Entertainment

```
/bot_conversation 
  participants:maury,toad,scav 
  topic:Who ate the last slice of pizza?
  max_turns:12
```

Chaos ensues with multiple comedic characters.

### Research

```
/bot_conversation 
  participants:hal9000,zenos 
  topic:The trolley problem in AI ethics
  max_turns:20
  enable_metrics:true
```

Study how different AI architectures approach ethical dilemmas.

---

## Related Commands

| Command | Description |
|---------|-------------|
| `/bot_conversation` | Start a new bot-to-bot conversation |
| `/review_conversation` | Post conversation for human review |
| `/archive_conversation` | Manually archive a conversation |
| `/list_conversations` | List recent conversations |
| `/get_conversation` | Retrieve full conversation transcript |

---

## Further Reading

- [Architecture Documentation](BOT_CONVERSATIONS_ARCHITECTURE.md) - Technical deep dive
- [Persona System Guide](../README.md#multi-persona-system) - Creating characters
- [RAG Integration](FEATURES.md#memory-systems) - Search and retrieval

---

## Support

**Issues?** Check logs: `journalctl -f -u discordbot`

**Questions?** See [Troubleshooting](#troubleshooting) or open a GitHub issue.
