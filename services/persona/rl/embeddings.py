"""State embedding encoder for RL agents.

Converts rich state features and message text into a dense embedding vector
using the cheap thinking service for text understanding.
"""

import hashlib
import logging
import time
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

from services.persona.rl.state_features import StateFeatures

logger = logging.getLogger(__name__)

DEFAULT_TARGET_DIM = 128
TEXT_EMBED_DIM = 64
STRUCTURED_FEATURES_DIM = 16
COMBINED_DIM = STRUCTURED_FEATURES_DIM + TEXT_EMBED_DIM  # 80


class StateEmbeddingEncoder:
    """Encodes StateFeatures and message text into a dense embedding vector.

    Combines structured state features with text embeddings from the thinking
    service to create a rich state representation for neural RL agents.

    Performance target: < 50ms p95 for encoding with caching
    """

    def __init__(
        self,
        thinking_service=None,
        target_dim: int = DEFAULT_TARGET_DIM,
        text_embed_dim: int = TEXT_EMBED_DIM,
        cache_size: int = 1000,
    ):
        """Initialize the state embedding encoder.

        Args:
            thinking_service: Service for text embeddings (cheap LLM)
            target_dim: Target dimension for output embeddings (default 128)
            text_embed_dim: Dimension for text embeddings (default 64)
            cache_size: Maximum number of cached embeddings
        """
        self.thinking_service = thinking_service
        self.target_dim = target_dim
        self.text_embed_dim = text_embed_dim
        self._cache: Dict[str, Tuple[np.ndarray, float]] = {}
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

        # Projection layer: combined features -> target dimension
        combined_dim = STRUCTURED_FEATURES_DIM + text_embed_dim
        self._projection = nn.Linear(combined_dim, target_dim)

        # Initialize weights with Xavier uniform
        nn.init.xavier_uniform_(self._projection.weight)
        nn.init.zeros_(self._projection.bias)

        logger.debug(
            f"StateEmbeddingEncoder initialized: target_dim={target_dim}, "
            f"text_embed_dim={text_embed_dim}, cache_size={cache_size}"
        )

    async def encode(
        self,
        state_features: StateFeatures,
        message_text: Optional[str] = None,
        use_cache: bool = True,
    ) -> np.ndarray:
        """Encode state features and optional message text into embedding vector.

        Args:
            state_features: Rich state features from StateFeatureExtractor
            message_text: Optional message text to embed
            use_cache: Whether to use caching (default True)

        Returns:
            Normalized embedding vector of shape (target_dim,)

        Performance: < 50ms p95 with caching enabled
        """
        start_time = time.perf_counter()

        # Generate cache key
        cache_key = self._generate_cache_key(state_features, message_text)

        # Check cache
        if use_cache and cache_key in self._cache:
            embedding, _ = self._cache[cache_key]
            self._cache_hits += 1
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Cache hit: encoding took {elapsed_ms:.2f}ms")
            return embedding

        self._cache_misses += 1

        # Get structured features vector (16 dims)
        structured_vector = np.array(
            state_features.to_vector(include_one_hot=False), dtype=np.float32
        )

        # Get text embedding (64 dims) if message provided
        if message_text and message_text.strip():
            text_embedding = await self._embed_text(message_text)
        else:
            text_embedding = np.zeros(self.text_embed_dim, dtype=np.float32)

        # Combine structured + text features
        combined = np.concatenate([structured_vector, text_embedding])

        # Project to target dimension
        embedding = self._project(combined)

        # L2 normalize (handle zero vector by adding small noise)
        if np.allclose(embedding, 0):
            embedding = np.random.randn(self.target_dim).astype(np.float32)
        embedding = self._normalize(embedding)

        # Update cache
        if use_cache:
            self._update_cache(cache_key, embedding)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(f"Cache miss: encoding took {elapsed_ms:.2f}ms")

        return embedding

    async def _embed_text(self, text: str) -> np.ndarray:
        """Get text embedding using thinking service.

        Uses a cheap/fast LLM to generate a dense representation of the text.
        Falls back to simple hashing if no thinking service available.

        Args:
            text: Text to embed

        Returns:
            Embedding vector of shape (text_embed_dim,)
        """
        if not text or not text.strip():
            return np.zeros(self.text_embed_dim, dtype=np.float32)

        # If thinking service available, use it for semantic embedding
        if self.thinking_service:
            try:
                # Truncate text if too long (thinking model has limited context)
                max_chars = 500
                truncated = text[:max_chars] if len(text) > max_chars else text

                # Use quick_generate to get a compact representation
                prompt = (
                    f"Summarize this message in 5 key aspects as numbers "
                    f"between -1 and 1, separated by commas. "
                    f"Format: aspect1,aspect2,aspect3,aspect4,aspect5\n\n"
                    f"Message: {truncated}\n\n"
                    f"Response (5 numbers only):"
                )

                response = await self.thinking_service.quick_generate(
                    prompt, max_tokens=50
                )

                # Parse the response into a 64-dim embedding
                embedding = self._parse_embedding_response(response)
                return embedding

            except Exception as e:
                logger.warning(f"Text embedding failed, using fallback: {e}")

        # Fallback: hash-based embedding (deterministic but not semantic)
        return self._fallback_text_embedding(text)

    def _parse_embedding_response(self, response: str) -> np.ndarray:
        """Parse LLM response into embedding vector.

        Extracts numbers from response and expands to target dimension.

        Args:
            response: LLM response with comma-separated numbers

        Returns:
            Embedding vector of shape (text_embed_dim,)
        """
        import re

        # Extract numbers from response
        numbers = re.findall(r"-?\d+\.?\d*", response)
        values = []

        for num_str in numbers[:10]:  # Take up to 10 numbers
            try:
                val = float(num_str)
                # Clamp to [-1, 1]
                val = max(-1.0, min(1.0, val))
                values.append(val)
            except ValueError:
                continue

        # If we got fewer than expected, pad with zeros
        if len(values) < 5:
            values.extend([0.0] * (5 - len(values)))

        # Expand 5 values to 64 dims using repetition and noise
        embedding = np.zeros(self.text_embed_dim, dtype=np.float32)
        for i in range(self.text_embed_dim):
            source_idx = i % len(values)
            embedding[i] = values[source_idx]

        return embedding

    def _fallback_text_embedding(self, text: str) -> np.ndarray:
        """Generate deterministic embedding from text hash.

        Used when thinking service is unavailable. Not semantic but consistent.

        Args:
            text: Text to hash

        Returns:
            Embedding vector of shape (text_embed_dim,)
        """
        # Use hash to seed RNG for deterministic output
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        np.random.seed(hash_val % (2**32))

        # Generate normalized random vector
        embedding = np.random.randn(self.text_embed_dim).astype(np.float32)
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

        # Reset RNG
        np.random.seed(None)

        return embedding

    def _project(self, vector: np.ndarray) -> np.ndarray:
        """Project vector to target dimension using learned projection.

        Args:
            vector: Input vector (combined structured + text features)

        Returns:
            Projected vector of shape (target_dim,)
        """
        # Convert to tensor
        tensor = torch.from_numpy(vector).float().unsqueeze(0)

        # Apply projection
        with torch.no_grad():
            projected = self._projection(tensor)

        # Convert back to numpy
        return projected.squeeze(0).numpy()

    def _normalize(self, vector: np.ndarray) -> np.ndarray:
        """L2 normalize vector to unit length.

        Args:
            vector: Input vector

        Returns:
            Normalized vector with L2 norm = 1.0
        """
        norm = np.linalg.norm(vector)
        if norm > 0:
            return vector / norm
        return vector

    def _generate_cache_key(
        self, state_features: StateFeatures, message_text: Optional[str]
    ) -> str:
        """Generate cache key from state features and message.

        Args:
            state_features: State features
            message_text: Optional message text

        Returns:
            Cache key string
        """
        # Use feature vector + message hash as key
        feature_str = ",".join(f"{v:.4f}" for v in state_features.to_vector())
        message_hash = (
            hashlib.md5(message_text.encode()).hexdigest()[:16] if message_text else ""
        )
        return f"{feature_str}|{message_hash}"

    def _update_cache(self, key: str, embedding: np.ndarray) -> None:
        """Update cache with new embedding.

        Implements simple LRU eviction when cache is full.

        Args:
            key: Cache key
            embedding: Embedding vector to cache
        """
        # Evict oldest if cache is full
        if len(self._cache) >= self._cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = (embedding, time.time())

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache hits, misses, and size
        """
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._cache),
            "hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
        }

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.debug("Embedding cache cleared")
