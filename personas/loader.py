from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Valid cognitive modes for persona operation
VALID_MODES = {"default", "creative", "logic", "analytical", "reflective", "focused"}


def _get_validated_default_mode(data: dict[str, Any]) -> str:
    """Extract and validate default_mode from character data.

    Falls back to 'default' if not specified or invalid.
    Looks in data.default_mode first, then data.extensions.mode_profiles.default_mode.
    """
    # Check top-level default_mode first
    top_level_mode = data.get("default_mode")
    if isinstance(top_level_mode, str) and top_level_mode.strip():
        mode = top_level_mode.strip().lower()
        if mode in VALID_MODES:
            return mode

    # Check extensions.mode_profiles.default_mode
    extensions = data.get("extensions", {})
    if isinstance(extensions, dict):
        mode_profiles = extensions.get("mode_profiles", {})
        if isinstance(mode_profiles, dict):
            ext_mode = mode_profiles.get("default_mode")
            if isinstance(ext_mode, str) and ext_mode.strip():
                mode = ext_mode.strip().lower()
                if mode in VALID_MODES:
                    return mode

    return "default"


@dataclass(slots=True)
class PersonaDefinition:
    persona_id: str
    display_name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_message: str = ""
    system_prompt: str = ""
    default_mode: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PersonaCatalog:
    personas: dict[str, PersonaDefinition]

    def by_id(self, persona_id: str) -> PersonaDefinition | None:
        return self.personas.get(persona_id)

    def all(self) -> list[PersonaDefinition]:
        return list(self.personas.values())


def _normalize_persona(raw: dict[str, Any], fallback_id: str) -> PersonaDefinition:
    data = raw.get("data", raw)
    name = str(data.get("name") or data.get("id") or fallback_id)
    persona_id = str(data.get("id") or name).strip().replace(" ", "_").lower()
    display_name = str(data.get("display_name") or data.get("name") or persona_id)
    return PersonaDefinition(
        persona_id=persona_id,
        display_name=display_name,
        description=str(data.get("description") or ""),
        personality=str(data.get("personality") or ""),
        scenario=str(data.get("scenario") or ""),
        first_message=str(data.get("first_mes") or data.get("first_message") or ""),
        system_prompt=str(data.get("system_prompt") or ""),
        default_mode=_get_validated_default_mode(data),
        metadata=dict(data.get("extensions") or {}),
    )


def load_persona_catalog(characters_dir: str | Path) -> PersonaCatalog:
    path = Path(characters_dir)
    personas: dict[str, PersonaDefinition] = {}
    if not path.exists():
        return PersonaCatalog(personas={})

    for file_path in sorted(path.glob("*.json")):
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            persona = _normalize_persona(raw, fallback_id=file_path.stem)
            personas[persona.persona_id] = persona
        except Exception:
            continue
    return PersonaCatalog(personas=personas)


def resolve_default_persona_id(
    catalog: PersonaCatalog,
    *,
    preferred_id: str = "",
) -> str:
    """Resolve default persona id from preference or catalog order.

    Falls back to `"default"` when catalog is empty.
    """
    preferred = str(preferred_id or "").strip().replace(" ", "_").lower()
    if preferred and catalog.by_id(preferred) is not None:
        return preferred
    personas = catalog.all()
    if personas:
        return str(personas[0].persona_id or "default")
    return "default"
