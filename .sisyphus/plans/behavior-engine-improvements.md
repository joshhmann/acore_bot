# Behavior Engine Improvements: Fix Robotic Conversations

## TL;DR

> **Quick Summary**: Overhaul the BehaviorEngine to make Discord bot conversations feel natural and engaging rather than mechanical and constrained. Focus on simplifying decision logic, boosting engagement rates, and reducing system prompt complexity.
> 
> **Deliverables**:
> - Updated `services/persona/behavior.py` with simplified decision pipeline
> - Modified engagement probabilities (15%/30% → 60%/70%)
> - Simplified system prompt construction in `services/core/context.py`
> - Optional configuration flag for "conversation mode" bypass
> - Updated character template with reduced complexity
> - Test coverage for conversation quality improvements
> 
> **Estimated Effort**: Medium (6-8 hours)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Probability Updates → Prompt Simplification → Testing

---

## Context

### Original Request
User wants to fix the behavior engine so conversations feel "more conversational" and less robotic, despite having a sophisticated behavior system.

### Interview Summary
**Key Discussions**:
- BehaviorEngine consolidates 8 behavioral systems but conversations still feel mechanical
- User frustration with overly polite, low-engagement bot behavior
- Core issue identified as over-engineering rather than missing features

**Research Findings**:
- **behavior.py lines 377-535**: Complex RL decision logic creates decision paralysis
- **behavior.py lines 950, 1088**: Base reaction chance 15%, proactive engagement 30% - too conservative
- **behavior.py lines 660-684**: Mood intensity capped at 0.1 shift per message - too subtle
- **context.py**: Injects 6+ instruction blocks ([EMOTIONAL GUIDANCE], [FRAMEWORK BLENDING], [KNOWLEDGE], etc.) causing "Frankenstein prompts"
- **Character JSON files**: 500+ line technical specifications rather than organic personalities
- **message_handler.py line 308**: Hardcoded "conversational" style with no actual conversation flow

**Metis Review**
**Identified Gaps** (addressed):
- Missing risk assessment for changing core behavior (documented in Must NOT Have)
- Unclear rollback strategy (added to Rollback Plan)
- Need explicit acceptance criteria for "conversational feel" (defined in Success Criteria)
- Potential for breaking existing character behavior (addressed with toggleable changes)

---

## Work Objectives

### Core Objective
Transform the behavior engine from a complex decision optimization system into a streamlined engagement system that prioritizes natural conversation flow over "correct" behavior.

### Concrete Deliverables
1. Updated `services/persona/behavior.py` with simplified decision pipeline
2. Higher engagement probabilities in `_calculate_reaction_probability()` and `_calculate_engagement_probability()`
3. Modified `services/core/context.py` to reduce prompt complexity
4. Optional `conversation_mode` configuration flag in `config.py`
5. Simplified character template with <100 lines of personality definition
6. Updated tests in `tests/unit/test_behavior_engine.py`
7. Documentation update in `docs/BEHAVIOR_ENGINE.md`

### Definition of Done
- [ ] Bot responds to 60%+ of direct mentions without cooldown violations
- [ ] System prompts reduced to <100 lines per character
- [ ] Character responses feel more spontaneous in user testing
- [ ] All existing tests pass
- [ ] New integration tests verify engagement rates

### Must Have
- Increased base engagement probabilities (minimum 2x increase)
- Removal or option to disable mood/contagion/framework blending overlap
- Simplified prompt construction with fewer instruction blocks
- Backward compatibility with existing character definitions
- Rollback plan if changes degrade experience

### Must NOT Have (Guardrails)
- **DO NOT** remove RL system entirely (needed for spam prevention)
- **DO NOT** break existing character loading system
- **DO NOT** change database schema or user data storage
- **DO NOT** remove safety checks entirely (keep cooldowns, just make them shorter)
- **DO NOT** affect voice/TTS functionality (keep scope to text chat)
- **NO scope creep** into unrelated features like analytics or admin dashboard
- **DO NOT** make changes that increase latency beyond 5ms overhead target

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> ALL verification is executed by the agent using tools (Playwright, interactive_bash, curl, etc.).

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after
- **Framework**: pytest (existing)

### Agent-Executed QA Scenarios (MANDATORY - ALL tasks)

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Backend Logic** | Bash (pytest) | Run test suite, assert pass rates |
| **Behavior Validation** | Bash (bun test) | Run unit tests, verify engagement probabilities |
| **Integration** | Bash (curl + grep) | Start bot, send test messages, count responses |

