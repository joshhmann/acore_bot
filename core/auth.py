from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from providers.registry import canonical_provider_name


def default_auth_path() -> Path:
    if os.name == "nt":
        root = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
        return root / "gestalt" / "auth.json"
    if os.uname().sysname.lower() == "darwin":
        return Path.home() / "Library" / "Application Support" / "gestalt" / "auth.json"
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "gestalt" / "auth.json"
    return Path.home() / ".config" / "gestalt" / "auth.json"


class AuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_auth_path()

    def list_providers(self) -> list[str]:
        payload = self._load()
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            return []
        return sorted([str(name) for name in providers.keys()])

    def list_provider_summaries(self) -> list[dict[str, Any]]:
        payload = self._load()
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            return []
        summaries: list[dict[str, Any]] = []
        for name in sorted(providers.keys()):
            entry = providers.get(name)
            if not isinstance(entry, dict):
                continue
            summaries.append(
                {
                    "provider": str(name),
                    "base_url": str(entry.get("base_url") or ""),
                    "model": str(entry.get("model") or ""),
                    "has_api_key": bool(str(entry.get("api_key") or "").strip()),
                    "has_token": bool(str(entry.get("token") or "").strip()),
                    "updated_at": str(entry.get("updated_at") or ""),
                }
            )
        return summaries

    def get_last_used_provider(self) -> str:
        payload = self._load()
        value = payload.get("last_used_provider")
        return str(value).strip().lower() if isinstance(value, str) else ""

    def get_provider_config(self, provider: str) -> dict[str, Any]:
        payload = self._load()
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            return {}
        normalized = canonical_provider_name(provider)
        probe = normalized or provider.strip().lower()
        entry = providers.get(probe)
        if not isinstance(entry, dict) and probe != provider.strip().lower():
            entry = providers.get(provider.strip().lower())
        if not isinstance(entry, dict):
            return {}
        return dict(entry)

    def get_token(self, provider: str) -> str:
        config = self.get_provider_config(provider)
        api_key = str(config.get("api_key") or "").strip()
        if api_key:
            return api_key
        token = config.get("token")
        return str(token) if isinstance(token, str) else ""

    def set_token(self, provider: str, token: str) -> None:
        self.upsert_provider(provider=provider, token=token)

    def upsert_provider(
        self,
        provider: str,
        token: str = "",
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        clean_provider = canonical_provider_name(provider) or provider.strip().lower()
        clean_token = token.strip()
        clean_api_key = api_key.strip()
        clean_base_url = base_url.strip()
        clean_model = model.strip()
        if not clean_provider:
            raise ValueError("provider is required")
        if not any([clean_token, clean_api_key, clean_base_url, clean_model]):
            raise ValueError("at least one auth field is required")

        payload = self._load()
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            providers = {}
            payload["providers"] = providers

        existing = providers.get(clean_provider)
        baseline = dict(existing) if isinstance(existing, dict) else {}
        if clean_token:
            baseline["token"] = clean_token
        if clean_api_key:
            baseline["api_key"] = clean_api_key
        if clean_base_url:
            baseline["base_url"] = clean_base_url
        if clean_model:
            baseline["model"] = clean_model

        providers[clean_provider] = {
            **baseline,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        payload["last_used_provider"] = clean_provider
        self._save(payload)

    def remove_provider(self, provider: str) -> bool:
        payload = self._load()
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            return False
        canonical = canonical_provider_name(provider) or provider.strip().lower()
        removed = providers.pop(canonical, None) is not None
        if not removed and canonical != provider.strip().lower():
            removed = providers.pop(provider.strip().lower(), None) is not None
        if removed:
            if payload.get("last_used_provider") == canonical:
                payload["last_used_provider"] = ""
            self._save(payload)
        return removed

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"providers": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"providers": {}}
        return data if isinstance(data, dict) else {"providers": {}}

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=str(self.path.parent)
        ) as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
            temp_name = handle.name
        os.replace(temp_name, self.path)
        if os.name != "nt":
            os.chmod(self.path, 0o600)
