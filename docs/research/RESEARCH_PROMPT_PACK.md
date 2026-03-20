# Gestalt Research Prompt Pack

**Last Updated**: 2026-03-20

## Purpose

This document splits Gestalt research into smaller prompt slices so multiple
researchers or models can work in parallel without one overloaded mega-prompt.

Use these prompts independently, then synthesize the outputs into one
architecture decision pass.

## Shared Context Block

Use this context block at the top of every prompt:

```text
Gestalt is a runtime-first personal agent framework.

Primary repository:
- https://github.com/joshhmann/acore_bot

Use the repository as grounding context for current architecture and existing
implementation direction when useful, but do not turn this task into a full
repo audit unless explicitly asked. The main goal is external research and
pattern synthesis to guide what Gestalt should implement next.

Core principles:
- the runtime is the central authority
- adapters and surfaces are thin clients over the runtime
- the runtime owns sessions, memory, provider/model routing, tool policy,
  traces, autonomy/action policy, and persona/session state
- surfaces include CLI, web UI, Discord, and future adapters like Slack,
  Telegram, and other environment bridges
- long-term direction includes user adaptation, memory/learning, bounded
  autonomy, proactive assistance, and future browser-based VRM/avatar
  embodiment

We want realistic, implementable patterns.
We do not want hype demos, vague “agent” claims, or architectures where UI or
adapters become second runtimes.

Prioritize:
- researching external implementation patterns, architecture methods, and
  serious prior art
- grounding recommendations against Gestalt’s current direction

Do not prioritize:
- producing a generic repo walkthrough
- cataloging every file unless it directly helps architecture recommendations
- reviewing legacy code for its own sake

When evaluating external projects, explicitly call out:
- what is actually useful
- what is just polish or demo behavior
- what conflicts with a runtime-first architecture
- what is near-term vs long-term vs speculative
```

## Prompt 1: Runtime Architecture

```text
Using the shared Gestalt context above, produce a deep research brief on
runtime-centered agent architecture.

Focus on:
- canonical runtime/core orchestrator patterns
- runtime lifecycle and shutdown ownership
- session ownership and state boundaries
- provider abstraction and routing
- tool execution systems
- command/action routing
- trace and introspection models
- standalone runtime hosting
- multi-surface consistency across CLI, web, Discord, and future adapters

Research relevant examples from serious systems, official docs, and strong
open-source projects. Include Kimi CLI, OpenAI docs, Anthropic docs, ElizaOS,
Project Airi, and any other relevant systems.

Deliver:
1. Executive summary
2. Recommended runtime architecture patterns for Gestalt
3. Anti-patterns to avoid
4. What belongs in runtime vs adapters vs web UI
5. Comparison of external systems
6. 5-10 prioritized implementation recommendations

Be direct and concrete. Include example module/layer breakdowns and interface
ideas where useful.
```

## Prompt 2: Memory, Context, and Learning

```text
Using the shared Gestalt context above, produce a deep research brief on
memory, context, caching, and learning architecture for Gestalt.

Focus on:
- short-term memory
- recent-turn context
- summaries and recaps
- episodic memory
- semantic fact memory
- preference memory
- procedural/workflow memory
- retrieval and ranking
- context compaction
- prompt assembly
- stable-prefix prompt caching
- provider-native caching where available
- memory invalidation and revision strategies
- user adaptation over time
- recurring task and automation memory
- learning from outcomes without making magical claims

Research patterns from official docs and serious systems. Include OpenAI prompt
caching, Anthropic prompt caching, Kimi CLI if relevant, ElizaOS if relevant,
Project Airi if relevant, and any strong memory-oriented systems or papers.

Deliver:
1. Executive summary
2. Recommended memory model for Gestalt
3. Recommended prompt assembly and cache model
4. Recommended user-adaptation model
5. Data model ideas and schema suggestions
6. Anti-patterns and failure modes
7. 5-10 prioritized implementation recommendations

Where useful, include pseudo-code, cache key examples, invalidation rules, and
operator-facing inspection patterns.
```

## Prompt 3: Autonomy, Action, and Safe Execution

```text
Using the shared Gestalt context above, produce a deep research brief on
bounded autonomy, action systems, and safe execution design.

Focus on:
- tool calling patterns
- bounded retries and reflection loops
- task continuation
- proactive checks and monitoring
- approval flows
- action logs and reversibility
- policy gating
- failure recovery
- long-running tasks
- multi-step task execution
- operator intervention and interruption
- learning from action outcomes

Research how strong systems make autonomous behavior useful without making it
reckless. Include official platform patterns where relevant, plus Kimi CLI,
ElizaOS, Project Airi, and other serious systems if they are useful.

Deliver:
1. Executive summary
2. Recommended autonomy model for Gestalt
3. Recommended approval and control model
4. Recommended action/outcome data model
5. Anti-patterns to avoid
6. What should live in runtime vs UI vs adapter
7. 5-10 prioritized implementation recommendations

Optimize for practical runtime design, not hype.
```

## Prompt 4: Adapter SDK and Surface Contracts