**Each Scenario Format:**

```
Scenario: [Descriptive name]
  Tool: [Playwright / interactive_bash / Bash]
  Preconditions: [What must be true]
  Steps:
    1. [Exact action with specific selector/command]
    2. [Assertion with expected value]
  Expected Result: [Concrete outcome]
  Failure Indicators: [What indicates failure]
  Evidence: [Screenshot/output path]
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Boost engagement probabilities
├── Task 2: Add conversation mode configuration flag
└── Task 3: Create simplified character template

Wave 2 (After Wave 1):
├── Task 4: Simplify prompt construction
├── Task 5: Add conversation mode bypass logic
└── Task 6: Disable overlapping behavioral systems

Wave 3 (After Wave 2):
├── Task 7: Update tests
└── Task 8: Update documentation
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 7 | 2, 3 |
| 2 | None | 5 | 1, 3 |
| 3 | None | None | 1, 2 |
| 4 | None | 5 | 1, 2, 3 |
| 5 | 2, 4 | 6, 7 | None |
| 6 | 5 | 7 | None |
| 7 | 1, 5, 6 | 8 | None |
| 8 | 7 | None | None |

### Critical Path: Task 1 → Task 5 → Task 6 → Task 7 → Task 8
### Parallel Speedup: ~35% faster than sequential

---

## TODOs

### Task 1: Boost Engagement Probabilities

**What to do**:
- Increase base reaction probability from 0.15 to 0.60 in `_calculate_reaction_probability()`
- Increase proactive engagement from 0.30 to 0.70 in `_calculate_engagement_probability()`
- Reduce cooldown periods by 50% (e.g., 300s → 150s)
- Keep RL system for spam detection but bypass for direct mentions

**Must NOT do**:
- Remove cooldowns entirely (keep minimum safety)
- Change RL system for non-conversation detection
- Affect voice channel behavior

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple probability changes, low risk, well-scoped
- **Skills**: []
  - No special skills needed - basic Python modifications

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2, 3)
- **Blocks**: Task 7 (tests need updated values)
- **Blocked By**: None

**References**:
- `services/persona/behavior.py:950` - `_calculate_reaction_probability()` method
- `services/persona/behavior.py:1088` - `_calculate_engagement_probability()` method
- `services/persona/behavior.py:377-535` - RL decision logic to understand bypass strategy
- `tests/unit/test_behavior_engine.py` - existing tests to update

**WHY Each Reference Matters**:
- Lines 950, 1088: Direct probability constants to modify
- Lines 377-535: Shows where to add conversation mode bypass

**Acceptance Criteria**:
- [ ] `base_reaction_probability` = 0.60 (from 0.15)
- [ ] `proactive_engagement_probability` = 0.70 (from 0.30)
- [ ] Cooldowns reduced by 50% throughout
- [ ] `uv run pytest tests/unit/test_behavior_engine.py -v` → PASS

**Agent-Executed QA Scenarios**:

```
Scenario: Verify engagement probability constants updated
  Tool: Bash (grep + assertion)
  Preconditions: File exists at services/persona/behavior.py
  Steps:
    1. Run: grep -n "base_reaction_probability" services/persona/behavior.py
    2. Assert: Output contains "0.60" or "= 0.6"
    3. Run: grep -n "proactive_engagement" services/persona/behavior.py
    4. Assert: Output contains "0.70" or "= 0.7"
    5. Run: grep -n "cooldown" services/persona/behavior.py | head -5
    6. Assert: Values reduced (e.g., 150 instead of 300)
  Expected Result: All probability constants updated to higher values
  Evidence: Terminal output captured

Scenario: Unit tests pass with new probabilities
  Tool: Bash (pytest)
  Preconditions: uv installed, tests exist
  Steps:
    1. Run: uv run pytest tests/unit/test_behavior_engine.py -v --tb=short
    2. Assert: Exit code 0
    3. Assert: Output shows "passed" for all tests
    4. Assert: No "FAILED" in output
  Expected Result: All behavior engine tests pass
  Evidence: pytest output saved to .sisyphus/evidence/task-1-pytest.log
