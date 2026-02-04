"""Hierarchical RL with Meta-Controller for high-level strategy selection.

This module implements a two-level hierarchical RL architecture:
- Meta-Controller: Selects high-level strategies (BUILD_RAPPORT, ENTERTAIN, INFORM, SUPPORT)
- Worker Agents: Each strategy has a NeuralAgent that selects low-level actions (WAIT, REACT, ENGAGE, INITIATE)

The meta-controller learns which strategies work best in different contexts,
while workers learn optimal actions within their strategy.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from .constants import RL_DISCOUNT_FACTOR
from .neural_agent import NeuralAgent, QNetwork
from .types import RLAction, RLState

logger = logging.getLogger(__name__)

# Minimum duration (in interactions) before strategy can switch
MIN_STRATEGY_DURATION = 3

# Maximum duration (in interactions) before forced strategy switch
MAX_STRATEGY_DURATION = 20

# Meta-controller state dimension (higher-level context features)
META_STATE_DIM = 64

# Number of strategies
NUM_STRATEGIES = 4


class Strategy(IntEnum):
    """High-level strategies available to the meta-controller."""

    BUILD_RAPPORT = 0  # Focus on relationship building, personal questions, empathy
    ENTERTAIN = 1  # Focus on fun, humor, games, light conversation
    INFORM = 2  # Focus on facts, education, helpful information
    SUPPORT = 3  # Focus on emotional support, encouragement, validation


@dataclass
class StrategyContext:
    """Context information for strategy selection."""

    user_sentiment: float = 0.0  # -1.0 to 1.0
    conversation_depth: int = 0  # Number of back-and-forth exchanges
    user_engagement: float = 0.5  # 0.0 to 1.0 (response rate, message length)
    relationship_strength: float = 0.0  # 0.0 to 1.0 (affinity normalized)
    topic_interest_match: float = 0.5  # 0.0 to 1.0 (how well topics align)
    time_since_last_interaction: float = 0.0  # Seconds
    user_initiated: bool = True  # Whether user or bot initiated

    def to_vector(self, state_dim: int = META_STATE_DIM) -> np.ndarray:
        """Convert context to feature vector for meta-controller."""
        # Base features
        features = [
            self.user_sentiment,
            self.conversation_depth / 50.0,  # Normalize
            self.user_engagement,
            self.relationship_strength,
            self.topic_interest_match,
            min(self.time_since_last_interaction / 3600.0, 1.0),  # Cap at 1 hour
            float(self.user_initiated),
        ]

        # Create full state vector with padding
        vec = np.zeros(state_dim, dtype=np.float32)
        vec[: len(features)] = features

        # Add derived features to fill remaining dimensions
        if state_dim > len(features):
            # Interaction features
            vec[7] = abs(self.user_sentiment)  # Sentiment magnitude
            vec[8] = (
                self.user_sentiment * self.user_engagement
            )  # Sentiment-engagement product
            vec[9] = (
                self.relationship_strength * self.user_engagement
            )  # Relationship-engagement

            # Context features
            vec[10] = float(self.conversation_depth > 0)  # Has conversation started
            vec[11] = float(self.time_since_last_interaction < 60)  # Recent interaction
            vec[12] = float(self.topic_interest_match > 0.7)  # High topic match

        return vec


@dataclass
class MetaControllerStats:
    """Training statistics for the meta-controller."""

    total_meta_updates: int = 0
    total_strategy_switches: int = 0
    strategy_durations: Dict[Strategy, List[int]] = field(
        default_factory=lambda: {s: [] for s in Strategy}
    )
    strategy_rewards: Dict[Strategy, List[float]] = field(
        default_factory=lambda: {s: [] for s in Strategy}
    )
    current_strategy_start: float = field(default_factory=time.time)
    epsilon: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_meta_updates": self.total_meta_updates,
            "total_strategy_switches": self.total_strategy_switches,
            "epsilon": self.epsilon,
            "strategy_avg_duration": {
                s.name: np.mean(durations) if durations else 0.0
                for s, durations in self.strategy_durations.items()
            },
            "strategy_avg_reward": {
                s.name: np.mean(rewards) if rewards else 0.0
                for s, rewards in self.strategy_rewards.items()
            },
        }


class MetaController:
    """
    Meta-Controller for Hierarchical RL.

    Architecture:
    1. Meta-level: Selects high-level strategy based on conversation context
    2. Worker-level: Each strategy has a dedicated NeuralAgent for action selection

    The meta-controller uses a separate Q-network to learn strategy values,
    while workers learn optimal actions within their domain.

    Strategy Selection:
    - BUILD_RAPPORT: For new users, low relationship strength
    - ENTERTAIN: For high engagement, positive sentiment
    - INFORM: For questions, educational topics
    - SUPPORT: For negative sentiment, emotional content

    Termination Conditions:
    - Minimum duration: Prevents rapid switching (3 interactions)
    - Maximum duration: Forces exploration (20 interactions)
    - Context change: Significant shift in sentiment/topic
    - Low reward: Strategy not performing well
    """

    def __init__(
        self,
        state_dim: int = META_STATE_DIM,
        learning_rate: float = 1e-4,
        discount_factor: float = RL_DISCOUNT_FACTOR,
        tau: float = 0.005,
        epsilon: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        min_strategy_duration: int = MIN_STRATEGY_DURATION,
        max_strategy_duration: int = MAX_STRATEGY_DURATION,
        device: Optional[str] = None,
    ):
        """
        Initialize the Meta-Controller.

        Args:
            state_dim: Dimension of meta-level state vector
            learning_rate: Learning rate for meta-controller optimizer
            discount_factor: Discount factor for future rewards
            tau: Soft update parameter for target network
            epsilon: Initial exploration rate for strategy selection
            epsilon_end: Minimum exploration rate
            epsilon_decay: Decay rate for epsilon
            min_strategy_duration: Minimum interactions before strategy switch
            max_strategy_duration: Maximum interactions before forced switch
            device: Device to use ('cpu', 'cuda')
        """
        self.state_dim = state_dim
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.tau = tau
        self.epsilon = epsilon
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.min_strategy_duration = min_strategy_duration
        self.max_strategy_duration = max_strategy_duration

        if device is None:
            self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)

        # Meta-level Q-networks for strategy selection
        self.meta_online_network = QNetwork(
            state_dim=state_dim, action_dim=NUM_STRATEGIES, hidden_dims=(128, 128)
        ).to(self.device)
        self.meta_target_network = QNetwork(
            state_dim=state_dim, action_dim=NUM_STRATEGIES, hidden_dims=(128, 128)
        ).to(self.device)

        self.meta_target_network.load_state_dict(self.meta_online_network.state_dict())
        for param in self.meta_target_network.parameters():
            param.requires_grad = False

        self.meta_optimizer = optim.Adam(
            self.meta_online_network.parameters(), lr=learning_rate
        )
        self.loss_fn = nn.SmoothL1Loss()

        # Worker agents - one per strategy
        self.workers: Dict[Strategy, NeuralAgent] = {
            strategy: NeuralAgent(
                state_dim=128,  # Standard state dim for workers
                action_dim=4,  # WAIT, REACT, ENGAGE, INITIATE
                learning_rate=learning_rate,
                discount_factor=discount_factor,
                tau=tau,
                epsilon=epsilon,
                epsilon_end=epsilon_end,
                epsilon_decay=epsilon_decay,
                device=device,
            )
            for strategy in Strategy
        }

        # Current strategy tracking
        self.current_strategy: Optional[Strategy] = None
        self.current_strategy_duration: int = 0
        self.last_meta_state: Optional[np.ndarray] = None
        self.last_meta_action: Optional[Strategy] = None

        # Statistics
        self._stats = MetaControllerStats(epsilon=epsilon)

        logger.debug(
            f"MetaController initialized: state_dim={state_dim}, "
            f"min_duration={min_strategy_duration}, max_duration={max_strategy_duration}"
        )

    def select_strategy(
        self, context: StrategyContext, force_selection: bool = False
    ) -> Strategy:
        """
        Select a high-level strategy using epsilon-greedy policy.

        Args:
            context: Current conversation context
            force_selection: If True, always select new strategy regardless of duration

        Returns:
            Selected strategy
        """
        meta_state = context.to_vector(self.state_dim)

        # Check if we should switch strategies
        if not force_selection and self.current_strategy is not None:
            if not self.should_terminate_strategy(context):
                # Continue with current strategy
                return self.current_strategy

        # Convert to tensor
        state_tensor = torch.from_numpy(meta_state).unsqueeze(0).float().to(self.device)

        # Epsilon-greedy strategy selection
        if np.random.random() < self.epsilon:
            strategy_idx = np.random.randint(0, NUM_STRATEGIES)
        else:
            with torch.no_grad():
                q_values = self.meta_online_network(state_tensor)
                strategy_idx = q_values.argmax(dim=1).item()

        selected_strategy = Strategy(strategy_idx)

        # Update tracking
        if (
            self.current_strategy is not None
            and selected_strategy != self.current_strategy
        ):
            self._record_strategy_switch()

        self.current_strategy = selected_strategy
        self.current_strategy_duration = 0
        self.last_meta_state = meta_state
        self.last_meta_action = selected_strategy

        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
        self._stats.epsilon = self.epsilon

        logger.debug(
            f"Selected strategy: {selected_strategy.name} (epsilon={self.epsilon:.3f})"
        )

        return selected_strategy

    def get_action(
        self,
        strategy: Strategy,
        state: Union[RLState, np.ndarray, torch.Tensor, List[float]],
    ) -> RLAction:
        """
        Get low-level action from worker agent for given strategy.

        Args:
            strategy: Current strategy
            state: Current state for worker agent

        Returns:
            Selected action
        """
        worker = self.workers[strategy]
        action = worker.select_action(state)
        self.current_strategy_duration += 1
        return action

    def update_meta_controller(
        self,
        context: StrategyContext,
        strategy: Strategy,
        reward: float,
        next_context: StrategyContext,
        done: bool = False,
    ) -> float:
        """
        Update meta-controller Q-network using Double DQN.

        Args:
            context: Previous context (state)
            strategy: Strategy that was selected (action)
            reward: Reward received
            next_context: Next context (next_state)
            done: Whether episode is done

        Returns:
            Loss value for this update
        """
        state_tensor = (
            torch.from_numpy(context.to_vector(self.state_dim))
            .unsqueeze(0)
            .float()
            .to(self.device)
        )
        next_state_tensor = (
            torch.from_numpy(next_context.to_vector(self.state_dim))
            .unsqueeze(0)
            .float()
            .to(self.device)
        )
        next_state_tensor = (
            torch.from_numpy(next_context.to_vector())
            .unsqueeze(0)
            .float()
            .to(self.device)
        )
        action_idx = strategy.value

        with torch.no_grad():
            # Double DQN: online network selects best action
            next_q_online = self.meta_online_network(next_state_tensor)
            best_next_action = next_q_online.argmax(dim=1, keepdim=True)

            # Target network evaluates that action
            next_q_target = self.meta_target_network(next_state_tensor)
            next_q_value = next_q_target.gather(1, best_next_action).squeeze(1)

            target_q = reward + (1 - int(done)) * self.discount_factor * next_q_value

        current_q = self.meta_online_network(state_tensor)
        current_q_value = current_q[0, action_idx]

        loss = self.loss_fn(current_q_value, target_q.squeeze())

        self.meta_optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            self.meta_online_network.parameters(), max_norm=1.0
        )
        self.meta_optimizer.step()

        # Soft update target network
        self._soft_update_target()

        # Update statistics
        self._stats.total_meta_updates += 1
        self._stats.strategy_rewards[strategy].append(reward)

        logger.debug(
            f"Meta update: strategy={strategy.name}, reward={reward:.2f}, loss={loss.item():.4f}"
        )

        return loss.item()

    def update_worker(
        self,
        strategy: Strategy,
        state: Union[RLState, np.ndarray, torch.Tensor, List[float]],
        action: Union[RLAction, int],
        reward: float,
        next_state: Union[RLState, np.ndarray, torch.Tensor, List[float]],
        done: bool = False,
    ) -> float:
        """
        Update worker agent for given strategy.

        Args:
            strategy: Strategy whose worker to update
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done

        Returns:
            Loss value
        """
        worker = self.workers[strategy]
        return worker.update(state, action, reward, next_state, done)

    def should_terminate_strategy(self, context: StrategyContext) -> bool:
        """
        Determine if current strategy should terminate.

        Termination conditions:
        1. Minimum duration not met: Cannot terminate yet
        2. Maximum duration exceeded: Must terminate
        3. Context shift: Significant change in sentiment/topic
        4. Strategy timeout: Too long without meaningful progress

        Args:
            context: Current conversation context

        Returns:
            True if strategy should terminate
        """
        if self.current_strategy is None:
            return True

        # Condition 1: Minimum duration not met
        if self.current_strategy_duration < self.min_strategy_duration:
            return False

        # Condition 2: Maximum duration exceeded
        if self.current_strategy_duration >= self.max_strategy_duration:
            logger.debug(
                f"Strategy {self.current_strategy.name} terminated: max duration reached"
            )
            return True

        # Condition 3: Context shift - sentiment changed significantly
        if self.last_meta_state is not None:
            last_sentiment = self.last_meta_state[0]
            current_sentiment = context.user_sentiment
            sentiment_change = abs(current_sentiment - last_sentiment)

            # If sentiment shifted by more than 0.5, consider strategy change
            if (
                sentiment_change > 0.5
                and self.current_strategy_duration >= self.min_strategy_duration
            ):
                logger.debug(
                    f"Strategy {self.current_strategy.name} terminated: sentiment shift {sentiment_change:.2f}"
                )
                return True

        return False

    def get_worker_stats(self, strategy: Strategy) -> Dict[str, Any]:
        """Get statistics for a specific worker agent."""
        return self.workers[strategy].get_stats()

    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics for meta-controller and all workers."""
        stats = {
            "meta_controller": self._stats.to_dict(),
            "current_strategy": self.current_strategy.name
            if self.current_strategy
            else None,
            "current_strategy_duration": self.current_strategy_duration,
            "workers": {s.name: self.workers[s].get_stats() for s in Strategy},
        }
        return stats

    def get_strategy_q_values(self, context: StrategyContext) -> np.ndarray:
        """
        Get Q-values for all strategies given context.

        Args:
            context: Current conversation context

        Returns:
            numpy array of Q-values for each strategy
        """
        meta_state = context.to_vector(self.state_dim)
        state_tensor = torch.from_numpy(meta_state).unsqueeze(0).float().to(self.device)

        with torch.no_grad():
            q_values = self.meta_online_network(state_tensor)

        return q_values.cpu().numpy().flatten()

    def _soft_update_target(self) -> None:
        """Soft update meta-level target network."""
        with torch.no_grad():
            for target_param, online_param in zip(
                self.meta_target_network.parameters(),
                self.meta_online_network.parameters(),
            ):
                target_param.data.copy_(
                    self.tau * online_param.data + (1 - self.tau) * target_param.data
                )

    def _record_strategy_switch(self) -> None:
        """Record statistics when switching strategies."""
        self._stats.total_strategy_switches += 1
        if self.current_strategy is not None:
            duration = self.current_strategy_duration
            self._stats.strategy_durations[self.current_strategy].append(duration)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize meta-controller state."""
        return {
            "state_dim": self.state_dim,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
            "tau": self.tau,
            "epsilon": self.epsilon,
            "epsilon_end": self.epsilon_end,
            "epsilon_decay": self.epsilon_decay,
            "min_strategy_duration": self.min_strategy_duration,
            "max_strategy_duration": self.max_strategy_duration,
            "meta_online_network_state": {
                k: v.cpu().numpy().tolist()
                for k, v in self.meta_online_network.state_dict().items()
            },
            "meta_target_network_state": {
                k: v.cpu().numpy().tolist()
                for k, v in self.meta_target_network.state_dict().items()
            },
            "workers": {s.name: self.workers[s].to_dict() for s in Strategy},
            "stats": {
                "total_meta_updates": self._stats.total_meta_updates,
                "total_strategy_switches": self._stats.total_strategy_switches,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaController":
        """Deserialize meta-controller from dictionary."""
        controller = cls(
            state_dim=data.get("state_dim", META_STATE_DIM),
            learning_rate=data.get("learning_rate", 1e-4),
            discount_factor=data.get("discount_factor", RL_DISCOUNT_FACTOR),
            tau=data.get("tau", 0.005),
            epsilon=data.get("epsilon", 1.0),
            epsilon_end=data.get("epsilon_end", 0.01),
            epsilon_decay=data.get("epsilon_decay", 0.995),
            min_strategy_duration=data.get(
                "min_strategy_duration", MIN_STRATEGY_DURATION
            ),
            max_strategy_duration=data.get(
                "max_strategy_duration", MAX_STRATEGY_DURATION
            ),
        )

        # Restore meta-level networks
        if "meta_online_network_state" in data:
            state_dict = {
                k: torch.tensor(v) for k, v in data["meta_online_network_state"].items()
            }
            controller.meta_online_network.load_state_dict(state_dict)

        if "meta_target_network_state" in data:
            state_dict = {
                k: torch.tensor(v) for k, v in data["meta_target_network_state"].items()
            }
            controller.meta_target_network.load_state_dict(state_dict)

        # Restore workers
        if "workers" in data:
            for strategy in Strategy:
                if strategy.name in data["workers"]:
                    controller.workers[strategy] = NeuralAgent.from_dict(
                        data["workers"][strategy.name]
                    )

        # Restore stats
        if "stats" in data:
            controller._stats.total_meta_updates = data["stats"].get(
                "total_meta_updates", 0
            )
            controller._stats.total_strategy_switches = data["stats"].get(
                "total_strategy_switches", 0
            )

        return controller

    def train_mode(self) -> None:
        """Set all networks to training mode."""
        self.meta_online_network.train()
        for worker in self.workers.values():
            worker.train_mode()

    def eval_mode(self) -> None:
        """Set all networks to evaluation mode."""
        self.meta_online_network.eval()
        self.meta_target_network.eval()
        for worker in self.workers.values():
            worker.eval_mode()

    def reset(self) -> None:
        """Reset current strategy and duration (call at episode end)."""
        if self.current_strategy is not None:
            self._record_strategy_switch()
        self.current_strategy = None
        self.current_strategy_duration = 0
        self.last_meta_state = None
        self.last_meta_action = None
