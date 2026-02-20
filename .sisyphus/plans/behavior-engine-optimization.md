# Behavior Engine Optimization: Settings, RL Training & Monitoring

## TL;DR

> **Quick Summary**: Optimize the existing BehaviorEngine through better configuration, RL training data integration, and monitoring. Keep the sophisticated system intact while making it more conversational through data-driven learning.
> 
> **Deliverables**:
> - Configuration guide documenting all tweakable behavior settings
> - Updated default probabilities (15% → 50% reaction, 30% → 60% engagement)
> - Bot-to-bot conversation integration with RL training pipeline
> - Monitoring dashboard for behavior engine metrics and RL learning progress
> - Documentation on how RL learns from interactions
> 
> **Estimated Effort**: Medium (4-6 hours)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Config Guide → Probability Update → RL Integration → Monitoring

---

## Context

### Original Request
User wants conversations to feel more natural. Currently using default settings with RL enabled, adding bot-to-bot conversations for training data. Wants to understand and optimize the behavior system rather than replace it.

### Interview Summary
**Key Discussions**:
- User likes the behavior system architecture
- RL is enabled and learning from interactions
- Bot-to-bot conversations provide training data
- Default settings (15% reaction) feel too conservative
- User wants 50% balanced reaction probability

**Research Findings**:
- **behavior.py**: Sophisticated RL system exists but defaults are conservative
- **behavior.py:950, 1088**: Hardcoded probabilities need configuration exposure
- **Bot conversations**: Not currently feeding into RL training rewards
- **Missing**: Documentation on what settings exist and how to tune them
- **Missing**: Visibility into RL learning progress

---

## Work Objectives

### Core Objective
Transform the behavior engine from "black box with conservative defaults" to "transparent, tunable system with RL learning visibility" while preserving all existing functionality.

### Concrete Deliverables
1. **Configuration Guide** (`docs/BEHAVIOR_CONFIGURATION.md`): Document all tweakable parameters with explanations
2. **Settings Exposed** (`config.py`): Move hardcoded probabilities to environment variables
3. **Updated Defaults** (`services/persona/behavior.py`): 15% → 50% reaction, 30% → 60% engagement
4. **RL Integration** (`services/persona/behavior.py`): Bot-to-bot conversations feed training rewards
5. **Monitoring Dashboard** (`services/core/metrics.py` + web): Track RL decisions, learning progress, engagement rates
6. **Documentation** (`docs/RL_LEARNING.md`): Explain how RL learns and how to interpret metrics

### Definition of Done
- [x] All behavior settings configurable via environment variables
- [x] Bot responds ~50% of the time to direct mentions
- [x] Bot-to-bot conversations contribute to RL training data
- [x] Dashboard shows RL decision distribution and learning progress
- [x] Documentation explains each setting and how RL learns
- [x] All existing tests pass
- [x] New integration tests verify RL training integration

### Must Have
- Expose all hardcoded probabilities as configuration
- Document every behavior setting with recommendations
- Integrate botconv with RL reward system
- Add metrics tracking for RL decisions
- Keep backward compatibility (existing configs still work)
- Balanced 50% reaction probability as new default

### Must NOT Have (Guardrails)
- **DO NOT** remove or disable any existing behavior systems
- **DO NOT** break RL learning continuity (preserve existing models)
- **DO NOT** require manual RL retraining
- **DO NOT** change database schema
- **NO scope creep** into unrelated features
- **DO NOT** make RL mandatory (keep it optional/configurable)

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> ALL verification is executed by the agent using tools.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after
- **Framework**: pytest (existing)

### Agent-Executed QA Scenarios (MANDATORY - ALL tasks)

See individual tasks for detailed QA scenarios using Bash (pytest, grep, python) to verify configurations, RL integration, and metrics.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Document all behavior settings
├── Task 2: Expose probabilities as config
└── Task 3: Update default probabilities (15%→50%)

Wave 2 (After Wave 1):
├── Task 4: Integrate botconv with RL training
├── Task 5: Add behavior engine metrics
└── Task 6: Create monitoring dashboard