```

**Evidence to Capture**:
- [ ] Terminal output showing updated constants
- [ ] Pytest results in `.sisyphus/evidence/task-1-pytest.log`

**Commit**: YES
- Message: `feat(behavior): Increase engagement probabilities for more natural conversation`
- Files: `services/persona/behavior.py`
- Pre-commit: `uv run pytest tests/unit/test_behavior_engine.py`

---

### Task 2: Add Conversation Mode Configuration

**What to do**:
- Add `CONVERSATION_MODE_ENABLED` boolean to `config.py`
- Add `CONVERSATION_MODE_PROBABILITY_BOOST` float (default 0.4)
- Add `CONVERSATION_MODE_PROMPT_SIMPLIFICATION` boolean
- Load from environment variables with sensible defaults

**Must NOT do**:
- Break existing config loading
- Require mandatory config changes

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple configuration additions
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 3)
- **Blocks**: Task 5 (needs config to implement bypass)
- **Blocked By**: None

**References**:
- `config.py` - existing configuration structure
- `.env.example` - environment variable examples

**Acceptance Criteria**:
- [ ] `config.py` has `CONVERSATION_MODE_ENABLED` (default False)
- [ ] `config.py` has `CONVERSATION_MODE_PROBABILITY_BOOST` (default 0.4)
- [ ] Config loads from env with defaults
- [ ] Existing tests still pass

**Agent-Executed QA Scenarios**:

```
Scenario: Configuration variables load correctly
  Tool: Bash (python)
  Preconditions: Python environment ready
  Steps:
    1. Run: uv run python -c "from config import CONVERSATION_MODE_ENABLED, CONVERSATION_MODE_PROBABILITY_BOOST; print(f'ENABLED={CONVERSATION_MODE_ENABLED}, BOOST={CONVERSATION_MODE_PROBABILITY_BOOST}')"
    2. Assert: Output shows ENABLED=False, BOOST=0.4
    3. Run: export CONVERSATION_MODE_ENABLED=true && uv run python -c "from config import CONVERSATION_MODE_ENABLED; print(CONVERSATION_MODE_ENABLED)"
    4. Assert: Output contains "True"
  Expected Result: Config loads with defaults and respects env vars
  Evidence: Terminal output captured
```

**Commit**: YES
- Message: `feat(config): Add conversation mode configuration options`
- Files: `config.py`, `.env.example`
- Pre-commit: `uv run pytest tests/unit/test_config.py` (if exists) or syntax check

---

### Task 3: Create Simplified Character Template

**What to do**:
- Create `prompts/characters/example_simple_persona.json` as reference
- Limit to: name, core personality (2-3 traits), speaking style (1-2 sentences), 2-3 hot takes
- Remove: detailed behavioral rules, framework blending configs, mood triggers
- Keep: interests list for topic filtering (but simplify)

**Must NOT do**:
- Delete existing character files
- Break backward compatibility

**Recommended Agent Profile**:
- **Category**: `writing`
  - Reason: Creating documentation and template content
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 2)
- **Blocks**: None (documentation/template only)
- **Blocked By**: None

**References**:
- `prompts/characters/example_advanced_persona.json` - shows all features to simplify
- `prompts/characters/dagoth_ur.json` - example of current complexity

**Acceptance Criteria**:
- [ ] Template file created at `prompts/characters/example_simple_persona.json`
- [ ] File <100 lines
- [ ] Bot can load and use template without errors
- [ ] Template loads via existing loader system

**Agent-Executed QA Scenarios**:

```
Scenario: Simple persona template loads correctly
  Tool: Bash (python)
  Preconditions: Template file exists
  Steps:
    1. Run: uv run python -c "from utils.persona_loader import load_persona; p = load_persona('example_simple_persona'); print(f'Loaded: {p.name}')"
    2. Assert: Output shows persona name loaded
    3. Assert: No exceptions raised
    4. Run: wc -l prompts/characters/example_simple_persona.json
    5. Assert: Line count < 100
  Expected Result: Template loads successfully and is concise
  Evidence: Terminal output captured
```

**Commit**: YES
- Message: `docs(personas): Add simplified character template for natural conversation`
- Files: `prompts/characters/example_simple_persona.json`
- Pre-commit: Load test via Python

---

### Task 4: Simplify Prompt Construction

**What to do**:
- Modify `services/core/context.py` to reduce instruction blocks
- When `CONVERSATION_MODE_ENABLED=True`:
  - Skip [FRAMEWORK_BLENDING] block
  - Skip [EMOTIONAL_GUIDANCE] block
  - Skip [MOOD_STATE] block
  - Keep: [CHARACTER_DEFINITION], [CONTEXT], [USER_INFO]
- Consolidate remaining blocks into single [INSTRUCTIONS] section

**Must NOT do**:
- Break existing prompt construction
- Remove blocks when conversation mode is disabled

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Conditional logic to skip blocks
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Task 2 for config)
- **Parallel Group**: Wave 2
- **Blocks**: Task 5
- **Blocked By**: Task 2

**References**:
- `services/core/context.py` - prompt construction logic
- `services/core/context.py:build_system_prompt()` - main method to modify

**Acceptance Criteria**:
- [ ] Prompt length reduced by 50%+ when conversation mode enabled
- [ ] All existing tests pass
- [ ] Manual inspection shows fewer [BLOCK] headers

**Agent-Executed QA Scenarios**:

```
Scenario: Conversation mode reduces prompt length
  Tool: Bash (python)
  Preconditions: Task 2 completed
  Steps:
    1. Run: uv run python -c "
