"""Conversation summarization service with RAG storage for long-term memory."""
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json
import aiofiles

from services.ollama import OllamaService
from services.rag import RAGService

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """Summarizes conversations and stores them in RAG for long-term memory recall."""

    def __init__(
        self,
        ollama: OllamaService,
        rag: RAGService,
        summary_dir: Path,
        min_messages_for_summary: int = 10,
    ):
        """Initialize conversation summarizer.

        Args:
            ollama: Ollama service for generating summaries
            rag: RAG service for storing summaries
            summary_dir: Directory to store summary files
            min_messages_for_summary: Minimum messages needed to create summary
        """
        self.ollama = ollama
        self.rag = rag
        self.summary_dir = Path(summary_dir)
        self.min_messages_for_summary = min_messages_for_summary

        self.summary_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Conversation summarizer initialized")

    async def summarize_conversation(
        self,
        messages: List[Dict[str, str]],
        channel_id: int,
        participants: Optional[List[str]] = None,
    ) -> Optional[Dict[str, any]]:
        """Summarize a conversation using AI.

        Args:
            messages: List of message dicts
            channel_id: Discord channel ID
            participants: List of participant names

        Returns:
            Summary dict or None if failed
        """
        if len(messages) < self.min_messages_for_summary:
            logger.debug(
                f"Not enough messages to summarize ({len(messages)} < {self.min_messages_for_summary})"
            )
            return None

        try:
            # Build conversation text with user attribution
            conversation_text = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                username = msg.get("username", "User")

                if role == "user":
                    conversation_text.append(f"{username}: {content}")
                elif role == "assistant":
                    conversation_text.append(f"Assistant: {content}")

            full_conversation = "\n".join(conversation_text)

            # Create summarization prompt
            summary_prompt = f"""Analyze and summarize this conversation. Include:

1. Main topics discussed
2. Key points and decisions made
3. Important facts or information shared
4. Emotional tone and relationship dynamics
5. Any questions that were answered
6. Notable quotes or memorable moments

Be concise but comprehensive. Focus on information that would be valuable for future reference.

CONVERSATION:
{full_conversation}

SUMMARY:"""

            # Generate summary using AI
            summary_text = await self.ollama.generate(
                summary_prompt,
                system_prompt="You are an expert at analyzing and summarizing conversations. "
                "Create clear, structured summaries that capture the essence and key information.",
            )
            
            # Clean thinking process
            from utils.response_validator import ResponseValidator
            summary_text = ResponseValidator.clean_thinking_process(summary_text)

            # Create summary metadata
            summary_data = {
                "channel_id": channel_id,
                "timestamp": datetime.now().isoformat(),
                "message_count": len(messages),
                "participants": participants or [],
                "summary": summary_text,
                "first_message_time": messages[0].get("timestamp") if messages else None,
                "last_message_time": messages[-1].get("timestamp") if messages else None,
            }

            logger.info(
                f"Generated summary for channel {channel_id}: {len(messages)} messages"
            )
            return summary_data

        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return None

    async def save_summary_to_rag(
        self, summary_data: Dict[str, any], channel_id: int
    ) -> bool:
        """Save conversation summary to RAG system for future recall.

        Args:
            summary_data: Summary dictionary
            channel_id: Discord channel ID

        Returns:
            True if successful
        """
        try:
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{channel_id}_{timestamp}.txt"

            # Format summary for RAG storage
            content_parts = [
                f"Conversation Summary - Channel {channel_id}",
                f"Date: {summary_data['timestamp']}",
                f"Participants: {', '.join(summary_data.get('participants', []))}",
                f"Messages: {summary_data['message_count']}",
                "",
                "SUMMARY:",
                summary_data["summary"],
                "",
                f"[Stored: {datetime.now().isoformat()}]",
            ]

            content = "\n".join(content_parts)

            # Add to RAG system
            success = await self.rag.add_document(filename, content)

            if success:
                logger.info(f"Saved conversation summary to RAG: {filename}")
            else:
                logger.error(f"Failed to save summary to RAG: {filename}")

            return success

        except Exception as e:
            logger.error(f"Error saving summary to RAG: {e}")
            return False

    async def save_summary_to_file(
        self, summary_data: Dict[str, any], channel_id: int
    ) -> bool:
        """Save summary to local file system.

        Args:
            summary_data: Summary dictionary
            channel_id: Discord channel ID

        Returns:
            True if successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summary_{channel_id}_{timestamp}.json"
            filepath = self.summary_dir / filename

            async with aiofiles.open(filepath, "w") as f:
                await f.write(json.dumps(summary_data, indent=2))

            logger.info(f"Saved summary to file: {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving summary to file: {e}")
            return False

    async def summarize_and_store(
        self,
        messages: List[Dict[str, str]],
        channel_id: int,
        participants: Optional[List[str]] = None,
        store_in_rag: bool = True,
        store_in_file: bool = True,
    ) -> Optional[Dict[str, any]]:
        """Summarize conversation and store in RAG and/or files.

        Args:
            messages: List of message dicts
            channel_id: Discord channel ID
            participants: List of participant names
            store_in_rag: Whether to store in RAG system
            store_in_file: Whether to store in file system

        Returns:
            Summary data dict or None
        """
        summary_data = await self.summarize_conversation(
            messages, channel_id, participants
        )

        if not summary_data:
            return None

        # Store in RAG for retrieval
        if store_in_rag:
            await self.save_summary_to_rag(summary_data, channel_id)

        # Store in file for backup/archival
        if store_in_file:
            await self.save_summary_to_file(summary_data, channel_id)

        return summary_data

    async def retrieve_relevant_memories(
        self, query: str, max_results: int = 3
    ) -> List[str]:
        """Retrieve relevant past conversation summaries based on query.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of relevant summary texts
        """
        try:
            # Search RAG for relevant summaries
            results = self.rag.search(query, top_k=max_results)

            memories = []
            for result in results:
                content = result.get("content", "")
                relevance = result.get("relevance_score", 0)

                if relevance > 0.1:  # Minimum relevance threshold
                    memories.append(content)

            logger.debug(f"Retrieved {len(memories)} relevant memories for query")
            return memories

        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            return []

    async def build_memory_context(
        self, current_message: str, max_length: int = 500
    ) -> str:
        """Build context from past conversations relevant to current message.

        Args:
            current_message: Current user message
            max_length: Maximum character length of context

        Returns:
            Formatted memory context string
        """
        memories = await self.retrieve_relevant_memories(current_message)

        if not memories:
            return ""

        context_parts = ["[Relevant past conversations:]"]

        total_length = len(context_parts[0])
        for memory in memories:
            # Extract just the summary part
            if "SUMMARY:" in memory:
                summary_part = memory.split("SUMMARY:")[1].split("[Stored:")[0].strip()
            else:
                summary_part = memory[:200]  # Fallback to first 200 chars

            if total_length + len(summary_part) + 10 < max_length:
                context_parts.append(f"- {summary_part[:200]}...")
                total_length += len(summary_part) + 10
            else:
                break

        if len(context_parts) == 1:  # Only header, no memories added
            return ""

        return "\n".join(context_parts)

    async def list_summaries(self, channel_id: Optional[int] = None) -> List[Dict[str, any]]:
        """List all stored conversation summaries.

        Args:
            channel_id: Optional channel ID to filter by

        Returns:
            List of summary metadata
        """
        summaries = []

        try:
            pattern = (
                f"summary_{channel_id}_*.json" if channel_id else "summary_*.json"
            )

            # Glob is synchronous but fast for directory listing. Reading files should be async.
            for summary_file in self.summary_dir.glob(pattern):
                try:
                    async with aiofiles.open(summary_file, "r") as f:
                        content = await f.read()
                        summary_data = json.loads(content)
                        summaries.append(
                            {
                                "filename": summary_file.name,
                                "channel_id": summary_data.get("channel_id"),
                                "timestamp": summary_data.get("timestamp"),
                                "message_count": summary_data.get("message_count"),
                                "participants": summary_data.get("participants", []),
                            }
                        )
                except Exception as e:
                    logger.error(f"Error loading summary {summary_file}: {e}")

            # Sort by timestamp (most recent first)
            summaries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        except Exception as e:
            logger.error(f"Error listing summaries: {e}")

        return summaries
