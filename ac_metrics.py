import os
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

# --- PyMySQL import with safe fallback (for test environments) ---
try:
    import pymysql  # type: ignore
except Exception:  # pragma: no cover - fallback when pymysql is missing
    class _DummyPyMysql:
        class cursors:
            DictCursor = dict

        @staticmethod
        def connect(*args, **kwargs):  # type: ignore[empty-body]
            raise RuntimeError("pymysql not installed")

    pymysql = _DummyPyMysql()  # type: ignore

from utils.formatters import copper_to_gsc

# --- Optional formatter imports (provide fallbacks if module is absent) ---
try:
    from utils.formatter import format_gold, wrap_response
except Exception:
    def format_gold(copper: int) -> str:
        # Very small fallback; replace if you have kpi.copper_to_gold_s
        try:
            from ac_metrics import copper_to_gold_s  # lazy import to avoid cycles
            return copper_to_gold_s(int(copper))
        except Exception:
            g, rem = divmod(int(copper), 10000)
            s, c = divmod(rem, 100)
            return f"{g}g {s}s {c}c"

    def wrap_response(title: str, content: str) -> str:
        return f"**{title}**\n{content}"


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "")
DB_PASS = os.getenv("DB_PASS", "")
DB_AUTH = os.getenv("DB_AUTH_DB", os.getenv("DB_AUTH", "auth"))
DB_CHAR = os.getenv("DB_CHAR_DB", os.getenv("DB_CHAR", "characters"))
DB_WORLD = os.getenv("DB_WORLD_DB", os.getenv("DB_WORLD", "world"))

TTL_HOT = int(os.getenv("METRICS_TTL_SECONDS", "8"))

DICT = pymysql.cursors.DictCursor if pymysql else None
_cache: Dict[Any, Dict[str, Any]] = {}
# Track whether the last cache access was a hit for external logging.
last_cache_hit: bool = False

MAX_LEVEL_ROWS = 80
MAX_ARENA_ROWS = 100

# Insights configuration (lightweight, in-memory)
INSIGHTS_ENABLED = os.getenv("INSIGHTS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
INSIGHTS_SNAPSHOT_SEC = int(os.getenv("METRICS_SNAPSHOT_SEC", "60"))
INSIGHTS_WINDOW_SEC = int(os.getenv("INSIGHTS_WINDOW_SEC", str(24 * 3600)))

# Provider selection
METRICS_PROVIDER = os.getenv("METRICS_PROVIDER", "db").lower()  # db | acore_api
_api_client = None
if METRICS_PROVIDER == "acore_api":
    try:
        from acore_api_client import AcoreApiClient  # type: ignore

        _api_client = AcoreApiClient()
    except Exception:
        _api_client = None


def _cache_get(key):
    global last_cache_hit
    hit = _cache.get(key)
    if not hit:
        last_cache_hit = False
        return None
    if time.time() - hit["ts"] > hit["ttl"]:
        _cache.pop(key, None)
        last_cache_hit = False
        return None
    last_cache_hit = True
    return hit["val"]


def _cache_set(key, val, ttl=TTL_HOT):
    global last_cache_hit
    _cache[key] = {"val": val, "ts": time.time(), "ttl": ttl}
    last_cache_hit = False


def _now() -> float:
    return time.time()


def _cache_list(key: str) -> list:
    item = _cache.get(key)
    if item and isinstance(item.get("val"), list):
        return item["val"]
    lst: list = []
    _cache_set(key, lst, ttl=INSIGHTS_WINDOW_SEC * 2)
    return lst


@contextmanager
def conn(dbname: str):
    if not pymysql:  # pragma: no cover - protective guard
        raise RuntimeError("pymysql is required for DB connections")
    cn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=dbname,
        autocommit=True,
        cursorclass=DICT,
        charset="utf8mb4",
    )
    try:
        yield cn
    finally:
        cn.close()


