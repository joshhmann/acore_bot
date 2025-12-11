"""Lorebook service for managing and injecting world info."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LoreEntry:
    """A single lorebook entry."""
    uid: str
    keys: List[str]  # Keywords that trigger this entry
    content: str     # The actual lore text
    order: int = 100 # Insertion order (lower = higher priority/earlier in prompt)
    enabled: bool = True
    case_sensitive: bool = False

    # Non-standard extensions
    constant: bool = False  # Always include this entry
    position: str = "before_char"  # where to insert: before_char, after_char


@dataclass
class Lorebook:
    """A collection of lore entries."""
    name: str
    entries: Dict[str, LoreEntry] = field(default_factory=dict)

    def get_entries_list(self) -> List[LoreEntry]:
        """Get all entries as a list sorted by order."""
        return sorted(self.entries.values(), key=lambda x: x.order)


class LorebookService:
    """Service for managing lorebooks and scanning text for triggers."""

    def __init__(self, lorebooks_dir: Path = Path("./data/lorebooks")):
        """
        Initialize lorebook service.

        Args:
            lorebooks_dir: Directory where lorebooks are stored
        """
        self.lorebooks_dir = lorebooks_dir
        self.lorebooks_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_lorebooks: Dict[str, Lorebook] = {}

        # Load all available lorebooks on startup
        self._load_all_lorebooks()

    def _load_all_lorebooks(self):
        """Load all JSON lorebooks from directory."""
        for file in self.lorebooks_dir.glob("*.json"):
            try:
                self.load_lorebook(file.stem)
            except Exception as e:
                logger.error(f"Failed to load lorebook {file}: {e}")

    def load_lorebook(self, name: str) -> Optional[Lorebook]:
        """
        Load a lorebook by name.

        Args:
            name: Lorebook name (filename without extension)

        Returns:
            Lorebook object or None if not found
        """
        file_path = self.lorebooks_dir / f"{name}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entries = {}
            # Handle standard V2/SillyTavern format
            raw_entries = data.get('entries', {})

            # If entries is a list (common export format)
            if isinstance(raw_entries, list):
                # Convert list to dict keyed by uid
                for i, raw_entry in enumerate(raw_entries):
                    uid = str(raw_entry.get('uid', i))
                    entries[uid] = self._parse_entry(raw_entry, uid)
            else:
                # If it's a dict (internal format)
                for uid, raw_entry in raw_entries.items():
                     entries[uid] = self._parse_entry(raw_entry, uid)

            lorebook = Lorebook(
                name=data.get('name', name),
                entries=entries
            )

            self.loaded_lorebooks[name] = lorebook
            logger.info(f"Loaded lorebook: {name} with {len(entries)} entries")
            return lorebook

        except Exception as e:
            logger.error(f"Error loading lorebook {name}: {e}")
            return None

    def _parse_entry(self, raw: Dict, uid: str) -> LoreEntry:
        """Parse a raw dictionary into a LoreEntry."""
        return LoreEntry(
            uid=str(uid),
            keys=raw.get('key', []),
            content=raw.get('content', ''),
            order=int(raw.get('order', 100)),
            enabled=raw.get('enabled', True),
            case_sensitive=raw.get('case_sensitive', False),
            constant=raw.get('constant', False),
            position=raw.get('position', 'before_char')
        )

    def scan_for_triggers(self, text: str, lorebook_names: List[str]) -> List[LoreEntry]:
        """
        Scan text for keywords from specified lorebooks.

        Args:
            text: Text to scan (usually user input + recent history)
            lorebook_names: List of lorebooks to check

        Returns:
            List of matching LoreEntry objects, sorted by order
        """
        triggered_entries = []
        seen_uids = set()

        text_lower = text.lower()

        for lb_name in lorebook_names:
            lorebook = self.loaded_lorebooks.get(lb_name)
            if not lorebook:
                continue

            for entry in lorebook.entries.values():
                if not entry.enabled:
                    continue

                if entry.uid in seen_uids:
                    continue

                # Check constant entries
                if entry.constant:
                    triggered_entries.append(entry)
                    seen_uids.add(entry.uid)
                    continue

                # Check keywords
                for key in entry.keys:
                    if not key:
                        continue

                    is_match = False
                    if entry.case_sensitive:
                        if key in text:
                            is_match = True
                    else:
                        if key.lower() in text_lower:
                            is_match = True

                    if is_match:
                        triggered_entries.append(entry)
                        seen_uids.add(entry.uid)
                        break # Stop checking keys for this entry once triggered

        # Sort by insertion order
        triggered_entries.sort(key=lambda x: x.order)
        return triggered_entries

    def create_lorebook_from_text(self, name: str, text: str):
        """Simple helper to create a basic lorebook from text file (one entry per paragraph)."""
        entries = {}
        paragraphs = text.split('\n\n')

        for i, p in enumerate(paragraphs):
            p = p.strip()
            if not p:
                continue

            # Naive keyword extraction: first 2 words
            words = p.split()[:2]
            key = " ".join(words)

            entries[str(i)] = LoreEntry(
                uid=str(i),
                keys=[key],
                content=p,
                order=100 + i
            )

        lorebook = Lorebook(name=name, entries=entries)
        self.loaded_lorebooks[name] = lorebook

        # Save to disk
        self._save_lorebook(lorebook)

    def _save_lorebook(self, lorebook: Lorebook):
        """Save lorebook to disk."""
        path = self.lorebooks_dir / f"{lorebook.name}.json"

        data = {
            "name": lorebook.name,
            "entries": [
                {
                    "uid": e.uid,
                    "key": e.keys,
                    "content": e.content,
                    "order": e.order,
                    "enabled": e.enabled,
                    "constant": e.constant
                }
                for e in lorebook.entries.values()
            ]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_available_lorebooks(self) -> List[str]:
        """List names of available lorebooks."""
        return list(self.loaded_lorebooks.keys())
