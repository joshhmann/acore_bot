"""Tiny TTL cache for tool handlers."""
from __future__ import annotations

import time
from typing import Any, Callable, Hashable

_cache: dict[Hashable, tuple[float, Any]] = {}


def memoize(key: Hashable, ttl_s: int, fn: Callable[[], Any]) -> Any:
    now = time.time()
    entry = _cache.get(key)
    if entry and entry[0] > now:
        return entry[1]
    val = fn()
    _cache[key] = (now + ttl_s, val)
    return val
