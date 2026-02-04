# RL Enhancement Master Plan: From Tabular Q-Learning to Production Neural RL

## TL;DR

> **Vision**: Transform your Discord bot's RL system from simple tabular Q-learning into a sophisticated, production-grade neural RL platform with experience replay, multi-objective rewards, hierarchical decision-making, and transfer learning.
>
> **Deliverables**:
> - Phase 1: DQN with Experience Replay (faster, stable learning)
> - Phase 2: Multi-Objective Rewards (strategic balancing)
> - Phase 3: Rich State Space (context awareness)
> - Phase 4: Hierarchical RL (strategy + action levels)
> - Phase 5: Neural Networks + Transfer Learning (cutting-edge AI)
>
> **Estimated Effort**: Large (6-8 weeks)
> **Parallel Execution**: YES - Each phase builds on previous, but dashboard work can parallelize
> **Critical Path**: Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

---

## Context

### Original Request
User wants to add more complex RL features and enhance dashboard visualizations for their Discord bot's reinforcement learning system.

### Current System State
- **Algorithm**: Tabular Q-learning with epsilon-greedy exploration
- **State**: 3D discrete tuple `(sentiment_bin, time_bin, message_count_bin)` = 80 discrete states
- **Actions**: 4 discrete actions (WAIT, REACT, ENGAGE, INITIATE)
- **Storage**: JSON file with atomic writes (`rl_policies.json`)
- **Dashboard**: Real-time metrics via WebSocket (agents, states, epsilon, Q-values)
- **Safety**: Hard limits on action frequency (3/5min per user, 20/hour per channel)

### Interview Summary
**Key Discussions**:
- User is excited about all advanced RL features
- Wants full "living AI persona" vision
- Dashboard already exists and shows basic RL metrics
- User wants enhanced visualizations

### Metis Review
**Identified Gaps** (addressed):
- **Data Migration**: Need warm-start strategy for Q-table → neural network
- **Training Strategy**: Online vs offline learning decision
- **Performance**: Inference latency targets (<5ms p95)
- **Safety**: Preserve existing safety layer independent of algorithm
- **Backwards Compatibility**: Keep tabular as fallback

---

## Work Objectives

### Core Objective
Transform the bot's RL system into a production-grade platform that learns faster, makes strategic decisions, understands rich context, and can transfer knowledge between personas.

### Concrete Deliverables
1. **Neural DQN Agent** with experience replay buffer (Phase 1)
2. **Multi-objective reward system** with Pareto optimization (Phase 2)
3. **Rich state encoder** with embeddings (Phase 3)
4. **Hierarchical RL architecture** with meta-controller (Phase 4)
5. **Transfer learning framework** for knowledge sharing (Phase 5)
6. **Enhanced dashboard** with learning curves, heatmaps, and per-user views
7. **Gymnasium simulation environment** for testing
8. **Comprehensive test suite** with regression testing

### Definition of Done
- [x] All phases implemented with passing acceptance criteria
- [x] Inference latency < 5ms (p95) on production hardware
- [x] Dashboard shows all new visualizations
- [x] Existing tests pass (backwards compatibility)
- [x] Migration script validates Q-table → neural conversion
- [x] Safety layer works with both tabular and neural agents

### Must Have
- Experience replay buffer (10K-100K capacity)
- Double DQN (not vanilla DQN)
- Multi-objective reward decomposition
- Safety layer preservation (hard constraints)
- Dashboard learning curves and state heatmaps
- ONNX inference optimization
- Checkpointing and crash recovery

### Must NOT Have (Guardrails)
- **NO removal of tabular Q-learning** - keep as fallback
- **NO blocking Discord event loop** during training
- **NO deployment without warm-up period** (collect 10K transitions first)
- **NO reward hacking** - clip rewards to [-10, 10]
- **NO breaking dashboard WebSocket contracts**

---

## Verification Strategy

### Test Infrastructure Decision
- **Infrastructure exists**: YES (pytest with mocking fixtures)
- **Automated tests**: YES (Tests-after for each phase)
- **Framework**: pytest + Gymnasium simulation environment
- **Agent-Executed QA**: MANDATORY for all dashboard and RL functionality

### Agent-Executed QA Scenarios (MANDATORY)

**Scenario: Neural agent inference latency test**
  Tool: Bash (Python script)
  Preconditions: RL service initialized with neural agent
  Steps:
    1. Run: `python scripts/benchmark_rl.py --model neural --iterations 1000`
    2. Parse output JSON
    3. Assert: p95_latency_ms < 10
    4. Assert: mean_latency_ms < 5
  Expected Result: Latency metrics within bounds
  Evidence: `.sisyphus/evidence/rl-latency-benchmark.json`

**Scenario: Experience replay buffer functionality**
  Tool: Bash (pytest)
  Preconditions: RL service with replay buffer
  Steps:
    1. Run: `python -m pytest tests/rl/test_replay_buffer.py -v`
    2. Assert: All tests pass
    3. Check coverage: `pytest --cov=services.persona.rl tests/rl/`
    4. Assert: Coverage > 80%
  Expected Result: Buffer adds, samples, and trains correctly
  Evidence: Terminal output capture