def _has_table(dbname: str, table: str) -> bool:
    key = f"has:{dbname}:{table}"
    memo = _cache_get(key)
    if memo is not None:
        return memo
    q = (
        "SELECT COUNT(*) AS n FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name=%s"
    )
    with conn("information_schema") as c, c.cursor() as cur:
        cur.execute(q, (dbname, table))
        ok = cur.fetchone()["n"] > 0
    _cache_set(key, ok, ttl=60)
    return ok


def copper_to_gold_s(copper: int) -> str:
    """Backwards-compatible helper using :func:`format_gold`."""
    return format_gold(copper)


def kpi_players_online() -> int:
    key = "kpi:online"
    memo = _cache_get(key)
    if memo is not None:
        return memo
    if _has_table(DB_CHAR, "character_online"):
        q = "SELECT COUNT(*) AS n FROM character_online"
        with conn(DB_CHAR) as c, c.cursor() as cur:
            cur.execute(q)
            n = int(cur.fetchone()["n"])
    else:
        q = "SELECT COUNT(*) AS n FROM characters WHERE online = 1"
        with conn(DB_CHAR) as c, c.cursor() as cur:
            cur.execute(q)
            n = int(cur.fetchone()["n"])
    _cache_set(key, n)
    return n


# ---- Insights helpers ----
_RACE_TO_FACTION = {
    1: "alliance",  # Human
    3: "alliance",  # Dwarf
    4: "alliance",  # Night Elf
    7: "alliance",  # Gnome
    11: "alliance",  # Draenei
    2: "horde",    # Orc
    5: "horde",    # Undead
    6: "horde",    # Tauren
    8: "horde",    # Troll
    10: "horde",   # Blood Elf
}


def _record_online_sample() -> None:
    """Append a timestamped online sample, pruning to 24h window."""
    key = "samples:online"
    lst: list[Tuple[float, int]] = _cache_list(key)  # type: ignore[assignment]
    now = _now()
    # Only sample if last sample is older than configured interval
    if lst and (now - lst[-1][0] < INSIGHTS_SNAPSHOT_SEC):
        return
    try:
        n = _online_now()
    except Exception:
        return
    lst.append((now, int(n)))
    # prune
    cutoff = now - INSIGHTS_WINDOW_SEC
    while lst and lst[0][0] < cutoff:
        lst.pop(0)


def insights_population_online() -> Dict[str, Any]:
    """Faction split among currently online characters.

    Returns: { total, alliance, horde, unknown, alliance_pct, horde_pct }
    """
    q = (
        "SELECT race, COUNT(*) AS n FROM characters WHERE online = 1 GROUP BY race"
    )
    alliance = horde = unknown = 0
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q)
        for row in cur.fetchall():
            race = int(row.get("race", 0) or 0)
            n = int(row.get("n", 0) or 0)
            side = _RACE_TO_FACTION.get(race, "unknown")
            if side == "alliance":
                alliance += n
            elif side == "horde":
                horde += n
            else:
                unknown += n
    total = alliance + horde + unknown
    ap = round((alliance / total * 100) if total else 0, 1)
    hp = round((horde / total * 100) if total else 0, 1)
    return {
        "total": total,
        "alliance": alliance,
        "horde": horde,
        "unknown": unknown,
        "alliance_pct": ap,
        "horde_pct": hp,
    }


def insights_economy() -> Dict[str, Any]:
    """Approximate gold in circulation from characters.money."""
    q_sum = "SELECT SUM(money) AS total_copper FROM characters"
    q_count = "SELECT COUNT(*) AS n FROM characters"
    total_copper = 0
    total_chars = 0
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q_sum)
        total_copper = int(cur.fetchone().get("total_copper") or 0)
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q_count)
        total_chars = int(cur.fetchone().get("n") or 0)
    per_capita = int(total_copper / max(total_chars, 1))
    return {
        "total_copper": total_copper,
        "total_gold": round(total_copper / 10000, 1),
        "per_capita_copper": per_capita,
        "per_capita_gold": round(per_capita / 10000, 2),
        "population": total_chars,
    }


