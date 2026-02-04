#!/usr/bin/env python3
"""
Migration script for converting tabular Q-table RL policies to neural network (DQN) format.

This enables warm-starting the neural agent with learned Q-values from the tabular agent,
preserving learning progress during the migration.

Usage:
    python scripts/migrate_rl_policies.py --dry-run          # Preview what would happen
    python scripts/migrate_rl_policies.py --execute          # Perform migration with warm-start
    python scripts/migrate_rl_policies.py --execute --fresh  # Fresh neural init (no warm-start)
    python scripts/migrate_rl_policies.py --rollback --backup-path /path/to/backup

Options:
    --dry-run       Show conversion plan without executing
    --execute       Perform actual migration
    --fresh         Use random initialization instead of warm-start from Q-values
    --backup-dir    Custom backup directory (default: ./data/rl/backups/)
    --data-dir      Source data directory (default: ./data/rl/)
    --rollback      Restore from backup
    --backup-path   Path to backup file for rollback
"""

import argparse
import ast
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from services.persona.rl.neural_agent import (
    NEURAL_DEFAULT_ACTION_DIM,
    NEURAL_DEFAULT_HIDDEN_DIMS,
    NEURAL_DEFAULT_LEARNING_RATE,
    NEURAL_DEFAULT_STATE_DIM,
    NeuralAgent,
)
from services.persona.rl.types import RLAction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

POLICY_VERSION_V1 = 1
POLICY_VERSION_V2 = 2
MIGRATION_WARM_START_EPOCHS = 100
MIGRATION_BATCH_SIZE = 32


def load_tabular_policies(path: Path) -> Dict[str, Any]:
    """
    Load existing tabular Q-table policies.

    Args:
        path: Path to rl_policies.json

    Returns:
        Dictionary with policy data or empty dict if file doesn't exist
    """
    if not path.exists():
        logger.warning(f"Policy file not found: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        version = data.get("version", 1)
        if version >= POLICY_VERSION_V2:
            logger.warning(f"Policies already at version {version} (neural format)")
            return data

        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse policy file: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load policy file: {e}")
        return {}


def parse_state_str(state_str: str) -> Optional[Tuple[int, int, int]]:
    """
    Parse state string representation back to tuple.

    Args:
        state_str: String like "(1, 2, 3)"

    Returns:
        Tuple of 3 integers or None if parsing fails
    """
    try:
        state = ast.literal_eval(state_str)
        if isinstance(state, tuple) and len(state) == 3:
            return (int(state[0]), int(state[1]), int(state[2]))
    except (SyntaxError, ValueError, TypeError):
        pass
    return None


def state_to_vector(state: Tuple[int, int, int], state_dim: int) -> np.ndarray:
    """
    Convert RLState tuple to feature vector.

    Uses the same encoding as NeuralAgent._state_to_tensor.

    Args:
        state: (sentiment_bin, time_since_last_bin, message_count_bin)
        state_dim: Dimension of output vector

    Returns:
        numpy array of shape (state_dim,)
    """
    arr = np.zeros(state_dim, dtype=np.float32)
    arr[0] = state[0] / 10.0
    arr[1] = state[1] / 100.0
    arr[2] = state[2] / 50.0
    return arr


def warm_start_neural_agent(
    q_table: Dict[str, Dict[str, float]],
    epsilon: float,
    state_dim: int = NEURAL_DEFAULT_STATE_DIM,
    action_dim: int = NEURAL_DEFAULT_ACTION_DIM,
    epochs: int = MIGRATION_WARM_START_EPOCHS,
) -> NeuralAgent:
    """
    Initialize neural network from Q-table values using supervised learning.

    The Q-table provides target Q-values for each (state, action) pair.
    We train the neural network to approximate these values.

    Args:
        q_table: Dictionary of state_str -> {action_str -> q_value}
        epsilon: Current epsilon value from tabular agent
        state_dim: State dimension for neural network
        action_dim: Action dimension for neural network
        epochs: Number of training epochs for warm-start

    Returns:
        NeuralAgent initialized with Q-table knowledge
    """
    agent = NeuralAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        epsilon=epsilon,
    )

    states: List[np.ndarray] = []
    q_values: List[List[float]] = []

    for state_str, q_row in q_table.items():
        state = parse_state_str(state_str)
        if state is None:
            continue

        state_vec = state_to_vector(state, state_dim)
        states.append(state_vec)

        q_vec = []
        for action in RLAction:
            action_str = str(int(action))
            q_val = q_row.get(action_str, 10.0)
            q_vec.append(q_val)
        q_values.append(q_vec)

    if not states:
        logger.warning("No valid states in Q-table, returning fresh agent")
        return agent

    states_tensor = torch.tensor(np.array(states), dtype=torch.float32)
    q_values_tensor = torch.tensor(np.array(q_values), dtype=torch.float32)

    optimizer = optim.Adam(
        agent.online_network.parameters(), lr=NEURAL_DEFAULT_LEARNING_RATE * 10
    )
    loss_fn = nn.MSELoss()

    agent.online_network.train()
    logger.info(
        f"Warm-starting neural agent with {len(states)} states for {epochs} epochs"
    )

    avg_loss = 0.0
    for epoch in range(epochs):
        total_loss = 0.0
        n_batches = 0

        indices = np.random.permutation(len(states))
        for i in range(0, len(states), MIGRATION_BATCH_SIZE):
            batch_idx = indices[i : i + MIGRATION_BATCH_SIZE]
            batch_states = states_tensor[batch_idx]
            batch_targets = q_values_tensor[batch_idx]

            optimizer.zero_grad()
            predicted = agent.online_network(batch_states)
            loss = loss_fn(predicted, batch_targets)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / n_batches if n_batches > 0 else 0.0
        if (epoch + 1) % 20 == 0 or epoch == 0:
            logger.info(f"  Epoch {epoch + 1}/{epochs}: loss = {avg_loss:.4f}")

    agent.hard_update()
    agent.eval_mode()

    logger.info(f"Warm-start complete. Final loss: {avg_loss:.4f}")
    return agent