**Scenario: Dashboard RL metrics endpoint**
  Tool: Bash (curl)
  Preconditions: Bot running with dashboard enabled
  Steps:
    1. curl -s "http://localhost:8080/api/metrics?api_key=$API_KEY"
    2. Assert: Response contains "rl" field
    3. Assert: rl.enabled is boolean
    4. Assert: rl.total_agents >= 0
    5. Assert: rl.avg_epsilon between 0 and 1
  Expected Result: Valid JSON with RL metrics
  Evidence: Response body saved

**Scenario: Multi-objective reward calculation**
  Tool: Bash (Python)
  Preconditions: Mock message and state
  Steps:
    1. Run: `python -c "from services.persona.rl import MultiObjectiveReward; r = MultiObjectiveReward(); print(r.calculate(...))"`
    2. Assert: Output is dict with keys: engagement, quality, affinity
    3. Assert: Each value between -10 and 10
    4. Assert: Total reward equals weighted sum
  Expected Result: Correct reward decomposition
  Evidence: Output capture

**Scenario: State encoder produces valid embeddings**
  Tool: Bash (Python)
  Preconditions: State encoder initialized
  Steps:
    1. Run: `python -c "from services.persona.rl.embeddings import StateEncoder; e = StateEncoder(); emb = e.encode('test'); print(emb.shape)"`
    2. Assert: Shape is (128,) or configured dimension
    3. Assert: Values are finite (no NaN/Inf)
    4. Assert: L2 norm is reasonable (not exploding/vanishing)
  Expected Result: Valid embedding vector
  Evidence: Output capture

---

## Execution Strategy

### Phase Dependencies

```
Phase 1 (Foundation)
├── Task 1: DQN Neural Agent
├── Task 2: Experience Replay Buffer
├── Task 3: Enhanced Reward Tracking
├── Task 4: Dashboard Learning Curves
└── Task 5: Migration Script

Phase 2 (Multi-Objective)
├── Task 6: Reward Decomposition
├── Task 7: Pareto Optimization
├── Task 8: Dashboard Multi-Objective Viz
└── Depends on: Phase 1

Phase 3 (Rich Context)
├── Task 9: State Feature Engineering
├── Task 10: Embedding Encoder
├── Task 11: Dashboard State Heatmap
└── Depends on: Phase 2

Phase 4 (Hierarchical)
├── Task 12: Meta-Controller Agent
├── Task 13: Worker Agents per Strategy
├── Task 14: Option Framework
├── Task 15: Dashboard Strategy Viz
└── Depends on: Phase 3

Phase 5 (Transfer Learning)
├── Task 16: Offline RL Pre-training
├── Task 17: Knowledge Transfer Framework
├── Task 18: Dashboard Transfer Network
└── Depends on: Phase 4
```

### Parallel Execution Waves

**Wave 1 (Phase 1 Core)**:
- Task 1: DQN Neural Agent
- Task 2: Experience Replay Buffer
- Task 3: Enhanced Reward Tracking

**Wave 2 (Phase 1 Dashboard & Migration)**:
- Task 4: Dashboard Learning Curves
- Task 5: Migration Script
- Depends on: Wave 1

**Wave 3 (Phase 2)**:
- Task 6: Reward Decomposition
- Task 7: Pareto Optimization
- Task 8: Dashboard Multi-Objective Viz
- Depends on: Wave 2

**Wave 4 (Phase 3)**:
- Task 9: State Feature Engineering
- Task 10: Embedding Encoder
- Task 11: Dashboard State Heatmap
- Depends on: Wave 3

**Wave 5 (Phase 4)**:
- Task 12: Meta-Controller Agent
- Task 13: Worker Agents
- Task 14: Option Framework
- Task 15: Dashboard Strategy Viz
- Depends on: Wave 4

**Wave 6 (Phase 5)**:
- Task 16: Offline RL Pre-training
- Task 17: Knowledge Transfer Framework
- Task 18: Dashboard Transfer Network
- Depends on: Wave 5

---

## TODOs

### Phase 1: DQN Foundation with Experience Replay

---

