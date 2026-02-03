# Bot-to-Bot Conversations - Architecture

## Overview

The bot-to-bot conversation system orchestrates multi-turn dialogues between AI personas, enabling character development, entertainment, and behavioral research. This document details the technical architecture, data flows, and extension points.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Discord Channel                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Webhook 1   │  │  Webhook 2   │  │  Webhook 3   │          │
│  │ (Dagoth Ur)  │  │   (Scav)     │  │   (Toad)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────┬────────────────┬────────────────┬──────────────────┘
             │                │                │
             │    Webhook Messages            │
             └────────────────┼────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│              BotConversationOrchestrator                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Conversation Loop (async)                                   │ │
│  │  1. Select next speaker (TurnManager)                        │ │
│  │  2. Build context (history + system prompt)                  │ │
│  │  3. Generate response (LLM)                                  │ │
│  │  4. Send via webhook (WebhookPool)                           │ │
│  │  5. Check termination (TerminationDetector)                  │ │
│  │  6. Repeat until complete                                    │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
┌─────────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────┐
│   Persona   │ │  Turn  │ │  LLM   │ │ Metrics│ │  Archival   │
│   Router    │ │Manager │ │Service │ │Calc    │ │  Service    │
└─────────────┘ └────────┘ └────────┘ └────────┘ └─────────────┘
        │                      │          │          │
        ▼                      ▼          ▼          ▼
┌─────────────┐          ┌────────┐ ┌────────┐ ┌─────────────┐
│   Persona   │          │  LLM   │ │ State  │ │ RAG Service │
│  Definitions│          │Provider│ │Storage │ │             │
│   (JSON)    │          │        │ │(JSONL) │ │             │
└─────────────┘          └────────┘ └────────┘ └─────────────┘
```

---

## Core Components

### 1. BotConversationOrchestrator

**Location:** `services/conversation/orchestrator.py`

**Responsibilities:**
- Manage conversation lifecycle (start, run, complete)
- Coordinate all subcomponents
- Handle errors and timeouts
- Persist conversation state

**Key Methods:**
```python
async def start_conversation(
    participants: List[str],
    topic: str,
    channel: discord.TextChannel,
    config: ConversationConfig
) -> str
```

**State Management:**
- Active conversations stored in-memory (`self.active_conversations`)
- Completed conversations persisted to disk via `ConversationPersistence`
- Background task manages conversation loop

---

### 2. WebhookPool

**Location:** `services/conversation/orchestrator.py`

**Purpose:** Manage Discord webhooks to avoid rate limits (10 webhooks/guild max).

**Features:**
- **LRU Eviction:** Least recently used webhook repurposed for new persona
- **Avatar Caching:** Fetches and caches persona avatars
- **Webhook Reuse:** Same persona = same webhook (no recreation)

**Discord Limits:**
- Max 10 webhooks per guild
- 30 requests/minute per webhook

**Algorithm:**
```python
if persona in pool:
    return existing_webhook
elif pool.size < max_webhooks:
    create_new_webhook()
else:
    evict_lru_webhook()
    repurpose_for_new_persona()
```

---

### 3. TurnManager

**Location:** `services/conversation/turn_manager.py`

**Purpose:** Decide which persona speaks next.

**Strategies:**

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `ROUND_ROBIN` | Strict alternation (A, B, A, B, ...) | Fair, predictable conversations |
| `RANDOM` | Random selection (no immediate repeats) | Natural, varied pacing |
| `AFFINITY_WEIGHTED` | Higher affinity = more speaking time | Relationship-driven conversations |
| `ROLE_HIERARCHY` | Leaders speak more than members | Organizational dynamics |

**Speaker Selection Logic:**
```python
def select_next_speaker(state: ConversationState, strategy: TurnStrategy) -> str:
    exclude_last_speaker()  # Prevent immediate repeats
    
    if strategy == ROUND_ROBIN:
        return next_in_sequence()
    elif strategy == AFFINITY_WEIGHTED:
        weights = [affinity_scores[p] for p in participants]
        return random.choices(participants, weights=weights)[0]
    # ...
