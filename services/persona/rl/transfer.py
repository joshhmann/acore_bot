"""Knowledge Transfer Framework for RL personas.

This module implements transfer learning between different persona neural networks,
enabling knowledge from one trained persona to be transferred to another to
accelerate learning for new personas.

Key Features:
- Persona similarity computation using Big Five traits, interests, and communication style
- Progressive weight transfer with similarity-based interpolation
- Strategy transfer between meta-controllers
- Fine-tuning after transfer using CQL
- Transfer lineage tracking for knowledge ancestry visualization
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import torch
import torch.nn as nn

from .hierarchical import MetaController, Strategy
from .neural_agent import NeuralAgent
from .offline_rl import (
    CQLTrainer,
    OfflineRLDataset,
    TransitionBatch,
    collate_transitions,
)

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_PERSONA_DIR = Path("prompts/characters")
DEFAULT_TRANSFER_LOG_PATH = Path("data/rl_transfers.json")
DEFAULT_SIMILARITY_THRESHOLD = 0.3

# Similarity weights
TRAIT_SIMILARITY_WEIGHT = 0.5
INTEREST_OVERLAP_WEIGHT = 0.3
STYLE_COMPATIBILITY_WEIGHT = 0.2


@dataclass
class PersonaFeatures:
    """Extracted features from a persona definition."""

    persona_id: str
    display_name: str
    big_five: Dict[str, float] = field(default_factory=dict)
    interests: Set[str] = field(default_factory=set)
    communication_style: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure all Big Five traits are present."""
        default_traits = {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
        }
        for trait, default in default_traits.items():
            if trait not in self.big_five:
                self.big_five[trait] = default

        default_style = {
            "formality": 0.5,
            "verbosity": 0.5,
            "expressiveness": 0.5,
        }
        for style, default in default_style.items():
            if style not in self.communication_style:
                self.communication_style[style] = default


@dataclass
class TransferEvent:
    """Record of a knowledge transfer event."""

    source_id: str
    target_id: str
    timestamp: str
    similarity: float
    components_transferred: List[str]
    weight_transfer_ratio: float
    strategy_transfer_ratio: float
    fine_tune_epochs: int = 0
    fine_tune_loss: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "timestamp": self.timestamp,
            "similarity": self.similarity,
            "components_transferred": self.components_transferred,
            "weight_transfer_ratio": self.weight_transfer_ratio,
            "strategy_transfer_ratio": self.strategy_transfer_ratio,
            "fine_tune_epochs": self.fine_tune_epochs,
            "fine_tune_loss": self.fine_tune_loss,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransferEvent":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            timestamp=data["timestamp"],
            similarity=data["similarity"],
            components_transferred=data["components_transferred"],
            weight_transfer_ratio=data["weight_transfer_ratio"],
            strategy_transfer_ratio=data["strategy_transfer_ratio"],
            fine_tune_epochs=data.get("fine_tune_epochs", 0),
            fine_tune_loss=data.get("fine_tune_loss", 0.0),
        )


