import re
from typing import Tuple, Dict


Intent = Tuple[str, Dict[str, int | str]]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def classify(text: str) -> Intent | None:
    s = _norm(text)
    if not s:
        return None

    # Online population
    if any(k in s for k in ["players online", "how many online", "population", "online now", "active player count"]):
        return ("online_count", {})

    # Totals
    if any(k in s for k in ["how many characters", "characters total", "total characters"]):
        return ("total_characters", {})
    if any(k in s for k in ["how many accounts", "accounts total", "total accounts"]):
        return ("total_accounts", {})

    # Auctions
    if any(k in s for k in ["how many auctions", "auctions total", "auction count"]):
        return ("auction_count", {})

    # Rates
    if any(k in s for k in ["xp rate", "xp rates", "rates", "drop rate", "honor rate", "reputation rate", "profession rate"]):
        return ("server_rates", {})

    # Gold per hour (we don't track)
    if any(k in s for k in ["gold per hour", "average gold per hour", "avg gold/hour", "gph"]):
        return ("gold_per_hour", {})

    # Bots (not exposed)
    if "how many bots" in s or "bots online" in s:
        return ("bots_count", {})

    # Simple parameterized intents (optional future use)
    m = re.search(r"top\s+(\d+)\s+gold", s)
    if m:
        try:
            n = int(m.group(1))
            return ("gold_top", {"limit": n})
        except Exception:
            pass

    return None

