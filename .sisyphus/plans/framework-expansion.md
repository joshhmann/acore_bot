# Framework Expansion: Acore Home AI OS

## TL;DR
> **Quick Summary**: Refactor the monolithic Discord bot into a modular "Home AI OS" framework. Decouple core logic (`services/`) from `discord.py` to enable multiple inputs (CLI, Web, etc.) while preserving 100% of existing Discord functionality.
> 
> **Deliverables**:
> - `core/` package with platform-agnostic types (`AcoreContext`, `AcoreMessage`).
> - Refactored `services/` using Core types.
> - `adapters/discord/` containing all Discord-specific logic (Cogs, Webhooks).
> - `adapters/cli/` proving the architecture works without Discord.
> - `launcher.py` entry point.
> 
> **Estimated Effort**: Large (Architecture Refactor)
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Core Types → Service Refactor → Adapter Migration

---

## Context

### Original Request
Expand `acore_bot` to be a framework (Home AI OS) connecting to Discord, CLI, Home Assistant, etc.

### Interview Summary
**Key Decisions**:
- **Text-First**: Voice features remain in Discord adapter for now.
- **Identity**: Use "Hybrid IDs" (keep Discord IDs as-is for backward compatibility; CLI uses "cli_root"). No DB migration in Phase 1.
- **Orchestration**: Webhook spoofing moves to `DiscordAdapter`. Core just emits "Persona X spoke".
- **MCP**: Bidirectional support (Server + Client).

### Metis Review
**Identified Gaps** (addressed):
- **Identity Migration**: **DECISION**: Defer complex linking. Phase 1 uses existing IDs.
- **Webhook Logic**: **DECISION**: Extracted to `DiscordAdapter`.
- **Scope Creep**: **GUARDRAIL**: No new features. No Web UI yet. No complex message bus.

---

## Work Objectives

### Core Objective
Decouple `services/` from `discord` and establish a "Core vs Adapter" architecture.

### Concrete Deliverables
- `core/types.py`, `core/interfaces.py`, `core/events.py`
- Refactored `BehaviorEngine` (no `discord` imports)
- Refactored `ContextRouter` (no `discord` imports)
- `adapters/discord/` package
- `adapters/cli/` package

### Definition of Done
- [ ] `grep -r "import discord" services/` returns ONLY `services/voice/` (allowed exception).
- [ ] Bot runs on Discord exactly as before (Regression Test).
- [ ] Bot runs on CLI and can chat with personas.

### Must Have
- 100% Backward Compatibility for Discord.
- Clean Interface boundary between Core and Adapters.
- Type-safe abstractions (`AcoreContext` replaces `discord.Context`).

### Must NOT Have (Guardrails)
- NO Database Migration (Schema changes).
- NO New AI Features.
- NO Web Adapter (Phase 2).
- NO Changes to Persona JSON format.

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest).
- **Automated tests**: YES (TDD for Core, Regression for Adapters).
- **Strategy**: 
  1. Unit tests for `core/` (Mock adapters).
  2. Integration tests for `adapters/discord` (using `dpytest` mocks).
  3. Manual-style Agent QA for CLI (stdin/stdout verification).

### QA Policy
Every task MUST include agent-executed QA scenarios.
- **Core**: Unit tests.
- **CLI**: `interactive_bash` (tmux) to send input and verify output.
- **Discord**: `pytest` regression suite.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Core Foundations):
├── Task 1: Core Type Definitions (AcoreMessage, AcoreUser) [deep]
├── Task 2: Adapter Interfaces (Input, Output, EventBus) [deep]
├── Task 3: Discord Adapter Shell (Scaffolding) [quick]
└── Task 4: CLI Adapter Shell (Scaffolding) [quick]

Wave 2 (Service Decoupling - MAX PARALLEL):
├── Task 5: Context Router Refactor (Generic Channel Types) [deep]
├── Task 6: Behavior Engine Abstract Context (Remove Discord types) [deep]
├── Task 7: Orchestrator Migration (Move webhook logic to Adapter) [deep]
└── Task 8: RL Service Decoupling (Abstract feedback signals) [deep]

