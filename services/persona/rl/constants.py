"""RL constants and parameters."""

# Epsilon-Greedy parameters
RL_EPSILON_START = 1.0
RL_EPSILON_END = 0.01
RL_EPSILON_DECAY = 0.9995  # Decay once per user message processed

# Q-Learning parameters
RL_Q_INIT = 10.0  # Optimistic initialization
RL_LEARNING_RATE = 0.1
RL_DISCOUNT_FACTOR = 0.9

# Service parameters
RL_PERSIST_INTERVAL = 60  # Seconds between background saves
RL_LOCK_TIMEOUT = 0.050  # 50ms timeout for acquiring locks
RL_MAX_LATENCY_SEC = 0.050  # 50ms max latency for RL operations

# Reward calculation parameters
RL_REWARD_SPEED_THRESHOLD = 60.0  # seconds - threshold for speed bonus
RL_REWARD_LONG_MSG_CHAR = 100  # character count for long message threshold
RL_CONTEXT_MAX_AGE = 3600  # seconds - max age of reward context entries
RL_MAX_AGENTS_PER_CHANNEL = 100  # max agents per channel

# Neural RL (DQN) parameters
RL_ALGORITHM = "tabular"  # "tabular" or "dqn"
RL_REPLAY_BUFFER_SIZE = 10000  # Capacity of replay buffer
RL_BATCH_SIZE = 32  # Batch size for training
RL_WARMUP_STEPS = 1000  # Transitions to collect before training starts
RL_TRAIN_EVERY = 4  # Train every N steps after warmup

# Multi-objective reward weights (must sum to 1.0)
REWARD_WEIGHT_ENGAGEMENT = 0.3
REWARD_WEIGHT_QUALITY = 0.3
REWARD_WEIGHT_AFFINITY = 0.2
REWARD_WEIGHT_CURIOSITY = 0.2

# Component clipping
REWARD_CLIP_COMPONENT = 5.0
REWARD_CLIP_TOTAL = 10.0
