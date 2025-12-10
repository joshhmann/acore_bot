"""LLM response caching service to reduce API calls."""
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class LLMCache:
    """Cache for LLM responses with TTL and LRU eviction."""

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        enabled: bool = True
    ):
        """Initialize LLM cache.

        Args:
            max_size: Maximum number of cached responses (LRU eviction)
            ttl_seconds: Time-to-live for cached entries (default: 1 hour)
            enabled: Whether caching is enabled
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

        # OrderedDict for LRU: {cache_key: (response, timestamp)}
        self.cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.ttl_expirations = 0

        logger.info(f"LLM Cache initialized (enabled={enabled}, max_size={max_size}, ttl={ttl_seconds}s)")

    def _generate_cache_key(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate deterministic cache key from request parameters.

        Args:
            messages: Conversation messages
            model: Model name
            temperature: Temperature parameter
            system_prompt: Optional system prompt
            **kwargs: Additional parameters to include in key

        Returns:
            SHA256 hash of serialized parameters
        """
        # Build cache key from all relevant parameters
        key_data = {
            "messages": messages,
            "model": model,
            "temperature": round(temperature, 2),  # Round to avoid float precision issues
            "system_prompt": system_prompt,
            **kwargs
        }

        # Serialize to JSON (sorted keys for determinism)
        key_json = json.dumps(key_data, sort_keys=True, ensure_ascii=True)

        # Hash for compact key
        return hashlib.sha256(key_json.encode()).hexdigest()

    def get(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """Get cached response if available and not expired.

        Args:
            messages: Conversation messages
            model: Model name
            temperature: Temperature parameter
            system_prompt: Optional system prompt
            **kwargs: Additional cache key parameters

        Returns:
            Cached response or None if not found/expired
        """
        if not self.enabled:
            return None

        cache_key = self._generate_cache_key(
            messages=messages,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            **kwargs
        )

        if cache_key not in self.cache:
            self.misses += 1
            return None

        response, timestamp = self.cache[cache_key]

        # Check if expired
        age = time.time() - timestamp
        if age > self.ttl_seconds:
            logger.debug(f"Cache entry expired (age: {age:.1f}s, TTL: {self.ttl_seconds}s)")
            del self.cache[cache_key]
            self.ttl_expirations += 1
            self.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(cache_key)

        self.hits += 1
        logger.debug(f"Cache HIT (age: {age:.1f}s, key: {cache_key[:16]}...)")

        return response

    def set(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        """Store response in cache.

        Args:
            messages: Conversation messages
            model: Model name
            temperature: Temperature parameter
            response: LLM response to cache
            system_prompt: Optional system prompt
            **kwargs: Additional cache key parameters
        """
        if not self.enabled:
            return

        cache_key = self._generate_cache_key(
            messages=messages,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            **kwargs
        )

        # Evict oldest entry if at capacity
        if len(self.cache) >= self.max_size and cache_key not in self.cache:
            oldest_key, _ = self.cache.popitem(last=False)
            self.evictions += 1
            logger.debug(f"Evicted oldest cache entry (LRU), key: {oldest_key[:16]}...")

        # Store with current timestamp
        self.cache[cache_key] = (response, time.time())
        logger.debug(f"Cache SET (key: {cache_key[:16]}..., size: {len(self.cache)}/{self.max_size})")

    def clear(self):
        """Clear all cached entries."""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cache cleared ({count} entries removed)")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "enabled": self.enabled,
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 1),
            "evictions": self.evictions,
            "ttl_expirations": self.ttl_expirations,
            "avg_saved_per_hit": "~2-10 seconds and API cost"
        }

    def __repr__(self) -> str:
        """String representation of cache stats."""
        stats = self.get_stats()
        return (
            f"LLMCache(size={stats['size']}/{stats['max_size']}, "
            f"hits={stats['hits']}, misses={stats['misses']}, "
            f"hit_rate={stats['hit_rate_percent']}%)"
        )