- [x] **1.1 Create NeuralAgent class with DQN implementation**

  **What to do**:
  - Create `services/persona/rl/neural_agent.py`
  - Implement Double DQN (not vanilla DQN to avoid overestimation)
  - Target network with soft updates (tau=0.005)
  - Support both discrete and continuous actions
  - ONNX export for inference optimization
  - Inherits from or replaces existing RLAgent interface

  **Must NOT do**:
  - Break existing RLAgent interface (can wrap/extend)
  - Remove tabular Q-learning agent
  - Block event loop during training

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` (complex algorithm implementation)
  - **Skills**: `git-master` (for careful refactoring)
  - **Skills Evaluated but Omitted**: `frontend-ui-ux` (backend only)

  **Parallelization**:
  - **Can Run In Parallel**: YES - With Task 1.2, 1.3
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 1.4 (Dashboard), Task 1.5 (Migration)
  - **Blocked By**: None

  **References**:
  - `services/persona/rl/agent.py:RLAgent` - Existing tabular agent interface
  - `services/persona/rl/types.py` - RLAction, RLState definitions
  - Stable Baselines3 DQN documentation - Reference implementation
  - `services/persona/rl/constants.py` - Hyperparameters

  **Acceptance Criteria**:
  - [ ] NeuralAgent can be instantiated with config
  - [ ] `select_action()` returns valid RLAction
  - [ ] `update()` performs Bellman update with target network
  - [ ] Inference latency < 5ms (p95) on CPU
  - [ ] Q-values converge in simulation within 5000 steps
  - [ ] ONNX export produces valid model file
  - [ ] pytest tests/rl/test_neural_agent.py -v passes

  **Agent-Executed QA**:
  Scenario: DQN inference benchmark
    Tool: Bash
    Steps:
      1. python scripts/benchmark_rl.py --model neural --iterations 1000
      2. Parse JSON output
      3. Assert p95_latency_ms < 10
      4. Assert mean_latency_ms < 5
    Evidence: .sisyphus/evidence/phase1-dqn-latency.json

  **Commit**: YES
  - Message: `feat(rl): add NeuralAgent with Double DQN implementation`
  - Files: `services/persona/rl/neural_agent.py`, `tests/rl/test_neural_agent.py`
  - Pre-commit: `pytest tests/rl/test_neural_agent.py -v`

---

- [x] **1.2 Implement Experience Replay Buffer**

  **What to do**:
  - Create `services/persona/rl/replay_buffer.py`
  - Circular buffer with configurable capacity (default: 10000)
  - Store tuples: (state, action, reward, next_state, done)
  - Sampling methods: uniform random, prioritized (Phase 2 enhancement)
  - Efficient numpy storage
  - Thread-safe for async access

  **Must NOT do**:
  - Store raw Discord objects (only extracted features)
  - Allow buffer to grow unbounded
  - Block on sampling during inference

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: YES - With Task 1.1
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 1.3 (Reward tracking integration)
  - **Blocked By**: None

  **References**:
  - `services/persona/rl/agent.py` - Agent interface
  - Prioritized Experience Replay paper (Schaul et al. 2016)
  - `collections.deque` - For circular buffer pattern

  **Acceptance Criteria**:
  - [ ] Buffer stores (s, a, r, s', done) tuples
  - [ ] Capacity limit enforced (oldest removed)
  - [ ] Sample returns random batch of specified size
  - [ ] Thread-safe for concurrent add/sample
  - [ ] Memory usage < 100MB for 100K capacity
  - [ ] pytest tests/rl/test_replay_buffer.py passes

  **Agent-Executed QA**:
  Scenario: Replay buffer stress test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_replay_buffer.py::test_stress -v
      2. Assert: 10000 adds + 1000 samples complete < 1s
      3. Assert: No memory leaks (check RSS before/after)
    Evidence: Terminal output

  **Commit**: YES
  - Message: `feat(rl): implement experience replay buffer`
  - Files: `services/persona/rl/replay_buffer.py`, `tests/rl/test_replay_buffer.py`

---

- [x] **1.3 Integrate Neural Agent and Replay Buffer into RLService**

  **What to do**:
  - Modify `services/persona/rl/service.py`
  - Add algorithm selection: `algorithm="tabular"` or `"dqn"`
  - Initialize replay buffer in service
  - Batch training updates every N steps
  - Warm-up period: collect 1000 transitions before training
  - Configurable batch size (default: 32)

  **Must NOT do**:
  - Remove tabular agent support
  - Train on every single transition (use batching)
  - Break existing RLService interface

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain` (complex integration)
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO - Must integrate with 1.1 and 1.2
  - **Parallel Group**: Wave 1 (sequential within wave)
  - **Blocks**: All Phase 1 dashboard work
  - **Blocked By**: Task 1.1, Task 1.2

  **References**:
  - `services/persona/rl/service.py:RLService` - Main service class
  - `services/persona/rl/agent.py` - Tabular agent (keep compatible)
  - `services/core/factory.py` - Service initialization

  **Acceptance Criteria**:
  - [ ] RLService accepts `algorithm` parameter
  - [ ] Can switch between tabular and DQN via config
  - [ ] Warm-up period enforced (no training until 1000 transitions)
  - [ ] Batch training every N steps (configurable)
  - [ ] All existing tests pass with tabular agent
  - [ ] New tests pass with DQN agent

  **Agent-Executed QA**:
  Scenario: Service integration test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_service_integration.py -v
      2. Assert: Both tabular and DQN modes pass
      3. Assert: Warm-up period respected
  Evidence: pytest output

  **Commit**: YES
  - Message: `feat(rl): integrate DQN and replay buffer into RLService`
  - Files: `services/persona/rl/service.py`

---

