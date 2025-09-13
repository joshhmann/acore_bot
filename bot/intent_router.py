from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class Intent(Enum):
    GENERIC_CHAT = auto()
    ACCOUNT = auto()
    PW_CHANGE = auto()
    REALM_STATUS = auto()
    ECONOMY_STATS = auto()
    HELP = auto()


SENSITIVE = {Intent.ACCOUNT, Intent.PW_CHANGE, Intent.REALM_STATUS, Intent.ECONOMY_STATS}


@dataclass
class RouteDecision:
    intent: Intent
    mode: str  # "chat" or "authoritative"
    reason: str


_KEYWORDS = {
    Intent.ACCOUNT: ["account", "register", "signup", "sign up"],
    Intent.PW_CHANGE: ["password", "pass"],
    Intent.REALM_STATUS: ["realm", "server", "population", "uptime", "status", "online"],
    Intent.ECONOMY_STATS: ["auction", "economy", "gold", "price", "market"],
    Intent.HELP: ["help", "commands", "what can you do"],
}


def classify_intent(text: str) -> Intent:
    lt = text.lower()
    for intent, words in _KEYWORDS.items():
        if any(w in lt for w in words):
            if intent is Intent.PW_CHANGE:
                if any(k in lt for k in ["change", "reset", "forgot", "lost"]):
                    return intent
                continue
            return intent
    return Intent.GENERIC_CHAT


_CHAT_WORDS = {"thanks", "lol", "hi", "hello", "sup", "ty"}


def route(text: str, prior_mode: Optional[str] = None) -> RouteDecision:
    intent = classify_intent(text)
    reason = "matched keywords" if intent is not Intent.GENERIC_CHAT else "default"
    mode = "authoritative" if intent in SENSITIVE else "chat"
    if prior_mode == "authoritative" and intent is Intent.GENERIC_CHAT:
        if not any(w in text.lower() for w in _CHAT_WORDS):
            mode = "authoritative"
            reason = "prior authoritative context"
    return RouteDecision(intent=intent, mode=mode, reason=reason)
