from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _project_root(arguments: dict[str, Any]) -> Path:
    configured = str(arguments.get("project_root") or "").strip()
    root = Path(configured).resolve() if configured else Path.cwd().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid project root")
    return root


def _resolve_within_root(path_value: str, root: Path) -> Path:
    if not path_value.strip():
        raise ValueError("Missing 'path'")
    candidate = (root / path_value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Path outside project root is not allowed") from exc
    return candidate


async def tool_file_read(arguments: dict[str, Any]) -> str:
    root = _project_root(arguments)
    max_chars = max(200, min(50000, int(arguments.get("max_chars") or 8000)))
    target = _resolve_within_root(str(arguments.get("path") or ""), root)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError("File not found")

    data = target.read_text(encoding="utf-8", errors="replace")
    truncated = len(data) > max_chars
    payload = {
        "path": str(target.relative_to(root)),
        "content": data[:max_chars],
        "truncated": truncated,
    }
    return json.dumps(payload, ensure_ascii=True)


async def tool_file_list(arguments: dict[str, Any]) -> str:
    root = _project_root(arguments)
    include_hidden = bool(arguments.get("include_hidden", False))
    target = _resolve_within_root(str(arguments.get("path") or "."), root)
    if not target.exists() or not target.is_dir():
        raise NotADirectoryError("Directory not found")

    entries: list[dict[str, Any]] = []
    for item in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if not include_hidden and item.name.startswith("."):
            continue
        entries.append(
            {
                "name": item.name,
                "kind": "dir" if item.is_dir() else "file",
            }
        )

    payload = {
        "path": str(target.relative_to(root)) if target != root else ".",
        "entries": entries,
    }
    return json.dumps(payload, ensure_ascii=True)


async def tool_file_write(arguments: dict[str, Any]) -> str:
    root = _project_root(arguments)
    overwrite = bool(arguments.get("overwrite", False))
    content = str(arguments.get("content") or "")
    target = _resolve_within_root(str(arguments.get("path") or ""), root)
    existed = target.exists()
    if existed and not overwrite:
        raise PermissionError(
            "Refusing to overwrite existing file without overwrite=true"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    payload = {
        "path": str(target.relative_to(root)),
        "bytes_written": len(content.encode("utf-8")),
        "overwrote": existed,
    }
    return json.dumps(payload, ensure_ascii=True)
