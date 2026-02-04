# RL Configuration Guide

## Quick Start

### Enable Basic RL (Tabular Q-Learning)
```bash
# In your .env file
RL_ENABLED=true
RL_ALGORITHM=tabular
```

### Enable Advanced RL (DQN - Neural Networks)
```bash
# In your .env file
RL_ENABLED=true
RL_ALGORITHM=dqn
RL_USE_HIERARCHICAL=true
RL_USE_TRANSFER=true
RL_USE_MULTI_OBJECTIVE=true

# Also enable dashboard to see metrics
ANALYTICS_DASHBOARD_ENABLED=true
```

## Configuration Options

### Basic Settings

| Variable | Default | Description |
|----------|---------|-------------|
| RL_ENABLED | false | Enable/disable RL system |
| RL_DATA_DIR | ./data/rl | Where to store RL data |
| RL_ALGORITHM | tabular | Algorithm: "tabular" or "dqn" |

### DQN-Specific Settings

| Variable | Default | Description |
|----------|---------|-------------|
| RL_REPLAY_BUFFER_SIZE | 10000 | Experience replay capacity |
| RL_BATCH_SIZE | 32 | Training batch size |
| RL_WARMUP_STEPS | 1000 | Steps before training starts |
| RL_TRAIN_EVERY | 4 | Train every N steps |
| RL_STATE_DIM | 128 | State embedding dimension |
| RL_USE_HIERARCHICAL | true | Enable meta-controller |
| RL_USE_TRANSFER | true | Enable knowledge transfer |
| RL_USE_MULTI_OBJECTIVE | true | Enable multi-objective rewards |
| RL_OFFLINE_PRETRAINING | false | Enable offline CQL training |

## Algorithm Comparison

### Tabular Q-Learning
**Best for:** Testing, simple scenarios, low resource usage
- ✅ Fast and lightweight
- ✅ Easy to understand
- ✅ Deterministic
- ❌ Limited state space (80 discrete states)
- ❌ No generalization

### Deep Q-Network (DQN)
**Best for:** Production, complex scenarios, learning from experience
- ✅ Rich state representation (128+ dimensions)
- ✅ Experience replay for stable learning
- ✅ Multi-objective optimization
- ✅ Knowledge transfer between personas
- ✅ Hierarchical strategy selection
- ❌ Requires more memory
- ❌ Needs warmup period (1000 steps)

## Using the Configuration Helper

```bash
# Check current status
python scripts/configure_rl.py --status

# Switch to DQN mode
python scripts/configure_rl.py --mode dqn

# Interactive setup wizard
python scripts/configure_rl.py --interactive

# Enable/disable RL
python scripts/configure_rl.py --enable
python scripts/configure_rl.py --disable
```

## Migration from Tabular to DQN

If you have existing tabular Q-table policies:

```bash
# Migrate with warm-start (preserves learned values)
python scripts/migrate_rl_policies.py --execute

# Or start fresh (random initialization)
python scripts/migrate_rl_policies.py --execute --fresh
```

## Dashboard Visualizations

When using DQN mode with the dashboard enabled, you can see:

1. **Learning Curves** - Loss and Q-value trends over time
2. **Replay Buffer Stats** - Buffer utilization and sampling
3. **Multi-Objective Radar** - Engagement, quality, affinity, curiosity
4. **State Space Heatmap** - Which states are visited most
5. **Strategy Distribution** - Meta-controller strategy usage
6. **Transfer Network** - Knowledge flow between personas

Access at: http://localhost:8080 (requires ANALYTICS_API_KEY)

## Advanced Features

### Knowledge Transfer
Transfer learned behaviors between similar personas:

```bash
# Transfer from Dagoth Ur to Hal9000
python scripts/transfer_knowledge.py --source dagoth_ur --target hal9000

# View transfer lineage
python scripts/transfer_knowledge.py --lineage hal9000
```

### Offline Pre-training
Train on historical conversation data before deployment:

```bash
# Enable in .env
RL_OFFLINE_PRETRAINING=true

# Train on historical data
python scripts/train_offline_rl.py --episodes 1000
```

### Hierarchical RL
The meta-controller selects high-level strategies:
- `build_rapport` - Focus on relationship building
- `entertain` - Be funny and engaging
- `inform` - Share knowledge and facts
- `support` - Be helpful and empathetic

Each strategy has its own worker agent that learns tactics.

## Troubleshooting

### RL Not Working
1. Check `RL_ENABLED=true` in .env
2. Verify `RL_DATA_DIR` exists and is writable
3. Check logs for RL initialization messages

### DQN Training Not Starting
- DQN has a warmup period (1000 transitions by default)
- The bot collects experience but doesn't train until warmup is complete
- Check dashboard for "warmup_steps" metric

### Out of Memory
- Reduce `RL_REPLAY_BUFFER_SIZE` (default: 10000)
- Reduce `RL_STATE_DIM` (default: 128)
- Reduce `RL_BATCH_SIZE` (default: 32)

### Slow Performance
- Switch to `RL_ALGORITHM=tabular` for testing
- Reduce `RL_STATE_DIM` to 64
- Disable hierarchical: `RL_USE_HIERARCHICAL=false`

## Performance Benchmarks

On typical hardware (CPU):
- **Tabular**: < 1ms per decision
- **DQN**: < 5ms per decision (p95)
- **Dashboard updates**: Every 2 seconds

## Best Practices

1. **Start with tabular** for testing, then migrate to DQN
2. **Enable dashboard** to monitor learning progress
3. **Use transfer learning** when adding new personas
4. **Set appropriate warmup** for your traffic (1000-10000 steps)
5. **Monitor replay buffer** utilization (should be 50-90%)
6. **Regular backups** of `data/rl/` directory

## See Also

- `docs/RL_ARCHITECTURE.md` - Technical deep dive
- `docs/DASHBOARD.md` - Dashboard usage guide
- `scripts/migrate_rl_policies.py --help`
- `scripts/transfer_knowledge.py --help`
- `scripts/train_offline_rl.py --help`
