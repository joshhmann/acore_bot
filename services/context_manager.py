"""Context manager for token-aware prompt construction."""

import logging
from typing import List, Dict, Optional, Tuple
import tiktoken

from config import Config
from services.persona_system import CompiledPersona
from services.lorebook_service import LoreEntry
from services.rag import RAGService

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages the construction of the LLM context window with token budgeting."""

    def __init__(self):
        """Initialize context manager."""
        # Cache encoders to avoid re-initialization
        self._encoders = {}

    def _get_encoder(self, model_name: str):
        """Get tiktoken encoder for a model."""
        if model_name in self._encoders:
            return self._encoders[model_name]

        try:
            # Try to map common model names to tiktoken encodings
            if "gpt-4" in model_name:
                encoding = tiktoken.encoding_for_model("gpt-4")
            elif "gpt-3.5" in model_name:
                encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            else:
                # Default to cl100k_base (used by GPT-3.5/4/Llama3 usually good approximation)
                encoding = tiktoken.get_encoding("cl100k_base")

            self._encoders[model_name] = encoding
            return encoding
        except Exception as e:
            logger.warning(f"Could not get specific encoder for {model_name}, using default: {e}")
            return tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str, model_name: str = "gpt-3.5-turbo") -> int:
        """Count tokens in a string."""
        if not text:
            return 0
        encoder = self._get_encoder(model_name)
        return len(encoder.encode(text))

    def count_message_tokens(self, messages: List[Dict[str, str]], model_name: str = "gpt-3.5-turbo") -> int:
        """Count tokens in a list of messages."""
        count = 0
        encoder = self._get_encoder(model_name)

        for msg in messages:
            # Add tokens for message overhead (role + content)
            # This is an approximation; different APIs have different overheads
            count += 4  # ~4 tokens per message for overhead
            count += len(encoder.encode(msg.get("content", "")))
            if "name" in msg:
                count += len(encoder.encode(msg["name"]))

        return count

    async def build_context(
        self,
        persona: CompiledPersona,
        history: List[Dict[str, str]],
        model_name: str,
        lore_entries: List[LoreEntry] = None,
        rag_content: str = None,
        user_context: str = None,
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Build the final list of messages for the LLM, respecting the token limit.

        Strategy:
        1. System Prompt (Highest Priority)
        2. User Context / RAG (High Priority)
        3. Lorebook Entries (High Priority)
        4. Chat History (Fill remaining budget, newest to oldest)

        Args:
            persona: Active compiled persona
            history: Full chat history
            model_name: Name of the model (for context limit)
            lore_entries: Active lorebook entries
            rag_content: Content retrieved from RAG
            user_context: User profile information
            max_tokens: Override config limit

        Returns:
            List of messages ready for the API
        """
        # Determine Token Limit
        limit = max_tokens
        if not limit:
            # Check model specific limit first
            limit = Config.MODEL_CONTEXT_LIMITS.get(model_name)
        if not limit:
            # Fallback to global default
            limit = Config.MAX_CONTEXT_TOKENS

        # Reserve some tokens for the generation response (output)
        # e.g., if model is 8k, we want to input max 7.5k to leave room for reply
        max_input_tokens = int(limit * 0.9)

        # 1. Build System Prompt Message
        system_content = persona.system_prompt

        # Inject User Context / RAG into System Prompt or as separate System msg
        # Usually appending to system prompt is cleaner for "Context"
        context_additions = []
        if user_context:
            context_additions.append(f"\n[USER INFO]\n{user_context}")

        if rag_content:
            context_additions.append(f"\n[KNOWLEDGE]\n{rag_content}")

        # Inject Lore Entries
        if lore_entries:
            lore_text = "\n[WORLD INFO]\n" + "\n".join([e.content for e in lore_entries])
            context_additions.append(lore_text)

        # Combine all system-level content
        full_system_content = system_content + "\n".join(context_additions)

        # Initial messages list
        final_messages = [
            {"role": "system", "content": full_system_content}
        ]

        # Check budget usage so far
        current_tokens = self.count_message_tokens(final_messages, model_name)
        remaining_tokens = max_input_tokens - current_tokens

        if remaining_tokens <= 0:
            logger.warning("System prompt exceeds token limit! Truncating not implemented yet.")
            return final_messages

        # 2. Add Chat History (Newest first, then reverse)
        history_to_include = []

        # Always try to include the very last message (user's new input)
        # Assuming 'history' includes the new user message at the end

        reversed_history = list(reversed(history))

        for msg in reversed_history:
            msg_tokens = self.count_message_tokens([msg], model_name)

            if remaining_tokens - msg_tokens >= 0:
                history_to_include.append(msg)
                remaining_tokens -= msg_tokens
            else:
                logger.info(f"Context limit reached. Dropping {len(history) - len(history_to_include)} older messages.")
                break

        # Re-reverse to get chronological order
        final_messages.extend(reversed(history_to_include))

        return final_messages
