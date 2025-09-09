from __future__ import annotations

"""Formatting helpers for metrics and bot responses.

This module centralizes small formatting utilities so both slash commands
and LLM tool responses produce consistent output before sending to Discord
or models.
"""

from typing import Any


def normalize_ratio(value: Any) -> str:
    """Return a canonical representation of a ratio like ``1x``.

    Accepts numbers or strings optionally suffixed with ``x``. The output
    is trimmed to at most two decimal places and always suffixed with ``x``.
    Unparsable values are returned as-is.
    """
    if value is None:
        return ""
    s = str(value).strip().lower()
    if s.endswith("x"):
        s = s[:-1]
    try:
        f = float(s)
    except ValueError:
        return str(value)
    if f.is_integer():
        return f"{int(f)}x"
    # format with up to 2 decimals, strip trailing zeros/point
    return f"{f:.2f}".rstrip("0").rstrip(".") + "x"


def format_gold(copper: int) -> str:
    """Convert copper units to ``g s c`` string."""
    g, rem = divmod(int(copper or 0), 10_000)
    s, c = divmod(rem, 100)
    parts: list[str] = []
    if g:
        parts.append(f"{g}g")
    if s:
        parts.append(f"{s}s")
    if c or not parts:
        parts.append(f"{c}c")
    return " ".join(parts)


def normalize_item_name(name: Any) -> str:
    """Standardize item names (title case, spaces instead of underscores)."""
    s = str(name or "").replace("_", " ").strip()
    return " ".join(w.capitalize() for w in s.split())


def wrap_response(metric: str, value: str) -> str:
    """Wrap a metric/value pair in the standard template."""
    return f"{metric}: {value} — source: Slum DB"