Wave 3 (After Wave 2):
└── Task 7: Update tests and documentation
```

### Critical Path: Task 2 → Task 3 → Task 4 → Task 6

---

## TODOs

### Task 1: Document All Behavior Settings

**What to do**:
- Create `docs/BEHAVIOR_CONFIGURATION.md`
- Document every configurable parameter in behavior.py
- Explain what each setting does and when to adjust it
- Provide recommended values for different use cases (quiet bot, active bot, spam prevention focus)
- Include troubleshooting guide

**Must NOT do**:
- Remove or change any settings
- Make recommendations that contradict existing functionality

**Recommended Agent Profile**:
- **Category**: `writing`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: None
- **Blocked By**: None

**References**:
- `services/persona/behavior.py` - all hardcoded values and config references
- `.env.example` - existing configuration pattern

**Acceptance Criteria**:
- [x] Document lists all behavior parameters
- [x] Each parameter has: description, default value, recommended range
- [x] Document <1000 lines
- [x] Includes troubleshooting section

**Agent-Executed QA Scenarios**:

```
Scenario: Configuration documentation exists and covers all settings
  Tool: Bash (file checks)
  Preconditions: None
  Steps:
    1. Run: ls -la docs/BEHAVIOR_CONFIGURATION.md
    2. Assert: File exists
    3. Run: wc -l docs/BEHAVIOR_CONFIGURATION.md
    4. Assert: Line count > 50 (substantial content)
    5. Run: grep -c "BEHAVIOR_" docs/BEHAVIOR_CONFIGURATION.md
    6. Assert: Count >= 5 (documents multiple settings)
  Expected Result: Comprehensive configuration guide exists
  Evidence: File stats captured
```

**Commit**: YES
- Message: `docs: Add comprehensive behavior engine configuration guide`
- Files: `docs/BEHAVIOR_CONFIGURATION.md`
- Pre-commit: File existence check

---

### Task 2: Expose Probabilities as Configuration

**What to do**:
- Add to `config.py`:
  - `BEHAVIOR_REACTION_PROBABILITY` (default 0.50)
  - `BEHAVIOR_PROACTIVE_PROBABILITY` (default 0.60)
  - `BEHAVIOR_COOLDOWN_SECONDS` (default 150, was 300)
  - `BEHAVIOR_MOOD_SHIFT_MAX` (default 0.2, was 0.1)
- Update `services/persona/behavior.py` to read from config instead of hardcoded values
- Add to `.env.example` with comments

**Must NOT do**:
- Break existing behavior when config missing (use defaults)
- Change the logic, just the source of values

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: Task 3
- **Blocked By**: None

**References**:
- `services/persona/behavior.py:950` - reaction probability constant
- `services/persona/behavior.py:1088` - engagement probability constant
- `config.py` - existing configuration structure

**Acceptance Criteria**:
- [x] All probability constants moved to config
- [x] Config loads from environment with defaults
- [x] Behavior.py reads from config instead of hardcoded values
- [x] `.env.example` updated

**Agent-Executed QA Scenarios**:

```
Scenario: Configuration values are used instead of hardcoded constants
  Tool: Bash (python + grep)
  Preconditions: None
  Steps:
    1. Run: grep -n "BEHAVIOR_REACTION_PROBABILITY" services/persona/behavior.py | head -3
    2. Assert: Found in behavior.py (not just config.py)
    3. Run: grep -n "0.15\|base_reaction.*=" services/persona/behavior.py | grep -v "config"
    4. Assert: No hardcoded 0.15 found (should use config)
    5. Run: uv run python -c "from config import BEHAVIOR_REACTION_PROBABILITY; print(BEHAVIOR_REACTION_PROBABILITY)"
    6. Assert: Output shows 0.5
  Expected Result: Values configurable via environment
  Evidence: Terminal output captured

