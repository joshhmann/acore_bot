"""Episodic memory system for storing and retrieving agent trajectories.

AF-2.9: Implements episode storage, vector similarity search, and few-shot
prompting support for learning from past successful/failed runs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Episode:
    """A single episode representing a trajectory of context, actions, and outcome.

    Episodes capture successful or failed runs for few-shot learning and
    retrieval during similar future situations.

    Attributes:
        episode_id: Unique identifier for the episode
        context: Situation/context description (e.g., user request, environment state)
        actions: Sequence of actions taken
        outcome: Result/outcome of the actions (success, failure, partial)
        timestamp: When the episode occurred
        metadata: Additional metadata (duration, tokens used, etc.)
        embedding: Optional pre-computed embedding vector for similarity search
    """

    episode_id: str
    context: str
    actions: list[dict[str, Any]]
    outcome: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert episode to dictionary for serialization."""
        return {
            "episode_id": self.episode_id,
            "context": self.context,
            "actions": self.actions,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        """Create Episode from dictionary."""
        return cls(
            episode_id=data["episode_id"],
            context=data["context"],
            actions=data.get("actions", []),
            outcome=data["outcome"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
        )

    @property
    def is_success(self) -> bool:
        """Check if episode represents a successful outcome."""
        outcome_lower = self.outcome.lower()
        return any(
            word in outcome_lower
            for word in ["success", "completed", "done", "finished"]
        )

    @property
    def is_failure(self) -> bool:
        """Check if episode represents a failed outcome."""
        outcome_lower = self.outcome.lower()
        return any(
            word in outcome_lower
            for word in ["fail", "error", "exception", "timeout", "abort"]
        )


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation providers."""

    async def embed(self, text: str) -> list[float]: ...


@dataclass
class EpisodicMemoryConfig:
    """Configuration for episodic memory system.

    Attributes:
        max_episodes: Maximum number of episodes to store per namespace
        similarity_threshold: Minimum similarity score for retrieval (0.0-1.0)
        embedding_dim: Dimension of embedding vectors
        enable_success_filtering: Only retrieve successful episodes
        max_context_length: Maximum length of context text to store
    """

    max_episodes: int = 1000
    similarity_threshold: float = 0.6
    embedding_dim: int = 384  # Standard for all-MiniLM-L6-v2
    enable_success_filtering: bool = False
    max_context_length: int = 2000

    def validate(self) -> bool:
        """Validate configuration values."""
        if self.max_episodes <= 0:
            logger.error(f"max_episodes must be positive, got {self.max_episodes}")
            return False
        if not 0.0 <= self.similarity_threshold <= 1.0:
            logger.error(
                f"similarity_threshold must be in [0, 1], got {self.similarity_threshold}"
            )
            return False
        if self.embedding_dim <= 0:
            logger.error(f"embedding_dim must be positive, got {self.embedding_dim}")
            return False
        return True


class EpisodicMemory:
    """Episodic memory system for storing and retrieving agent trajectories.

    Features:
    - Async storage and retrieval of episodes
    - Vector similarity search for finding similar past episodes
    - Support for few-shot prompting by retrieving relevant examples
    - Efficient JSON-based storage with namespace isolation

    Example:
        memory = EpisodicMemory("data/episodes")
        await memory.initialize()

        # Record a successful trajectory
        await memory.record_trajectory(
            namespace=MemoryNamespace("agent_1", "task_room"),
            context="User asked to summarize a document",
            actions=[{"tool": "read_file", "args": {...}}, {"tool": "summarize", "args": {...}}],
            outcome="success: Document summarized successfully",
        )

        # Find similar past episodes
        similar = await memory.search_similar(
            namespace=MemoryNamespace("agent_1", "task_room"),
            query="summarize this document for me",
            top_k=3,
        )
    """

    def __init__(
        self,
        root_dir: str | Path = "data/episodes",
        config: EpisodicMemoryConfig | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize episodic memory.

        Args:
            root_dir: Directory for storing episode files
            config: Configuration options
            embedding_provider: Optional provider for generating embeddings
        """
        self.root = Path(root_dir)
        self.config = config or EpisodicMemoryConfig()
        self.embedding_provider = embedding_provider

        if not self.config.validate():
            raise ValueError("Invalid episodic memory configuration")

        self._cache: dict[str, list[Episode]] = {}
        self._stats = {
            "total_episodes": 0,
            "total_searches": 0,
            "storage_ops": 0,
        }

    async def initialize(self) -> None:
        """Initialize the episodic memory system.

        Creates storage directory and loads existing episodes.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info(f"EpisodicMemory initialized at {self.root}")

    def _namespace_path(self, namespace: Any) -> Path:
        """Get file path for a namespace.

        Args:
            namespace: MemoryNamespace or object with persona_id and room_id

        Returns:
            Path to the namespace's episode file
        """
        # Handle both MemoryNamespace objects and dict-like objects
        if hasattr(namespace, "persona_id") and hasattr(namespace, "room_id"):
            persona_id = namespace.persona_id
            room_id = namespace.room_id
        elif isinstance(namespace, dict):
            persona_id = namespace.get("persona_id", "default")
            room_id = namespace.get("room_id", "default")
        else:
            persona_id = str(namespace)
            room_id = "default"

        safe_persona = str(persona_id).replace("/", "_").replace("\\", "_")
        safe_room = str(room_id).replace("/", "_").replace("\\", "_")
        ns_dir = self.root / safe_persona
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / f"{safe_room}.json"

    def _load_episodes(self, namespace: Any) -> list[Episode]:
        """Load episodes for a namespace.

        Args:
            namespace: MemoryNamespace or compatible object

        Returns:
            List of episodes for the namespace
        """
        cache_key = str(namespace)
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._namespace_path(namespace)
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            episodes = [Episode.from_dict(e) for e in data.get("episodes", [])]
            self._cache[cache_key] = episodes
            return episodes
        except Exception as e:
            logger.warning(f"Failed to load episodes for {namespace}: {e}")
            return []

    def _save_episodes(self, namespace: Any, episodes: list[Episode]) -> None:
        """Save episodes for a namespace.

        Args:
            namespace: MemoryNamespace or compatible object
            episodes: List of episodes to save
        """
        path = self._namespace_path(namespace)
        try:
            data = {"episodes": [e.to_dict() for e in episodes]}
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self._cache[str(namespace)] = episodes
        except Exception as e:
            logger.error(f"Failed to save episodes for {namespace}: {e}")
            raise

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text.

        Uses the embedding provider if available, otherwise falls back
        to a simple hash-based deterministic embedding.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        # Truncate if too long
        if len(text) > self.config.max_context_length:
            text = text[: self.config.max_context_length]

        if self.embedding_provider:
            try:
                return await self.embedding_provider.embed(text)
            except Exception as e:
                logger.warning(f"Embedding provider failed, using fallback: {e}")

        # Fallback: deterministic hash-based embedding
        return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> list[float]:
        """Generate deterministic embedding from text hash.

        Not semantically meaningful but consistent for testing and
        when no embedding provider is available.

        Args:
            text: Text to hash

        Returns:
            Normalized embedding vector
        """
        import numpy as np

        # Use hash to seed for determinism
        hash_val = int(hashlib.md5(text.lower().encode()).hexdigest(), 16)
        np.random.seed(hash_val % (2**32))

        # Generate normalized random vector
        vec = np.random.randn(self.config.embedding_dim).astype(np.float32)
        vec = vec / (np.linalg.norm(vec) + 1e-8)

        # Reset RNG
        np.random.seed(None)

        return vec.tolist()

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity in range [-1, 1]
        """
        import numpy as np

        a_vec = np.array(a, dtype=np.float32)
        b_vec = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(a_vec)
        norm_b = np.linalg.norm(b_vec)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a_vec, b_vec) / (norm_a * norm_b))

    async def record_trajectory(
        self,
        namespace: Any,
        context: str,
        actions: list[dict[str, Any]],
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> Episode:
        """Record a new trajectory episode.

        Args:
            namespace: MemoryNamespace or compatible object for isolation
            context: Situation/context description
            actions: Sequence of actions taken
            outcome: Result of the actions
            metadata: Optional additional metadata

        Returns:
            The created Episode

        Example:
            episode = await memory.record_trajectory(
                namespace=MemoryNamespace("agent_1", "room_1"),
                context="User asked to analyze data",
                actions=[{"tool": "read_csv", "args": {"path": "data.csv"}}],
                outcome="success: Analysis complete",
                metadata={"duration_ms": 1200, "tokens": 500},
            )
        """
        # Generate episode ID
        episode_id = hashlib.md5(
            f"{namespace}:{context}:{time.time()}".encode()
        ).hexdigest()[:16]

        # Generate embedding for context
        embedding = await self._generate_embedding(context)

        # Create episode
        episode = Episode(
            episode_id=episode_id,
            context=context[: self.config.max_context_length],
            actions=actions,
            outcome=outcome,
            timestamp=time.time(),
            metadata=metadata or {},
            embedding=embedding,
        )

        # Load existing episodes
        episodes = self._load_episodes(namespace)

        # Add new episode
        episodes.append(episode)

        # Enforce max episodes limit (keep most recent)
        if len(episodes) > self.config.max_episodes:
            episodes = episodes[-self.config.max_episodes :]

        # Save
        self._save_episodes(namespace, episodes)

        # Update stats
        self._stats["total_episodes"] += 1
        self._stats["storage_ops"] += 1

        logger.debug(f"Recorded episode {episode_id} for {namespace}")

        return episode

    async def search_similar(
        self,
        namespace: Any,
        query: str,
        top_k: int = 5,
        success_only: bool | None = None,
    ) -> list[tuple[Episode, float]]:
        """Search for similar episodes using vector similarity.

        Args:
            namespace: MemoryNamespace or compatible object
            query: Query text to find similar episodes
            top_k: Maximum number of results to return
            success_only: If True, only return successful episodes.
                         If None, uses config.enable_success_filtering

        Returns:
            List of (Episode, similarity_score) tuples, sorted by similarity

        Example:
            results = await memory.search_similar(
                namespace=MemoryNamespace("agent_1", "room_1"),
                query="analyze sales data",
                top_k=3,
            )
            for episode, score in results:
                print(f"Similar episode (score={score:.2f}): {episode.context}")
        """
        self._stats["total_searches"] += 1

        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Load episodes
        episodes = self._load_episodes(namespace)

        if not episodes:
            return []

        # Compute similarities
        scored_episodes: list[tuple[Episode, float]] = []
        for episode in episodes:
            if episode.embedding is None:
                continue

            # Filter by success if requested
            if success_only is True and not episode.is_success:
                continue
            if success_only is False and episode.is_success:
                continue

            # Check config setting for success filtering
            if (
                success_only is None
                and self.config.enable_success_filtering
                and not episode.is_success
            ):
                continue

            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, episode.embedding)

            # Filter by threshold
            if similarity >= self.config.similarity_threshold:
                scored_episodes.append((episode, similarity))

        # Sort by similarity (descending)
        scored_episodes.sort(key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Search for '{query[:50]}...' found {len(scored_episodes)} matches "
            f"in namespace {namespace}"
        )

        return scored_episodes[:top_k]

    async def get_episodes(
        self,
        namespace: Any,
        limit: int = 100,
        success_only: bool = False,
    ) -> list[Episode]:
        """Get recent episodes for a namespace.

        Args:
            namespace: MemoryNamespace or compatible object
            limit: Maximum number of episodes to return
            success_only: If True, only return successful episodes

        Returns:
            List of episodes, sorted by timestamp (most recent first)
        """
        episodes = self._load_episodes(namespace)

        if success_only:
            episodes = [e for e in episodes if e.is_success]

        # Sort by timestamp (descending)
        episodes.sort(key=lambda e: e.timestamp, reverse=True)

        return episodes[:limit]

    async def delete_episode(self, namespace: Any, episode_id: str) -> bool:
        """Delete a specific episode.

        Args:
            namespace: MemoryNamespace or compatible object
            episode_id: ID of episode to delete

        Returns:
            True if deleted, False if not found
        """
        episodes = self._load_episodes(namespace)
        original_count = len(episodes)

        episodes = [e for e in episodes if e.episode_id != episode_id]

        if len(episodes) < original_count:
            self._save_episodes(namespace, episodes)
            self._stats["storage_ops"] += 1
            return True

        return False

    async def clear_namespace(self, namespace: Any) -> int:
        """Clear all episodes for a namespace.

        Args:
            namespace: MemoryNamespace or compatible object

        Returns:
            Number of episodes cleared
        """
        episodes = self._load_episodes(namespace)
        count = len(episodes)

        if count > 0:
            self._save_episodes(namespace, [])
            self._stats["storage_ops"] += 1

        return count

    def get_stats(self) -> dict[str, Any]:
        """Get episodic memory statistics.

        Returns:
            Dictionary with usage statistics
        """
        return self._stats.copy()

    async def get_few_shot_examples(
        self,
        namespace: Any,
        query: str,
        top_k: int = 3,
        success_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Get few-shot examples for prompting.

        Retrieves similar successful episodes formatted for use in
        few-shot prompting.

        Args:
            namespace: MemoryNamespace or compatible object
            query: Query to find similar examples
            top_k: Number of examples to return
            success_only: Only include successful episodes

        Returns:
            List of example dictionaries with 'context', 'actions', 'outcome'

        Example:
            examples = await memory.get_few_shot_examples(
                namespace=MemoryNamespace("agent_1", "room_1"),
                query="summarize this",
                top_k=2,
            )
            # Use in prompt: f"Examples: {json.dumps(examples)}"
        """
        results = await self.search_similar(
            namespace, query, top_k=top_k, success_only=success_only
        )

        examples = []
        for episode, score in results:
            examples.append(
                {
                    "context": episode.context,
                    "actions": episode.actions,
                    "outcome": episode.outcome,
                    "similarity": round(score, 3),
                }
            )

        return examples

    async def shutdown(self) -> None:
        """Clean up resources and persist any cached data."""
        # Persist any in-memory cache
        for cache_key, episodes in self._cache.items():
            try:
                # Extract namespace info from cache key if possible
                # Otherwise episodes are already persisted on write
                pass
            except Exception as e:
                logger.warning(f"Error during shutdown for {cache_key}: {e}")

        self._cache.clear()
        logger.info("EpisodicMemory shutdown complete")