import os
os.environ['CONVERSATION_MODE_ENABLED'] = 'true'
from services.core.context import ContextManager
from services.persona.system import PersonaSystem
ctx = ContextManager(PersonaSystem())
persona = type('obj', (object,), {'system_prompt': 'Test', 'character': type('c', (object,), {'name': 'Test'})()})()
prompt = ctx.build_system_prompt(persona, None)
print(f'Length: {len(prompt)}')
print(f'Has [FRAMEWORK_BLENDING]: {\"[FRAMEWORK_BLENDING]\" in prompt}')
print(f'Has [EMOTIONAL_GUIDANCE]: {\"[EMOTIONAL_GUIDANCE]\" in prompt}')
"
    2. Assert: Length < 500 characters (reduced from typical 2000+)
    3. Assert: "[FRAMEWORK_BLENDING]" not in output
    4. Assert: "[EMOTIONAL_GUIDANCE]" not in output
  Expected Result: Prompt is significantly shorter without behavioral blocks
  Evidence: Terminal output with character counts
```

**Commit**: YES
- Message: `feat(context): Simplify prompt construction in conversation mode`
- Files: `services/core/context.py`
- Pre-commit: `uv run pytest tests/unit/test_context.py` (if exists)

---

### Task 5: Implement Conversation Mode Bypass Logic

**What to do**:
- In `behavior.py`, check `CONVERSATION_MODE_ENABLED` config
- When enabled:
  - Skip RL decision tree for direct mentions (lines 377-535)
  - Bypass mood/contagion calculations for response generation
  - Use fast path: direct response instead of decision matrix
- Keep RL for spam detection on non-mentioned messages

**Must NOT do**:
- Remove RL system entirely
- Break existing non-conversation mode behavior

**Recommended Agent Profile**:
- **Category**: `unspecified-medium`
  - Reason: Requires understanding behavior engine architecture
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Tasks 2, 4)
- **Parallel Group**: Wave 2
- **Blocks**: Task 6
- **Blocked By**: Tasks 2, 4

**References**:
- `services/persona/behavior.py:handle_message()` - entry point
- `services/persona/behavior.py:377-535` - RL decision logic to bypass
- `config.py` - for config access

**Acceptance Criteria**:
- [ ] When `CONVERSATION_MODE_ENABLED=True`, direct mentions bypass RL decision tree
- [ ] Response time improved (measure via logging)
- [ ] All existing tests pass

**Agent-Executed QA Scenarios**:

```
Scenario: Conversation mode bypasses RL for direct mentions
  Tool: Bash (python + logging)
  Preconditions: Bot code runnable
  Steps:
    1. Add debug logging to behavior.py showing RL bypass
    2. Set CONVERSATION_MODE_ENABLED=true in env
    3. Run: uv run python -c "
import asyncio
from services.persona.behavior import BehaviorEngine
from unittest.mock import MagicMock

engine = BehaviorEngine(MagicMock(), MagicMock())
# Simulate direct mention
result = asyncio.run(engine.handle_message(MagicMock(mentions=[MagicMock()]), MagicMock()))
print('Test completed')
" 2>&1 | grep -i "bypass\|conversation mode" || echo "Pattern not found - check implementation"
    4. Assert: Log output shows bypass message
  Expected Result: Conversation mode skips RL processing
  Evidence: Log output captured