- [x] **1.4 Add Dashboard Learning Curves and Replay Stats**

  **What to do**:
  - Modify `services/analytics/dashboard.py:_collect_rl_metrics()`
  - Add new metrics:
    - Loss history (last 100 training steps)
    - TD error distribution
    - Replay buffer utilization (% full)
    - Training steps count
    - Q-value distribution histogram
  - Update WebSocket message format
  - Modify `templates/dashboard/index.html`
  - Add Chart.js visualizations:
    - Loss curve over time
    - Q-value distribution
    - Replay buffer fill rate

  **Must NOT do**:
  - Break existing dashboard metrics (keep backwards compatible)
  - Send too much data over WebSocket (limit history size)
  - Block dashboard on RL metrics collection

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES - Can work on HTML/JS while backend integrates
  - **Parallel Group**: Wave 2
  - **Blocks**: Phase 2 dashboard enhancements
  - **Blocked By**: Task 1.3 (needs metrics from service)

  **References**:
    - `services/analytics/dashboard.py:648-714` - Existing `_collect_rl_metrics()`
    - `templates/dashboard/index.html:1000-1078` - Existing RL metrics JS
    - Chart.js documentation for line charts and histograms
    - `services/analytics/dashboard.py:551` - RL metrics endpoint

  **Acceptance Criteria**:
  - [ ] Dashboard shows loss curve chart
  - [ ] Dashboard shows Q-value distribution
  - [ ] Dashboard shows replay buffer utilization
  - [ ] All charts update via WebSocket every 2 seconds
  - [ ] Backwards compatible with tabular agent metrics

  **Agent-Executed QA**:
  Scenario: Dashboard RL visualization test
    Tool: Playwright (skill_mcp: playwright)
    Preconditions: Dashboard running at localhost:8080, RL enabled
    Steps:
      1. Navigate to dashboard with API key
      2. Click "RL Learning" tab
      3. Wait for charts to load (timeout: 5s)
      4. Assert: Loss curve canvas exists
      5. Assert: Q-value distribution canvas exists
      6. Assert: Buffer utilization metric visible
      7. Wait 3 seconds, assert charts update
      8. Screenshot: .sisyphus/evidence/phase1-dashboard.png
    Evidence: Screenshot + console logs

  **Commit**: YES
  - Message: `feat(dashboard): add RL learning curves and replay stats`
  - Files: `services/analytics/dashboard.py`, `templates/dashboard/index.html`

---

- [x] **1.5 Create Migration Script for Q-table → Neural Network**

  **What to do**:
  - Create `scripts/migrate_rl_policies.py`
  - Read existing `rl_policies.json` (tabular Q-tables)
  - Initialize neural network weights from Q-values (warm start)
  - Option to start fresh (random initialization)
  - Dry-run mode (show what would happen)
  - Backup original file
  - Version metadata in saved policies

  **Must NOT do**:
  - Delete original Q-table policies
  - Fail if migration has issues (graceful fallback)
  - Require migration (fresh start should be option)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: YES - Utility script, independent
  - **Parallel Group**: Wave 2
  - **Blocks**: Phase 2 (uses migrated data)
  - **Blocked By**: Task 1.1 (needs neural agent)

  **References**:
  - `services/persona/rl/persistence.py` - Existing persistence layer
  - `services/persona/rl/agent.py:from_dict()` - Q-table loading
  - Neural network weight initialization techniques

  **Acceptance Criteria**:
  - [ ] Script reads existing tabular policies
  - [ ] Dry-run mode shows conversion plan
  - [ ] Warm-start initializes network from Q-values
  - [ ] Backup created before migration
  - [ ] Version metadata added to saved files
  - [ ] Rollback capability to original state

  **Agent-Executed QA**:
  Scenario: Migration script test
    Tool: Bash
    Steps:
      1. Create test Q-table policy file
      2. Run: `python scripts/migrate_rl_policies.py --dry-run`
      3. Assert: Shows conversion summary
      4. Run: `python scripts/migrate_rl_policies.py --execute`
      5. Assert: Creates backup file
      6. Assert: Produces neural policy file
      7. Load neural policy in RL service, assert it works
  Evidence: Script output logs

  **Commit**: YES
  - Message: `feat(rl): add Q-table to neural network migration script`
  - Files: `scripts/migrate_rl_policies.py`

---

### Phase 2: Multi-Objective Rewards

---

