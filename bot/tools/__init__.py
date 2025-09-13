"""Tool registry and handlers exposed to the LLM."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict
import logging

try:
    from .slum_queries import run_named_query, SLUM_QUERY_TOOL
except Exception:  # pragma: no cover
    run_named_query = None  # type: ignore
    SLUM_QUERY_TOOL = None  # type: ignore
from .time_tool import get_current_time
from ..cache import memoize

try:  # These functions may not be available in tests and will be patched.
    from ac_db import create_account as _create_account
    from ac_db import change_password as _change_password
except Exception:  # pragma: no cover - tests provide mocks
    _create_account = None  # type: ignore
    _change_password = None  # type: ignore

try:
    from ac_metrics import (
        get_realm_kpis as _get_realm_kpis,
        get_top_auctions as _get_top_auctions,
        get_gold_flow as _get_gold_flow,
    )
except Exception:  # pragma: no cover - tests provide mocks
    _get_realm_kpis = None  # type: ignore
    _get_top_auctions = None  # type: ignore
    _get_gold_flow = None  # type: ignore

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Tool handlers ---------------------------------------------------------

def register_account(username: str, password: str, email: str | None = None) -> dict:
    if not _create_account:
        raise RuntimeError("create_account unavailable")
    _create_account(username=username, password=password, email=email)
    return {"ok": True, "ts": _now()}


def change_password(username: str, old_password: str, new_password: str) -> dict:
    if not _change_password:
        raise RuntimeError("change_password unavailable")
    _change_password(username=username, old_password=old_password, new_password=new_password)
    return {"ok": True, "ts": _now()}


def realm_status(realm: str) -> dict:
    ttl = 30
    def fetch() -> dict:
        if not _get_realm_kpis:
            raise RuntimeError("get_realm_kpis unavailable")
        data = _get_realm_kpis(realm)
        if not isinstance(data, dict):
            data = {}
        data.update({"realm": realm, "ts": _now(), "ttl_s": ttl})
        return data
    return memoize(("realm_status", realm), ttl, fetch)


def auction_stats(
    realm: str,
    item_name: str | None = None,
    metric: str = "median",
    window_days: int = 7,
) -> dict:
    ttl = 30
    def fetch() -> dict:
        if metric == "gold_flow":
            if not _get_gold_flow:
                raise RuntimeError("get_gold_flow unavailable")
            rows = _get_gold_flow(realm, item_name=item_name, window_days=window_days)
        else:
            if not _get_top_auctions:
                raise RuntimeError("get_top_auctions unavailable")
            rows = _get_top_auctions(
                realm,
                item_name=item_name,
                metric=metric,
                window_days=window_days,
            )
        return {
            "realm": realm,
            "metric": metric,
            "window_days": window_days,
            "items": rows,
            "ts": _now(),
            "ttl_s": ttl,
        }
    key = ("auction_stats", realm, item_name, metric, window_days)
    return memoize(key, ttl, fetch)


def time_now() -> dict:
    return {"ts": _now()}


# --- Registry --------------------------------------------------------------

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "register_account": {
        "description": "Create a new game account",
        "schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "password": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["username", "password"],
        },
        "handler": lambda args: register_account(**args),
        "redact": ["password"],
    },
    "change_password": {
        "description": "Change an account password",
        "schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "old_password": {"type": "string"},
                "new_password": {"type": "string"},
            },
            "required": ["username", "old_password", "new_password"],
        },
        "handler": lambda args: change_password(**args),
        "redact": ["old_password", "new_password"],
    },
    "realm_status": {
        "description": "Current status for a realm",
        "schema": {
            "type": "object",
            "properties": {"realm": {"type": "string"}},
            "required": ["realm"],
        },
        "handler": lambda args: realm_status(**args),
        "redact": [],
    },
    "auction_stats": {
        "description": "Auction house statistics",
        "schema": {
            "type": "object",
            "properties": {
                "realm": {"type": "string"},
                "item_name": {"type": "string"},
                "metric": {
                    "type": "string",
                    "enum": ["median", "mean", "p90", "volume", "gold_flow"],
                },
                "window_days": {"type": "integer", "minimum": 1},
            },
            "required": ["realm"],
        },
        "handler": lambda args: auction_stats(**args),
        "redact": [],
    },
    "time_now": {
        "description": "Current UTC time",
        "schema": {"type": "object", "properties": {}},
        "handler": lambda args: time_now(),
        "redact": [],
    },
}


def tool_specs_for_llm() -> list[dict]:
    specs: list[dict] = []
    for name, meta in TOOL_REGISTRY.items():
        specs.append(
            {
                "type": "function",
                "name": name,
                "description": meta["description"],
                "parameters": meta["schema"],
            }
        )
    return specs


__all__ = ["run_named_query", "SLUM_QUERY_TOOL", "get_current_time",
    "TOOL_REGISTRY",
    "tool_specs_for_llm",
    "register_account",
    "change_password",
    "realm_status",
    "auction_stats",
    "time_now",
]
