from __future__ import annotations

import json
import os
from typing import List

try:  # pragma: no cover - fallback when discord is missing
    import discord  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    discord = None  # type: ignore


def json_load(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default


def json_save_atomic(path: str, data) -> None:
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def chunk_text(text: str, limit: int = 1900) -> List[str]:
    s = str(text)
    if len(s) <= limit:
        return [s]
    chunks: List[str] = []
    while s:
        if len(s) <= limit:
            chunks.append(s)
            break
        cut = s.rfind("\n", 0, limit)
        if cut == -1 or cut < int(limit * 0.6):
            cut = limit
        chunk, s = s[:cut].rstrip(), s[cut:].lstrip()
        chunks.append(chunk)
    return chunks


async def send_ephemeral(interaction: discord.Interaction, content: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
        else:
            await interaction.response.send_message(content, ephemeral=True)
    except Exception:
        pass


async def send_long_ephemeral(interaction: discord.Interaction, content: str, code_block: bool = False):
    chunks = chunk_text(content, 1900)
    def wrap(c: str) -> str:
        return f"```\n{c}\n```" if code_block else c
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(wrap(chunks[0]), ephemeral=True)
            start = 1
        else:
            start = 0
        for c in chunks[start:]:
            await interaction.followup.send(wrap(c), ephemeral=True)
    except Exception:
        pass


async def send_long_reply(message: discord.Message, content: str, code_block: bool = False, max_parts: int = 4):
    chunks = chunk_text(content, 1900)
    if len(chunks) > max_parts:
        chunks = chunks[:max_parts - 1] + [chunks[max_parts - 1] + "…"]
    wrap = (lambda c: f"```\n{c}\n```") if code_block else (lambda c: c)
    for c in chunks:
        try:
            await message.reply(wrap(c), mention_author=False)
        except Exception:
            break
