"""Notes service - allows users to save text notes."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import uuid

from config import Config

logger = logging.getLogger(__name__)


class NotesService:
    """Service for managing user notes."""

    def __init__(self, bot, data_dir: Path = None):
        """Initialize the notes service.

        Args:
            bot: Discord bot instance
            data_dir: Directory to store notes data
        """
        self.bot = bot
        self.data_dir = data_dir or Config.DATA_DIR / "notes"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.notes: Dict[str, Dict] = {}  # note_id -> note data

        # Load existing notes
        self._load_notes()

        logger.info(f"Notes service initialized with {len(self.notes)} notes")

    def _load_notes(self):
        """Load notes from disk."""
        notes_file = self.data_dir / "notes.json"
        if notes_file.exists():
            try:
                with open(notes_file, 'r') as f:
                    data = json.load(f)
                    # Convert string dates back to datetime
                    for nid, note in data.items():
                        try:
                            note['created_at'] = datetime.fromisoformat(note['created_at'])
                            self.notes[nid] = note
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Skipping invalid note {nid}: {e}")
                            
                logger.info(f"Loaded {len(self.notes)} notes from disk")
            except Exception as e:
                logger.error(f"Failed to load notes: {e}")
                # Don't wipe notes on error, just keep empty
                if not self.notes:
                    self.notes = {}

    def _save_notes(self):
        """Save notes to disk."""
        notes_file = self.data_dir / "notes.json"
        try:
            # Convert datetime to string for JSON
            data = {}
            for nid, note in self.notes.items():
                data[nid] = {
                    **note,
                    'created_at': note['created_at'].isoformat(),
                }
            with open(notes_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save notes: {e}")

    async def add_note(
        self,
        user_id: int,
        content: str,
        category: str = "general"
    ) -> Optional[str]:
        """Add a new note.

        Args:
            user_id: User who created the note
            content: Note content
            category: Optional category/tag

        Returns:
            Note ID or None if failed
        """
        # Check user's note count (optional limit)
        user_notes = self.get_user_notes(user_id)
        max_notes = 50  # Hardcoded limit for now, could be in Config

        if len(user_notes) >= max_notes:
            return None

        note_id = str(uuid.uuid4())[:8]

        self.notes[note_id] = {
            'user_id': user_id,
            'content': content,
            'category': category,
            'created_at': datetime.now(),
        }

        self._save_notes()
        logger.info(f"Added note {note_id} for user {user_id}")

        return note_id

    def get_user_notes(self, user_id: int, category: Optional[str] = None) -> List[Dict]:
        """Get all notes for a user.

        Args:
            user_id: User ID
            category: Optional category filter

        Returns:
            List of note dicts
        """
        user_notes = [
            {'id': nid, **note}
            for nid, note in self.notes.items()
            if note['user_id'] == user_id
        ]
        
        if category:
            user_notes = [n for n in user_notes if n['category'].lower() == category.lower()]
            
        return user_notes

    def delete_note(self, note_id: str, user_id: int) -> bool:
        """Delete a note.

        Args:
            note_id: Note ID to delete
            user_id: User requesting deletion (must own the note)

        Returns:
            True if deleted, False if not found or not owned
        """
        if note_id not in self.notes:
            return False

        if self.notes[note_id]['user_id'] != user_id:
            return False

        del self.notes[note_id]
        self._save_notes()
        logger.info(f"Deleted note {note_id}")

        return True

    def clear_user_notes(self, user_id: int) -> int:
        """Clear all notes for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of notes deleted
        """
        to_delete = [nid for nid, note in self.notes.items() if note['user_id'] == user_id]
        
        for nid in to_delete:
            del self.notes[nid]
            
        if to_delete:
            self._save_notes()
            
        return len(to_delete)