def migrate_single_agent(
    agent_key: str,
    agent_data: Dict[str, Any],
    warm_start: bool = True,
) -> Dict[str, Any]:
    """
    Migrate a single tabular agent to neural format.

    Args:
        agent_key: Agent identifier (channel_id:user_id)
        agent_data: Tabular agent data with q_table and epsilon
        warm_start: Whether to initialize from Q-values

    Returns:
        Neural agent data dictionary
    """
    epsilon = agent_data.get("epsilon", 1.0)
    q_table = agent_data.get("q_table", {})

    if warm_start and q_table:
        neural_agent = warm_start_neural_agent(
            q_table=q_table,
            epsilon=epsilon,
        )
    else:
        neural_agent = NeuralAgent(epsilon=epsilon)

    return neural_agent.to_dict()


def migrate_policies(
    tabular_data: Dict[str, Any],
    warm_start: bool = True,
) -> Dict[str, Any]:
    """
    Convert all tabular policies to neural format.

    Args:
        tabular_data: Full tabular policy data structure
        warm_start: Whether to initialize networks from Q-values

    Returns:
        New policy data structure in neural format
    """
    agents_data = tabular_data.get("agents", {})
    migrated_agents = {}

    for agent_key, agent_data in agents_data.items():
        logger.info(f"Migrating agent: {agent_key}")
        migrated_agents[agent_key] = migrate_single_agent(
            agent_key=agent_key,
            agent_data=agent_data,
            warm_start=warm_start,
        )

    return {
        "version": POLICY_VERSION_V2,
        "algorithm": "dqn",
        "migrated_from_version": tabular_data.get("version", POLICY_VERSION_V1),
        "migration_timestamp": datetime.now().isoformat(),
        "warm_started": warm_start,
        "agents": migrated_agents,
    }


def create_backup(source: Path, backup_dir: Path) -> Optional[Path]:
    """
    Create timestamped backup of original file.

    Args:
        source: Path to file to backup
        backup_dir: Directory to store backup

    Returns:
        Path to backup file or None if source doesn't exist
    """
    if not source.exists():
        logger.warning(f"Source file does not exist: {source}")
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"rl_policies_v1_backup_{timestamp}.json"
    backup_path = backup_dir / backup_name

    shutil.copy2(source, backup_path)
    logger.info(f"Created backup: {backup_path}")

    return backup_path


