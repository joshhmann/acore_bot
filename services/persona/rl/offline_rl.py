"""Offline RL Pre-training with Conservative Q-Learning (CQL).

This module implements CQL for pre-training RL agents on historical conversation
data before online deployment. CQL prevents overestimation of Q-values for
out-of-distribution actions by adding a conservative penalty term.

Reference:
    Kumar et al. (2020). Conservative Q-Learning for Offline Reinforcement Learning.
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim

from .neural_agent import NeuralAgent
from .replay_buffer import ReplayBuffer, Transition
from .types import RLAction

logger = logging.getLogger(__name__)


@dataclass
class TransitionBatch:
    """Batch of transitions for training.

    Attributes:
        states: Batch of states [batch_size, state_dim]
        actions: Batch of actions [batch_size]
        rewards: Batch of rewards [batch_size]
        next_states: Batch of next states [batch_size, state_dim]
        dones: Batch of done flags [batch_size]
    """

    states: torch.Tensor
    actions: torch.Tensor
    rewards: torch.Tensor
    next_states: torch.Tensor
    dones: torch.Tensor

    def to(self, device: torch.device) -> "TransitionBatch":
        """Move batch to specified device."""
        return TransitionBatch(
            states=self.states.to(device),
            actions=self.actions.to(device),
            rewards=self.rewards.to(device),
            next_states=self.next_states.to(device),
            dones=self.dones.to(device),
        )


class CQLTrainer:
    """Conservative Q-Learning for offline RL.

    CQL adds a conservative penalty to the standard Bellman error:
    Loss = Bellman_error + alpha * (logsumexp(Q) - Q(dataset_action))

    This prevents the Q-function from overestimating values for
    out-of-distribution actions.

    Attributes:
        agent: NeuralAgent to train
        alpha: CQL regularization coefficient
        optimizer: Adam optimizer for online network
    """

    def __init__(
        self,
        agent: NeuralAgent,
        alpha: float = 1.0,
        learning_rate: float = 1e-4,
        device: Optional[torch.device] = None,
    ):
        """Initialize CQL trainer.

        Args:
            agent: NeuralAgent to pre-train
            alpha: CQL regularization coefficient (default: 1.0)
            learning_rate: Learning rate for optimizer (default: 1e-4)
            device: Device to use for training (default: agent's device)
        """
        self.agent = agent
        self.alpha = alpha
        self.device = device if device is not None else agent.device

        self.optimizer = optim.Adam(agent.online_network.parameters(), lr=learning_rate)

        self._loss_history: List[float] = []
        self._bellman_error_history: List[float] = []
        self._cql_penalty_history: List[float] = []

        logger.info(
            f"CQLTrainer initialized: alpha={alpha}, lr={learning_rate}, "
            f"device={self.device}"
        )

    def compute_cql_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        rewards: torch.Tensor,
        next_states: torch.Tensor,
        dones: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute CQL loss with conservative penalty.

        Loss = MSE(Q, Q_target) + alpha * CQL_penalty

        where CQL_penalty = E[logsumexp(Q(s, a'))] - E[Q(s, a)]

        Args:
            states: Batch of states [batch_size, state_dim]
            actions: Batch of actions [batch_size]
            rewards: Batch of rewards [batch_size]
            next_states: Batch of next states [batch_size, state_dim]
            dones: Batch of done flags [batch_size]

        Returns:
            Tuple of (total_loss, bellman_error, cql_penalty)
        """
        # Standard Bellman error
        current_q = self.agent.online_network(states).gather(1, actions.unsqueeze(1))

        with torch.no_grad():
            # Double DQN: use online network to select action
            next_q_online = self.agent.online_network(next_states)
            best_next_actions = next_q_online.argmax(dim=1, keepdim=True)

            # Use target network to evaluate Q-value
            next_q_target = self.agent.target_network(next_states)
            next_q_values = next_q_target.gather(1, best_next_actions).squeeze(1)

            target_q = (
                rewards + (1 - dones) * self.agent.discount_factor * next_q_values
            )

        bellman_error = F.mse_loss(current_q.squeeze(), target_q)

        # CQL conservative penalty
        # logsumexp over all actions for each state
        all_q = self.agent.online_network(states)
        logsumexp_q = torch.logsumexp(all_q, dim=1)

        # Q-value of the taken action
        dataset_q = all_q.gather(1, actions.unsqueeze(1)).squeeze()

        cql_penalty = (logsumexp_q - dataset_q).mean()

        total_loss = bellman_error + self.alpha * cql_penalty

        return total_loss, bellman_error, cql_penalty

    def train_step(self, batch: TransitionBatch) -> Dict[str, float]:
        """Single training step with CQL.

        Args:
            batch: Batch of transitions

        Returns:
            Dictionary with training metrics
        """
        batch = batch.to(self.device)

        self.optimizer.zero_grad()

        loss, bellman_error, cql_penalty = self.compute_cql_loss(
            batch.states,
            batch.actions,
            batch.rewards,
            batch.next_states,
            batch.dones,
        )

        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            self.agent.online_network.parameters(), max_norm=1.0
        )
        self.optimizer.step()

        # Soft update target network
        self.agent.soft_update()

        # Track metrics
        loss_val = loss.item()
        bellman_val = bellman_error.item()
        cql_val = cql_penalty.item()

        self._loss_history.append(loss_val)
        self._bellman_error_history.append(bellman_val)
        self._cql_penalty_history.append(cql_val)

        # Keep history bounded
        if len(self._loss_history) > 1000:
            self._loss_history = self._loss_history[-1000:]
            self._bellman_error_history = self._bellman_error_history[-1000:]
            self._cql_penalty_history = self._cql_penalty_history[-1000:]

        return {
            "loss": loss_val,
            "bellman_error": bellman_val,
            "cql_penalty": cql_val,
        }

    def get_stats(self) -> Dict[str, float]:
        """Get training statistics.

        Returns:
            Dictionary with mean loss, bellman error, and CQL penalty
        """
        return {
            "mean_loss": np.mean(self._loss_history) if self._loss_history else 0.0,
            "mean_bellman_error": (
                np.mean(self._bellman_error_history)
                if self._bellman_error_history
                else 0.0
            ),
            "mean_cql_penalty": (
                np.mean(self._cql_penalty_history) if self._cql_penalty_history else 0.0
            ),
            "alpha": self.alpha,
        }


