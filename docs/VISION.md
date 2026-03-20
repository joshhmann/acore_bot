# Gestalt Vision

**Last Updated**: 2026-03-10

## Summary

Gestalt is a personal runtime-first agentic framework.

It is designed to be:

- an assistant
- a multi-persona character system
- an autonomous action-taking runtime
- a learning system with memory
- a framework that can expand through providers, tools, MCP, voice, and future embodiment

The product is not a single UI. The product is the runtime and its governed capability surface.

## Gestalt v1 vs Current Vision

`Gestalt v1` established the right base:

- normalized runtime events
- platform-agnostic orchestration
- provider routing
- tool policy and MCP
- memory isolation
- runtime-owned command handling

That was the correct foundation.

But `Gestalt v1` was still too narrow compared to the actual intended framework.

The canonical current layer and phase model now lives in:

- `docs/ARCHITECTURE.md`

### Gestalt v1 Was

- a runtime-first architecture
- a safer command/tool system
- a multi-surface execution model
- an incremental migration path away from legacy Discord/service logic

### The Real Gestalt Vision Is Larger

Gestalt should become:

- a runtime-first agentic framework for personal use
- multi-persona by design
- able to assist, remember, plan, act, and learn
- able to adapt to a specific user over time through memory, feedback, and repeated interaction
- able to operate across CLI, web, and Discord
- extensible through MCP and multiple model/voice providers
- eventually embodied through browser-based VRM/scene interaction
- eventually capable of improving itself through bounded self-development workflows

So:

- `Gestalt v1` = architecture foundation
- `Gestalt vision` = full framework direction

## Core Identity

Gestalt is a framework for a characterized intelligence that can:

- talk
- remember
- decide
- use tools
- call external systems
- learn from outcomes
- express itself through multiple personas

That means the framework must support:

- multi-persona behavior
- memory and recall
- user adaptation and personalization
- autonomy and planning
- tool use and action
- provider flexibility
- media I/O
- workflow and skill development over time
- learning systems
- future embodiment

## Primary Pillars

### 1. Runtime Authority

The runtime is the authority for:

- sessions
- commands
- provider/model routing
- tool selection and execution
- memory updates
- autonomy
- traces
- policy

No surface should become a second runtime.

### 2. Multi-Persona

Gestalt is not just “one assistant with skins.”

Multi-persona is core:

- distinct personas
- persona switching
- persona-specific style/model/provider preferences
- persona-local and shared memory decisions
- future persona collaboration and delegation

### 3. Memory and Learning

Gestalt should learn over time.

That includes:

- short-term conversational memory
- long-term episodic memory
- user and environment preferences
- adaptation to the user's language, tone, and interaction style
- recap and summarization
- successful action trajectory memory
- recurring workflow and automation memory
- later skill/procedural memory

Learning should start with explicit memory and feedback, not magic claims.

### 4. Action and Autonomy

Gestalt should be able to:

- use tools
- interact with MCP servers
- continue bounded work
- reflect and retry
- act proactively for the user
- automate recurring tasks and checks when the user wants that behavior

Autonomy should remain:

- bounded
- inspectable
- policy-gated
- reversible where practical

### 5. Extensibility

Gestalt should support many backends and integrations:

- multiple LLM providers
- embeddings/rerankers
- TTS
- STT
- MCP servers
- connectors like Home Assistant and other apps
- bounded environment bridges for digital worlds, simulations, and game-like systems

MCP is not peripheral. It is one of the main extensibility mechanisms.

### 6. Embodiment

Embodiment is a real long-term direction, but not current platform truth.

The right path is:

- browser-based presence first
- VRM avatar support
- VRMA motion support
- authored scenes
- bounded action vocabularies
- runtime-driven expression, action, and presence outputs
- later scene learning and RL-style training

Embodiment should be built on the runtime, not beside it.

## Canonical Product Surface Today

These define the current Gestalt product:

- `core/runtime.py`
- `core/commands.py`
- `providers/*`
- `tools/*`
- `mcp_client/*`
- `memory/*`
- `adapters/cli/*`
- `adapters/tui/*`
- `adapters/web/*`
- `adapters/discord/discord_bot.py`
- `adapters/discord/commands/runtime_chat.py`
- `adapters/discord/commands/help.py`
- `adapters/discord/commands/system.py`
- `adapters/discord/commands/social.py`
- `adapters/discord/commands/profile.py`
- `adapters/discord/commands/search.py`

These are secondary or experimental until cleaned up:

- `adapters/desktop/*`
- `core/agentic/*`
- `services/*`
- `cogs/*`
- large historical docs and planning artifacts

## Product Surfaces

### CLI / TUI

Primary operator and development surface.

Use for:

- command execution
- trace visibility
- runtime debugging
- agent operator workflows

### Web UI

Primary long-term interactive surface.

Use for:

- browser-based agent cockpit
- live transcript, trace, and state
- future embodied presence
- future scene systems

### Discord

Social multi-persona surface.

Use for:

- conversation with personas
- multi-user interaction
- personality expression in a social environment

## What Gestalt Is Not

Gestalt is not:

- every subsystem in the repository
- a catch-all bot feature pile
- a game framework first
- a VRM experiment first
- a collection of “completed” plans
- a system whose status is defined by reports instead of tests

## Near-Term Direction

The next real milestones should focus on:

1. runtime stabilization
2. surface consolidation
3. identity, memory, and learning architecture
4. autonomy improvements
5. provider/TTS/STT/MCP ecosystem quality
6. browser embodiment later, on top of a stable runtime

## Long-Term Direction

Long term, Gestalt should support:

- skill learning
- scene interaction
- RL-style embodied training in bounded environments
- bounded environment adapters for learning and action
- app/home automation connectors
- personal agent workflows
- bounded self-improvement and self-development

This should happen through governed runtime contracts, not speculative core sprawl.

## Alignment Rule

A change is aligned if it strengthens one or more of these:

- runtime authority
- multi-persona capability
- memory and learning
- autonomy and action
- MCP/provider/media extensibility
- coherent surface quality

A change is misaligned if it:

- adds a major subsystem with no clear owner
- introduces new authority outside runtime
- updates status/docs ahead of reality
- expands experimental scope faster than platform stability
