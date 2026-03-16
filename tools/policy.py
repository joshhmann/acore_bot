from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolRiskTier(str, Enum):
    SAFE = "safe"
    NETWORK = "network"
    DANGEROUS = "dangerous"


@dataclass(slots=True)
class ToolPolicy:
    allowlist_by_persona: dict[str, set[str]] = field(default_factory=dict)
    allowlist_by_environment: dict[str, set[str]] = field(default_factory=dict)
    max_tool_calls_per_turn: int = 3
    network_enabled: bool = False
    dangerous_enabled: bool = False
    tool_risk_tiers: dict[str, str] = field(default_factory=dict)

    def _risk_allowed(self, tool_name: str) -> bool:
        tier = ToolRiskTier(
            self.tool_risk_tiers.get(tool_name, ToolRiskTier.SAFE.value)
        )
        if tier is ToolRiskTier.SAFE:
            return True
        if tier is ToolRiskTier.NETWORK:
            return self.network_enabled
        if tier is ToolRiskTier.DANGEROUS:
            return self.dangerous_enabled
        return False

    def allowed_tools(self, persona_id: str, environment: str) -> set[str] | None:
        p = self.allowlist_by_persona.get(persona_id)
        e = self.allowlist_by_environment.get(environment)
        if p is None and e is None:
            return None
        elif p is None:
            baseline = set(e or set())
        elif e is None:
            baseline = set(p)
        else:
            baseline = set(p).intersection(e)
        return {name for name in baseline if self._risk_allowed(name)}

    def is_tool_allowed(
        self,
        tool_name: str,
        allowed_tools: set[str] | None,
    ) -> bool:
        if allowed_tools is not None and tool_name not in allowed_tools:
            return False
        return self._risk_allowed(tool_name)