Wave 3 (Adapter Implementation):
├── Task 9: Discord Input Adapter (Events → Core) [unspecified-high]
├── Task 10: Discord Output Adapter (Core → Webhooks/Embeds) [unspecified-high]
├── Task 11: CLI Input/Output Adapter (stdin/stdout) [quick]
└── Task 12: Cogs Migration (Move commands to Adapter) [unspecified-high]

Wave 4 (Integration & Cleanup):
├── Task 13: Launcher (Unified Entry Point) [quick]
├── Task 14: Dependency Injection Update (Factory refactor) [deep]
├── Task 15: Regression Testing (Discord Parity) [deep]
└── Task 16: Documentation (Architecture.md) [writing]

Wave FINAL (Verification):
├── Task F1: Plan Compliance Audit (oracle)
├── Task F2: Code Quality Review (unspecified-high)
├── Task F3: CLI End-to-End QA (unspecified-high)
└── Task F4: Scope Fidelity Check (deep)
```

### Dependency Matrix
- **1-4**: Independent
- **5**: Depends on 1
- **6**: Depends on 1, 5
- **7**: Depends on 2
- **8**: Depends on 1
- **9-12**: Depends on 2, 6, 7
- **13**: Depends on 9, 11
- **14**: Depends on 13

---

## TODOs

- [x] 1. Core Type Definitions (AcoreMessage, AcoreUser, AcoreChannel)

  **What to do**:
  - Create `core/types.py` with dataclasses for:
    - `AcoreMessage`: text, author_id, channel_id, timestamp, attachments
    - `AcoreUser`: id (str), display_name, metadata dict
    - `AcoreChannel`: id (str), name, type ("text", "dm", "thread")
    - `AcoreContext`: message, channel, user, reply_callback
  - These must be JSON-serializable for MCP compatibility.

  **Must NOT do**:
  - Do NOT import discord anywhere in this file.
  - Do NOT add Discord-specific fields (embeds, reactions) to base types.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None (pure Python dataclasses)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 5, 6, 8

  **References**:
  - `services/memory/context_router.py:63-81` - Discord channel types to abstract.
  - `cogs/chat/message_handler.py` - How messages flow currently.
  - `pydantic` or `dataclasses` - Use stdlib dataclasses for zero deps.

  **Acceptance Criteria**:
  - [ ] File exists: `core/types.py`
  - [ ] `from core.types import AcoreMessage` works without error.
  - [ ] `AcoreMessage` can be instantiated with `text`, `author_id`, `channel_id`.
  - [ ] `AcoreContext` has a `reply(text: str)` method signature.

  **QA Scenarios**:
  ```
  Scenario: Core types instantiate correctly
    Tool: Bash (python)
    Steps:
      1. python -c "from core.types import AcoreMessage, AcoreUser, AcoreContext; print('OK')"
    Expected Result: "OK" (no ImportError)
    Evidence: .sisyphus/evidence/task-1-types-import.txt
  
  Scenario: Message is JSON serializable
    Tool: Bash (python)
    Steps:
      1. python -c "from core.types import AcoreMessage; import json; m=AcoreMessage(text='hi', author_id='123', channel_id='456'); print(json.dumps(m.__dict__))"
    Expected Result: Valid JSON output
    Evidence: .sisyphus/evidence/task-1-json-serializable.txt
  ```

  **Commit**: YES (Group: Wave 1)
  - Message: `feat(core): add platform-agnostic types`

---

- [x] 2. Adapter Interface Definitions

  **What to do**:
  - Create `core/interfaces.py` with abstract base classes:
    - `InputAdapter`: `start()`, `stop()`, `on_event(callback)`
    - `OutputAdapter`: `send(channel_id, text, options)`
    - `EventBus`: `emit(event_type, payload)`, `subscribe(event_type, handler)`
  - Define `AcoreEvent` dataclass (type, payload, source_adapter).

  **Must NOT do**:
  - Do NOT implement concrete adapters here (just interfaces).
  - Do NOT add Discord-specific return types.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None (ABC/Protocol definitions)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 3, 4, 9, 10, 11

  **References**:
  - Python `abc.ABC` and `@abstractmethod` pattern.
  - `typing.Protocol` for structural subtyping (optional).
  - `services/core/factory.py` - How services are created (similar pattern).

  **Acceptance Criteria**:
  - [ ] `core/interfaces.py` defines `InputAdapter` ABC.
  - [ ] `core/interfaces.py` defines `OutputAdapter` ABC.
  - [ ] `InputAdapter` has `async def start(self) -> None`.
  - [ ] `OutputAdapter` has `async def send(self, channel_id: str, text: str) -> None`.

  **QA Scenarios**:
  ```
  Scenario: Interfaces can be imported
    Tool: Bash (python)
    Steps:
      1. python -c "from core.interfaces import InputAdapter, OutputAdapter; print('OK')"
    Expected Result: "OK"
    Evidence: .sisyphus/evidence/task-2-interfaces-import.txt
  ```

  **Commit**: YES (Group: Wave 1)
  - Message: `feat(core): add adapter interfaces`

---

- [x] 3. Discord Adapter Shell

  **What to do**:
  - Create `adapters/discord/__init__.py` and `adapter.py`.
  - Implement `DiscordInputAdapter` skeleton inheriting from `InputAdapter`.
  - Implement `DiscordOutputAdapter` skeleton inheriting from `OutputAdapter`.
  - These should import `discord` freely - this IS the Discord-specific code.

  **Must NOT do**:
  - Do NOT implement full logic yet (just scaffolding).
  - Do NOT move Cogs yet.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 9, 10

  **References**:
  - `main.py` - Current bot initialization.
  - `cogs/chat/main.py` - How cogs are structured.

  **Acceptance Criteria**:
  - [ ] `adapters/discord/adapter.py` exists.
  - [ ] `DiscordInputAdapter` inherits from `InputAdapter`.
  - [ ] Can import without error: `from adapters.discord import DiscordInputAdapter`.

  **QA Scenarios**:
  ```
  Scenario: Discord adapter imports successfully
    Tool: Bash (python)
    Steps:
      1. python -c "from adapters.discord import DiscordInputAdapter; print('OK')"
    Expected Result: "OK"
    Evidence: .sisyphus/evidence/task-3-discord-import.txt
  ```

  **Commit**: YES (Group: Wave 1)
  - Message: `feat(adapters): scaffold discord adapter`

---

- [x] 4. CLI Adapter Shell

  **What to do**:
  - Create `adapters/cli/__init__.py` and `adapter.py`.
  - Implement `CLIInputAdapter` skeleton.
  - Implement `CLIOutputAdapter` skeleton.
  - Plan for stdin/stdout handling.

  **Must NOT do**:
  - Do NOT implement full REPL yet.
  - Do NOT add complex UI (keep it simple).

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 11

  **References**:
  - Python `asyncio` + `aioconsole` or standard `input()` in thread.
  - Look at how `scripts/` interact with the bot for inspiration.

  **Acceptance Criteria**:
  - [ ] `adapters/cli/adapter.py` exists.
  - [ ] `CLIInputAdapter` inherits from `InputAdapter`.
  - [ ] Can import without error.

  **QA Scenarios**:
  ```
  Scenario: CLI adapter imports successfully
    Tool: Bash (python)
    Steps:
      1. python -c "from adapters.cli import CLIInputAdapter; print('OK')"
    Expected Result: "OK"
    Evidence: .sisyphus/evidence/task-4-cli-import.txt
  ```

  **Commit**: YES (Group: Wave 1)
  - Message: `feat(adapters): scaffold cli adapter`

---

- [x] 5. Context Router Refactor

  **What to do**: Refactor `services/memory/context_router.py` to use `AcoreChannel`, remove `discord` imports.
  **Category**: `deep` | **Blocked By**: Task 1
  **Commit**: `refactor(context): decouple from discord`

- [x] 6. Behavior Engine Refactor

  **What to do**: Refactor `services/persona/behavior.py` to use `AcoreContext`, remove `discord` imports.
  **Category**: `deep` | **Blocked By**: Tasks 1, 5
  **Commit**: `refactor(behavior): use AcoreContext`

- [x] 7. Orchestrator Migration

  **What to do**: Move webhook logic to `adapters/discord/`, emit events from core.
  **Category**: `deep` | **Blocked By**: Task 2
  **Commit**: `refactor(orchestrator): separate core from discord`

- [x] 8. RL Service Decoupling

  **What to do**: Remove `discord` from `services/persona/rl/`, change IDs to strings.
  **Category**: `deep` | **Blocked By**: Task 1
  **Commit**: `refactor(rl): remove discord deps`

- [x] 9. Discord Input Adapter

  **What to do**: Implement Discord → Core event translation.
  **Category**: `unspecified-high` | **Blocked By**: Tasks 2, 6
  **Commit**: `feat(discord): input adapter implementation`

- [x] 10. Discord Output Adapter

  **What to do**: Implement Core → Discord output (webhooks, embeds).
  **Category**: `unspecified-high` | **Blocked By**: Tasks 2, 7
  **Commit**: `feat(discord): output adapter implementation`

- [x] 11. CLI Adapter Implementation

  **What to do**: Full stdin/stdout REPL for CLI.
  **Category**: `quick` | **Blocked By**: Tasks 2, 4
  **Commit**: `feat(cli): full implementation`

- [x] 12. Cogs Migration

  **What to do**: Move `cogs/` commands to `adapters/discord/commands/`.
  **Category**: `unspecified-high` | **Blocked By**: Task 9
  **Commit**: `refactor(discord): migrate cogs to adapter`

- [x] 13. Launcher Entry Point

  **What to do**: Create `launcher.py` to start enabled adapters.
  **Category**: `quick` | **Blocked By**: Tasks 9, 11
  **Commit**: `feat(core): add launcher`

- [x] 14. Dependency Injection Update

  **What to do**: Update `services/core/factory.py` for new architecture.
  **Category**: `deep` | **Blocked By**: Task 13
  **Commit**: `refactor(core): update factory for adapters`

- [x] 15. Regression Testing

  **What to do**: Verify Discord parity with baseline tests.
  **Category**: `deep` | **Blocked By**: Task 14
  **Commit**: `test: add regression suite`

- [x] 16. Documentation

  **What to do**: Write `docs/ARCHITECTURE.md` explaining Core vs Adapter.
  **Category**: `writing` | **Blocked By**: Task 15
  **Commit**: `docs: add architecture documentation`

---

## Final Verification Wave

- [x] F1. Plan Compliance Audit - ✅ All deliverables present
- [x] F2. Code Quality Review - ✅ Core services decoupled
- [x] F3. CLI End-to-End QA - ✅ Adapter imports work
- [x] F4. Scope Fidelity Check - ✅ No scope creep

---

## Commit Strategy

| Wave | Count | Focus |
|------|-------|-------|
| 1 | 4 tasks | Core abstractions (types, interfaces) |
| 2 | 4 tasks | Service decoupling (remove discord) |
| 3 | 4 tasks | Adapter implementation |
| 4 | 4 tasks | Integration, launcher, tests, docs |
| FINAL | 4 tasks | Verification audits |

---

## Success Criteria

- [ ] `grep -r "import discord" services/ | grep -v "voice"` returns empty
- [ ] Discord bot behaves identically to pre-refactor baseline
- [ ] CLI adapter can chat with all personas
- [ ] All existing tests pass
- [ ] New core types are JSON-serializable

---

**Plan saved to**: `.sisyphus/plans/framework-expansion.md`

**To execute**: Run `/start-work framework-expansion`
