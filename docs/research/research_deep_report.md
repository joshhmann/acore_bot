# Gestalt Research Synthesis: Runtime-First Personal Agent Framework Architecture

## Executive summary

Gestalt’s own architecture authority already states the “runtime-first” contract clearly: surfaces normalize platform input into shared runtime facts/events, `GestaltRuntime` owns orchestration and policy, and surfaces render runtime outputs; the canonical composition root is `gestalt/runtime_bootstrap.py`, and adapters must not re-own provider/tool/memory/persona policy. citeturn4view0

External prior art strongly supports doubling down on that direction—but with a few specific, implementable upgrades:

A central, long-lived runtime should function like an “agent operating system”: it owns sessions, context assembly, tool execution budgets/approval queues, provider routing, and trace emission, and it exposes a stable event-stream API to thin clients. This matches patterns in (a) Kimi Code CLI’s “Wire mode” JSON‑RPC protocol that decouples UI from agent core while still supporting bidirectional approvals and capability negotiation, citeturn24view1turn24view0 (b) elizaOS’s `AgentRuntime` as the orchestrator that composes state from “providers” before each model call and dispatches actions, citeturn12view0turn35view2 and (c) AutoGen’s explicit “agent runtime environment” concept (standalone vs distributed) that centralizes identity/lifecycle/security boundaries. citeturn15view0

In memory and context, the strongest practical architecture is tiered: fast short-term conversational state + structured long-term memory types (facts/preferences/episodes/procedures) + retrieval on demand, with explicit revision and invalidation rules. This is consistent with MemGPT’s “hierarchical memory tiers” framing, citeturn19search3 Letta’s separation of editable “memory blocks” vs semantically searchable “archival memory,” citeturn19search1turn19search2 and elizaOS’s explicit memory-type taxonomy (messages/facts/documents/relationships/goals/tasks/actions) in runtime-owned memory APIs. citeturn35view3turn35view0

For tools and autonomy, the consistent lesson is: useful autonomy requires hard bounds, explicit approval gating for risky operations, and first-class observability. Kimi’s persisted approval decisions and explicit YOLO (auto-approve) mode—with strong warnings—are a concrete pattern to borrow, citeturn24view0turn29search10turn29search6 while OpenAI’s and Anthropic’s ecosystems converge on: schema-defined tool calling, deferred tool loading (“tool search”), and “human-in-the-loop” approvals for MCP/connectors. citeturn8view1turn10view2turn7search14turn34view2

Security-wise, the biggest architectural risk is letting untrusted content (web pages, tool outputs, MCP tool descriptions) flow “up” into privileged runtime decisions without structured filtering. MCP’s own specification explicitly warns that tool safety requires consent and that even tool annotations/descriptions should be considered untrusted unless from a trusted server—pushing Gestalt toward defense-in-depth control planes, not adapter-local hacks. citeturn17view0turn21view2turn21view1

## Runtime-centered architecture patterns Gestalt should standardize

### Runtime lifecycle, hosting, and shutdown ownership

Gestalt’s repo-level architecture authority already identifies a “canonical startup” via `launcher.py` → `gestalt/runtime_bootstrap.create_runtime_host()` and frames `RuntimeHost` as the shared lifecycle owner across surfaces. citeturn4view0 The direction to “finish launcher/runtime-host ownership cleanup” and reduce hybrid seams (especially in Discord) is consistent with what mature agent shells do: a single orchestrator/host constructs the runtime once, then attaches multiple IO frontends. citeturn4view0turn13view0turn24view1

A practical pattern (mirroring Kimi CLI’s layering) is:

