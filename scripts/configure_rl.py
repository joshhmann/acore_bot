#!/usr/bin/env python3
"""RL Configuration Helper

Helps users configure the RL system for their needs.

Usage:
    python scripts/configure_rl.py --mode dqn          # Switch to DQN
    python scripts/configure_rl.py --mode tabular      # Switch to tabular
    python scripts/configure_rl.py --interactive       # Interactive setup
    python scripts/configure_rl.py --status            # Show current config
    python scripts/configure_rl.py --enable            # Enable RL
    python scripts/configure_rl.py --disable           # Disable RL
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_env_file_path():
    """Find the .env file path."""
    # Check for .env first, then .env.example as template
    env_path = Path(".env")
    if env_path.exists():
        return env_path
    # If no .env, use .env.example as reference
    example_path = Path(".env.example")
    if example_path.exists():
        print("Note: No .env file found. Using .env.example as reference.")
        print("Run: cp .env.example .env  # to create your config")
        return example_path
    raise FileNotFoundError("No .env or .env.example file found")


def read_env_file():
    """Read current .env file."""
    env_path = get_env_file_path()
    with open(env_path, "r") as f:
        return f.readlines()


def write_env_file(lines):
    """Write updated .env file."""
    env_path = get_env_file_path()
    with open(env_path, "w") as f:
        f.writelines(lines)


def update_env_var(key, value):
    """Update or add an environment variable."""
    lines = read_env_file()
    updated = False
    new_lines = []

    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        # Add to end of file
        new_lines.append(f"\n# Added by configure_rl.py\n")
        new_lines.append(f"{key}={value}\n")

    write_env_file(new_lines)


def switch_mode(mode):
    """Switch between tabular and DQN modes."""
    update_env_var("RL_ALGORITHM", mode)
    print(f"✅ Switched to {mode} mode")
    print("\nNext steps:")
    if mode == "dqn":
        print("  1. Ensure RL_ENABLED=true")
        print("  2. Restart the bot")
        print("  3. Check dashboard at http://localhost:8080")
        print("\nDQN Features enabled:")
        print("  - Experience replay buffer")
        print("  - Multi-objective rewards")
        print("  - Hierarchical RL (meta-controller)")
        print("  - Knowledge transfer between personas")
    else:
        print("  1. Restart the bot")
        print("\nTabular mode: Simple Q-learning, fast and lightweight")


def interactive_setup():
    """Interactive configuration wizard."""
    print("🤖 RL Configuration Wizard")
    print("=" * 50)

    # Enable RL?
    enable = input("\n1. Enable RL system? (y/n): ").lower().strip()
    if enable in ("y", "yes"):
        update_env_var("RL_ENABLED", "true")
        print("   ✅ RL enabled")
    else:
        update_env_var("RL_ENABLED", "false")
        print("   ✅ RL disabled")
        return

    # Algorithm selection
    print("\n2. Select algorithm:")
    print("   a) tabular - Simple Q-learning (fast, lightweight)")
    print("   b) dqn - Deep Q-Network (advanced, neural RL)")
    algo = input("   Choice (a/b): ").lower().strip()

    if algo == "b":
        update_env_var("RL_ALGORITHM", "dqn")
        print("   ✅ DQN selected")

        # Advanced features
        print("\n3. Enable advanced features?")

        hierarchical = (
            input("   Hierarchical RL (meta-controller)? (y/n): ").lower().strip()
        )
        update_env_var(
            "RL_USE_HIERARCHICAL", "true" if hierarchical in ("y", "yes") else "false"
        )

        transfer = (
            input("   Knowledge transfer between personas? (y/n): ").lower().strip()
        )
        update_env_var(
            "RL_USE_TRANSFER", "true" if transfer in ("y", "yes") else "false"
        )

        multi_obj = input("   Multi-objective rewards? (y/n): ").lower().strip()
        update_env_var(
            "RL_USE_MULTI_OBJECTIVE", "true" if multi_obj in ("y", "yes") else "false"
        )

        # Buffer size
        print("\n4. Replay buffer size (default: 10000):")
        buffer_size = input("   Enter size or press Enter for default: ").strip()
        if buffer_size:
            update_env_var("RL_REPLAY_BUFFER_SIZE", buffer_size)

        print("\n✅ DQN configuration complete!")
        print("\nNext steps:")
        print("  1. Enable dashboard: ANALYTICS_DASHBOARD_ENABLED=true")
        print("  2. Restart the bot")
        print("  3. Access dashboard at http://localhost:8080")
    else:
        update_env_var("RL_ALGORITHM", "tabular")
        print("   ✅ Tabular selected")
        print("\n✅ Configuration complete! Restart the bot to apply changes.")


def show_status():
    """Display current RL configuration."""
    # Try to import config, but handle if it fails
    try:
        from config import Config

        print("📊 Current RL Configuration")
        print("=" * 50)
        print(f"RL Enabled: {getattr(Config, 'RL_ENABLED', 'N/A')}")
        print(f"Algorithm: {getattr(Config, 'RL_ALGORITHM', 'tabular')}")
        print(f"Data Directory: {getattr(Config, 'RL_DATA_DIR', 'N/A')}")

        if getattr(Config, "RL_ALGORITHM", "tabular") == "dqn":
            print("\nDQN Settings:")
            print(f"  Replay Buffer: {getattr(Config, 'RL_REPLAY_BUFFER_SIZE', 'N/A')}")
            print(f"  Batch Size: {getattr(Config, 'RL_BATCH_SIZE', 'N/A')}")
            print(f"  Warmup Steps: {getattr(Config, 'RL_WARMUP_STEPS', 'N/A')}")
            print(f"  Hierarchical RL: {getattr(Config, 'RL_USE_HIERARCHICAL', 'N/A')}")
            print(f"  Transfer Learning: {getattr(Config, 'RL_USE_TRANSFER', 'N/A')}")
            print(
                f"  Multi-Objective: {getattr(Config, 'RL_USE_MULTI_OBJECTIVE', 'N/A')}"
            )
    except Exception as e:
        print(f"⚠️  Could not load config: {e}")
        print("\nReading from .env file directly...")

        try:
            lines = read_env_file()
            print("\n📊 Current .env Settings")
            print("=" * 50)
            for line in lines:
                if line.strip().startswith("RL_") and not line.strip().startswith("#"):
                    print(f"  {line.strip()}")
        except Exception as e2:
            print(f"❌ Error reading .env: {e2}")


def main():
    parser = argparse.ArgumentParser(description="Configure RL system settings")
    parser.add_argument(
        "--mode", choices=["tabular", "dqn"], help="Switch RL algorithm mode"
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run interactive setup wizard"
    )
    parser.add_argument(
        "--status", "-s", action="store_true", help="Show current configuration"
    )
    parser.add_argument("--enable", action="store_true", help="Enable RL system")
    parser.add_argument("--disable", action="store_true", help="Disable RL system")

    args = parser.parse_args()

    if args.mode:
        switch_mode(args.mode)
    elif args.interactive:
        interactive_setup()
    elif args.status:
        show_status()
    elif args.enable:
        update_env_var("RL_ENABLED", "true")
        print("✅ RL system enabled")
        print("\nNext steps:")
        print("  1. Choose algorithm: python scripts/configure_rl.py --mode dqn")
        print("  2. Restart the bot")
    elif args.disable:
        update_env_var("RL_ENABLED", "false")
        print("✅ RL system disabled")
        print("Restart the bot to apply changes")
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/configure_rl.py --status")
        print("  python scripts/configure_rl.py --mode dqn")
        print("  python scripts/configure_rl.py --interactive")


if __name__ == "__main__":
    main()
