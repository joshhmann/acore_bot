"""Memory management service for cleaning up old data and optimizing storage."""
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import shutil

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages memory, storage, and cleanup of old data."""

    def __init__(
        self,
        temp_dir: Path,
        chat_history_dir: Path,
        max_temp_file_age_hours: int = 24,
        max_history_age_days: int = 30,
        max_archived_conversations: int = 100,
    ):
        """Initialize memory manager.

        Args:
            temp_dir: Directory for temporary files
            chat_history_dir: Directory for chat history
            max_temp_file_age_hours: Max age of temp files in hours before cleanup
            max_history_age_days: Max age of history files before archiving
            max_archived_conversations: Max number of archived conversations to keep
        """
        self.temp_dir = Path(temp_dir)
        self.chat_history_dir = Path(chat_history_dir)
        self.max_temp_file_age_hours = max_temp_file_age_hours
        self.max_history_age_days = max_history_age_days
        self.max_archived_conversations = max_archived_conversations

        # Create archive directory
        self.archive_dir = chat_history_dir.parent / "chat_history_archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Memory manager initialized")

    async def cleanup_temp_files(self) -> Dict[str, int]:
        """Clean up old temporary audio/data files.

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            "files_deleted": 0,
            "bytes_freed": 0,
            "errors": 0,
        }

        if not self.temp_dir.exists():
            return stats

        cutoff_time = datetime.now() - timedelta(hours=self.max_temp_file_age_hours)

        try:
            for file_path in self.temp_dir.iterdir():
                if not file_path.is_file():
                    continue

                try:
                    # Check file age
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        stats["files_deleted"] += 1
                        stats["bytes_freed"] += file_size
                        logger.debug(f"Deleted old temp file: {file_path.name}")

                except Exception as e:
                    logger.error(f"Error deleting temp file {file_path}: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
            stats["errors"] += 1

        if stats["files_deleted"] > 0:
            mb_freed = stats["bytes_freed"] / (1024 * 1024)
            logger.info(
                f"Cleanup: Deleted {stats['files_deleted']} temp files, "
                f"freed {mb_freed:.2f} MB"
            )

        return stats

    async def archive_old_conversations(self) -> Dict[str, int]:
        """Archive old chat history files to save space.

        Returns:
            Dictionary with archival statistics
        """
        stats = {
            "conversations_archived": 0,
            "bytes_saved": 0,
            "errors": 0,
        }

        if not self.chat_history_dir.exists():
            return stats

        cutoff_time = datetime.now() - timedelta(days=self.max_history_age_days)

        try:
            for history_file in self.chat_history_dir.glob("*.json"):
                try:
                    # Check file age
                    mtime = datetime.fromtimestamp(history_file.stat().st_mtime)

                    if mtime < cutoff_time:
                        # Load and compress the history
                        async with aiofiles.open(history_file, "r") as f:
                            content = await f.read()
                            history_data = json.loads(content)

                        # Create archive filename with timestamp
                        archive_name = (
                            f"{history_file.stem}_{mtime.strftime('%Y%m%d')}.json"
                        )
                        archive_path = self.archive_dir / archive_name

                        # Save to archive
                        async with aiofiles.open(archive_path, "w") as f:
                            await f.write(json.dumps(
                                {
                                    "channel_id": history_file.stem,
                                    "archived_at": datetime.now().isoformat(),
                                    "original_modified": mtime.isoformat(),
                                    "messages": history_data,
                                },
                                indent=2
                            ))

                        original_size = history_file.stat().st_size
                        history_file.unlink()

                        stats["conversations_archived"] += 1
                        stats["bytes_saved"] += original_size
                        logger.info(f"Archived conversation: {history_file.stem}")

                except Exception as e:
                    logger.error(f"Error archiving {history_file}: {e}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error during conversation archival: {e}")
            stats["errors"] += 1

        if stats["conversations_archived"] > 0:
            logger.info(
                f"Archived {stats['conversations_archived']} old conversations"
            )

        # Trim old archives if needed
        await self._trim_old_archives()

        return stats

    async def _trim_old_archives(self) -> None:
        """Remove oldest archives if exceeding max count."""
        try:
            archives = sorted(
                self.archive_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            if len(archives) > self.max_archived_conversations:
                for archive in archives[self.max_archived_conversations :]:
                    archive.unlink()
                    logger.debug(f"Removed old archive: {archive.name}")

        except Exception as e:
            logger.error(f"Error trimming archives: {e}")

    async def get_memory_stats(self) -> Dict[str, any]:
        """Get memory and storage statistics.

        Returns:
            Dictionary with memory statistics
        """
        stats = {
            "temp_files": 0,
            "temp_size_mb": 0,
            "history_files": 0,
            "history_size_mb": 0,
            "archived_files": 0,
            "archived_size_mb": 0,
        }

        try:
            # Temp files
            if self.temp_dir.exists():
                temp_files = list(self.temp_dir.glob("*"))
                stats["temp_files"] = len(temp_files)
                stats["temp_size_mb"] = (
                    sum(f.stat().st_size for f in temp_files if f.is_file())
                    / (1024 * 1024)
                )

            # History files
            if self.chat_history_dir.exists():
                history_files = list(self.chat_history_dir.glob("*.json"))
                stats["history_files"] = len(history_files)
                stats["history_size_mb"] = (
                    sum(f.stat().st_size for f in history_files) / (1024 * 1024)
                )

            # Archived files
            if self.archive_dir.exists():
                archived_files = list(self.archive_dir.glob("*.json"))
                stats["archived_files"] = len(archived_files)
                stats["archived_size_mb"] = (
                    sum(f.stat().st_size for f in archived_files) / (1024 * 1024)
                )

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")

        return stats

    async def compress_history(self, channel_id: int, max_messages: int = 20) -> bool:
        """Compress chat history by keeping only recent messages.

        Args:
            channel_id: Discord channel ID
            max_messages: Maximum messages to keep

        Returns:
            True if successful
        """
        history_file = self.chat_history_dir / f"{channel_id}.json"

        if not history_file.exists():
            return False

        try:
            async with aiofiles.open(history_file, "r") as f:
                content = await f.read()
                messages = json.loads(content)

            if len(messages) > max_messages:
                # Keep only the most recent messages
                trimmed = messages[-max_messages:]

                async with aiofiles.open(history_file, "w") as f:
                    await f.write(json.dumps(trimmed, indent=2))

                logger.info(
                    f"Compressed history for channel {channel_id}: "
                    f"{len(messages)} → {len(trimmed)} messages"
                )

            return True

        except Exception as e:
            logger.error(f"Error compressing history for channel {channel_id}: {e}")
            return False

    async def start_background_cleanup(self, interval_hours: int = 6):
        """Start background cleanup task.

        Args:
            interval_hours: Hours between cleanup runs
        """
        logger.info(f"Starting background cleanup (every {interval_hours}h)")

        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)

                logger.info("Running scheduled memory cleanup...")
                temp_stats = await self.cleanup_temp_files()
                archive_stats = await self.archive_old_conversations()

                logger.info(
                    f"Cleanup complete - Temp: {temp_stats['files_deleted']} files, "
                    f"Archived: {archive_stats['conversations_archived']} conversations"
                )

            except asyncio.CancelledError:
                logger.info("Background cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background cleanup: {e}")
                # Continue running despite errors