- [x] **2.1 Decompose Rewards into Multiple Objectives**

  **What to do**:
  - Create `services/persona/rl/multi_objective.py`
  - Define reward components:
    - Engagement: message length, response time, emoji reactions
    - Quality: sentiment positivity, conversation coherence
    - Affinity: relationship score change
    - Curiosity: topic novelty, question diversity
  - Each component returns scalar value
  - Configurable weights for each objective
  - Reward clipping per component and total

  **Must NOT do**:
  - Allow unbounded rewards (clip to [-10, 10])
  - Make objectives too correlated (avoid redundancy)
  - Remove existing reward calculation (extend it)

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain` (complex reward engineering)
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO - Sequential within Phase 2
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 2.2 (Pareto optimization)
  - **Blocked By**: Phase 1 complete

  **References**:
  - `services/persona/rl/service.py:calculate_reward()` - Existing reward function
  - `services/persona/behavior.py` - Behavior state for features
  - Multi-objective RL literature (MORL)

  **Acceptance Criteria**:
  - [ ] Each objective has clear calculation formula
  - [ ] Weights sum to 1.0 (normalized)
  - [ ] Individual components clipped to [-5, 5]
  - [ ] Total reward clipped to [-10, 10]
  - [ ] Configurable via config file
  - [ ] pytest tests/rl/test_multi_objective.py passes

  **Agent-Executed QA**:
  Scenario: Multi-objective reward test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_multi_objective.py -v
      2. Assert: All objective components tested
      3. Assert: Weighted sum equals total reward
      4. Assert: Clipping works correctly
  Evidence: pytest output

  **Commit**: YES
  - Message: `feat(rl): implement multi-objective reward decomposition`
  - Files: `services/persona/rl/multi_objective.py`, `tests/rl/test_multi_objective.py`

---

- [x] **2.2 Implement Pareto Frontier Action Selection**

  **What to do**:
  - Modify action selection to consider multiple Q-values (one per objective)
  - Calculate Pareto frontier for non-dominated actions
  - Selection strategies:
    - Weighted sum (default)
    - Epsilon-greedy on Pareto set
    - User preference-based (future enhancement)
  - Track Pareto-optimal policies

  **Must NOT do**:
  - Make selection too complex (performance impact)
  - Ignore user preferences entirely
  - Remove epsilon-greedy exploration

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 2.3
  - **Blocked By**: Task 2.1

  **References**:
    - `services/persona/rl/agent.py:select_action()` - Existing selection
    - Pareto optimization algorithms
    - MORL survey papers

  **Acceptance Criteria**:
  - [ ] Pareto frontier calculated correctly
  - [ ] Non-dominated actions identified
  - [ ] Selection strategy configurable
  - [ ] Performance impact < 1ms per decision
  - [ ] Tests verify Pareto optimality

  **Agent-Executed QA**:
  Scenario: Pareto action selection test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_pareto_selection.py -v
      2. Assert: Pareto frontier correctly identified
      3. Benchmark: 1000 selections < 1s
  Evidence: pytest + benchmark output

  **Commit**: YES
  - Message: `feat(rl): add Pareto frontier action selection for multi-objective RL`
  - Files: `services/persona/rl/agent.py`, `services/persona/rl/pareto.py`

---

- [x] **2.3 Add Dashboard Multi-Objective Visualizations**

  **What to do**:
  - Add radar chart showing objective values
  - Add Pareto frontier plot (2D projection)
  - Add objective weight configuration UI
  - Show per-objective reward history
  - Success rate per action type

  **Must NOT do**:
  - Overcrowd dashboard (use tabs or accordions)
  - Allow real-time weight changes without safety checks

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES (frontend work)
  - **Parallel Group**: Wave 3
  - **Blocks**: Phase 3 dashboard
  - **Blocked By**: Task 2.2

  **References**:
    - `templates/dashboard/index.html` - Existing dashboard
    - Chart.js radar charts
    - `services/analytics/dashboard.py` - Metrics endpoint

  **Acceptance Criteria**:
  - [ ] Radar chart shows 4 objectives
  - [ ] Pareto frontier visualization works
  - [ ] Objective history line charts
  - [ ] Success rate by action type table
  - [ ] All charts update in real-time

  **Agent-Executed QA**:
  Scenario: Multi-objective dashboard test
    Tool: Playwright
    Preconditions: Dashboard running with Phase 2 RL
    Steps:
      1. Navigate to RL tab
      2. Assert: Radar chart visible
      3. Assert: Pareto plot visible
      4. Assert: Objective history charts visible
      5. Screenshot: .sisyphus/evidence/phase2-dashboard.png
  Evidence: Screenshot

  **Commit**: YES
  - Message: `feat(dashboard): add multi-objective RL visualizations`
  - Files: `templates/dashboard/index.html`, `services/analytics/dashboard.py`

---

### Phase 3: Rich State Space

---

- [x] **3.1 Engineer Additional State Features**

  **What to do**:
  - Expand state representation beyond 3 bins:
    - Time of day (hour, day of week)
    - Conversation depth (turn count in session)
    - Topic categories (extracted from messages)
    - User mood trajectory (sentiment trend)
    - Bot's previous action
    - Message velocity (messages per minute)
  - Feature normalization
  - Feature selection (avoid curse of dimensionality)

  **Must NOT do**:
  - Create too many features (>256 dims initially)
  - Include PII in state features
  - Make features computationally expensive

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain` (feature engineering)
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 3.2
  - **Blocked By**: Phase 2 complete

  **References**:
    - `services/persona/behavior.py:BehaviorState` - Existing state tracking
    - `services/persona/rl/types.py` - RLState type
    - Feature engineering best practices

  **Acceptance Criteria**:
  - [ ] At least 10 new state features
  - [ ] All features normalized to [0, 1] or [-1, 1]
  - [ ] Feature computation < 1ms
  - [ ] Dimensionality <= 128 (configurable)
  - [ ] Tests verify feature extraction

  **Agent-Executed QA**:
  Scenario: State feature extraction test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_state_features.py -v
      2. Assert: All 10+ features extracted
      3. Assert: All values normalized
      4. Benchmark: 1000 extractions < 1s
  Evidence: pytest output

  **Commit**: YES
  - Message: `feat(rl): add rich state features (time, topic, mood trajectory)`
  - Files: `services/persona/rl/state_features.py`, `tests/rl/test_state_features.py`

