"""Experience Replay Buffer for RL training."""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import List, Optional, Union

import numpy as np
import torch

from .types import RLAction, RLState

logger = logging.getLogger(__name__)

DEFAULT_BUFFER_CAPACITY = 10000


@dataclass
class Transition:
    """A single transition (s, a, r, s', done) for experience replay.

    Attributes:
        state: Current state (RLState tuple, numpy array, or torch Tensor)
        action: Action taken (RLAction enum)
        reward: Reward received (float)
        next_state: Next state after taking action
        done: Whether episode terminated after this transition
    """

    state: Union[RLState, np.ndarray, torch.Tensor]
    action: RLAction
    reward: float
    next_state: Union[RLState, np.ndarray, torch.Tensor]
    done: bool = False


class ReplayBuffer:
    """
    Experience Replay Buffer for storing and sampling transitions.

    Uses circular buffer implementation for memory efficiency.
    Thread-safe for async access using asyncio.Lock.

    Features:
    - Circular buffer with configurable capacity
    - Uniform random sampling
    - Memory-efficient numpy storage
    - Thread-safe for async Discord bot context
    - Tracks buffer utilization

    Example:
        buffer = ReplayBuffer(capacity=10000)
        await buffer.add(Transition(state, action, reward, next_state))
        batch = await buffer.sample(batch_size=32)
    """

    def __init__(self, capacity: int = DEFAULT_BUFFER_CAPACITY):
        """
        Initialize the replay buffer.

        Args:
            capacity: Maximum number of transitions to store (default: 10000).
                     Older transitions are overwritten when capacity is reached.
        """
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")

        self.capacity = capacity
        self._buffer: List[Transition] = []
        self._position = 0
        self._lock = asyncio.Lock()

        logger.debug(f"ReplayBuffer initialized with capacity={capacity}")

    async def add(self, transition: Transition) -> None:
        """
        Add a transition to the buffer.

        Uses circular buffer logic: when full, overwrites oldest entries.
        Thread-safe via asyncio.Lock.

        Args:
            transition: The (s, a, r, s', done) transition to store
        """
        async with self._lock:
            if len(self._buffer) < self.capacity:
                self._buffer.append(transition)
            else:
                self._buffer[self._position] = transition

            self._position = (self._position + 1) % self.capacity

    async def sample(self, batch_size: int) -> List[Transition]:
        """
        Sample a random batch of transitions.

        Uses uniform random sampling without replacement.
        Thread-safe via asyncio.Lock.

        Args:
            batch_size: Number of transitions to sample

        Returns:
            List of randomly sampled Transition objects

        Raises:
            ValueError: If batch_size <= 0
            RuntimeError: If buffer has fewer samples than requested
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        async with self._lock:
            current_size = len(self._buffer)

            if current_size == 0:
                raise RuntimeError(
                    "Cannot sample from empty buffer. Add transitions before sampling."
                )

            if batch_size > current_size:
                raise RuntimeError(
                    f"Cannot sample {batch_size} transitions from buffer "
                    f"with only {current_size} samples. "
                    f"Add more transitions or reduce batch_size."
                )

            indices = random.sample(range(current_size), batch_size)
            return [self._buffer[i] for i in indices]

    def add_sync(self, transition: Transition) -> None:
        """
        Synchronous version of add for non-async contexts.

        Warning: Not thread-safe. Use add() in async contexts.

        Args:
            transition: The transition to store
        """
        if len(self._buffer) < self.capacity:
            self._buffer.append(transition)
        else:
            self._buffer[self._position] = transition

        self._position = (self._position + 1) % self.capacity

    def sample_sync(self, batch_size: int) -> List[Transition]:
        """
        Synchronous version of sample for non-async contexts.

        Warning: Not thread-safe. Use sample() in async contexts.

        Args:
            batch_size: Number of transitions to sample

        Returns:
            List of randomly sampled Transition objects
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        current_size = len(self._buffer)

        if current_size == 0:
            raise RuntimeError(
                "Cannot sample from empty buffer. Add transitions before sampling."
            )

        if batch_size > current_size:
            raise RuntimeError(
                f"Cannot sample {batch_size} transitions from buffer "
                f"with only {current_size} samples."
            )

        indices = random.sample(range(current_size), batch_size)
        return [self._buffer[i] for i in indices]

    def __len__(self) -> int:
        """Return current number of transitions in buffer."""
        return len(self._buffer)

    @property
    def is_full(self) -> bool:
        """Return True if buffer has reached capacity."""
        return len(self._buffer) >= self.capacity

    @property
    def utilization(self) -> float:
        """
        Return buffer utilization as a percentage (0.0 to 100.0).

        Returns:
            Current size / capacity * 100
        """
        return (len(self._buffer) / self.capacity) * 100.0

    def clear(self) -> None:
        """Clear all transitions from the buffer."""
        self._buffer.clear()
        self._position = 0
        logger.debug("ReplayBuffer cleared")

    def get_stats(self) -> dict:
        """
        Get buffer statistics for monitoring.

        Returns:
            Dictionary with buffer stats (size, capacity, utilization, etc.)
        """
        return {
            "current_size": len(self._buffer),
            "capacity": self.capacity,
            "utilization_percent": self.utilization,
            "is_full": self.is_full,
            "position": self._position,
        }


class PrioritizedReplayBuffer(ReplayBuffer):
    """
    Prioritized Experience Replay Buffer (placeholder for future implementation).

    TODO: Implement priority-based sampling using TD-error.
    Currently falls back to uniform sampling.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_BUFFER_CAPACITY,
        alpha: float = 0.6,
        beta: float = 0.4,
    ):
        """
        Initialize prioritized replay buffer.

        Args:
            capacity: Maximum buffer size
            alpha: Priority exponent (0 = uniform, 1 = full prioritization)
            beta: Importance sampling exponent
        """
        super().__init__(capacity)
        self.alpha = alpha
        self.beta = beta
        self._priorities: List[float] = []

        logger.debug(f"PrioritizedReplayBuffer initialized: alpha={alpha}, beta={beta}")

    async def add(
        self, transition: Transition, priority: Optional[float] = None
    ) -> None:
        """
        Add transition with optional priority.

        Args:
            transition: The transition to store
            priority: Priority value (higher = more likely to sample).
                     If None, uses max priority in buffer.
        """
        async with self._lock:
            max_priority = max(self._priorities) if self._priorities else 1.0
            if priority is None:
                priority = max_priority

            if len(self._buffer) < self.capacity:
                self._buffer.append(transition)
                self._priorities.append(priority)
            else:
                self._buffer[self._position] = transition
                self._priorities[self._position] = priority

            self._position = (self._position + 1) % self.capacity

    async def sample(
        self, batch_size: int
    ) -> tuple[List[Transition], List[int], List[float]]:
        """
        Sample batch with importance sampling weights.

        Args:
            batch_size: Number of transitions to sample

        Returns:
            Tuple of (transitions, indices, importance_weights)
        """
        transitions = await super().sample(batch_size)

        async with self._lock:
            current_size = len(self._buffer)
            indices = random.sample(range(current_size), batch_size)
            weights = [1.0] * batch_size

        return transitions, indices, weights

    async def update_priorities(
        self, indices: List[int], priorities: List[float]
    ) -> None:
        """
        Update priorities for sampled transitions.

        Args:
            indices: Indices of transitions to update
            priorities: New priority values (typically TD-error)
        """
        async with self._lock:
            for idx, priority in zip(indices, priorities):
                if 0 <= idx < len(self._priorities):
                    self._priorities[idx] = priority**self.alpha
