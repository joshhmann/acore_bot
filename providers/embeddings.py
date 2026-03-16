from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    @property
    def embedding_dim(self) -> int: ...

    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(slots=True)
class EmbeddingCache:
    """Disk-persistent cache for embeddings."""

    cache_dir: str = field(default="data/embeddings_cache")
    _cache: dict[str, list[float]] = field(default_factory=dict, repr=False)
    _dirty: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize and load cache from disk."""
        os.makedirs(self.cache_dir, exist_ok=True)
        self._load_cache()

    def _cache_file(self) -> str:
        """Get cache file path."""
        return os.path.join(self.cache_dir, "embeddings.json")

    def _load_cache(self) -> None:
        """Load cache from disk."""
        cache_file = self._cache_file()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache = {k: v for k, v in data.items() if isinstance(v, list)}
                logger.debug("Loaded %d cached embeddings", len(self._cache))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load embedding cache: %s", e)
                self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        if not self._dirty:
            return
        cache_file = self._cache_file()
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, separators=(",", ":"))
            self._dirty = False
            logger.debug("Saved %d embeddings to cache", len(self._cache))
        except IOError as e:
            logger.warning("Failed to save embedding cache: %s", e)

    def get(self, text: str) -> list[float] | None:
        """Get cached embedding for text."""
        key = hashlib.sha256(text.encode()).hexdigest()[:32]
        return self._cache.get(key)

    def set(self, text: str, embedding: list[float]) -> None:
        """Cache embedding for text."""
        key = hashlib.sha256(text.encode()).hexdigest()[:32]
        self._cache[key] = embedding
        self._dirty = True

    def persist(self) -> None:
        """Persist cache to disk."""
        self._save_cache()

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._dirty = True
        self._save_cache()

    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)

    def __contains__(self, text: str) -> bool:
        """Check if text is cached."""
        key = hashlib.sha256(text.encode()).hexdigest()[:32]
        return key in self._cache


@dataclass(slots=True)
class FallbackEmbeddingProvider:
    """Hash-based fallback embedding provider for when others fail."""

    dim: int = 384
    _cache: EmbeddingCache | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize cache if not provided."""
        if self._cache is None:
            self._cache = EmbeddingCache()

    @property
    def embedding_dim(self) -> int:
        """Return embedding dimension."""
        return self.dim

    async def embed(self, text: str) -> list[float]:
        """
        Generate deterministic hash-based embedding.
        Uses multiple hash functions for better distribution.
        """
        if self._cache and text in self._cache:
            return self._cache.get(text)

        text_bytes = text.encode("utf-8")
        embedding: list[float] = []

        # Use multiple hash functions for better distribution
        hashes = [
            hashlib.sha256(text_bytes).digest(),
            hashlib.blake2b(text_bytes, digest_size=32).digest(),
            hashlib.sha3_256(text_bytes).digest(),
        ]

        # Combine hashes and normalize to [-1, 1]
        for i in range(self.dim):
            byte_val = hashes[i % len(hashes)][i % 32]
            val = (byte_val / 255.0) * 2 - 1
            embedding.append(float(val))

        # Normalize to unit sphere
        arr = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
            embedding = arr.tolist()

        if self._cache:
            self._cache.set(text, embedding)
            self._cache.persist()

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [await self.embed(text) for text in texts]


