import asyncio
import sys
import time
from types import SimpleNamespace

import pytest

import slum_queries as sq


def test_init_pool_uses_env(monkeypatch):
    calls = {}

    class FakePool:
        def __init__(self, **kw):
            self.minsize = kw["minsize"]
            self.maxsize = kw["maxsize"]
            self.size = self.minsize
            self.freesize = self.minsize

    async def fake_create_pool(**kw):
        calls.update(kw)
        return FakePool(**kw)

    monkeypatch.setenv("SLUM_DB_MIN_POOL", "2")
    monkeypatch.setenv("SLUM_DB_MAX_POOL", "7")
    monkeypatch.setitem(sys.modules, "aiomysql", SimpleNamespace(create_pool=fake_create_pool))

    sq._pool = None
    pool = asyncio.run(sq.init_pool())
    assert pool.minsize == 2 and pool.maxsize == 7
    assert calls["minsize"] == 2 and calls["maxsize"] == 7


def test_circuit_breaker_timeout(monkeypatch):
    async def slow_query(sql, args):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(sq, "_run_query", slow_query)
    monkeypatch.setattr(sq, "QUERY_TIMEOUT", 0.01, raising=False)
    monkeypatch.setattr(sq, "FAIL_THRESHOLD", 1, raising=False)
    monkeypatch.setattr(sq, "COOLDOWN_SECONDS", 0.05, raising=False)

    sq._fail_count = 0
    sq._breaker_until = 0.0

    with pytest.raises(sq.SlumQueryError):
        asyncio.run(sq.query("SELECT 1"))

    assert sq._breaker_open()

    # Second call should fail fast due to open breaker
    start = time.monotonic()
    with pytest.raises(sq.SlumQueryError):
        asyncio.run(sq.query("SELECT 1"))
    assert time.monotonic() - start < 0.02

    # After cooldown breaker should reset and query succeeds
    asyncio.run(asyncio.sleep(0.06))

    async def ok_query(sql, args):
        return [1]

    monkeypatch.setattr(sq, "_run_query", ok_query)
    res = asyncio.run(sq.query("SELECT 1"))
    assert res == [1]