def insights_auctions() -> Dict[str, Any]:
    """Auction summary: total active auctions and average buyout."""
    q_count = "SELECT COUNT(*) AS n FROM auctionhouse"
    q_avg = "SELECT AVG(buyoutprice) AS avg_buyout FROM auctionhouse WHERE buyoutprice > 0"
    n = 0
    avg_buyout = 0
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q_count)
        n = int(cur.fetchone().get("n") or 0)
    with conn(DB_CHAR) as c, c.cursor() as cur:
        try:
            cur.execute(q_avg)
            avg_buyout = int(cur.fetchone().get("avg_buyout") or 0)
        except Exception:
            avg_buyout = 0
    return {"active": n, "avg_buyout_copper": avg_buyout}


def insights_stability() -> Dict[str, Any]:
    """Realm uptime and last restart time from auth.uptime."""
    q = "SELECT starttime, uptime FROM uptime ORDER BY starttime DESC LIMIT 1"
    start_ts = None
    uptime_sec = None
    try:
        with conn(DB_AUTH) as c, c.cursor() as cur:
            cur.execute(q)
            row = cur.fetchone() or {}
            start_ts = int(row.get("starttime") or 0)
            uptime_sec = int(row.get("uptime") or 0)
    except Exception:
        pass
    return {
        "start_time": start_ts,
        "uptime_sec": uptime_sec,
        "uptime_hours": round((uptime_sec or 0) / 3600, 2) if uptime_sec else None,
    }


def insights_concurrency() -> Dict[str, Any]:
    """Current online and 24h p95/peak from in-process snapshots."""
    _record_online_sample()
    lst: list[Tuple[float, int]] = _cache_list("samples:online")  # type: ignore[assignment]
    now = _now()
    cutoff = now - INSIGHTS_WINDOW_SEC
    samples = [n for (ts, n) in lst if ts >= cutoff]
    samples.sort()
    total = len(samples)
    peak = max(samples) if samples else 0
    # Find peak time
    peak_time = None
    if lst:
        try:
            pt = max((p for p in lst if p[0] >= cutoff), key=lambda x: x[1])
            peak_time = int(pt[0])
        except Exception:
            peak_time = None
    def pctile(p: float) -> int:
        if not samples:
            return 0
        k = int(round((p / 100.0) * (len(samples) - 1)))
        return int(samples[max(0, min(k, len(samples) - 1))])
    return {
        "current": _online_now(),
        "count": total,
        "p95": pctile(95),
        "peak": peak,
        "peak_time": peak_time,
        # Downsampled series for charting (max 100 points)
        "series": _downsample_series([n for (ts, n) in lst if ts >= cutoff], 100),
    }


def _downsample_series(vals: List[int], max_points: int) -> List[int]:
    if len(vals) <= max_points:
        return [int(v) for v in vals]
    step = len(vals) / max_points
    out: List[int] = []
    i = 0.0
    while int(i) < len(vals) and len(out) < max_points:
        out.append(int(vals[int(i)]))
        i += step
    return out


def get_online_samples() -> List[Tuple[int, int]]:
    """Expose recent (ts, value) samples for charting."""
    _record_online_sample()
    lst: list[Tuple[float, int]] = _cache_list("samples:online")  # type: ignore[assignment]
    cutoff = _now() - INSIGHTS_WINDOW_SEC
    return [(int(ts), int(n)) for (ts, n) in lst if ts >= cutoff]


