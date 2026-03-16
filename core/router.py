from __future__ import annotations

import re

from core.schemas import Event
from personas.loader import PersonaCatalog, PersonaDefinition


class Router:
    def __init__(self, default_persona_id: str = "default") -> None:
        self.default_persona_id = default_persona_id

    def _normalize(self, value: str) -> str:
        return value.lower().replace(" ", "_").strip()

    def select_persona(
        self,
        event: Event,
        catalog: PersonaCatalog,
    ) -> PersonaDefinition:
        metadata_persona = str(event.metadata.get("persona_id") or "").strip()
        if metadata_persona:
            candidate = catalog.by_id(self._normalize(metadata_persona))
            if candidate:
                return candidate

        mention_match = re.search(r"@([a-zA-Z0-9_]+)", event.text or "")
        if mention_match:
            mention = self._normalize(mention_match.group(1))
            candidate = catalog.by_id(mention)
            if candidate:
                return candidate

        default_persona = catalog.by_id(self.default_persona_id)
        if default_persona:
            return default_persona

        all_personas = catalog.all()
        if all_personas:
            return all_personas[0]

        return PersonaDefinition(persona_id="default", display_name="Default")
