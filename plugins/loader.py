from __future__ import annotations

import importlib.util
import inspect
import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from plugins.context import PluginContext


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PluginManifest:
    name: str
    version: str
    kind: str
    entrypoint: str
    enabled_by_default: bool
    enabled_env: str | None
    description: str


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_plugin_roots(root_dir: Path) -> list[tuple[str, Path]]:
    raw = os.getenv("GESTALT_PLUGIN_DIRS", "").strip()
    if raw:
        roots: list[tuple[str, Path]] = []
        for item in raw.split(","):
            candidate = Path(item.strip())
            if candidate:
                roots.append(("custom", candidate))
        return roots
    return [
        ("builtins", root_dir / "plugins" / "builtins"),
        ("community", root_dir / "plugins" / "community"),
    ]


def _parse_manifest(manifest_path: Path) -> PluginManifest | None:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    name = str(data.get("name") or "").strip()
    version = str(data.get("version") or "").strip()
    kind = str(data.get("kind") or "").strip()
    entrypoint = str(data.get("entrypoint") or "").strip()
    enabled_by_default = bool(data.get("enabled_by_default", False))
    enabled_env_raw = data.get("enabled_env")
    enabled_env = (
        str(enabled_env_raw).strip() if isinstance(enabled_env_raw, str) else None
    )
    description = str(data.get("description") or "").strip()

    if not name or not version or not kind or not entrypoint:
        return None

    return PluginManifest(
        name=name,
        version=version,
        kind=kind,
        entrypoint=entrypoint,
        enabled_by_default=enabled_by_default,
        enabled_env=enabled_env,
        description=description,
    )


def _is_enabled(manifest: PluginManifest) -> bool:
    if manifest.enabled_env:
        return _truthy(os.getenv(manifest.enabled_env), False)
    return manifest.enabled_by_default


def _discover(root_dir: Path) -> list[tuple[Path, PluginManifest]]:
    discovered: list[tuple[Path, PluginManifest]] = []
    for _group, plugins_root in _resolve_plugin_roots(root_dir):
        if not plugins_root.exists() or not plugins_root.is_dir():
            continue
        for child in sorted(plugins_root.iterdir()):
            if not child.is_dir():
                continue
            manifest_path = child / "plugin.json"
            if not manifest_path.exists():
                continue
            manifest = _parse_manifest(manifest_path)
            if manifest is None:
                continue
            discovered.append((child, manifest))
    return discovered


class PluginLoader:
    @staticmethod
    async def load_all(context: PluginContext, root_dir: Path) -> list[str]:
        return await load_plugins(context=context, root_dir=root_dir)


async def load_plugins(context: PluginContext, root_dir: Path) -> list[str]:
    strict = _truthy(os.getenv("GESTALT_STRICT_PLUGINS"), False)
    loaded: list[str] = []
    for plugin_dir, manifest in _discover(root_dir):
        if not _is_enabled(manifest):
            continue

        entrypoint_path = (plugin_dir / manifest.entrypoint).resolve()
        if not entrypoint_path.exists() or not entrypoint_path.is_file():
            logger.warning(
                "Plugin '%s' entrypoint not found: %s", manifest.name, entrypoint_path
            )
            continue

        module_name = f"gestalt_plugin_{manifest.name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, entrypoint_path)
            if spec is None or spec.loader is None:
                logger.warning("Plugin '%s' failed to load module spec", manifest.name)
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                logger.warning("Plugin '%s' missing callable register", manifest.name)
                continue

            result = register(context)
            if inspect.isawaitable(result):
                await result
            loaded.append(manifest.name)
        except Exception as exc:
            logger.warning("Plugin '%s' load failed: %s", manifest.name, exc)
            if strict:
                raise

    return loaded