def get_insights() -> Dict[str, Any]:
    """Aggregate high-level insights. Safe, fast queries only.

    This function does not raise; it returns best-effort fields.
    """
    out: Dict[str, Any] = {"ok": True}
    if METRICS_PROVIDER == "acore_api" and _api_client and _api_client.enabled:
        # API-backed insights with same output shape
        try:
            pop = _api_client.get_population()
            out["population"] = {
                "total": int(pop.get("alliance", 0)) + int(pop.get("horde", 0)),
                "alliance": int(pop.get("alliance", 0)),
                "horde": int(pop.get("horde", 0)),
                "unknown": 0,
                "alliance_pct": 0,
                "horde_pct": 0,
            }
            t = max(1, out["population"]["total"])
            out["population"]["alliance_pct"] = round(out["population"]["alliance"] / t * 100, 1)
            out["population"]["horde_pct"] = round(out["population"]["horde"] / t * 100, 1)
        except Exception as e:
            out["population_error"] = str(e)
        try:
            # Snapshot concurrency still works, using API online
            out["concurrency"] = insights_concurrency()
        except Exception as e:
            out["concurrency_error"] = str(e)
        try:
            out["economy"] = {"total_copper": 0, "total_gold": 0, "per_capita_copper": 0, "per_capita_gold": 0, "population": out.get("population", {}).get("total", 0)}
        except Exception as e:
            out["economy_error"] = str(e)
        try:
            out["auctions"] = _api_client.get_auctions()
        except Exception as e:
            out["auctions_error"] = str(e)
        try:
            stb = _api_client.get_uptime()
            out["stability"] = {
                "start_time": stb.get("start_time"),
                "uptime_sec": stb.get("uptime_sec"),
                "uptime_hours": round((stb.get("uptime_sec") or 0) / 3600, 2) if stb.get("uptime_sec") else None,
            }
        except Exception as e:
            out["stability_error"] = str(e)
        return out

    # Default DB-backed insights
    try:
        out["population"] = insights_population_online()
    except Exception as e:
        out["population_error"] = str(e)
    try:
        out["concurrency"] = insights_concurrency()
    except Exception as e:
        out["concurrency_error"] = str(e)
    try:
        out["economy"] = insights_economy()
    except Exception as e:
        out["economy_error"] = str(e)
    try:
        out["auctions"] = insights_auctions()
    except Exception as e:
        out["auctions_error"] = str(e)
    try:
        out["stability"] = insights_stability()
    except Exception as e:
        out["stability_error"] = str(e)
    return out


def _online_now() -> int:
    if METRICS_PROVIDER == "acore_api" and _api_client and _api_client.enabled:
        try:
            return int(_api_client.get_online())
        except Exception:
            return 0
    return kpi_players_online()


def kpi_totals() -> Dict[str, int]:
    key = "kpi:totals"
    memo = _cache_get(key)
    if memo is not None:
        return memo
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM characters")
        total_chars = int(cur.fetchone()["n"])
    with conn(DB_AUTH) as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM account")
        total_accounts = int(cur.fetchone()["n"])
    out = {"total_chars": total_chars, "total_accounts": total_accounts}
    _cache_set(key, out, ttl=30)
    return out


def kpi_level_distribution() -> List[Dict[str, int]]:
    key = "kpi:levels"
    memo = _cache_get(key)
    if memo is not None:
        return memo
    q = (
        "SELECT level, COUNT(*) AS n FROM characters "
        "GROUP BY level ORDER BY level LIMIT %s"
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q, (MAX_LEVEL_ROWS,))
        rows = cur.fetchall()
    _cache_set(key, rows)
    return rows


def kpi_top_gold(limit: int = 10) -> List[Dict[str, Any]]:
    q = (
        "SELECT name, level, money FROM characters "
        "ORDER BY money DESC LIMIT %s"
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q, (limit,))
        return cur.fetchall()


def kpi_guild_activity(days: int = 14, limit: int = 10) -> List[Dict[str, Any]]:
    q = (
        """
    SELECT g.name AS guild, COUNT(*) AS active_members
    FROM guild_member gm
    JOIN characters c ON c.guid = gm.guid
    JOIN guild g ON g.guildid = gm.guildid
    WHERE FROM_UNIXTIME(c.logout_time) >= NOW() - INTERVAL %s DAY
    GROUP BY g.name
    ORDER BY active_members DESC
    LIMIT %s
    """
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q, (days, limit))
        return cur.fetchall()