```

**Commit**: YES
- Message: `feat(behavior): Add conversation mode bypass for faster direct responses`
- Files: `services/persona/behavior.py`
- Pre-commit: `uv run pytest tests/unit/test_behavior_engine.py`

---

### Task 6: Disable Overlapping Behavioral Systems

**What to do**:
- When `CONVERSATION_MODE_ENABLED=True`:
  - Disable `MoodSystem` updates (keep state but don't apply modifiers)
  - Disable `EmotionalContagion` processing
  - Disable `FrameworkBlending` completely
  - Keep: `CuriositySystem` (can add value)
  - Keep: `ProactiveEngagement` (with higher probabilities from Task 1)

**Must NOT do**:
- Remove the systems entirely (just disable in conversation mode)
- Break mood tracking (disable application, not tracking)

**Recommended Agent Profile**:
- **Category**: `unspecified-medium`
  - Reason: Conditional disabling of multiple systems
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Task 5)
- **Parallel Group**: Wave 2
- **Blocks**: Task 7
- **Blocked By**: Task 5

**References**:
- `services/persona/behavior.py` - all system integration points
- Look for: `self.mood_system`, `self.emotional_contagion`, `self.framework_blending`

**Acceptance Criteria**:
- [ ] Mood system updates disabled in conversation mode
- [ ] Emotional contagion disabled in conversation mode
- [ ] Framework blending disabled in conversation mode
- [ ] All existing tests pass

**Agent-Executed QA Scenarios**:

```
Scenario: Behavioral systems disabled in conversation mode
  Tool: Bash (python + assertions)
  Preconditions: Task 5 completed
  Steps:
    1. Run: uv run python -c "
import os
os.environ['CONVERSATION_MODE_ENABLED'] = 'true'
from services.persona.behavior import BehaviorEngine
from unittest.mock import MagicMock, patch

engine = BehaviorEngine(MagicMock(), MagicMock())
# Verify systems are disabled
assert not engine.mood_system_enabled, 'Mood system should be disabled'
assert not engine.emotional_contagion_enabled, 'Contagion should be disabled'
assert not engine.framework_blending_enabled, 'Blending should be disabled'
print('All systems correctly disabled in conversation mode')
"
    2. Assert: No assertion errors
    3. Assert: Output shows success message
  Expected Result: Systems disabled when conversation mode enabled
  Evidence: Terminal output captured
```

**Commit**: YES
- Message: `feat(behavior): Disable overlapping systems in conversation mode`
- Files: `services/persona/behavior.py`
- Pre-commit: `uv run pytest tests/unit/test_behavior_engine.py`

---

### Task 7: Update Tests

**What to do**:
- Update `tests/unit/test_behavior_engine.py`:
  - Add tests for new probability values
  - Add tests for conversation mode toggle
  - Add tests for bypass logic
- Add `tests/integration/test_conversation_mode.py`:
  - Test end-to-end conversation flow
  - Verify engagement rates with mock messages
  - Test response quality metrics

**Must NOT do**:
- Break existing test coverage
- Skip testing edge cases

**Recommended Agent Profile**:
- **Category**: `unspecified-medium`
  - Reason: Comprehensive test coverage
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Tasks 1, 5, 6)
- **Parallel Group**: Wave 3
- **Blocks**: Task 8
- **Blocked By**: Tasks 1, 5, 6

**References**:
- `tests/unit/test_behavior_engine.py` - existing tests
- `tests/conftest.py` - fixtures

**Acceptance Criteria**:
- [ ] All unit tests pass (`uv run pytest tests/unit/test_behavior_engine.py`)
- [ ] New tests added for conversation mode
- [ ] Test coverage >= 70% (maintain existing)
- [ ] Integration tests verify engagement rates

**Agent-Executed QA Scenarios**:

```
Scenario: All behavior engine tests pass
  Tool: Bash (pytest)
  Preconditions: All previous tasks completed
  Steps:
    1. Run: uv run pytest tests/unit/test_behavior_engine.py -v --tb=short --cov=services/persona/behavior --cov-report=term-missing
    2. Assert: Exit code 0
    3. Assert: Output shows "passed" for all tests
    4. Assert: Coverage >= 70%
    5. Run: uv run pytest tests/integration/test_conversation_mode.py -v
    6. Assert: Exit code 0
  Expected Result: All tests pass with good coverage
  Evidence: Pytest output saved to .sisyphus/evidence/task-7-tests.log

Scenario: Integration test verifies engagement
  Tool: Bash (pytest)
  Preconditions: Integration test file exists
  Steps:
    1. Run: uv run pytest tests/integration/test_conversation_mode.py::test_engagement_rate -v
    2. Assert: Exit code 0
    3. Assert: Output shows "PASSED"
    4. Assert: Engagement rate >= 0.60 (60%)
  Expected Result: Integration test confirms improved engagement
  Evidence: Test output captured
