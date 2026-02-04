#!/usr/bin/env python3
"""Training script for offline RL with CQL.

This script pre-trains a NeuralAgent on historical conversation data
using Conservative Q-Learning (CQL) before online deployment.

Usage:
    python scripts/train_offline_rl.py --db-path data/conversations.db
    python scripts/train_offline_rl.py --dry-run  # Test with synthetic data
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.persona.rl.neural_agent import NeuralAgent
from services.persona.rl.offline_rl import (
    CQLTrainer,
    OfflineRLDataset,
    Transition,
    TransitionBatch,
    collate_transitions,
    validate_agent,
)
from services.persona.rl.replay_buffer import ReplayBuffer
from services.persona.rl.types import RLAction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_synthetic_dataset(
    num_transitions: int = 1000,
    state_dim: int = 128,
    action_dim: int = 4,
) -> OfflineRLDataset:
    """Create synthetic dataset for testing.

    Args:
        num_transitions: Number of transitions to generate
        state_dim: State dimension
        action_dim: Number of actions

    Returns:
        OfflineRLDataset with synthetic transitions
    """
    dataset = OfflineRLDataset(db_path="synthetic")
    dataset.transitions = []

    np.random.seed(42)

    for i in range(num_transitions):
        # Create state
        state = np.random.randn(state_dim).astype(np.float32)
        next_state = np.random.randn(state_dim).astype(np.float32)

        # Create action (biased toward better actions for pattern)
        if i % 4 == 0:
            action = RLAction.WAIT
            reward = np.random.normal(0.5, 0.3)
        elif i % 4 == 1:
            action = RLAction.REACT
            reward = np.random.normal(0.8, 0.2)
        elif i % 4 == 2:
            action = RLAction.ENGAGE
            reward = np.random.normal(1.0, 0.2)
        else:
            action = RLAction.INITIATE
            reward = np.random.normal(0.3, 0.4)

        transition = Transition(
            state=state,
            action=action,
            reward=float(np.clip(reward, -2.0, 2.0)),
            next_state=next_state,
            done=False,
        )
        dataset.transitions.append(transition)

    logger.info(f"Created synthetic dataset with {num_transitions} transitions")
    return dataset


def train_epoch(
    trainer: CQLTrainer,
    dataset: OfflineRLDataset,
    batch_size: int,
    device: torch.device,
) -> dict:
    """Train for one epoch.

    Args:
        trainer: CQLTrainer instance
        dataset: OfflineRLDataset
        batch_size: Batch size for training
        device: Device to use

    Returns:
        Dictionary with epoch metrics
    """
    epoch_losses = []
    epoch_bellman_errors = []
    epoch_cql_penalties = []

    # Calculate number of batches
    num_train = len(dataset._train_indices)
    if num_train == 0:
        return {
            "loss": 0.0,
            "bellman_error": 0.0,
            "cql_penalty": 0.0,
        }

    num_batches = max(1, num_train // batch_size)

    for _ in range(num_batches):
        batch_transitions = dataset.get_train_batch(batch_size)
        if not batch_transitions:
            break

        batch = collate_transitions(batch_transitions, device)
        metrics = trainer.train_step(batch)

        epoch_losses.append(metrics["loss"])
        epoch_bellman_errors.append(metrics["bellman_error"])
        epoch_cql_penalties.append(metrics["cql_penalty"])

    return {
        "loss": float(np.mean(epoch_losses)) if epoch_losses else 0.0,
        "bellman_error": float(np.mean(epoch_bellman_errors))
        if epoch_bellman_errors
        else 0.0,
        "cql_penalty": float(np.mean(epoch_cql_penalties))
        if epoch_cql_penalties
        else 0.0,
    }


def main(
    db_path: Optional[str] = None,
    dry_run: bool = False,
    epochs: int = 100,
    batch_size: int = 32,
    alpha: float = 1.0,
    learning_rate: float = 1e-4,
    val_ratio: float = 0.1,
    save_path: str = "models/pretrained_agent.pt",
    min_quality_score: float = 0.5,
    max_conversations: int = 10000,
    state_dim: int = 128,
    action_dim: int = 4,
) -> int:
    """Main training loop.

    Args:
        db_path: Path to SQLite database
        dry_run: Use synthetic data for testing
        epochs: Number of training epochs
        batch_size: Batch size for training
        alpha: CQL regularization coefficient
        learning_rate: Learning rate
        val_ratio: Validation split ratio
        save_path: Path to save trained model
        min_quality_score: Minimum quality score for data filtering
        max_conversations: Maximum conversations to load
        state_dim: State dimension for agent
        action_dim: Action dimension for agent

    Returns:
        Exit code (0 for success)
    """
    logger.info("=" * 60)
    logger.info("Offline RL Training with CQL")
    logger.info("=" * 60)

    # Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # Initialize agent
    agent = NeuralAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        learning_rate=learning_rate,
        device=str(device),
    )
    logger.info(f"Initialized agent: state_dim={state_dim}, action_dim={action_dim}")

    # Load data
    if dry_run:
        logger.info("Running in dry-run mode with synthetic data")
        dataset = create_synthetic_dataset(
            num_transitions=1000,
            state_dim=state_dim,
            action_dim=action_dim,
        )
    else:
        if not db_path:
            logger.error("Must specify --db-path or use --dry-run")
            return 1

        logger.info(f"Loading data from {db_path}")
        dataset = OfflineRLDataset(db_path=db_path)
        num_loaded = dataset.load_from_history(
            min_quality_score=min_quality_score,
            max_conversations=max_conversations,
        )

        if num_loaded == 0:
            logger.error("No transitions loaded. Check database path and schema.")
            return 1

    # Split train/val
    train_size, val_size = dataset.split_train_val(val_ratio=val_ratio)
    logger.info(f"Dataset split: {train_size} train, {val_size} val")

    # Print dataset stats
    stats = dataset.get_stats()
    logger.info(f"Dataset stats: {json.dumps(stats, indent=2)}")

    # Initialize CQL trainer
    trainer = CQLTrainer(
        agent=agent,
        alpha=alpha,
        learning_rate=learning_rate,
        device=device,
    )
    logger.info(f"Initialized CQL trainer: alpha={alpha}, lr={learning_rate}")

    # Training loop
    logger.info("-" * 60)
    logger.info("Starting training...")
    logger.info("-" * 60)

    best_val_q = float("-inf")
    history = {
        "train_loss": [],
        "train_bellman_error": [],
        "train_cql_penalty": [],
        "val_avg_q": [],
        "val_avg_reward": [],
    }

    for epoch in range(epochs):
        # Train
        train_metrics = train_epoch(trainer, dataset, batch_size, device)

        # Validate every 10 epochs
        if epoch % 10 == 0 or epoch == epochs - 1:
            val_transitions = dataset.get_val_data()
            val_metrics = validate_agent(agent, val_transitions, device)

            logger.info(
                f"Epoch {epoch:3d}/{epochs}: "
                f"loss={train_metrics['loss']:.4f}, "
                f"bellman={train_metrics['bellman_error']:.4f}, "
                f"cql={train_metrics['cql_penalty']:.4f}, "
                f"val_q={val_metrics['avg_q']:.4f}, "
                f"val_reward={val_metrics['avg_reward']:.4f}"
            )

            # Track best model
            if val_metrics["avg_q"] > best_val_q:
                best_val_q = val_metrics["avg_q"]
                logger.info(f"  New best model! val_q={best_val_q:.4f}")

            history["val_avg_q"].append(val_metrics["avg_q"])
            history["val_avg_reward"].append(val_metrics["avg_reward"])
        else:
            logger.info(
                f"Epoch {epoch:3d}/{epochs}: "
                f"loss={train_metrics['loss']:.4f}, "
                f"bellman={train_metrics['bellman_error']:.4f}, "
                f"cql={train_metrics['cql_penalty']:.4f}"
            )

        history["train_loss"].append(train_metrics["loss"])
        history["train_bellman_error"].append(train_metrics["bellman_error"])
        history["train_cql_penalty"].append(train_metrics["cql_penalty"])

    # Final validation
    logger.info("-" * 60)
    logger.info("Final validation...")
    val_transitions = dataset.get_val_data()
    final_val_metrics = validate_agent(agent, val_transitions, device)
    logger.info(f"Final val_q={final_val_metrics['avg_q']:.4f}")

    # Save model
    save_path_obj = Path(save_path)
    save_path_obj.parent.mkdir(parents=True, exist_ok=True)

    # Save agent state
    agent_dict = agent.to_dict()
    torch.save(agent_dict, save_path)
    logger.info(f"Saved model to {save_path}")

    # Save training history
    history_path = save_path_obj.parent / "training_history.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
    logger.info(f"Saved training history to {history_path}")

    # Print summary
    logger.info("=" * 60)
    logger.info("Training Complete!")
    logger.info("=" * 60)
    logger.info(f"Final metrics:")
    logger.info(f"  Train loss: {history['train_loss'][-1]:.4f}")
    logger.info(f"  Val Q-value: {final_val_metrics['avg_q']:.4f}")
    logger.info(f"  Val reward: {final_val_metrics['avg_reward']:.4f}")
    logger.info(f"  Best val Q: {best_val_q:.4f}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train NeuralAgent with CQL on historical data"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/conversations.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic data for testing",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for training",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="CQL regularization coefficient",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-4,
        help="Learning rate",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Validation split ratio",
    )
    parser.add_argument(
        "--save-path",
        type=str,
        default="models/pretrained_agent.pt",
        help="Path to save trained model",
    )
    parser.add_argument(
        "--min-quality-score",
        type=float,
        default=0.5,
        help="Minimum quality score for data filtering",
    )
    parser.add_argument(
        "--max-conversations",
        type=int,
        default=10000,
        help="Maximum conversations to load",
    )
    parser.add_argument(
        "--state-dim",
        type=int,
        default=128,
        help="State dimension",
    )
    parser.add_argument(
        "--action-dim",
        type=int,
        default=4,
        help="Action dimension",
    )

    args = parser.parse_args()

    exit_code = main(
        db_path=args.db_path,
        dry_run=args.dry_run,
        epochs=args.epochs,
        batch_size=args.batch_size,
        alpha=args.alpha,
        learning_rate=args.learning_rate,
        val_ratio=args.val_ratio,
        save_path=args.save_path,
        min_quality_score=args.min_quality_score,
        max_conversations=args.max_conversations,
        state_dim=args.state_dim,
        action_dim=args.action_dim,
    )

    sys.exit(exit_code)