def active_guilds(window_secs: int, limit: int = 10) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]] | None]:
    """Guild member counts for characters active within ``window_secs``.

    Returns a tuple of ``(rows, previous_rows)`` where ``previous_rows`` is the
    cached result from the last call with the same parameters, if available.
    """
    key = f"active_guilds:{window_secs}:{limit}"
    prev = _cache_get(key)
    q = (
        """
    SELECT g.name AS guild, COUNT(*) AS active_members
    FROM guild_member gm
    JOIN characters c ON c.guid = gm.guid
    JOIN guild g ON g.guildid = gm.guildid
    WHERE c.logout_time >= UNIX_TIMESTAMP() - %s
    GROUP BY g.name
    ORDER BY active_members DESC
    LIMIT %s
    """
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q, (int(window_secs), int(limit)))
        rows = cur.fetchall()
    _cache_set(key, rows)
    return rows, prev


def kpi_auction_hot_items(limit: int = 10) -> List[Dict[str, Any]]:
    """Top auction items with summary stats and 24h delta.

    Returns aggregated listings, total and average buyout/bid, unique sellers,
    and the delta in listings versus a cached 24h snapshot. Item names are
    joined from the world database when available.
    """

    cache_key = f"kpi:ah_hot:{limit}"
    memo = _cache_get(cache_key)
    if memo is not None:
        return memo

    q_join = f"""
    SELECT a.item_template,
           COUNT(*) AS listings,
           SUM(a.buyoutprice) AS total_buyout,
           SUM(a.startbid)  AS total_bid,
           AVG(a.buyoutprice) AS avg_buyout,
           COUNT(DISTINCT a.owner) AS sellers,
           COALESCE(MIN(wt.name), CONCAT('Template ', a.item_template)) AS name
    FROM auctionhouse a
    LEFT JOIN {DB_WORLD}.item_template wt ON wt.entry = a.item_template
    GROUP BY a.item_template
    ORDER BY listings DESC
    LIMIT %s
    """

    try:
        with conn(DB_CHAR) as c, c.cursor() as cur:
            cur.execute(q_join, (limit,))
            rows = cur.fetchall()
    except Exception:
        q_fallback = """
        SELECT a.item_template,
               COUNT(*) AS listings,
               SUM(a.buyoutprice) AS total_buyout,
               SUM(a.startbid)  AS total_bid,
               AVG(a.buyoutprice) AS avg_buyout,
               COUNT(DISTINCT a.owner) AS sellers
        FROM auctionhouse a
        GROUP BY a.item_template
        ORDER BY listings DESC
        LIMIT %s
        """
        with conn(DB_CHAR) as c, c.cursor() as cur:
            cur.execute(q_fallback, (limit,))
            rows = cur.fetchall()
        for r in rows:
            r["name"] = f"Template {r['item_template']}"

    snap = _cache.get("ah_hot_snapshot")
    snap_data: Dict[int, int] = {}
    if snap and time.time() - snap["ts"] <= 86400:
        snap_data = snap["val"]

    for r in rows:
        prev = int(snap_data.get(r["item_template"], 0))
        r["delta_24h"] = int(r["listings"]) - prev

    if not snap or time.time() - snap["ts"] > 86400:
        _cache_set(
            "ah_hot_snapshot",
            {r["item_template"]: int(r["listings"]) for r in rows},
            ttl=86400 * 2,
        )

    _cache_set(cache_key, rows)
    return rows


def kpi_auction_count() -> int:
    """Total number of rows in auctionhouse (active auctions)."""
    q = "SELECT COUNT(*) AS n FROM auctionhouse"
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q)
        row = cur.fetchone()
        try:
            return int(row["n"]) if row is not None else 0
        except Exception:
            return 0