```

**Evidence to Capture**:
- [ ] Test output in `.sisyphus/evidence/task-7-tests.log`
- [ ] Coverage report

**Commit**: YES
- Message: `test(behavior): Add tests for conversation mode and engagement improvements`
- Files: `tests/unit/test_behavior_engine.py`, `tests/integration/test_conversation_mode.py`
- Pre-commit: `uv run pytest tests/unit/test_behavior_engine.py tests/integration/test_conversation_mode.py`

---

### Task 8: Update Documentation

**What to do**:
- Update `docs/BEHAVIOR_ENGINE.md` (or create if missing):
  - Document conversation mode feature
  - Explain new engagement probabilities
  - Show before/after prompt examples
  - Migration guide for existing users
- Update `docs/PERSONAS.md`:
  - Reference simplified template
  - Explain character design philosophy
- Update `README.md`:
  - Mention conversation mode feature
  - Quick start for more natural conversations

**Must NOT do**:
- Remove existing documentation
- Leave outdated references

**Recommended Agent Profile**:
- **Category**: `writing`
  - Reason: Documentation creation
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Task 7 for test results)
- **Parallel Group**: Wave 3
- **Blocks**: None
- **Blocked By**: Task 7

**References**:
- `docs/` directory structure
- Existing documentation style

**Acceptance Criteria**:
- [ ] Documentation explains conversation mode
- [ ] Examples show prompt simplification
- [ ] Migration guide included
- [ ] README updated with feature mention

**Agent-Executed QA Scenarios**:

```
Scenario: Documentation files exist and are valid
  Tool: Bash (file checks)
  Preconditions: None
  Steps:
    1. Run: ls -la docs/BEHAVIOR_ENGINE.md docs/PERSONAS.md README.md
    2. Assert: All files exist
    3. Run: grep -i "conversation mode" docs/BEHAVIOR_ENGINE.md README.md
    4. Assert: Output found in both files
    5. Run: grep -i "simplified" docs/PERSONAS.md
    6. Assert: Output found
  Expected Result: Documentation updated with new features
  Evidence: Terminal output captured
```

**Commit**: YES
- Message: `docs: Update behavior engine and persona documentation`
- Files: `docs/BEHAVIOR_ENGINE.md`, `docs/PERSONAS.md`, `README.md`
- Pre-commit: Markdown validation (if available)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(behavior): Increase engagement probabilities` | `services/persona/behavior.py` | `uv run pytest tests/unit/test_behavior_engine.py` |
| 2 | `feat(config): Add conversation mode configuration` | `config.py`, `.env.example` | Config load test |
| 3 | `docs(personas): Add simplified character template` | `prompts/characters/example_simple_persona.json` | Template load test |
| 4 | `feat(context): Simplify prompt construction` | `services/core/context.py` | Context tests |
| 5 | `feat(behavior): Add conversation mode bypass` | `services/persona/behavior.py` | Behavior tests |
| 6 | `feat(behavior): Disable overlapping systems` | `services/persona/behavior.py` | Behavior tests |
| 7 | `test(behavior): Add conversation mode tests` | `tests/` | All tests pass |
| 8 | `docs: Update documentation` | `docs/`, `README.md` | File exists check |

---

## Success Criteria

### Verification Commands
```bash
# Test 1: Engagement probabilities updated
uv run pytest tests/unit/test_behavior_engine.py -v
# Expected: All tests pass

# Test 2: Conversation mode config loads
uv run python -c "from config import CONVERSATION_MODE_ENABLED; print(CONVERSATION_MODE_ENABLED)"
# Expected: Output shows boolean value

# Test 3: Integration tests pass
uv run pytest tests/integration/test_conversation_mode.py -v
# Expected: Exit code 0, engagement rate >= 60%

# Test 4: Simple persona loads
uv run python -c "from utils.persona_loader import load_persona; load_persona('example_simple_persona')"
# Expected: No errors
```

### Rollback Plan
If changes degrade conversation quality:
1. Set `CONVERSATION_MODE_ENABLED=false` in config (immediate)
2. Revert commits if needed: `git revert HEAD~7..HEAD`
3. Restore original probabilities from git history

### Final Checklist
- [ ] All "Must Have" present (probabilities updated, prompt simplified)
- [ ] All "Must NOT Have" absent (RL system intact, no breaking changes)
- [ ] All tests pass (unit + integration)
- [ ] Documentation updated
- [ ] Rollback plan documented
- [ ] No latency regression (>5ms overhead maintained)
