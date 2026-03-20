# Gestalt Runtime API

**Last Updated**: 2026-03-19

## Purpose

This document defines the canonical adapter-facing contract for Gestalt.

Surface adapters should integrate with Gestalt through this API instead of
reaching into runtime internals or legacy service seams directly.

The web runtime is the current reference implementation of this contract.

## Scope

The Runtime API exists for:

- web and browser clients
- CLI/TUI parity work
- Discord migration
- future Slack, Telegram, and voice surfaces
- local desktop packaging

It is not the connector API.
MCP, Home Assistant, app integrations, and scene bridges remain capability-layer
surfaces behind runtime policy.

## Authority

Runtime owns:

- session creation and mutation
- persona, mode, and social state
- command execution
- provider/model routing
- tool and connector orchestration
- trace and presence updates
- memory and learning coordination

Surface adapters own:

- platform input parsing
- transport
- rendering/runtime output presentation
- platform-specific UX quirks

Surface adapters do not own:

- provider calls
- tool execution policy
- memory writes
- social logic
- session mutation outside the Runtime API

## Contract Shape

The Runtime API should support the same conceptual operations across in-process,
stdio, and HTTP/WebSocket transports.

### Event Submission

Submit normalized events into runtime:

- chat text
- slash commands
- system observations
- later scene/action observations

Current routes:

- `POST /api/runtime/event`
- stdio `send_event`
- direct runtime `handle_event_envelope(...)`

### Snapshot Access

Read runtime-owned state without adapter-side reconstruction:

- commands
- status
- session summary
- recent sessions
- tools
- trace
- presence
- social state
- context cache
- providers

Current routes:

- `GET /api/runtime/commands`
- `POST /api/runtime/status`
- `POST /api/runtime/session`
- `POST /api/runtime/sessions`
- `POST /api/runtime/tools`
- `POST /api/runtime/trace`
- `POST /api/runtime/presence`
- `POST /api/runtime/social`
- `POST /api/runtime/context`
- `POST /api/runtime/context/reset`
- `POST /api/runtime/providers`

Current stdio methods:

- `list_commands`
- `get_status`
- `get_session`
- `list_sessions`
- `get_tools`
- `get_trace`
- `get_presence`
- `get_social`
- `get_context`
- `reset_context`
- `get_providers`

Maintained standalone entrypoints now share one canonical runtime assembly and
host seam through `gestalt/runtime_bootstrap.py`. Canonical runtime assembly
now lives there directly, while `adapters/runtime_factory.py` remains only as a
compatibility shim during migration. This is the beginning of the
target model where Gestalt runtime can run independently and surface adapters
attach to it through this API instead of each entrypoint inventing its own
bootstrap path.

### Social-State Mutation

Allow adapters to mutate social-mode state only through runtime:

- `POST /api/runtime/social/mode`
- `POST /api/runtime/social/reset`
- stdio `set_social_mode`
- stdio `reset_social_state`

### Context Cache Controls

Allow operators and surfaces to introspect/reset runtime-owned context caching:

- `POST /api/runtime/context`
- `POST /api/runtime/context/reset`
- stdio `get_context`
- stdio `reset_context`
- runtime commands `/context` and `/context reset`

The maintained runtime cache model is `stable-prefix`:

- runtime caches reusable prompt prefixes owned by persona/mode/provider/tool state
- dynamic memory context, recent history, and the current user turn remain outside the cached prefix
- adapters do not participate in cache-key construction or prompt segmentation
- provider-native prompt caching may be used opportunistically on top of this when the backend reports cached-token usage

### Streaming

Live adapters use the runtime websocket stream for:

- connection status
- transcript deltas
- transcript entries
- trace entries
- presence updates
- request completion/errors

Current route:

- `/api/runtime/ws`

## Session Model

Sessions are runtime-owned and adapter-scoped.

Session summaries should expose enough information for adapters to render
current state without recomputing it locally:

- `session_id`
- `persona_id`
- `mode`
- `platform`
- `room_id`
- `flags`
- `yolo`
- `provider`
- `model`
- `social`
- recent activity timestamps
- last visible text
- autopilot activity

Adapters may create or bootstrap sessions implicitly by requesting a session
snapshot with context.

Recent-session listing is intentionally adapter-scoped.

Maintained adapters should pass stable scope metadata when listing sessions so a
surface only sees its own recent work instead of every runtime session on the
same platform. The current maintained browser client does this with a stable
client-scoped `flags.user_scope` value and a separate stable `user_id` for
request attribution.

The maintained web/browser path also propagates a stable client identifier at
the transport layer:

- HTTP uses `X-Gestalt-Client-Id`
- HTTP uses `X-Gestalt-User-Id`
- websocket connect uses `client_id`
- websocket connect uses `user_id`

The web adapter merges those values into runtime flags when the adapter did not
already set them explicitly and uses the resolved `user_id` as the maintained
actor on HTTP and websocket event paths.

When API-token auth is enabled, the maintained web adapter no longer trusts the
caller-supplied `user_id` header or websocket field as runtime authority. It
derives a server-owned authenticated actor id from the authenticated web scope
and preserves the client-supplied id only as `flags.claimed_user_id`.