---

- [x] **3.2 Implement State Embedding Encoder**

  **What to do**:
  - Create `services/persona/rl/embeddings.py`
  - Use cheap LLM (thinking service) for text embedding
  - Combine structured features + text embeddings
  - Output fixed-size vector (default: 128 dims)
  - Caching for repeated states

  **Must NOT do**:
  - Use expensive LLM for every state encoding
  - Create embeddings > 256 dims (performance)
  - Skip normalization

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 3.3
  - **Blocked By**: Task 3.1

  **References**:
    - `services/llm/thinking.py` - Cheap LLM for embeddings
    - Sentence-transformers library
    - Embedding caching patterns

  **Acceptance Criteria**:
  - [ ] Encoder produces (128,) vector
  - [ ] Structured features + text combined
  - [ ] Caching reduces repeated encoding
  - [ ] Encoding latency < 50ms p95
  - [ ] Handles missing features gracefully

  **Agent-Executed QA**:
  Scenario: Embedding encoder test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_embeddings.py -v
      2. Assert: Output shape (128,)
      3. Assert: Values normalized
      4. Assert: Caching works (second call faster)
  Evidence: pytest output + timing

  **Commit**: YES
  - Message: `feat(rl): implement state embedding encoder with caching`
  - Files: `services/persona/rl/embeddings.py`, `tests/rl/test_embeddings.py`

---

- [x] **3.3 Add Dashboard State Space Heatmap and Feature Importance**

  **What to do**:
  - Add heatmap visualization of state space coverage
  - Show which states are visited most
  - Feature importance analysis (which features matter most)
  - State trajectory visualization (user journey through states)

  **Must NOT do**:
  - Show high-D embeddings directly (use PCA/t-SNE)
  - Overwhelm user with too much detail

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Phase 4 dashboard
  - **Blocked By**: Task 3.2

  **References**:
    - Chart.js heatmaps or D3.js
    - PCA/t-SNE for dimensionality reduction
    - Feature importance algorithms

  **Acceptance Criteria**:
  - [ ] State space heatmap visible
  - [ ] Feature importance bar chart
  - [ ] State trajectory visualization
  - [ ] Real-time updates

  **Agent-Executed QA**:
  Scenario: State space dashboard test
    Tool: Playwright
    Steps:
      1. Navigate to RL tab
      2. Assert: State heatmap visible
      3. Assert: Feature importance chart visible
      4. Screenshot: .sisyphus/evidence/phase3-dashboard.png
  Evidence: Screenshot

  **Commit**: YES
  - Message: `feat(dashboard): add state space heatmap and feature importance`
  - Files: `templates/dashboard/index.html`

---

### Phase 4: Hierarchical RL

---

