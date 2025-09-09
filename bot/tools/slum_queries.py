import os
import json
import time
from typing import Any, Dict, Callable, Tuple

import aiomysql

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_RO_USER") or os.getenv("DB_USER", "")
DB_PASS = os.getenv("DB_RO_PASS") or os.getenv("DB_PASS", "")
DB_CHAR = os.getenv("DB_CHAR_DB", os.getenv("DB_CHAR", "characters"))
DB_WORLD = os.getenv("DB_WORLD_DB", os.getenv("DB_WORLD", "world"))

_pool: aiomysql.Pool | None = None
_cache: Dict[str, Dict[str, Any]] = {}

TTL_MAP = {
    "realm_online": 20,
    "faction_ratio": 60,
    "race_class_counts": 60,
    "economy_snapshot": 30,
    "top_gold": 30,
    "ah_hot": 30,
    "profession_counts": 45,
    "level_histogram": 60,
    "arena_distribution": 60,
    "active_guilds": 60,
}


async def _get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            db=DB_CHAR,
            autocommit=True,
            charset="utf8mb4",
        )
    return _pool


def _cache_key(name: str, params: Dict[str, Any]) -> str:
    return json.dumps([name, params], sort_keys=True)


def _get_cached(key: str):
    hit = _cache.get(key)
    if not hit:
        return None
    if time.time() >= hit["exp"]:
        _cache.pop(key, None)
        return None
    return hit["val"]


def _set_cached(key: str, val: Any, ttl: int) -> None:
    _cache[key] = {"val": val, "exp": time.time() + ttl}

def _q_realm_online(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    return "SELECT COUNT(*) AS online FROM character_online", ()


def _q_faction_ratio(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    q = (
        """
        SELECT faction, COUNT(*) AS count FROM (
            SELECT CASE
                WHEN race IN (1,3,4,7,11,22,25,29) THEN 'Alliance'
                ELSE 'Horde'
            END AS faction
            FROM characters
        ) AS t
        GROUP BY faction
        """
    )
    return q, ()


def _q_race_class_counts(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    return "SELECT race, class, COUNT(*) AS count FROM characters GROUP BY race, class", ()


def _q_economy_snapshot(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    q = (
        """
        SELECT
            (SELECT SUM(money) FROM characters) AS total_copper,
            (SELECT AVG(money) FROM characters) AS avg_copper,
            (SELECT COUNT(*) FROM auctionhouse) AS auctions
        """
    )
    return q, ()


def _q_top_gold(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    limit = int(params.get("limit", 10))
    return (
        "SELECT name, level, money FROM characters ORDER BY money DESC LIMIT %s",
        (limit,),
    )


def _q_ah_hot(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    limit = int(params.get("limit", 10))
    q = (
        f"""
        SELECT a.item_template,
               COUNT(*) AS listings,
               AVG(a.buyoutprice) AS avg_buyout,
               COALESCE(MIN(wt.name), CONCAT('Template ', a.item_template)) AS name
        FROM auctionhouse a
        LEFT JOIN {DB_WORLD}.item_template wt ON wt.entry = a.item_template
        GROUP BY a.item_template
        ORDER BY listings DESC
        LIMIT %s
        """
    )
    return q, (limit,)


def _q_profession_counts(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    skill_id = int(params.get("skill_id"))
    min_value = int(params.get("min_value", 300))
    return (
        "SELECT COUNT(*) AS n FROM character_skills WHERE skill=%s AND value >= %s",
        (skill_id, min_value),
    )


def _q_level_histogram(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    return (
        "SELECT level, COUNT(*) AS n FROM characters GROUP BY level ORDER BY level",
        (),
    )


def _q_arena_distribution(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    limit = int(params.get("limit", 20))
    return (
        "SELECT rating, COUNT(*) AS teams FROM arena_team GROUP BY rating ORDER BY rating DESC LIMIT %s",
        (limit,),
    )


def _q_active_guilds(params: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    days = int(params.get("days", 14))
    limit = int(params.get("limit", 10))
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
    return q, (days, limit)


_QUERY_MAP: Dict[str, Callable[[Dict[str, Any]], Tuple[str, Tuple[Any, ...]]]] = {
    "realm_online": _q_realm_online,
    "faction_ratio": _q_faction_ratio,
    "race_class_counts": _q_race_class_counts,
    "economy_snapshot": _q_economy_snapshot,
    "top_gold": _q_top_gold,
    "ah_hot": _q_ah_hot,
    "profession_counts": _q_profession_counts,
    "level_histogram": _q_level_histogram,
    "arena_distribution": _q_arena_distribution,
    "active_guilds": _q_active_guilds,
}


async def run_named_query(name: str, params: Dict[str, Any]) -> Any:
    name = str(name)
    params = params or {}
    builder = _QUERY_MAP.get(name)
    if not builder:
        raise ValueError(f"Unknown query: {name}")
    key = _cache_key(name, params)
    hit = _get_cached(key)
    if hit is not None:
        return hit
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            sql, args = builder(params)
            try:
                await cur.execute(sql, args)
            except Exception:
                if name == "realm_online":
                    await cur.execute("SELECT COUNT(*) AS online FROM characters WHERE online=1")
                else:
                    raise
            rows = await cur.fetchall()
    ttl = TTL_MAP.get(name, 30)
    _set_cached(key, rows, ttl)
    return rows


SLUM_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "slum_query",
        "description": "Run a predefined game realm query and return rows as JSON.",
        "parameters": {
            "type": "object",
            "oneOf": [
                {"properties": {"name": {"const": "realm_online"}}, "required": ["name"]},
                {"properties": {"name": {"const": "faction_ratio"}}, "required": ["name"]},
                {"properties": {"name": {"const": "race_class_counts"}}, "required": ["name"]},
                {"properties": {"name": {"const": "economy_snapshot"}}, "required": ["name"]},
                {
                    "properties": {
                        "name": {"const": "top_gold"},
                        "params": {
                            "type": "object",
                            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                            "required": ["limit"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name", "params"],
                },
                {
                    "properties": {
                        "name": {"const": "ah_hot"},
                        "params": {
                            "type": "object",
                            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                            "required": ["limit"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name", "params"],
                },
                {
                    "properties": {
                        "name": {"const": "profession_counts"},
                        "params": {
                            "type": "object",
                            "properties": {
                                "skill_id": {"type": "integer"},
                                "min_value": {"type": "integer"},
                            },
                            "required": ["skill_id"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name", "params"],
                },
                {"properties": {"name": {"const": "level_histogram"}}, "required": ["name"]},
                {
                    "properties": {
                        "name": {"const": "arena_distribution"},
                        "params": {
                            "type": "object",
                            "properties": {"limit": {"type": "integer"}},
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name"],
                },
                {
                    "properties": {
                        "name": {"const": "active_guilds"},
                        "params": {
                            "type": "object",
                            "properties": {
                                "days": {"type": "integer"},
                                "limit": {"type": "integer"},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "required": ["name"],
                },
            ],
        },
    },
}