## Security

All Runtime API transports should enforce the same rules:

- auth is required when configured
- requests are scoped to a session
- adapters never bypass tool or connector policy
- trace and request attribution remain runtime-owned

This contract is intentionally narrower than a plugin marketplace or skill
execution layer. Capability execution remains behind runtime policy.

## Current Status

Implemented in the maintained product path:

- shared runtime bootstrap/helper module and `RuntimeHost` seam for maintained
  launcher, CLI, TUI, web, stdio, and Discord runtime-chat entrypoints
- direct standalone runtime host entrypoints through
  `gestalt runtime --stdio` and `gestalt runtime --web --port <port>`
- HTTP bootstrap and event routes
- websocket live transport
- stdio parity for the same core snapshots
- explicit social-state routes
- explicit context-cache snapshot/reset routes
- stable-prefix prompt assembly that separates reusable system/persona/mode
  prompt content from dynamic memory context and recent turns
- provider usage telemetry including cached-input token reporting when the
  backend exposes it
- session bootstrap and adapter-scoped recent-session listing
- browser runtime bridge adoption for session bootstrap, recent-session listing,
  social snapshot rendering, and social-mode mutation
- browser social-state mutation through the same Runtime API contract used for
  snapshot/bootstrap work
- web/browser client-scope propagation through HTTP headers and websocket
  connect payloads for maintained session attribution
- web/browser user-id propagation through HTTP headers and websocket connect
  payloads for maintained request attribution when auth is disabled
- server-owned authenticated actor attribution for maintained web/browser
  requests when API-token auth is enabled

Still partial or deferred:

- stronger typed SDK surfaces over the existing contract
- identity-specific snapshots
- scene/action observation extensions
- stronger cross-transport schema centralization
- full Discord migration onto this contract
- runtime-owned approval queue and action-record surfaces
- richer trace and memory-inspection transport schemas

## Adapter SDK Contract (v1.0)

The adapter SDK defines a four-phase lifecycle contract for platform adapters.
This contract enforces runtime-first boundaries while providing clear extension
points for new platforms (Slack, Telegram, etc.).

Near-term formalization direction:

- extend the existing `PlatformFacts` ingress contract rather than inventing a
  parallel adapter stack
- standardize adapter capability declaration and response-envelope typing on top
  of the current maintained web/stdio contract
- keep approval, memory, trace, and session mutation surfaces runtime-owned and
  transport-agnostic

### Design Principles

1. **Adapters Extract Facts Only**
   - Adapters parse platform-native events into `PlatformFacts`
   - Facts contain only observable data (mentions, IDs, text)
   - Facts never contain policy decisions (should_respond, persona, style)

2. **Runtime Owns All Policy**
   - `should_respond` decision: runtime-owned via `decide_surface_response()`
   - Persona selection: runtime-owned based on facts + context
   - Style/personality: runtime-owned, not adapter-selected

3. **Adapters Render Runtime Output Only**
   - Adapters receive `RuntimeDecision` from runtime
   - Adapters may only choose how to render, not what to render
   - No adapter-side persona switching allowed

### Four-Phase Lifecycle

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Platform Event │────▶│  Phase 1: parse  │────▶│ PlatformFacts   │
│  (native type)  │     │  (adapter-owned) │     │ (normalized)    │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                          ┌──────────────────┐           │
                          │  Phase 3: from_  │◄──────────┘
                          │  runtime_response│
                          │  (adapter-owned) │
                          └────────┬─────────┘
                                   │
┌─────────────────┐     ┌──────────▼─────────┐     ┌─────────────────┐
│  Platform       │◀────│  Phase 4: render   │◀────│ RuntimeDecision │
│  Response       │     │  (adapter-owned)   │     │ + Response      │
└─────────────────┘     └────────────────────┘     └─────────────────┘
                               ▲
                               │
┌─────────────────┐     ┌──────┴─────────────┐
│  Runtime        │◀────│  Phase 2: to_      │
│  handle_event   │     │  runtime_event     │
│  (runtime-owned)│     │  (adapter-owned)   │
└─────────────────┘     └────────────────────┘
```

#### Phase 1: `parse()`

Transform platform-native event to normalized facts.

```python
@abstractmethod
def parse(self, event: T) -> PlatformFacts:
    """Extract facts from platform-native event."""
    # Example (Discord generalized):
    return PlatformFacts(
        text=message.content,
        user_id=str(message.author.id),
        room_id=str(message.channel.id),
        is_direct_mention=bot.user in message.mentions,
        is_reply_to_bot=await self._is_reply_to_bot(message),
        # ... other facts
    )
```

**Adapter Responsibility:** Extract platform-specific facts only  
**Runtime Responsibility:** None (facts passed to runtime in Phase 2)

#### Phase 2: `to_runtime_event()`

Build runtime Event from normalized facts.

```python
def to_runtime_event(
    self,
    facts: PlatformFacts,
    *,
    session_id: str | None = None,
    persona_id: str = "",
    mode: str = "",
) -> Event:
    """Create runtime Event from PlatformFacts."""
