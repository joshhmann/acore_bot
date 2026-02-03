import json
import gzip
import aiofiles
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from services.conversation.state import ConversationState

logger = logging.getLogger(__name__)


class ConversationPersistence:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_dir = self.base_dir / "active"
        self.archive_dir = self.base_dir / "archive"
        self.active_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)

    def _get_file_path(self, conversation_id: str, archived: bool = False) -> Path:
        dir_path = self.archive_dir if archived else self.active_dir
        return dir_path / f"{conversation_id}.jsonl"

    async def save(self, state: ConversationState) -> None:
        file_path = self._get_file_path(state.conversation_id)
        temp_path = file_path.with_suffix(".tmp")

        try:
            async with aiofiles.open(temp_path, "w") as f:
                await f.write(json.dumps(state.to_dict()) + "\n")

            temp_path.replace(file_path)
            logger.debug(f"Saved conversation {state.conversation_id}")

        except Exception as e:
            logger.error(f"Failed to save conversation {state.conversation_id}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

    async def load(self, conversation_id: str) -> Optional[ConversationState]:
        for archived in [False, True]:
            file_path = self._get_file_path(conversation_id, archived)
            if file_path.exists():
                try:
                    async with aiofiles.open(file_path, "r") as f:
                        content = await f.read()
                        data = json.loads(content.strip())
                        return ConversationState.from_dict(data)
                except Exception as e:
                    logger.error(f"Failed to load conversation {conversation_id}: {e}")
                    return None

        return None

    async def list_active(self) -> List[str]:
        return [f.stem for f in self.active_dir.glob("*.jsonl")]

    async def archive(self, conversation_id: str) -> bool:
        active_path = self._get_file_path(conversation_id, archived=False)
        archive_path = self.archive_dir / f"{conversation_id}.jsonl.gz"

        if not active_path.exists():
            return False

        try:
            async with aiofiles.open(active_path, "rb") as f:
                content = await f.read()

            async with aiofiles.open(archive_path, "wb") as f:
                await f.write(gzip.compress(content))

            active_path.unlink()
            logger.info(f"Archived conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive conversation {conversation_id}: {e}")
            return False

    async def cleanup_old(self, max_age_days: int = 30) -> int:
        cutoff = datetime.now() - timedelta(days=max_age_days)
        removed = 0

        for file_path in self.archive_dir.glob("*.jsonl.gz"):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff:
                    file_path.unlink()
                    removed += 1
                    logger.info(f"Cleaned up old conversation file: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to cleanup {file_path}: {e}")

        return removed
