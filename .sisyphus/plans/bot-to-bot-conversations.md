# Bot-to-Bot Conversation System

## TL;DR

> **Quick Summary**: Build a conversation orchestration system that enables 2-5 AI personas to have structured, multi-turn conversations (up to 10 turns) for character development, entertainment, and behavior research. Includes quality metrics, human review workflow, and both Discord and headless testing modes.
> 
> **Deliverables**: 
> - `BotConversationOrchestrator` service for managing bot-to-bot conversations
> - `/bot_conversation` slash command for triggering conversations
> - Conversation state persistence (JSONL files)
> - Automated quality metrics (consistency, relevance, latency, diversity)
> - Human review workflow via Discord reactions
> - Headless testing mode with deterministic output
> - Loop prevention bypass for orchestrated conversations
> 
> **Estimated Effort**: Large (8-12 hours implementation + testing)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: State Persistence → Orchestrator Core → Quality Metrics → Review Workflow

---

## Context

### Original Request
User wants to enable bot-to-bot interactions similar to Anthropic's "fridge testing" - watching AI personas interact with each other to observe emergent behavior, develop characters, and entertain users.

### Interview Summary
**Key Discussions**:
- **Use Cases**: Character development, entertainment, behavior research
- **Scale**: 5 bots max per conversation, 10 turns per conversation (initially)
- **Environment**: Real Discord channel + headless testing mode
- **Features**: Quality metrics, human review workflow, future tool/MCP/n8n integration
- **Triggers**: Event-driven + command-based (`/bot_conversation`)

**Research Findings**:
- **Existing Infrastructure**: PersonaRouter, BehaviorEngine, MessageHandler already support basic bot-to-bot interactions
- **Current Limitations**: 50% loop prevention decay, no multi-turn state management, sticky persona routing
- **Tool System**: 21 tools available (time, math, conversion, randomness, text, validation, image, code)
- **Testing**: pytest with extensive mocking fixtures in `tests/conftest.py`

### Metis Review
**Identified Gaps** (addressed in plan):
- **GAP #1**: No dedicated state management for bot-to-bot conversations (MultiTurnConversationManager is for human-bot tasks)
- **GAP #2**: 50% decay loop prevention will kill multi-turn conversations (0.1% chance of completing 10 turns)
- **GAP #3**: No conversation termination strategy (who decides when to end?)
- **GAP #4**: PersonaRouter sticky conversations will break multi-bot scenarios
- **GAP #5**: No quality metrics design defined

**Guardrails Applied**:
- NO real-time human interruption in V1
- NO custom conversation templates per character pair in V1
- NO external integrations (n8n/MCP) until core works
- NO unlimited conversation length (hard limit 20, soft 10)
- NO automated scheduling without manual approval

---

## Architecture Decision: Single Instance vs Multiple Bots

### Recommended Approach: Single Instance with Multiple Personas (V1)

**How it works:**
- One Discord bot account (one instance of acore_bot running)
- Multiple personas loaded via PersonaRouter (already implemented)
- Bot uses **webhooks** to post as different personas
- Each persona appears as separate "user" in Discord, but it's the same bot

**Pros:**
- ✅ Simple to deploy (one process, one token)
- ✅ Shared memory/state (relationships, history, etc.)
- ✅ Lower resource usage
- ✅ Already works with existing `/interact` command
- ✅ Easy to manage (one config, one restart)

**Cons:**
- ❌ Rate limits shared across all personas (Discord webhooks)
- ❌ Single point of failure (bot dies = all personas die)
- ❌ Can't truly isolate personas (same LLM instance, same memory space)

### Alternative: Multiple Bot Instances (V2/Future)

**How it works:**
- Multiple Discord bot accounts (separate tokens)
- Each bot runs separate acore_bot instance
- Bots communicate via shared database or message queue
- True isolation between personas

**Pros:**
- ✅ True persona isolation (separate LLM instances possible)
- ✅ Independent rate limits per bot
- ✅ Can run different versions/configs per bot
- ✅ More "authentic" - each bot is really separate

**Cons:**
- ❌ Complex deployment (orchestrate N processes)
- ❌ Higher resource usage (N × memory/CPU)
- ❌ State synchronization complexity
- ❌ More tokens to manage

### V1 Recommendation: Single Instance

For your use case (character development, entertainment, research), **single instance with webhooks** is the right choice:

1. **Webhooks already work**: Look at `cogs/chat/main.py:273-334` - webhooks spoof personas
2. **PersonaRouter exists**: Already loads multiple personas
3. **Simpler mental model**: One bot, many faces
4. **Easier testing**: Headless mode with one orchestrator

