from __future__ import annotations
import contextlib
from dataclasses import dataclass
from typing import Optional, Tuple

import pymysql


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    auth_db: str = "auth"
    char_db: str = "characters"
    world_db: str = "world"


def _connect(db: str, cfg: DBConfig):
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=db,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
        autocommit=True,
    )


def table_exists(db: str, table: str, cfg: DBConfig) -> bool:
    try:
        with _connect(db, cfg) as conn, conn.cursor() as cur:
            cur.execute("SHOW TABLES LIKE %s", (table,))
            return cur.fetchone() is not None
    except Exception:
        return False


def scalar(db: str, sql: str, cfg: DBConfig, args: tuple = ()) -> Optional[int]:
    try:
        with _connect(db, cfg) as conn, conn.cursor() as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
            if not row:
                return None
            val = row[0]
            try:
                return int(val)
            except Exception:
                return None
    except Exception:
        return None


def get_online_count(cfg: DBConfig) -> Optional[int]:
    # AzerothCore commonly uses characters.character_online table. Some forks store online flag in characters table.
    if table_exists(cfg.char_db, "character_online", cfg):
        return scalar(cfg.char_db, "SELECT COUNT(*) FROM character_online", cfg)
    # Fallback to characters.online flag
    return scalar(cfg.char_db, "SELECT COUNT(*) FROM characters WHERE online=1", cfg)


def get_totals(cfg: DBConfig) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    accounts = scalar(cfg.auth_db, "SELECT COUNT(*) FROM account", cfg)
    characters = scalar(cfg.char_db, "SELECT COUNT(*) FROM characters", cfg)
    guilds = scalar(cfg.char_db, "SELECT COUNT(*) FROM guild", cfg)
    return accounts, characters, guilds

