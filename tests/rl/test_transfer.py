"""Tests for Knowledge Transfer Framework."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from services.persona.rl.hierarchical import MetaController, Strategy
from services.persona.rl.neural_agent import NeuralAgent
from services.persona.rl.offline_rl import OfflineRLDataset, Transition
from services.persona.rl.transfer import (
    DEFAULT_SIMILARITY_THRESHOLD,
    INTEREST_OVERLAP_WEIGHT,
    STYLE_COMPATIBILITY_WEIGHT,
    TRAIT_SIMILARITY_WEIGHT,
    KnowledgeTransfer,
    PersonaFeatures,
    TransferEvent,
)
from services.persona.rl.types import RLAction


class TestPersonaFeatures:
    """Tests for PersonaFeatures dataclass."""

    def test_default_initialization(self):
        features = PersonaFeatures(persona_id="test", display_name="Test")
        assert features.persona_id == "test"
        assert features.display_name == "Test"
        assert len(features.big_five) == 5
        assert len(features.interests) == 0
        assert len(features.communication_style) == 3

    def test_post_init_defaults(self):
        features = PersonaFeatures(persona_id="test", display_name="Test")
        assert features.big_five["openness"] == 0.5
        assert features.big_five["conscientiousness"] == 0.5
        assert features.big_five["extraversion"] == 0.5
        assert features.big_five["agreeableness"] == 0.5
        assert features.big_five["neuroticism"] == 0.5

    def test_custom_values(self):
        features = PersonaFeatures(
            persona_id="test",
            display_name="Test",
            big_five={"openness": 0.8, "conscientiousness": 0.9},
            interests={"gaming", "coding"},
            communication_style={"formality": 0.7},
        )
        assert features.big_five["openness"] == 0.8
        assert features.big_five["conscientiousness"] == 0.9
        assert "gaming" in features.interests
        assert features.communication_style["formality"] == 0.7


class TestTransferEvent:
    """Tests for TransferEvent dataclass."""

    def test_to_dict(self):
        event = TransferEvent(
            source_id="source",
            target_id="target",
            timestamp="2024-01-01T00:00:00",
            similarity=0.75,
            components_transferred=["weights", "strategies"],
            weight_transfer_ratio=0.75,
            strategy_transfer_ratio=0.75,
            fine_tune_epochs=10,
            fine_tune_loss=0.05,
        )
        d = event.to_dict()
        assert d["source_id"] == "source"
        assert d["target_id"] == "target"
        assert d["similarity"] == 0.75
        assert d["components_transferred"] == ["weights", "strategies"]

    def test_from_dict(self):
        data = {
            "source_id": "source",
            "target_id": "target",
            "timestamp": "2024-01-01T00:00:00",
            "similarity": 0.75,
            "components_transferred": ["weights"],
            "weight_transfer_ratio": 0.75,
            "strategy_transfer_ratio": 0.0,
            "fine_tune_epochs": 5,
            "fine_tune_loss": 0.1,
        }
        event = TransferEvent.from_dict(data)
        assert event.source_id == "source"
        assert event.target_id == "target"
        assert event.similarity == 0.75


class TestKnowledgeTransferInitialization:
    """Tests for KnowledgeTransfer initialization."""

    def test_default_initialization(self):
        transfer = KnowledgeTransfer()
        assert transfer.persona_dir == Path("prompts/characters")
        assert transfer.transfer_log_path == Path("data/rl_transfers.json")
        assert transfer.similarity_threshold == DEFAULT_SIMILARITY_THRESHOLD
        assert transfer.device == torch.device("cpu")

    def test_custom_initialization(self):
        transfer = KnowledgeTransfer(
            persona_dir=Path("custom/personas"),
            transfer_log_path=Path("custom/transfers.json"),
            similarity_threshold=0.5,
            device="cpu",
        )
        assert transfer.persona_dir == Path("custom/personas")
        assert transfer.transfer_log_path == Path("custom/transfers.json")
        assert transfer.similarity_threshold == 0.5

    def test_creates_transfer_log_directory(self, tmp_path):
        log_path = tmp_path / "nested" / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)
        assert log_path.parent.exists()


class TestLoadPersonaFeatures:
    """Tests for loading persona features from JSON."""

    def test_load_chara_card_v2_format(self, tmp_path):
        persona_data = {
            "spec": "chara_card_v2",
            "data": {
                "name": "Test Persona",
                "extensions": {
                    "big_five": {
                        "openness": 0.8,
                        "conscientiousness": 0.7,
                        "extraversion": 0.6,
                        "agreeableness": 0.5,
                        "neuroticism": 0.4,
                    },
                    "topic_interests": ["gaming", "coding"],
                    "communication_style": {
                        "formality": 0.9,
                        "verbosity": 0.8,
                        "expressiveness": 0.7,
                    },
                },
            },
        }

        persona_file = tmp_path / "test_persona.json"
        with open(persona_file, "w") as f:
            json.dump(persona_data, f)

        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        features = transfer.load_persona_features("test_persona")

        assert features.persona_id == "test_persona"
        assert features.display_name == "Test Persona"
        assert features.big_five["openness"] == 0.8
        assert "gaming" in features.interests
        assert features.communication_style["formality"] == 0.9

    def test_load_flat_format(self, tmp_path):
        persona_data = {
            "display_name": "Flat Persona",
            "big_five": {"openness": 0.9},
            "interests": ["reading", "writing"],
            "communication_style": {"formality": 0.5},
        }

        persona_file = tmp_path / "flat_persona.json"
        with open(persona_file, "w") as f:
            json.dump(persona_data, f)

        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        features = transfer.load_persona_features("flat_persona")

        assert features.display_name == "Flat Persona"
        assert features.big_five["openness"] == 0.9
        assert "reading" in features.interests

    def test_load_knowledge_format(self, tmp_path):
        persona_data = {
            "name": "Knowledge Persona",
            "knowledge": {
                "topic_interests": ["science", "math"],
            },
        }

        persona_file = tmp_path / "knowledge_persona.json"
        with open(persona_file, "w") as f:
            json.dump(persona_data, f)

        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        features = transfer.load_persona_features("knowledge_persona")

        assert "science" in features.interests
        assert "math" in features.interests

    def test_file_not_found(self, tmp_path):
        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            transfer.load_persona_features("nonexistent")

    def test_invalid_json(self, tmp_path):
        persona_file = tmp_path / "invalid.json"
        with open(persona_file, "w") as f:
            f.write("not valid json")

        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        with pytest.raises(ValueError):
            transfer.load_persona_features("invalid")

    def test_caching(self, tmp_path):
        persona_data = {"name": "Cached Persona"}
        persona_file = tmp_path / "cached.json"
        with open(persona_file, "w") as f:
            json.dump(persona_data, f)

        transfer = KnowledgeTransfer(persona_dir=tmp_path)

        # First load
        features1 = transfer.load_persona_features("cached")
        # Second load should use cache
        features2 = transfer.load_persona_features("cached")

        assert features1 is features2


class TestTraitSimilarity:
    """Tests for trait similarity computation."""

    def test_identical_traits(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            big_five={
                "openness": 0.5,
                "conscientiousness": 0.5,
                "extraversion": 0.5,
                "agreeableness": 0.5,
                "neuroticism": 0.5,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            big_five={
                "openness": 0.5,
                "conscientiousness": 0.5,
                "extraversion": 0.5,
                "agreeableness": 0.5,
                "neuroticism": 0.5,
            },
        )

        transfer = KnowledgeTransfer()
        similarity = transfer.compute_trait_similarity(source, target)
        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_opposite_traits(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            big_five={
                "openness": 1.0,
                "conscientiousness": 1.0,
                "extraversion": 1.0,
                "agreeableness": 1.0,
                "neuroticism": 1.0,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            big_five={
                "openness": 0.0,
                "conscientiousness": 0.0,
                "extraversion": 0.0,
                "agreeableness": 0.0,
                "neuroticism": 0.0,
            },
        )

        transfer = KnowledgeTransfer()
        similarity = transfer.compute_trait_similarity(source, target)
        assert similarity == pytest.approx(0.0, abs=0.01)

    def test_partial_similarity(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            big_five={
                "openness": 0.8,
                "conscientiousness": 0.6,
                "extraversion": 0.7,
                "agreeableness": 0.5,
                "neuroticism": 0.4,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            big_five={
                "openness": 0.6,
                "conscientiousness": 0.8,
                "extraversion": 0.5,
                "agreeableness": 0.7,
                "neuroticism": 0.3,
            },
        )

        transfer = KnowledgeTransfer()
        similarity = transfer.compute_trait_similarity(source, target)
        assert 0.0 < similarity < 1.0


class TestInterestOverlap:
    """Tests for interest overlap computation."""

    def test_identical_interests(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            interests={"gaming", "coding", "reading"},
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            interests={"gaming", "coding", "reading"},
        )

        transfer = KnowledgeTransfer()
        overlap = transfer.compute_interest_overlap(source, target)
        assert overlap == 1.0

    def test_no_overlap(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            interests={"gaming", "coding"},
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            interests={"reading", "writing"},
        )

        transfer = KnowledgeTransfer()
        overlap = transfer.compute_interest_overlap(source, target)
        assert overlap == 0.0

    def test_partial_overlap(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            interests={"gaming", "coding", "reading"},
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            interests={"gaming", "writing", "math"},
        )

        transfer = KnowledgeTransfer()
        overlap = transfer.compute_interest_overlap(source, target)
        # Intersection: {gaming}, Union: {gaming, coding, reading, writing, math}
        assert overlap == pytest.approx(0.2, abs=0.01)

    def test_empty_interests(self):
        source = PersonaFeatures(
            persona_id="source", display_name="Source", interests=set()
        )
        target = PersonaFeatures(
            persona_id="target", display_name="Target", interests={"gaming"}
        )

        transfer = KnowledgeTransfer()
        overlap = transfer.compute_interest_overlap(source, target)
        assert overlap == 0.0


class TestStyleCompatibility:
    """Tests for style compatibility computation."""

    def test_identical_style(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            communication_style={
                "formality": 0.5,
                "verbosity": 0.5,
                "expressiveness": 0.5,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            communication_style={
                "formality": 0.5,
                "verbosity": 0.5,
                "expressiveness": 0.5,
            },
        )

        transfer = KnowledgeTransfer()
        compat = transfer.compute_style_compatibility(source, target)
        assert compat == pytest.approx(1.0, abs=0.01)

    def test_opposite_style(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            communication_style={
                "formality": 1.0,
                "verbosity": 1.0,
                "expressiveness": 1.0,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            communication_style={
                "formality": 0.0,
                "verbosity": 0.0,
                "expressiveness": 0.0,
            },
        )

        transfer = KnowledgeTransfer()
        compat = transfer.compute_style_compatibility(source, target)
        assert compat == pytest.approx(0.0, abs=0.01)

    def test_partial_compatibility(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            communication_style={
                "formality": 0.8,
                "verbosity": 0.6,
                "expressiveness": 0.7,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            communication_style={
                "formality": 0.4,
                "verbosity": 0.8,
                "expressiveness": 0.5,
            },
        )

        transfer = KnowledgeTransfer()
        compat = transfer.compute_style_compatibility(source, target)
        assert 0.0 < compat < 1.0


class TestPersonaSimilarity:
    """Tests for overall persona similarity computation."""

    def test_similarity_weights(self, tmp_path):
        # Create two personas
        source_data = {
            "name": "Source",
            "big_five": {
                "openness": 0.8,
                "conscientiousness": 0.7,
                "extraversion": 0.6,
                "agreeableness": 0.5,
                "neuroticism": 0.4,
            },
            "interests": ["gaming", "coding"],
            "communication_style": {
                "formality": 0.9,
                "verbosity": 0.8,
                "expressiveness": 0.7,
            },
        }
        target_data = {
            "name": "Target",
            "big_five": {
                "openness": 0.7,
                "conscientiousness": 0.8,
                "extraversion": 0.5,
                "agreeableness": 0.6,
                "neuroticism": 0.3,
            },
            "interests": ["gaming", "reading"],
            "communication_style": {
                "formality": 0.8,
                "verbosity": 0.7,
                "expressiveness": 0.8,
            },
        }

        (tmp_path / "source.json").write_text(json.dumps(source_data))
        (tmp_path / "target.json").write_text(json.dumps(target_data))

        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        similarity = transfer.compute_persona_similarity("source", "target")

        assert 0.0 <= similarity <= 1.0

    def test_missing_persona(self, tmp_path):
        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        similarity = transfer.compute_persona_similarity("nonexistent1", "nonexistent2")
        assert similarity == 0.0


class TestWeightTransfer:
    """Tests for neural network weight transfer."""

    def test_successful_transfer(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4, hidden_dims=(32,))
        target_agent = NeuralAgent(state_dim=64, action_dim=4, hidden_dims=(32,))

        # Set source weights to known values
        with torch.no_grad():
            for param in source_agent.online_network.parameters():
                param.fill_(1.0)
            for param in source_agent.target_network.parameters():
                param.fill_(1.0)

        # Set target weights to different values
        with torch.no_grad():
            for param in target_agent.online_network.parameters():
                param.fill_(0.0)
            for param in target_agent.target_network.parameters():
                param.fill_(0.0)

        transfer = KnowledgeTransfer(similarity_threshold=0.0)
        result = transfer.transfer_weights(source_agent, target_agent, similarity=0.5)

        assert result["transferred"] is True
        assert result["similarity"] == 0.5
        assert result["online_layers_transferred"] > 0

        # Check that weights were interpolated
        for param in target_agent.online_network.parameters():
            assert param.mean().item() == pytest.approx(0.5, abs=0.01)

    def test_below_threshold(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4)
        target_agent = NeuralAgent(state_dim=64, action_dim=4)

        transfer = KnowledgeTransfer(similarity_threshold=0.5)
        result = transfer.transfer_weights(source_agent, target_agent, similarity=0.3)

        assert result["transferred"] is False
        assert result["reason"] == "similarity_below_threshold"

    def test_incompatible_architectures(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4)
        target_agent = NeuralAgent(state_dim=32, action_dim=4)

        transfer = KnowledgeTransfer(similarity_threshold=0.0)
        with pytest.raises(ValueError, match="State dimension mismatch"):
            transfer.transfer_weights(source_agent, target_agent, similarity=0.5)

    def test_skip_target_network(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4, hidden_dims=(32,))
        target_agent = NeuralAgent(state_dim=64, action_dim=4, hidden_dims=(32,))

        with torch.no_grad():
            for param in source_agent.online_network.parameters():
                param.fill_(1.0)
            for param in target_agent.online_network.parameters():
                param.fill_(0.0)

        transfer = KnowledgeTransfer(similarity_threshold=0.0)
        result = transfer.transfer_weights(
            source_agent, target_agent, similarity=0.5, transfer_target_network=False
        )

        assert result["target_layers_transferred"] == 0


class TestStrategyTransfer:
    """Tests for strategy transfer between meta-controllers."""

    def test_successful_strategy_transfer(self):
        source_meta = MetaController(state_dim=64)
        target_meta = MetaController(state_dim=64)

        # Set source meta weights
        with torch.no_grad():
            for param in source_meta.meta_online_network.parameters():
                param.fill_(1.0)

        # Set target meta weights
        with torch.no_grad():
            for param in target_meta.meta_online_network.parameters():
                param.fill_(0.0)

        transfer = KnowledgeTransfer(similarity_threshold=0.0)
        result = transfer.transfer_strategies(source_meta, target_meta, similarity=0.5)

        assert result["transferred"] is True
        assert result["workers_transferred"] == 4  # All strategies

    def test_below_threshold(self):
        source_meta = MetaController()
        target_meta = MetaController()

        transfer = KnowledgeTransfer(similarity_threshold=0.5)
        result = transfer.transfer_strategies(source_meta, target_meta, similarity=0.3)

        assert result["transferred"] is False


class TestFineTuning:
    """Tests for fine-tuning after transfer."""

    def test_no_data(self):
        agent = NeuralAgent()
        dataset = OfflineRLDataset(db_path="nonexistent.db")

        transfer = KnowledgeTransfer()
        result = transfer.fine_tune_after_transfer(agent, dataset, epochs=5)

        assert result["fine_tuned"] is False
        assert result["reason"] == "no_data"

    def test_successful_fine_tuning(self, tmp_path):
        agent = NeuralAgent(state_dim=128, action_dim=4)
        dataset = OfflineRLDataset(db_path=tmp_path / "test.db")

        # Add some transitions
        for i in range(50):
            transition = Transition(
                state=(i % 10, i, i % 50),
                action=RLAction.WAIT,
                reward=1.0,
                next_state=((i + 1) % 10, i + 1, (i + 1) % 50),
                done=False,
            )
            dataset.transitions.append(transition)

        dataset._train_indices = list(range(len(dataset.transitions)))

        transfer = KnowledgeTransfer()
        result = transfer.fine_tune_after_transfer(
            agent, dataset, epochs=2, batch_size=8
        )

        assert result["fine_tuned"] is True
        assert result["epochs"] == 2
        assert "avg_loss" in result


class TestTransferRecording:
    """Tests for transfer event recording."""

    def test_record_transfer(self, tmp_path):
        log_path = tmp_path / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)

        transfer.record_transfer(
            source_id="source",
            target_id="target",
            similarity=0.75,
            components_transferred=["weights", "strategies"],
            weight_transfer_ratio=0.75,
            strategy_transfer_ratio=0.75,
            fine_tune_epochs=10,
            fine_tune_loss=0.05,
        )

        assert log_path.exists()
        with open(log_path) as f:
            transfers = json.load(f)
        assert len(transfers) == 1
        assert transfers[0]["source_id"] == "source"

    def test_append_to_existing(self, tmp_path):
        log_path = tmp_path / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)

        transfer.record_transfer("source1", "target1", 0.5, ["weights"], 0.5, 0.0)
        transfer.record_transfer("source2", "target2", 0.6, ["strategies"], 0.0, 0.6)

        with open(log_path) as f:
            transfers = json.load(f)
        assert len(transfers) == 2


class TestTransferLineage:
    """Tests for transfer lineage tracking."""

    def test_empty_lineage(self, tmp_path):
        transfer = KnowledgeTransfer(transfer_log_path=tmp_path / "transfers.json")
        lineage = transfer.get_transfer_lineage("persona")

        assert lineage["persona_id"] == "persona"
        assert lineage["ancestors"] == []
        assert lineage["descendants"] == []

    def test_with_transfers(self, tmp_path):
        log_path = tmp_path / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)

        # Record some transfers
        transfer.record_transfer("ancestor", "persona", 0.8, ["weights"], 0.8, 0.0)
        transfer.record_transfer("persona", "descendant", 0.7, ["strategies"], 0.0, 0.7)

        lineage = transfer.get_transfer_lineage("persona")

        assert len(lineage["ancestors"]) == 1
        assert lineage["ancestors"][0]["persona_id"] == "ancestor"
        assert len(lineage["descendants"]) == 1
        assert lineage["descendants"][0]["persona_id"] == "descendant"
        assert lineage["total_transfers_in"] == 1
        assert lineage["total_transfers_out"] == 1


class TestGetAllTransfers:
    """Tests for getting all transfers."""

    def test_empty(self, tmp_path):
        transfer = KnowledgeTransfer(transfer_log_path=tmp_path / "transfers.json")
        transfers = transfer.get_all_transfers()
        assert transfers == []

    def test_with_transfers(self, tmp_path):
        log_path = tmp_path / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)

        transfer.record_transfer("a", "b", 0.5, ["weights"], 0.5, 0.0)
        transfer.record_transfer("c", "d", 0.6, ["strategies"], 0.0, 0.6)

        transfers = transfer.get_all_transfers()
        assert len(transfers) == 2


class TestClearTransferHistory:
    """Tests for clearing transfer history."""

    def test_clear_existing(self, tmp_path):
        log_path = tmp_path / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)

        transfer.record_transfer("a", "b", 0.5, ["weights"], 0.5, 0.0)
        assert log_path.exists()

        transfer.clear_transfer_history()
        assert not log_path.exists()

    def test_clear_nonexistent(self, tmp_path):
        log_path = tmp_path / "transfers.json"
        transfer = KnowledgeTransfer(transfer_log_path=log_path)

        # Should not raise
        transfer.clear_transfer_history()


class TestExecuteFullTransfer:
    """Tests for execute_full_transfer convenience method."""

    def test_full_transfer_weights_only(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4, hidden_dims=(32,))
        target_agent = NeuralAgent(state_dim=64, action_dim=4, hidden_dims=(32,))

        # Set source weights
        with torch.no_grad():
            for param in source_agent.online_network.parameters():
                param.fill_(1.0)

        # Set target weights
        with torch.no_grad():
            for param in target_agent.online_network.parameters():
                param.fill_(0.0)

        transfer = KnowledgeTransfer(similarity_threshold=0.0)
        result = transfer.execute_full_transfer(
            source_id="source",
            target_id="target",
            source_agent=source_agent,
            target_agent=target_agent,
            components="weights",
        )

        assert result["source_id"] == "source"
        assert result["target_id"] == "target"
        assert result["components"] == "weights"
        assert result["weight_transfer"]["transferred"] is True

    def test_full_transfer_with_strategies(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4)
        target_agent = NeuralAgent(state_dim=64, action_dim=4)
        source_meta = MetaController(state_dim=64)
        target_meta = MetaController(state_dim=64)

        transfer = KnowledgeTransfer(similarity_threshold=0.0)
        result = transfer.execute_full_transfer(
            source_id="source",
            target_id="target",
            source_agent=source_agent,
            target_agent=target_agent,
            source_meta=source_meta,
            target_meta=target_meta,
            components="both",
        )

        assert result["strategy_transfer"]["transferred"] is True


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_similarity(self):
        source = PersonaFeatures(
            persona_id="source",
            display_name="Source",
            big_five={
                "openness": 1.0,
                "conscientiousness": 1.0,
                "extraversion": 1.0,
                "agreeableness": 1.0,
                "neuroticism": 1.0,
            },
            interests={"a", "b", "c"},
            communication_style={
                "formality": 1.0,
                "verbosity": 1.0,
                "expressiveness": 1.0,
            },
        )
        target = PersonaFeatures(
            persona_id="target",
            display_name="Target",
            big_five={
                "openness": 0.0,
                "conscientiousness": 0.0,
                "extraversion": 0.0,
                "agreeableness": 0.0,
                "neuroticism": 0.0,
            },
            interests={"d", "e", "f"},
            communication_style={
                "formality": 0.0,
                "verbosity": 0.0,
                "expressiveness": 0.0,
            },
        )

        transfer = KnowledgeTransfer()
        trait_sim = transfer.compute_trait_similarity(source, target)
        interest_overlap = transfer.compute_interest_overlap(source, target)
        style_compat = transfer.compute_style_compatibility(source, target)

        assert trait_sim == pytest.approx(0.0, abs=0.1)
        assert interest_overlap == 0.0
        assert style_compat == pytest.approx(0.0, abs=0.1)

    def test_identical_personas(self, tmp_path):
        persona_data = {
            "name": "Identical",
            "big_five": {
                "openness": 0.7,
                "conscientiousness": 0.6,
                "extraversion": 0.5,
                "agreeableness": 0.4,
                "neuroticism": 0.3,
            },
            "interests": ["gaming", "coding"],
            "communication_style": {
                "formality": 0.8,
                "verbosity": 0.7,
                "expressiveness": 0.6,
            },
        }

        (tmp_path / "source.json").write_text(json.dumps(persona_data))
        (tmp_path / "target.json").write_text(json.dumps(persona_data))

        transfer = KnowledgeTransfer(persona_dir=tmp_path)
        similarity = transfer.compute_persona_similarity("source", "target")

        assert similarity == pytest.approx(1.0, abs=0.1)

    def test_empty_persona_features(self):
        source = PersonaFeatures(persona_id="source", display_name="Source")
        target = PersonaFeatures(persona_id="target", display_name="Target")

        transfer = KnowledgeTransfer()
        trait_sim = transfer.compute_trait_similarity(source, target)
        interest_overlap = transfer.compute_interest_overlap(source, target)
        style_compat = transfer.compute_style_compatibility(source, target)

        # Both have default values, so should have some similarity
        assert trait_sim == pytest.approx(1.0, abs=0.1)  # Identical defaults
        assert interest_overlap == 0.0  # No interests
        assert style_compat == pytest.approx(1.0, abs=0.1)  # Identical defaults


class TestSimilarityWeights:
    """Tests to verify similarity weight constants."""

    def test_trait_weight(self):
        assert TRAIT_SIMILARITY_WEIGHT == 0.5

    def test_interest_weight(self):
        assert INTEREST_OVERLAP_WEIGHT == 0.3

    def test_style_weight(self):
        assert STYLE_COMPATIBILITY_WEIGHT == 0.2

    def test_weights_sum_to_one(self):
        total = (
            TRAIT_SIMILARITY_WEIGHT
            + INTEREST_OVERLAP_WEIGHT
            + STYLE_COMPATIBILITY_WEIGHT
        )
        assert total == pytest.approx(1.0, abs=0.01)


class TestDefaultThreshold:
    """Tests for default similarity threshold."""

    def test_default_threshold_value(self):
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.3

    def test_threshold_respected(self):
        source_agent = NeuralAgent(state_dim=64, action_dim=4)
        target_agent = NeuralAgent(state_dim=64, action_dim=4)

        transfer = KnowledgeTransfer()  # Uses default threshold
        result = transfer.transfer_weights(source_agent, target_agent, similarity=0.2)

        assert result["transferred"] is False

        result = transfer.transfer_weights(source_agent, target_agent, similarity=0.5)
        assert result["transferred"] is True