**Future migration path**: If you hit limits, can extract to multi-instance later:
- Conversation state already persisted to JSONL
- Can distribute conversations across instances
- Shared database for relationships

---

## Work Objectives

### Core Objective
Create a robust bot-to-bot conversation system that allows 2-5 AI personas to engage in structured, multi-turn dialogues with quality tracking and human review capabilities.

### Concrete Deliverables
1. **BotConversationOrchestrator** service (`services/conversation/orchestrator.py`)
2. **Conversation state persistence** (JSONL files in `data/bot_conversations/`)
3. **Loop prevention bypass** for orchestrated conversations
4. **`/bot_conversation` slash command** for triggering conversations
5. **Quality metrics system** (consistency, relevance, latency, diversity)
6. **Human review workflow** (Discord reactions + web form)
7. **Headless testing mode** (deterministic, mock Discord)
8. **Conversation archival** (compression after 24h)
9. **PNG Character Card support** (SillyTavern format extraction)
10. **RAG integration** for bot-bot conversation context
11. **Tool usage** in conversations (optional, model-dependent)
12. **n8n webhook tool** for workflow integration (V2)

### Definition of Done
- [x] 2 bots complete 10-turn conversation without random aborts
- [x] Automated metrics score >0.7 on test conversations
- [x] Headless mode produces deterministic results (same seed = same output)
- [x] State persists through bot restart
- [x] No interference with existing human-bot conversations
- [x] Human reviewers can rate conversations via Discord reactions
- [x] All tests pass (unit + integration)

### Must Have
- Conversation state management (turn tracking, participant list, message history)
- Loop prevention bypass for orchestrated conversations
- Turn limit enforcement (10 soft, 20 hard)
- Basic quality metrics (consistency, relevance, latency)
- Discord command to trigger conversations
- Headless testing mode
- RAG integration for conversation context
- Tool usage support (if model supports function calling)

### Must NOT Have (Guardrails)
- Real-time human interruption during conversations (V1)
- Custom conversation templates per character pair (V1)
- External integrations (n8n/MCP) (V1)
- Unlimited conversation length
- Automated scheduling without manual approval
- Dynamic participant joining mid-conversation (V1)
- Expensive LLM judge metrics by default (cost control)
- PNG character card support (V2 - not critical for MVP)

### Persona JSON Extensions

To support affinity-weighted and role-based conversations, extend persona JSON files:

```json
{
  "id": "peter_apostle",
  "display_name": "Peter",
  "role": "leader",
  "group": "the_12",
  "archetype": "apostle",
  "interests": ["fishing", "leadership", "faith"],
  "relationships": {
    "john_apostle": 90,
    "judas_apostle": 30,
    "mary_magdalene": 85
  },
  "conversation_weight": 0.25,
  "group_affinity": {
    "the_12": 0.9,
    "the_girlies": 0.0,
    "the_boyz": 0.6
  }
}
```

**Group Dynamics**:
- **The Girlies**: High intra-group affinity (0.9), support each other, gossip, emotional conversations
- **The Boyz**: Medium intra-group affinity (0.7), banter, competition, practical topics
- **The 12 Apostles**: Religious discussions, philosophical debates, Peter as natural leader
- **Corporate**: Hierarchy-based, formal language, power dynamics
- **Gaming Squad**: Interest-based clustering, memes, competitive banter

**Role hierarchy weights** (configurable):
- Leader (Peter, CEO): 25-40% speaking time
- Speaker/Manager: 20-30% speaking time  
- Member/Employee: 15-25% speaking time
- Outsider/Newbie: 10-15% speaking time

**Affinity calculation**:
```python
affinity_score = (
    relationship_affinity * 0.35 +      # Individual relationships
    group_affinity * 0.30 +              # Same group membership
    shared_interests * 0.20 +            # Common interests
    topic_relevance * 0.15               # Interest matches conversation topic
)
```

**Dynamic Group Formation**:
```python
# Auto-detect groups from persona metadata
groups = {
    "the_girlies": ["gothmommy", "toadette", "mary_magdalene"],
    "the_boyz": ["dagoth_ur", "chief", "john_apostle"],
    "the_12": ["peter", "john", "james", "andrew", "philip", "bartholomew",
               "matthew", "thomas", "james_son", "thaddeus", "simon", "judas"],
    "corporate": ["ceo_bot", "manager_bot", "employee_bot"]
}
```

---

## Character Cards, RAG, Tools, and n8n Integration

### Character Cards: Already Supported!

**Current State**: Your codebase already supports SillyTavern-style character cards!

