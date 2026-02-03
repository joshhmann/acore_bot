"""Conversation archival and RAG integration service.

This service manages the archival lifecycle of bot-to-bot conversations:
- Auto-archive completed conversations after 24 hours (review window)
- Index conversation content to RAG for searchability
- Clean up old archives after 30 days (retention policy)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from services.conversation.persistence import ConversationPersistence
from services.conversation.state import ConversationState, ConversationStatus

logger = logging.getLogger(__name__)


class ConversationArchivalService:
    """Service for managing conversation archival and RAG integration.

    Features:
    - Auto-archive completed conversations after 24-hour review window
    - Index conversations to RAG for searchability
    - Clean up old archives after 30-day retention period
    - Background task scheduling for maintenance
    """

    # Configuration constants
    REVIEW_WINDOW_HOURS = 24  # Hours before archiving completed conversations
    RETENTION_DAYS = 30  # Days to keep archived conversations
    ARCHIVAL_CHECK_INTERVAL_MINUTES = 60  # How often to check for archival

    def __init__(
        self,
        persistence: ConversationPersistence,
        rag_service: Optional[Any] = None,
        history_manager: Optional[Any] = None,
    ):
        """Initialize the archival service.

        Args:
            persistence: ConversationPersistence instance for archive operations
            rag_service: Optional RAGService for indexing conversations
            history_manager: Optional ChatHistoryManager for conversation messages
        """
        self.persistence = persistence
        self.rag_service = rag_service
        self.history_manager = history_manager

        self._archival_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Track archival statistics
        self._stats = {
            "archived_count": 0,
            "indexed_count": 0,
            "cleaned_count": 0,
            "errors": 0,
            "last_archival_check": None,
            "last_cleanup": None,
        }

    async def start(self):
        """Start background archival and cleanup tasks."""
        if self._running:
            return

        self._running = True
        self._archival_task = asyncio.create_task(self._archival_worker())
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())

        logger.info("Conversation archival service started")

    async def stop(self):
        """Stop background tasks gracefully."""
        self._running = False

        if self._archival_task:
            self._archival_task.cancel()
            try:
                await self._archival_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Conversation archival service stopped")

    async def _archival_worker(self):
        """Background worker that periodically checks for conversations to archive."""
        while self._running:
            try:
                await self.auto_archive_completed()
                self._stats["last_archival_check"] = datetime.now().isoformat()
            except Exception as e:
                logger.error(f"Error in archival worker: {e}")
                self._stats["errors"] += 1

            # Wait for next check interval
            await asyncio.sleep(self.ARCHIVAL_CHECK_INTERVAL_MINUTES * 60)

    async def _cleanup_worker(self):
        """Background worker that periodically cleans up old archives."""
        # Start first cleanup after 1 hour, then daily
        await asyncio.sleep(3600)

        while self._running:
            try:
                removed = await self.cleanup_old_archives()
                self._stats["last_cleanup"] = datetime.now().isoformat()
                if removed > 0:
                    logger.info(f"Cleaned up {removed} old conversation archives")
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
                self._stats["errors"] += 1

            # Run cleanup once per day
            await asyncio.sleep(86400)

    async def auto_archive_completed(self) -> int:
        """Archive completed conversations that have passed the review window.

        Returns:
            Number of conversations archived
        """
        archived_count = 0
        cutoff_time = datetime.now() - timedelta(hours=self.REVIEW_WINDOW_HOURS)

        try:
            # List all active conversations
            active_ids = await self.persistence.list_active()

            for conversation_id in active_ids:
                try:
                    # Load conversation state
                    state = await self.persistence.load(conversation_id)
                    if not state:
                        continue

                    # Check if conversation is completed and past review window
                    if state.status != ConversationStatus.COMPLETED:
                        continue

                    if not state.ended_at:
                        continue

                    if state.ended_at > cutoff_time:
                        # Still in review window
                        continue

                    # Archive the conversation
                    success = await self.persistence.archive(conversation_id)
                    if success:
                        archived_count += 1
                        self._stats["archived_count"] += 1
                        logger.info(f"Archived conversation {conversation_id}")

                        # Index to RAG if available
                        if self.rag_service:
                            await self.index_to_rag(state)

                except Exception as e:
                    logger.error(
                        f"Failed to archive conversation {conversation_id}: {e}"
                    )
                    self._stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error during auto-archive: {e}")
            self._stats["errors"] += 1

        return archived_count

    async def index_to_rag(self, state: ConversationState) -> bool:
        """Index a conversation to RAG for searchability.

        Args:
            state: Conversation state to index

        Returns:
            True if indexed successfully
        """
        if not self.rag_service:
            logger.debug("RAG service not available, skipping indexing")
            return False

        try:
            # Build searchable content from conversation
            conversation_text = self._build_conversation_text(state)

            if not conversation_text:
                logger.warning(
                    f"No content to index for conversation {state.conversation_id}"
                )
                return False

            # Create metadata for the conversation
            metadata = {
                "conversation_id": state.conversation_id,
                "participants": ",".join(state.participants),
                "topic": state.topic,
                "turn_count": state.turn_count,
                "started_at": state.started_at.isoformat()
                if state.started_at
                else None,
                "ended_at": state.ended_at.isoformat() if state.ended_at else None,
                "termination_reason": state.termination_reason,
                "source": "bot_conversation",
            }

            # Add to RAG as a document
            filename = f"conversation_{state.conversation_id}.txt"
            success = await self.rag_service.add_document(
                filename=filename,
                content=conversation_text,
                category="conversations",
            )

            if success:
                self._stats["indexed_count"] += 1
                logger.info(f"Indexed conversation {state.conversation_id} to RAG")

                # Also index individual messages if history manager available
                if self.history_manager:
                    await self._index_messages_to_rag(state)

            return success

        except Exception as e:
            logger.error(
                f"Failed to index conversation {state.conversation_id} to RAG: {e}"
            )
            self._stats["errors"] += 1
            return False

    def _build_conversation_text(self, state: ConversationState) -> str:
        """Build searchable text from conversation state.

        Args:
            state: Conversation state

        Returns:
            Formatted conversation text
        """
        lines = [
            f"Conversation: {state.conversation_id}",
            f"Topic: {state.topic}",
            f"Participants: {', '.join(state.participants)}",
            f"Turns: {state.turn_count}",
            "",
            "Messages:",
        ]

        for msg in state.messages:
            timestamp = (
                msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if msg.timestamp
                else "Unknown"
            )
            lines.append(f"[{timestamp}] {msg.speaker}: {msg.content}")

        return "\n".join(lines)

    async def _index_messages_to_rag(self, state: ConversationState):
        """Index individual messages to RAG for granular search.

        Args:
            state: Conversation state
        """
        if not self.rag_service:
            return

        try:
            for i, msg in enumerate(state.messages):
                # Create unique message ID
                message_id = f"{state.conversation_id}_msg_{i}"

                # Build message content with context
                content = f"""