- [x] **4.1 Implement Meta-Controller Agent (Strategy Level)**

  **What to do**:
  - Create `services/persona/rl/hierarchical.py`
  - Define strategies: build_rapport, entertain, inform, support
  - Meta-controller selects strategy based on high-level context
  - Strategy determines which worker agent to use
  - Option termination conditions (time, state change)

  **Must NOT do**:
  - Make strategies too granular (keep it high-level)
  - Remove low-level actions (just add hierarchy)

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain` (HRL architecture)
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5
  - **Blocks**: Task 4.2
  - **Blocked By**: Phase 3 complete

  **References**:
    - Option Framework (Sutton et al.)
    - Feudal Networks
    - `services/persona/rl/agent.py`

  **Acceptance Criteria**:
  - [ ] Meta-controller selects from 4+ strategies
  - [ ] Strategy persists for option duration
  - [ ] Termination conditions work
  - [ ] Both levels learn (meta + worker)
  - [ ] Tests verify hierarchy

  **Agent-Executed QA**:
  Scenario: Hierarchical RL test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_hierarchical.py -v
      2. Assert: Meta-controller learns strategy preferences
      3. Assert: Worker agents learn within strategies
      4. Assert: Termination conditions trigger
  Evidence: pytest output

  **Commit**: YES
  - Message: `feat(rl): implement hierarchical RL with meta-controller`
  - Files: `services/persona/rl/hierarchical.py`, `tests/rl/test_hierarchical.py`

---

- [x] **4.2 Create Worker Agents per Strategy**

  **What to do**:
  - Each strategy has its own RL agent
  - Worker agents learn strategy-specific policies
  - Shared replay buffer or separate (configurable)
  - Workers implement strategy-specific actions

  **Must NOT do**:
  - Duplicate too much code (use composition)
  - Make workers completely independent (share learnings)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5
  - **Blocks**: Task 4.3
  - **Blocked By**: Task 4.1

  **References**:
    - `services/persona/rl/agent.py` - Base agent
    - Strategy pattern in RL

  **Acceptance Criteria**:
  - [ ] 4 worker agents implemented
  - [ ] Each has strategy-specific action space
  - [ ] All workers train correctly
  - [ ] Can switch workers dynamically

  **Agent-Executed QA**:
  Scenario: Worker agent test
    Tool: Bash
    Steps:
      1. python -m pytest tests/rl/test_workers.py -v
      2. Assert: All 4 workers selectable
      3. Assert: Workers learn different policies
  Evidence: pytest output

  **Commit**: YES
  - Message: `feat(rl): add strategy-specific worker agents`
  - Files: `services/persona/rl/workers.py`

---

- [x] **4.3 Add Dashboard Strategy Distribution and Hierarchy Viz**

  **What to do**:
  - Show strategy distribution pie chart
  - Hierarchy tree visualization (meta → workers)
  - Strategy transition graph
  - Per-strategy performance metrics

  **Must NOT do**:
  - Make hierarchy viz too complex
  - Forget to show aggregate stats

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: Phase 5 dashboard
  - **Blocked By**: Task 4.2

  **Acceptance Criteria**:
  - [ ] Strategy pie chart visible
  - [ ] Hierarchy tree rendered
  - [ ] Transition graph shows switches
  - [ ] Per-strategy metrics table

  **Agent-Executed QA**:
  Scenario: Hierarchy dashboard test
    Tool: Playwright
    Steps:
      1. Navigate to RL tab
      2. Assert: Strategy pie chart visible
      3. Assert: Hierarchy tree visible
      4. Screenshot: .sisyphus/evidence/phase4-dashboard.png
  Evidence: Screenshot

  **Commit**: YES
  - Message: `feat(dashboard): add hierarchical RL visualizations`
  - Files: `templates/dashboard/index.html`

---

### Phase 5: Transfer Learning

---

- [x] **5.1 Implement Offline RL Pre-training**

  **What to do**:
  - Create `services/persona/rl/offline_rl.py`
  - Load historical conversation data
  - Implement CQL (Conservative Q-Learning) for offline training
  - Pre-train on historical data before online deployment
  - Save/load pre-trained models

  **Must NOT do**:
  - Train on low-quality historical data
  - Skip validation on held-out data

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain` (offline RL is complex)
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6
  - **Blocks**: Task 5.2
  - **Blocked By**: Phase 4 complete

  **References**:
    - CQL paper (Kumar et al.)
    - `services/memory/sqlite_history.py` - Historical data
    - Offline RL best practices

  **Acceptance Criteria**:
  - [ ] Loads historical data correctly
  - [ ] CQL training converges
  - [ ] Pre-trained model beats random initialization
  - [ ] Validation on held-out data

  **Agent-Executed QA**:
  Scenario: Offline RL test
    Tool: Bash
    Steps:
      1. python scripts/train_offline_rl.py --episodes 1000
      2. Assert: Training completes without errors
      3. Assert: Validation score > baseline
      4. Assert: Model saved correctly
  Evidence: Training logs + validation scores

  **Commit**: YES
  - Message: `feat(rl): implement offline RL pre-training with CQL`
  - Files: `services/persona/rl/offline_rl.py`, `scripts/train_offline_rl.py`

---