```

---

### 4. TerminationDetector

**Location:** `services/conversation/turn_manager.py`

**Purpose:** Detect when conversation should end.

**Termination Conditions:**

1. **Turn Limit Reached:** `turn_count >= max_turns`
2. **Farewell Detected:** Keywords like "goodbye", "farewell", "see you later"
3. **Topic Exhausted:** No questions asked in last 3 messages (after turn 6)
4. **Timeout:** No message in `turn_timeout_seconds`

**Detection Logic:**
```python
FAREWELL_KEYWORDS = [
    "goodbye", "farewell", "see you", "take care",
    "bye", "later", "signing off", "gotta go", "peace out"
]

def should_end_naturally(state: ConversationState) -> bool:
    last_message = state.messages[-1]
    
    # Farewell detection
    if any(keyword in last_message.content.lower() 
           for keyword in FAREWELL_KEYWORDS):
        return True
    
    # Topic exhaustion
    if state.turn_count >= 6:
        recent = state.messages[-3:]
        if not any('?' in msg.content for msg in recent):
            return True
    
    return False
```

---

### 5. ConversationPersistence

**Location:** `services/conversation/persistence.py`

**Purpose:** Save/load conversation state to disk.

**Storage Format:** JSONL (JSON Lines)

**File Structure:**
```
data/
├── conversations/                 # Active conversations
│   └── conv-20260129-123456-7890.jsonl
└── conversation_archives/         # Archived (30-day retention)
    └── conv-20260129-123456-7890.jsonl
```

**JSONL Format:**
```jsonl
{"conversation_id":"conv-...","participants":["bot1","bot2"],"status":"active",...}
{"speaker":"bot1","content":"Hello!","timestamp":"2026-01-29T12:34:56",...}
{"speaker":"bot2","content":"Hi there!","timestamp":"2026-01-29T12:34:58",...}
```

**Methods:**
```python
async def save(state: ConversationState) -> None
async def load(conversation_id: str) -> ConversationState
async def archive(conversation_id: str) -> None
async def list_active() -> List[str]
async def cleanup_old(days: int = 30) -> int
```

---

### 6. ConversationMetricsCalculator

**Location:** `services/conversation/metrics.py`

**Purpose:** Calculate conversation quality metrics.

**Metrics:**

#### Turn Relevance (0.0 - 1.0)
```python
def calculate_turn_relevance(messages: List[Message]) -> float:
    similarities = []
    for i in range(1, len(messages)):
        tokens_a = set(tokenize(messages[i-1].content))
        tokens_b = set(tokenize(messages[i].content))
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        similarities.append(jaccard)
    return sum(similarities) / len(similarities)
```

#### Vocabulary Diversity (0.0 - 1.0)
```python
def calculate_vocab_diversity(messages: List[Message]) -> float:
    all_words = []
    for msg in messages:
        all_words.extend(tokenize(msg.content))
    unique = set(all_words)
    return len(unique) / len(all_words)
```

#### Response Latency (seconds)
```python
def calculate_avg_latency(messages: List[Message]) -> float:
    latencies = [msg.metadata.get('latency', 0.0) for msg in messages]
    return sum(latencies) / len(latencies)
```

#### Character Consistency (0.0 - 1.0) *[Optional]*
```python
def calculate_character_consistency(messages: List[Message]) -> float:
    lengths = [len(msg.content) for msg in messages]
    mean = sum(lengths) / len(lengths)
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    cv = (variance ** 0.5) / mean  # Coefficient of variation
    return max(0.0, 1.0 - cv)  # Lower variance = higher consistency
