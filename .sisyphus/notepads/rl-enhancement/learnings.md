
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