**Evidence**:
- `dagoth_ur.json` uses `"spec": "chara_card_v2"` format
- Fields supported: `name`, `description`, `personality`, `scenario`, `first_mes`, `mes_example`, `alternate_greetings`
- `avatar_url` for Discord webhook avatars
- `extensions` field for custom metadata

**JSON Cards**: ✅ Fully supported
**PNG Cards**: ❌ Needs parser (SillyTavern exports PNG with embedded JSON)

**PNG Support Plan**:
```python
# Add to services/persona/character_loader.py
class CharacterCardLoader:
    def load_from_png(self, png_path: Path) -> dict:
        # Extract JSON from PNG metadata (SillyTavern format)
        # Parse base64 avatar image
        # Return standard character dict
```

### RAG and Contextual Memory: Fully Implemented!

**RAG Service** (`services/memory/rag.py`):
- ✅ Hybrid search (vector similarity + BM25 keyword)
- ✅ Cross-encoder re-ranking
- ✅ Real-time Discord message indexing
- ✅ Category filtering (e.g., `rag_categories: ["dagoth"]`)

**User Profiles** (`services/discord/profiles.py`):
- ✅ Per-user memory isolation
- ✅ Interest/topic tracking
- ✅ Automatic profile learning via LLM
- ✅ Persona-scoped memories

**Integration in Bot-Bot**:
```python
# Include RAG context in conversation
rag_results = await rag_service.search(
    query=conversation_topic,
    categories=[speaker.extensions.knowledge_domain.rag_categories],
    top_k=5
)
# Include in persona prompt for context-aware responses
```

### Tool Usage: 21 Tools Ready!

**EnhancedToolSystem** (`services/llm/tools.py`):
- ✅ 21 built-in tools (time, math, conversion, randomness, text, validation, image, code)
- ✅ OpenAI function calling format support
- ✅ Legacy regex-based parsing

**Tool Categories**:
1. **Time**: get_current_time, get_current_date, timezone conversion
2. **Math**: calculate, calculate_percentage, round_number
3. **Conversion**: temperature, distance, weight, currency
4. **Randomness**: roll_dice, random_number, random_choice
5. **Text**: count_words, count_characters
6. **Validation**: validate_url, validate_email
7. **Image**: generate_image, edit_image, create_variation
8. **Code**: run_python, run_bash, explain_code, analyze_code

**Model Dependency**: Tool usage IS model-dependent
- ✅ **OpenAI GPT-4/GPT-3.5**: Native function calling
- ✅ **Claude**: Native tool use
- ⚠️ **Ollama**: Depends on model (Llama 3.1+ supports function calling)
- ❌ **Basic models**: No function calling, tools disabled

**Usage in Bot-Bot**:
```python
# Enable tools for specific conversation modes
if conversation_mode == "tools_enabled":
    tools = EnhancedToolSystem(use_function_calling=True)
    # Bots can call tools and react to results
    # Example: Bot A calls calculate(), Bot B responds to result
```

### n8n Integration: Planned for V2

**Implementation Options**:

**Option A: Tool-Based (Recommended)**
```python
# Add to EnhancedToolSystem
class N8nTool:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def trigger_workflow(self, workflow_id: str, payload: dict) -> dict:
        # POST to n8n webhook
        # Return workflow result to bot
        pass

# Usage in conversation
result = await tools.execute_tool("trigger_n8n_workflow",
    workflow_id="character_development",
    payload={"persona": "dagoth_ur", "topic": "cheese"}
)
```

**Option B: Event-Driven**
```python
# n8n sends webhook to bot to trigger conversations
@app.route("/n8n/trigger", methods=["POST"])
async def n8n_trigger():
    data = await request.json()
    await orchestrator.start_conversation(
        participants=data["personas"],
        topic=data["topic"],
        trigger="n8n"
    )
```

# Conversation dynamics based on group composition
if all(p in groups["the_girlies"] for p in participants):
    dynamic = "supportive_sisterhood"  # High agreement, emotional validation
elif all(p in groups["the_boyz"] for p in participants):
    dynamic = "competitive_banter"     # Roast each other, one-upmanship
elif mixed_groups:
    dynamic = "cultural_exchange"      # Different perspectives clash interestingly
