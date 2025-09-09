import time
from functools import wraps


def ttl_cache(ttl_seconds: int = 8):
    def deco(fn):
        cache = {}

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            hit = cache.get(key)
            now = time.time()
            if hit and now - hit["ts"] < ttl_seconds:
                return hit["val"]
            val = fn(*args, **kwargs)
            cache[key] = {"val": val, "ts": now}
            return val

        return wrapper

    return deco