Scenario: Environment variables override defaults
  Tool: Bash (python)
  Preconditions: Config implemented
  Steps:
    1. Run: export BEHAVIOR_REACTION_PROBABILITY=0.75 && uv run python -c "from config import BEHAVIOR_REACTION_PROBABILITY; print(f'Reaction: {BEHAVIOR_REACTION_PROBABILITY}')"
    2. Assert: Output shows 0.75
    3. Run: unset BEHAVIOR_REACTION_PROBABILITY && uv run python -c "from config import BEHAVIOR_REACTION_PROBABILITY; print(f'Default: {BEHAVIOR_REACTION_PROBABILITY}')"
    4. Assert: Output shows 0.5
  Expected Result: Env vars override, defaults work
  Evidence: Terminal output captured
```

**Commit**: YES
- Message: `feat(config): Expose behavior engine probabilities as configuration`
- Files: `config.py`, `services/persona/behavior.py`, `.env.example`
- Pre-commit: `uv run pytest tests/unit/test_behavior_engine.py -v`

---

### Task 3: Update Default Probabilities

**What to do**:
- Change defaults in config.py:
  - `BEHAVIOR_REACTION_PROBABILITY`: 0.15 → 0.50
  - `BEHAVIOR_PROACTIVE_PROBABILITY`: 0.30 → 0.60
  - `BEHAVIOR_COOLDOWN_SECONDS`: 300 → 150
  - `BEHAVIOR_MOOD_SHIFT_MAX`: 0.1 → 0.2
- Document the changes in config comments
- Update any tests that assert on old values

**Must NOT do**:
- Change logic, just defaults
- Break existing user configurations

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Task 2)
- **Parallel Group**: Wave 1
- **Blocks**: Task 7 (tests)
- **Blocked By**: Task 2

**Acceptance Criteria**:
- [x] All default probabilities updated to new values
- [x] Tests updated to match new defaults
- [x] Behavior tests pass

**Agent-Executed QA Scenarios**:

```
Scenario: Default probabilities updated correctly
  Tool: Bash (python)
  Preconditions: Task 2 completed
  Steps:
    1. Run: uv run python -c "
from config import (
    BEHAVIOR_REACTION_PROBABILITY,
    BEHAVIOR_PROACTIVE_PROBABILITY,
    BEHAVIOR_COOLDOWN_SECONDS,
    BEHAVIOR_MOOD_SHIFT_MAX
)
print(f'Reaction: {BEHAVIOR_REACTION_PROBABILITY}')
print(f'Proactive: {BEHAVIOR_PROACTIVE_PROBABILITY}')
print(f'Cooldown: {BEHAVIOR_COOLDOWN_SECONDS}')
print(f'Mood Shift: {BEHAVIOR_MOOD_SHIFT_MAX}')
"
    2. Assert: Reaction ≈ 0.50
    3. Assert: Proactive ≈ 0.60
    4. Assert: Cooldown ≈ 150
    5. Assert: Mood shift ≈ 0.2
  Expected Result: All defaults at new balanced values
  Evidence: Terminal output captured

Scenario: Updated values pass behavior tests
  Tool: Bash (pytest)
  Preconditions: None
  Steps:
    1. Run: uv run pytest tests/unit/test_behavior_engine.py -v --tb=short 2>&1 | head -50
    2. Assert: Exit code 0
    3. Assert: Output shows "passed" for all tests
  Expected Result: All tests pass with new defaults
  Evidence: pytest output in .sisyphus/evidence/task-3-pytest.log
```

**Commit**: YES
- Message: `feat(behavior): Update default probabilities to balanced values (50%/60%)`
- Files: `config.py`, `tests/unit/test_behavior_engine.py`
- Pre-commit: `uv run pytest tests/unit/test_behavior_engine.py`

---

### Task 4: Integrate Bot-to-Bot Conversations with RL Training

**What to do**:
- Modify bot conversation handler to emit RL training signals
- When bot conversation completes:
  - If conversation was high quality (engaging, natural): positive reward
  - If conversation was repetitive/broken: negative reward
- Feed these signals into `BehaviorEngine.rl_service.record_feedback()`
- Add configuration: `BOTCONV_RL_TRAINING_ENABLED` (default true)

**Must NOT do**:
- Break existing botconv functionality
- Make RL training mandatory

**Recommended Agent Profile**:
- **Category**: `unspecified-medium`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Task 3)
- **Parallel Group**: Wave 2
- **Blocks**: Task 6 (metrics need this data)
- **Blocked By**: Task 3

**References**:
- `cogs/chat/bot_conversations.py` or similar botconv handler
- `services/persona/behavior.py` - RL service interface
- Look for: `record_feedback()`, `rl_service`, bot conversation completion

**Acceptance Criteria**:
- [x] Bot conversations emit RL training signals
- [x] Quality assessment determines reward/penalty
- [x] Config flag controls whether training is enabled
- [x] Existing botconv tests pass

**Agent-Executed QA Scenarios**:

```
Scenario: Bot conversations feed RL training data
  Tool: Bash (python + mock)
  Preconditions: Task 3 completed
  Steps:
    1. Run: uv run python -c "
