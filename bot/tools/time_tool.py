from __future__ import annotations

from datetime import datetime, timezone


def get_current_time() -> dict:
    """Return current time information.

    Returns:
        dict: ``{"ok": bool, "iso_local": str, "iso_utc": str, "epoch": int, "tz_local": str}``
    """
    try:
        local = datetime.now().astimezone()
        utc = datetime.now(timezone.utc)
        return {
            "ok": True,
            "iso_local": local.isoformat(),
            "iso_utc": utc.isoformat(),
            "epoch": int(utc.timestamp()),
            "tz_local": str(local.tzinfo),
        }
    except Exception:
        return {"ok": False, "iso_local": "", "iso_utc": "", "epoch": 0, "tz_local": ""}
