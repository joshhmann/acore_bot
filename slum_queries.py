from __future__ import annotations
from typing import Dict, Optional, Union

from ac_metrics import kpi_profession_counts

# Mapping of profession names to their skill IDs
PROFESSION_IDS: Dict[str, int] = {
    "alchemy": 171,
    "herbalism": 182,
    "mining": 186,
    "blacksmithing": 164,
    "leatherworking": 165,
    "engineering": 202,
    "enchanting": 333,
    "tailoring": 197,
    "skinning": 393,
    "cooking": 185,
    "first aid": 129,
    "firstaid": 129,
    "fishing": 356,
    "jewelcrafting": 755,
    "inscription": 773,
}


def resolve_skill_id(name_or_id: Union[str, int]) -> Optional[int]:
    """Resolve a profession name or numeric ID to an integer skill ID.

    Args:
        name_or_id: Either the numeric ID or profession name.

    Returns:
        The corresponding skill ID, or None if it cannot be resolved.
    """
    try:
        return int(name_or_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pass
    if not isinstance(name_or_id, str):
        return None
    key = name_or_id.strip().lower()
    return PROFESSION_IDS.get(key)


def profession_counts(skill_id: int, min_value: int = 225) -> int:
    """Return count of characters with a profession at or above a value.

    This function passes through to the underlying metrics layer which
    performs the actual query. It defaults the minimum value to 225.
    """
    return kpi_profession_counts(skill_id=skill_id, min_value=min_value)