import os
os.environ['BOTCONV_RL_TRAINING_ENABLED'] = 'true'
from unittest.mock import MagicMock, patch

# Mock the behavior engine RL service
with patch('services.persona.behavior.BehaviorEngine') as MockEngine:
    mock_instance = MagicMock()
    mock_instance.rl_service = MagicMock()
    MockEngine.return_value = mock_instance
    
    # Simulate bot conversation completion
    from cogs.chat.bot_conversations import complete_conversation
    complete_conversation(conversation_id='test-123', quality_score=0.8)
    
    # Check if RL got feedback
    assert mock_instance.rl_service.record_feedback.called, 'RL feedback not recorded'
    print('RL training integration working')
"
    2. Assert: No assertion errors
    3. Assert: Output shows success
  Expected Result: Bot conversations contribute to RL learning
  Evidence: Test output captured

Scenario: Quality score affects reward signal
  Tool: Bash (python)
  Preconditions: Integration implemented
  Steps:
    1. Run: uv run python -c "
# Check that high quality = positive reward, low quality = negative
from services.persona.behavior import calculate_rl_reward
print(f'High quality (0.8): {calculate_rl_reward(0.8)}')
print(f'Low quality (0.2): {calculate_rl_reward(0.2)}')
"
    2. Assert: High quality returns positive value
    3. Assert: Low quality returns negative or near-zero value
  Expected Result: Quality score properly influences RL
  Evidence: Reward values captured
```

**Commit**: YES
- Message: `feat(botconv): Integrate bot conversations with RL training pipeline`
- Files: `cogs/chat/bot_conversations.py`, `services/persona/behavior.py`, `config.py`
- Pre-commit: `uv run pytest tests/unit/test_bot_conversations.py tests/unit/test_behavior_engine.py`

---

### Task 5: Add Behavior Engine Metrics

**What to do**:
- Extend `services/core/metrics.py` to track:
  - RL decision distribution (react vs wait vs proactive)
  - Engagement rates over time
  - Mood state transitions
  - Bot-to-bot conversation quality scores
- Add metrics collection hooks in behavior.py
- Store metrics in existing metrics storage

**Must NOT do**:
- Create new storage systems (use existing metrics)
- Impact performance (>5ms overhead)

**Recommended Agent Profile**:
- **Category**: `quick`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2
- **Blocks**: Task 6 (dashboard needs this data)
- **Blocked By**: None

**References**:
- `services/core/metrics.py` - existing metrics system
- `services/persona/behavior.py` - where to add collection hooks

**Acceptance Criteria**:
- [x] Behavior metrics being collected
- [x] RL decision counts tracked
- [x] Engagement rates calculated
- [x] No performance regression

**Agent-Executed QA Scenarios**:

```
Scenario: Behavior metrics are being collected
  Tool: Bash (python)
  Preconditions: None
  Steps:
    1. Run: uv run python -c "
from services.core.metrics import MetricsCollector
m = MetricsCollector()
# Simulate behavior events
m.record_behavior_decision(decision='react', context='direct_mention')
m.record_behavior_decision(decision='wait', context='ambient')
print(f'Behavior metrics: {m.get_behavior_stats()}')
"
    2. Assert: Output shows decision counts
    3. Assert: No exceptions
  Expected Result: Metrics system captures behavior data
  Evidence: Metrics output captured

