"""Context builder for chat responses.

This module handles constructing the system prompt and context (history, profiles, memory) for the LLM.
"""

import logging
from typing import List, Optional, Dict, Any
import discord
from discord.ext import commands

from config import Config
from utils.system_context import SystemContextProvider

logger = logging.getLogger(__name__)

class ContextBuilder:
    def __init__(self, cog: commands.Cog):
        """Initialize context builder.
        
        Args:
            cog: The ChatCog instance containing services and state
        """
        self.cog = cog
        
    async def build_context(
        self, 
        user: discord.User,
        channel: discord.TextChannel,
        user_content: str, 
        history: List[Dict[str, str]],
        suggested_style: Optional[str] = None
    ) -> str:
        """Build the full system prompt with context.
        
        Args:
            user: The user interacting with the bot
            channel: The channel the interaction is in
            user_content: The content of the user's message
            history: Conversation history
            suggested_style: Style suggestion from decision engine
            
        Returns:
            Complete system prompt string with injected context
        """
        user_id = user.id
        channel_id = channel.id
        
        # Build system prompt with context (TIME FIRST so it's most prominent)
        context_parts = [SystemContextProvider.get_compact_context()]

        # Add multi-user context
        multi_user_context = self.cog.history.build_multi_user_context(history)
        if multi_user_context:
            context_parts.append(f"\n[Context: {multi_user_context}]")

        # Add user profile context if enabled
        if self.cog.user_profiles and Config.USER_CONTEXT_IN_CHAT:
             await self._add_user_profile_context(context_parts, user)

        # Add affection/relationship context if enabled
        if self.cog.user_profiles and Config.USER_AFFECTION_ENABLED:
            affection_context = self.cog.user_profiles.get_affection_context(user_id)
            if affection_context:
                context_parts.append(f"\n[Relationship: {affection_context}]")

        # Add memory recall from past conversations
        if self.cog.summarizer:
            memory_context = await self.cog.summarizer.build_memory_context(user_content)
            if memory_context:
                context_parts.append(f"\n{memory_context}")

        # Add RAG context from documents (if enabled and has documents)
        if self.cog.rag and Config.RAG_IN_CHAT and self.cog.rag.is_enabled():
            self._add_rag_context(context_parts, user_content)

        # Add emotional state context
        emotional_context = self.cog.enhancer.get_emotional_context()
        if emotional_context:
            context_parts.append(f"\n[{emotional_context}]")

        # Track conversation topics for callbacks and add callback prompts
        if self.cog.callbacks:
            await self._handle_callbacks(context_parts, channel_id, user_content, user.name)

        # Track message rhythm and add rhythm context
        if self.cog.naturalness:
            self._add_naturalness_context(context_parts, channel, len(user_content))

        # Add web search results
        if self.cog.web_search:
            await self._add_web_search_context(context_parts, user_content)

        # Add mood context
        if self.cog.naturalness and Config.MOOD_SYSTEM_ENABLED:
            mood_context = self.cog.naturalness.get_mood_context()
            if mood_context:
                context_parts.append(f"\n{mood_context}")

        # Add user-specific adaptation guidance
        if self.cog.pattern_learner:
            adaptation_guidance = self.cog.pattern_learner.get_adaptation_guidance(user_id)
            if adaptation_guidance:
                context_parts.append(f"\n[User Adaptation: {adaptation_guidance}]")
                logger.debug(f"Added adaptation guidance for user {user.id}")

        # Add AI Decision Engine style guidance
        if suggested_style:
            self._add_style_guidance(context_parts, suggested_style)

        # Add response style guidance for natural conversation
        self._add_conversational_style_guide(context_parts)

        # Inject all context into system prompt (CHARACTER FIRST, then context)
        context_injected_prompt = (
            f"{self.cog.system_prompt}\n\n{''.join(context_parts)}"
        )
        
        return context_injected_prompt

    async def _add_user_profile_context(self, context_parts: List[str], user: discord.User):
        """Add user profile and special instructions."""
        user_context = await self.cog.user_profiles.get_user_context(user.id)
        if user_context and user_context != "New user - no profile information yet.":
            # Check for behavioral instructions in user profile
            profile = await self.cog.user_profiles.load_profile(user.id)
            special_instructions = []

            # Look for "when you see" or "always say" type facts
            for fact_entry in profile.get("facts", []):
                # Handle both dict (new format) and string (legacy format)
                if isinstance(fact_entry, dict):
                    fact_text = fact_entry.get("fact", "")
                else:
                    fact_text = str(fact_entry)

                fact_lower = fact_text.lower()

                # Check for instructions
                if any(keyword in fact_lower for keyword in [
                    "when you see", "always say", "greet with",
                    "call them", "respond with", "call me"
                ]):
                    special_instructions.append(fact_text)

            # If there are special instructions, put them at the VERY TOP
            if special_instructions:
                instruction_text = "\n".join([f"- {inst}" for inst in special_instructions])
                context_parts.insert(
                    0,
                    f"\n[CRITICAL USER-SPECIFIC INSTRUCTIONS - FOLLOW EXACTLY:\n{instruction_text}\n]",
                )

            # Add general user context
            context_parts.append(f"\n[User Info: {user_context}]")

    def _add_rag_context(self, context_parts: List[str], user_content: str):
        """Add RAG context."""
        # Boost documents matching the current persona
        persona_boost = None
        if self.cog.current_persona:
            # Use explicitly configured category or fallback to persona name
            persona_boost = (
                self.cog.current_persona.rag_boost_category
                or self.cog.current_persona.name
            )

        rag_context = self.cog.rag.get_context(
            user_content, max_length=1000, boost_category=persona_boost
        )
        if rag_context:
            # CRITICAL: Insert RAG context at the VERY BEGINNING of context_parts
            context_parts.insert(
                0,
                f"\n[CRITICAL KNOWLEDGE - USE THIS TO ANSWER:\n{rag_context}\n]",
            )

    async def _handle_callbacks(self, context_parts: List[str], channel_id: int, message_content: str, user_name: str):
        """Track topics and get callback prompts."""
        await self.cog.callbacks.track_conversation_topic(
            channel_id, message_content, str(user_name)
        )

        # Check for callback opportunities
        callback_prompt = await self.cog.callbacks.get_callback_opportunity(
            channel_id, message_content
        )
        if callback_prompt:
            context_parts.append(f"\n{callback_prompt}")

        # Add recent conversation context
        recent_context = await self.cog.callbacks.get_recent_context(channel_id)
        if recent_context:
            context_parts.append(f"\n{recent_context}")

    def _add_naturalness_context(self, context_parts: List[str], channel: discord.TextChannel, msg_len: int):
        """Add rhythm and voice context."""
        self.cog.naturalness.track_message_rhythm(channel.id, msg_len)

        # Add rhythm-based style guidance
        rhythm_prompt = self.cog.naturalness.get_rhythm_style_prompt(channel.id)
        if rhythm_prompt:
            context_parts.append(f"\n{rhythm_prompt}")

        # Add voice context if applicable
        if channel.guild:
            voice_context = self.cog.naturalness.get_voice_context(channel.guild)
            if voice_context:
                context_parts.append(f"\n{voice_context}")

    async def _add_web_search_context(self, context_parts: List[str], message_content: str):
        """Add web search results."""
        if await self.cog.web_search.should_search(message_content):
            try:
                search_context = await self.cog.web_search.get_context(
                    message_content, max_length=800
                )
                if search_context:
                    context_parts.append(
                        f"\n\n{'=' * 60}\n[REAL-TIME WEB SEARCH RESULTS - READ THIS EXACTLY]\n{'=' * 60}\n{search_context}\n{'=' * 60}\n[END OF WEB SEARCH RESULTS]\n{'=' * 60}\n\n[CRITICAL INSTRUCTIONS - VIOLATION WILL BE DETECTED]\n1. You MUST ONLY cite information that appears EXACTLY in the search results above\n2. COPY the exact URLs shown - DO NOT modify or create new ones\n3. If search results are irrelevant (e.g., wrong topic, unrelated content), tell the user: 'The search didn't return relevant results'\n4. DO NOT invent Steam pages, Reddit posts, YouTube videos, or patch notes\n5. If you cite a URL, it MUST be copied EXACTLY from the search results\n6. When in doubt, say 'I don't have current information' - DO NOT GUESS\n\nVIOLATING THESE RULES BY INVENTING INFORMATION WILL BE IMMEDIATELY DETECTED."
                    )
                    logger.info(
                        f"Added web search context for: {message_content[:50]}..."
                    )
            except Exception as e:
                logger.error(f"Web search failed: {e}")

    def _add_style_guidance(self, context_parts: List[str], suggested_style: str):
        """Add style guidance."""
        style_map = {
            "direct": "Be direct and to-the-point in your response.",
            "conversational": "Keep the conversation flowing naturally and casually.",
            "descriptive": "Provide detailed, descriptive responses.",
            "helpful": "Be helpful and informative.",
            "casual": "Keep it casual and relaxed.",
            "playful": "Be playful and engaging in your tone.",
            "corrective": "Provide corrections or clarifications confidently.",
            "engaged": "Show genuine interest and engagement with the topic.",
            "random": "Feel free to be spontaneous and unpredictable.",
        }
        style_guidance = style_map.get(
            suggested_style, f"Adopt a {suggested_style} tone."
        )
        context_parts.append(f"\n[Response Style: {style_guidance}]")
        logger.debug(f"Added style guidance: {suggested_style}")

    def _add_conversational_style_guide(self, context_parts: List[str]):
        """Add the standard conversational style guide."""
        context_parts.append("""
[CONVERSATIONAL STYLE GUIDE - FOLLOW THIS CAREFULLY]
• FLOW NATURALLY - Don't announce yourself, introduce yourself, or explain yourself
• NEVER say "As [character name]..." or "[Character name] here" or "Speaking as..."
• NEVER explain your status/nature mid-conversation ("I'm a god", "being immortal", etc.)
• Just BE the character - respond naturally without meta-commentary
• Avoid filler phrases like "Tell me more...", "How interesting...", "Fascinating..." (sounds fake)
• Talk like a real person would talk
• Use contractions (I'm, you're, don't, can't) frequently
• Vary your sentence structure - mix short and long sentences
• Express genuine reactions: "Oh nice!", "Hmm interesting", "Wait really?"
• Match the user's energy and tone
• Response length: Aim for 2-4 sentences typically. Simple acknowledgments can be 1 sentence, but questions about YOU deserve fuller responses with personality
• NEVER give one-word answers unless it's truly appropriate (rare)
• It's okay to be uncertain or admit when you don't know something
• Use informal language when appropriate: "yeah", "nah", "totally", "pretty much"
• Show personality consistent with your character
• USE YOUR MEMORIES & KNOWLEDGE: If you see relevant info in the context, use it naturally as if it's your own memory
]""")