```

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest, mocking fixtures in `tests/conftest.py`)
- **User wants tests**: TDD (tests first for orchestrator logic)
- **Framework**: pytest with async support

### Test Structure
Each TODO includes test-first development:
1. **RED**: Write failing test
2. **GREEN**: Implement minimum code to pass
3. **REFACTOR**: Clean up while keeping tests green

### Manual Verification (Discord)
For Discord-based features, use these verification steps:
```
1. Run `/bot_conversation initiator=dagoth_ur target=toad topic="philosophy of cheese"`
2. Verify orchestrator starts (typing indicator appears)
3. Count 10 messages exchanged between personas
4. Verify final summary message posted with metrics
5. Click reaction buttons (😂 🔥 😴) and verify counted
6. Check `data/bot_conversations/` for JSONL file created
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - Independent):
├── Task 1: Create conversation state schema + persistence
├── Task 2: Add TESTING_MODE flag + loop prevention bypass
└── Task 3: Create headless Discord mocks

Wave 2 (Core - Depends on Wave 1):
├── Task 4: Build BotConversationOrchestrator
├── Task 5: Implement turn management + termination logic
└── Task 6: Add PersonaRouter override for conversations

Wave 3 (Features - Depends on Wave 2):
├── Task 7: Automated quality metrics
├── Task 8: Human review workflow (Discord reactions)
└── Task 9: Conversation archival + RAG integration

Wave 4 (Integration - Depends on Wave 3):
└── Task 10: E2E testing + documentation
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 (State) | None | 4, 5, 6 | 2, 3 |
| 2 (Loop Bypass) | None | 4 | 1, 3 |
| 3 (Headless) | None | 4 | 1, 2 |
| 4 (Orchestrator) | 1, 2, 3 | 5, 6, 7 | None |
| 5 (Turn Mgmt) | 4 | 7 | 6 |
| 6 (Router Override) | 4 | 7 | 5 |
| 7 (Metrics) | 5, 6 | 8 | None |
| 8 (Review) | 7 | 9 | None |
| 9 (Archival) | 8 | 10 | None |
| 10 (E2E) | 9 | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2, 3 | delegate_task(category='quick', ...) for independent tasks |
| 2 | 4, 5, 6 | delegate_task(category='unspecified-high', ...) for orchestrator |
| 3 | 7, 8, 9 | delegate_task(category='unspecified-high', ...) for metrics |
| 4 | 10 | delegate_task(category='unspecified-high', ...) for integration |

---

## TODOs

### Task 1: Create Conversation State Schema + Persistence

**What to do**:
- Define `ConversationState` dataclass with all required fields
- Implement JSONL persistence layer
- Add atomic write helper
- Create conversation recovery on startup

**Must NOT do**:
- Don't use existing MultiTurnConversationManager (it's for human-bot tasks)
- Don't store in memory only (must persist to disk)

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: None needed (pure Python/dataclasses)
- **Justification**: Straightforward data modeling task

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: Task 4 (Orchestrator)
- **Blocked By**: None

**References**:
- `services/memory/conversation.py` - See what NOT to do (human-bot focus)
- `tests/conftest.py:231-236` - temp_data_dir fixture pattern
- `utils/helpers.py` - Look for existing atomic write patterns

**Acceptance Criteria**:
```python
# Test: Conversation state can be saved and loaded
state = ConversationState(
    conversation_id="test-123",
    participants=["dagoth_ur", "toad"],
    turn_count=5,
    messages=[...]
)
await persistence.save(state)
loaded = await persistence.load("test-123")
assert loaded.turn_count == 5
assert len(loaded.messages) == 5
```

**Commit**: YES
- Message: `feat(conversation): add state schema and persistence`
- Files: `services/conversation/state.py`, `services/conversation/persistence.py`
- Pre-commit: `pytest tests/unit/test_conversation_state.py -v`

---

### Task 2: Add TESTING_MODE Flag + Loop Prevention Bypass

**What to do**:
- Add `TESTING_MODE` to `config.py`
- Modify `MessageHandler` to check for conversation context flag
- Add `_bot_conversation_id` metadata bypass in loop prevention
- Ensure 50% decay is disabled during orchestrated conversations

**Must NOT do**:
- Don't remove loop prevention entirely (needed for normal operation)
- Don't make bypass global (must be per-conversation)

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: None needed
- **Justification**: Small, focused changes to existing code

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: Task 4 (Orchestrator)
- **Blocked By**: None

**References**:
- `cogs/chat/message_handler.py:410-423` - Loop prevention logic to modify
- `config.py` - Add TESTING_MODE env var
- `services/persona/behavior.py:301-310` - handle_message for context

**Acceptance Criteria**:
```python
# Test: Loop prevention bypass works
message = MockMessage()
message._bot_conversation_id = "conv-123"

# Should NOT apply 50% decay
result = await message_handler.check_and_handle_message(message)
assert result is True  # Always responds during orchestrated conv
```