def collate_transitions(
    transitions: List[Transition], device: torch.device
) -> TransitionBatch:
    """Convert list of transitions to batched tensors.

    Args:
        transitions: List of Transition objects
        device: Device to move tensors to

    Returns:
        TransitionBatch with batched tensors
    """
    states = []
    actions = []
    rewards = []
    next_states = []
    dones = []

    for t in transitions:
        # Convert state to numpy array
        if isinstance(t.state, tuple):
            arr = np.zeros(128, dtype=np.float32)
            arr[0] = t.state[0] / 10.0
            arr[1] = t.state[1] / 100.0
            arr[2] = t.state[2] / 50.0
            states.append(arr)
        elif isinstance(t.state, np.ndarray):
            states.append(t.state.astype(np.float32))
        else:
            states.append(np.array(t.state, dtype=np.float32))

        # Convert next_state
        if isinstance(t.next_state, tuple):
            arr = np.zeros(128, dtype=np.float32)
            arr[0] = t.next_state[0] / 10.0
            arr[1] = t.next_state[1] / 100.0
            arr[2] = t.next_state[2] / 50.0
            next_states.append(arr)
        elif isinstance(t.next_state, np.ndarray):
            next_states.append(t.next_state.astype(np.float32))
        else:
            next_states.append(np.array(t.next_state, dtype=np.float32))

        actions.append(t.action.value if isinstance(t.action, RLAction) else t.action)
        rewards.append(t.reward)
        dones.append(float(t.done))

    return TransitionBatch(
        states=torch.tensor(np.array(states), dtype=torch.float32, device=device),
        actions=torch.tensor(actions, dtype=torch.long, device=device),
        rewards=torch.tensor(rewards, dtype=torch.float32, device=device),
        next_states=torch.tensor(
            np.array(next_states), dtype=torch.float32, device=device
        ),
        dones=torch.tensor(dones, dtype=torch.float32, device=device),
    )


