"""Neural RL Agent with Double DQN implementation."""

import io
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Attempt to import PyTorch. If unavailable, expose a flag and implement
# safe fallbacks for runtime usage when neural RL is not possible.
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .constants import RL_DISCOUNT_FACTOR
from .types import RLAction, RLState

logger = logging.getLogger(__name__)

NEURAL_DEFAULT_STATE_DIM = 128
NEURAL_DEFAULT_ACTION_DIM = 4
NEURAL_DEFAULT_LEARNING_RATE = 1e-4
NEURAL_DEFAULT_TAU = 0.005
NEURAL_DEFAULT_HIDDEN_DIMS = (256, 256)
NEURAL_DEFAULT_EPSILON_START = 1.0
NEURAL_DEFAULT_EPSILON_END = 0.01
NEURAL_DEFAULT_EPSILON_DECAY = 0.995

if TORCH_AVAILABLE:

    class QNetwork(nn.Module):
        """Q-Network for estimating action values."""

        def __init__(
            self,
            state_dim: int = NEURAL_DEFAULT_STATE_DIM,
            action_dim: int = NEURAL_DEFAULT_ACTION_DIM,
            hidden_dims: Tuple[int, ...] = NEURAL_DEFAULT_HIDDEN_DIMS,
        ):
            super().__init__()
            self.state_dim = state_dim
            self.action_dim = action_dim

            layers: List[nn.Module] = []
            prev_dim = state_dim

            for hidden_dim in hidden_dims:
                layers.append(nn.Linear(prev_dim, hidden_dim))
                layers.append(nn.ReLU())
                prev_dim = hidden_dim

            layers.append(nn.Linear(prev_dim, action_dim))
            self.network = nn.Sequential(*layers)

            self._init_weights()

        def _init_weights(self) -> None:
            for module in self.modules():
                if isinstance(module, nn.Linear):
                    nn.init.xavier_uniform_(module.weight)
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)

        def forward(self, state: torch.Tensor) -> torch.Tensor:
            return self.network(state)

    @dataclass
    class NeuralAgentStats:
        """Training statistics for the neural agent."""

        total_updates: int = 0
        total_episodes: int = 0
        mean_loss: float = 0.0
        mean_q_value: float = 0.0
        epsilon: float = NEURAL_DEFAULT_EPSILON_START
        inference_times_ms: List[float] = field(default_factory=list)
        update_times_ms: List[float] = field(default_factory=list)

        def to_dict(self) -> Dict[str, Any]:
            return {
                "total_updates": self.total_updates,
                "total_episodes": self.total_episodes,
                "mean_loss": self.mean_loss,
                "mean_q_value": self.mean_q_value,
                "epsilon": self.epsilon,
                "p50_inference_ms": np.percentile(self.inference_times_ms, 50)
                if self.inference_times_ms
                else 0.0,
                "p95_inference_ms": np.percentile(self.inference_times_ms, 95)
                if self.inference_times_ms
                else 0.0,
                "mean_update_ms": np.mean(self.update_times_ms)
                if self.update_times_ms
                else 0.0,
            }

    class NeuralAgent:
        """
        Double DQN Agent for persona behavior learning.

        Uses Double DQN algorithm to avoid overestimation bias:
        - Online network selects the best action
        - Target network evaluates the Q-value of that action

        Target network is updated via soft updates:
            theta_target = tau * theta_online + (1 - tau) * theta_target
        """

        def __init__(
            self,
            state_dim: int = NEURAL_DEFAULT_STATE_DIM,
            action_dim: int = NEURAL_DEFAULT_ACTION_DIM,
            learning_rate: float = NEURAL_DEFAULT_LEARNING_RATE,
            discount_factor: float = RL_DISCOUNT_FACTOR,
            tau: float = NEURAL_DEFAULT_TAU,
            hidden_dims: Tuple[int, ...] = NEURAL_DEFAULT_HIDDEN_DIMS,
            epsilon: float = NEURAL_DEFAULT_EPSILON_START,
            epsilon_end: float = NEURAL_DEFAULT_EPSILON_END,
            epsilon_decay: float = NEURAL_DEFAULT_EPSILON_DECAY,
            device: Optional[str] = None,
        ):
            """
            Initialize the Double DQN agent.

            Args:
                state_dim: Dimension of state vector (default 128)
                action_dim: Number of discrete actions (default 4: WAIT, REACT, ENGAGE, INITIATE)
                learning_rate: Learning rate for optimizer
                discount_factor: Discount factor (gamma) for future rewards
                tau: Soft update parameter for target network
                hidden_dims: Tuple of hidden layer sizes
                epsilon: Initial exploration rate
                epsilon_end: Minimum exploration rate
                epsilon_decay: Decay rate for epsilon
                device: Device to use ('cpu', 'cuda'). Default: auto-detect
            """
            self.state_dim = state_dim
            self.action_dim = action_dim
            self.learning_rate = learning_rate
            self.discount_factor = discount_factor
            self.tau = tau
            self.hidden_dims = hidden_dims
            self.epsilon = epsilon
            self.epsilon_end = epsilon_end
            self.epsilon_decay = epsilon_decay

            if device is None:
                self.device = torch.device("cpu")
            else:
                self.device = torch.device(device)

            self.online_network = QNetwork(state_dim, action_dim, hidden_dims).to(
                self.device
            )
            self.target_network = QNetwork(state_dim, action_dim, hidden_dims).to(
                self.device
            )

            self.target_network.load_state_dict(self.online_network.state_dict())

            for param in self.target_network.parameters():
                param.requires_grad = False

            self.optimizer = optim.Adam(
                self.online_network.parameters(), lr=learning_rate
            )
            self.loss_fn = nn.SmoothL1Loss()

            self._stats = NeuralAgentStats(epsilon=epsilon)
            self._loss_history: List[float] = []
            self._q_value_history: List[float] = []

            self.dirty = False

            logger.debug(
                f"NeuralAgent initialized: state_dim={state_dim}, action_dim={action_dim}, "
                f"hidden_dims={hidden_dims}, device={self.device}"
            )

        def _state_to_tensor(
            self, state: Union[RLState, np.ndarray, torch.Tensor, List[float]]
        ) -> torch.Tensor:
            """
            Convert state to tensor.

            Supports multiple input formats:
            - RLState (tuple of 3 ints): Embedded into state_dim vector
            - numpy array: Direct conversion
            - torch Tensor: Already tensor
            - List of floats: Direct conversion
            """
            if isinstance(state, torch.Tensor):
                tensor = state.float().to(self.device)
                if tensor.dim() == 1:
                    tensor = tensor.unsqueeze(0)
                return tensor

            if isinstance(state, tuple) and len(state) == 3:
                arr = np.zeros(self.state_dim, dtype=np.float32)
                arr[0] = state[0] / 10.0
                arr[1] = state[1] / 100.0
                arr[2] = state[2] / 50.0
                tensor = torch.from_numpy(arr).unsqueeze(0).to(self.device)
                return tensor

            if isinstance(state, np.ndarray):
                tensor = torch.from_numpy(state.astype(np.float32)).to(self.device)
                if tensor.dim() == 1:
                    tensor = tensor.unsqueeze(0)
                return tensor

            if isinstance(state, list):
                tensor = torch.tensor(state, dtype=torch.float32).to(self.device)
                if tensor.dim() == 1:
                    tensor = tensor.unsqueeze(0)
                return tensor

            raise TypeError(f"Unsupported state type: {type(state)}")

        def select_action(
            self,
            state: Union[RLState, np.ndarray, torch.Tensor, List[float]],
            epsilon: Optional[float] = None,
        ) -> RLAction:
            """
            Select an action using epsilon-greedy policy.

            Args:
                state: Current state (various formats supported)
                epsilon: Override exploration rate. If None, uses internal epsilon.

            Returns:
                RLAction enum value
            """
            start_time = time.perf_counter()

            if epsilon is None:
                epsilon = self.epsilon

            if np.random.random() < epsilon:
                action_idx = np.random.randint(0, self.action_dim)
            else:
                state_tensor = self._state_to_tensor(state)
                with torch.no_grad():
                    q_values = self.online_network(state_tensor)
                    action_idx = q_values.argmax(dim=1).item()

            self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
            self._stats.epsilon = self.epsilon

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._stats.inference_times_ms.append(elapsed_ms)
            if len(self._stats.inference_times_ms) > 1000:
                self._stats.inference_times_ms = self._stats.inference_times_ms[-1000:]

            return RLAction(action_idx)

        def get_q_values(
            self, state: Union[RLState, np.ndarray, torch.Tensor, List[float]]
        ) -> np.ndarray:
            """
            Get Q-values for all actions given a state.

            Args:
                state: Current state

            Returns:
                numpy array of Q-values for each action
            """
            state_tensor = self._state_to_tensor(state)
            with torch.no_grad():
                q_values = self.online_network(state_tensor)
            return q_values.cpu().numpy().flatten()

        def update(
            self,
            state: Union[RLState, np.ndarray, torch.Tensor, List[float]],
            action: Union[RLAction, int],
            reward: float,
            next_state: Union[RLState, np.ndarray, torch.Tensor, List[float]],
            done: bool = False,
        ) -> float:
            """
            Perform a Double DQN update step.

            Double DQN algorithm:
            1. Use online network to SELECT the best action for next_state
            2. Use target network to EVALUATE the Q-value of that action
            3. Compute TD target: r + gamma * Q_target(s', argmax_a Q_online(s', a))
            4. Update online network via gradient descent

            Args:
                state: Current state
                action: Action taken (RLAction or int)
                reward: Reward received
                next_state: Next state
                done: Whether episode is done

            Returns:
                Loss value for this update
            """
            start_time = time.perf_counter()

            state_tensor = self._state_to_tensor(state)
            next_state_tensor = self._state_to_tensor(next_state)
            action_idx = action.value if isinstance(action, RLAction) else action

            with torch.no_grad():
                next_q_online = self.online_network(next_state_tensor)
                best_next_action = next_q_online.argmax(dim=1, keepdim=True)

                next_q_target = self.target_network(next_state_tensor)
                next_q_value = next_q_target.gather(1, best_next_action).squeeze(1)

                target_q = (
                    reward + (1 - int(done)) * self.discount_factor * next_q_value
                )

            current_q = self.online_network(state_tensor)
            current_q_value = current_q[0, action_idx]

            loss = self.loss_fn(current_q_value, target_q.squeeze())

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                self.online_network.parameters(), max_norm=1.0
            )
            self.optimizer.step()

            self.soft_update()

            loss_value = loss.item()
            self._loss_history.append(loss_value)
            self._q_value_history.append(current_q_value.item())

            if len(self._loss_history) > 1000:
                self._loss_history = self._loss_history[-1000:]
            if len(self._q_value_history) > 1000:
                self._q_value_history = self._q_value_history[-1000:]

            self._stats.total_updates += 1
            self._stats.mean_loss = np.mean(self._loss_history)
            self._stats.mean_q_value = np.mean(self._q_value_history)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._stats.update_times_ms.append(elapsed_ms)
            if len(self._stats.update_times_ms) > 1000:
                self._stats.update_times_ms = self._stats.update_times_ms[-1000:]

            self.dirty = True

            logger.debug(
                f"DQN Update: action={RLAction(action_idx).name}, reward={reward:.2f}, "
                f"Q: {current_q_value.item():.3f}, loss={loss_value:.4f}"
            )

            return loss_value

        def soft_update(self, tau: Optional[float] = None) -> None:
            """
            Soft update target network: theta_target = tau * theta_online + (1-tau) * theta_target.

            Args:
                tau: Interpolation parameter. If None, uses self.tau
            """
            if tau is None:
                tau = self.tau

            with torch.no_grad():
                for target_param, online_param in zip(
                    self.target_network.parameters(), self.online_network.parameters()
                ):
                    target_param.data.copy_(
                        tau * online_param.data + (1 - tau) * target_param.data
                    )

        def hard_update(self) -> None:
            """Copy online network weights to target network."""
            self.target_network.load_state_dict(self.online_network.state_dict())

        def get_stats(self) -> Dict[str, Any]:
            """Get training statistics for dashboard monitoring."""
            stats = self._stats.to_dict()
            stats.update(
                {
                    "state_dim": self.state_dim,
                    "action_dim": self.action_dim,
                    "device": str(self.device),
                    "learning_rate": self.learning_rate,
                    "discount_factor": self.discount_factor,
                    "tau": self.tau,
                }
            )
            return stats

        def to_dict(self) -> Dict[str, Any]:
            """Serialize agent state including network weights, optimizer state, and hyperparameters."""
            return {
                "state_dim": self.state_dim,
                "action_dim": self.action_dim,
                "learning_rate": self.learning_rate,
                "discount_factor": self.discount_factor,
                "tau": self.tau,
                "hidden_dims": list(self.hidden_dims),
                "epsilon": self.epsilon,
                "epsilon_end": self.epsilon_end,
                "epsilon_decay": self.epsilon_decay,
                "online_network_state": {
                    k: v.cpu().numpy().tolist()
                    for k, v in self.online_network.state_dict().items()
                },
                "target_network_state": {
                    k: v.cpu().numpy().tolist()
                    for k, v in self.target_network.state_dict().items()
                },
                "optimizer_state": self._serialize_optimizer_state(),
                "stats": {
                    "total_updates": self._stats.total_updates,
                    "total_episodes": self._stats.total_episodes,
                    "mean_loss": self._stats.mean_loss,
                    "mean_q_value": self._stats.mean_q_value,
                },
            }

        def _serialize_optimizer_state(self) -> Dict[str, Any]:
            state = self.optimizer.state_dict()
            serialized: Dict[str, Any] = {"param_groups": state["param_groups"]}
            return serialized

        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> "NeuralAgent":
            """
            Deserialize agent from dictionary.

            Args:
                data: Dictionary from to_dict()

            Returns:
                Restored NeuralAgent instance
            """
            agent = cls(
                state_dim=data.get("state_dim", NEURAL_DEFAULT_STATE_DIM),
                action_dim=data.get("action_dim", NEURAL_DEFAULT_ACTION_DIM),
                learning_rate=data.get("learning_rate", NEURAL_DEFAULT_LEARNING_RATE),
                discount_factor=data.get("discount_factor", RL_DISCOUNT_FACTOR),
                tau=data.get("tau", NEURAL_DEFAULT_TAU),
                hidden_dims=tuple(data.get("hidden_dims", NEURAL_DEFAULT_HIDDEN_DIMS)),
                epsilon=data.get("epsilon", NEURAL_DEFAULT_EPSILON_START),
                epsilon_end=data.get("epsilon_end", NEURAL_DEFAULT_EPSILON_END),
                epsilon_decay=data.get("epsilon_decay", NEURAL_DEFAULT_EPSILON_DECAY),
            )

            if "online_network_state" in data:
                state_dict = {
                    k: torch.tensor(v) for k, v in data["online_network_state"].items()
                }
                agent.online_network.load_state_dict(state_dict)

            if "target_network_state" in data:
                state_dict = {
                    k: torch.tensor(v) for k, v in data["target_network_state"].items()
                }
                agent.target_network.load_state_dict(state_dict)

            if "stats" in data:
                agent._stats.total_updates = data["stats"].get("total_updates", 0)
                agent._stats.total_episodes = data["stats"].get("total_episodes", 0)
                agent._stats.mean_loss = data["stats"].get("mean_loss", 0.0)
                agent._stats.mean_q_value = data["stats"].get("mean_q_value", 0.0)

            return agent

        def export_onnx(self, path: str, opset_version: int = 14) -> None:
            """
            Export online network to ONNX format for optimized inference.

            Args:
                path: Output file path (.onnx)
                opset_version: ONNX opset version (default 14)
            """
            self.online_network.eval()

            dummy_input = torch.randn(1, self.state_dim, device=self.device)

            torch.onnx.export(
                self.online_network,
                dummy_input,
                path,
                export_params=True,
                opset_version=opset_version,
                do_constant_folding=True,
                input_names=["state"],
                output_names=["q_values"],
                dynamic_axes={
                    "state": {0: "batch_size"},
                    "q_values": {0: "batch_size"},
                },
            )

            logger.info(f"Exported neural agent to ONNX: {path}")

        def export_onnx_bytes(self, opset_version: int = 14) -> bytes:
            """
            Export online network to ONNX format as bytes.

            Args:
                opset_version: ONNX opset version

            Returns:
                ONNX model as bytes
            """
            buffer = io.BytesIO()
            self.online_network.eval()

            dummy_input = torch.randn(1, self.state_dim, device=self.device)

            torch.onnx.export(
                self.online_network,
                dummy_input,
                buffer,
                export_params=True,
                opset_version=opset_version,
                do_constant_folding=True,
                input_names=["state"],
                output_names=["q_values"],
                dynamic_axes={
                    "state": {0: "batch_size"},
                    "q_values": {0: "batch_size"},
                },
            )

            return buffer.getvalue()

        def train_mode(self) -> None:
            """Set networks to training mode."""
            self.online_network.train()

        def eval_mode(self) -> None:
            """Set networks to evaluation mode."""
            self.online_network.eval()
            self.target_network.eval()

        def get_action(
            self, state: Union[RLState, np.ndarray, torch.Tensor, List[float]]
        ) -> RLAction:
            """Alias for select_action for compatibility with RLAgent interface."""
            return self.select_action(state)
else:
    TORCH_AVAILABLE = False

    class NeuralAgent:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "PyTorch is not available. Install PyTorch to use neural RL features."
            )

    # Provide a placeholder DQNNetwork to keep imports stable if referenced elsewhere
    class DQNNetwork:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "PyTorch is not available. Install PyTorch to use neural RL features."
            )