class KnowledgeTransfer:
    """
    Knowledge Transfer Framework for RL personas.

    Enables transfer learning between different persona neural networks by:
    1. Computing persona similarity based on traits, interests, and style
    2. Transferring neural network weights using progressive interpolation
    3. Transferring meta-level Q-values for strategies
    4. Fine-tuning transferred networks on target persona's data
    5. Tracking transfer lineage for knowledge ancestry visualization

    Example:
        transfer = KnowledgeTransfer()

        # Compute similarity between two personas
        similarity = transfer.compute_persona_similarity("dagoth_ur", "hal9000")

        # Transfer weights from source to target agent
        transfer.transfer_weights(source_agent, target_agent, similarity)

        # Transfer strategies between meta-controllers
        transfer.transfer_strategies(source_meta, target_meta, similarity)

        # Fine-tune after transfer
        transfer.fine_tune_after_transfer(target_agent, dataset, epochs=10)
    """

    def __init__(
        self,
        persona_dir: Optional[Path] = None,
        transfer_log_path: Optional[Path] = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        device: Optional[str] = None,
    ):
        """
        Initialize the KnowledgeTransfer framework.

        Args:
            persona_dir: Directory containing persona JSON files
            transfer_log_path: Path to store transfer history
            similarity_threshold: Minimum similarity for transfer (default 0.3)
            device: Device for torch operations ('cpu' or 'cuda')
        """
        self.persona_dir = persona_dir or DEFAULT_PERSONA_DIR
        self.transfer_log_path = transfer_log_path or DEFAULT_TRANSFER_LOG_PATH
        self.similarity_threshold = similarity_threshold
        self.device = torch.device(device if device else "cpu")

        # Cache for loaded persona features
        self._persona_cache: Dict[str, PersonaFeatures] = {}

        # Ensure transfer log directory exists
        self.transfer_log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"KnowledgeTransfer initialized: persona_dir={self.persona_dir}, "
            f"threshold={similarity_threshold}, device={self.device}"
        )

    def load_persona_features(self, persona_id: str) -> PersonaFeatures:
        """
        Load and extract features from a persona JSON file.

        Args:
            persona_id: Persona identifier (e.g., "dagoth_ur")

        Returns:
            PersonaFeatures object with extracted traits, interests, and style

        Raises:
            FileNotFoundError: If persona file doesn't exist
            ValueError: If persona file is invalid
        """
        if persona_id in self._persona_cache:
            return self._persona_cache[persona_id]

        # Try different file naming conventions
        possible_paths = [
            self.persona_dir / f"{persona_id}.json",
            self.persona_dir / persona_id,
        ]

        persona_path = None
        for path in possible_paths:
            if path.exists():
                persona_path = path
                break

        if persona_path is None:
            raise FileNotFoundError(
                f"Persona file not found for '{persona_id}' in {self.persona_dir}"
            )

        try:
            with open(persona_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in persona file {persona_path}: {e}")

        # Handle different JSON structures
        if "data" in data:
            data = data["data"]  # chara_card_v2 format

        # Extract Big Five traits
        big_five = {}
        if "big_five" in data:
            big_five = data["big_five"]
        elif "extensions" in data and "big_five" in data["extensions"]:
            big_five = data["extensions"]["big_five"]

        # Extract interests
        interests = set()
        if "interests" in data:
            interests = set(data["interests"])
        elif "extensions" in data and "topic_interests" in data["extensions"]:
            interests = set(data["extensions"]["topic_interests"])
        elif "knowledge" in data and "topic_interests" in data["knowledge"]:
            interests = set(data["knowledge"]["topic_interests"])

        # Extract communication style
        communication_style = {}
        if "communication_style" in data:
            communication_style = data["communication_style"]
        elif "extensions" in data and "communication_style" in data["extensions"]:
            communication_style = data["extensions"]["communication_style"]

        # Get display name
        display_name = data.get("display_name", data.get("name", persona_id))

        features = PersonaFeatures(
            persona_id=persona_id,
            display_name=display_name,
            big_five=big_five,
            interests=interests,
            communication_style=communication_style,
        )

        self._persona_cache[persona_id] = features
        return features

    def compute_trait_similarity(
        self, source: PersonaFeatures, target: PersonaFeatures
    ) -> float:
        """
        Compute cosine similarity between Big Five trait vectors.

        Args:
            source: Source persona features
            target: Target persona features

        Returns:
            Cosine similarity score between 0 and 1
        """
        traits = [
            "openness",
            "conscientiousness",
            "extraversion",
            "agreeableness",
            "neuroticism",
        ]

        source_vec = np.array(
            [source.big_five.get(t, 0.5) for t in traits], dtype=np.float32
        )
        target_vec = np.array(
            [target.big_five.get(t, 0.5) for t in traits], dtype=np.float32
        )

        # Cosine similarity
        norm_source = np.linalg.norm(source_vec)
        norm_target = np.linalg.norm(target_vec)

        if norm_source == 0 or norm_target == 0:
            return 0.0

        similarity = np.dot(source_vec, target_vec) / (norm_source * norm_target)

        # Normalize from [-1, 1] to [0, 1]
        return float((similarity + 1.0) / 2.0)

    def compute_interest_overlap(
        self, source: PersonaFeatures, target: PersonaFeatures
    ) -> float:
        """
        Compute Jaccard index for interest overlap.

        Args:
            source: Source persona features
            target: Target persona features

        Returns:
            Jaccard index between 0 and 1
        """
        if not source.interests or not target.interests:
            return 0.0

        intersection = source.interests & target.interests
        union = source.interests | target.interests

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def compute_style_compatibility(
        self, source: PersonaFeatures, target: PersonaFeatures
    ) -> float:
        """
        Compute compatibility based on communication style.

        Uses weighted sum of formality and expressiveness differences.
        Higher score means more compatible styles.

        Args:
            source: Source persona features
            target: Target persona features

        Returns:
            Compatibility score between 0 and 1
        """
        weights = {"formality": 0.4, "verbosity": 0.3, "expressiveness": 0.3}

        total_diff = 0.0
        total_weight = 0.0

        for style, weight in weights.items():
            source_val = source.communication_style.get(style, 0.5)
            target_val = target.communication_style.get(style, 0.5)
            diff = abs(source_val - target_val)
            total_diff += weight * diff
            total_weight += weight

        if total_weight == 0:
            return 0.5

        # Convert difference to similarity (1 - normalized difference)
        avg_diff = total_diff / total_weight
        return 1.0 - avg_diff

    def compute_persona_similarity(self, source_id: str, target_id: str) -> float:
        """
        Compute overall similarity between two personas.

        Similarity = 0.5*trait_similarity + 0.3*interest_overlap + 0.2*style_compatibility

        Args:
            source_id: Source persona identifier
            target_id: Target persona identifier

        Returns:
            Similarity score between 0 and 1
        """
        try:
            source_features = self.load_persona_features(source_id)
            target_features = self.load_persona_features(target_id)
        except (FileNotFoundError, ValueError) as e:
            # Persona file not found - this is expected for invalid/placeholder IDs
            logger.debug(
                f"Persona features not found for '{source_id}' or '{target_id}': {e}"
            )
            return 0.0

        trait_sim = self.compute_trait_similarity(source_features, target_features)
        interest_overlap = self.compute_interest_overlap(
            source_features, target_features
        )
        style_compat = self.compute_style_compatibility(
            source_features, target_features
        )

        overall_similarity = (
            TRAIT_SIMILARITY_WEIGHT * trait_sim
            + INTEREST_OVERLAP_WEIGHT * interest_overlap
            + STYLE_COMPATIBILITY_WEIGHT * style_compat
        )

        if overall_similarity > 0.8 or overall_similarity < 0.3:
            logger.debug(
                f"Similarity between '{source_id}' and '{target_id}': "
                f"overall={overall_similarity:.3f}, traits={trait_sim:.3f}, "
                f"interests={interest_overlap:.3f}, style={style_compat:.3f}"
            )

        return overall_similarity

    def transfer_weights(
        self,
        source_agent: NeuralAgent,
        target_agent: NeuralAgent,
        similarity: float,
        transfer_target_network: bool = True,
    ) -> Dict[str, Any]:
        """
        Transfer neural network weights using progressive interpolation.

        For each layer: target_weight = similarity * source_weight + (1 - similarity) * target_weight

        Args:
            source_agent: Source NeuralAgent to transfer from
            target_agent: Target NeuralAgent to transfer to
            similarity: Similarity score between 0 and 1
            transfer_target_network: Whether to also transfer target network weights

        Returns:
            Dictionary with transfer statistics

        Raises:
            ValueError: If agents have incompatible architectures
        """
        if similarity < self.similarity_threshold:
            logger.warning(
                f"Similarity {similarity:.3f} below threshold {self.similarity_threshold}, "
                "skipping weight transfer"
            )
            return {"transferred": False, "reason": "similarity_below_threshold"}

        # Check architecture compatibility
        if source_agent.state_dim != target_agent.state_dim:
            raise ValueError(
                f"State dimension mismatch: source={source_agent.state_dim}, "
                f"target={target_agent.state_dim}"
            )
        if source_agent.action_dim != target_agent.action_dim:
            raise ValueError(
                f"Action dimension mismatch: source={source_agent.action_dim}, "
                f"target={target_agent.action_dim}"
            )

        # Transfer online network weights
        online_transferred = 0
        with torch.no_grad():
            for target_param, source_param in zip(
                target_agent.online_network.parameters(),
                source_agent.online_network.parameters(),
            ):
                # Progressive interpolation
                target_param.data.copy_(
                    similarity * source_param.data
                    + (1 - similarity) * target_param.data
                )
                online_transferred += 1

        # Transfer target network weights if requested
        target_transferred = 0
        if transfer_target_network:
            with torch.no_grad():
                for target_param, source_param in zip(
                    target_agent.target_network.parameters(),
                    source_agent.target_network.parameters(),
                ):
                    target_param.data.copy_(
                        similarity * source_param.data
                        + (1 - similarity) * target_param.data
                    )
                    target_transferred += 1

        logger.info(
            f"Transferred weights from source to target agent: "
            f"similarity={similarity:.3f}, online_layers={online_transferred}, "
            f"target_layers={target_transferred}"
        )

        return {
            "transferred": True,
            "similarity": similarity,
            "online_layers_transferred": online_transferred,
            "target_layers_transferred": target_transferred,
        }

    def transfer_strategies(
        self,
        source_meta: MetaController,
        target_meta: MetaController,
        similarity: float,
    ) -> Dict[str, Any]:
        """
        Transfer meta-level Q-values and worker agents between meta-controllers.

        Args:
            source_meta: Source MetaController to transfer from
            target_meta: Target MetaController to transfer to
            similarity: Similarity score between 0 and 1

        Returns:
            Dictionary with transfer statistics
        """
        if similarity < self.similarity_threshold:
            logger.warning(
                f"Similarity {similarity:.3f} below threshold {self.similarity_threshold}, "
                "skipping strategy transfer"
            )
            return {"transferred": False, "reason": "similarity_below_threshold"}

        results = {
            "transferred": True,
            "similarity": similarity,
            "meta_layers_transferred": 0,
            "workers_transferred": 0,
            "worker_transfer_results": [],
        }

        # Transfer meta-level network weights
        with torch.no_grad():
            for target_param, source_param in zip(
                target_meta.meta_online_network.parameters(),
                source_meta.meta_online_network.parameters(),
            ):
                target_param.data.copy_(
                    similarity * source_param.data
                    + (1 - similarity) * target_param.data
                )
                results["meta_layers_transferred"] += 1

            for target_param, source_param in zip(
                target_meta.meta_target_network.parameters(),
                source_meta.meta_target_network.parameters(),
            ):
                target_param.data.copy_(
                    similarity * source_param.data
                    + (1 - similarity) * target_param.data
                )

        # Transfer worker agents for each strategy
        for strategy in Strategy:
            if strategy in source_meta.workers and strategy in target_meta.workers:
                worker_result = self.transfer_weights(
                    source_meta.workers[strategy],
                    target_meta.workers[strategy],
                    similarity,
                    transfer_target_network=True,
                )
                results["workers_transferred"] += 1
                results["worker_transfer_results"].append(
                    {
                        "strategy": strategy.name,
                        **worker_result,
                    }
                )

        logger.info(
            f"Transferred strategies: similarity={similarity:.3f}, "
            f"meta_layers={results['meta_layers_transferred']}, "
            f"workers={results['workers_transferred']}"
        )

        return results

    def fine_tune_after_transfer(
        self,
        agent: NeuralAgent,
        dataset: OfflineRLDataset,
        epochs: int = 10,
        batch_size: int = 32,
        alpha: float = 1.0,
        learning_rate: float = 1e-4,
    ) -> Dict[str, Any]:
        """
        Fine-tune transferred network on target persona's own data.

        Uses CQLTrainer from offline_rl.py for conservative Q-learning.

        Args:
            agent: NeuralAgent to fine-tune
            dataset: OfflineRLDataset with target persona's historical data
            epochs: Number of training epochs
            batch_size: Batch size for training
            alpha: CQL regularization coefficient
            learning_rate: Learning rate for fine-tuning

        Returns:
            Dictionary with fine-tuning statistics
        """
        if not dataset.transitions:
            logger.warning("No transitions in dataset, skipping fine-tuning")
            return {"fine_tuned": False, "reason": "no_data"}

        trainer = CQLTrainer(
            agent=agent,
            alpha=alpha,
            learning_rate=learning_rate,
            device=agent.device,
        )

        agent.train_mode()

        epoch_losses = []
        for epoch in range(epochs):
            batch = dataset.get_train_batch(batch_size)
            if not batch:
                break

            transition_batch = collate_transitions(batch, agent.device)
            metrics = trainer.train_step(transition_batch)
            epoch_losses.append(metrics["loss"])

        agent.eval_mode()

        avg_loss = np.mean(epoch_losses) if epoch_losses else 0.0

        logger.info(f"Fine-tuned agent for {epochs} epochs: avg_loss={avg_loss:.4f}")

        return {
            "fine_tuned": True,
            "epochs": epochs,
            "avg_loss": avg_loss,
            "final_loss": epoch_losses[-1] if epoch_losses else 0.0,
            "trainer_stats": trainer.get_stats(),
        }

    def record_transfer(
        self,
        source_id: str,
        target_id: str,
        similarity: float,
        components_transferred: List[str],
        weight_transfer_ratio: float = 0.0,
        strategy_transfer_ratio: float = 0.0,
        fine_tune_epochs: int = 0,
        fine_tune_loss: float = 0.0,
    ) -> None:
        """
        Record a transfer event to the transfer log.

        Args:
            source_id: Source persona identifier
            target_id: Target persona identifier
            similarity: Similarity score between personas
            components_transferred: List of transferred components (e.g., ["weights", "strategies"])
            weight_transfer_ratio: Ratio of weights transferred
            strategy_transfer_ratio: Ratio of strategies transferred
            fine_tune_epochs: Number of fine-tuning epochs
            fine_tune_loss: Final fine-tuning loss
        """
        event = TransferEvent(
            source_id=source_id,
            target_id=target_id,
            timestamp=datetime.now().isoformat(),
            similarity=similarity,
            components_transferred=components_transferred,
            weight_transfer_ratio=weight_transfer_ratio,
            strategy_transfer_ratio=strategy_transfer_ratio,
            fine_tune_epochs=fine_tune_epochs,
            fine_tune_loss=fine_tune_loss,
        )

        # Load existing transfers
        transfers = []
        if self.transfer_log_path.exists():
            try:
                with open(self.transfer_log_path, "r", encoding="utf-8") as f:
                    transfers = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load transfer log: {e}")

        # Append new event
        transfers.append(event.to_dict())

        # Save updated log
        try:
            with open(self.transfer_log_path, "w", encoding="utf-8") as f:
                json.dump(transfers, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save transfer log: {e}")

        logger.info(
            f"Recorded transfer: {source_id} -> {target_id} "
            f"(similarity={similarity:.3f}, components={components_transferred})"
        )

    def get_transfer_lineage(self, persona_id: str) -> Dict[str, Any]:
        """
        Build ancestry tree showing knowledge flow for a persona.

        Args:
            persona_id: Persona identifier to trace lineage for

        Returns:
            Dictionary with ancestry tree and transfer history
        """
        if not self.transfer_log_path.exists():
            return {"persona_id": persona_id, "ancestors": [], "descendants": []}

        try:
            with open(self.transfer_log_path, "r", encoding="utf-8") as f:
                transfers = json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"persona_id": persona_id, "ancestors": [], "descendants": []}

        # Build ancestry (sources that transferred TO this persona)
        ancestors = []
        for transfer in transfers:
            if transfer["target_id"] == persona_id:
                ancestors.append(
                    {
                        "persona_id": transfer["source_id"],
                        "similarity": transfer["similarity"],
                        "timestamp": transfer["timestamp"],
                        "components": transfer["components_transferred"],
                    }
                )

        # Build descendants (targets that received FROM this persona)
        descendants = []
        for transfer in transfers:
            if transfer["source_id"] == persona_id:
                descendants.append(
                    {
                        "persona_id": transfer["target_id"],
                        "similarity": transfer["similarity"],
                        "timestamp": transfer["timestamp"],
                        "components": transfer["components_transferred"],
                    }
                )

        return {
            "persona_id": persona_id,
            "ancestors": ancestors,
            "descendants": descendants,
            "total_transfers_in": len(ancestors),
            "total_transfers_out": len(descendants),
        }

    def get_all_transfers(self) -> List[Dict[str, Any]]:
        """
        Get all recorded transfer events.

        Returns:
            List of transfer event dictionaries
        """
        if not self.transfer_log_path.exists():
            return []

        try:
            with open(self.transfer_log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load transfer log: {e}")
            return []

    def clear_transfer_history(self) -> None:
        """Clear all transfer history."""
        if self.transfer_log_path.exists():
            try:
                self.transfer_log_path.unlink()
                logger.info("Cleared transfer history")
            except IOError as e:
                logger.error(f"Failed to clear transfer history: {e}")

    def execute_full_transfer(
        self,
        source_id: str,
        target_id: str,
        source_agent: NeuralAgent,
        target_agent: NeuralAgent,
        source_meta: Optional[MetaController] = None,
        target_meta: Optional[MetaController] = None,
        dataset: Optional[OfflineRLDataset] = None,
        fine_tune_epochs: int = 0,
        components: str = "both",
    ) -> Dict[str, Any]:
        """
        Execute a complete knowledge transfer between two personas.

        This is a convenience method that performs similarity computation,
        weight/strategy transfer, optional fine-tuning, and records the event.

        Args:
            source_id: Source persona identifier
            target_id: Target persona identifier
            source_agent: Source NeuralAgent
            target_agent: Target NeuralAgent
            source_meta: Optional source MetaController
            target_meta: Optional target MetaController
            dataset: Optional dataset for fine-tuning
            fine_tune_epochs: Number of fine-tuning epochs (0 to skip)
            components: Which components to transfer ("weights", "strategies", or "both")

        Returns:
            Dictionary with complete transfer results
        """
        # Compute similarity
        similarity = self.compute_persona_similarity(source_id, target_id)

        results = {
            "source_id": source_id,
            "target_id": target_id,
            "similarity": similarity,
            "components": components,
            "weight_transfer": None,
            "strategy_transfer": None,
            "fine_tuning": None,
        }

        components_transferred = []
        weight_ratio = 0.0
        strategy_ratio = 0.0

        # Transfer weights
        if components in ("weights", "both"):
            weight_result = self.transfer_weights(
                source_agent, target_agent, similarity
            )
            results["weight_transfer"] = weight_result
            if weight_result.get("transferred"):
                components_transferred.append("weights")
                weight_ratio = weight_result.get("similarity", 0.0)

        # Transfer strategies
        if components in ("strategies", "both") and source_meta and target_meta:
            strategy_result = self.transfer_strategies(
                source_meta, target_meta, similarity
            )
            results["strategy_transfer"] = strategy_result
            if strategy_result.get("transferred"):
                components_transferred.append("strategies")
                strategy_ratio = strategy_result.get("similarity", 0.0)

        # Fine-tune
        fine_tune_loss = 0.0
        if fine_tune_epochs > 0 and dataset:
            ft_result = self.fine_tune_after_transfer(
                target_agent, dataset, epochs=fine_tune_epochs
            )
            results["fine_tuning"] = ft_result
            if ft_result.get("fine_tuned"):
                fine_tune_loss = ft_result.get("final_loss", 0.0)

        # Record transfer
        self.record_transfer(
            source_id=source_id,
            target_id=target_id,
            similarity=similarity,
            components_transferred=components_transferred,
            weight_transfer_ratio=weight_ratio,
            strategy_transfer_ratio=strategy_ratio,
            fine_tune_epochs=fine_tune_epochs,
            fine_tune_loss=fine_tune_loss,
        )

        return results
