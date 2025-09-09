from __future__ import annotations
from typing import Dict, Optional, Union

from ac_metrics import kpi_profession_counts

# Mapping of profession names to their skill IDs
PROFESSION_IDS: Dict[str, int] = {
    "alchemy": 171,
    "herbalism": 182,
    "mining": 186,
    "blacksmithing": 164,
    "leatherworking": 165,
    "engineering": 202,
    "enchanting": 333,
    "tailoring": 197,
    "skinning": 393,
    "cooking": 185,
    "first aid": 129,
    "firstaid": 129,
    "fishing": 356,
    "jewelcrafting": 755,
    "inscription": 773,
}


def resolve_skill_id(name_or_id: Union[str, int]) -> Optional[int]:
    """Resolve a profession name or numeric ID to an integer skill ID.

    Args:
        name_or_id: Either the numeric ID or profession name.

    Returns:
        The corresponding skill ID, or None if it cannot be resolved.
    """
    try:
        return int(name_or_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pass
    if not isinstance(name_or_id, str):
        return None
    key = name_or_id.strip().lower()
    return PROFESSION_IDS.get(key)


def profession_counts(skill_id: int, min_value: int = 225) -> int:
    """Return count of characters with a profession at or above a value.

    This function passes through to the underlying metrics layer which
    performs the actual query. It defaults the minimum value to 225.
    """
    return kpi_profession_counts(skill_id=skill_id, min_value=min_value)
=======
"""Async queries for WowSlums MySQL with circuit breaker.

This module exposes a small helper to run read-only queries against the
``WowSlums`` database.  Connections are managed via an ``aiomysql`` pool whose
min/max sizes are configured through environment variables
``SLUM_DB_MIN_POOL`` and ``SLUM_DB_MAX_POOL``.  Queries are wrapped with
``asyncio.wait_for`` to enforce a short timeout and a basic circuit breaker is
used to avoid hammering the database when it is slow or down.

The goal of the circuit breaker is to fail fast after repeated problems and to
recover automatically after a cooldown period.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Iterable

log = logging.getLogger("acbot.slumdb")

# Pool and breaker state
_pool: Any | None = None
_fail_count = 0
_breaker_until = 0.0

# Configuration constants
QUERY_TIMEOUT = float(os.getenv("SLUM_QUERY_TIMEOUT", "3"))
FAIL_THRESHOLD = int(os.getenv("SLUM_QUERY_FAILS", "3"))
COOLDOWN_SECONDS = float(os.getenv("SLUM_QUERY_COOLDOWN", "30"))


class SlumQueryError(RuntimeError):
    """Raised when the Slums database cannot be queried."""


async def init_pool() -> Any:
    """Initialise and return a global ``aiomysql`` connection pool.

    The pool is created on first use.  ``SLUM_DB_MIN_POOL`` and
    ``SLUM_DB_MAX_POOL`` environment variables control the min and max pool
    sizes.  Pool creation and basic status are logged for observability.
    """

    global _pool
    if _pool is not None:
        return _pool

    # Import lazily so test environments do not require the dependency unless
    # the pool is actually created.
    import aiomysql

    minsize = int(os.getenv("SLUM_DB_MIN_POOL", "1"))
    maxsize = int(os.getenv("SLUM_DB_MAX_POOL", "5"))

    _pool = await aiomysql.create_pool(
        host=os.getenv("SLUM_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("SLUM_DB_PORT", "3306")),
        user=os.getenv("SLUM_DB_USER", ""),
        password=os.getenv("SLUM_DB_PASS", ""),
        db=os.getenv("SLUM_DB_NAME", ""),
        minsize=minsize,
        maxsize=maxsize,
        autocommit=True,
    )

    # Log basic pool status for monitoring
    try:
        log.info(
            "slum pool ready min=%s max=%s size=%s free=%s",
            minsize,
            maxsize,
            _pool.size,
            _pool.freesize,
        )
    except Exception:
        log.info("slum pool ready min=%s max=%s", minsize, maxsize)

    return _pool


def _breaker_open() -> bool:
    """Check and update breaker state."""

    global _breaker_until, _fail_count
    now = time.monotonic()
    if _breaker_until and now < _breaker_until:
        return True
    if _breaker_until and now >= _breaker_until:
        log.info("slum breaker reset")
        _breaker_until = 0.0
        _fail_count = 0
    return False


def _register_failure(exc: Exception) -> None:
    """Record a query failure and maybe trip the breaker."""

    global _fail_count, _breaker_until
    _fail_count += 1
    log.warning("slum query failure count=%s err=%s", _fail_count, exc)
    if _fail_count >= FAIL_THRESHOLD or isinstance(exc, asyncio.TimeoutError):
        _breaker_until = time.monotonic() + COOLDOWN_SECONDS
        log.error("slum breaker opened for %.0fs", COOLDOWN_SECONDS)


async def _run_query(sql: str, args: Iterable[Any] | None) -> list[dict[str, Any]]:
    """Execute the SQL using the global pool and return all rows."""

    pool = await init_pool()
    try:
        log.debug("pool status size=%s free=%s", pool.size, pool.freesize)
    except Exception:
        pass

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, args or ())
            return await cur.fetchall()


async def query(sql: str, args: Iterable[Any] | None = None) -> Any:
    """Run a query with timeout and circuit breaker protection."""

    global _fail_count

    if _breaker_open():
        raise SlumQueryError(
            "Slums database temporarily unavailable, please try again later."
        )

    try:
        rows = await asyncio.wait_for(_run_query(sql, args), timeout=QUERY_TIMEOUT)
    except Exception as exc:  # includes TimeoutError
        _register_failure(exc)
        raise SlumQueryError(
            "Slums database temporarily unavailable, please try again later."
        ) from exc

    # Success resets failure counter
    _fail_count = 0
    return rows


__all__ = ["init_pool", "query", "SlumQueryError"]

