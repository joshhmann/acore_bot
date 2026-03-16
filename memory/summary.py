from __future__ import annotations


class DeterministicSummary:
    def __init__(self, max_chars: int = 1200) -> None:
        self.max_chars = max_chars

    def update(self, existing: str, recent_messages: list[dict[str, str]]) -> str:
        lines: list[str] = []
        if existing:
            lines.append(existing.strip())
        for message in recent_messages:
            role = message.get("role", "unknown")
            content = (message.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")
        merged = "\n".join(lines)
        if len(merged) <= self.max_chars:
            return merged
        return merged[-self.max_chars :]