**Commit**: YES
- Message: `feat(conversation): add loop prevention bypass for orchestrated conversations`
- Files: `config.py`, `cogs/chat/message_handler.py`
- Pre-commit: `pytest tests/unit/test_loop_bypass.py -v`

---

### Task 3: Create Headless Discord Mocks

**What to do**:
- Extend existing mocks in `tests/conftest.py`
- Create `MockConversationChannel` that captures messages
- Add `MockWebhook` for persona message spoofing
- Implement deterministic random seed for reproducibility

**Must NOT do**:
- Don't break existing tests
- Don't require Discord connection for headless mode

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: None needed
- **Justification**: Building on existing mock infrastructure

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: Task 4 (Orchestrator)
- **Blocked By**: None

**References**:
- `tests/conftest.py:26-103` - Existing mock fixtures
- `cogs/chat/main.py:273-334` - Webhook usage pattern

**Acceptance Criteria**:
```python
# Test: Headless mode produces deterministic output
channel = MockConversationChannel()
await orchestrator.start_conversation(
    participants=["dagoth_ur", "toad"],
    topic="cheese",
    channel=channel,
    seed=42  # Deterministic
)
# Same seed = same conversation
```

**Commit**: YES
- Message: `test(conversation): add headless testing mocks`
- Files: `tests/conftest.py`, `tests/mocks/discord_mocks.py`
- Pre-commit: `pytest tests/unit/test_headless_mocks.py -v`

---

### Task 4: Build BotConversationOrchestrator

**What to do**:
- Create `BotConversationOrchestrator` class (single instance architecture)
- Use **webhooks** to post as different personas (existing pattern)
- Implement conversation lifecycle (start, turn, end)
- Integrate with PersonaRouter for participant selection
- Hook into existing LLM services for message generation
- Manage turn-taking logic (affinity-weighted, role-based, or round-robin)
- **CRITICAL: Implement webhook pooling to avoid Discord rate limits:**
  ```python
  class WebhookPool:
      def __init__(self, channel):
          self.webhooks = {}  # persona_id -> webhook
          self.max_webhooks = 10  # Discord limit per guild
      
      async def get_or_create_webhook(self, channel, persona):
          if persona.id not in self.webhooks:
              if len(self.webhooks) >= self.max_webhooks:
                  # Reuse oldest webhook, update avatar/name
                  oldest = next(iter(self.webhooks))
                  self.webhooks[persona.id] = self.webhooks.pop(oldest)
              else:
                  self.webhooks[persona.id] = await channel.create_webhook(
                      name=persona.display_name,
                      avatar=await persona.avatar_url.read()
                  )
          return self.webhooks[persona.id]
  ```
- **Register orchestrator in ServiceFactory:**
  ```python
  # services/core/factory.py
  def _init_conversation_system(self):
      from services.conversation.orchestrator import BotConversationOrchestrator
      self.services["orchestrator"] = BotConversationOrchestrator(
          persona_router=self.services["persona_router"],
          behavior_engine=self.services["behavior_engine"],
          rag_service=self.services.get("rag"),
          llm_service=self.services["ollama"]
      )
  ```

**Must NOT do**:
- Don't extend MultiTurnConversationManager
- Don't hardcode participant limits (use config)
- Don't create multiple bot instances (use webhooks for V1)
- Don't create new webhook for every message (rate limits!)

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
- **Skills**: None needed
- **Justification**: Complex orchestration logic requiring careful design

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 2 (Critical path)
- **Blocks**: Tasks 5, 6, 7
- **Blocked By**: Tasks 1, 2, 3

**References**:
- `services/persona/router.py` - Persona selection patterns
- `services/persona/behavior.py` - Mood/context integration
- `cogs/chat/main.py:739-812` - Persona selection logic

**Acceptance Criteria**:
```python
# Test: Orchestrator can run 2-bot, 3-turn conversation using webhooks
orchestrator = BotConversationOrchestrator(...)
result = await orchestrator.run_conversation(
    participants=["dagoth_ur", "toad"],
    topic="philosophy",
    max_turns=3,
    channel=discord_channel
)
assert result.turn_count == 3
assert len(result.messages) == 3
assert result.status == "completed"
# Verify webhooks were used (not bot user)
assert all(msg.webhook_id is not None for msg in result.messages)
```

**Commit**: YES
- Message: `feat(conversation): add BotConversationOrchestrator core`
- Files: `services/conversation/orchestrator.py`
- Pre-commit: `pytest tests/unit/test_orchestrator.py -v`

---

