import os
from typing import Any, Dict, Optional
import requests


def _join(base: str, path: str) -> str:
    base = base.rstrip('/')
    if not path.startswith('/'):
        path = '/' + path
    return base + path


class AcoreApiClient:
    """Minimal client for acore-api with flexible endpoints via env.

    Env vars (all optional unless using this provider):
    - ACORE_API_BASE_URL
    - ACORE_API_TOKEN ("Bearer ..." or raw token; we prefix Bearer if missing a space)
    - ACORE_API_TIMEOUT_SEC (default 3)
    - ACORE_API_REALM_ID (default 1)
    - ACORE_API_ONLINE_PATH (default "/realms/{realm_id}/online")
    - ACORE_API_POP_PATH (default "/realms/{realm_id}/online/races")
    - ACORE_API_UPTIME_PATH (default "/realms/{realm_id}/status")
    - ACORE_API_AUCTIONS_PATH (default "/auctionhouse/{realm_id}/stats")
    """

    def __init__(self) -> None:
        self.base = os.getenv("ACORE_API_BASE_URL", "").strip()
        self.token = os.getenv("ACORE_API_TOKEN", "").strip()
        try:
            self.timeout = float(os.getenv("ACORE_API_TIMEOUT_SEC", "3"))
        except Exception:
            self.timeout = 3.0
        try:
            self.realm_id = int(os.getenv("ACORE_API_REALM_ID", "1"))
        except Exception:
            self.realm_id = 1
        self.paths = {
            "online": os.getenv("ACORE_API_ONLINE_PATH", "/realms/{realm_id}/online"),
            "population": os.getenv("ACORE_API_POP_PATH", "/realms/{realm_id}/online/races"),
            "uptime": os.getenv("ACORE_API_UPTIME_PATH", "/realms/{realm_id}/status"),
            "auctions": os.getenv("ACORE_API_AUCTIONS_PATH", "/auctionhouse/{realm_id}/stats"),
        }

    @property
    def enabled(self) -> bool:
        return bool(self.base)

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.token:
            hval = self.token
            if " " not in hval:
                hval = f"Bearer {hval}"
            h["Authorization"] = hval
        return h

    def _get_json(self, path_key: str) -> Dict[str, Any]:
        tpl = self.paths.get(path_key, "")
        url = _join(self.base, tpl.format(realm_id=self.realm_id))
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {"data": data}

    # --- High-level helpers ---
    def get_online(self) -> int:
        try:
            j = self._get_json("online")
        except Exception:
            return 0
        for k in ("online", "players", "count", "connected"):
            if isinstance(j.get(k), int):
                return int(j[k])
        # Sometimes shape: {"data": {"online": n}}
        data = j.get("data") or {}
        for k in ("online", "players", "count", "connected"):
            v = data.get(k)
            if isinstance(v, int):
                return int(v)
        return 0

    def get_population(self) -> Dict[str, int]:
        try:
            j = self._get_json("population")
        except Exception:
            return {"alliance": 0, "horde": 0}
        # Accept either {factions:{alliance:.., horde:..}} or {races:{race_id:count}}
        factions = j.get("factions") or (j.get("data") or {}).get("factions")
        if isinstance(factions, dict):
            a = int(factions.get("alliance") or factions.get("Alliance") or 0)
            h = int(factions.get("horde") or factions.get("Horde") or 0)
            return {"alliance": a, "horde": h}
        races = j.get("races") or (j.get("data") or {}).get("races")
        if isinstance(races, dict):
            mapping = {
                1: "alliance", 3: "alliance", 4: "alliance", 7: "alliance", 11: "alliance",
                2: "horde", 5: "horde", 6: "horde", 8: "horde", 10: "horde",
            }
            a = h = 0
            for k, v in races.items():
                try:
                    race = int(k)
                    n = int(v)
                except Exception:
                    continue
                side = mapping.get(race)
                if side == "alliance":
                    a += n
                elif side == "horde":
                    h += n
            return {"alliance": a, "horde": h}
        return {"alliance": 0, "horde": 0}

    def get_uptime(self) -> Dict[str, Optional[int]]:
        try:
            j = self._get_json("uptime")
        except Exception:
            return {"uptime_sec": None, "start_time": None}
        data = j.get("data") or j
        uptime = data.get("uptime") or data.get("uptime_sec")
        start = data.get("starttime") or data.get("start_time")
        try:
            uptime = int(uptime) if uptime is not None else None
        except Exception:
            uptime = None
        try:
            start = int(start) if start is not None else None
        except Exception:
            start = None
        return {"uptime_sec": uptime, "start_time": start}

    def get_auctions(self) -> Dict[str, int]:
        try:
            j = self._get_json("auctions")
        except Exception:
            return {"active": 0, "avg_buyout_copper": 0}
        data = j.get("data") or j
        active = data.get("active") or data.get("count") or 0
        avg = data.get("avg_buyout") or data.get("avg_buyout_copper") or 0
        try:
            active = int(active)
        except Exception:
            active = 0
        try:
            avg = int(avg)
        except Exception:
            avg = 0
        return {"active": active, "avg_buyout_copper": avg}

