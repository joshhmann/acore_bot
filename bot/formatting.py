"""Render tool results into Discord-friendly strings."""
from __future__ import annotations

from typing import Any, Dict


def _fmt_ts(ts: str | None) -> str:
    return f"as of {ts}" if ts else ""


def render_tool_result(tr: Dict[str, Any]) -> str:
    name = tr.get("name")
    result = tr.get("result", {})
    ts = result.get("ts")
    if name == "realm_status":
        return (
            f"Realm — Online: {result.get('online')} | Uptime: {result.get('uptime_h')}h | "
            f"Players: {result.get('players')} · {_fmt_ts(ts)}"
        )
    if name == "auction_stats":
        header = (
            f"Top auctions on {result.get('realm')} — {result.get('metric')} over {result.get('window_days')}d:\n"
        )
        lines = []
        for row in result.get("items", [])[:5]:
            item = row.get("item") or row.get("name") or "item"
            val = row.get("value") or row.get("price") or row.get("metric")
            vol = row.get("volume") or row.get("count")
            lines.append(f"{item}: {val} ({vol}x)")
        return header + "\n".join(lines) + f"\n{_fmt_ts(ts)}"
    if name == "register_account":
        return "✅ Account created"
    if name == "change_password":
        return "🔒 Credentials updated"
    if name == "time_now":
        return f"Current time: {ts}" if ts else ""
    return str(result)