```

**Adapter Responsibility:** Create Event with facts attached as metadata  
**Runtime Responsibility:** Process event and return Response

#### Phase 3: `from_runtime_response()`

Transform runtime output to normalized decision.

```python
def from_runtime_response(
    self,
    runtime_response: Response,
    original_facts: PlatformFacts,
) -> RuntimeDecision:
    """Extract runtime decision from Response."""
```

**Adapter Responsibility:** Extract decision from runtime output  
**Runtime Responsibility:** Provide complete policy decision

#### Phase 4: `render()`

Send runtime response to platform.

```python
@abstractmethod
async def render(
    self,
    platform_context: R,
    decision: RuntimeDecision,
    runtime_response: Response,
) -> None:
    """Send response to platform (pure transport)."""
```

**Adapter Responsibility:** Transport response to platform  
**Runtime Responsibility:** None (decision already made)

### Key Data Types

#### `PlatformFacts`

Normalized facts extracted from any platform:

```python
@dataclass(frozen=True, slots=True)
class PlatformFacts:
    text: str                    # Message content
    user_id: str                 # Platform user ID
    room_id: str                 # Platform room/channel ID
    message_id: str              # Platform message ID
    is_direct_mention: bool      # Bot was mentioned
    is_reply_to_bot: bool        # Reply to bot's message
    is_persona_message: bool     # From persona webhook
    has_visual_context: bool     # Has attachments/embeds
    author_is_bot: bool          # Author is bot account
    platform_flags: dict         # Platform-specific flags
    raw_metadata: dict           # Debug metadata
```

#### `RuntimeDecision`

Runtime-owned policy decision:

```python
@dataclass(frozen=True, slots=True)
class RuntimeDecision:
    should_respond: bool     # Whether to respond
    reason: str              # Human-readable reason
    suggested_style: str     # Optional style hint
    persona_id: str          # Selected persona
    session_id: str          # Session identifier
```

### Implementation Requirements

New platform adapters must:

1. **Inherit from `AdapterLifecycleContract[T, R]`**
   - `T`: Platform-native event type (e.g., `discord.Message`)
   - `R`: Platform-native context type (e.g., `discord.TextChannel`)

2. **Implement `parse()`**
   - Extract `PlatformFacts` from platform-native events
   - Never make policy decisions

3. **Implement `render()`**
   - Send responses to platform
   - Never override runtime decisions

4. **Use inherited `to_runtime_event()` and `from_runtime_response()`**
   - Override only if platform needs custom behavior
   - Call `super()` to maintain contract invariants

### Example: Discord Pattern Generalized

```python
class DiscordAdapter(AdapterLifecycleContract[discord.Message, discord.TextChannel]):
    def __init__(self, bot: discord.Bot):
        super().__init__(AdapterConfig(
            platform_name="discord",
            supports_embeds=True,
            supports_threads=True,
        ))
        self.bot = bot

    def parse(self, message: discord.Message) -> PlatformFacts:
        """Extract facts from Discord message."""
        return PlatformFacts(
            text=message.content,
            user_id=str(message.author.id),
            room_id=str(message.channel.id),
            message_id=str(message.id),
            is_direct_mention=self.bot.user in message.mentions,
            is_reply_to_bot=message.reference is not None,
            has_visual_context=bool(message.attachments or message.embeds),
            author_is_bot=message.author.bot,
        )

    async def render(
        self,
        channel: discord.TextChannel,
        decision: RuntimeDecision,
        response: Response,
    ) -> None:
        """Send response to Discord channel."""
        if response.text:
            async with channel.typing():
                await channel.send(response.text)
```

### Slack/Telegram Compatibility

The contract is designed to support Slack and Telegram patterns:

**Slack-specific facts:**
- `thread_ts`: Thread timestamp for reply chains
- `channel_type`: channel, group, im
- `mention_format`: `<@USER_ID>` mention syntax

**Telegram-specific facts:**
- `chat_type`: private, group, supergroup, channel
- `is_command`: Message starts with /
- `reply_to_message`: Reply chain reference

Platform-specific facts go in `platform_flags` dictionary while common
facts use standardized fields.

### Migration Path

The contract is additive and non-breaking:

- Existing Discord adapter continues to work unchanged
- New adapters use the contract for consistency
- Legacy adapters can migrate incrementally
- Both paths call the same runtime methods

See `core/interfaces.py` for the complete contract definition and
`tests/unit/core/test_adapter_contract.py` for contract shape verification.

Discord status for this contract:

- slash chat response generation is runtime-native
- maintained Discord chat can now attach to a provided runtime or `RuntimeHost`
  instead of always creating its own runtime locally
- on-message response generation now also routes through the runtime-native chat
  path
- on-message trigger parsing is still adapter-owned, but it is now normalized
  into one maintained fact payload before response and persona selection route
  through a runtime-owned decision helper
- runtime now owns recent-conversation and auto-reply response gating for the
  maintained Discord path
- optional legacy chat initialization no longer blocks maintained runtime chat
  startup
