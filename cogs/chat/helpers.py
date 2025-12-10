"""Helper utilities for chat processing."""

import re
import logging
import discord
from pathlib import Path

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
        content = re.sub(r'^TOOL:\s*\S+\s*\n+', '', content, flags=re.MULTILINE)
        
        # Remove any remaining tool call artifacts
        content = re.sub(r'\[TOOL_CALL:.*?\]', '', content)
        
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
        if pos > neg: compound = 0.5
        elif neg > pos: compound = -0.5
        
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
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Sanitize mass mentions (prevent @everyone/@here pings)
        cleaned = cleaned.replace("@everyone", "@\u200beveryone")
        cleaned = cleaned.replace("@here", "@\u200bhere")
        
        # Remove empty lines
        cleaned = cleaned.strip()
        
        return cleaned

    @staticmethod
    def clean_for_history(content: str) -> str:
        """Clean response for history storage."""
        return ChatHelpers.clean_response(content)

    @staticmethod
    def calculate_max_tokens(messages: list, model_name: str) -> int:
        """Calculate optimal max tokens for the response."""
        # For now, just return the configured default.
        # In future, this could dynamically adjust based on context length or model interaction.
        from config import Config
        return Config.OLLAMA_MAX_TOKENS
