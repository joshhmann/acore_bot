import asyncio
from typing import Any, Callable, Dict
import ac_metrics as kpi


def _arena(top: int = 20):
    return kpi.kpi_arena_rating_distribution(limit_rows=top)

NAMED_QUERIES: Dict[str, Callable[..., Any]] = {
    "wowkpi": kpi.kpi_summary_text,
    "wowlevels": kpi.kpi_level_distribution,
    "wowgold_top": kpi.kpi_top_gold,
    "wowah_hot": kpi.kpi_auction_hot_items,
    "wowarena": _arena,
    "wowprof": kpi.kpi_profession_counts,
    "wowguilds": kpi.kpi_guild_activity,
}


async def run_named_query(name: str, **params) -> Any:
    func = NAMED_QUERIES.get(name)
    if not func:
        return []
    return await asyncio.to_thread(func, **params)