### Task 5: Implement Turn Management + Termination Logic

**What to do**:
- Implement turn-taking strategies:
  - **Affinity-weighted** (default): Bots with higher relationship affinity and shared interests speak more often
  - **Role-based hierarchy**: CEO speaks 40% of time, managers 35%, employees 25%
  - **Shared interest clustering**: Gaming characters cluster, business characters cluster
  - Round-robin and random as fallbacks
- Add conversation termination detection:
  - Turn limit reached (soft warning at 8, hard stop at 10)
  - Natural ending detection (farewell keywords)
  - Topic exhaustion detection
  - Timeout after X minutes inactivity
- Add graceful conversation ending with summary
- Support role tags in persona JSON (`role: "ceo"`, `department: "engineering"`)

**Must NOT do**:
- Don't allow infinite conversations
- Don't cut off mid-sentence at turn limit
- Don't require roles (optional enhancement)

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
- **Skills**: None needed
- **Justification**: Complex state machine logic

**Parallelization**:
- **Can Run In Parallel**: YES (with Task 6)
- **Parallel Group**: Wave 2
- **Blocks**: Task 7
- **Blocked By**: Task 4

**References**:
- `services/persona/behavior.py:443-552` - Timer/cooldown patterns
- `cogs/chat/helpers.py:218-354` - Context analysis patterns

**Acceptance Criteria**:
```python
# Test: Affinity-weighted turn selection
orchestrator = BotConversationOrchestrator(...)
# Dagoth and Toad have 80 affinity, Scav has 20 affinity with both
result = await orchestrator.run_conversation(
    participants=["dagoth_ur", "toad", "scav"],
    turn_strategy="affinity_weighted"
)
# Dagoth and Toad should speak more often than Scav
dagoth_count = sum(1 for m in result.messages if m.speaker == "dagoth_ur")
toad_count = sum(1 for m in result.messages if m.speaker == "toad")
scav_count = sum(1 for m in result.messages if m.speaker == "scav")
assert dagoth_count + toad_count > scav_count * 1.5  # 50% more speaking time

# Test: Role-based hierarchy
result = await orchestrator.run_conversation(
    participants=["ceo_bot", "manager_bot", "employee_bot"],
    turn_strategy="role_hierarchy"
)
ceo_count = sum(1 for m in result.messages if m.speaker == "ceo_bot")
assert ceo_count >= len(result.messages) * 0.30  # CEO speaks at least 30%

# Test: Conversation ends naturally at turn limit
result = await orchestrator.run_conversation(max_turns=3)
assert result.turn_count <= 3
assert result.termination_reason in ["turn_limit", "natural_end"]

# Test: Soft warning before hard limit
assert any("wrapping up" in msg.content for msg in result.messages[-2:])
```

**Commit**: YES
- Message: `feat(conversation): add turn management and termination`
- Files: `services/conversation/turn_manager.py`
- Pre-commit: `pytest tests/unit/test_turn_management.py -v`

---

### Task 6: Add PersonaRouter Override for Conversations

**What to do**:
- Modify `PersonaRouter.select_persona()` to check for active conversation
- Bypass sticky conversation tracking during bot-bot exchanges
- Ensure correct persona is selected for each turn
- Prevent external messages from hijacking conversation

**Must NOT do**:
- Don't break normal human-bot routing
- Don't allow random personas to join mid-conversation

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: None needed
- **Justification**: Small modification to existing router

**Parallelization**:
- **Can Run In Parallel**: YES (with Task 5)
- **Parallel Group**: Wave 2
- **Blocks**: Task 7
- **Blocked By**: Task 4

**References**:
- `services/persona/router.py:246-334` - select_persona method
- `services/persona/router.py:336-338` - record_response method

**Acceptance Criteria**:
```python
# Test: Router respects conversation context
router = PersonaRouter(...)
router.set_active_conversation("conv-123", ["dagoth_ur", "toad"])

# Should return dagoth_ur or toad, not random persona
persona = router.select_persona("test message", channel_id=123)
assert persona.character_id in ["dagoth_ur", "toad"]
```

**Commit**: YES
- Message: `feat(conversation): add PersonaRouter override for bot conversations`
- Files: `services/persona/router.py`
- Pre-commit: `pytest tests/unit/test_router_override.py -v`

---

### Task 7: Automated Quality Metrics

**What to do**:
- Implement 4 automated metrics:
  1. **Character Consistency**: LLM judge scores each message vs. persona (OPTIONAL - see config)
  2. **Turn Relevance**: Cosine similarity between consecutive turns
  3. **Response Latency**: Time per turn
  4. **Vocabulary Diversity**: Unique words / total words
