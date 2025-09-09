import time, json, logging
from contextlib import contextmanager
from typing import Any, Dict, Optional, Callable

log = logging.getLogger("acbot.tools")
_last_error: Optional[str] = None


def get_last_error() -> Optional[str]:
    """Return the last recorded tool error, if any."""
    return _last_error


def _emit(base: Dict[str, Any], t0: float, **extra: Any) -> None:
    """Emit a log entry combining base fields and extra data."""
    global _last_error
    payload: Dict[str, Any] = dict(base)
    payload["ms"] = int((time.time() - t0) * 1000)
    for k, v in extra.items():
        if v is not None:
            payload[k] = v
    if payload.get("error"):
        _last_error = str(payload["error"])
        try:
            log.error(json.dumps(payload))
        except Exception:
            pass
    else:
        try:
            log.info(json.dumps(payload))
        except Exception:
            pass


@contextmanager
def tool_context(name: str, *, params: Optional[Dict[str, Any]] = None,
                 guild_id: Optional[int] = None,
                 channel_id: Optional[int] = None,
                 user_id: Optional[int] = None) -> Callable[..., None]:
    """Context manager to time and log tool usage.

    Usage::
        with tool_context("tool", guild_id=123) as log:
            ... do work ...
            log(rows=5, cache_hit=True)
    """
    base: Dict[str, Any] = {"tool": name}
    if params:
        base["params"] = params
    if guild_id is not None:
        base["guild_id"] = guild_id
    if channel_id is not None:
        base["channel_id"] = channel_id
    if user_id is not None:
        base["user_id"] = user_id
    t0 = time.time()
    try:
        yield lambda **extra: _emit(base, t0, **extra)
    except Exception as e:
        _emit(base, t0, error=str(e), db_timeout="timeout" in str(e).lower())
        raise