class OfflineRLDataset:
    """Load and process historical conversation data for offline RL.

    Loads conversation history from SQLite, filters by quality metrics,
    and converts to transitions for offline training.

    Attributes:
        db_path: Path to SQLite database
        transitions: List of loaded transitions
    """

    def __init__(self, db_path: Union[str, Path]):
        """Initialize dataset.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.transitions: List[Transition] = []
        self._train_indices: List[int] = []
        self._val_indices: List[int] = []

    def load_from_history(
        self,
        min_quality_score: float = 0.5,
        max_conversations: int = 10000,
        reward_threshold: Optional[float] = None,
    ) -> int:
        """Load historical conversations from SQLite.

        Filters:
        - Min quality score (exclude low-quality interactions)
        - Max conversations (limit dataset size)
        - Valid state-action-reward sequences

        Args:
            min_quality_score: Minimum quality score for interactions (default: 0.5)
            max_conversations: Maximum number of conversations to load (default: 10000)
            reward_threshold: Optional minimum reward threshold

        Returns:
            Number of transitions loaded
        """
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
            return 0

        self.transitions = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Query messages with metadata
                # Note: This assumes a schema with quality metrics
                # Adjust query based on actual database schema
                cursor.execute(
                    """
                    SELECT 
                        m.channel_id,
                        m.role,
                        m.content,
                        m.username,
                        m.user_id,
                        m.timestamp,
                        COALESCE(r.quality_score, 0.5) as quality_score,
                        COALESCE(r.reward, 0.0) as reward,
                        COALESCE(r.action_taken, 0) as action_taken
                    FROM messages m
                    LEFT JOIN rewards r ON m.id = r.message_id
                    WHERE COALESCE(r.quality_score, 0.5) >= ?
                    ORDER BY m.timestamp
                    LIMIT ?
                    """,
                    (min_quality_score, max_conversations * 10),
                )

                rows = cursor.fetchall()

                # Convert to transitions
                # Group by channel and create state transitions
                channel_messages: Dict[int, List[Dict]] = {}
                for row in rows:
                    channel_id = row[0]
                    if channel_id not in channel_messages:
                        channel_messages[channel_id] = []

                    channel_messages[channel_id].append(
                        {
                            "role": row[1],
                            "content": row[2],
                            "username": row[3],
                            "user_id": row[4],
                            "timestamp": row[5],
                            "quality_score": row[6],
                            "reward": row[7],
                            "action_taken": row[8],
                        }
                    )

                # Create transitions from message sequences
                for channel_id, messages in channel_messages.items():
                    for i in range(len(messages) - 1):
                        current = messages[i]
                        next_msg = messages[i + 1]

                        # Skip if reward threshold not met
                        if (
                            reward_threshold is not None
                            and current["reward"] < reward_threshold
                        ):
                            continue

                        # Create state from message context
                        # State: (sentiment_bin, time_since_last_bin, message_count_bin)
                        state = self._extract_state(current, i)
                        next_state = self._extract_state(next_msg, i + 1)

                        action = RLAction(current.get("action_taken", 0))
                        reward = current.get("reward", 0.0)

                        transition = Transition(
                            state=state,
                            action=action,
                            reward=reward,
                            next_state=next_state,
                            done=False,  # Episodes don't really end in chat
                        )

                        self.transitions.append(transition)

                        if len(self.transitions) >= max_conversations:
                            break

                    if len(self.transitions) >= max_conversations:
                        break

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return 0

        logger.info(f"Loaded {len(self.transitions)} transitions from {self.db_path}")
        return len(self.transitions)

    def _extract_state(self, message: Dict, index: int) -> Tuple[int, int, int]:
        """Extract RL state from message.

        Args:
            message: Message dictionary
            index: Message index in sequence

        Returns:
            RLState tuple (sentiment_bin, time_since_last_bin, message_count_bin)
        """
        # Simple state extraction - can be enhanced with actual sentiment analysis
        sentiment_bin = 5  # Neutral
        time_since_last_bin = min(index, 99)  # Time proxy
        message_count_bin = min(index, 49)  # Count proxy

        return (sentiment_bin, time_since_last_bin, message_count_bin)

    def split_train_val(
        self, val_ratio: float = 0.1, seed: int = 42
    ) -> Tuple[int, int]:
        """Split transitions into training and validation sets.

        Args:
            val_ratio: Fraction of data to use for validation (default: 0.1)
            seed: Random seed for reproducibility

        Returns:
            Tuple of (train_size, val_size)
        """
        if not self.transitions:
            return 0, 0

        np.random.seed(seed)
        indices = np.random.permutation(len(self.transitions))

        val_size = int(len(indices) * val_ratio)
        self._val_indices = indices[:val_size].tolist()
        self._train_indices = indices[val_size:].tolist()

        logger.info(
            f"Split dataset: {len(self._train_indices)} train, "
            f"{len(self._val_indices)} val"
        )

        return len(self._train_indices), len(self._val_indices)

    def get_train_batch(self, batch_size: int) -> List[Transition]:
        """Get a random batch of training transitions.

        Args:
            batch_size: Number of transitions to sample

        Returns:
            List of transitions
        """
        if not self._train_indices:
            return []

        indices = np.random.choice(
            self._train_indices,
            size=min(batch_size, len(self._train_indices)),
            replace=False,
        )
        return [self.transitions[i] for i in indices]

    def get_val_data(self) -> List[Transition]:
        """Get all validation transitions.

        Returns:
            List of validation transitions
        """
        return [self.transitions[i] for i in self._val_indices]

    def to_replay_buffer(self) -> ReplayBuffer:
        """Convert all transitions to a replay buffer.

        Returns:
            ReplayBuffer containing all transitions
        """
        buffer = ReplayBuffer(capacity=max(len(self.transitions), 1000))
        for transition in self.transitions:
            buffer.add_sync(transition)
        return buffer

    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics.

        Returns:
            Dictionary with dataset statistics
        """
        if not self.transitions:
            return {"total_transitions": 0}

        rewards = [t.reward for t in self.transitions]
        actions = [t.action.value for t in self.transitions]

        return {
            "total_transitions": len(self.transitions),
            "train_size": len(self._train_indices),
            "val_size": len(self._val_indices),
            "mean_reward": float(np.mean(rewards)),
            "std_reward": float(np.std(rewards)),
            "min_reward": float(np.min(rewards)),
            "max_reward": float(np.max(rewards)),
            "action_distribution": {
                action: actions.count(action) for action in set(actions)
            },
        }


