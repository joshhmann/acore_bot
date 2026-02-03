# Plan: RL Autonomy for Behavioral Engine

## TL;DR

> **Quick Summary**: Implement a tabular Q-Learning system to drive persona autonomy. The RL agent learns optimal actions (Wait, React, Engage, Initiate) based on a discretized state space, maximizing user engagement and sentiment.
> 
> **Deliverables**:
> - `services/persona/rl/` package (Agent, Service, Safety, Persistence)
> - Integrated `BehaviorEngine` with RL decision loop
> - `data/rl/` storage for learned policies
> 
> **Estimated Effort**: Medium (4-6 hours)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: RL Service → Behavior Integration → Reward Logic → Testing

---

## Technical Specifications (MANDATORY)

### RL Parameters
```python
RL_EPSILON_START = 1.0
RL_EPSILON_END = 0.01
RL_EPSILON_DECAY = 0.9995  # Decay once per user message processed
RL_Q_INIT = 10.0
RL_LEARNING_RATE = 0.1
RL_DISCOUNT_FACTOR = 0.9
RL_PERSIST_INTERVAL = 60
RL_LOCK_TIMEOUT = 0.050
RL_MAX_LATENCY_SEC = 0.050
RL_REWARD_SPEED_THRESHOLD = 60.0 # seconds
RL_REWARD_LONG_MSG_CHAR = 100
RL_CONTEXT_MAX_AGE = 3600
RL_MAX_AGENTS_PER_CHANNEL = 100
```

### Data Structures

**RLAction Enum**:
```python
class RLAction(IntEnum):
    WAIT = 0      # Return (WAIT, None) -> Do nothing
    REACT = 1     # Return (REACT, emoji) -> Call _decide_reaction
    ENGAGE = 2    # Return (ENGAGE, text) -> Call _decide_proactive_engagement(force=False)
    INITIATE = 3  # Return (INITIATE, text) -> Call _decide_proactive_engagement(force=True)
```

**Persistence Format (JSON)**:
```json
{
  "version": 1,
  "agents": {
    "12345:67890": {  # key: "channel_id:user_id" (ints as str)
      "epsilon": 0.5,
      "q_table": {
        "(0,0,0)": {"0": 10.0, "1": 10.0, "2": 10.0, "3": 10.0}
      }
    }
  }
}
```

**Context & Storage**:
- **Key**: `Tuple[int, int]` -> `(channel_id, user_id)` (Both Ints)
- **Agent Storage**: `Dict[Tuple[int, int], RLAgent]` with LRU eviction
- **Locks**: `Dict[Tuple[int, int], asyncio.Lock]`
- **Debounce**: `Dict[int, float]` (user_id -> last_processed_time)

**State Binning** (Inclusive Lower, Exclusive Upper):
```python
def _bin_sentiment(score: float) -> int:
    # [-∞, -0.5)=0, [-0.5, 0.0)=1, [0.0, 0.5)=2, [0.5, +∞)=3
    # Note: -0.5 -> 1, 0.0 -> 2
    if score < -0.5: return 0
    if score < 0.0: return 1
    if score < 0.5: return 2
    return 3
```

### Reward Function (Exact)
Signature:
```python
def calculate_reward(
    previous_action: RLAction,
    current_sentiment: float,  # [-1.0, 1.0]
    affinity_delta: float,     # current - snapshot
    user_reply_latency: float, # Time between bot action and user reply
    user_message_text: str     # Content
) -> float:
```
Formula:
```python
if user_message_text is None: user_message_text = ""
user_reply_latency = max(0.0, user_reply_latency)

# Base terms
r_sentiment = current_sentiment * 1.0
r_affinity = math.tanh(affinity_delta * 0.1) * 5.0
# Speed bonus (if user replied quickly)
r_speed = 0.5 if user_reply_latency < RL_REWARD_SPEED_THRESHOLD else 0.0

# Penalties
r_penalty = 0.0
# Match "stop", "shut up", "quiet"
if re.search(r'\b(?:stop|shut\s*up|quiet)\b', user_message_text.lower()):
    r_penalty -= 2.0
# Penalty for waiting ONLY if user was negative (wanted engagement)
if previous_action == RLAction.WAIT and current_sentiment < -0.3:
    r_penalty -= 0.5

REWARD = r_sentiment + r_affinity + r_speed + r_penalty
REWARD = max(-10.0, min(10.0, REWARD))
```

### Tool Integration Strategy (Hierarchical)
- **RL Role**: Decides STRATEGY (Engage vs Wait).
- **LLM Role**: Decides TACTICS (Use Tool vs Speak).
- **Integration Point**: `BehaviorEngine` injects tool definitions into the system prompt when `RLAction.ENGAGE` or `INITIATE` is selected.
- **MCP Client**: Exposes tools to the LLM via `EnhancedToolSystem`.

---

## TODOs