```

**Quality Score:**
```python
quality_score = (
    0.35 * turn_relevance +
    0.25 * vocab_diversity +
    0.20 * (1 - normalized_latency) +
    0.20 * character_consistency
)
```

---

### 7. ConversationArchivalService

**Location:** `services/conversation/archival.py`

**Purpose:** Archive completed conversations and index to RAG.

**Features:**
- **24-Hour Review Window:** Delay archival for human review
- **Auto-Cleanup:** Delete archives older than 30 days
- **RAG Indexing:** Add approved conversations to searchable database
- **Background Workers:** Periodic archival and cleanup

**Workflow:**
```
Conversation Complete
        │
        ├──→ [24 Hours] ──→ Human Review
        │                      │
        │                      ├──→ ✅ Approve → Index to RAG → Archive
        │                      └──→ ❌ Reject → Archive (no RAG)
        │
        └──→ [30 Days] ──→ Auto-Delete
```

**Background Tasks:**
- `_archival_worker()`: Runs every 60 minutes, archives conversations older than 24 hours
- `_cleanup_worker()`: Runs daily, deletes archives older than 30 days

---

### 8. PersonaRouter Integration

**Location:** `services/persona/router.py` (modified in Task 6)

**Purpose:** Override persona selection during active conversations.

**Routing Phases:**

| Priority | Phase | Logic |
|----------|-------|-------|
| 0 | **Active Conversation** | If channel has active conversation, select from participants only |
| 1 | Explicit Mention | @character_name |
| 2 | Keyword Match | Character-specific keywords |
| 3 | Affinity | User-persona relationship scores |
| 4 | Sticky | Last speaker in channel |
| 5 | Random | Fallback |

**Conversation Context API:**
```python
router.set_active_conversation(channel_id, participants)
router.clear_active_conversation(channel_id)
router.get_active_conversation(channel_id) -> List[str]
```

---

## Data Flow

### Starting a Conversation

```
User executes /bot_conversation
        │
        ▼
ConversationCommandsCog.bot_conversation()
        │
        ├──→ Validate participants
        ├──→ Create ConversationConfig
        └──→ orchestrator.start_conversation()
                │
                ├──→ Generate conversation_id
                ├──→ Create ConversationState
                ├──→ router.set_active_conversation()
                └──→ asyncio.create_task(_run_conversation)
```

### Conversation Loop

```
_run_conversation() starts
        │
        ├──→ Create WebhookPool
        ├──→ Select initial speaker (random)
        │
        └──→ LOOP: while turn_count < max_turns
                │
                ├──→ Build context (system prompt + history)
                ├──→ llm.generate(context)
                ├──→ Create Message object
                ├──→ Send via webhook
                ├──→ Add to state.messages
                ├──→ Increment state.turn_count
                ├──→ Check termination conditions
                │    ├──→ Farewell? → Break
                │    ├──→ Timeout? → Break
                │    └──→ Turn limit? → Continue
                │
                └──→ await asyncio.sleep(1)  # Natural pacing
        │
        ├──→ state.status = COMPLETED
        ├──→ Calculate metrics (if enabled)
        ├──→ persistence.save(state)
        ├──→ archival.index_to_rag(state)
        ├──→ router.clear_active_conversation()
        └──→ Send summary to channel
```

### Message Generation

```
_generate_and_send_message()
        │
        ├──→ persona = router.get_persona(speaker_id)
        ├──→ context = _build_context(state, speaker, is_first)
        │       │
        │       └──→ System prompt + conversation history
        │
        ├──→ response = await llm.generate(
        │        system_prompt=persona.system_prompt,
        │        messages=context,
        │        temperature=0.8
        │    )
        │
        ├──→ message = Message(speaker, response, timestamp, turn_number)
        ├──→ webhook = webhook_pool.get_or_create_webhook(persona)
        └──→ await webhook.send(response)
```

---

## Extension Points

### 1. Custom Turn Strategies

Add new turn selection logic by extending `TurnManager`:

```python
class TurnManager:
    def select_next_speaker(
        self, 
        state: ConversationState,
        custom_logic: Optional[Callable] = None
    ) -> str:
        if custom_logic:
            return custom_logic(state)
        # ... existing logic
