from __future__ import annotations
from typing import Iterable, Tuple

try:  # pragma: no cover - optional dependency
    import discord  # type: ignore
except Exception:  # pragma: no cover
    discord = None  # type: ignore


def copper_to_gsc(copper: int) -> str:
    g, rem = divmod(int(copper or 0), 10000)
    s, c = divmod(rem, 100)
    parts: list[str] = []
    if g:
        parts.append(f"{g}g")
    if s:
        parts.append(f"{s}s")
    if c or not parts:
        parts.append(f"{c}c")
    return " ".join(parts)


def rows_to_embed(title: str, rows: Iterable[str], color: int = 0x2ECC71) -> discord.Embed:
    embed = discord.Embed(title=title, color=color)
    rows = list(rows)
    if rows:
        embed.description = "\n".join(rows)
    return embed


def kv_to_embed(title: str, items: Iterable[Tuple[str, str]], color: int = 0x2ECC71) -> discord.Embed:
    embed = discord.Embed(title=title, color=color)
    for name, value in items:
        embed.add_field(name=name, value=value, inline=False)
    return embed
