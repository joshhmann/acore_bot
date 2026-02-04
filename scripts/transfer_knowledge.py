#!/usr/bin/env python3
"""CLI script for executing knowledge transfers between RL personas.

This script provides a command-line interface for transferring knowledge
between different persona neural networks, enabling transfer learning.

Examples:
    # Transfer weights from dagoth_ur to hal9000
    python scripts/transfer_knowledge.py --source dagoth_ur --target hal9000

    # Transfer both weights and strategies with fine-tuning
    python scripts/transfer_knowledge.py --source dagoth_ur --target hal9000 \
        --components both --fine-tune-epochs 10

    # Dry run to preview transfer
    python scripts/transfer_knowledge.py --source dagoth_ur --target hal9000 --dry-run

    # View transfer lineage for a persona
    python scripts/transfer_knowledge.py --lineage dagoth_ur

    # List all transfers
    python scripts/transfer_knowledge.py --list-transfers
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.persona.rl.hierarchical import MetaController
from services.persona.rl.neural_agent import NeuralAgent
from services.persona.rl.offline_rl import OfflineRLDataset
from services.persona.rl.transfer import KnowledgeTransfer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Knowledge Transfer Framework for RL Personas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --source dagoth_ur --target hal9000
  %(prog)s --source dagoth_ur --target hal9000 --components both --fine-tune-epochs 10
  %(prog)s --source dagoth_ur --target hal9000 --dry-run
  %(prog)s --lineage dagoth_ur
  %(prog)s --list-transfers
  %(prog)s --clear-history
        """,
    )

    # Main transfer arguments
    parser.add_argument(
        "--source",
        type=str,
        help="Source persona ID (e.g., dagoth_ur)",
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Target persona ID (e.g., hal9000)",
    )

    # Transfer options
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.3,
        help="Minimum similarity threshold for transfer (default: 0.3)",
    )
    parser.add_argument(
        "--components",
        type=str,
        choices=["weights", "strategies", "both"],
        default="both",
        help="Which components to transfer (default: both)",
    )
    parser.add_argument(
        "--fine-tune-epochs",
        type=int,
        default=0,
        help="Number of fine-tuning epochs (default: 0)",
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        help="Path to dataset for fine-tuning",
    )

    # Control options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview transfer without executing",
    )
    parser.add_argument(
        "--persona-dir",
        type=str,
        default="prompts/characters",
        help="Directory containing persona JSON files",
    )
    parser.add_argument(
        "--transfer-log",
        type=str,
        default="data/rl_transfers.json",
        help="Path to transfer log file",
    )

    # Information commands
    parser.add_argument(
        "--lineage",
        type=str,
        metavar="PERSONA_ID",
        help="Show transfer lineage for a persona",
    )
    parser.add_argument(
        "--list-transfers",
        action="store_true",
        help="List all recorded transfers",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear all transfer history",
    )

    # Similarity-only command
    parser.add_argument(
        "--compute-similarity",
        nargs=2,
        metavar=("SOURCE", "TARGET"),
        help="Compute similarity between two personas without transferring",
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file for results (JSON format)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    return parser


def load_or_create_agent(persona_id: str, device: str = "cpu") -> NeuralAgent:
    """Load existing agent or create new one for a persona."""
    agent_path = Path(f"data/rl_agents/{persona_id}_agent.json")

    if agent_path.exists():
        logger.info(f"Loading existing agent for '{persona_id}' from {agent_path}")
        with open(agent_path, "r") as f:
            data = json.load(f)
        return NeuralAgent.from_dict(data)
    else:
        logger.info(f"Creating new agent for '{persona_id}'")
        return NeuralAgent(device=device)


def load_or_create_meta_controller(
    persona_id: str, device: str = "cpu"
) -> MetaController:
    """Load existing meta-controller or create new one for a persona."""
    meta_path = Path(f"data/rl_agents/{persona_id}_meta.json")

    if meta_path.exists():
        logger.info(
            f"Loading existing meta-controller for '{persona_id}' from {meta_path}"
        )
        with open(meta_path, "r") as f:
            data = json.load(f)
        return MetaController.from_dict(data)
    else:
        logger.info(f"Creating new meta-controller for '{persona_id}'")
        return MetaController(device=device)


def save_agent(persona_id: str, agent: NeuralAgent) -> None:
    """Save agent to disk."""
    agent_dir = Path("data/rl_agents")
    agent_dir.mkdir(parents=True, exist_ok=True)

    agent_path = agent_dir / f"{persona_id}_agent.json"
    with open(agent_path, "w") as f:
        json.dump(agent.to_dict(), f, indent=2)
    logger.info(f"Saved agent for '{persona_id}' to {agent_path}")


def save_meta_controller(persona_id: str, meta: MetaController) -> None:
    """Save meta-controller to disk."""
    agent_dir = Path("data/rl_agents")
    agent_dir.mkdir(parents=True, exist_ok=True)

    meta_path = agent_dir / f"{persona_id}_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta.to_dict(), f, indent=2)
    logger.info(f"Saved meta-controller for '{persona_id}' to {meta_path}")


def execute_transfer(args: argparse.Namespace) -> dict:
    """Execute knowledge transfer based on arguments."""
    transfer = KnowledgeTransfer(
        persona_dir=Path(args.persona_dir),
        transfer_log_path=Path(args.transfer_log),
        similarity_threshold=args.similarity_threshold,
    )

    # Compute similarity first
    similarity = transfer.compute_persona_similarity(args.source, args.target)
    logger.info(
        f"Similarity between '{args.source}' and '{args.target}': {similarity:.3f}"
    )

    if similarity < args.similarity_threshold:
        logger.warning(
            f"Similarity {similarity:.3f} is below threshold {args.similarity_threshold}. "
            "Transfer may be skipped."
        )

    if args.dry_run:
        logger.info("DRY RUN: Would execute the following transfer:")
        logger.info(f"  Source: {args.source}")
        logger.info(f"  Target: {args.target}")
        logger.info(f"  Similarity: {similarity:.3f}")
        logger.info(f"  Components: {args.components}")
        logger.info(f"  Fine-tune epochs: {args.fine_tune_epochs}")
        return {
            "dry_run": True,
            "source": args.source,
            "target": args.target,
            "similarity": similarity,
            "components": args.components,
            "fine_tune_epochs": args.fine_tune_epochs,
        }

    # Load or create agents
    source_agent = load_or_create_agent(args.source)
    target_agent = load_or_create_agent(args.target)

    # Load or create meta-controllers if needed
    source_meta = None
    target_meta = None
    if args.components in ("strategies", "both"):
        source_meta = load_or_create_meta_controller(args.source)
        target_meta = load_or_create_meta_controller(args.target)

    # Load dataset for fine-tuning if specified
    dataset = None
    if args.fine_tune_epochs > 0:
        dataset = OfflineRLDataset(db_path=args.dataset_path or "data/conversations.db")
        if args.dataset_path:
            dataset.load_from_history()

    # Execute transfer
    results = transfer.execute_full_transfer(
        source_id=args.source,
        target_id=args.target,
        source_agent=source_agent,
        target_agent=target_agent,
        source_meta=source_meta,
        target_meta=target_meta,
        dataset=dataset,
        fine_tune_epochs=args.fine_tune_epochs,
        components=args.components,
    )

    # Save updated agents
    save_agent(args.target, target_agent)
    if args.components in ("strategies", "both") and target_meta:
        save_meta_controller(args.target, target_meta)

    return results


def show_lineage(persona_id: str, args: argparse.Namespace) -> dict:
    """Show transfer lineage for a persona."""
    transfer = KnowledgeTransfer(
        persona_dir=Path(args.persona_dir),
        transfer_log_path=Path(args.transfer_log),
    )

    lineage = transfer.get_transfer_lineage(persona_id)

    print(f"\nTransfer Lineage for '{persona_id}':")
    print("=" * 50)

    print(f"\nAncestors (knowledge sources) [{lineage['total_transfers_in']}]:")
    if lineage["ancestors"]:
        for ancestor in lineage["ancestors"]:
            print(f"  - {ancestor['persona_id']}")
            print(f"    Similarity: {ancestor['similarity']:.3f}")
            print(f"    Components: {', '.join(ancestor['components'])}")
            print(f"    Date: {ancestor['timestamp']}")
    else:
        print("  None")

    print(f"\nDescendants (knowledge recipients) [{lineage['total_transfers_out']}]:")
    if lineage["descendants"]:
        for descendant in lineage["descendants"]:
            print(f"  - {descendant['persona_id']}")
            print(f"    Similarity: {descendant['similarity']:.3f}")
            print(f"    Components: {', '.join(descendant['components'])}")
            print(f"    Date: {descendant['timestamp']}")
    else:
        print("  None")

    return lineage


def list_transfers(args: argparse.Namespace) -> list:
    """List all recorded transfers."""
    transfer = KnowledgeTransfer(
        persona_dir=Path(args.persona_dir),
        transfer_log_path=Path(args.transfer_log),
    )

    transfers = transfer.get_all_transfers()

    print(f"\nAll Recorded Transfers ({len(transfers)} total):")
    print("=" * 70)

    if not transfers:
        print("No transfers recorded yet.")
        return []

    for i, t in enumerate(transfers, 1):
        print(f"\n{i}. {t['source_id']} -> {t['target_id']}")
        print(f"   Similarity: {t['similarity']:.3f}")
        print(f"   Components: {', '.join(t['components_transferred'])}")
        print(f"   Date: {t['timestamp']}")
        if t.get("fine_tune_epochs", 0) > 0:
            print(f"   Fine-tuned: {t['fine_tune_epochs']} epochs")

    return transfers


def compute_similarity(source: str, target: str, args: argparse.Namespace) -> dict:
    """Compute similarity between two personas without transferring."""
    transfer = KnowledgeTransfer(
        persona_dir=Path(args.persona_dir),
        transfer_log_path=Path(args.transfer_log),
    )

    similarity = transfer.compute_persona_similarity(source, target)

    # Load features for detailed breakdown
    try:
        source_features = transfer.load_persona_features(source)
        target_features = transfer.load_persona_features(target)

        trait_sim = transfer.compute_trait_similarity(source_features, target_features)
        interest_overlap = transfer.compute_interest_overlap(
            source_features, target_features
        )
        style_compat = transfer.compute_style_compatibility(
            source_features, target_features
        )

        print(f"\nSimilarity Analysis: '{source}' vs '{target}'")
        print("=" * 50)
        print(f"Overall Similarity: {similarity:.3f}")
        print(f"\nBreakdown:")
        print(f"  Trait Similarity:      {trait_sim:.3f} (weight: 0.5)")
        print(f"  Interest Overlap:      {interest_overlap:.3f} (weight: 0.3)")
        print(f"  Style Compatibility:   {style_compat:.3f} (weight: 0.2)")

        print(f"\nSource Persona: {source}")
        print(f"  Big Five: {source_features.big_five}")
        print(f"  Interests: {source_features.interests}")
        print(f"  Communication Style: {source_features.communication_style}")

        print(f"\nTarget Persona: {target}")
        print(f"  Big Five: {target_features.big_five}")
        print(f"  Interests: {target_features.interests}")
        print(f"  Communication Style: {target_features.communication_style}")

        return {
            "source": source,
            "target": target,
            "similarity": similarity,
            "trait_similarity": trait_sim,
            "interest_overlap": interest_overlap,
            "style_compatibility": style_compat,
        }
    except Exception as e:
        logger.error(f"Failed to compute detailed similarity: {e}")
        return {"source": source, "target": target, "similarity": similarity}


def clear_history(args: argparse.Namespace) -> None:
    """Clear all transfer history."""
    transfer = KnowledgeTransfer(
        persona_dir=Path(args.persona_dir),
        transfer_log_path=Path(args.transfer_log),
    )

    transfer.clear_transfer_history()
    print("Transfer history cleared.")


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        results = None

        if args.clear_history:
            clear_history(args)
            return 0

        if args.list_transfers:
            results = list_transfers(args)
        elif args.lineage:
            results = show_lineage(args.lineage, args)
        elif args.compute_similarity:
            source, target = args.compute_similarity
            results = compute_similarity(source, target, args)
        elif args.source and args.target:
            results = execute_transfer(args)
        else:
            parser.print_help()
            return 1

        # Save results to file if specified
        if args.output and results:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {args.output}")

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid value: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