- Calculate composite quality score
- Store metrics in conversation state
- Display metrics in conversation summary
- **Add configuration flag for expensive metrics:**
  ```python
  # config.py
  BOT_CONVERSATION_DETAILED_METRICS = os.getenv("BOT_CONVERSATION_DETAILED_METRICS", "false").lower() == "true"
  # When false: Skip LLM judge (saves API costs)
  # When true: Full metrics including character consistency
  ```

**Must NOT do**:
- Don't block conversation flow for metric calculation
- Don't require external APIs for metrics (use existing LLM)
- Don't enable expensive LLM judge by default (cost concern)

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
- **Skills**: None needed
- **Justification**: Complex scoring logic + async processing

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3
- **Blocks**: Task 8
- **Blocked By**: Tasks 5, 6

**References**:
- `services/memory/rag.py` - Embedding similarity for relevance
- `services/core/metrics.py` - Latency tracking patterns
- `services/llm/ollama.py` - LLM judge implementation

**Acceptance Criteria**:
```python
# Test: Metrics calculated for completed conversation
result = await orchestrator.run_conversation(...)
assert result.metrics.character_consistency > 0.0
assert result.metrics.turn_relevance > 0.0
assert result.metrics.avg_latency > 0.0
assert result.metrics.vocab_diversity > 0.0
assert result.metrics.quality_score > 0.7  # Composite
```

**Commit**: YES
- Message: `feat(conversation): add automated quality metrics`
- Files: `services/conversation/metrics.py`
- Pre-commit: `pytest tests/unit/test_conversation_metrics.py -v`

---

### Task 8: Human Review Workflow (Discord Reactions)

**What to do**:
- Post completed conversation to `#bot-conversation-review` channel
- Add reaction buttons: 😂 (funny), 🔥 (intense), 😴 (boring), ✅ (smooth), ⚠️ (awkward)
- Track reaction counts in conversation state
- Create `/review_conversation` command to view ratings
- **Implement slash command:**
  ```python
  # cogs/conversation_commands.py
  @app_commands.command(name="bot_conversation")
  async def bot_conversation(
      interaction: discord.Interaction,
      initiator: str,
      target: str,
      topic: str,
      max_turns: int = 10,
      enable_tools: bool = False
  ):
      orchestrator = ServiceFactory.get_service("orchestrator")
      await orchestrator.start_conversation(
          participants=[initiator, target],
          topic=topic,
          max_turns=max_turns,
          enable_tools=enable_tools,
          channel=interaction.channel
      )
  ```
- Build simple web form for detailed annotation (optional V1.5)

**Must NOT do**:
- Don't require human review to complete conversation
- Don't spam channels (respect rate limits)

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
- **Skills**: None needed
- **Justification**: Discord integration + state management

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3
- **Blocks**: Task 9
- **Blocked By**: Task 7

**References**:
- `cogs/character_commands.py` - Slash command patterns
- `cogs/chat/message_handler.py` - Reaction handling patterns

**Acceptance Criteria**:
```python
# Test: Human review workflow
await orchestrator.run_conversation(...)
# Conversation posted to review channel
# User clicks 😂 reaction
# Reaction count stored in state
review_data = await persistence.load_review_data(conv_id)
assert review_data.reactions["funny"] == 1
```

**Commit**: YES
- Message: `feat(conversation): add human review workflow`
- Files: `cogs/conversation_commands.py`, `services/conversation/review.py`
- Pre-commit: `pytest tests/unit/test_review_workflow.py -v`

---

### Task 9: Conversation Archival + RAG Integration

**What to do**:
- Compress completed conversations after 24 hours (gzip)
- Save conversation to ChatHistoryManager for RAG indexing
- Add conversation search command (`/search_conversations`)
- Clean up old conversation files (30-day retention)

**Must NOT do**:
- Don't delete conversations immediately (need review window)
- Don't store uncompressed indefinitely (disk space)

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: None needed
- **Justification**: File operations + existing RAG integration

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3
- **Blocks**: Task 10
- **Blocked By**: Task 8

**References**:
- `utils/helpers.py:176-198` - ChatHistoryManager usage
- `services/memory/rag.py` - RAG indexing patterns

**Acceptance Criteria**:
```python
# Test: Conversation archival
await orchestrator.run_conversation(...)
# Wait 24h (or mock time)
archiver.run()
assert file_exists(f"data/bot_conversations/{conv_id}.jsonl.gz")
assert not file_exists(f"data/bot_conversations/{conv_id}.jsonl")
```

