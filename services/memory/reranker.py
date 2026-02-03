"""Cross-Encoder Re-ranker for improved document retrieval.

Uses sentence-transformers CrossEncoder models to re-rank initial
retrieval results based on query-document relevance.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-Encoder re-ranker using sentence-transformers.

    Re-ranks documents using a cross-encoder model that jointly
    encodes query and document for more accurate relevance scoring.

    Performance optimized with:
    - Lazy model loading
    - Batched inference
    - Result caching
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        max_batch_size: int = 32,
        cache_size: int = 1000,
    ):
        """Initialize the re-ranker.

        Args:
            model_name: HuggingFace model name for cross-encoder
            max_batch_size: Maximum batch size for inference
            cache_size: Maximum number of cached query-document scores
        """
        self.model_name = model_name
        self.max_batch_size = max_batch_size
        self.cache_size = cache_size

        self._model = None
        self._model_lock = asyncio.Lock()
        self._score_cache: Dict[str, Dict[str, float]] = {}
        self._cache_order: List[str] = []
        self._stats = {
            "rerank_calls": 0,
            "cache_hits": 0,
            "total_docs_reranked": 0,
            "avg_rerank_time_ms": 0,
        }

    async def initialize(self):
        """Initialize the cross-encoder model asynchronously."""
        async with self._model_lock:
            if self._model is not None:
                return

            try:
                from sentence_transformers import CrossEncoder

                logger.info(f"Loading cross-encoder model: {self.model_name}")
                loop = asyncio.get_event_loop()
                self._model = await loop.run_in_executor(
                    None, lambda: CrossEncoder(self.model_name)
                )
                logger.info("Cross-encoder model loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load cross-encoder model: {e}")
                logger.warning("Re-ranker will be disabled")
                self._model = None
                raise

    def _get_cache_key(self, query: str, documents: List[str]) -> str:
        """Generate a cache key for a query-document batch.

        Args:
            query: Search query
            documents: List of document contents

        Returns:
            Cache key string
        """
        import hashlib

        content = query + "||" + "|".join(documents[:5])
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached_scores(
        self,
        query: str,
        documents: List[str],
    ) -> Optional[List[float]]:
        """Get cached scores if available.

        Args:
            query: Search query
            documents: List of document contents

        Returns:
            Cached scores or None if not cached
        """
        cache_key = self._get_cache_key(query, documents)

        if cache_key in self._score_cache:
            self._stats["cache_hits"] += 1
            return list(self._score_cache[cache_key].values())

        return None

    def _cache_scores(
        self,
        query: str,
        documents: List[str],
        scores: List[float],
    ):
        """Cache scores for a query-document batch.

        Args:
            query: Search query
            documents: List of document contents
            scores: Computed scores
        """
        cache_key = self._get_cache_key(query, documents)

        self._score_cache[cache_key] = {str(i): s for i, s in enumerate(scores)}
        self._cache_order.append(cache_key)

        while len(self._cache_order) > self.cache_size:
            old_key = self._cache_order.pop(0)
            self._score_cache.pop(old_key, None)

    def _ensure_model_loaded(self):
        """Ensure the model is loaded, loading if necessary."""
        if self._model is None:
            raise RuntimeError(
                "Cross-encoder model not initialized. "
                "Call initialize() first or use ensure_initialized()."
            )

    async def ensure_initialized(self):
        """Ensure model is initialized, with lazy loading on first use."""
        if self._model is None:
            await self.initialize()

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int = 5,
        metadata: Optional[List[Dict]] = None,
    ) -> List[Tuple[int, float, Dict]]:
        """Re-rank documents using cross-encoder scores.

        Args:
            query: Search query
            documents: List of document contents to re-rank
            top_n: Number of top results to return
            metadata: Optional list of metadata for each document

        Returns:
            List of (doc_index, score, metadata) tuples sorted by score (descending)
        """
        if not documents:
            return []

        self._stats["rerank_calls"] += 1
        start_time = time.time()

        await self.ensure_initialized()

        cached_scores = self._get_cached_scores(query, documents)
        if cached_scores is not None:
            scores = cached_scores
        else:
            self._ensure_model_loaded()

            scores = await self._compute_scores_batch(query, documents)
            self._cache_scores(query, documents, scores)

        self._stats["total_docs_reranked"] += len(documents)

        elapsed_ms = (time.time() - start_time) * 1000
        self._stats["avg_rerank_time_ms"] = (
            self._stats["avg_rerank_time_ms"] * (self._stats["rerank_calls"] - 1)
            + elapsed_ms
        ) / self._stats["rerank_calls"]

        results = []
        for idx, score in enumerate(scores):
            doc_metadata = metadata[idx] if metadata else {}
            results.append((idx, float(score), doc_metadata))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]

    async def _compute_scores_batch(
        self,
        query: str,
        documents: List[str],
    ) -> List[float]:
        """Compute cross-encoder scores in batches.

        Args:
            query: Search query
            documents: List of document contents

        Returns:
            List of relevance scores
        """
        self._ensure_model_loaded()

        loop = asyncio.get_event_loop()

        pairs = [[query, doc] for doc in documents]
        scores = await loop.run_in_executor(
            None, lambda: self._model.predict(pairs, batch_size=self.max_batch_size)
        )

        return scores.tolist() if hasattr(scores, "tolist") else list(scores)

    async def rerank_with_metadata(
        self,
        query: str,
        results: List[Dict],
        top_n: int = 5,
    ) -> List[Dict]:
        """Re-rank results that include metadata.

        Args:
            query: Search query
            results: List of result dictionaries with 'content' key
            top_n: Number of top results to return

        Returns:
            Re-ranked result dictionaries with updated scores
        """
        if not results:
            return []

        documents = [r.get("content", "") for r in results]
        metadata = [r.get("metadata", {}) for r in results]

        reranked = await self.rerank(query, documents, top_n, metadata)

        output = []
        for idx, score, doc_metadata in reranked:
            original_result = results[idx].copy()
            original_result["rerank_score"] = score
            original_result["rerank_rank"] = len(output) + 1
            original_result["reranker_model"] = self.model_name
            original_result["metadata"].update(doc_metadata)
            output.append(original_result)

        return output

    def get_stats(self) -> Dict:
        """Get re-ranker statistics.

        Returns:
            Statistics dictionary
        """
        cache_hit_rate = 0
        if self._stats["rerank_calls"] > 0:
            cache_hit_rate = self._stats["cache_hits"] / self._stats["rerank_calls"]

        return {
            "rerank_calls": self._stats["rerank_calls"],
            "cache_hits": self._stats["cache_hits"],
            "cache_hit_rate": cache_hit_rate,
            "total_docs_reranked": self._stats["total_docs_reranked"],
            "avg_rerank_time_ms": round(self._stats["avg_rerank_time_ms"], 2),
            "model_name": self.model_name,
            "model_loaded": self._model is not None,
        }

    async def clear_cache(self):
        """Clear the score cache."""
        self._score_cache.clear()
        self._cache_order.clear()
        logger.debug("Re-ranker cache cleared")

    def shutdown(self):
        """Clean up resources."""
        self._model = None
        self._score_cache.clear()
        logger.info("Cross-encoder re-ranker shut down")


async def create_reranker(
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
) -> CrossEncoderReranker:
    """Factory function to create and initialize a re-ranker.

    Args:
        model_name: Cross-encoder model name

    Returns:
        Initialized CrossEncoderReranker instance
    """
    reranker = CrossEncoderReranker(model_name=model_name)
    await reranker.initialize()
    return reranker
