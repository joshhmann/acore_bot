"""Validate and execute tool calls."""
from __future__ import annotations

import logging
from typing import Any, Dict


from .tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def _redact(args: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
    red = {}
    for k, v in args.items():
        red[k] = "***" if k in fields else v
    return red


def _validate(args: Dict[str, Any], schema: Dict[str, Any]) -> None:
    required = schema.get("required", [])
    for r in required:
        if r not in args:
            raise ValueError(f"missing {r}")
    props = schema.get("properties", {})
    for k, v in args.items():
        spec = props.get(k, {})
        t = spec.get("type")
        if t == "string" and not isinstance(v, str):
            raise ValueError(f"{k} must be string")
        if t == "integer" and not isinstance(v, int):
            raise ValueError(f"{k} must be integer")
        enum = spec.get("enum")
        if enum and v not in enum:
            raise ValueError(f"{k} not in enum")
def dispatch(call: Dict[str, Any]) -> Dict[str, Any]:
    name = call.get("name")
    args = call.get("arguments", {}) or {}
    spec = TOOL_REGISTRY.get(name)
    if not spec:
        return {"type": "tool_error", "name": name, "error": "unknown tool"}
    try:
        _validate(args, spec["schema"])
    except ValueError as e:
        return {"type": "tool_error", "name": name, "error": f"invalid arguments: {e}"}
    redacted = _redact(args, spec.get("redact", []))
    logger.info("tool_call", extra={"tool": name, "params": redacted})
    try:
        result = spec["handler"](args)
        return {"type": "tool_result", "name": name, "result": result}
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("tool_error %s", name)
        return {"type": "tool_error", "name": name, "error": str(e)}