@dataclass(slots=True)
class OpenAIEmbeddingProvider:
    """OpenAI-compatible embedding provider."""

    api_key: str | None = None
    base_url: str | None = None
    model: str = "text-embedding-3-small"
    _cache: EmbeddingCache | None = field(default=None, repr=False)
    _client: Any = field(default=None, repr=False)
    _dim: int = field(default=1536, repr=False)

    def __post_init__(self) -> None:
        """Initialize cache and client."""
        if self._cache is None:
            self._cache = EmbeddingCache()

        # Set dimension based on model
        model_dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        self._dim = model_dims.get(self.model, 1536)

    @property
    def embedding_dim(self) -> int:
        """Return embedding dimension."""
        return self._dim

    def _get_client(self) -> Any:
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                api_key = self.api_key or os.getenv("OPENAI_API_KEY")
                base_url = self.base_url or os.getenv("OPENAI_BASE_URL")

                if not api_key:
                    raise ValueError("OpenAI API key required")

                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            except ImportError as e:
                raise ImportError("openai package required") from e
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API."""
        if self._cache and text in self._cache:
            return self._cache.get(text)

        client = self._get_client()
        response = await client.embeddings.create(model=self.model, input=text)
        embedding = response.data[0].embedding

        if self._cache:
            self._cache.set(text, embedding)
            self._cache.persist()

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        if not texts:
            return []

        # Check cache first
        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            if self._cache and text in self._cache:
                results[i] = self._cache.get(text)
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if not uncached_texts:
            return [r for r in results if r is not None]

        client = self._get_client()
        response = await client.embeddings.create(
            model=self.model, input=uncached_texts
        )
        embeddings = [d.embedding for d in response.data]

        # Update cache and results
        if self._cache:
            for idx, text, emb in zip(uncached_indices, uncached_texts, embeddings):
                self._cache.set(text, emb)
                results[idx] = emb
            self._cache.persist()
        else:
            for idx, emb in zip(uncached_indices, embeddings):
                results[idx] = emb

        return [r for r in results if r is not None]


@dataclass(slots=True)
class LocalEmbeddingProvider:
    """Local embedding provider using sentence-transformers."""

    model_name: str = "all-MiniLM-L6-v2"
    device: str | None = None
    _cache: EmbeddingCache | None = field(default=None, repr=False)
    _model: Any = field(default=None, repr=False)
    _dim: int = field(default=384, repr=False)
    _initialized: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize cache."""
        if self._cache is None:
            self._cache = EmbeddingCache()

    def _get_model(self) -> Any:
        """Lazy load the model."""
        if not self._initialized:
            try:
                from sentence_transformers import SentenceTransformer

                device = self.device or os.getenv("EMBEDDING_DEVICE", "cpu")
                logger.info(
                    "Loading embedding model: %s on %s", self.model_name, device
                )

                self._model = SentenceTransformer(self.model_name, device=device)
                self._dim = self._model.get_sentence_embedding_dimension()
                self._initialized = True
                logger.info("Loaded embedding model with dim=%d", self._dim)
            except ImportError as e:
                raise ImportError("sentence-transformers required") from e
        return self._model

    @property
    def embedding_dim(self) -> int:
        """Return embedding dimension."""
        if not self._initialized:
            # Try to get dim without loading model
            model_dims = {
                "all-MiniLM-L6-v2": 384,
                "all-mpnet-base-v2": 768,
                "all-distilroberta-v1": 768,
                "paraphrase-multilingual-MiniLM-L12-v2": 384,
            }
            return model_dims.get(self.model_name, 384)
        return self._dim

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using local model."""
        if self._cache and text in self._cache:
            return self._cache.get(text)

        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        result = embedding.tolist()

        if self._cache:
            self._cache.set(text, result)
            self._cache.persist()

        return result

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        if not texts:
            return []

        # Check cache first
        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            if self._cache and text in self._cache:
                results[i] = self._cache.get(text)
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if not uncached_texts:
            return [r for r in results if r is not None]

        model = self._get_model()
        embeddings = model.encode(uncached_texts, convert_to_numpy=True)
        embeddings_list = embeddings.tolist()

        # Update cache and results
        if self._cache:
            for idx, text, emb in zip(
                uncached_indices, uncached_texts, embeddings_list
            ):
                self._cache.set(text, emb)
                results[idx] = emb
            self._cache.persist()
        else:
            for idx, emb in zip(uncached_indices, embeddings_list):
                results[idx] = emb

        return [r for r in results if r is not None]


def get_provider(
    provider_type: str | None = None,
    cache_dir: str | None = None,
    **kwargs: Any,
) -> EmbeddingProvider:
    """
    Get appropriate embedding provider based on configuration.

    Args:
        provider_type: 'local', 'openai', 'fallback', or None (auto-detect)
        cache_dir: Directory for embedding cache
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured EmbeddingProvider instance

    Examples:
        >>> provider = get_provider("local")
        >>> provider = get_provider("openai", api_key="sk-...")
        >>> provider = get_provider()  # Auto-detect
    """
    provider_type = provider_type or os.getenv("EMBEDDING_PROVIDER", "auto")
    cache = EmbeddingCache(cache_dir=cache_dir) if cache_dir else EmbeddingCache()

    if provider_type == "auto":
        # Auto-detect: prefer local if available, fallback to hash-based
        try:
            import sentence_transformers  # noqa: F401

            provider_type = "local"
            logger.info("Auto-selected local embedding provider")
        except ImportError:
            logger.info("sentence-transformers not available, using fallback")
            provider_type = "fallback"

    if provider_type == "local":
        model = kwargs.get("model") or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        device = kwargs.get("device") or os.getenv("EMBEDDING_DEVICE")
        return LocalEmbeddingProvider(
            model_name=model,
            device=device,
            _cache=cache,
        )

    if provider_type == "openai":
        api_key = kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")
        base_url = kwargs.get("base_url") or os.getenv("OPENAI_BASE_URL")
        model = kwargs.get("model") or os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
            _cache=cache,
        )

    if provider_type == "fallback":
        dim = kwargs.get("dim") or int(os.getenv("EMBEDDING_DIM", "384"))
        return FallbackEmbeddingProvider(dim=dim, _cache=cache)

    raise ValueError(f"Unknown embedding provider: {provider_type}")
