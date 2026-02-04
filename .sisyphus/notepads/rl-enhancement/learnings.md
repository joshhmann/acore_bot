
## NeuralAgent Implementation (2026-02-03)

### Key Design Decisions:
1. **Double DQN over vanilla DQN**: Avoids overestimation bias by using online network to SELECT actions and target network to EVALUATE them
2. **Soft updates (tau=0.005)**: Provides stable target values without periodic hard updates
3. **CPU default**: Discord bot inference should prioritize latency over throughput; CPU gives sub-ms inference
4. **Huber loss (SmoothL1Loss)**: More robust to outliers than MSE, better for RL

### Interface Compatibility:
- Maintains `select_action()`, `update()`, `to_dict()`, `from_dict()` matching existing RLAgent
- Added `get_action()` alias for backwards compatibility
- State conversion supports both RLState tuples and raw numpy/tensor arrays

### Performance Results:
- 40/40 tests passing
- Inference latency: p95 < 10ms, mean < 5ms (requirement met)
- ONNX export working for production inference optimization

### Dependencies Added:
- `onnxscript`, `onnx` for ONNX export functionality

### State Normalization (RLState tuple):
- sentiment_bin: normalized by /10.0
- time_since_last_bin: normalized by /100.0  
- message_count_bin: normalized by /50.0
- Embedded into first 3 positions of state_dim vector (rest zeros)


## ReplayBuffer Implementation (2026-02-03)

### Key Design Decisions:
1. **Circular buffer with Python list**: Simple, memory-efficient for moderate sizes
2. **asyncio.Lock for thread safety**: Discord bot uses asyncio, not threading
3. **Separate sync methods**: `add_sync()` and `sample_sync()` for non-async contexts (training loops)
4. **Transition dataclass**: Clean interface for (s, a, r, s', done) tuples

### Memory Usage Results:
- RLState tuples (recommended): ~77MB for 100K capacity (well under 100MB)
- 128-dim numpy arrays: ~125MB for 100K (exceeds limit due to object overhead)
- Recommendation: Use RLState tuples in production, convert to tensors during training

### Interface:
- `ReplayBuffer(capacity)` - main class
- `Transition(state, action, reward, next_state, done)` - dataclass for experiences
- `async add()` / `add_sync()` - thread-safe and non-blocking
- `async sample(batch_size)` / `sample_sync()` - uniform random sampling
- Properties: `is_full`, `utilization`, `__len__`

### Test Coverage:
- 41 tests covering: init, add, sample, properties, state types, thread safety, stress
- Concurrent add/sample test: 10 parallel tasks adding + 5 parallel tasks sampling
- Performance: 10K adds + 1K samples of batch 32 < 1 second

### Dependencies Added:
- `pytest-asyncio` for async test support

