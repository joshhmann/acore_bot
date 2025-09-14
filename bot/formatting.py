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
    if name == "realm_insights":
        pop = result.get("population") or {}
        cc = result.get("concurrency") or {}
        eco = result.get("economy") or {}
        auc = result.get("auctions") or {}
        stb = result.get("stability") or {}
        parts = []
        if pop:
            parts.append(
                f"Pop: A {pop.get('alliance',0)} ({pop.get('alliance_pct',0)}%) / H {pop.get('horde',0)} ({pop.get('horde_pct',0)}%)"
            )
        if cc:
            parts.append(
                f"Concurrency: cur {cc.get('current',0)}, p95 {cc.get('p95',0)}, peak {cc.get('peak',0)}"
            )
        if eco:
            parts.append(
                f"Economy: total {eco.get('total_gold','?')}g, per player {eco.get('per_capita_gold','?')}g"
            )
        if auc:
            parts.append(
                f"Auctions: {auc.get('active',0)} active, avg buyout {auc.get('avg_buyout_copper',0)}c"
            )
        if stb and stb.get("uptime_hours") is not None:
            parts.append(f"Uptime: {stb.get('uptime_hours')}h")
        base = " | ".join(parts) if parts else "No insights"
        return base + (f" · {_fmt_ts(ts)}" if ts else "")
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