Conversation: {state.conversation_id}
Topic: {state.topic}
Speaker: {msg.speaker}
Message: {msg.content}
                """.strip()

                metadata = {
                    "conversation_id": state.conversation_id,
                    "speaker": msg.speaker,
                    "turn_number": msg.turn_number,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "source": "bot_conversation_message",
                }

                # Use index_discord_message method if available
                if hasattr(self.rag_service, "index_discord_message"):
                    await self.rag_service.index_discord_message(
                        message_id=message_id,
                        content=content,
                        metadata=metadata,
                    )

        except Exception as e:
            logger.error(
                f"Failed to index messages for conversation {state.conversation_id}: {e}"
            )

    async def cleanup_old_archives(self, max_age_days: Optional[int] = None) -> int:
        """Clean up archived conversations older than retention period.

        Args:
            max_age_days: Override default retention period (optional)

        Returns:
            Number of archives removed
        """
        retention_days = max_age_days or self.RETENTION_DAYS

        try:
            removed = await self.persistence.cleanup_old(retention_days)
            self._stats["cleaned_count"] += removed
            return removed

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            self._stats["errors"] += 1
            return 0

    async def search_conversations(
        self,
        query: str,
        top_k: int = 5,
        participant: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search archived conversations using RAG.

        Args:
            query: Search query
            top_k: Number of results to return
            participant: Optional filter by participant name

        Returns:
            List of search results with conversation metadata
        """
        if not self.rag_service:
            logger.warning("RAG service not available for conversation search")
            return []

        try:
            # Build filters
            filters = {"source": "bot_conversation"}
            if participant:
                filters["participants"] = participant

            # Search in conversations category
            results = self.rag_service.search(
                query=query,
                top_k=top_k,
                category="conversations",
                filters=filters if participant else None,
            )

            return results

        except Exception as e:
            logger.error(f"Error searching conversations: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get archival service statistics.

        Returns:
            Dictionary of statistics
        """
        return self._stats.copy()

    async def archive_conversation_now(self, conversation_id: str) -> bool:
        """Force immediate archival of a specific conversation.

        Args:
            conversation_id: ID of conversation to archive

        Returns:
            True if archived successfully
        """
        try:
            state = await self.persistence.load(conversation_id)
            if not state:
                logger.warning(f"Conversation {conversation_id} not found")
                return False

            # Archive via persistence
            success = await self.persistence.archive(conversation_id)
            if success:
                self._stats["archived_count"] += 1
                logger.info(f"Manually archived conversation {conversation_id}")

                # Index to RAG
                if self.rag_service:
                    await self.index_to_rag(state)

            return success

        except Exception as e:
            logger.error(f"Failed to archive conversation {conversation_id}: {e}")
            self._stats["errors"] += 1
            return False

    async def restore_conversation(
        self, conversation_id: str
    ) -> Optional[ConversationState]:
        """Restore an archived conversation to active status.

        Args:
            conversation_id: ID of conversation to restore

        Returns:
            Restored conversation state or None
        """
        try:
            # Try to load (will check both active and archive)
            state = await self.persistence.load(conversation_id)
            if not state:
                logger.warning(f"Conversation {conversation_id} not found")
                return None

            # If already active, just return
            archive_path = self.persistence.archive_dir / f"{conversation_id}.jsonl.gz"
            if not archive_path.exists():
                return state

            # Move from archive to active
            active_path = self.persistence.active_dir / f"{conversation_id}.jsonl"

            import gzip
            import aiofiles

            async with aiofiles.open(archive_path, "rb") as f:
                content = await f.read()
                decompressed = gzip.decompress(content)

            async with aiofiles.open(active_path, "wb") as f:
                await f.write(decompressed)

            archive_path.unlink()

            logger.info(f"Restored conversation {conversation_id} from archive")
            return state

        except Exception as e:
            logger.error(f"Failed to restore conversation {conversation_id}: {e}")
            return None