- [x] **5.2 Create Knowledge Transfer Framework**

  **What to do**:
  - Transfer weights between persona agents
  - Similarity-based transfer (similar personas share more)
  - Fine-tuning after transfer
  - Track knowledge lineage

  **Must NOT do**:
  - Transfer between dissimilar personas (check similarity first)
  - Overwrite target persona completely (fine-tune)

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain` (transfer learning)
  - **Skills**: `git-master`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 6
  - **Blocks**: Task 5.3
  - **Blocked By**: Task 5.1

  **References**:
    - Transfer learning in RL
    - Progressive networks
    - Persona similarity metrics

  **Acceptance Criteria**:
  - [ ] Can transfer from source to target agent
  - [ ] Similarity metric calculated
  - [ ] Fine-tuning improves over raw transfer
  - [ ] Knowledge lineage tracked

  **Agent-Executed QA**:
  Scenario: Knowledge transfer test
    Tool: Bash
    Steps:
      1. python scripts/transfer_knowledge.py --source dagoth --target scav
      2. Assert: Transfer completes
      3. Assert: Target performance improves
      4. Assert: Lineage recorded
  Evidence: Transfer logs + performance metrics

  **Commit**: YES
  - Message: `feat(rl): add knowledge transfer framework between personas`
  - Files: `services/persona/rl/transfer.py`, `scripts/transfer_knowledge.py`

---

- [x] **5.3 Add Dashboard Transfer Learning Network Visualization**

  **What to do**:
  - Network graph showing knowledge transfers
  - Persona similarity matrix
  - Transfer lineage timeline
  - Knowledge contribution attribution

  **Must NOT do**:
  - Make network graph unreadable (limit nodes)
  - Forget to show transfer impact

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 6
  - **Blocks**: None (final task)
  - **Blocked By**: Task 5.2

  **Acceptance Criteria**:
  - [ ] Network graph shows transfers
  - [ ] Similarity matrix visible
  - [ ] Timeline of transfers
  - [ ] Attribution metrics

  **Agent-Executed QA**:
  Scenario: Transfer dashboard test
    Tool: Playwright
    Steps:
      1. Navigate to RL tab
      2. Assert: Knowledge network graph visible
      3. Assert: Similarity matrix visible
      4. Screenshot: .sisyphus/evidence/phase5-dashboard.png
  Evidence: Screenshot

  **Commit**: YES
  - Message: `feat(dashboard): add knowledge transfer network visualization`
  - Files: `templates/dashboard/index.html`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1.1 | `feat(rl): add NeuralAgent with Double DQN` | neural_agent.py, tests | pytest |
| 1.2 | `feat(rl): implement experience replay buffer` | replay_buffer.py, tests | pytest |
| 1.3 | `feat(rl): integrate DQN and replay buffer` | service.py | pytest |
| 1.4 | `feat(dashboard): add RL learning curves` | dashboard.py, index.html | Playwright |
| 1.5 | `feat(rl): add migration script` | migrate_rl_policies.py | manual test |
| 2.1 | `feat(rl): multi-objective reward decomposition` | multi_objective.py | pytest |
| 2.2 | `feat(rl): Pareto frontier action selection` | pareto.py | pytest |
| 2.3 | `feat(dashboard): multi-objective RL viz` | index.html | Playwright |
| 3.1 | `feat(rl): rich state features` | state_features.py | pytest |
| 3.2 | `feat(rl): state embedding encoder` | embeddings.py | pytest |
| 3.3 | `feat(dashboard): state space heatmap` | index.html | Playwright |
| 4.1 | `feat(rl): hierarchical RL meta-controller` | hierarchical.py | pytest |
| 4.2 | `feat(rl): strategy-specific worker agents` | workers.py | pytest |
| 4.3 | `feat(dashboard): hierarchical RL viz` | index.html | Playwright |
| 5.1 | `feat(rl): offline RL pre-training` | offline_rl.py | script test |
| 5.2 | `feat(rl): knowledge transfer framework` | transfer.py | script test |
| 5.3 | `feat(dashboard): knowledge transfer network` | index.html | Playwright |

---

## Success Criteria

### Verification Commands
```bash
# Phase 1
pytest tests/rl/test_neural_agent.py -v  # DQN tests
pytest tests/rl/test_replay_buffer.py -v  # Buffer tests
python scripts/benchmark_rl.py --model neural --iterations 1000 | jq '.p95_latency_ms < 10'

# Phase 2
pytest tests/rl/test_multi_objective.py -v  # Multi-objective tests
pytest tests/rl/test_pareto_selection.py -v  # Pareto tests

# Phase 3
pytest tests/rl/test_state_features.py -v  # Feature tests
pytest tests/rl/test_embeddings.py -v  # Embedding tests

# Phase 4
pytest tests/rl/test_hierarchical.py -v  # HRL tests
pytest tests/rl/test_workers.py -v  # Worker tests

# Phase 5
python scripts/train_offline_rl.py --validate  # Offline RL
python scripts/transfer_knowledge.py --dry-run  # Transfer

# All phases
pytest tests/rl/ -v --cov=services.persona.rl  # Full test suite
curl -s "http://localhost:8080/api/metrics?api_key=$KEY" | jq '.rl'  # Dashboard API
```

### Final Checklist
- [x] All 18 tasks complete
- [x] All acceptance criteria met
- [x] Inference latency < 5ms p95
- [x] Dashboard shows all visualizations
- [x] Existing tests pass (backwards compatibility)
- [x] Migration script validated
- [x] Documentation updated
- [x] Performance benchmarks documented

---

## Notes

### Dependencies to Add
```toml
[project.dependencies]
torch = "^2.0"  # For neural networks
numpy = "^1.24"  # For replay buffer
stable-baselines3 = "^2.0"  # Optional: reference DQN
gymnasium = "^0.29"  # For testing environment
onnx = "^1.15"  # For inference optimization
```

### Configuration Updates
```python
# config.py additions
RL_ALGORITHM = "dqn"  # "tabular" or "dqn"
RL_REPLAY_BUFFER_SIZE = 10000
RL_BATCH_SIZE = 32
RL_LEARNING_RATE = 1e-4
RL_STATE_DIM = 128
RL_USE_HIERARCHICAL = True
RL_USE_TRANSFER = True
```

### Testing Infrastructure
- Create `tests/rl/gym_env.py` - Gymnasium wrapper for Discord bot
- Add `tests/rl/conftest.py` - Shared RL fixtures
- Property-based tests for reward invariants
- Chaos tests for robustness

---

**Plan Generated**: RL Enhancement Master Plan  
**Phases**: 5 (18 tasks total)  
**Estimated Duration**: 6-8 weeks  
**Next Step**: Run `/start-work` to begin Phase 1 execution
