"""Helper utilities for chat processing."""

import re
import logging
import discord
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class ChatHelpers:
    """Utility methods for chat text processing."""

    @staticmethod
    def replace_mentions_with_names(
        content: str, message: discord.Message, bot_user_id: int
    ) -> str:
        """Replace user mention IDs with readable usernames.

        Args:
            content: Message content with <@user_id> mentions
            message: Discord message object with mentions list
            bot_user_id: Bot's user ID to skip

        Returns:
            Content with mentions replaced as @username
        """
        if not message or not message.mentions:
            return content

        # Replace each user mention with their display name
        for user in message.mentions:
            # Skip bot mentions (already handled separately)
            if user.id == bot_user_id:
                continue

            # Replace <@user_id> with @username
            mention_pattern = f"<@{user.id}>"
            # Use display_name for server nicknames, fallback to name
            display_name = (
                user.display_name if hasattr(user, "display_name") else user.name
            )
            content = content.replace(mention_pattern, f"@{display_name}")

            # Also handle <!@user_id> format (mobile mentions)
            mention_pattern_mobile = f"<@!{user.id}>"
            content = content.replace(mention_pattern_mobile, f"@{display_name}")

        return content

    @staticmethod
    def restore_mentions(content: str, guild: discord.Guild) -> str:
        """Convert @Username mentions back to <@user_id> for Discord.

        This ensures that when the LLM outputs @Username, it gets converted to
        a proper Discord mention tag that is clickable.

        Args:
            content: Message content with @Username mentions
            guild: Discord guild to get member list from

        Returns:
            Content with @Username replaced by <@user_id>
        """
        if not guild or not content:
            return content

        # Get all members and sort by name length (descending) to prevent partial matches
        # e.g., "Rob" inside "Robert"
        members = sorted(guild.members, key=lambda m: len(m.display_name), reverse=True)

        for member in members:
            # Skip bots
            if member.bot:
                continue

            # Try display name first (server nickname)
            display_name = member.display_name
            content = content.replace(f"@{display_name}", f"<@{member.id}>")

            # Also try global username if different from display name
            if member.name != display_name:
                content = content.replace(f"@{member.name}", f"<@{member.id}>")

        return content

    @staticmethod
    def clean_for_tts(content: str, guild: discord.Guild) -> str:
        """Clean content for TTS by replacing mentions with natural names.

        This ensures that TTS pronounces "Username" instead of reading out
        "less than at one two three four five..."

        Args:
            content: Message content with <@user_id> or @Username mentions
            guild: Discord guild to get member list from

        Returns:
            Content with mentions replaced by natural names
        """
        if not guild or not content:
            return content

        # First, replace <@user_id> with display names
        for member in guild.members:
            # Skip bots
            if member.bot:
                continue

            # Replace <@ID> with display name
            mention_pattern = f"<@{member.id}>"
            content = content.replace(mention_pattern, member.display_name)

            # Also handle <@!ID> format (mobile mentions)
            mention_pattern_mobile = f"<@!{member.id}>"
            content = content.replace(mention_pattern_mobile, member.display_name)

        # Second, remove @ symbols from any remaining @Username patterns
        # This handles cases where LLM outputs @Username
        content = re.sub(r"@([A-Za-z0-9_]+)", r"\1", content)

        return content

    @staticmethod
    def clean_for_history(content: str) -> str:
        """Clean response content before saving to history.

        Removes:
        - TOOL: prefixes and their lines
        - Empty lines at start
        - Excessive whitespace

        Args:
            content: Raw LLM response

        Returns:
            Cleaned content suitable for history storage
        """
        if not content:
            return content

        # Remove TOOL: lines (e.g., "TOOL: get_current_time\n\n")
        content = re.sub(r"^TOOL:\s*\S+\s*\n+", "", content, flags=re.MULTILINE)

        # Remove any remaining tool call artifacts
        content = re.sub(r"\[TOOL_CALL:.*?\]", "", content)

        # Strip leading/trailing whitespace
        content = content.strip()

        return content

    @staticmethod
    def analyze_sentiment(text: str) -> dict:
        """Analyze sentiment of text.

        Returns:
            Dict with 'compound', 'pos', 'neg', 'neu' scores.
        """
        # Simple heuristic since NLTK/VADER usage might be missing
        text = text.lower()
        positive_words = {"love", "amazing", "good", "great", "excellent", "happy"}
        negative_words = {"bad", "terrible", "sad", "awful", "sorry", "hate"}

        pos = sum(1 for w in positive_words if w in text)
        neg = sum(1 for w in negative_words if w in text)

        compound = 0.0
        if pos > neg:
            compound = 0.5
        elif neg > pos:
            compound = -0.5

        return {"compound": compound, "pos": pos, "neg": neg, "neu": 1.0}

    @staticmethod
    def load_system_prompt(prompt_file: Path, default_prompt: str) -> str:
        """Load system prompt from file or use default.

        Args:
            prompt_file: Path to system prompt file
            default_prompt: Default prompt to use if file doesn't exist

        Returns:
            System prompt text
        """
        if prompt_file.exists():
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompt = f.read().strip()
                    if prompt:
                        logger.info(f"Loaded custom system prompt from {prompt_file}")
                        return prompt
            except Exception as e:
                logger.warning(f"Failed to load system prompt from file: {e}")

        return default_prompt

    @staticmethod
    def clean_response(content: str) -> str:
        """Clean LLM response (remove thinking tags, artifacts)."""
        if not content:
            return ""

        # Remove <think> blocks
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)

        # Sanitize mass mentions (prevent @everyone/@here pings)
        cleaned = cleaned.replace("@everyone", "@\u200beveryone")
        cleaned = cleaned.replace("@here", "@\u200bhere")

        # Remove empty lines
        cleaned = cleaned.strip()

        return cleaned

    @staticmethod
    def analyze_conversation_context(
        message: str, history: Optional[List[Dict]] = None
    ) -> str:
        """Analyze conversation context to determine response verbosity needs.

        Args:
            message: Current user message
            history: Recent conversation history (list of message dicts)

        Returns:
            Context type: "quick_reply", "casual_chat", "detailed_question", "storytelling"
        """
        import time

        start = time.time()

        if not message:
            return "casual_chat"

        message_lower = message.lower().strip()
        message_length = len(message)
        word_count = len(message.split())

        # 1. Quick Reply Detection (< 20 chars, simple responses)
        if message_length < 20 or word_count <= 3:
            # Short affirmations, greetings, simple questions
            quick_patterns = [
                "yes",
                "no",
                "ok",
                "thanks",
                "hi",
                "hello",
                "bye",
                "lol",
                "lmao",
                "nice",
                "cool",
                "wow",
            ]
            if any(pattern in message_lower for pattern in quick_patterns):
                logger.debug(
                    f"Context analysis: quick_reply ({(time.time() - start) * 1000:.1f}ms)"
                )
                return "quick_reply"

        # 2. Storytelling Detection (narrative keywords, descriptive language)
        storytelling_keywords = [
            "once upon",
            "tell me about",
            "story",
            "imagine",
            "what if",
            "describe",
            "explain how",
            "walk me through",
            "let me tell you",
            "happened when",
            "remember when",
            "back when",
            "there was",
        ]
        if any(keyword in message_lower for keyword in storytelling_keywords):
            logger.debug(
                f"Context analysis: storytelling ({(time.time() - start) * 1000:.1f}ms)"
            )
            return "storytelling"

        # 3. Detailed Question Detection (complex queries needing thorough answers)
        question_indicators = [
            "?",
            "how",
            "why",
            "what",
            "when",
            "where",
            "who",
            "which",
        ]
        has_question = any(ind in message_lower for ind in question_indicators)

        # Complex query words that trigger detailed_question even without question indicators
        complex_query_words = [
            "explain",
            "difference between",
            "compare",
            "analyze",
            "thoughts on",
            "opinion on",
            "what do you think",
            "how does",
            "why does",
            "tell me more",
            "meaning of",
            "what is",
            "what are",
            "how can",
            "why is",
        ]
        has_complex_query = any(word in message_lower for word in complex_query_words)

        # Check if it's a detailed question (either has question indicators OR complex query words)
        if has_question or has_complex_query:
            is_complex = (
                word_count
                > 5  # Reduced to catch medium questions like "Explain quantum computing"
                or message.count("?") > 1
                or has_complex_query  # Any complex query word makes it detailed
            )

            if is_complex:
                logger.debug(
                    f"Context analysis: detailed_question ({(time.time() - start) * 1000:.1f}ms)"
                )
                return "detailed_question"

        # 4. History Analysis (ongoing deep discussion vs casual banter)
        if history and len(history) > 2:
            # Check recent message lengths for conversation depth
            recent_messages = history[-5:] if len(history) >= 5 else history
            avg_length = sum(
                len(msg.get("content", "")) for msg in recent_messages
            ) / len(recent_messages)

            # Deep discussion: average message length > 100 chars
            if avg_length > 100:
                logger.debug(
                    f"Context analysis: detailed_question (deep discussion, {(time.time() - start) * 1000:.1f}ms)"
                )
                return "detailed_question"

        # 5. Default: Casual Chat
        logger.debug(
            f"Context analysis: casual_chat ({(time.time() - start) * 1000:.1f}ms)"
        )
        return "casual_chat"

    @staticmethod
    def calculate_max_tokens_for_context(
        context_type: str, persona_config: Optional[Dict] = None
    ) -> int:
        """Calculate max tokens based on conversation context type.

        Args:
            context_type: Context type from analyze_conversation_context()
            persona_config: Optional persona configuration with verbosity_by_context

        Returns:
            Max tokens for response generation
        """
        from config import Config

        # Default token mappings (conservative to prevent overflow)
        default_mappings = {
            "quick_reply": 75,  # Short, punchy responses
            "casual_chat": 150,  # Standard conversation
            "detailed_question": 300,  # Thorough explanations
            "storytelling": 450,  # Rich narratives
        }

        # Check persona config for custom verbosity settings
        if persona_config and "verbosity_by_context" in persona_config:
            verbosity_config = persona_config["verbosity_by_context"]

            # Map verbosity levels to token counts
            verbosity_to_tokens = {
                "very_short": 50,
                "short": 100,
                "medium": 200,
                "long": 350,
                "very_long": 500,
            }

            # Get verbosity level for this context
            verbosity_level = verbosity_config.get(context_type)
            logger.debug(f"Context: {context_type}, Verbosity level: {verbosity_level}")

            if verbosity_level and verbosity_level in verbosity_to_tokens:
                max_tokens = verbosity_to_tokens[verbosity_level]
                logger.debug(f"Using custom tokens: {max_tokens}")
            else:
                max_tokens = default_mappings.get(context_type, 150)
                logger.debug(f"Using default tokens: {max_tokens}")
        else:
            max_tokens = default_mappings.get(context_type, 150)
            logger.debug(f"No persona config, using default tokens: {max_tokens}")

        # Respect global ceiling from Config
        ceiling = Config.OLLAMA_MAX_TOKENS
        if max_tokens > ceiling:
            logger.debug(
                f"Capping max_tokens from {max_tokens} to {ceiling} (Config.OLLAMA_MAX_TOKENS)"
            )
            max_tokens = ceiling

        logger.debug(f"Max tokens for {context_type}: {max_tokens}")
        return max_tokens

    @staticmethod
    def calculate_max_tokens(messages: list, model_name: str) -> int:
        """Calculate optimal max tokens for the response.

        Legacy method - delegates to context-aware calculation if possible.
        """
        from config import Config

        # Try to extract context from messages
        if messages and len(messages) > 0:
            # Find last user message
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break

            if last_user_msg:
                # Analyze context
                context_type = ChatHelpers.analyze_conversation_context(
                    last_user_msg,
                    history=messages[:-1],  # Everything except current message
                )
                return ChatHelpers.calculate_max_tokens_for_context(context_type)

        # Fallback to config default
        return Config.OLLAMA_MAX_TOKENS