def kpi_arena_rating_distribution(limit_rows: Optional[int] = None) -> List[Dict[str, Any]]:
    limit = int(limit_rows) if limit_rows else MAX_ARENA_ROWS
    if limit > MAX_ARENA_ROWS:
        limit = MAX_ARENA_ROWS
    q = (
        "SELECT rating, COUNT(*) AS teams FROM arena_team "
        "GROUP BY rating ORDER BY rating DESC LIMIT %s"
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q, (limit,))
        rows = cur.fetchall()
    return rows


def kpi_arena_distribution(limit_rows: Optional[int] = None) -> List[Dict[str, Any]]:
    """Arena team counts per rating and bracket."""
    q = (
        """
    SELECT type AS bracket, rating, COUNT(*) AS teams
    FROM arena_team
    GROUP BY type, rating
    ORDER BY rating DESC
    """
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q)
        rows = cur.fetchall()
    return rows[:limit_rows] if limit_rows else rows


def kpi_profession_counts(skill_id: int, min_value: int = 300) -> int:
    q = (
        """
    SELECT COUNT(DISTINCT guid) AS count_chars
    FROM character_skills
    WHERE skill = %s AND value >= %s
    """
    )
    with conn(DB_CHAR) as c, c.cursor() as cur:
        cur.execute(q, (skill_id, min_value))
        return int(cur.fetchone()["count_chars"]) or 0


def kpi_bans_today() -> int:
    q = (
        """
    SELECT COUNT(*) AS n
    FROM account_banned
    WHERE FROM_UNIXTIME(ban_date) >= CURDATE() AND active = 1
    """
    )
    with conn(DB_AUTH) as c, c.cursor() as cur:
        cur.execute(q)
        return int(cur.fetchone()["n"]) or 0


def kpi_find_characters(name_query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Find characters by name (case-insensitive, partial match). Returns basic fields and guild name if available."""
    if not name_query:
        return []
    # Build LIKE pattern safely via parameters
    like = f"%{name_query}%"
    q = (
        """
    SELECT c.guid, c.name, c.level, c.class, c.race, c.gender, c.online,
           g.name AS guild
    FROM characters c
    LEFT JOIN guild_member gm ON gm.guid = c.guid
    LEFT JOIN guild g ON g.guildid = gm.guildid
    WHERE c.name LIKE %s
    ORDER BY c.level DESC, c.name ASC
    LIMIT %s
    """
    )
    with conn(DB_CHAR) as cn, cn.cursor() as cur:
        cur.execute(q, (like, int(limit)))
        return cur.fetchall()


def kpi_summary_text() -> str:
    online = kpi_players_online()
    totals = kpi_totals()
    arena = kpi_arena_rating_distribution(limit_rows=5)
    topgold = kpi_top_gold(limit=3)
    lines = [
        wrap_response("Online now", str(online)),
        wrap_response("Characters", str(totals['total_chars'])),
        wrap_response("Accounts", str(totals['total_accounts'])),
    ]
    if arena:
        head = ", ".join(f"{r['rating']}: {r['teams']}" for r in arena[:5])
        lines.append(wrap_response("Arena (top buckets)", head))
    if topgold:
        tg = " | ".join(
            f"{r['name']} (Lv {r['level']}): {copper_to_gsc(r['money'])}" for r in topgold
        )
        lines.append(wrap_response("Top gold", tg))
    return "\n".join(lines)


def kpi_summary_json() -> str:
    import json

    return json.dumps(
        {
            "online": kpi_players_online(),
            "totals": kpi_totals(),
            "arena_top": kpi_arena_rating_distribution(limit_rows=5),
            "top_gold": kpi_top_gold(limit=3),
            "levels": kpi_level_distribution(),
        },
        ensure_ascii=False,
    )
