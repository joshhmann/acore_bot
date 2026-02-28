"""RL Service Manager."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
from collections import OrderedDict

from .types import RLAction, RLState
from .agent import RLAgent
from .neural_agent import NeuralAgent, TORCH_AVAILABLE
from .replay_buffer import ReplayBuffer, Transition
from .constants import (
    RL_EPSILON_START,
    RL_MAX_AGENTS_PER_CHANNEL,
    RL_PERSIST_INTERVAL,
    RL_ALGORITHM,
    RL_REPLAY_BUFFER_SIZE,
    RL_BATCH_SIZE,
    RL_WARMUP_STEPS,
    RL_TRAIN_EVERY,
    RL_EXPLORATION_MODE,
    RL_EXPLORATION_ACTIVITY_THRESHOLD,
    RL_EXPLORATION_BONUS_MAX,
    RL_EPSILON_BOOST_FACTOR,
    RL_EPSILON_BOOST_DECAY,
)
from .persistence import RLStorage
from .safety import SafetyLayer

logger = logging.getLogger(__name__)


class RLService:
    """Service for managing RL agents per (channel_id, user_id)."""

    def __init__(self, bot=None, config=None, algorithm: str = RL_ALGORITHM):
        """
        Initialize RL Service.

        Args:
            bot: Discord bot instance
            config: Configuration object
            algorithm: RL algorithm to use - "tabular" or "dqn" (default: from constants)
        """
        self.bot = bot
        self.config = config
        self.algorithm = algorithm
        self.enabled = getattr(config, "RL_ENABLED", False) if config else False
        self.data_dir = Path(
            getattr(config, "RL_DATA_DIR", "./data/rl") if config else "./data/rl"
        )

        if self.enabled:
            self.data_dir.mkdir(parents=True, exist_ok=True)

        # Tabular agents storage
        self.agents: OrderedDict[Tuple[int, int], RLAgent] = OrderedDict()
        self.agent_locks: Dict[Tuple[int, int], asyncio.Lock] = {}

        # Neural agents storage (DQN mode)
        self.neural_agents: Dict[Tuple[int, int], NeuralAgent] = {}

        # Replay buffer for DQN mode
        self.replay_buffer: Optional[ReplayBuffer] = None
        # If torch is not available, gracefully fall back to tabular mode
        self.has_torch = TORCH_AVAILABLE
        if self.algorithm == "dqn" and not self.has_torch:
            logger.warning(
                "PyTorch not available; falling back from DQN to Tabular RL."
            )
            self.algorithm = "tabular"

        if self.algorithm == "dqn":
            self.replay_buffer = ReplayBuffer(capacity=RL_REPLAY_BUFFER_SIZE)
            logger.info(
                f"Initialized ReplayBuffer with capacity={RL_REPLAY_BUFFER_SIZE}"
            )

        # Training state for DQN mode
        self.training_step = 0
        self.warmup_steps = RL_WARMUP_STEPS
        self.batch_size = RL_BATCH_SIZE
        self.train_every = RL_TRAIN_EVERY
        self._training_lock = asyncio.Lock()

        self.max_agents = RL_MAX_AGENTS_PER_CHANNEL * 10
        self.save_interval = RL_PERSIST_INTERVAL

        self.storage = RLStorage(self.data_dir)
        self.safety = SafetyLayer()

        # Training metrics for DQN
        self._training_metrics: Dict[str, Any] = {
            "total_training_steps": 0,
            "total_loss": 0.0,
            "mean_q_value": 0.0,
            "buffer_size": 0,
            "buffer_utilization": 0.0,
        }

        self._bg_task = None

        # Exploration-heavy mode for low-interaction training
        self.exploration_mode = (
            getattr(config, "RL_EXPLORATION_MODE", RL_EXPLORATION_MODE)
            if config
            else RL_EXPLORATION_MODE
        )
        self.exploration_activity_threshold = (
            getattr(
                config,
                "RL_EXPLORATION_ACTIVITY_THRESHOLD",
                RL_EXPLORATION_ACTIVITY_THRESHOLD,
            )
            if config
            else RL_EXPLORATION_ACTIVITY_THRESHOLD
        )
        self.exploration_bonus_max = (
            getattr(config, "RL_EXPLORATION_BONUS_MAX", RL_EXPLORATION_BONUS_MAX)
            if config
            else RL_EXPLORATION_BONUS_MAX
        )
        self.epsilon_boost_factor = (
            getattr(config, "RL_EPSILON_BOOST_FACTOR", RL_EPSILON_BOOST_FACTOR)
            if config
            else RL_EPSILON_BOOST_FACTOR
        )
        self.epsilon_boost_decay = (
            getattr(config, "RL_EPSILON_BOOST_DECAY", RL_EPSILON_BOOST_DECAY)
            if config
            else RL_EPSILON_BOOST_DECAY
        )

        # Activity tracking for exploration mode
        self._channel_activity: Dict[int, Dict[str, Any]] = {}
        self._activity_window_seconds = 3600  # 1 hour window

        logger.info(f"RLService initialized with algorithm='{self.algorithm}'")

    async def start(self):
        if not self.enabled:
            return

        try:
            loaded_agents = await asyncio.to_thread(self.storage.load)
            self.agents.update(loaded_agents)
            logger.info(f"RL Service loaded {len(self.agents)} agents")
        except Exception as e:
            logger.error(f"Failed to load agents: {e}")

        if self._bg_task is None:
            self._bg_task = asyncio.create_task(self._persistence_loop())
            logger.info("RL Service started")

    async def stop(self):
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass

        await self._save_all_dirty()
        logger.info("RL Service stopped")

    async def get_agent(self, channel_id: int, user_id: int) -> RLAgent:
        """Get or create a tabular RL agent for the given channel/user."""
        key = (channel_id, user_id)

        if key in self.agents:
            self.agents.move_to_end(key)
            return self.agents[key]

        agent = RLAgent(epsilon=RL_EPSILON_START)

        if len(self.agents) >= self.max_agents:
            old_key, old_agent = self.agents.popitem(last=False)
            if old_agent.dirty:
                await self._save_agent(old_key[0], old_key[1], old_agent)

        self.agents[key] = agent
        return agent

    async def get_neural_agent(self, channel_id: int, user_id: int) -> NeuralAgent:
        """Get or create a neural RL agent for the given channel/user."""
        key = (channel_id, user_id)

        if key in self.neural_agents:
            return self.neural_agents[key]

        agent = NeuralAgent()
        self.neural_agents[key] = agent
        logger.debug(
            f"Created new NeuralAgent for channel={channel_id}, user={user_id}"
        )
        return agent

    async def get_action(
        self, channel_id: int, user_id: int, state: RLState
    ) -> Tuple[RLAction, Optional[str]]:
        """Get the next action for a user context."""
        if not self.enabled:
            return RLAction.WAIT, None

        key = (channel_id, user_id)
        if key not in self.agent_locks:
            self.agent_locks[key] = asyncio.Lock()

        async with self.agent_locks[key]:
            if self.algorithm == "tabular":
                return await self._get_action_tabular(channel_id, user_id, state)
            else:
                return await self._get_action_dqn(channel_id, user_id, state)

    async def _get_action_tabular(
        self, channel_id: int, user_id: int, state: RLState
    ) -> Tuple[RLAction, Optional[str]]:
        """Get action using tabular Q-learning agent."""
        # Record activity for exploration mode
        self._record_channel_activity(channel_id)

        agent = await self.get_agent(channel_id, user_id)

        # Apply epsilon boost during low activity periods
        original_epsilon = agent.epsilon
        agent.epsilon = self._get_boosted_epsilon(channel_id, agent.epsilon)

        action = agent.get_action(state)

        # Restore original epsilon (boost is tracked separately)
        agent.epsilon = original_epsilon

        # Log decision for observability
        q_values = agent.q_table.get(state, {})
        q_str = (
            ", ".join([f"{a.name}={q:.2f}" for a, q in q_values.items()])
            if q_values
            else "N/A (new state)"
        )
        logger.info(
            f"RL Decision (tabular): channel={channel_id}, user={user_id}, "
            f"state={state}, chosen={action.name}, epsilon={agent.epsilon:.4f}, "
            f"Q-values=[{q_str}]"
        )

        if not self.safety.check(channel_id, user_id, action):
            logger.warning(f"RL Safety blocked action {action.name} for user {user_id}")
            return RLAction.WAIT, None

        return action, None

    async def _get_action_dqn(
        self, channel_id: int, user_id: int, state: RLState
    ) -> Tuple[RLAction, Optional[str]]:
        """Get action using neural DQN agent."""
        # Record activity for exploration mode
        self._record_channel_activity(channel_id)

        agent = await self.get_neural_agent(channel_id, user_id)

        # Apply epsilon boost during low activity periods
        boosted_epsilon = self._get_boosted_epsilon(channel_id, agent.epsilon)

        action = agent.select_action(state, epsilon=boosted_epsilon)

        # Log decision for observability
        q_values = agent.get_q_values(state)
        q_str = ", ".join(
            [f"{RLAction(i).name}={q:.2f}" for i, q in enumerate(q_values)]
        )
        logger.info(
            f"RL Decision (DQN): channel={channel_id}, user={user_id}, "
            f"state={state}, chosen={action.name}, epsilon={agent.epsilon:.4f}, "
            f"Q-values=[{q_str}]"
        )

        if not self.safety.check(channel_id, user_id, action):
            logger.warning(f"RL Safety blocked action {action.name} for user {user_id}")
            return RLAction.WAIT, None

        return action, None

    async def calculate_reward(
        self,
        channel_id: int,
        user_id: int,
        message: Any,
        state: Any,
        prev_action: RLAction,
        prev_sentiment: float,
        latency: float = 0.0,
        affinity_delta: float = 0.0,
    ) -> float:
        r"""Calculate reward for the previous action.

        Logic:
          - Base reward: current_sentiment * 1.0
          - Affinity reward: math.tanh(affinity_delta * 0.1) * 5.0
          - Speed bonus: 0.5 if latency < RL_REWARD_SPEED_THRESHOLD
          - Penalty 1: -2.0 if user message matches regex r'\b(?:stop|shut\s*up|quiet)\b'
          - Penalty 2: -0.5 if previous_action == RLAction.WAIT AND current_sentiment < -0.3
          - Clamp reward: [-10.0, 10.0]
        """
        import math
        import re
        from .constants import RL_REWARD_SPEED_THRESHOLD

        # Extract current sentiment from state
        # state is expected to be BehaviorState
        current_sentiment = 0.0
        if hasattr(state, "sentiment_history") and state.sentiment_history:
            current_sentiment = state.sentiment_history[-1]

        reward = current_sentiment * 1.0

        # Affinity reward
        reward += math.tanh(affinity_delta * 0.1) * 5.0

        # Speed bonus
        if latency < RL_REWARD_SPEED_THRESHOLD:
            reward += 0.5

        # Penalty 1: Stop words
        if hasattr(message, "content"):
            if re.search(
                r"\b(?:stop|shut\s*up|quiet)\b", message.content, re.IGNORECASE
            ):
                reward -= 2.0

        # Penalty 2: Wait action with negative sentiment
        if prev_action == RLAction.WAIT and current_sentiment < -0.3:
            reward -= 0.5

        # Exploration bonus for proactive engagement during low activity
        exploration_bonus = self._get_exploration_bonus(channel_id, prev_action)
        reward += exploration_bonus

        # Clamp reward
        return max(-10.0, min(10.0, reward))

    async def update_agent(
        self,
        channel_id: int,
        user_id: int,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState,
    ):
        """Update agent policy based on reward."""
        if not self.enabled:
            return

        key = (channel_id, user_id)
        if key not in self.agent_locks:
            self.agent_locks[key] = asyncio.Lock()

        async with self.agent_locks[key]:
            if self.algorithm == "tabular":
                await self._update_agent_tabular(
                    channel_id, user_id, state, action, reward, next_state
                )
            else:
                await self._update_agent_dqn(
                    channel_id, user_id, state, action, reward, next_state
                )

    async def _update_agent_tabular(
        self,
        channel_id: int,
        user_id: int,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState,
    ):
        """Update tabular Q-learning agent."""
        agent = await self.get_agent(channel_id, user_id)
        agent.update(state, action, reward, next_state)

        # Log learning event for observability
        logger.info(
            f"RL Learning (tabular): channel={channel_id}, user={user_id}, "
            f"action={action.name}, reward={reward:.2f}, "
            f"epsilon={agent.epsilon:.4f}, states_learned={len(agent.q_table)}"
        )

    async def _update_agent_dqn(
        self,
        channel_id: int,
        user_id: int,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState,
    ):
        """Update neural DQN agent via replay buffer."""
        # Store transition in replay buffer
        transition = Transition(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=False,  # Episodes are continuous in this context
        )
        await self.store_transition(transition)

        # Check if we should train
        await self._maybe_train()

        # Log learning event
        buffer_size = len(self.replay_buffer) if self.replay_buffer else 0
        logger.info(
            f"RL Learning (DQN): channel={channel_id}, user={user_id}, "
            f"action={action.name}, reward={reward:.2f}, "
            f"buffer_size={buffer_size}, step={self.training_step}"
        )

    async def store_transition(self, transition: Transition) -> None:
        """
        Store a transition in the replay buffer.

        Args:
            transition: The (s, a, r, s', done) transition to store
        """
        if self.replay_buffer is None:
            logger.warning(
                "store_transition called but replay_buffer is not initialized"
            )
            return

        await self.replay_buffer.add(transition)

    async def _maybe_train(self) -> None:
        """
        Check if training should occur and trigger it if conditions are met.

        Training conditions:
        1. Buffer has at least warmup_steps transitions
        2. Current step is a multiple of train_every
        """
        if self.replay_buffer is None:
            return

        async with self._training_lock:
            self.training_step += 1

            # Check warmup period
            buffer_size = len(self.replay_buffer)
            if buffer_size < self.warmup_steps:
                return

            # Check if we should train this step
            if self.training_step % self.train_every != 0:
                return

            # Perform training
            await self.train_step()

    async def train_step(self) -> Optional[float]:
        """
        Perform a single training step using a batch from the replay buffer.

        Samples a batch from the replay buffer and updates the neural agent.
        Uses the first available neural agent for training (shared network).

        Returns:
            Mean loss for this training step, or None if training didn't occur
        """
        if self.replay_buffer is None:
            return None

        if len(self.replay_buffer) < self.batch_size:
            return None

        try:
            # Sample batch from replay buffer
            batch = await self.replay_buffer.sample(self.batch_size)

            # Get or create a neural agent for training
            # We use a shared network approach - train one agent, all benefit
            if not self.neural_agents:
                # Create a dummy agent for training if none exist
                await self.get_neural_agent(0, 0)

            # Use the first neural agent for training
            agent = next(iter(self.neural_agents.values()))

            # Update agent for each transition in batch
            total_loss = 0.0
            for transition in batch:
                loss = agent.update(
                    state=transition.state,
                    action=transition.action,
                    reward=transition.reward,
                    next_state=transition.next_state,
                    done=transition.done,
                )
                total_loss += loss

            mean_loss = total_loss / len(batch)

            # Update metrics
            self._training_metrics["total_training_steps"] += 1
            self._training_metrics["total_loss"] += mean_loss
            self._training_metrics["mean_q_value"] = agent.get_stats()["mean_q_value"]
            self._training_metrics["buffer_size"] = len(self.replay_buffer)
            self._training_metrics["buffer_utilization"] = (
                self.replay_buffer.utilization
            )

            logger.debug(
                f"DQN Training step {self._training_metrics['total_training_steps']}: "
                f"loss={mean_loss:.4f}, buffer_size={len(self.replay_buffer)}"
            )

            return mean_loss

        except Exception as e:
            logger.error(f"Error during DQN training step: {e}")
            return None

    def get_training_metrics(self) -> Dict[str, Any]:
        """
        Get current training metrics for monitoring.

        Returns:
            Dictionary containing training metrics
        """
        if self.replay_buffer:
            self._training_metrics["buffer_size"] = len(self.replay_buffer)
            self._training_metrics["buffer_utilization"] = (
                self.replay_buffer.utilization
            )

        return self._training_metrics.copy()

    async def _save_agent(self, channel_id: int, user_id: int, agent: RLAgent):
        """Save a single agent."""
        await self._save_all_dirty()

    async def _save_all_dirty(self):
        """Save all agents marked as dirty."""
        any_dirty = any(a.dirty for a in self.agents.values())
        if not any_dirty:
            return

        try:
            await asyncio.to_thread(self.storage.save, self.agents)

            for agent in self.agents.values():
                agent.dirty = False

        except Exception as e:
            logger.error(f"Failed to save RL agents: {e}")

    def record_feedback(self, state_info: Any, reward: float) -> None:
        """Accept external feedback for RL training hooks (non-blocking)."""
        if not self.enabled:
            return
        try:
            logger.info(
                f"External RL feedback received: state_info={state_info}, reward={reward}"
            )
        except Exception as e:
            logger.debug(f"record_feedback failed: {e}")

    async def _persistence_loop(self):
        """Background loop to periodically save data."""
        while True:
            try:
                await asyncio.sleep(self.save_interval)
                await self._save_all_dirty()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in RL persistence loop: {e}")

    def _record_channel_activity(self, channel_id: int):
        """Record message activity for a channel."""
        import time

        if channel_id not in self._channel_activity:
            self._channel_activity[channel_id] = {
                "message_times": [],
                "last_boosted_epsilon": 0.0,
            }

        activity = self._channel_activity[channel_id]
        current_time = time.time()

        # Add current message time
        activity["message_times"].append(current_time)

        # Clean up old messages outside the window
        cutoff_time = current_time - self._activity_window_seconds
        activity["message_times"] = [
            t for t in activity["message_times"] if t > cutoff_time
        ]

    def _get_channel_activity_level(self, channel_id: int) -> int:
        """Get the number of messages in the activity window for a channel."""
        import time

        if channel_id not in self._channel_activity:
            return 0

        activity = self._channel_activity[channel_id]
        current_time = time.time()
        cutoff_time = current_time - self._activity_window_seconds

        # Clean and count
        activity["message_times"] = [
            t for t in activity["message_times"] if t > cutoff_time
        ]
        return len(activity["message_times"])

    def _is_low_activity(self, channel_id: int) -> bool:
        """Check if channel has low activity (below threshold)."""
        if not self.exploration_mode:
            return False

        activity_level = self._get_channel_activity_level(channel_id)
        return activity_level < self.exploration_activity_threshold

    def _get_exploration_bonus(self, channel_id: int, action: RLAction) -> float:
        """Calculate exploration bonus reward for proactive engagement during low activity.

        Args:
            channel_id: The Discord channel ID
            action: The action taken by the agent

        Returns:
            Exploration bonus value (0 to exploration_bonus_max)
        """
        if not self.exploration_mode:
            return 0.0

        if not self._is_low_activity(channel_id):
            return 0.0

        # Reward proactive actions more during low activity
        if action == RLAction.INITIATE:
            return self.exploration_bonus_max
        elif action == RLAction.ENGAGE:
            return self.exploration_bonus_max * 0.7
        elif action == RLAction.REACT:
            return self.exploration_bonus_max * 0.3
        else:  # WAIT
            return 0.0

    def _get_boosted_epsilon(self, channel_id: int, base_epsilon: float) -> float:
        """Get epsilon value with boost applied during low activity periods.

        Args:
            channel_id: The Discord channel ID
            base_epsilon: The base epsilon value from the agent

        Returns:
            Potentially boosted epsilon value
        """
        import time

        if not self.exploration_mode:
            return base_epsilon

        if channel_id not in self._channel_activity:
            return base_epsilon

        activity = self._channel_activity[channel_id]
        current_time = time.time()

        # Check if we should apply boost
        if self._is_low_activity(channel_id):
            # Apply boost
            boosted = min(1.0, base_epsilon * self.epsilon_boost_factor)
            activity["last_boosted_epsilon"] = boosted
            return boosted
        else:
            # Decay the boosted epsilon back to normal
            last_boosted = activity.get("last_boosted_epsilon", 0.0)
            if last_boosted > base_epsilon:
                decayed = max(base_epsilon, last_boosted * self.epsilon_boost_decay)
                activity["last_boosted_epsilon"] = decayed
                return decayed
            return base_epsilon