```

**Example: Debate Mode**
```python
def debate_mode(state: ConversationState) -> str:
    # Alternate between two "sides"
    turn = state.turn_count
    side_a = state.participants[:len(state.participants)//2]
    side_b = state.participants[len(state.participants)//2:]
    return side_a[turn % len(side_a)] if turn % 2 == 0 else side_b[turn % len(side_b)]
```

### 2. Custom Metrics

Add new quality metrics by extending `ConversationMetricsCalculator`:

```python
class CustomMetrics(ConversationMetricsCalculator):
    def calculate_emotional_arc(self, messages: List[Message]) -> float:
        # Use sentiment analysis to track emotional trajectory
        sentiments = [analyze_sentiment(msg.content) for msg in messages]
        # Return variance or trend measure
```

### 3. Tool Integration (MCP, n8n)

Enable personas to use tools during conversations:

```python
config = ConversationConfig(enable_tools=True)

# In orchestrator._generate_and_send_message():
if config.enable_tools and persona.supports_tools:
    response = await llm.generate_with_tools(
        system_prompt=persona.system_prompt,
        messages=context,
        tools=available_tools
    )
```

### 4. Real-Time Human Intervention

Add callback for human interruptions:

```python
class BotConversationOrchestrator:
    def __init__(self, ..., on_human_message: Optional[Callable] = None):
        self.on_human_message = on_human_message
    
    async def _run_conversation(self, ...):
        # ... in loop
        if self.on_human_message:
            human_input = await self.on_human_message(state)
            if human_input:
                state.messages.append(Message("human", human_input, ...))
```

### 5. Multi-Channel Conversations

Extend to support conversations across multiple channels:

```python
async def start_multi_channel_conversation(
    participants: List[str],
    channels: List[discord.TextChannel],
    topic: str
):
    # Each persona posts in their "home" channel
    # Creates cross-channel narrative
```

---

## Testing Strategy

### Unit Tests

**Coverage:** Individual components in isolation

- `test_conversation_state.py`: State data structure validation
- `test_orchestrator.py`: Orchestrator lifecycle (9 tests)
- `test_turn_management.py`: Turn selection strategies (8 tests)
- `test_conversation_metrics.py`: Metric calculations (27 tests)
- `test_archival.py`: Archival workflows (21 tests)

### Integration Tests

**Coverage:** Service interactions

- `test_phase4.py`: Multi-service integration (existing pattern)
- Validates: Orchestrator + Persistence + Metrics + Archival

### E2E Tests

**Coverage:** Full user-facing workflows

- `test_two_bot_ten_turn_conversation`: Complete 10-turn conversation
- `test_headless_deterministic`: Reproducible output via seeding
- `test_state_recovery`: Persistence across restarts

**Test Infrastructure:**
- `MockConversationChannel`: Headless Discord channel
- `MockWebhook`: Webhook simulation without Discord API
- `MockPersona`: Test persona definitions
- `mock_llm_service`: Deterministic LLM responses

---

## Performance Considerations

### Scalability

**Current Limits:**
- Max 5 personas per conversation
- Max 20 turns per conversation
- 1 second delay between turns (natural pacing)

**Bottlenecks:**
- LLM latency (2-5s per generation)
- Discord webhook rate limits (30/min)
- JSONL file I/O (append-only, fast)

### Optimizations

1. **Webhook Pooling:** Reuse webhooks across conversations (LRU eviction)
2. **Async Everything:** Non-blocking message generation and sending
3. **Batch Metrics:** Calculate metrics after conversation (not per-turn)
4. **RAG Indexing:** Background task, doesn't block conversation flow

### Memory Usage

- Active conversation state: ~10KB per conversation
- Persisted conversations: ~50KB per 10-turn conversation (JSONL)
- Webhook pool: 10 webhooks * ~1KB = 10KB per guild

---

## Configuration Reference

### Environment Variables

```env
# Core Settings
BOT_CONVERSATION_ENABLED=true
BOT_CONVERSATION_MAX_TURNS=10
BOT_CONVERSATION_TURN_TIMEOUT=60

# Metrics
BOT_CONVERSATION_DETAILED_METRICS=false
BOT_CONVERSATION_AUTO_APPROVE_THRESHOLD=0.7

# Archival
BOT_CONVERSATION_REVIEW_WINDOW_HOURS=24
BOT_CONVERSATION_RETENTION_DAYS=30
```

### ConversationConfig Object

```python
@dataclass
class ConversationConfig:
    max_turns: int = 10              # Maximum conversation turns
    turn_timeout_seconds: int = 60   # Timeout per turn
    enable_tools: bool = False       # Allow tool usage (future)
    enable_metrics: bool = True      # Calculate quality metrics
    seed: Optional[int] = None       # Random seed for reproducibility
```

---

## Security Considerations

### Rate Limiting

- Discord webhook limits enforced by `WebhookPool`
- LLM rate limits handled by provider-specific services

### Content Filtering

- No built-in profanity filter (assumes trusted personas)
- Future: Add content moderation hooks via `on_message_generated` callback

### Access Control

- Only admins can start conversations (Discord permission checks)
- Review workflow requires admin approval for archival

---

## Future Enhancements

### Planned Features

1. **Tool Integration:** MCP/n8n tool usage during conversations
2. **Multi-Channel:** Conversations spanning multiple channels
3. **Voice Support:** TTS/STT for audio conversations
4. **Real-Time Intervention:** Humans can join mid-conversation
5. **Scheduled Conversations:** Cron-like scheduling
6. **Conversation Templates:** Predefined topics and turn strategies

### Research Opportunities

- **Emergent Behavior:** Study how personas develop relationships
- **Debate Dynamics:** Analyze argumentation patterns
- **Character Consistency:** Measure personality stability over time
- **Topic Drift:** Track how conversations evolve from initial topic

---

## Related Documentation

- [User Guide](BOT_CONVERSATIONS.md) - Usage and troubleshooting
- [Persona System](../README.md#multi-persona-system) - Character definitions
- [Service Factory](../services/core/factory.py) - Dependency injection
- [Testing Guide](../tests/README.md) - Running tests

---

## Appendix: State Schema

### ConversationState

```python
@dataclass
class ConversationState:
    conversation_id: str                    # Unique ID
    participants: List[str]                 # Persona IDs
    status: ConversationStatus              # ACTIVE, COMPLETED, FAILED
    turn_count: int = 0                     # Current turn number
    max_turns: int = 10                     # Max allowed turns
    messages: List[Message] = []            # Conversation history
    current_speaker: Optional[str] = None   # Active speaker
    topic: str = ""                         # Conversation topic
    started_at: Optional[datetime] = None   # Start timestamp
    ended_at: Optional[datetime] = None     # End timestamp
    termination_reason: Optional[str] = None # Why conversation ended
    metrics: ConversationMetrics = ...      # Quality metrics
    metadata: Dict[str, Any] = {}           # Extensible metadata
```

### Message

```python
@dataclass
class Message:
    speaker: str                    # Persona ID
    content: str                    # Message text
    timestamp: datetime             # When message was sent
    turn_number: int                # Turn number (1-indexed)
    metadata: Dict[str, Any] = {}   # Latency, tool calls, etc.
```

### ConversationMetrics

```python
@dataclass
class ConversationMetrics:
    character_consistency: float = 0.0  # 0.0-1.0
    turn_relevance: float = 0.0         # 0.0-1.0
    avg_latency: float = 0.0            # Seconds
    vocab_diversity: float = 0.0        # 0.0-1.0
    quality_score: float = 0.0          # 0.0-1.0 (weighted average)
```

---

**Last Updated:** 2026-01-29  
**Version:** 1.0