```text
Using the shared Gestalt context above, produce a deep research brief on
adapter contracts and multi-surface integration patterns.

Focus on:
- thin adapter contract design
- normalized event/fact models
- response rendering models
- transport hygiene vs runtime policy ownership
- persona and session context flow
- API versioning and compatibility
- integration patterns for web, CLI, Discord, Slack, Telegram, and future
  environment/game bridges
- how to support adapter quirks without adapter-local intelligence drift

Research strong examples from official docs and serious systems, including Kimi
CLI, ElizaOS, Project Airi, MCP-related systems, and any clean runtime/client
architectures.

Deliver:
1. Executive summary
2. Recommended adapter contract for Gestalt
3. Recommended event and response schemas
4. Versioning/governance guidance
5. Anti-patterns to avoid
6. External comparison notes
7. 5-10 prioritized implementation recommendations

Be explicit about what adapters should never own.
```

## Prompt 5: Web Operator Surface

```text
Using the shared Gestalt context above, produce a deep research brief on the
web UI as Gestalt’s primary operator surface.

Focus on:
- runtime status dashboards
- session inspection
- memory/context inspection and editing
- traces and event history
- tool activity views
- approval queues
- proactive/autonomous workflow visibility
- multi-agent or task orchestration views
- debugging and ops controls
- operator information hierarchy
- what should be default vs advanced

Research strong operator UX patterns from agent systems, developer tools,
runtime consoles, and any serious web-based operator surfaces.

Deliver:
1. Executive summary
2. Recommended web operator model for Gestalt
3. Recommended information hierarchy
4. Recommended panels/endpoints/views
5. Anti-patterns to avoid
6. External comparison notes
7. 5-10 prioritized implementation recommendations

Optimize for a useful operator cockpit, not flashy UI.
```

## Prompt 6: Security and Trust Boundaries

```text
Using the shared Gestalt context above, produce a deep research brief on
security, trust boundaries, and safe deployment architecture for Gestalt.

Focus on:
- provider secret handling
- auth and admin boundaries
- runtime vs adapter trust boundaries
- tool risk tiers
- command authorization
- approval flows
- sandboxing
- MCP and connector safety
- audit logging
- user, identity, and session isolation
- prompt injection risk
- data exfiltration risk
- autonomous action safeguards
- what must be designed early vs later

Research realistic production-minded security patterns. Include official docs,
serious systems, and relevant security guidance where applicable.

Deliver:
1. Executive summary
2. Recommended security architecture for Gestalt
3. Threat model categories
4. Defense-in-depth recommendations
5. Anti-patterns to avoid
6. Release blockers vs later hardening items
7. 5-10 prioritized implementation recommendations

Be concrete. Avoid generic “use auth” advice.
```

## Prompt 7: Embodiment, VRM, and Environment Bridges

```text
Using the shared Gestalt context above, produce a deep research brief on future
embodiment, VRM/browser presence, scene interaction, and bounded environment
bridges.

Focus on:
- browser-based avatar systems
- VRM/VRMA pipelines
- runtime-driven expression, action, and presence protocols
- authored scenes
- bounded scene and action vocabularies
- game/digital-environment bridges
- learning in bounded environments
- how embodied behavior should be driven by runtime state, memory, and policy
- what should live in runtime vs client/presence layer

Include review of systems like Project Airi and any other embodiment or avatar
systems that are relevant. Compare them critically against Gestalt’s
runtime-first architecture.

Deliver:
1. Executive summary
2. Recommended embodiment direction for Gestalt
3. Recommended runtime/client boundary for VRM and presence
4. Recommended protocol/event ideas
5. Recommended staged roadmap: near-term, mid-term, long-term
6. Anti-patterns to avoid
7. 5-10 prioritized implementation recommendations

Keep this future-facing but realistic. Do not collapse embodiment into the
runtime core.
```

## Prompt 8: Comparative Review

```text
Using the shared Gestalt context above, produce a comparative review of
external systems and sources relevant to Gestalt.

You must include:
- OpenAI official docs
- Anthropic official docs
- Kimi CLI
- ElizaOS
- Project Airi
- MCP ecosystem references

You may include other serious systems if relevant.

For each system or source, evaluate:
- what it does well
- what it does poorly for Gestalt’s goals
- what patterns are worth borrowing
- what would be a mistake to copy
- what is architecture vs just UI polish
- what appears mature vs experimental

Deliver:
1. Comparative matrix
2. Strongest patterns worth borrowing
3. Strongest anti-patterns to avoid
4. Near-term recommendations for Gestalt
5. Long-term ideas worth tracking

Be opinionated and architecture-focused.
```

## Synthesis Prompt

Use this after you have multiple research outputs:

```text
Synthesize the attached research reports into one decision-oriented architecture
brief for Gestalt.

Tasks:
1. identify where the reports agree
2. identify contradictions
3. separate near-term implementation from long-term R&D
4. reject recommendations that conflict with a runtime-first architecture
5. produce one unified set of recommendations
6. map those recommendations into concrete next-phase implementation slices

Output:
- executive summary
- consensus findings
- conflicts and how to resolve them
- final recommended architecture direction
- top 10 implementation priorities
- what to defer
- anti-patterns to explicitly avoid

Optimize for action, not completeness.
```
