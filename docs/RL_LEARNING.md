# RL Learning Guide

## How RL Works in the Bot

The bot uses Reinforcement Learning (RL) to improve its behavior over time based on user interactions and conversation outcomes.

### RL System Overview

The RL system makes decisions about:
- **When to react** to messages
- **When to wait** silently
- **When to engage proactively** in conversations
- **How to adjust behavior** based on context

### Actions the RL Agent Can Take

1. **REACT** - Respond to a direct mention or message
2. **WAIT** - Stay silent and observe
3. **PROACTIVE** - Jump into conversation without being mentioned
4. **AMBIENT** - Send a message during quiet periods

### How Rewards Are Calculated

The RL system receives rewards based on:
- **Engagement**: Did the user respond positively?
- **Conversation Quality**: Was the interaction natural and helpful?
- **Bot-to-Bot Conversations**: Quality scores from multi-bot conversations
- **User Feedback**: Implicit feedback from continued engagement

**Reward Values:**
- Positive reward (+1.0): High engagement (>0.7)
- Neutral (0.0): Moderate engagement (0.4-0.7)
- Negative reward (-1.0): Low engagement (<0.4)

### How the Bot Learns Over Time

1. **Exploration vs Exploitation** (Epsilon-Greedy)
   - Epsilon starts high (exploration)
   - Gradually decreases over time (exploitation)
   - Configurable via `RL_EPSILON_START`, `RL_EPSILON_END`, `RL_EPSILON_DECAY`

2. **Q-Learning Updates**
   - The bot maintains Q-values for state-action pairs
   - After each action, Q-values are updated based on reward
   - Higher Q-values = better expected outcomes

3. **Experience Replay**
   - Past experiences stored in replay buffer
   - Randomly sampled for training to break correlations

## Understanding RL Metrics

### Dashboard Metrics

The analytics dashboard shows:
- **Total Training Samples**: How many experiences RL has learned from
- **Current Epsilon**: Exploration rate (0-1)
- **Decision Distribution**: Pie chart of REACT/WAIT/PROACTIVE/AMBIENT choices
- **Learning Curve**: Reward trends over time

### What Epsilon Means

- **High Epsilon (0.8-1.0)**: Bot is exploring, trying new behaviors
- **Medium Epsilon (0.3-0.7)**: Balanced exploration/exploitation
- **Low Epsilon (0.0-0.3)**: Bot is exploiting learned behaviors

### How to Tell If RL Is Learning

**Good Signs:**
- Rewards trending upward over time
- Epsilon decreasing steadily
- More consistent engagement rates
- Better conversation quality scores

**Warning Signs:**
- Rewards flat or declining
- Epsilon stuck high (not learning)
- Repetitive behavior patterns

## Tuning RL Behavior

### Adjusting Exploration Rate

```bash
# More exploration (better for new environments)
RL_EPSILON_START=1.0
RL_EPSILON_END=0.1
RL_EPSILON_DECAY=0.995

# Less exploration (better for stable environments)
RL_EPSILON_START=0.5
RL_EPSILON_END=0.05
RL_EPSILON_DECAY=0.999
```

### When to Reset RL Models

Reset RL when:
- Moving to a completely new Discord server
- Major persona changes
- RL appears stuck in bad patterns

**How to Reset:**
```bash
# Delete RL data directory
rm -rf data/rl/
# Restart bot
```

### Speeding Up/Slowing Down Learning

```bash
# Faster learning (more aggressive updates)
RL_LEARNING_RATE=0.1

# Slower learning (more stable)
RL_LEARNING_RATE=0.01
```

## Troubleshooting

### RL Not Learning (Rewards Not Improving)

**Symptoms:**
- Rewards flat over time
- Epsilon not decreasing
- Bot behavior repetitive

**Solutions:**
1. Check `RL_ENABLED=true` in config
2. Increase `RL_LEARNING_RATE`
3. Verify epsilon is decaying: check dashboard
4. Ensure sufficient training data (need 100+ interactions)
5. Check RL data directory exists and is writable

### Bot Being Too Random

**Symptoms:**
- High epsilon (0.8+)
- Inconsistent behavior
- Not using learned patterns

**Solutions:**
1. Let epsilon decay naturally (wait for more training)
2. Decrease `RL_EPSILON_START`
3. Increase `RL_EPSILON_DECAY` (slower decay)
4. Check dashboard for epsilon value

### Bot Being Too Predictable

**Symptoms:**
- Low epsilon (0.1 or less)
- Repetitive responses
- Not adapting to new contexts

**Solutions:**
1. Increase `RL_EPSILON_END` (maintain some exploration)
2. Reset RL models to re-learn
3. Add `RL_EXPLORATION_MODE=true` for boosted exploration

### Checking RL State

```bash
# Check if RL is enabled
uv run python -c "from config import Config; print(f'RL Enabled: {Config.RL_ENABLED}')"

# Check RL metrics via API
curl -s http://localhost:8080/api/metrics | python -m json.tool

# Check RL data files
ls -la data/rl/
```

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `RL_ENABLED` | true | Enable/disable RL system |
| `RL_EPSILON_START` | 1.0 | Initial exploration rate |
| `RL_EPSILON_END` | 0.01 | Final exploration rate |
| `RL_EPSILON_DECAY` | 0.995 | Decay rate per step |
| `RL_LEARNING_RATE` | 0.1 | How fast to learn |
| `RL_DISCOUNT_FACTOR` | 0.95 | Future reward importance |
| `BOTCONV_RL_TRAINING_ENABLED` | false | Train from bot conversations |

## Best Practices

1. **Start with defaults** - They work well for most cases
2. **Monitor dashboard** - Watch epsilon and rewards weekly
3. **Be patient** - RL needs 100+ interactions to show results
4. **Enable botconv training** - Great source of training data
5. **Reset if stuck** - Sometimes starting fresh helps

## Quick Reference

```bash
# Enable RL training from bot conversations
export BOTCONV_RL_TRAINING_ENABLED=true

# Check RL status
uv run python -c "from config import Config; print(f'RL: {Config.RL_ENABLED}, Epsilon: {Config.RL_EPSILON_START}')"

# View RL metrics in dashboard
open http://localhost:8080
```

---

For more details, see `docs/BEHAVIOR_CONFIGURATION.md`