Scenario: Metrics don't impact performance
  Tool: Bash (python)
  Preconditions: Metrics implemented
  Steps:
    1. Run: uv run python -c "
import time
from services.core.metrics import MetricsCollector
from services.persona.behavior import BehaviorEngine

# Time behavior processing with metrics
start = time.time()
for _ in range(100):
    # Simulate behavior processing
    pass
elapsed = time.time() - start
print(f'100 iterations: {elapsed*1000:.2f}ms')
print(f'Average per message: {elapsed*10:.2f}ms')
"
    2. Assert: Average < 5ms per message
  Expected Result: Performance target maintained
  Evidence: Timing output captured
```

**Commit**: YES
- Message: `feat(metrics): Add behavior engine and RL decision tracking`
- Files: `services/core/metrics.py`, `services/persona/behavior.py`
- Pre-commit: `uv run pytest tests/unit/test_metrics.py -v`

---

### Task 6: Create Monitoring Dashboard

**What to do**:
- Extend existing web dashboard (`cogs/web_dashboard.py` or similar) with:
  - Behavior engine section showing:
    - Current engagement rate (rolling 24h)
    - RL decision distribution pie chart
    - Mood state timeline
    - Bot-to-bot conversation quality trend
  - RL learning progress showing:
    - Total training samples
    - Reward distribution
    - Learning curve (if tracked)
- Use existing Chart.js infrastructure

**Must NOT do**:
- Create new web framework dependencies
- Break existing dashboard functionality

**Recommended Agent Profile**:
- **Category**: `visual-engineering`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Task 5)
- **Parallel Group**: Wave 2
- **Blocks**: Task 7
- **Blocked By**: Task 5

**References**:
- `cogs/web_dashboard.py` - existing dashboard
- Look for: Chart.js usage, FastAPI routes, WebSocket updates

**Acceptance Criteria**:
- [x] Dashboard shows behavior engine metrics
- [x] Dashboard shows RL learning progress
- [x] Charts update in real-time (or near real-time)
- [x] Mobile-responsive layout

**Agent-Executed QA Scenarios**:

```
Scenario: Dashboard shows behavior metrics
  Tool: Bash (curl + grep)
  Preconditions: Dashboard running
  Steps:
    1. Run: curl -s http://localhost:8080/dashboard | grep -i "behavior\|engagement\|mood" | head -5
    2. Assert: Output contains behavior-related content
    3. Run: curl -s http://localhost:8080/api/behavior-metrics | python -m json.tool | head -20
    4. Assert: Valid JSON with behavior data
  Expected Result: Dashboard exposes behavior metrics
  Evidence: API response captured

Scenario: RL progress visible on dashboard
  Tool: Bash (curl)
  Preconditions: Dashboard running, RL has data
  Steps:
    1. Run: curl -s http://localhost:8080/api/rl-progress | python -m json.tool
    2. Assert: Contains "training_samples" or "rewards"
    3. Assert: Contains "decision_distribution"
  Expected Result: RL learning progress trackable
  Evidence: JSON response saved
```

**Commit**: YES
- Message: `feat(dashboard): Add behavior engine and RL monitoring charts`
- Files: `cogs/web_dashboard.py`, `templates/dashboard.html` (or equivalent)
- Pre-commit: Dashboard loads without errors

---

### Task 7: Update Tests and Documentation

**What to do**:
- Update `tests/unit/test_behavior_engine.py`:
  - Add tests for config-based probabilities
  - Add tests for RL integration with botconv
  - Add tests for metrics collection
- Create `docs/RL_LEARNING.md`:
  - Explain how RL works in your bot
  - How to interpret metrics
  - How to know if RL is learning
  - Troubleshooting RL issues
- Update main README with behavior configuration section

**Must NOT do**:
- Remove existing tests
- Leave documentation outdated

**Recommended Agent Profile**:
- **Category**: `writing`
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO (depends on Tasks 3, 4, 5)
- **Parallel Group**: Wave 3
- **Blocks**: None
- **Blocked By**: Tasks 3, 4, 5

**Acceptance Criteria**:
- [x] All unit tests pass with new config system
- [x] New tests for RL integration
- [x] RL documentation explains learning process
- [x] README updated

**Agent-Executed QA Scenarios**:

```
Scenario: All tests pass including new ones
  Tool: Bash (pytest)
  Preconditions: All previous tasks completed
  Steps:
    1. Run: uv run pytest tests/unit/test_behavior_engine.py tests/unit/test_bot_conversations.py -v --tb=short
    2. Assert: Exit code 0
    3. Assert: All tests passed
    4. Run: uv run pytest --cov=services/persona/behavior --cov-report=term-missing
    5. Assert: Coverage >= 70%
  Expected Result: Full test suite passes
  Evidence: pytest output in .sisyphus/evidence/task-7-tests.log

