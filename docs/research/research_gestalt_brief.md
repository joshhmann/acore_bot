# Gestalt Architecture Research Brief
## Complete Research Pack — All 8 Prompts + Synthesis

**Date**: 2026-03-20
**Repo**: `joshhmann/acore_bot` (master)
**Author**: Research compiled against Gestalt shared context

---

# Prompt 1: Runtime Architecture

## Executive Summary

Gestalt's current architecture already embodies the right instinct: the runtime is the central authority, adapters are thin, and `GestaltRuntime` owns orchestration. The `ARCHITECTURE.md` and `runtime_bootstrap.py` composition root are correct structural decisions. What's missing is the hardening of these boundaries — the legacy `services/*` layer still has authority in Discord paths, the adapter contract isn't formally typed, and there's no explicit session lifecycle or trace emission system. The next phase should formalize what's already implied.

External systems confirm this direction. The strongest agent frameworks (OpenAI Agents SDK, Anthropic's MCP architecture, Kimi CLI) all converge on a pattern: a central orchestrator owns the loop, tools are registered capabilities, and surfaces are renderers. ElizaOS gets this partially right with its AgentRuntime but blurs boundaries with its plugin system. Project Airi's `server-runtime` package shows the right separation for embodied agents.

## Recommended Runtime Architecture Patterns

### Core Runtime Responsibilities (Already Correct — Formalize)

The runtime must own exactly these concerns, with no sharing:

1. **Session lifecycle**: Create, suspend, resume, destroy. Sessions carry conversation state, active persona, memory scope, and tool budget.
2. **Provider routing**: Model selection, fallback chains, cost/latency routing. No adapter should import a provider directly.
3. **Tool policy and execution**: Tool registry, budget enforcement, approval gates, execution sandboxing.
4. **Memory coordination**: Orchestrate reads/writes across short-term, episodic, semantic, and preference stores.
5. **Trace emission**: Structured event log for every runtime decision — model calls, tool invocations, memory reads, routing decisions.
6. **Command/action dispatch**: Normalize incoming events into runtime commands; dispatch to appropriate handlers.
7. **Persona/session state**: Active persona selection, persona switching, relationship state access.
8. **Context-cache lifecycle**: Prompt assembly, cache key management, invalidation.

### Runtime Lifecycle Model

```
INIT → READY → RUNNING → DRAINING → STOPPED
         ↑        ↓
         └─ SUSPENDED
```

- **INIT**: Load config, construct providers, memory stores, tool registry, persona catalog. This is `runtime_bootstrap.py`.
- **READY**: All subsystems initialized, no active sessions.
- **RUNNING**: Accepting and processing events from adapters.
- **DRAINING**: Stop accepting new events, finish in-flight, flush traces, close sessions.
- **STOPPED**: All resources released.

The runtime must own shutdown. No adapter should be able to keep the process alive after the runtime enters DRAINING.

### Module/Layer Breakdown

```
gestalt/
├── runtime.py              # GestaltRuntime — the god object (intentionally)
├── runtime_bootstrap.py    # Composition root (already exists)
├── session.py              # Session lifecycle, state container
├── router.py               # Command/event routing
├── schemas.py              # Normalized event/response types
├── trace.py                # Structured trace emitter
│
├── providers/
│   ├── registry.py         # Provider catalog, routing logic
│   ├── router.py           # Cost/latency/capability routing
│   └── adapters/           # Per-provider adapters (OpenRouter, Ollama, etc.)
│
├── tools/
│   ├── registry.py         # Tool catalog
│   ├── policy.py           # Budget, approval gates, risk tiers
│   ├── executor.py         # Sandboxed execution
│   └── mcp_bridge.py       # MCP server client
│
├── memory/
│   ├── coordinator.py      # Orchestrates memory subsystems
│   ├── short_term.py       # Recent turns, sliding window
│   ├── episodic.py         # Conversation summaries, events
│   ├── semantic.py         # Facts, RAG, vector search
│   └── preference.py       # User/persona preferences
│
├── persona/
│   ├── catalog.py          # Persona definitions, loading
│   ├── state.py            # Active persona, relationships
│   └── prompt.py           # Persona-aware prompt assembly
│
└── context/
    ├── assembler.py         # Prompt construction pipeline
    └── cache.py             # Cache key management, invalidation
```

## Anti-Patterns to Avoid

1. **Adapter-local intelligence**: If an adapter needs to make a "smart" decision (which persona to use, whether to respond, spam filtering), that logic must live in the runtime. The current `ThinkingService` pattern is correct in concept but should be runtime-owned, not a service.

2. **Service layer as second runtime**: The legacy `services/*` directory acts as an alternative authority. Services should be capabilities consumed by the runtime, not independent decision-makers with their own state.

3. **Event bus as architecture**: Event buses create invisible coupling. Prefer explicit function calls through typed interfaces. Events are fine for traces and monitoring, not for primary control flow.

4. **Multi-adapter state divergence**: If Discord and CLI can produce different behavior for the same input, you have a bug. The runtime must be the sole determinant of behavior.

5. **God-prompt assembly in adapters**: Adapters should never construct prompts. They provide facts; the runtime assembles context.

## What Belongs Where

| Concern | Runtime | Adapter | Web UI |
|---------|---------|---------|--------|
| Session state | ✓ owns | reads session ID | reads via API |
| Provider selection | ✓ owns | — | displays choice |
| Tool execution | ✓ owns | — | approval UI |
| Prompt assembly | ✓ owns | — | — |
| Message parsing | — | ✓ owns | — |
| Platform rendering | — | ✓ owns | — |
| Trace display | emits | — | ✓ renders |
| Memory inspection | exposes API | — | ✓ renders |
| Persona display | provides state | ✓ renders name/avatar | ✓ renders dashboard |

## Comparison of External Systems

### OpenAI Agents SDK
**Useful**: Agent loop abstraction, handoff mechanism, guardrails-as-parallel-checks, built-in tracing. The Runner concept (conductor) is a clean orchestrator pattern.
**Not useful**: Deeply tied to OpenAI's API shape. Handoffs are one-directional which limits complex routing.
**Borrow**: Guardrail parallel execution pattern, trace structure.

### Anthropic MCP
**Useful**: Clean client-server separation, tool-as-capability model, the new code-execution-over-MCP pattern for scaling tool count. The trust boundary model (tools are untrusted by default) is correct.
**Not useful**: MCP is a connector protocol, not a runtime architecture. Don't confuse the two.
**Borrow**: Tool capability description schema, trust tier model, the "load tools on demand via code execution" scaling pattern.

### Kimi CLI
**Useful**: Layered architecture (config, execution, tool, UI). Checkpoint/undo system for safe autonomous operation. Approval mechanism for dangerous operations. Auto-wired tool registration.
**Not useful**: CLI-specific patterns don't all translate to multi-surface.
**Borrow**: Checkpoint/rollback for tool execution, layered config, approval gates.

### ElizaOS
**Useful**: Character file as personality definition, plugin hot-swap at runtime, Worlds/Rooms context isolation.
**Not useful**: Web3 focus pollutes architecture decisions. Plugin system is too permissive — plugins can own too much state. Runtime refinement acknowledged as a known limitation in their own paper. The "Actions" and "Evaluators" pattern creates a second dispatch system alongside the runtime.
**Borrow**: Character file schema (Gestalt already has this), Worlds/Rooms context scoping idea.

### Project Airi
**Useful**: `server-runtime` as backend, `server-sdk` as client adapter pattern. xsAI as provider abstraction layer. Clean separation of rendering (stage-ui) from runtime.
**Not useful**: Browser-first design means many architectural decisions optimize for WebGPU/WASM constraints that don't apply to Gestalt's server-first model. The monorepo is sprawling and hard to reason about.
**Borrow**: Provider abstraction layer pattern, runtime/client SDK separation, the soul container concept (personality as middleware, not just prompt prefix).

## Implementation Recommendations (Prioritized)

1. **Formalize the adapter contract as a typed protocol**. Define `AdapterProtocol` with explicit methods: `start()`, `stop()`, `on_event(callback)`, `render(response)`. Adapters implement this. No exceptions.

2. **Kill `services/*` authority in maintained paths**. Move remaining service logic into runtime-owned subsystems. The `services/` directory becomes a quarantine zone with a deprecation timeline.

3. **Add session lifecycle to the runtime**. `Session` objects with create/suspend/resume/destroy and explicit state boundaries. Every adapter interaction goes through a session.

4. **Build the trace emitter**. Structured events for every runtime decision. This is your debugging backbone and future operator dashboard data source.

5. **Implement provider routing as a runtime subsystem**. Abstract the current OpenRouter/Ollama split into a provider registry with capability-based routing (model supports tools? model supports vision? cost tier?).

6. **Formalize tool policy**. Tool registry with risk tiers, budget per session, approval gates. This is prerequisite for any autonomy work.

7. **Move prompt assembly into runtime context pipeline**. No adapter should touch prompt construction. The runtime assembles context from session state, memory, persona, and tool definitions.

8. **Implement graceful shutdown**. Runtime owns the lifecycle: DRAINING stops new events, flushes in-flight, closes sessions, then signals adapters to stop.

9. **Add runtime health/readiness endpoints**. The web adapter exposes `/health` and `/ready` from runtime state, not from its own assessment.

10. **Document the boundary**. Write a one-page "what adapters must never do" contract and enforce it in code review.

---

# Prompt 2: Memory, Context, and Learning

## Executive Summary

Gestalt already has memory building blocks: user profiles, RAG, conversation summarization, lorebooks. The gap is a unified memory coordination layer that the runtime owns, a prompt assembly pipeline with cache awareness, and a user-adaptation model that learns from outcomes without magical claims. The current memory system is spread across services without a single coordinator, and prompt construction happens in multiple places.

## Recommended Memory Model

### Memory Tiers

**Tier 1: Working Memory (per-turn)**
- Recent turns in the current conversation (sliding window, typically 10-20 turns)
- Active tool results
- Current persona context
- Lifetime: single session, discarded on session close
- Storage: in-memory on the runtime

**Tier 2: Session Memory (per-conversation)**
- Conversation summary (progressive — summarize every N turns, summarize summaries)
- Key facts extracted during conversation
- Emotional/social state trajectory
- Lifetime: persists across turns within a session, archived on session close
- Storage: session store (SQLite/Postgres)

**Tier 3: Episodic Memory (cross-session)**
- Archived conversation summaries with timestamps
- Notable events (first interaction, milestones, conflicts resolved)
- Interaction patterns (when user is active, preferred topics, communication style)
- Lifetime: long-term, decays with configurable half-life
- Storage: structured database with vector embeddings for retrieval

**Tier 4: Semantic Memory (knowledge base)**
- User facts (name, preferences, stated interests)
- Lorebook/world info entries
- RAG corpus (documents, reference material)
- Persona-specific knowledge
- Lifetime: persistent, manually or automatically curated
- Storage: vector store (existing RAG infrastructure) + structured facts table

**Tier 5: Preference Memory (adaptation)**
- Communication style preferences (verbosity, formality, humor)
- Topic engagement patterns
- Response quality signals (user reactions, conversation continuations, explicit feedback)
- Lifetime: persistent, slowly updated
- Storage: key-value store with confidence scores and timestamps

### Memory Coordinator

```python
class MemoryCoordinator:
    """Runtime-owned memory orchestrator."""

    async def recall(self, session: Session, query: str, budget_tokens: int) -> MemoryContext:
        """Retrieve relevant memories within token budget."""
        # 1. Always include: working memory (recent turns)
        # 2. Retrieve: episodic memories ranked by relevance + recency
        # 3. Retrieve: semantic facts relevant to query
        # 4. Retrieve: lorebook entries matching topic
        # 5. Include: user preference profile
        # 6. Trim to budget, prioritizing by tier

    async def commit(self, session: Session, event: RuntimeEvent):
        """Write new memories from runtime events."""
        # Extract facts, update preferences, log episodic events

    async def summarize(self, session: Session):
        """Progressive summarization of session history."""

    async def invalidate(self, scope: str, reason: str):
        """Invalidate/revise memories with audit trail."""
```

## Recommended Prompt Assembly and Cache Model

### Prompt Assembly Pipeline

```
[Stable Prefix]          ← cacheable (persona definition, system instructions, tool definitions)
[Semi-Stable Block]      ← cacheable with longer TTL (user profile, preference summary)
[Dynamic Context]         ← NOT cached (retrieved memories, current session state)
[Recent Turns]            ← NOT cached (conversation history)
[Current Input]           ← NOT cached
```

### Cache Key Strategy

```python
cache_key = hash(
    persona_id,
    system_prompt_version,
    tool_definitions_hash,
    user_profile_hash,     # only for semi-stable block
)
```

**Anthropic prompt caching**: Use cache_control breakpoints at the boundary between stable prefix and dynamic content. The persona definition + system instructions + tool definitions should be the cached prefix. This is the biggest win — these change rarely and can be substantial.

**OpenAI prompt caching**: Automatic for repeated prefixes. Structure prompts so the stable prefix is literally identical across calls for the same persona.

### Invalidation Rules

- **User profile changes** → invalidate semi-stable cache block
- **Persona definition edit** → invalidate stable prefix for that persona
- **Tool registry change** → invalidate stable prefix for all personas
- **Memory revision** → invalidate affected episodic/semantic entries, re-rank on next retrieval
- **Session close** → flush working memory, archive session memory, trigger progressive summarization

## Recommended User-Adaptation Model

No magic. Track concrete signals, update preferences, expose to operator.

**Signals to track:**
- Response length vs user's typical message length (calibrate verbosity)
- Topic continuation vs topic change (what engages them)
- Explicit feedback (reactions, corrections, "that's not right")
- Time of day patterns
- Persona preference patterns (who do they address most)

**Adaptation outputs:**
- `preferred_verbosity`: float (0=terse, 1=verbose), updated via exponential moving average
- `topic_interests`: dict[str, float], updated by engagement signals
- `communication_style`: enum (formal, casual, playful), inferred from user's language
- `active_hours`: time ranges, inferred from interaction timestamps

**What this is NOT:**
- Not reinforcement learning
- Not fine-tuning
- Not a personality model
- It's a preference profile with bounded, interpretable updates

## Data Model Suggestions

```sql
-- Core facts table
CREATE TABLE user_facts (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,  -- 'name', 'preference', 'interest', 'stated_fact'
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    source TEXT NOT NULL,      -- 'explicit', 'inferred', 'corrected'
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, fact_type, key)
);

-- Episodic memory
CREATE TABLE episodes (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    topics TEXT[],
    emotional_valence FLOAT,  -- -1 to 1
    created_at TIMESTAMP,
    embedding VECTOR(1536)    -- for similarity retrieval
);

-- Preference profile
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    verbosity FLOAT DEFAULT 0.5,
    formality FLOAT DEFAULT 0.5,
    topic_interests JSONB DEFAULT '{}',
    active_hours JSONB DEFAULT '{}',
    updated_at TIMESTAMP
);
```

## Anti-Patterns and Failure Modes

1. **Unbounded memory injection**: Stuffing all available memories into context regardless of relevance. Always budget-constrain retrieval.
2. **Memory without invalidation**: Facts become stale. Every memory needs a confidence score and a mechanism to be revised or expired.
3. **Magical learning claims**: "The agent learns your preferences" sounds great until you realize it's just a prompt that says "you like X." Track concrete signals, update bounded parameters.
4. **Cross-persona memory contamination**: Persona A shouldn't know what user told Persona B unless explicitly designed. Memory scoping by persona is critical.
5. **Summary drift**: Progressive summarization loses signal over time. Keep original episodic entries alongside summaries for retrieval.
6. **Cache-busting through personalization**: If every prompt is unique per-user, caching is worthless. Keep the stable prefix truly stable.

## Implementation Recommendations (Prioritized)

1. **Build the MemoryCoordinator as a runtime subsystem**. Single entry point for all memory operations. Replaces the current scattered memory access patterns.

2. **Implement the prompt assembly pipeline with explicit cache boundaries**. Define the stable prefix / dynamic context boundary. Use Anthropic cache_control breakpoints.

3. **Add progressive summarization**. Summarize every 10-15 turns. Summarize summaries when session archives exceed threshold. This is your long-term memory backbone.

4. **Create the user_facts table**. Replace ad-hoc user profile JSON with structured, queryable facts with confidence scores and provenance.

5. **Implement token-budget-aware retrieval**. The recall function must respect a token budget. Rank by relevance × recency × confidence, then truncate.

6. **Add memory invalidation and revision**. When a user corrects a fact, update with source='corrected'. When facts conflict, surface to operator.

7. **Scope memory by persona**. Add persona_id to memory queries. Persona A's private observations stay private unless relationship context is requested.

8. **Build preference tracking**. Start with verbosity and topic interests. Use exponential moving average for smooth updates. Expose in operator dashboard.

9. **Add operator memory inspection**. Web UI endpoint to browse, edit, and delete memories per user. This is essential for debugging and trust.

10. **Defer advanced RAG optimizations**. The current vector search setup works. Optimize retrieval ranking after the coordination layer is solid.

---

# Prompt 3: Autonomy, Action, and Safe Execution

## Executive Summary

Autonomy in Gestalt means the runtime can initiate actions without being directly prompted — proactive engagement, scheduled tasks, multi-step tool chains, and monitoring. The current system has proactive engagement and ambient messaging, which is a form of autonomy. The gap is formal policy gating, approval flows, action logging, and recovery. Kimi CLI's checkpoint/undo pattern and OpenAI's guardrails-as-parallel-checks are the strongest patterns to borrow.

## Recommended Autonomy Model

### Autonomy Levels

```
Level 0: PASSIVE       — Only responds when addressed
Level 1: REACTIVE      — Responds to mentions, DMs, and configured triggers
Level 2: AMBIENT       — May initiate in configured channels based on activity patterns
Level 3: PROACTIVE     — May initiate tasks, check status, offer assistance
Level 4: AUTONOMOUS    — May execute multi-step tasks with approval gates at risk boundaries
```

The operator sets the maximum autonomy level per channel/context. The runtime never exceeds the configured level.

### Action Classification

Every action the runtime can take gets a risk tier:

| Tier | Examples | Policy |
|------|----------|--------|
| READ | Memory retrieval, search, status check | Always allowed |
| INFORM | Send a message, update a dashboard | Allowed at Level 1+ |
| MODIFY_SELF | Update memory, change persona state | Allowed at Level 2+, logged |
| MODIFY_EXTERNAL | Call external API, post to channel, file operation | Requires Level 3+, logged, may require approval |
| IRREVERSIBLE | Delete data, send to external service, financial action | Always requires approval |

### Execution Model

```python
class ActionExecutor:
    async def execute(self, action: Action, session: Session) -> ActionResult:
        # 1. Check policy: is this action allowed at current autonomy level?
        # 2. Check budget: has this session exceeded its action budget?
        # 3. If approval required: create approval request, suspend, return pending
        # 4. Create checkpoint (snapshot of relevant state before action)
        # 5. Execute action with timeout
        # 6. Log result to action log
        # 7. If failed: attempt recovery or rollback to checkpoint
        # 8. Return result
```

## Recommended Approval and Control Model

### Approval Flow

```
Action requested → Policy check → Approved? →
  YES → Execute → Log
  NEEDS_APPROVAL → Queue in approval store → Notify operator →
    Operator approves → Execute → Log
    Operator denies → Log denial → Inform persona
    Timeout → Auto-deny → Log → Inform persona
```

### Operator Controls

- **Kill switch**: Immediately drop to Level 0 (PASSIVE) for all contexts
- **Per-channel autonomy ceiling**: Set max level per Discord channel, CLI session, or web context
- **Action budget**: Max actions per session, per hour, per day
- **Approval queue**: Web UI showing pending actions with approve/deny buttons
- **Action log**: Complete audit trail with checkpoint references

## Recommended Action/Outcome Data Model

```sql
CREATE TABLE action_log (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    tool_name TEXT,
    parameters JSONB,
    checkpoint_id TEXT,          -- reference to pre-action state snapshot
    status TEXT NOT NULL,        -- 'pending', 'approved', 'executed', 'failed', 'denied', 'rolled_back'
    result JSONB,
    error TEXT,
    approved_by TEXT,            -- 'auto', 'operator', or operator user ID
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE checkpoints (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    state_snapshot JSONB,       -- relevant state before action
    created_at TIMESTAMP,
    rolled_back BOOLEAN DEFAULT FALSE
);

CREATE TABLE approval_queue (
    id SERIAL PRIMARY KEY,
    action_log_id INTEGER REFERENCES action_log(id),
    description TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    expires_at TIMESTAMP,
    status TEXT DEFAULT 'pending'
);
```

## Anti-Patterns to Avoid

1. **Unbounded retry loops**: Agent retries a failed tool call indefinitely. Always cap retries (3 max), with exponential backoff, and escalate to operator after max retries.
2. **Autonomy without audit**: Every autonomous action must be logged. No exceptions. If you can't explain what the agent did and why, you can't trust it.
3. **Approval fatigue**: If every action needs approval, operators will approve everything without reading. Reserve approval for genuinely risky actions. Auto-approve READ and INFORM tiers.
4. **Recovery by re-execution**: Don't retry failed actions with the same parameters. Analyze the failure, adjust, or escalate.
5. **Tool chain without budget**: A multi-step task should have a total action budget. If step 3 of 10 exhausts the budget, stop and report, don't continue.

## What Should Live Where

| Concern | Runtime | UI | Adapter |
|---------|---------|-----|---------|
| Policy evaluation | ✓ | — | — |
| Action execution | ✓ | — | — |
| Checkpoint management | ✓ | — | — |
| Approval queue storage | ✓ | — | — |
| Approval UI | — | ✓ | — |
| Kill switch | ✓ (enforces) | ✓ (triggers) | — |
| Action notifications | ✓ (emits) | ✓ (displays) | ✓ (delivers to platform) |

## Implementation Recommendations (Prioritized)

1. **Define action risk tiers and autonomy levels**. Start with the five tiers above. Assign every current tool and action to a tier.

2. **Implement the action logger**. Before adding any new autonomy, ensure every action is logged. This is non-negotiable infrastructure.

3. **Add action budgets per session**. Simple counter: max N actions of tier MODIFY_EXTERNAL or above per session.

4. **Build the approval queue**. Web UI shows pending actions. Operator can approve/deny. Timeout auto-denies. Start simple — a list endpoint and a webhook.

5. **Implement checkpoints for MODIFY_EXTERNAL+ actions**. Snapshot relevant state before execution. Enable rollback for failures.

6. **Add the kill switch**. Runtime method that drops all contexts to Level 0. Web UI button that triggers it. This is a safety requirement.

7. **Implement bounded retry with escalation**. Max 3 retries, exponential backoff, then escalate to operator or report failure.

8. **Add outcome tracking**. After an action completes, log whether the user acknowledged it, corrected it, or ignored it. This feeds the learning model.

9. **Build proactive task scheduling**. Runtime can queue future actions ("check X in 1 hour"). Uses the same approval/policy pipeline.

10. **Defer multi-agent orchestration**. Single-agent autonomy with good controls is more valuable than multi-agent coordination without them.

---

# Prompt 4: Adapter SDK and Surface Contracts

## Executive Summary

Gestalt's adapters should be thin translation layers. The current CLI and web adapters are close to this ideal; Discord is hybrid with legacy service dependencies. The adapter contract needs formal typing, a normalized event model, and clear rules about what adapters must never own.

## Recommended Adapter Contract

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator

class GestaltAdapter(ABC):
    """Base contract for all Gestalt surface adapters."""

    @abstractmethod
    async def start(self, runtime: RuntimeHost) -> None:
        """Start the adapter. Receive runtime reference for event submission."""

    @abstractmethod
    async def stop(self) -> None:
        """Graceful shutdown. Finish in-flight rendering, then exit."""

    @abstractmethod
    async def render(self, response: RuntimeResponse) -> None:
        """Render a runtime response to the platform."""

    @abstractmethod
    async def stream(self, response_stream: AsyncGenerator[ResponseChunk, None]) -> None:
        """Render a streaming response to the platform."""

    # Adapters submit events via:
    # runtime.submit_event(NormalizedEvent)
```

### What Adapters Do
- Parse platform-specific input into `NormalizedEvent`
- Submit events to the runtime
- Render `RuntimeResponse` objects to platform-specific output
- Handle platform transport (WebSocket, HTTP, Discord gateway, stdin/stdout)
- Compute platform-specific facts (channel ID, user roles, message format constraints)
- Manage platform authentication and connection lifecycle

### What Adapters Must NEVER Do
- Select a provider or model
- Choose a persona
- Construct prompts
- Execute tools
- Access memory directly
- Make "smart" decisions about whether to respond
- Own conversation state beyond transport buffering
- Import from `services/*`

## Recommended Event and Response Schemas

### Normalized Event (Adapter → Runtime)

```python
@dataclass
class NormalizedEvent:
    event_id: str                    # Unique event ID
    event_type: EventType            # MESSAGE, COMMAND, REACTION, JOIN, LEAVE, etc.
    surface: str                     # 'discord', 'cli', 'web', 'slack', etc.
    timestamp: datetime

    # User context
    user_id: str                     # Platform-scoped user ID
    user_display_name: str
    user_roles: list[str]            # Platform roles (admin, mod, etc.)

    # Content
    content: str                     # Text content
    attachments: list[Attachment]    # Files, images
    mentions: list[str]              # Mentioned persona/user IDs
    reply_to: str | None             # Parent message ID if reply

    # Platform context (opaque to runtime, passed back in response)
    platform_context: dict           # Channel ID, guild ID, thread ID, etc.
```

### Runtime Response (Runtime → Adapter)

```python
@dataclass
class RuntimeResponse:
    response_id: str
    session_id: str
    event_id: str                    # References the triggering event

    # Content
    persona_id: str                  # Which persona is responding
    persona_display_name: str
    persona_avatar_url: str | None
    content: str                     # Response text
    attachments: list[Attachment]

    # Rendering hints
    format: ResponseFormat           # TEXT, EMBED, CARD, VOICE, etc.
    platform_context: dict           # Passed through from the event

    # Metadata (for traces, not rendering)
    model_used: str
    tokens_used: TokenUsage
    trace_id: str
```

## Versioning/Governance

- **Contract version**: Semantic versioning on the adapter protocol. Breaking changes require major version bump.
- **Adapter registration**: Adapters register with the runtime on start, declaring their version and capabilities.
- **Capability negotiation**: Runtime knows which adapters support streaming, voice, rich embeds. Adapters declare capabilities.

```python
class AdapterCapabilities:
    supports_streaming: bool = False
    supports_voice: bool = False
    supports_rich_embeds: bool = False
    supports_reactions: bool = False
    supports_webhooks: bool = False      # e.g., Discord webhook persona spoofing
    max_message_length: int = 4096
```

## Anti-Patterns to Avoid

1. **Adapter-local intelligence creep**: It starts with "just a small check" and ends with the adapter owning response decisions. Any logic that could differ between adapters for the same input is a bug.

2. **Platform-specific response shaping in runtime**: The runtime should emit a generic response. The adapter shapes it for the platform. Don't have the runtime produce Discord embeds.

3. **Bidirectional adapter coupling**: Adapter A should never communicate with Adapter B. They both talk to the runtime, period.

4. **Transport-specific retry logic in adapters**: Retry is a runtime concern (action execution). Adapters handle transport-level reconnection only.

5. **Adapter-owned persona state**: Adapters should not cache persona state. Request it from the runtime when needed for rendering.

## Implementation Recommendations (Prioritized)

1. **Type the adapter protocol**. Create `GestaltAdapter` ABC with the exact methods above. All three adapters implement it.

2. **Define `NormalizedEvent` and `RuntimeResponse` as dataclasses**. These are the contract types. All adapter↔runtime communication goes through them.

3. **Add adapter capability declaration**. Adapters register their capabilities on start. Runtime uses this for response formatting decisions.

4. **Refactor Discord adapter to remove service imports**. This is the main cleanup. Discord should not import from `services/*`. Route everything through runtime.

5. **Add contract tests**. Test that each adapter correctly normalizes platform events and correctly renders runtime responses. These tests enforce the boundary.

6. **Version the contract**. Start at v1. Document what changes require a version bump.

7. **Build a reference adapter**. The CLI adapter is closest to correct. Clean it up as the reference implementation that new adapters copy from.

8. **Add adapter health reporting**. Adapters report their connection status to the runtime. Runtime exposes aggregate adapter health in `/health`.

---

# Prompt 5: Web Operator Surface

## Executive Summary

The web UI is Gestalt's operator cockpit — not a chat UI (that's just one panel). The operator surface should give visibility into runtime state, sessions, memory, traces, tools, and approval queues. The current web adapter has a chat UI and basic API endpoints. The next phase should build it into a real operator dashboard.

## Recommended Information Hierarchy

### Level 1: Glance (Landing Dashboard)
- Runtime status (RUNNING/DRAINING/etc.)
- Active sessions count
- Adapter status (Discord: connected, CLI: 2 sessions, Web: 1 session)
- Recent activity feed (last 10 events)
- Pending approvals count (badge)
- Error rate (last hour)

### Level 2: Operational (One Click Deep)
- **Sessions panel**: Active sessions with user, persona, turn count, last activity
- **Approval queue**: Pending actions with approve/deny buttons
- **Traces**: Recent runtime traces with expandable detail
- **Alerts**: Errors, budget exhaustions, autonomy escalations

### Level 3: Diagnostic (Two Clicks Deep)
- **Session detail**: Full conversation, memory state, tool calls, trace timeline
- **Memory inspector**: Browse/search/edit user facts, episodic memories, preferences
- **Persona dashboard**: Active personas, relationship states, engagement stats
- **Provider dashboard**: Model usage, latency, cost, error rates by provider
- **Tool dashboard**: Tool invocation counts, success rates, average latency

### Level 4: Advanced (Settings/Config)
- Autonomy level configuration per channel/context
- Provider routing rules
- Tool policy editor
- Memory retention settings
- Persona catalog management

## Recommended Panels/Endpoints/Views

### Core Endpoints

```
GET  /api/health              → Runtime health
GET  /api/sessions            → Active sessions list
GET  /api/sessions/:id        → Session detail (conversation, memory, traces)
GET  /api/traces              → Recent traces (filterable)
GET  /api/traces/:id          → Trace detail (timeline view)
GET  /api/memory/users        → User list with memory summary
GET  /api/memory/users/:id    → User memory detail (facts, episodes, preferences)
PUT  /api/memory/users/:id    → Edit user memory
GET  /api/approvals           → Pending approval queue
POST /api/approvals/:id       → Approve/deny action
GET  /api/personas            → Persona catalog with stats
GET  /api/providers           → Provider status and usage
GET  /api/tools               → Tool registry with invocation stats
POST /api/runtime/kill        → Kill switch (drop to Level 0)
POST /api/runtime/drain       → Initiate graceful shutdown
```

### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│ Gestalt Operator │ Status: RUNNING │ Approvals: 2   │
├──────────┬──────────────────────────────────────────┤
│          │                                           │
│ Sessions │   [Main Content Area]                     │
│ Traces   │   - Session detail                        │
│ Memory   │   - Memory inspector                      │
│ Personas │   - Trace timeline                        │
│ Tools    │   - Approval queue                        │
│ Providers│   - Dashboard widgets                     │
│ Config   │                                           │
│          │                                           │
├──────────┴──────────────────────────────────────────┤
│ Activity Feed (live, streaming via WebSocket)        │
└─────────────────────────────────────────────────────┘
```

## Anti-Patterns to Avoid

1. **Dashboard as the runtime**: The web UI reads from the runtime; it never becomes a second decision-maker. No business logic in the dashboard.
2. **Metrics without context**: Raw numbers are useless. "432 messages processed" means nothing. "432 messages, 98.2% within 2s, 3 failures, 1 escalation" is useful.
3. **Chat-first design**: The chat panel is one view, not the whole UI. Operators need traces, memory, and controls more than they need to type messages.
4. **Polling for live data**: Use WebSocket for real-time updates. Polling creates unnecessary load and latency.
5. **Configuration without preview**: Before changing autonomy levels or tool policies, show what would change. Dry-run mode.

## Implementation Recommendations (Prioritized)

1. **Build the health/status API**. Runtime exposes health, adapter status, session count. Web UI renders it as the landing dashboard.

2. **Build the session list and detail views**. Operators need to see who's talking, what persona is active, and drill into conversation history.

3. **Build the approval queue UI**. This is critical for autonomy. List pending actions, approve/deny with one click.

4. **Build the trace viewer**. Expandable timeline showing: event received → persona selected → memory recalled → prompt assembled → model called → response rendered. This is your debugging superpower.

5. **Build the memory inspector**. Browse user facts, search episodic memories, edit/delete entries. This is essential for trust and debugging.

6. **Add WebSocket event stream**. Live activity feed that shows runtime events in real-time without polling.

7. **Build the kill switch button**. Prominently placed, requires confirmation. Drops all contexts to Level 0 immediately.

8. **Add provider usage dashboard**. Show model selection distribution, cost per session, latency percentiles. Helps optimize provider routing.

9. **Build persona stats panel**. Which personas are most engaged, relationship state overview, evolution stage distribution.

10. **Defer complex configuration UIs**. Start with read-only dashboards. Add configuration editing after the read layer is solid.

---

# Prompt 6: Security and Trust Boundaries

## Executive Summary

Security in Gestalt must be designed early for the trust boundaries that matter most: provider secret handling, runtime vs adapter trust, tool risk classification, and prompt injection defense. The current system runs as a single-user self-hosted instance, but architectural decisions now determine how hard it is to add multi-user isolation later.

## Recommended Security Architecture

### Trust Zones

```
Zone 0 (TRUSTED):     Runtime core, config, provider secrets
Zone 1 (SEMI-TRUSTED): Adapters (they parse untrusted input but are locally deployed)
Zone 2 (UNTRUSTED):    User input, MCP servers, external tool responses
Zone 3 (HOSTILE):      Internet-sourced content injected via tools (web search results, etc.)
```

### Key Principle: Defense in Depth from the Runtime Out

The runtime is the trust anchor. Everything flows through it. Security is enforced at the runtime layer, not at adapters.

## Threat Model Categories

1. **Provider secret leakage**: API keys exposed in logs, traces, error messages, or adapter-accessible state.
2. **Prompt injection**: User input or tool results that attempt to override system instructions, extract secrets, or manipulate behavior.
3. **Tool abuse**: Using tools beyond their intended scope, chaining tools to exfiltrate data, or invoking tools without authorization.
4. **Data exfiltration via tool responses**: External tool results containing instructions that the model follows (indirect injection).
5. **MCP server compromise**: A connected MCP server returns malicious tool descriptions or results.
6. **Session hijacking**: One user accessing another user's session state or memory.
7. **Adapter compromise**: A compromised adapter sending forged events.
8. **Denial of service**: Expensive model calls, unbounded tool chains, or memory flooding.

## Defense-in-Depth Recommendations

### Secrets Management
- Provider API keys live in environment variables or a secrets manager, never in config files committed to source.
- Runtime never passes secrets to adapters. Adapters never see API keys.
- Traces and logs must scrub secrets before writing. Implement a secret redaction filter on trace emission.
- Model responses are never logged with the full prompt if the prompt contains secrets.

### Prompt Injection Defense
- **System prompt isolation**: Clear delimiter between system instructions and user input. Use the provider's native system message role, never concatenate into a single message.
- **Tool result quarantine**: All tool results are injected as `tool` role messages (or equivalent), never as `system` or `assistant`. The model knows these are external data.
- **Output monitoring**: Check model outputs for patterns that suggest injection succeeded (echoing system prompts, tool definitions, or secrets).
- **Input sanitization**: Strip known injection patterns from user input. This is a weak defense but adds friction.

### Tool Security
- **Risk tier enforcement**: Every tool has a risk tier. The runtime enforces the tier policy before execution.
- **Parameter validation**: Tool inputs are validated against schemas before execution. No arbitrary parameter passthrough.
- **Result size limits**: Tool results are truncated to prevent context flooding.
- **MCP server allowlist**: Only explicitly configured MCP servers can be connected. No auto-discovery.
- **MCP tool sandboxing**: MCP tool descriptions are treated as untrusted. The runtime validates tool schemas match expectations.

### Session Isolation
- Sessions are scoped by user ID. No cross-session memory access without explicit runtime policy.
- Adapter-provided user IDs are the session key. Adapters are responsible for authenticating users on their platform.
- Memory queries are always scoped by user_id. No global memory queries from adapter-facing paths.

### Audit Logging
- Every tool invocation logged with parameters, result summary, and approval chain.
- Every memory write logged with source and confidence.
- Every model call logged with model used, token count, and prompt hash (not full prompt in production).
- Logs are append-only and not modifiable by the runtime.

## Release Blockers vs Later Hardening

### Release Blockers (Must have before production multi-user)
- Secret redaction in traces and logs
- Tool risk tier enforcement
- Session isolation by user ID
- Action logging for all MODIFY+ actions
- Input validation on all adapter-submitted events

### Later Hardening (Can defer for single-operator self-hosted)
- Full prompt injection detection pipeline
- MCP server certificate pinning
- Rate limiting per user
- Output monitoring for injection indicators
- Formal audit log tamper protection
- Multi-tenant isolation (separate databases per tenant)

## Implementation Recommendations (Prioritized)

1. **Implement secret redaction on trace/log emission**. Filter all outputs for API key patterns before writing. This is a release blocker.

2. **Enforce tool risk tiers in the runtime**. No tool executes without passing the policy check. Log every invocation.

3. **Scope all memory queries by user_id**. Add user_id as a required parameter to every memory coordinator method. No unscoped queries.

4. **Validate adapter event schemas**. NormalizedEvent must pass validation before the runtime processes it. Reject malformed events.

5. **Quarantine tool results**. All tool/MCP results enter the prompt as tool-role messages, never as system or assistant content.

6. **Add MCP server allowlist**. Only pre-configured MCP servers can be connected. Log all MCP interactions.

7. **Implement action logging**. Complete audit trail for all MODIFY+ actions with who/what/when/why.

8. **Add rate limiting**. Per-session and per-user rate limits on event submission and tool invocation.

9. **Add output monitoring**. Basic regex/pattern check on model outputs for secret leakage and injection indicators.

10. **Defer multi-tenant isolation**. For now, Gestalt is single-operator. Design the data model to support multi-tenant later (tenant_id columns) but don't build the isolation layer yet.

---

# Prompt 7: Embodiment, VRM, and Environment Bridges

## Executive Summary

Embodiment is Gestalt's long-term differentiator: a runtime-driven avatar that expresses state, not just renders a static model. Project Airi is the closest existing system and provides useful reference architecture, but their browser-first design and scattered monorepo should be learned from, not copied. The key principle: the runtime drives expression and action through a protocol; the client renders. No intelligence in the embodiment layer.

## Recommended Embodiment Direction

### Core Principle: Runtime State → Expression Protocol → Client Renderer

```
Runtime (owns state)           Protocol (data contract)         Client (renders)
┌──────────────────┐          ┌────────────────────┐          ┌─────────────────┐
│ Emotional state   │ ───────→│ ExpressionEvent     │─────────→│ VRM/Live2D      │
│ Attention target  │          │ - emotion: "amused"│          │ - Blend shapes   │
│ Action intent     │          │ - intensity: 0.7   │          │ - Animations     │
│ Speech state      │          │ - gaze: [x,y,z]    │          │ - Lip sync       │
│ Persona context   │          │ - action: "nod"    │          │ - Position       │
└──────────────────┘          └────────────────────┘          └─────────────────┘
```

The runtime computes what the avatar should express based on conversation context, emotional state, and persona personality. It emits expression events. The client receives these events and maps them to VRM blend shapes, animations, or scene actions. The client never decides what to express — only how.

## Recommended Runtime/Client Boundary

### Runtime Owns
- Emotional state model (derived from conversation analysis)
- Expression selection (which emotions/actions to express, when)
- Speech timing and segmentation (for lip sync alignment)
- Gaze direction (who/what to look at, derived from attention model)
- Action vocabulary selection (nod, shake head, gesture, idle)
- Scene awareness (what's happening in a bounded environment)

### Client/Presence Layer Owns
- VRM model loading and rendering
- Blend shape mapping (expression protocol → specific blend shape values)
- Animation playback
- Lip sync audio alignment
- Camera and viewport
- Scene rendering
- Platform-specific input (mouse tracking for gaze, etc.)

### Neither Should Own (Avoid)
- Client-side personality decisions
- Client-side conversation understanding
- Client-side tool execution
- Runtime-side rendering optimization

## Recommended Protocol/Event Ideas

### Expression Events (Runtime → Client)

```typescript
interface ExpressionEvent {
  type: 'expression';
  timestamp: number;
  emotion: string;           // 'neutral', 'happy', 'thinking', 'surprised', 'concerned', etc.
  intensity: number;         // 0.0 - 1.0
  duration_ms: number;       // How long to hold
  blend_with_current: boolean; // Smooth transition vs snap
}

interface GazeEvent {
  type: 'gaze';
  target: 'user' | 'away' | 'object';
  coordinates?: [number, number, number]; // For specific targets
  transition_ms: number;
}

interface ActionEvent {
  type: 'action';
  action: string;            // From bounded vocabulary: 'nod', 'shake_head', 'wave', 'think', 'idle'
  parameters?: Record<string, any>;
}

interface SpeechEvent {
  type: 'speech';
  state: 'start' | 'pause' | 'resume' | 'end';
  text_segment?: string;     // For lip sync alignment
  phoneme_timings?: PhonemeTimng[]; // If TTS provides them
}
```

### Bounded Action Vocabulary

For each environment type, define a fixed set of actions:

**Chat avatar**: nod, shake_head, think, wave, smile, surprised, idle, look_at_user, look_away
**Game bridge (Minecraft)**: move, mine, place, craft, look, jump, interact, idle
**Scene (authored)**: predefined interaction points per scene

The vocabulary is fixed per environment type. The runtime selects from this vocabulary. No open-ended action generation.

## Recommended Staged Roadmap

### Near-Term (Next 3-6 months)
- Define the expression protocol schema
- Build the expression event emitter in the runtime (driven by conversation emotion analysis)
- Create a basic web-based VRM viewer that receives expression events over WebSocket
- Implement idle behaviors (blink, subtle movement) client-side
- Connect TTS output to lip sync pipeline

### Mid-Term (6-12 months)
- Add authored scene support (predefined 3D scenes with interaction points)
- Implement gaze tracking (avatar follows mouse/user camera)
- Add action vocabulary for chat context (nod during user message, think during generation)
- Build the Tamagotchi/desktop companion mode (Airi-style always-on-top window)
- Add expression blending and smooth transitions

### Long-Term (12+ months)
- Game environment bridges (Minecraft, etc.) using bounded action vocabularies
- Multi-avatar scenes (persona-to-persona interactions with spatial awareness)
- User-provided VRM models with automatic blend shape mapping
- WebXR support for immersive contexts
- Learning from environment interactions (bounded, explicitly modeled)

## Anti-Patterns to Avoid

1. **Intelligence in the client**: The VRM viewer should be a dumb renderer. It maps events to visuals. It doesn't decide what to express.

2. **Open-ended action generation**: "Generate any action" leads to unpredictable behavior and impossible testing. Use bounded vocabularies.

3. **Embodiment coupled to runtime core**: The expression system should be a runtime module, not embedded in the core loop. If embodiment is disabled, the runtime should work identically.

4. **Browser-first at the cost of server authority**: Airi puts significant logic in the browser. Gestalt should compute expression server-side and stream to clients. Clients that go offline lose state; that's fine.

5. **Premature game integration**: Building a Minecraft agent before the expression protocol is solid means building it twice. Protocol first, environments second.

## Implementation Recommendations (Prioritized)

1. **Define the expression protocol schema**. TypeScript interfaces for ExpressionEvent, GazeEvent, ActionEvent, SpeechEvent. This is the contract between runtime and client.

2. **Build the emotion analysis module**. Simple sentiment/emotion detection on conversation context. Map to expression events. Start with rule-based (keywords, punctuation, persona personality) before adding model-based detection.

3. **Create a minimal VRM web viewer**. Three.js + VRM loader. Receives expression events over WebSocket. Renders to a web page. This is your proof-of-concept.

4. **Implement idle behaviors client-side**. Blink, subtle head movement, breathing. These don't need runtime events — they're ambient animation.

5. **Connect TTS to lip sync**. If Gestalt has TTS output (it does — Kokoro), pipe phoneme timings to the VRM viewer for lip sync.

6. **Add expression event emission to the runtime**. During response generation: emit 'thinking' expression. On response delivery: emit emotion matching content. Between turns: emit 'idle'.

7. **Build the action vocabulary system**. Define vocabularies per environment type. Runtime selects from vocabulary. Client maps to animations.

8. **Defer game bridges**. Minecraft/Factorio are cool but complex. Get the chat avatar working perfectly first.

9. **Defer WebXR**. Interesting but not essential. Browser-based VRM with expression is the priority.

10. **Defer multi-avatar scenes**. Two avatars interacting requires spatial coordination. Get single-avatar expression right first.

---

# Prompt 8: Comparative Review

## Comparative Matrix

| Dimension | OpenAI Agents SDK | Anthropic (MCP + Docs) | Kimi CLI | ElizaOS | Project Airi |
|-----------|------------------|----------------------|----------|---------|--------------|
| **Runtime clarity** | Good. Runner is clean orchestrator | MCP is protocol, not runtime. Docs describe tools well | Excellent. Layered: config/execution/tool/UI | Moderate. AgentRuntime exists but plugins blur boundaries | Good. server-runtime is distinct from clients |
| **Adapter/surface model** | N/A (SDK, not platform) | N/A (protocol spec) | Good. CLI is the surface, clean separation | Moderate. "Services" (Discord, Telegram) have too much logic | Good. stage-web/tamagotchi/pocket as clients via server-sdk |
| **Memory model** | Weak. Sessions added recently, external memory needed (Mem0) | Good docs on prompt caching. No memory architecture | Weak in CLI context | Basic. RAG + character memories. No tiered model | WIP. Memory Alaya planned. DuckDB WASM + pgvector present |
| **Tool system** | Good. Function tools + MCP integration + guardrails | Excellent. MCP is the industry standard for tool integration | Good. Auto-wired tools, checkpoint/undo | Actions system — functional but overloaded | xsAI as provider abstraction. Tool system tied to game agents |
| **Autonomy controls** | Moderate. Guardrails, but no approval flows or risk tiers | Good docs on tool safety. Trust model in MCP spec | Excellent. Checkpoint/undo, approval gates, undo system | Weak. Autonomous actions without formal controls | Minimal. Game agents act autonomously without gating |
| **Security** | Good. Guardrails run in parallel, input/output validation | Strong. MCP spec has explicit security sections, trust model | Good. Approval for dangerous ops | Sandboxed execution, permission controls | Minimal. Self-hosted focus, no formal trust model |
| **Embodiment** | None | None | None | None | Strong. VRM + Live2D + audio pipeline. Browser-first |
| **Maturity** | Production. Backed by OpenAI | Production protocol spec. Massive adoption | Production CLI tool | Production (Web3-focused). Token ecosystem concerns | Active development. Many WIP subsystems |

## Strongest Patterns Worth Borrowing

1. **OpenAI — Guardrails as parallel checks**: Run input validation concurrently with model execution. Fail fast if guardrail triggers. Don't make safety sequential.

2. **OpenAI — Handoff mechanism**: Agent-to-agent delegation as a typed tool call. Clean for multi-persona routing in Gestalt (persona A hands off to persona B).

3. **Anthropic MCP — Tool-as-capability schema**: Structured tool descriptions with parameter schemas, risk annotations. Gestalt should adopt this for its tool registry.

4. **Anthropic MCP — Code execution over MCP**: For scaling tool count without bloating context. Load tool definitions on demand via code.

5. **Anthropic — Prompt caching with cache_control breakpoints**: Structure prompts with explicit cache boundaries. Biggest single cost/latency optimization available.

6. **Kimi CLI — Checkpoint/undo system**: Before executing a risky action, snapshot state. Enable rollback. This is the safety backbone for autonomy.

7. **Kimi CLI — Layered architecture**: Config layer, execution layer, tool layer, UI layer — each with clear responsibilities. Gestalt's runtime/adapter split aligns but needs the tool/config layers formalized.

8. **Kimi CLI — Approval gates on dangerous operations**: Fine-grained control — auto-approve reads, require approval for writes. Gestalt needs exactly this.

9. **ElizaOS — Worlds/Rooms context isolation**: Scoping agent context by workspace and channel. Useful for Gestalt's multi-channel Discord deployment and future multi-user scenarios.

10. **Project Airi — Runtime/SDK client separation**: `server-runtime` + `server-sdk` as the interface between backend and all frontends (web, desktop, mobile, bots). Gestalt's RuntimeHost + adapter contract should mirror this.

11. **Project Airi — Soul container concept**: Personality as middleware that transforms model output, not just a system prompt prefix. Architectural personality, not prompt personality.

## Strongest Anti-Patterns to Avoid

1. **ElizaOS — Plugin-as-everything**: Plugins can define actions, evaluators, providers, and services. This creates a second runtime inside every plugin. Keep Gestalt's plugins as tool providers only.

2. **ElizaOS — Token/Web3 coupling**: Architecture decisions driven by token economics rather than technical merit. Don't let external concerns shape internal architecture.

3. **Project Airi — Monorepo sprawl**: 50+ packages across multiple organizations. Hard to reason about, hard to contribute to. Keep Gestalt's package count minimal and flat.

4. **Project Airi — Browser-first at the cost of server authority**: Putting computation in the browser limits what you can do without the browser. Gestalt is server-first. Keep it that way.

5. **OpenAI — Memory as an afterthought**: The Agents SDK shipped without built-in memory. Sessions were added later. Memory needs to be a first-class runtime subsystem from the start.

6. **Generic — Event bus as primary architecture**: Event buses create invisible coupling and make control flow hard to trace. Prefer explicit function calls for primary flows, events for monitoring/traces.

## Near-Term Recommendations for Gestalt

1. Formalize the adapter contract (typed protocol, normalized events)
2. Kill `services/*` authority in maintained paths
3. Build the action logger and trace emitter
4. Implement tool risk tiers and approval queue
5. Build the memory coordinator with tiered retrieval
6. Add prompt assembly pipeline with cache boundaries
7. Build the operator dashboard (health, sessions, traces, approvals)

## Long-Term Ideas Worth Tracking

1. Kimi's Agent Swarm — parallel sub-agent execution for complex tasks
2. MCP's code-execution-over-tools pattern for scaling tool count
3. Airi's soul container as personality middleware
4. Multi-model routing with automatic capability matching
5. Expression protocol for VRM embodiment
6. Bounded environment bridges with fixed action vocabularies

---

# Synthesis: Unified Architecture Brief

## Executive Summary

Across all eight research prompts, the findings converge on a single thesis: **Gestalt's runtime-first architecture is correct, and the next phase is formalization and hardening, not reinvention.** The runtime owns sessions, providers, tools, memory, traces, personas, and policy. Adapters are thin. The web UI is an operator surface. Embodiment is a future client driven by runtime state.

The research identifies no contradictions with this direction from any credible external system. The strongest agent frameworks all converge on centralized orchestration with peripheral surfaces.

## Consensus Findings

All eight prompts agree on:

1. **Runtime is the single authority.** No adapter, plugin, or UI should make orchestration decisions.
2. **Adapters are translators.** Parse input, normalize, submit to runtime, render output. Nothing more.
3. **Memory needs a coordinator.** The current scattered access pattern should be unified under a single runtime-owned subsystem.
4. **Traces are non-negotiable.** Every runtime decision needs a structured log. This powers debugging, the operator dashboard, and future learning.
5. **Tool execution needs policy.** Risk tiers, budgets, approval gates, and logging before any autonomy expansion.
6. **Prompt assembly should be cache-aware.** Stable prefix with explicit cache boundaries is the biggest single optimization.
7. **Security boundaries must be designed now, even if enforced gradually.** Trust zones, secret handling, and session isolation get harder to add later.
8. **Embodiment is a client concern driven by runtime state.** The expression protocol is the contract. No intelligence in the renderer.

## Conflicts and Resolutions

### Memory scoping vs cross-persona context
- **Prompts 2 and 4 tension**: Memory scoped by persona (Prompt 2) conflicts with cross-persona relationship context (Prompt 4 and existing persona relationships feature).
- **Resolution**: Default scope is per-persona. A separate "shared memory" tier exists for relationship and social state that personas can opt into. The runtime controls access.

### Autonomy level granularity
- **Prompts 3 and 6 tension**: Prompt 3 wants five autonomy levels; Prompt 6 wants minimal complexity for security.
- **Resolution**: Implement five levels but default to Level 1 (REACTIVE). Advanced levels are opt-in per channel. Security controls enforce the ceiling regardless of configured level.

### Browser-first vs server-first for embodiment
- **Prompts 7 and 1 tension**: Airi's browser-first approach vs Gestalt's runtime-first principle.
- **Resolution**: Server computes, client renders. Expression events are computed server-side and streamed to any client (browser, desktop, mobile). Client handles rendering and platform-specific input only.

## Final Recommended Architecture Direction

```
┌─────────────────────────────────────────────────────────┐
│                    OPERATOR SURFACE                       │
│  Web Dashboard: health, sessions, traces, approvals,     │
│  memory inspector, persona stats, provider usage         │
└────────────────────────┬────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────┴────────────────────────────────┐
│                   GESTALT RUNTIME                         │
│                                                           │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐  │
│  │ Session  │ │ Provider │ │ Tool   │ │ Memory       │  │
│  │ Manager  │ │ Router   │ │ Policy │ │ Coordinator  │  │
│  └─────────┘ └──────────┘ └────────┘ └──────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐  │
│  │ Persona  │ │ Context  │ │ Trace  │ │ Action       │  │
│  │ Catalog  │ │ Assembler│ │ Emitter│ │ Executor     │  │
│  └─────────┘ └──────────┘ └────────┘ └──────────────┘  │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Expression Engine (for embodiment, when enabled)    ││
│  └─────────────────────────────────────────────────────┘│
└────────────┬──────────┬──────────┬──────────┬───────────┘
             │          │          │          │
        ┌────┴───┐ ┌───┴────┐ ┌──┴───┐ ┌───┴─────┐
        │Discord │ │  CLI   │ │ Web  │ │  VRM    │
        │Adapter │ │Adapter │ │Chat  │ │ Client  │
        └────────┘ └────────┘ └──────┘ └─────────┘
```

## Top 10 Implementation Priorities

1. **Type the adapter contract.** `GestaltAdapter` ABC, `NormalizedEvent`, `RuntimeResponse`. This is the foundation everything else builds on.

2. **Build the trace emitter.** Structured events for every runtime decision. This powers debugging, the operator dashboard, and future optimization.

3. **Build the memory coordinator.** Tiered memory model (working → session → episodic → semantic → preference) with token-budget-aware retrieval. Single entry point, runtime-owned.

4. **Implement tool risk tiers and action logging.** Classify every tool. Log every invocation. This is prerequisite for autonomy and security.

5. **Build the prompt assembly pipeline with cache boundaries.** Stable prefix + dynamic context. Use Anthropic cache_control breakpoints. Biggest cost/latency win available.

6. **Kill `services/*` authority in maintained paths.** Move remaining service logic into runtime subsystems. Discord adapter should not import from services.

7. **Build the approval queue.** Web UI for pending actions. Approve/deny with one click. This enables safe Level 3+ autonomy.

8. **Build the operator dashboard landing page.** Runtime health, active sessions, adapter status, recent activity, pending approvals. This is your cockpit.

9. **Implement session lifecycle.** Create/suspend/resume/destroy with explicit state boundaries. Every adapter interaction goes through a session.

10. **Add secret redaction to trace/log output.** Filter all outputs for API key patterns before writing. This is a security release blocker.

## What to Defer

- **Multi-agent orchestration**: Single-agent autonomy with good controls first
- **VRM/embodiment implementation**: Define the protocol now, build the renderer later
- **Game environment bridges**: Chat avatar first, Minecraft second
- **Multi-tenant isolation**: Design the data model for it (tenant_id columns), but don't build the isolation layer
- **Advanced RAG optimizations**: Current vector search works. Optimize after the coordination layer is solid
- **Agent Swarm/parallel execution**: Track Kimi's approach, but Gestalt needs single-agent reliability first
- **WebXR**: Interesting but years away from being necessary
- **Fine-tuning/distillation pipeline**: Focus on good prompts and caching before model customization

## Anti-Patterns to Explicitly Avoid

1. **Adapter-local intelligence** — Any decision that could differ between adapters for the same input is a bug
2. **Service layer as second runtime** — services/* is legacy, not architecture authority
3. **Event bus as primary control flow** — Explicit function calls for control, events for monitoring
4. **Plugin-as-everything** (ElizaOS pattern) — Plugins provide tools, not intelligence
5. **Unbounded autonomy** — Every autonomous action needs a budget, a log, and a policy check
6. **Memory without invalidation** — Every memory needs confidence, provenance, and a mechanism to be revised
7. **Browser-first embodiment** — Server computes, client renders
8. **God-prompt in adapters** — Adapters provide facts; runtime assembles context
9. **Approval fatigue** — Auto-approve safe actions, require approval only for genuinely risky ones
10. **Architecture by demo** — Don't copy a system because its demo looks cool. Copy patterns that survive production pressure

---

*End of research brief. This document covers all 8 prompts from the Gestalt Research Prompt Pack plus the unified synthesis. Recommendations are prioritized for near-term implementation and grounded against the current `joshhmann/acore_bot` codebase.*