- **RuntimeHost** (process lifecycle): owns startup/shutdown, config loading/reload, persistence initialization, and surface registration; surfaces are hot-pluggable streams over a single runtime. citeturn4view0turn13view0turn24view1  
- **GestaltRuntime** (orchestrator): owns session state, command handling, provider selection/routing, tool policy and budgets, memory coordination, trace emission, and persona/social state. citeturn4view0turn12view0turn35view2  
- **Subsystems** (runtime-owned dependencies): providers/*, tools/*, memory/*, mcp_client/*, and any plugin modules remain libraries invoked by runtime policy, not standalone “mini apps.” citeturn4view0turn10view1  
- **Surfaces/adapters**: CLI/web/Discord/Slack/etc translate platform events to runtime events and render runtime outputs, without re-owning orchestration or policy. citeturn4view0turn24view1turn3view3  

This aligns with AutoGen’s explicit positioning: a runtime environment “facilitates communication between agents, manages identities and lifecycles, and enforces security and privacy boundaries,” and can be implemented as a standalone runtime or distributed runtime with a host + workers. citeturn15view0

### Session ownership, state boundaries, and consistency across surfaces

OpenAI’s conversation-state guidance provides two useful mental models that map cleanly to a runtime-first design:

- A durable **Conversation object** with a durable identifier that can store “items” (messages, tool calls, tool outputs, etc.) and be reused across sessions/devices/jobs. citeturn26view0  
- A lighter-weight “chain via `previous_response_id`” approach, useful for threading but still implying there is a canonical state store somewhere (your runtime, if you want portability). citeturn26view0turn25search4  

Kimi CLI’s session design makes the runtime-owned approach explicit: resuming a session restores not just chat history but runtime state like approval decisions, plan-mode state, dynamically created subagents, and additional workspace directories. citeturn24view0turn29search13

**Gestalt pattern recommendation:** define a single **Session** object in runtime with:

- `session_id` (stable), `surface_refs` (connections), `persona_state`, `policy_state` (budgets/allowlists), `memory_pointers` (what’s pinned), `context_compaction_state`, and `trace_root_id`.
- A strict boundary: adapters may propose session metadata, but runtime decides what is persisted and what is ephemeral.

This is also consistent with elizaOS: `AgentRuntime` owns identity, plugin/service lifecycles, context composition, routing, and action dispatch. citeturn12view0

### Provider abstraction and routing

Kimi CLI is a strong example of a production-minded provider abstraction: its config explicitly supports provider “types” including OpenAI (legacy + Responses), Anthropic, Gemini, and others, and persists configuration in a standard location. citeturn32view1turn32view0 More importantly, Kimi’s “Kosong” library explicitly positions itself as an abstraction layer that unifies message structures and asynchronous tool orchestration across providers to avoid lock-in. citeturn32view2

Gestalt already aspires to provider routing in runtime ownership. citeturn4view0 To make it realistic and maintainable:

- Separate **Provider API adapters** (OpenAI/Anthropic/local) from **Routing policy** (budget, latency, capability).
- Route on **capabilities**, not brand names. Both Kimi and OpenAI docs emphasize model capabilities (context limits, tool support like tool_search) affecting orchestration decisions. citeturn14search13turn8view2

### Tool execution systems, command/action routing, and introspection

Tool-calling ecosystems converge on a “multi-step conversation” pattern: models emit tool calls, the application executes them, then returns tool outputs, possibly repeating until completion. citeturn8view1turn9view2 For UI automation, OpenAI’s “computer use” explicitly defines a loop: run every action in `actions[]`, send back `computer_call_output`, repeat until no `computer_call`. citeturn8view3

Two key scalability patterns matter for Gestalt:

Deferred tool loading and tool search: OpenAI supports `tool_search` (gpt-5.4+) plus `defer_loading` to avoid loading the entire tool universe; citeturn8view2turn10view2 Anthropic supports dedicated tool-search tools and MCP defer-loading patterns. citeturn7search14turn7search5 This is essential if Gestalt intends to grow a large tool catalog or attach multiple MCP servers.

State composition and caching: elizaOS’s “providers” pattern is a robust answer to “how do we assemble context consistently?” Providers return structured `data`, templating `values`, and a preformatted `text` segment, and the runtime can cache composed state based on message+provider set to avoid redundant work. citeturn35view2

**Gesture-level recommendation:** treat “commands” (human/operator intents like `/debug`, `/approve`, `!reload`) as first-class runtime actions distinct from “tools” (capability calls), but route both through the same trace/event pipeline so every surface can render/inspect them.

### Trace and introspection models

OpenAI’s Agents SDK provides a clean conceptual model: traces are end-to-end workflow records composed of spans for agent runs, generations, function tool calls, guardrails, and handoffs; traces can be grouped by a `group_id` (e.g., conversation thread). citeturn34view1turn26view3 This maps to standard OpenTelemetry concepts: traces are the path of a request through a system, composed of spans representing timed work units. citeturn18search2

Gestalt should treat “trace emission” as runtime-owned (your architecture doc already says so). citeturn4view0 The immediate implementable pattern is:

- An append-only event stream per session (`TraceEvent`), then optional projection into spans for UI and downstream observability.
- A consistent event taxonomy: `llm.request`, `llm.response`, `tool.call`, `tool.result`, `approval.request`, `approval.response`, `memory.write`, `memory.patch`, `policy.tripwire`, `adapter.ingress`, `adapter.egress`.

## Memory, context, and caching architecture

### Recommended memory model for Gestalt

A practical, runtime-owned memory model should combine:

Short-term conversational state: keep the last N turns + “recent summary” and allow compaction. Kimi’s sessions explicitly support `/compact` to summarize and replace context, and they automatically compress context when needed. citeturn24view0 OpenAI’s ecosystem similarly treats compaction as a first-class primitive (server-side compaction and an explicit `/responses/compact` endpoint). citeturn28view1turn25search12

Typed long-term memory: elizaOS explicitly treats “every piece of information an agent processes” as a Memory object with identity and contextual fields (entityId, roomId, agentId, etc.), and enumerates memory types like messages, facts, documents, relationships, goals, tasks, and action records. citeturn35view0turn35view3 This is close to what Gestalt needs for a runtime-first system: adapters should not embed “memory logic”; they should just report events and render outputs.

Hierarchical memory tiers: MemGPT provides a helpful design lens—move information between fast/slow memory tiers and use interrupts/control flow to manage limited context windows. citeturn19search3 Letta’s current productization makes this concrete: editable “memory blocks” (agent edits via dedicated memory tools) and “archival memory” as a vector DB queried on demand. citeturn19search1turn19search2

Procedural and “automation memory”: Kimi’s “Agent Skills” show a very implementable approach: a skill is a directory with `SKILL.md`; the system prompt includes skill name/path/description, and the model decides when to read the full playbook. citeturn32view3turn28view1 This is a clean way to store procedures without overloading the runtime core with bespoke “planner intelligence.”

**Concrete Gestalt memory types to standardize now:**
- `ShortTermTurn`: the canonical message history for the session.
- `Episode`: a summarized multi-turn chunk with timestamps + participants + “what was decided.”
- `Fact`: semantic assertions scoped to user/persona/session/world; includes confidence and provenance.
- `Preference`: stable user preference with versioning and override rules.
- `Procedure`: versioned workflow snippets (skills/playbooks) plus “last used” and success metrics.
- `ActionRecord`: tool/action executions with inputs/outputs/outcome (success, failure, partial, rollback pointer).

### Prompt assembly and cache model

Provider-native prompt caching has real cost/latency implications and should influence Gestalt’s prompt assembly shapes:

OpenAI prompt caching: works on exact prefix matches; developers should place static content at the beginning and variable/user-specific content at the end; caching is enabled automatically for prompts ≥1024 tokens; retention is typically minutes in-memory with an extended retention option up to 24 hours on supported models; and a `prompt_cache_key` can influence routing to improve hit rate. citeturn8view0

Anthropic prompt caching: enabled via `cache_control` (automatic or explicit breakpoints); caches KV representations and cryptographic hashes rather than raw prompt/response text; default cache lifetime is 5 minutes (with an optional 1-hour cache at additional cost); and automatic caching moves the cache point forward as multi-turn conversations grow. citeturn9view0

**Gestalt prompt assembly implication:** keep a stable, deterministic “prefix” segment and isolate volatile segments. A practical internal representation:

```text
Prompt = [
  Prefix(system/persona + immutable policy + stable skill manifests),
  SessionPinned(memory blocks / user profile / long-lived facts),
  RecentWindow(last N turns),
  RetrievedContext(top-K episodic/fact/doc results),
  TurnSpecific(user input + adapter facts + tool outputs)
]
```

Then provide provider-specific “cache hints”:
- For OpenAI: keep Prefix and SessionPinned stable; optionally pass `prompt_cache_key` keyed by (persona_id, user_id, policy_version). citeturn8view0  
- For Anthropic: map Prefix and expensive tool results to explicit `cache_control` breakpoints and rely on automatic caching for the moving conversation window. citeturn9view0turn9view1  

### Memory invalidation and revision strategies

The hardest production problem is not “storing memory,” but changing it safely. Treat long-term memory as **revisioned**:

- All long-term memory writes produce a new revision with provenance (source turn/tool) and “supersedes” pointer.
- Allow operator edits that generate patch revisions (don’t mutate silently).
- For “facts” and “preferences,” define conflict resolution: last-write-wins only for low-stakes preferences, but require confirmation or multi-signal evidence for critical facts.

This aligns with the OWASP prompt injection warning that attackers can use indirect prompt injection to cause “persistent manipulation across sessions” if systems store untrusted instructions as memory. citeturn21view1 It also aligns with MCP security guidance emphasizing tool poisoning and “rug pull” attacks where definitions change after approval—suggesting you should pin trust and provenance, not treat tool outputs as truth. citeturn21view2turn17view0

## Autonomy, action systems, and safe execution

### Bounded autonomy model

A runtime-first agent should treat autonomy as a set of runtime-managed “loops,” each with explicit ceilings:

- **Per-turn tool-call loop**: OpenAI function calling explicitly describes repeated tool calling until completion; citeturn8view1 Anthropic’s server-side tool loop has a default limit of 10 iterations and returns `stop_reason="pause_turn"` when exhausted, requiring the client to continue the conversation. citeturn9view2  
- **UI automation loop**: OpenAI computer use requires executing all returned UI actions in order and iterating with screenshot feedback. citeturn8view3  
- **Long-horizon tasks**: OpenAI “background mode” allows long-running tasks asynchronously with polling; it stores response data for ~10 minutes and is not ZDR compatible. citeturn28view0  
- **Local agent loop limits**: Kimi CLI explicitly uses loop limits (max steps, bounded retries) to prevent runaway behavior and returns explicit statuses like “max_steps_reached” in its Wire protocol. citeturn27search2turn24view1  

**Implementable Gestalt rule:** every loop must have a budget struct (`max_steps`, `max_tool_calls`, `max_cost_usd`, `max_wall_time`, `max_tokens_in/out`) and every loop emits budget events into traces.

### Approval flows and operator control

Kimi provides one of the clearest “operator-control” designs to borrow:

- Sessions persist approval decisions (including YOLO mode status and “allow for this session” approvals). citeturn24view0turn29search0  
- YOLO mode is explicitly dangerous and visible (badge); it auto-approves everything. citeturn29search10turn29search6  
- Print mode is non-interactive and implicitly enables auto-approval (important as an anti-pattern warning for production). citeturn29search17  

OpenAI’s current safety guidance for agent workflows is similarly direct: keep tool approvals on (especially for MCP tools), use guardrails, and design workflows so untrusted data never directly drives behavior. citeturn34view2turn21view1

**Gestalt actionable design:** treat approval as a runtime-owned queue:

- Tools are assigned a risk tier (`read_low`, `write_low`, `write_high`, `external_money`, `external_auth`, `filesystem`, `process_exec`, etc.).
- Runtime policy decides `require_approval` and emits an `approval.request` event.
- Adapters render approval UI but cannot bypass policy except via explicit operator actions.

This aligns with OpenAI’s MCP tooling: remote MCP tools can be “allowed automatically or restricted with explicit approval required.” citeturn26view1turn10view1

### Action/outcome data model and reversibility

To make autonomy safe and debuggable, treat every effectful operation as an **action record**:

- Include inputs (normalized and validated), outputs, side effects, and an optional rollback plan.
- Store “intent vs outcome” and operator approvals as linked events.

This mirrors elizaOS’s explicit `ACTION` memory type notion and its broader memory taxonomy (actions/tasks/goals) that can be persisted. citeturn35view3 It also directly supports trace grading and eval-driven improvement loops: OpenAI defines trace grading as labeling decisions/tool calls/reasoning steps to assess where the agent performed well or made mistakes. citeturn26view3turn34view2

### Anti-patterns to avoid in autonomy

Do not implement “reckless reflection loops” that retry indefinitely or until the model “feels done.” Kimi’s explicit max-step controls exist specifically to prevent infinite loops and runaway resource use; citeturn27search2turn24view1 Anthropic similarly hard-limits server tool loops and requires explicit continuation when hitting `pause_turn`. citeturn9view2

Avoid “invisible autonomy” (tool calls happening without a traceable audit trail or operator visibility). OpenAI’s Agents SDK tracing is explicitly designed to capture LLM generations, tool calls, handoffs, guardrails, and custom events for debugging/monitoring. citeturn34view1turn26view3

## Adapter contracts, surface SDK, and web operator cockpit

### Thin adapter contract

Kimi’s Wire mode is the clearest “thin client” exemplar for Gestalt:

- Bidirectional JSON‑RPC over stdin/stdout, explicitly intended to let external programs build custom UIs or embed the agent core. citeturn24view1turn24view0  
- Optional `initialize` handshake with protocol version negotiation, capability discovery, and registration of external tool definitions. citeturn24view1  
- A `prompt` request runs an agent turn while emitting `event` notifications and interactive `request` messages (e.g., approvals) during execution, returning only when the turn completes. citeturn24view1  

Gestalt’s architecture doc already outlines the equivalent: surfaces normalize into shared runtime events/facts, call runtime, and render runtime outputs; adapters may compute platform facts but may not own provider/tool/persona/memory/response policy. citeturn4view0turn3view3

**Recommended Gestalt adapter SDK contract (conceptual):**
- `RuntimeIngressEvent`: `{session_ref, actor_ref, timestamp, kind, payload, attachments, adapter_facts}`
- `RuntimeEgressEvent`: `{session_id, trace_id, kind, payload, render_hints, requires_response?}`
- `AdapterCapabilities`: streaming support, rich rendering support, approval UI support, file upload support.
- `ProtocolVersion`: semantic + feature flags.

### Normalized event and response schemas

Borrow elizaOS’s “provider/state” discipline for the runtime-facing data model: providers feed structured data into a state object before model calls, and providers can be dynamic vs always included. citeturn35view2 In Gestalt terms: adapters should emit platform facts (“message came from Discord channel X, user Y”), but runtime consolidates memory/user/persona/tool availability into the state.

**Avoid adapter-local “intelligence drift”:** Project AIRI is a cautionary example: its architecture includes significant orchestration and chat management in shared UI stores (e.g., “chat orchestrator store”), which risks turning the UI into a second runtime and complicates multi-surface consistency. citeturn22view1 Gestalt explicitly does not want this. citeturn4view0

### Web operator surface as a cockpit

ElizaOS positions itself as runtime + modular architecture plus a “modern web UI” dashboard for management. citeturn2view2 OpenAI similarly treats “Traces” as a first-class operator console in the dashboard for inspecting workflows and then running graders/evals. citeturn26view3turn34view1 Kimi provides a practical UX model even in terminal form: status bars show context usage, sessions can be resumed and replayed, and `/export` produces an auditable transcript. citeturn24view0

**Recommended operator information hierarchy:**

Default view should answer: “What is running, what is it doing, what needs my approval, and what changed?”

- Runtime status: active surfaces, provider health, queue depth, cost/token burn (per session + global).
- Session list: recent activity, stuck sessions (budget hit, repeated failures), and “awaiting approval.”
- Trace viewer: timeline of events with filtering by tool calls, policy tripwires, and memory writes.
- Approval queue: diff-friendly rendering of proposed actions, risk tier, and “why the model wants this.”
- Memory inspector/editor: show pinned memory vs retrieved items, provenance, and revision history.
- Policy dashboard: tool risk tiers, allowlists, budgets, and “break glass” overrides (audited).

Advanced view can add: prompt assembly preview (with cache segmentation), provider routing rationale, embedding/RAG debug (top‑K candidates, ranks), and guardrail outputs.

## Security and trust boundaries

### Threat model categories that materially affect architecture

Prompt injection: OWASP describes prompt injection as a vulnerability where malicious input manipulates model behavior; impacts include unauthorized actions via connected tools/APIs and persistent manipulation across sessions. citeturn21view1 This is a runtime architecture problem: if adapters or tools write untrusted instructions into “memory” or “system prompt,” you have a persistence vulnerability.

MCP-specific risks: OWASP’s MCP Security cheat sheet highlights new attack surfaces: tool poisoning via descriptions/schemas/return values, rug pulls (tool definitions change after approval), tool shadowing/cross-origin escalation, confused deputy problems, data exfiltration via legitimate channels, and over-scoped tokens. citeturn21view2turn17view0

Untrusted UI content: OpenAI’s computer-use guidance recommends isolating the browser/container, using allowlists, and keeping a human in the loop for purchases/authenticated/destructive actions or anything hard to reverse. citeturn8view3

Remote MCP servers and connectors: OpenAI emphasizes that remote MCP servers can be any public server implementing MCP and that connectors/remote MCP tools can be approval-gated; citeturn26view1turn10view1 Anthropic’s MCP connector similarly is beta, supports OAuth, and has limitations (not all MCP features supported), reinforcing that runtime policy must own connector safety. citeturn9view3turn9view2

### Defense-in-depth design Gestalt should implement early

Runtime-owned least privilege: Tokens and provider secrets must live only in runtime; adapters should never have broad credentials. This fits both MCP’s “user consent and control” principle and OWASP’s recommendation for scoped per-server credentials. citeturn17view0turn21view2

Structured input boundaries: OWASP explicitly notes prompt injection is amplified when systems concatenate instructions and user data without clear separation. citeturn21view1 Therefore:
- Treat external content (web fetch results, tool outputs, MCP tool descriptions) as *data*, not *instructions*.
- Extract only structured fields (validated JSON/enums) from untrusted sources before allowing them to drive tool calls—matching OpenAI’s guidance to prevent untrusted data from flowing between nodes. citeturn34view2

Guardrails as runtime policy: OpenAI’s guardrail guidance frames input guardrails and output guardrails as distinct controls; designing guardrails requires explicit evaluation of accuracy/latency/cost tradeoffs. citeturn34view3turn33search0 The Agents SDK adds a useful operational distinction: tool guardrails run on every function-tool call invocation, not just at workflow boundaries. citeturn34view0 Gestalt should implement “tool guardrails” equivalents at the runtime tool runner layer—even if you don’t adopt OpenAI’s SDK.

Tool definition integrity and pinning: MCP security guidance recommends pinning tool definitions using cryptographic hashes and alerting on changes to prevent rug pulls. citeturn21view2turn17view0 This should be implemented in Gestalt’s MCP client layer and surfaced in the web operator UI.

### Release blockers vs later hardening

Release blockers (architecture-level):
- Centralized approval queue with risk tiers (no adapter bypass). citeturn4view0turn34view2  
- Full audit trail (trace + action records + memory write provenance). citeturn26view3turn34view1turn35view3  
- Tool output sanitization + injection-aware prompt assembly rules. citeturn21view1turn8view0turn34view2  
- MCP server trust model: allowlist, per-server creds, tool definition pinning. citeturn21view2turn26view1turn17view0  

Later hardening:
- Full isolation/sandboxing for high-risk tools and CUA harnesses (VM isolation, network microsegmentation), building on OpenAI’s computer-use guidance. citeturn8view3  
- Larger-scale red-teaming and eval automation pipelines (trace graders, regression harnesses). citeturn26view3turn34view2  

## Comparative review and roadmap priorities

### Comparative matrix of key systems

| System | What it does well for Gestalt | What to avoid copying | Maturity signal |
|---|---|---|---|
| OpenAI platform docs (Responses, tools, conversation state, prompt caching) | Clear primitives for state (`conversation` objects vs `previous_response_id`), citeturn26view0turn25search4 tool calling flows, citeturn8view1 deferred tools via `tool_search`, citeturn10view2 remote MCP tool shape and approval gating patterns, citeturn10view1turn26view1 strong caching guidance (prefix stability, retention, `prompt_cache_key`). citeturn8view0 | Provider-specific managed state is convenient, but runtime-first Gestalt should not *depend* on provider state as the canonical truth (portability/multi-provider). citeturn26view0turn4view0 | High: documented APIs + explicit operational guidance (background mode, tracing, safety). citeturn28view0turn26view3turn34view2 |
| Anthropic platform docs (tool use, caching, MCP connector) | Practical caching model (`cache_control`, automatic vs explicit breakpoints, KV+hash storage), citeturn9view0 explicit tool loop limits (`pause_turn`), citeturn9view2 MCP connector patterns (OAuth, multi-server, allow/deny lists) citeturn9view3 and tool-choice control (`auto/any/tool/none`). citeturn9view1 | Don’t rely on beta-only connector behaviors as architecture foundations; treat as optional backends behind your runtime’s own MCP client. citeturn9view3turn4view0 | High: strong official docs; tool + caching patterns clearly operationalized. citeturn9view0turn9view2 |
| Kimi Code CLI | Gold standard for thin-client decoupling (Wire mode JSON‑RPC, handshake/capabilities/external tool defs), citeturn24view1 runtime-owned session persistence including approvals/subagents, citeturn24view0 explicit operator controls (/sessions, /export, /compact), citeturn24view0 and “skills/playbooks” discovery that is compatible across tools. citeturn32view3 | Avoid normalizing YOLO/auto-approval defaults into “production.” Note that print mode auto-approves and is intended for scripting; citeturn29search17 Gestalt should keep “auto-approve” as a deliberate operator setting with audit trails. citeturn29search10turn24view0 | High: extensive docs + stable protocol versioning; multi-surface modes built around a shared core. citeturn24view1turn24view0 |
| elizaOS | Strong runtime-as-orchestrator framing (`AgentRuntime` owns identity/lifecycle/context/action dispatch), citeturn12view0turn2view2 excellent “provider/state composition” pattern with dynamic providers and runtime caching, citeturn35view2 explicit memory taxonomy citeturn35view3 and plugin interface structuring actions/providers/evaluators/services. citeturn35view1turn35view2 | elizaOS’s “everything is a plugin” approach can encourage plugin sprawl and unclear trust boundaries unless carefully governed; don’t copy plugin-first without strict runtime policy ownership. citeturn35view1turn4view0 | Medium-high: active ecosystem + docs; but plugin and multi-agent complexity varies by deployment. citeturn2view2turn35view1 |
| Project AIRI | Great embodiment/product surface inspiration: explicit Live2D + VRM support, multi-platform presence, and game agents; citeturn22view0turn22view1 highlights real challenges (audio pipelines, rendering, environment bridges). citeturn22view1 | AIRI’s architecture includes substantial orchestration in UI/shared client stores (risk of “UI as runtime”). citeturn22view1turn4view0 Gestalt should not copy client-side orchestration patterns if it wants multi-surface consistency and operator-grade runtime authority. citeturn4view0 | Medium: fast-moving, broad scope; good for ideas, not for runtime-first boundary discipline. citeturn22view1turn22view0 |
| MCP ecosystem (spec + security practice) | Crisp host/client/server roles, JSON‑RPC base protocol, stateful connections, and explicit security principles (consent, data privacy, tool safety, sampling controls). citeturn17view0 Security guidance highlights tool poisoning/rug pulls/confused deputy issues that must be handled in host/runtime policy. citeturn21view2turn17view0 | Don’t treat MCP as “just tools.” Tool descriptions/annotations are untrusted, and consent/authorization must be implemented at the host layer. citeturn17view0turn21view2 | High: cross-vendor adoption; now an industry standard integration layer. citeturn17view0turn30view2 |

### Strongest patterns worth borrowing now

The common, high-signal patterns across systems are:

- **Runtime-owned sessions + state** (Kimi session persistence, OpenAI Conversations, elizaOS runtime). citeturn24view0turn26view0turn12view0  
- **UI decoupling via event-stream protocols** (Kimi Wire JSON‑RPC). citeturn24view1  
- **State composition as a formal subsystem** (elizaOS providers returning structured data/values/text; dynamic provider selection; caching). citeturn35view2turn23search0  
- **Deferred tool loading** to keep tool universes scalable (OpenAI `tool_search` + `defer_loading`; Anthropic tool search with MCP defer-loading). citeturn10view2turn7search14  
- **Provider-native caching-aware prompt assembly** (OpenAI prefix caching; Anthropic `cache_control`). citeturn8view0turn9view0  
- **First-class approvals + visible autonomy** (Kimi YOLO + warnings; OpenAI “keep tool approvals on”). citeturn29search10turn34view2turn29search6  
- **Trace-first operations** (OpenAI tracing + trace grading + eval loops; OpenTelemetry model). citeturn34view1turn26view3turn18search2  

### Anti-patterns Gestalt should explicitly avoid

Adapters becoming second runtimes: Project AIRI’s UI-layer orchestration is a concrete caution; avoid “chat orchestrator” intelligence in the web UI or Discord adapter. citeturn22view1turn4view0

Silent persistence of untrusted instructions: OWASP prompt injection warns about persistent manipulation across sessions; storing tool/web content as “memory” without provenance/revision/validation is an architectural vulnerability. citeturn21view1turn21view2

Overloading context with all tools: Anthropic’s MCP efficiency post explains how loading all tool definitions and passing large intermediate results through the context window increases cost/latency and can break workflows; it recommends progressive disclosure and code execution patterns. citeturn30view2

Auto-approval defaults: Kimi’s print mode auto-approves (useful for scripts) but is a dangerous baseline for a personal agent framework unless tightly controlled and audited. citeturn29search17turn24view0

### Prioritized implementation recommendations for Gestalt

These are ordered for near-term architectural leverage while staying faithful to Gestalt’s runtime-first constraints. citeturn4view0

Implement a unified runtime event stream contract (Wire-like) across all surfaces: adopt a versioned protocol that supports (a) capability negotiation, (b) streaming events, (c) interactive requests (approvals/questions), and (d) deterministic “turn completion” statuses (finished/cancelled/max_steps_reached). Kimi Wire provides an implementable template. citeturn24view1turn14search19

Standardize a runtime-owned session object that persists both conversation and policy state (approvals, budgets, dynamic subagents/workflows) across surfaces, similar to Kimi’s session persistence and OpenAI’s “conversation as durable object.” citeturn24view0turn26view0

Adopt elizaOS-style state composition (“providers”) as a first-class runtime subsystem: providers should assemble structured state (`data/values/text`), support dynamic inclusion, and include a short-lived state cache keyed by (message, provider set) to reduce repeated DB/tool calls. citeturn35view2turn23search0

Implement tiered memory with revision semantics: short-term window + episode summaries + typed long-term memories (facts/preferences/procedures/action records) with provenance and edit history; use Letta/MemGPT tier ideas as guidance, not as a magical “learning” claim. citeturn19search3turn19search2turn35view3

Make prompt assembly explicitly caching-aware: keep stable prefixes, isolate volatile suffixes, and add provider-specific caching hints (`prompt_cache_key` for OpenAI; `cache_control` breakpoints for Anthropic). citeturn8view0turn9view0

Build tool scaling primitives early: implement deferred tool loading and “tool search” (both for native tools and MCP tools) to avoid tool-definition bloat; align with OpenAI `tool_search`/`defer_loading` and Anthropic tool-search + MCP defer-loading. citeturn10view2turn7search14

Ship a runtime-owned approval queue with risk tiers and policy gating: model it after Kimi’s approvals/YOLO logic but keep YOLO as an explicit operator setting with bright warnings, and align with OpenAI’s recommendation to keep tool approvals on (especially for MCP). citeturn24view0turn29search10turn34view2

Adopt trace-first observability with an event log that can map to spans: implement a trace model similar to OpenAI Agents SDK (trace_id, group_id/session_id, spans for LLM/tool/guardrails) and optionally export to OpenTelemetry. citeturn34view1turn18search2turn4view0

Harden MCP integrations with definition pinning and per-server credentials: treat MCP tool schemas/descriptions as an injection surface; pin tool definitions/hashes and surface changes to the operator UI; follow MCP’s own “tool safety” and OWASP MCP guidance. citeturn17view0turn21view2turn26view1

For future embodiment, design a runtime→presence protocol that is strictly high-level and bounded: use VRM/VRMA as the client-side avatar standard (VRM is glTF2.0-based and freely usable; VRMA is an explicit animation spec), but keep rendering/animation in the presence layer; runtime sends “intent events” (expression/gesture/speak/scene action) gated by policy and traceable. citeturn36search4turn36search5turn22view0turn4view0