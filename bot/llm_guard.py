"""Guardrails for LLM outputs."""
from __future__ import annotations

from .intent_router import SENSITIVE, Intent


class UngroundedAnswer(Exception):
    """Raised when a sensitive question is answered without tools."""


def require_tool_for_sensitive(intent: Intent, model_json: dict) -> None:
    if intent not in SENSITIVE:
        return
    t = model_json.get("type")
    if t == "tool_call":
        return
    if t == "final":
        text = str(model_json.get("text", ""))
        if "?" in text:
            return
    raise UngroundedAnswer("sensitive intent requires tool_call")