def validate_agent(
    agent: NeuralAgent,
    val_transitions: List[Transition],
    device: torch.device,
) -> Dict[str, float]:
    """Validate agent on held-out data.

    Args:
        agent: NeuralAgent to validate
        val_transitions: List of validation transitions
        device: Device to use

    Returns:
        Dictionary with validation metrics
    """
    if not val_transitions:
        return {"avg_q": 0.0, "avg_reward": 0.0}

    agent.eval_mode()

    q_values = []
    rewards = []

    with torch.no_grad():
        for transition in val_transitions:
            # Convert state to tensor
            if isinstance(transition.state, tuple):
                arr = np.zeros(agent.state_dim, dtype=np.float32)
                arr[0] = transition.state[0] / 10.0
                arr[1] = transition.state[1] / 100.0
                arr[2] = transition.state[2] / 50.0
                state_tensor = torch.from_numpy(arr).unsqueeze(0).to(device)
            elif isinstance(transition.state, np.ndarray):
                state_tensor = (
                    torch.from_numpy(transition.state.astype(np.float32))
                    .unsqueeze(0)
                    .to(device)
                )
            else:
                state_tensor = (
                    torch.tensor(transition.state, dtype=torch.float32)
                    .unsqueeze(0)
                    .to(device)
                )

            q = agent.online_network(state_tensor)
            action_idx = (
                transition.action.value
                if isinstance(transition.action, RLAction)
                else transition.action
            )
            q_values.append(q[0, action_idx].item())
            rewards.append(transition.reward)

    return {
        "avg_q": float(np.mean(q_values)),
        "std_q": float(np.std(q_values)),
        "avg_reward": float(np.mean(rewards)),
        "num_samples": len(val_transitions),
    }