def save_neural_policies(policies: Dict[str, Any], path: Path) -> None:
    """
    Save neural policies with atomic write.

    Args:
        policies: Policy data to save
        path: Output file path
    """
    tmp_path = path.with_suffix(".tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(policies, f, indent=2)

        os.replace(tmp_path, path)
        logger.info(f"Saved neural policies to: {path}")
    except Exception as e:
        logger.error(f"Failed to save policies: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def rollback(backup_path: Path, original_path: Path) -> None:
    """
    Restore original file from backup.

    Args:
        backup_path: Path to backup file
        original_path: Path to restore to
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    shutil.copy2(backup_path, original_path)
    logger.info(f"Restored {original_path} from {backup_path}")


def analyze_tabular_policies(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze tabular policies for dry-run summary.

    Args:
        data: Tabular policy data

    Returns:
        Analysis summary dictionary
    """
    agents_data = data.get("agents", {})
    summary = {
        "version": data.get("version", 1),
        "total_agents": len(agents_data),
        "agents": [],
    }

    for agent_key, agent_data in agents_data.items():
        q_table = agent_data.get("q_table", {})
        epsilon = agent_data.get("epsilon", 1.0)

        all_q_values = []
        for q_row in q_table.values():
            all_q_values.extend(q_row.values())

        agent_summary = {
            "key": agent_key,
            "epsilon": epsilon,
            "states_learned": len(q_table),
            "q_value_range": (min(all_q_values), max(all_q_values))
            if all_q_values
            else (0, 0),
            "mean_q_value": np.mean(all_q_values) if all_q_values else 0,
        }
        summary["agents"].append(agent_summary)

    return summary


def print_dry_run_summary(summary: Dict[str, Any], warm_start: bool) -> None:
    """Print formatted dry-run summary."""
    print("\n" + "=" * 60)
    print("DRY RUN - Migration Summary")
    print("=" * 60)
    print(f"\nCurrent Version: {summary['version']}")
    print(f"Target Version: {POLICY_VERSION_V2} (DQN)")
    print(f"Warm-Start: {'Yes' if warm_start else 'No (fresh initialization)'}")
    print(f"\nTotal Agents to Migrate: {summary['total_agents']}")

    if summary["agents"]:
        print("\nAgent Details:")
        print("-" * 60)
        for agent in summary["agents"]:
            print(f"\n  Agent: {agent['key']}")
            print(f"    Epsilon: {agent['epsilon']:.4f}")
            print(f"    States Learned: {agent['states_learned']}")
            if agent["states_learned"] > 0:
                print(
                    f"    Q-Value Range: [{agent['q_value_range'][0]:.2f}, {agent['q_value_range'][1]:.2f}]"
                )
                print(f"    Mean Q-Value: {agent['mean_q_value']:.2f}")

    print("\n" + "=" * 60)
    print("No changes made. Use --execute to perform migration.")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate RL policies from tabular Q-table to neural network format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show conversion plan without executing",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Perform actual migration",
    )
    mode_group.add_argument(
        "--rollback",
        action="store_true",
        help="Restore from backup",
    )

    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Use random initialization instead of warm-start from Q-values",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default="./data/rl/backups/",
        help="Custom backup directory (default: ./data/rl/backups/)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data/rl/",
        help="Source data directory (default: ./data/rl/)",
    )

    parser.add_argument(
        "--backup-path",
        type=str,
        help="Path to backup file for rollback",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    backup_dir = Path(args.backup_dir)
    policy_file = data_dir / "rl_policies.json"

    if args.rollback:
        if not args.backup_path:
            if backup_dir.exists():
                backups = sorted(backup_dir.glob("rl_policies_v1_backup_*.json"))
                if backups:
                    print("\nAvailable backups:")
                    for b in backups:
                        print(f"  {b}")
                    print("\nUse --backup-path to specify which backup to restore")
                else:
                    print("No backups found in", backup_dir)
            else:
                print("Backup directory does not exist:", backup_dir)
            sys.exit(1)

        backup_path = Path(args.backup_path)
        try:
            rollback(backup_path, policy_file)
            print(f"Successfully restored from {backup_path}")
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            sys.exit(1)
        return

    tabular_data = load_tabular_policies(policy_file)
    if not tabular_data:
        print(f"\nNo tabular policies found at {policy_file}")
        print("Nothing to migrate.")
        sys.exit(0)

    if tabular_data.get("version", 1) >= POLICY_VERSION_V2:
        print(
            f"\nPolicies are already at version {tabular_data.get('version')} (neural format)"
        )
        print("No migration needed.")
        sys.exit(0)

    warm_start = not args.fresh

    if args.dry_run:
        summary = analyze_tabular_policies(tabular_data)
        print_dry_run_summary(summary, warm_start)
        return

    if args.execute:
        print("\n" + "=" * 60)
        print("Executing Migration")
        print("=" * 60)

        backup_path = create_backup(policy_file, backup_dir)
        if backup_path:
            print(f"\nBackup created: {backup_path}")

        print(f"\nMigrating with warm_start={warm_start}...")
        neural_data = migrate_policies(tabular_data, warm_start=warm_start)

        save_neural_policies(neural_data, policy_file)

        print("\n" + "=" * 60)
        print("Migration Complete!")
        print("=" * 60)
        print(f"\nMigrated {len(neural_data['agents'])} agents to DQN format")
        print(f"Policy file: {policy_file}")
        print(f"Backup: {backup_path}")
        print("\nTo rollback, run:")
        print(
            f"  python scripts/migrate_rl_policies.py --rollback --backup-path {backup_path}"
        )
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