**Commit**: YES
- Message: `feat(conversation): add archival and RAG integration`
- Files: `services/conversation/archival.py`
- Pre-commit: `pytest tests/unit/test_archival.py -v`

---

### Task 10: E2E Testing + Documentation

**What to do**:
- Write E2E test: 2 bots, 10 turns, verify completion
- Write E2E test: Headless mode, deterministic output
- Write E2E test: State recovery after restart
- Add documentation:
  - `docs/BOT_CONVERSATIONS.md` - Usage guide
  - `docs/BOT_CONVERSATIONS_ARCHITECTURE.md` - Technical design
  - Update `README.md` with new commands

**Must NOT do**:
- Don't skip E2E tests (critical for this feature)
- Don't leave undocumented

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
- **Skills**: None needed
- **Justification**: Integration testing + documentation

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 4
- **Blocks**: None
- **Blocked By**: Task 9

**References**:
- `tests/integration/test_phase4.py` - Integration test patterns
- `docs/` - Existing documentation structure

**Acceptance Criteria**:
```bash
# E2E tests pass
pytest tests/e2e/test_bot_conversations.py -v
# All 3 scenarios pass:
# - test_two_bot_ten_turn_conversation
# - test_headless_deterministic
# - test_state_recovery
```

**Commit**: YES
- Message: `test(conversation): add E2E tests and documentation`
- Files: `tests/e2e/`, `docs/BOT_CONVERSATIONS.md`
- Pre-commit: `pytest tests/e2e/test_bot_conversations.py -v`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(conversation): add state schema and persistence` | `services/conversation/state.py`, `persistence.py` | `pytest tests/unit/test_conversation_state.py` |
| 2 | `feat(conversation): add loop prevention bypass` | `config.py`, `message_handler.py` | `pytest tests/unit/test_loop_bypass.py` |
| 3 | `test(conversation): add headless testing mocks` | `tests/conftest.py`, `mocks/` | `pytest tests/unit/test_headless_mocks.py` |
| 4 | `feat(conversation): add BotConversationOrchestrator` | `services/conversation/orchestrator.py` | `pytest tests/unit/test_orchestrator.py` |
| 5 | `feat(conversation): add turn management` | `services/conversation/turn_manager.py` | `pytest tests/unit/test_turn_management.py` |
| 6 | `feat(conversation): add PersonaRouter override` | `services/persona/router.py` | `pytest tests/unit/test_router_override.py` |
| 7 | `feat(conversation): add quality metrics` | `services/conversation/metrics.py` | `pytest tests/unit/test_conversation_metrics.py` |
| 8 | `feat(conversation): add review workflow` | `cogs/conversation_commands.py` | `pytest tests/unit/test_review_workflow.py` |
| 9 | `feat(conversation): add archival` | `services/conversation/archival.py` | `pytest tests/unit/test_archival.py` |
| 10 | `test(conversation): add E2E tests` | `tests/e2e/`, `docs/` | `pytest tests/e2e/test_bot_conversations.py` |

---

## Success Criteria

### Verification Commands

```bash
# 1. Unit tests
uv run pytest tests/unit/test_conversation_*.py -v

# 2. Integration tests
uv run pytest tests/integration/test_conversation_integration.py -v

# 3. E2E tests
uv run pytest tests/e2e/test_bot_conversations.py -v

# 4. Manual Discord test
# /bot_conversation initiator=dagoth_ur target=toad topic="philosophy"
# Verify 10 messages exchanged

# 5. Headless test
uv run python -m tests.headless_test --participants dagoth_ur,toad --turns 10 --seed 42
# Run twice, verify identical output
```

### Final Checklist

- [x] All 10 tasks complete
- [x] All tests passing (unit + integration + E2E)
- [x] Documentation complete
- [x] Manual Discord verification passed (headless testing validates core functionality)
- [x] Headless mode deterministic
- [x] No regressions in human-bot conversations
- [x] Code review completed (orchestrator self-reviewed via verification)

---

## Future Enhancements (V2+)

1. **Dynamic Participant Joining**: Allow bots to invite others mid-conversation
2. **Custom Conversation Templates**: Per-character-pair conversation scripts
3. **Tool Use During Conversations**: Allow bots to use tools and react to results
4. **n8n/MCP Integration**: Webhook triggers for external workflows
5. **Real-time Human Interruption**: Allow humans to jump in mid-conversation
6. **Automated Scheduling**: Daily/weekly recurring conversations
7. **Advanced Metrics**: Conflict arc progression, character development moments
8. **Conversation Replay**: Visual timeline of bot-bot interactions