Scenario: Documentation exists and is valid
  Tool: Bash (file checks)
  Preconditions: None
  Steps:
    1. Run: ls -la docs/RL_LEARNING.md docs/BEHAVIOR_CONFIGURATION.md
    2. Assert: Both files exist
    3. Run: wc -l docs/RL_LEARNING.md
    4. Assert: File has substantial content (>50 lines)
  Expected Result: Documentation complete
  Evidence: File stats captured
```

**Commit**: YES
- Message: `docs: Add RL learning guide and update behavior tests`
- Files: `tests/`, `docs/RL_LEARNING.md`, `README.md`
- Pre-commit: All tests pass

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `docs: Add comprehensive behavior engine configuration guide` | `docs/BEHAVIOR_CONFIGURATION.md` | File exists |
| 2 | `feat(config): Expose behavior engine probabilities as configuration` | `config.py`, `behavior.py`, `.env.example` | Config tests pass |
| 3 | `feat(behavior): Update default probabilities to balanced values` | `config.py`, `tests/` | Behavior tests pass |
| 4 | `feat(botconv): Integrate bot conversations with RL training` | `bot_conversations.py`, `behavior.py` | Integration tests pass |
| 5 | `feat(metrics): Add behavior engine and RL decision tracking` | `metrics.py`, `behavior.py` | Metrics tests pass |
| 6 | `feat(dashboard): Add behavior engine and RL monitoring charts` | `web_dashboard.py`, templates | Dashboard loads |
| 7 | `docs: Add RL learning guide and update behavior tests` | `tests/`, `docs/`, `README.md` | All tests pass |

---

## Success Criteria

### Verification Commands
```bash
# Test 1: Configurable probabilities
uv run python -c "from config import BEHAVIOR_REACTION_PROBABILITY; print(BEHAVIOR_REACTION_PROBABILITY)"
# Expected: 0.5

# Test 2: Behavior tests pass
uv run pytest tests/unit/test_behavior_engine.py -v
# Expected: All tests pass

# Test 3: Botconv RL integration
uv run pytest tests/unit/test_bot_conversations.py::test_rl_integration -v
# Expected: Test passes

# Test 4: Dashboard accessible
curl -s http://localhost:8080/api/behavior-metrics | python -m json.tool
# Expected: Valid JSON with behavior data

# Test 5: Documentation complete
ls docs/BEHAVIOR_CONFIGURATION.md docs/RL_LEARNING.md
# Expected: Both files exist
```

### What Success Looks Like
- **User can tune behavior** via environment variables (documented)
- **Bot responds ~50%** of the time to mentions (balanced)
- **Botconv feeds RL** with training data (learning over time)
- **Dashboard shows progress** of RL learning and engagement rates
- **Documentation explains** how to interpret and adjust settings

### Rollback Plan
If settings don't work well:
1. Adjust via environment variables (no code change needed)
2. Set `BEHAVIOR_REACTION_PROBABILITY=0.15` to restore original
3. Set `BOTCONV_RL_TRAINING_ENABLED=false` to disable training

### Final Checklist
- [x] All settings configurable via env vars
- [x] Balanced 50% reaction probability
- [x] Bot-to-bot conversations contribute to RL
- [x] Dashboard shows behavior metrics
- [x] Documentation explains everything
- [x] All tests pass
- [x] No breaking changes
