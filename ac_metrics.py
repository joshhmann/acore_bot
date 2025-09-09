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