- [x] 1. Create RL Service Infrastructure

  **What to do**:
  - Create `services/persona/rl/` package.
  - Implement `RLAgent` (Q-table, update logic).
  - Implement `RLService` (Manager with LRU cache, locks).
  - Register in `services/core/factory.py`: `service_factory.register("rl", RLService)`.
  - Update `config.py`: Add `RL_ENABLED=False`, `RL_DATA_DIR` defaults.
  - Add directory creation to `Config.validate`.

  **Acceptance Criteria**:
  - [ ] `agent.update` follows Bellman logic.
    **Verification**: `expected = old + 0.1 * (1.0 + 0.9 * 10.0 - old); assert abs(new_q - expected) < 0.001`
  - [ ] `epsilon` decays after action selection.
    **Verification**: `old=1.0; agent.select_action(s); assert abs(agent.epsilon - (old * 0.9995)) < 0.001`
  - [ ] Unseen states initialize to `RL_Q_INIT`.
    **Verification**: `default_q = {a: RL_Q_INIT for a in RLAction}; row = agent.q_table.get(s, default_q); assert row[RLAction.WAIT] == 10.0`
  - [ ] `RLService` returns `(RLAction.WAIT, None)` if `RL_ENABLED` is False.
    **Verification**: `config.RL_ENABLED=False; assert service.get_action(...) == (RLAction.WAIT, None)`

- [x] 2. Implement Persistence & Safety Layer

  **What to do**:
  - Implement `RLStorage` (JSON load/save, atomic write, error handling).
  - Implement `SafetyLayer` with `UserActionHistory` (key: `(channel_id, user_id)`).
  - Add background save task (60s interval).

  **Acceptance Criteria**:
  - [ ] Rate Limit: Returns `WAIT` if 3x same action in 300s.
    **Verification**: `h.add(REACT, t-20); h.add(REACT, t-10); h.add(REACT, t); assert check(REACT, t) == WAIT`
  - [ ] Global Limit: Returns `WAIT` if >20 actions in channel/hour.
    **Verification**: `for i in range(21): h.add_global(c1, t - i*100); assert check(REACT, c1) == WAIT`
  - [ ] `RLStorage` handles corrupt JSON (logs error, returns empty).
    **Verification**: `write("bad.json", "{"); assert load("bad.json") == {}`
  - [ ] Atomic write uses `.tmp` + `os.replace`.
    **Verification**: `save(); assert path.exists() and not path.with_suffix(".tmp").exists()`

- [x] 3. Integrate RL into BehaviorEngine

  **Path**: `services/persona/behavior.py`
  **Prerequisites**:
  - Verify `_decide_reaction` exists.
  - Verify `_decide_proactive_engagement` exists.
  **What to do**:
  - In `__init__`: `self.rl_service = self.bot.get_service("rl")` (if available).
  - In `handle_message`:
    1. **DEBOUNCE**: If user msg < 5s since last, skip.
    2. **REWARD**: Calculate using NEW msg, update agent (if context exists).
    3. **ACTION**: Get RL action (timeout 50ms).
    4. **EXECUTE**:
       - `WAIT`: Return `None`.
       - `REACT`: Call `_decide_reaction`.
       - `ENGAGE`: Call `_decide_proactive_engagement(force=False)`.
       - `INITIATE`: Call `_decide_proactive_engagement(force=True)`.
    5. **STORE**: Update `reward_context`.
    6. **CLEANUP**: Remove entries > 3600s old (timestamp check).

  **Acceptance Criteria**:
  - [ ] `_bin_sentiment(-0.5) == 1`.
    **Verification**: `assert _bin_sentiment(-0.5) == 1`
  - [ ] Reward calculated on *next* message using stored context.
    **Verification**: `handle(msg1); assert update_called==False; handle(msg2); assert update_called==True`
  - [ ] Fallback: If `rl_service` missing/fails, execute legacy logic.
    **Verification**: `mock_service.side_effect=Exception; handle(msg); assert legacy_called`
  - [ ] `INITIATE` calls proactive logic with `force=True`.
    **Verification**: `mock_proactive.assert_called_with(..., force=True)`
  - [ ] Context cleanup works.
    **Verification**: `context[u]=(..., old_time); cleanup(); assert u not in context`

- [x] 4. Implement Reward Logic Details

  **What to do**:
  - Implement `calculate_reward` in `RLService`.
  - Implement helpers: `_get_current_sentiment`, `_get_affinity`, `_get_silence`.

  **Acceptance Criteria**:
  - [ ] `calculate_reward` uses `r_speed` bonus if latency < 60s.
    **Verification**: `assert calculate_reward(..., user_reply_latency=59.0) > calculate_reward(..., user_reply_latency=61.0)`
  - [ ] `re.search` matches "shut up" (two words).
    **Verification**: `assert re.search(r'\b(?:stop|shut\s*up)\b', "shut up")`
  - [ ] `r_penalty` applied only if `WAIT` + negative sentiment.
    **Verification**: `assert calculate_reward(WAIT, sentiment=-0.8) < calculate_reward(WAIT, sentiment=0.0)`

- [x] 5. Add Management Commands

  **What to do**:
  - `!rl_reset confirm`: Owner only. Backup, wipe state.
  - `!rl_toggle`: Admin only. Switch enabled flag.
  - `!rl_stats`: Public. Show metrics for current channel.

  **Acceptance Criteria**:
  - [ ] `!rl_reset` checks owner_id.
    **Verification**: `ctx.author.id=123; bot.owner_id=456; assert reset() == "Forbidden"`
  - [ ] `!rl_toggle` changes `RLService.enabled`.
    **Verification**: `toggle(); assert service.enabled != old_enabled`
  - [ ] `!rl_reset confirm` creates `.bak` file.
    **Verification**: `reset("confirm"); assert len(glob("*.bak")) == 1`
