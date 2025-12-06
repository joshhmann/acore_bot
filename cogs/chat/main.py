"""Chat cog for Ollama-powered conversations."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import time
import json
import re
import asyncio

from config import Config
from services.ollama import OllamaService
from services.intent_recognition import (
    IntentRecognitionService,
    ConversationalResponder,
)
from services.intent_handler import IntentHandler
from services.naturalness import NaturalnessEnhancer
from utils.helpers import (
    ChatHistoryManager,
    chunk_message,
    format_error,
    format_success,
    download_attachment,
    image_to_base64,
    is_image_attachment,
)
from utils.persona_loader import PersonaLoader
from utils.system_context import SystemContextProvider
from utils.response_validator import ResponseValidator

# Import modularized components
from .helpers import ChatHelpers
from .session_manager import SessionManager
from .voice_integration import VoiceIntegration
from .response_handler import _handle_chat_response as _handle_chat_response_func
from .context_builder import ContextBuilder
from .message_handler import MessageHandler

logger = logging.getLogger(__name__)


class ChatCog(commands.Cog):
    """Cog for chat commands using Ollama."""

    def __init__(
        self,
        bot: commands.Bot,
        ollama: OllamaService,
        history_manager: ChatHistoryManager,
        user_profiles=None,
        summarizer=None,
        web_search=None,
        naturalness=None,
        rag=None,
        conversation_manager=None,
        persona_system=None,
        compiled_persona=None,
        decision_engine=None,
        callbacks_system=None,
        curiosity_system=None,
        pattern_learner=None,
        llm_fallback=None,
    ):
        """Initialize chat cog.

        Args:
            bot: Discord bot instance
            ollama: Ollama service instance
            history_manager: Chat history manager
            user_profiles: User profile service (optional)
            summarizer: Conversation summarizer service (optional)
            web_search: Web search service (optional)
            naturalness: Naturalness service (optional)
            rag: RAG service (optional)
            conversation_manager: Multi-turn conversation manager (optional)
            persona_system: AI-First PersonaSystem (optional)
            compiled_persona: Current compiled persona (character + framework) (optional)
            decision_engine: AI decision engine (optional)
            callbacks_system: Proactive callbacks system for topic memory (optional)
            curiosity_system: Curiosity system for follow-up questions (optional)
            pattern_learner: Pattern learner for user adaptation (optional)
            llm_fallback: LLM fallback manager for resilient model switching (optional)
        """
        self.bot = bot
        self.ollama = ollama
        self.llm_fallback = llm_fallback
        self.history = history_manager
        self.user_profiles = user_profiles
        self.summarizer = summarizer
        self.web_search = web_search
        self.naturalness = naturalness
        self.rag = rag
        self.conversation_manager = conversation_manager

        # AI-First Persona System (new modular system)
        self.persona_system = persona_system
        self.compiled_persona = compiled_persona
        self.decision_engine = decision_engine
        self.callbacks_system = callbacks_system
        self.curiosity_system = curiosity_system
        self.pattern_learner = pattern_learner

        # Naturalness enhancer for Neuro-like behaviors
        self.enhancer = NaturalnessEnhancer()
        logger.info("Naturalness enhancer initialized")

        # Conversational callbacks
        try:
            from services.conversational_callbacks import ConversationalCallbacks

            self.callbacks = ConversationalCallbacks(history_manager, summarizer)
            logger.info("Conversational callbacks initialized")
        except Exception as e:
            logger.warning(f"Could not load conversational callbacks: {e}")
            self.callbacks = None

        # Initialize modularized components (must be before _load_system_prompt)
        self.helpers = ChatHelpers()
        self.session_manager = SessionManager()
        self.voice_integration = VoiceIntegration(bot, self.helpers.analyze_sentiment)
        self.context_builder = ContextBuilder(self)
        self.message_handler = MessageHandler(self)

        # Load persona configurations
        self.persona_loader = PersonaLoader()

        # Load system prompt from file or env
        self.system_prompt = self._load_system_prompt()

        # Track current persona config
        self.current_persona = None

        # Try to load default persona "dagoth" if available
        if not self.current_persona:
            default_persona = self.persona_loader.get_persona("dagoth")
            if default_persona:
                self.current_persona = default_persona
                logger.info(f"Loaded default persona: {default_persona.display_name}")

        # Track background tasks for proper cleanup
        self._background_tasks: set = set()

        # Intent recognition for natural language commands
        self.intent_recognition = None
        self.intent_handler = None
        if Config.INTENT_RECOGNITION_ENABLED:
            self.intent_recognition = IntentRecognitionService()
            self.intent_handler = IntentHandler(bot)
            logger.info(
                "Intent recognition enabled - bot can now understand natural language commands"
            )

        # AI-powered message batching - feature removed during cleanup
        # from services.message_batcher import MessageBatcher
        # self.message_batcher = MessageBatcher(bot, ollama)
        # logger.info("AI-powered message batching initialized")
        self.message_batcher = None

        # Agentic tool system (ReAct pattern)
        from services.agentic_tools import AgenticToolSystem

        self.agentic_tools = AgenticToolSystem()
        logger.info("Agentic tool system initialized")

        # Bind extracted response handler method
        self._handle_chat_response = _handle_chat_response_func.__get__(self, type(self))

    async def _llm_chat(
        self, messages, system_prompt=None, temperature=None, max_tokens=None
    ):
        """Wrapper for LLM chat that uses fallback if enabled.

        Args:
            messages: Chat messages
            system_prompt: Optional system prompt
            temperature: Temperature override
            max_tokens: Max tokens override

        Returns:
            LLM response text
        """
        if self.llm_fallback:
            # Use fallback system (automatic model switching on failure)
            response, model_used = await self.llm_fallback.chat_with_fallback(
                llm_service=self.ollama,
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response
        else:
            # Direct call to LLM service (no fallback)
            return await self.ollama.chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    def _create_background_task(self, coro):
        """Create a background task and track it for cleanup.

        Args:
            coro: Coroutine to run in background

        Returns:
            The created task
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        # Remove from set when done
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def cleanup_tasks(self):
        """Cancel all background tasks (called on shutdown)."""
        if self._background_tasks:
            logger.info(
                f"Cancelling {len(self._background_tasks)} ChatCog background tasks..."
            )
            for task in self._background_tasks:
                task.cancel()
            # Wait for all to complete
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            logger.info("ChatCog background tasks cancelled")

    def _load_system_prompt(self) -> str:
        """Load system prompt from file or environment variable.

        Returns:
            System prompt string
        """
        # NEW: Check if compiled persona is available (AI-First PersonaSystem)
        if self.compiled_persona:
            logger.info(
                f"✨ Using system prompt from compiled persona: {self.compiled_persona.persona_id}"
            )
            logger.info(f"   Character: {self.compiled_persona.character.display_name}")
            logger.info(f"   Framework: {self.compiled_persona.framework.name}")
            return self.compiled_persona.system_prompt

        # Check if SYSTEM_PROMPT is set directly in env (takes precedence for legacy mode)
        if Config.SYSTEM_PROMPT:
            logger.info("Using system prompt from environment variable (legacy mode)")
            return Config.SYSTEM_PROMPT

        # Try to load from file (legacy mode)
        prompt_file = Path(Config.SYSTEM_PROMPT_FILE)
        default_prompt = (
            "You are a helpful AI assistant in a Discord server. "
            "Keep your responses concise and friendly. "
            "You can use Discord markdown for formatting."
        )
        return self.helpers.load_system_prompt(prompt_file, default_prompt)

    async def check_and_handle_message(self, message: discord.Message) -> bool:
        """Check if message should be handled as chat and process it."""
        return await self.message_handler.check_and_handle_message(message)

    async def _handle_chat_response(
        self,
        message_content: str,
        channel: discord.TextChannel,
        user: discord.User,
        interaction: Optional[discord.Interaction] = None,
        original_message: Optional[discord.Message] = None,
        response_reason: Optional[str] = None,
        suggested_style: Optional[str] = None,
    ):
        """Core chat logic shared by slash command and on_message listener.

        Args:
            message_content: The message to respond to
            channel: Discord channel
            user: User who sent the message
            interaction: Optional Discord interaction (for slash commands)
            original_message: Optional original Discord message
            response_reason: Why we're responding (for logging/analytics)
            suggested_style: Suggested response style from decision engine
        """
        # Start response time tracking
        import time

        start_time = time.time()

        # Track if streaming TTS was used (defined here for scope)
        use_streaming_tts = False

        # Helper for sending messages (handling interaction vs channel)
        async def send_response(content, ephemeral=False):
            if interaction:
                if interaction.response.is_done():
                    await interaction.followup.send(content, ephemeral=ephemeral)
                else:
                    await interaction.response.send_message(
                        content, ephemeral=ephemeral
                    )
            else:
                if not ephemeral:  # Can't send ephemeral to channel
                    await channel.send(content)

        # Input validation
        if not isinstance(message_content, str):
            logger.warning(f"message_content is not a string: {type(message_content)}")
            message_content = (
                str(message_content) if message_content is not None else ""
            )

        if len(message_content) > 4000:
            await send_response(
                "❌ Message too long! Please keep messages under 4000 characters.",
                ephemeral=True,
            )
            return

        # Replace user mentions with readable names for LLM
        if original_message:
            message_content = self.helpers.replace_mentions_with_names(
                message_content, original_message, self.bot.user.id
            )

        # Check for multi-turn conversation steps (only for actual messages)
        if original_message and self.conversation_manager:
            # Prepare user content (strip mention)
            user_content = message_content
            if self.bot.user in original_message.mentions:
                user_content = message_content.replace(
                    f"<@{self.bot.user.id}>", ""
                ).strip()

            conversation = self.conversation_manager.get_conversation(channel.id)
            if conversation:
                # Process response in multi-turn conversation
                result = await self.conversation_manager.process_response(
                    channel.id, user.id, user_content
                )

                if result:
                    if result["type"] == "next_step":
                        await channel.send(
                            f"**Step {result['step_number']}/{result['total_steps']}**\n{result['prompt']}"
                        )
                    elif result["type"] == "completed":
                        await channel.send(result["message"])
                    elif result["type"] == "invalid":
                        remaining = result.get("attempts_remaining", 0)
                        await channel.send(
                            f"{result['message']}\n*({remaining} attempts remaining)*"
                        )
                    elif result["type"] in ["cancelled", "failed", "error"]:
                        await channel.send(result["message"])

                    return  # Multi-turn conversation handled

        # Check for natural language intents (only for actual messages)
        if original_message and self.intent_recognition:
            # Prepare user content (strip mention)
            user_content = message_content
            if self.bot.user in original_message.mentions:
                user_content = message_content.replace(
                    f"<@{self.bot.user.id}>", ""
                ).strip()

            server_id = original_message.guild.id if original_message.guild else None
            intent = self.intent_recognition.detect_intent(
                user_content,
                bot_mentioned=(self.bot.user in original_message.mentions),
                server_id=server_id,
            )

            # Handle intents that don't need AI processing
            if intent and self.intent_handler:
                logger.info(
                    f"Detected intent: {intent.intent_type} (confidence: {intent.confidence}) for message: '{user_content[:50]}'"
                )
                handled = await self.intent_handler.handle_intent(
                    intent, original_message
                )
                logger.info(f"Intent {intent.intent_type} handled: {handled}")
                if handled:
                    # Intent was fully handled, no need for AI response
                    if self.intent_recognition.learner:
                        self.intent_recognition.report_success(
                            user_content, intent.intent_type
                        )
                    return
                else:
                    logger.info(
                        f"Intent {intent.intent_type} not handled, falling through to AI"
                    )

        # Check if user is referencing an image in recent messages
        image_reference_keywords = [
            "image above",
            "picture above",
            "photo above",
            "that image",
            "this image",
            "the image",
            "that picture",
            "this picture",
            "the picture",
            "react to",
            "what do you think of",
            "describe",
            "analyze",
            "what is that",
            "what is this",
            "look at this",
            "look at that",
            "who is this",
            "who is that",
            "thoughts?",
            "see this",
        ]

        message_lower = message_content.lower()
        is_referencing_image = any(
            keyword in message_lower for keyword in image_reference_keywords
        )

        # Also check if the current message HAS an image (implicit reference)
        has_attachment = False
        if original_message and (
            original_message.attachments or original_message.embeds
        ):
            has_attachment = True
            is_referencing_image = True  # Treat as referencing the attached image

        recent_image_url = None
        if is_referencing_image:
            # 1. Check current message first
            if original_message:
                if original_message.attachments:
                    for attachment in original_message.attachments:
                        if is_image_attachment(attachment.filename):
                            recent_image_url = attachment.url
                            break
                if not recent_image_url and original_message.embeds:
                    for embed in original_message.embeds:
                        if embed.image:
                            recent_image_url = embed.image.url
                            break
                        elif embed.thumbnail:
                            recent_image_url = embed.thumbnail.url
                            break

            # 2. Look back through recent messages if not found in current
            if not recent_image_url:
                try:
                    async for msg in channel.history(limit=10):
                        # Skip the current message/interaction
                        if (
                            interaction
                            and msg.author == user
                            and msg.content == message_content
                        ):
                            continue
                        if original_message and msg.id == original_message.id:
                            continue

                        # Check for image attachments
                        if msg.attachments:
                            for attachment in msg.attachments:
                                if is_image_attachment(attachment.filename):
                                    recent_image_url = attachment.url
                                    logger.info(
                                        f"Found recent image: {recent_image_url}"
                                    )
                                    break

                        # Check for embeds with images
                        if msg.embeds:
                            for embed in msg.embeds:
                                if embed.image:
                                    recent_image_url = embed.image.url
                                    logger.info(
                                        f"Found recent embed image: {recent_image_url}"
                                    )
                                    break
                                elif embed.thumbnail:
                                    recent_image_url = embed.thumbnail.url
                                    logger.info(
                                        f"Found recent thumbnail: {recent_image_url}"
                                    )
                                    break

                        if recent_image_url:
                            break
                except Exception as e:
                    logger.error(f"Error fetching recent images: {e}")

        # Check for trigger word reactions FIRST (before defer)
        trigger_reaction = self.enhancer.check_trigger_words(message_content)
        if trigger_reaction:
            await send_response(trigger_reaction)
            logger.info(f"Sent trigger word reaction: {trigger_reaction[:50]}...")
            return

        # Check for fake glitch
        glitch = self.enhancer.should_glitch()
        if glitch:
            await send_response(glitch)
            logger.info(f"Sent glitch message: {glitch[:50]}...")
            return

        # Calculate natural thinking delay
        thinking_delay = self.enhancer.calculate_thinking_delay(message_content)

        if interaction:
            await interaction.response.defer(thinking=True)
        # Note: For on_message, we already started typing in the listener

        # Apply thinking delay
        await asyncio.sleep(thinking_delay)

        try:
            channel_id = channel.id
            user_id = user.id

            # Update emotional state based on message
            sentiment_deltas = self.enhancer.analyze_message_sentiment(message_content)
            for emotion, delta in sentiment_deltas.items():
                self.enhancer.update_emotion(emotion, delta)

            # Check if we should use a sarcastic short response
            short_response = self.enhancer.should_use_short_response(message_content)
            if short_response:
                await send_response(short_response)
                logger.info(f"Sent short response: {short_response}")
                return

            # Load conversation history
            history = []
            if Config.CHAT_HISTORY_ENABLED:
                history = await self.history.load_history(channel_id)

            # Add user message
            history.append({"role": "user", "content": message_content})

            # Build system prompt with context (TIME FIRST so it's most prominent)
            context_parts = [SystemContextProvider.get_compact_context()]

            # Add multi-user context
            multi_user_context = self.history.build_multi_user_context(history)
            if multi_user_context:
                context_parts.append(f"\n[Context: {multi_user_context}]")

            # Add user profile context if enabled
            if self.user_profiles and Config.USER_CONTEXT_IN_CHAT:
                user_context = await self.user_profiles.get_user_context(user_id)
                if (
                    user_context
                    and user_context != "New user - no profile information yet."
                ):
                    # Check for behavioral instructions in user profile
                    profile = await self.user_profiles.load_profile(user.id)
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
                        if any(
                            keyword in fact_lower
                            for keyword in [
                                "when you see",
                                "always say",
                                "greet with",
                                "call them",
                                "respond with",
                                "call me",
                            ]
                        ):
                            special_instructions.append(fact_text)

                    # If there are special instructions, put them at the VERY TOP
                    if special_instructions:
                        instruction_text = "\n".join(
                            [f"- {inst}" for inst in special_instructions]
                        )
                        context_parts.insert(
                            0,
                            f"\n[CRITICAL USER-SPECIFIC INSTRUCTIONS - FOLLOW EXACTLY:\n{instruction_text}\n]",
                        )

                    # Add general user context
                    context_parts.append(f"\n[User Info: {user_context}]")

                # Add affection/relationship context if enabled
                if Config.USER_AFFECTION_ENABLED:
                    affection_context = self.user_profiles.get_affection_context(
                        user_id
                    )
                    if affection_context:
                        context_parts.append(f"\n[Relationship: {affection_context}]")

            # Add memory recall from past conversations
            if self.summarizer:
                memory_context = await self.summarizer.build_memory_context(
                    message_content
                )
                if memory_context:
                    context_parts.append(f"\n{memory_context}")

            # Add RAG context from documents (if enabled and has documents)
            if self.rag and Config.RAG_IN_CHAT and self.rag.is_enabled():
                # Boost documents matching the current persona
                persona_boost = None
                if self.current_persona:
                    # Use explicitly configured category or fallback to persona name
                    persona_boost = (
                        self.current_persona.rag_boost_category
                        or self.current_persona.name
                    )

                rag_context = self.rag.get_context(
                    message_content, max_length=1000, boost_category=persona_boost
                )
                if rag_context:
                    # CRITICAL: Insert RAG context at the VERY BEGINNING of context_parts
                    # This ensures it overrides general personality traits
                    context_parts.insert(
                        0,
                        f"\n[CRITICAL KNOWLEDGE - USE THIS TO ANSWER:\n{rag_context}\n]",
                    )

            # Add emotional state context
            emotional_context = self.enhancer.get_emotional_context()
            if emotional_context:
                context_parts.append(f"\n[{emotional_context}]")

            # Track conversation topics for callbacks
            if self.callbacks:
                await self.callbacks.track_conversation_topic(
                    channel_id, message_content, str(user.name)
                )

                # Check for callback opportunities
                callback_prompt = await self.callbacks.get_callback_opportunity(
                    channel_id, message_content
                )
                if callback_prompt:
                    context_parts.append(f"\n{callback_prompt}")

                # Add recent conversation context
                recent_context = await self.callbacks.get_recent_context(channel_id)
                if recent_context:
                    context_parts.append(f"\n{recent_context}")

            # Track message rhythm
            if self.naturalness:
                self.naturalness.track_message_rhythm(channel_id, len(message_content))

                # Add rhythm-based style guidance
                rhythm_prompt = self.naturalness.get_rhythm_style_prompt(channel_id)
                if rhythm_prompt:
                    context_parts.append(f"\n{rhythm_prompt}")

                # Add voice context if applicable
                if channel.guild:
                    voice_context = self.naturalness.get_voice_context(channel.guild)
                    if voice_context:
                        context_parts.append(f"\n{voice_context}")

            # Add web search results if query needs current information
            if self.web_search and await self.web_search.should_search(message_content):
                try:
                    search_context = await self.web_search.get_context(
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

            # Add mood context if naturalness service is available
            if self.naturalness and Config.MOOD_SYSTEM_ENABLED:
                mood_context = self.naturalness.get_mood_context()
                if mood_context:
                    context_parts.append(f"\n{mood_context}")

            # Add user-specific adaptation guidance (Learning & Adaptation)
            if self.pattern_learner:
                adaptation_guidance = self.pattern_learner.get_adaptation_guidance(
                    user.id
                )
                if adaptation_guidance:
                    context_parts.append(f"\n[User Adaptation: {adaptation_guidance}]")
                    logger.debug(f"Added adaptation guidance for user {user.id}")

            # Add AI Decision Engine style guidance if available
            if suggested_style:
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

            # Add response style guidance for natural conversation
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

            # Inject all context into system prompt (CHARACTER FIRST, then context)
            # CRITICAL: Put character instructions FIRST so they're not overridden by context
            context_injected_prompt = (
                f"{self.system_prompt}\n\n{''.join(context_parts)}"
            )

            # Log action for self-awareness
            if self.naturalness:
                self.naturalness.log_action("chat", f"User: {str(user.name)}")

            # Response optimization disabled - service removed
            # if Config.DYNAMIC_MAX_TOKENS:
            #     optimization = ResponseOptimizer.optimize_request_params(
            #         message_content,
            #         base_params={'max_tokens': Config.OLLAMA_MAX_TOKENS or 500},
            #         enable_dynamic_tokens=True,
            #         streaming_threshold=Config.STREAMING_TOKEN_THRESHOLD
            #     )
            #     optimal_max_tokens = optimization['max_tokens']
            #     optimization_info = optimization.get('_optimization_info', {})
            #
            #     # Override streaming decision if optimizer suggests
            #     if 'use_streaming' in optimization_info:
            #         should_stream = optimization_info['use_streaming']
            #         logger.debug(
            #             f"Optimizer suggests streaming: {should_stream} "
            #             f"(estimated {optimal_max_tokens} tokens)"
            #         )
            # Use default values since optimizer is disabled
            optimal_max_tokens = Config.OLLAMA_MAX_TOKENS or 500
            should_stream = Config.RESPONSE_STREAMING_ENABLED

            # If we found a recent image, process it with vision
            if recent_image_url and Config.VISION_ENABLED:
                try:
                    logger.info(
                        f"Processing recent image with vision: {recent_image_url}"
                    )
                    # Download the image (returns bytes)
                    image_data = await download_attachment(recent_image_url)

                    if image_data:
                        # Convert to base64
                        image_base64 = image_to_base64(image_data)

                        # Add image context to the message
                        vision_message = f"{message_content}\n\n[Note: User is referencing an image from a recent message]"

                        # Use vision model
                        response = await self.ollama.chat_with_vision(
                            prompt=vision_message,
                            images=[image_base64],
                            system_prompt=context_injected_prompt,
                            model=Config.VISION_MODEL,
                            max_tokens=optimal_max_tokens,
                        )

                        logger.info("Successfully processed recent image with vision")
                    else:
                        # Fallback to text-only if download failed
                        response = await self.ollama.chat(
                            history,
                            system_prompt=context_injected_prompt,
                            max_tokens=optimal_max_tokens,
                        )
                except Exception as e:
                    logger.error(f"Vision processing failed for recent image: {e}")
                    # Fallback to text-only
                    response = await self._llm_chat(
                        history,
                        system_prompt=context_injected_prompt,
                        max_tokens=optimal_max_tokens,
                    )
            else:
                # Regular text-only chat

                # 1. Use Agentic Tools (ReAct) if available
                # Note: Streaming is currently disabled for agentic tools to prevent showing tool calls to users
                if self.agentic_tools:

                    async def llm_generate(conv):
                        # LLM chat with fallback if enabled; system prompt already in conv
                        return await self._llm_chat(conv, system_prompt=None)

                    response = await self.agentic_tools.process_with_tools(
                        llm_generate_func=llm_generate,
                        user_message=message_content,
                        system_prompt=context_injected_prompt,
                        max_iterations=3,
                    )

                # 2. Fallback to Standard Streaming (if enabled)
                elif should_stream:
                    response = ""
                    response_message = None
                    last_update = time.time()

                    # Check if we should use streaming TTS (bot in voice + voice feature enabled)
                    voice_client = channel.guild.voice_client if channel.guild else None
                    use_streaming_tts = (
                        Config.AUTO_REPLY_WITH_VOICE
                        and voice_client
                        and voice_client.is_connected()
                        and not voice_client.is_playing()
                    )

                    if use_streaming_tts:
                        # Create streaming TTS processor
                        voice_cog = self.bot.get_cog("VoiceCog")
                        if voice_cog:
                            streaming_tts = StreamingTTSProcessor(
                                voice_cog.tts,
                                voice_cog.rvc if hasattr(voice_cog, "rvc") else None,
                            )

                            # Analyze sentiment for voice modulation
                            sentiment = self.helpers.analyze_sentiment(message_content)
                            kokoro_speed = 1.0
                            edge_rate = "+0%"

                            if sentiment == "positive":
                                kokoro_speed = 1.1
                                edge_rate = "+10%"
                            elif sentiment == "negative":
                                kokoro_speed = 0.9
                                edge_rate = "-10%"

                            # Create multiplexer for single LLM stream
                            llm_stream = self.ollama.chat_stream(
                                history,
                                system_prompt=context_injected_prompt,
                                max_tokens=optimal_max_tokens,
                            )
                            multiplexer = StreamMultiplexer(llm_stream)

                            # Create consumers
                            text_stream = multiplexer.create_consumer()
                            tts_stream = multiplexer.create_consumer()

                            # Process text updates
                            async def process_text_updates():
                                nonlocal response, response_message, last_update

                                async for chunk in text_stream:
                                    response += chunk

                                    # Update message periodically
                                    current_time = time.time()
                                    if (
                                        current_time - last_update
                                        >= Config.STREAM_UPDATE_INTERVAL
                                    ):
                                        if interaction:
                                            # Apply mention conversion for Discord display
                                            display_text = (
                                                self.helpers.restore_mentions(
                                                    response, guild
                                                )
                                                if guild
                                                else response
                                            )
                                            if not response_message:
                                                response_message = (
                                                    await interaction.followup.send(
                                                        display_text[:2000]
                                                    )
                                                )
                                            else:
                                                try:
                                                    await response_message.edit(
                                                        content=display_text[:2000]
                                                    )
                                                except discord.HTTPException:
                                                    pass

                                        last_update = current_time

                            # Run text updates and TTS in parallel
                            await asyncio.gather(
                                process_text_updates(),
                                streaming_tts.process_stream(
                                    tts_stream,
                                    voice_client,
                                    speed=kokoro_speed,
                                    rate=edge_rate,
                                ),
                            )

                            logger.info("Parallel streaming TTS completed")
                        else:
                            # Fallback if voice cog not available
                            async for chunk in self.ollama.chat_stream(
                                history,
                                system_prompt=context_injected_prompt,
                                max_tokens=optimal_max_tokens,
                            ):
                                response += chunk

                                current_time = time.time()
                                if (
                                    current_time - last_update
                                    >= Config.STREAM_UPDATE_INTERVAL
                                ):
                                    if interaction:
                                        # Apply mention conversion for Discord display
                                        display_text = (
                                            self.helpers.restore_mentions(
                                                response, guild
                                            )
                                            if guild
                                            else response
                                        )
                                        if not response_message:
                                            response_message = (
                                                await interaction.followup.send(
                                                    display_text[:2000]
                                                )
                                            )
                                        else:
                                            try:
                                                await response_message.edit(
                                                    content=display_text[:2000]
                                                )
                                            except discord.HTTPException:
                                                pass

                                    last_update = current_time
                    else:
                        # Standard text-only streaming (no voice or voice disabled)
                        async for chunk in self.ollama.chat_stream(
                            history,
                            system_prompt=context_injected_prompt,
                            max_tokens=optimal_max_tokens,
                        ):
                            response += chunk

                            # Update message periodically to avoid rate limits
                            current_time = time.time()
                            if (
                                current_time - last_update
                                >= Config.STREAM_UPDATE_INTERVAL
                            ):
                                if interaction:
                                    # Apply mention conversion for Discord display
                                    display_text = (
                                        self.helpers.restore_mentions(response, guild)
                                        if guild
                                        else response
                                    )
                                    if not response_message:
                                        response_message = (
                                            await interaction.followup.send(
                                                display_text[:2000]
                                            )
                                        )
                                    else:
                                        try:
                                            await response_message.edit(
                                                content=display_text[:2000]
                                            )
                                        except discord.HTTPException:
                                            pass  # Rate limit hit, skip this update
                                # Note: We don't stream edits to regular messages as it's spammy/rate-limited
                                # We only send final for non-interaction messages usually, or maybe 1-2 updates

                                last_update = current_time

                    # Send final update if needed
                    if interaction and response_message:
                        # Apply mention conversion for final Discord display
                        display_text = (
                            self.helpers.restore_mentions(response, guild)
                            if guild
                            else response
                        )
                        try:
                            await response_message.edit(content=display_text[:2000])
                        except discord.HTTPException:
                            pass
                    elif interaction:
                        # Apply mention conversion for final Discord display
                        display_text = (
                            self.helpers.restore_mentions(response, guild)
                            if guild
                            else response
                        )
                        await interaction.followup.send(display_text[:2000])
                    # Note: For non-interaction, the final response will be sent later
                    # after mention conversion (see lines below after response processing)

                # 3. Standard Non-Streaming Fallback
                else:
                    response = await self.ollama.chat(
                        history,
                        system_prompt=context_injected_prompt,
                        max_tokens=optimal_max_tokens,
                    )

            # Validate and clean response (remove thinking tags, fix hallucinations)
            response = ResponseValidator.validate_response(response)

            # Enhance response with self-awareness features if enabled
            if self.naturalness and Config.SELF_AWARENESS_ENABLED:
                response = self.naturalness.enhance_response(response, context="chat")

            # Apply AI-first persona framework effects (spontaneity, chaos, etc.)
            if hasattr(self.bot, "decision_engine") and self.bot.decision_engine:
                response = await self.bot.decision_engine.enhance_response(response)
                logger.debug("Applied decision engine framework effects to response")

            # Clean up response (remove trailing backslashes, extra whitespace)
            response = response.rstrip("\\").rstrip()

            # Create separate versions for Discord and TTS
            # Discord version: Convert @Username to <@user_id> for clickable mentions
            # TTS version: Convert <@user_id> to Username for natural pronunciation
            guild = channel.guild if hasattr(channel, "guild") else None
            if guild:
                discord_response = self.helpers.restore_mentions(response, guild)
                tts_response = self.helpers.clean_for_tts(response, guild)
            else:
                # No guild context (DMs), use original response
                discord_response = response
                tts_response = response

            # Update mood based on interaction
            if self.naturalness and Config.MOOD_UPDATE_FROM_INTERACTIONS:
                # Analyze sentiment
                sentiment = self.helpers.analyze_sentiment(message_content)
                # Check if conversation is interesting (has questions, details, etc.)
                is_interesting = (
                    len(message_content.split()) > 10
                    or "?" in message_content
                    or "how" in message_content.lower()
                )
                self.naturalness.update_mood(sentiment, is_interesting)

            # Update user profile - increment interaction count and learn from conversation
            if self.user_profiles:
                profile = await self.user_profiles.load_profile(user_id)
                profile["interaction_count"] += 1
                if not profile.get("username"):
                    profile["username"] = str(user.name)
                await self.user_profiles.save_profile(user_id)

                # AI-powered learning from conversation (runs in background)
                if Config.USER_PROFILES_AUTO_LEARN:
                    # Run in background to avoid blocking response
                    self._create_background_task(
                        self._safe_learn_from_conversation(
                            user_id=user_id,
                            username=str(user.name),
                            user_message=message_content,
                            bot_response=response,
                        )
                    )

                # Update affection score if enabled
                if Config.USER_AFFECTION_ENABLED:
                    # Run in background
                    self._create_background_task(
                        self._safe_update_affection(
                            user_id=user_id,
                            message=message_content,
                            bot_response=response,
                        )
                    )

            # Save to history with user attribution
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(
                    channel_id,
                    "user",
                    message_content,
                    username=str(user.name),
                    user_id=user.id,
                )
                # Use discord_response for history (with proper mention tags)
                await self.history.add_message(
                    channel_id, "assistant", discord_response
                )

            # Start a conversation session
            await self.session_manager.start_session(channel_id, user.id)

            # Send response (handle long messages) - only if not streaming
            if not Config.RESPONSE_STREAMING_ENABLED:
                # Use discord_response for Discord (with proper mention tags)
                chunks = await chunk_message(discord_response)
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await send_response(chunk)
                    else:
                        await channel.send(chunk)
            elif not interaction:
                # If streaming was enabled but we are in non-interaction mode, we haven't sent the final message yet
                # (because we skipped streaming updates to channel)
                # Use discord_response for Discord (with proper mention tags)
                chunks = await chunk_message(discord_response)
                for i, chunk in enumerate(chunks):
                    await channel.send(chunk)

            # Check if we should auto-summarize
            if self.summarizer and len(history) >= Config.AUTO_SUMMARIZE_THRESHOLD:
                # Summarize in background (don't block)
                participants = self.history.get_conversation_participants(history)
                self._create_background_task(
                    self.summarizer.summarize_and_store(
                        messages=history,
                        channel_id=channel_id,
                        participants=[p["username"] for p in participants],
                        store_in_rag=Config.STORE_SUMMARIES_IN_RAG,
                    )
                )

            # Also speak in voice channel if bot is connected and feature is enabled
            # Skip if streaming TTS was already used
            if Config.AUTO_REPLY_WITH_VOICE and not (
                Config.RESPONSE_STREAMING_ENABLED and use_streaming_tts
            ):
                # Only generate TTS if actually in a voice channel
                voice_client = channel.guild.voice_client if channel.guild else None
                if voice_client and voice_client.is_connected():
                    # Use tts_response for natural pronunciation (without mention tags)
                    await self.voice_integration.speak_response_in_voice(
                        channel.guild, tts_response
                    )

            # Record metrics for successful response
            if hasattr(self.bot, "metrics"):
                duration_ms = (time.time() - start_time) * 1000
                self.bot.metrics.record_response_time(duration_ms)
                self.bot.metrics.record_message(user.id, channel.id)

        except Exception as e:
            import traceback

            logger.error(f"Chat command failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Record error in metrics
            if hasattr(self.bot, "metrics"):
                error_type = type(e).__name__
                self.bot.metrics.record_error(error_type, str(e))

            await send_response(format_error(e))

    @app_commands.command(name="chat", description="Chat with the AI")
    @app_commands.describe(message="Your message to the AI")
    @app_commands.checks.cooldown(1, 3.0)  # 1 use per 3 seconds per user
    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with Ollama AI.

        Args:
            interaction: Discord interaction
            message: User's message
        """
        await self._handle_chat_response(
            message_content=message,
            channel=interaction.channel,
            user=interaction.user,
            interaction=interaction,
        )

    @app_commands.command(
        name="ambient", description="Toggle or check ambient mode status"
    )
    @app_commands.describe(action="Action to perform")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Status", value="status"),
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
        ]
    )
    async def ambient(self, interaction: discord.Interaction, action: str = "status"):
        """Control ambient mode.

        Args:
            interaction: Discord interaction
            action: Action to perform (status/enable/disable)
        """
        try:
            ambient = getattr(self.bot, "ambient_mode", None)

            if not ambient:
                await interaction.response.send_message(
                    "❌ Ambient mode is not configured.", ephemeral=True
                )
                return

            if action == "status":
                stats = ambient.get_stats()
                embed = discord.Embed(
                    title="🌙 Ambient Mode Status", color=discord.Color.purple()
                )
                embed.add_field(
                    name="Status",
                    value="🟢 Running" if stats["running"] else "🔴 Stopped",
                    inline=True,
                )
                embed.add_field(
                    name="Active Channels",
                    value=str(stats["active_channels"]),
                    inline=True,
                )
                embed.add_field(
                    name="Trigger Chance",
                    value=f"{int(stats['chance'] * 100)}%",
                    inline=True,
                )
                embed.add_field(
                    name="Lull Timeout", value=f"{stats['lull_timeout']}s", inline=True
                )
                embed.add_field(
                    name="Min Interval", value=f"{stats['min_interval']}s", inline=True
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif action == "enable":
                if ambient.running:
                    await interaction.response.send_message(
                        "✅ Ambient mode is already running.", ephemeral=True
                    )
                else:
                    await ambient.start()
                    await interaction.response.send_message(
                        "✅ Ambient mode enabled!", ephemeral=True
                    )

            elif action == "disable":
                if not ambient.running:
                    await interaction.response.send_message(
                        "❌ Ambient mode is already stopped.", ephemeral=True
                    )
                else:
                    await ambient.stop()
                    await interaction.response.send_message(
                        "✅ Ambient mode disabled.", ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Ambient command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(
        name="end_session", description="End the current conversation session"
    )
    async def end_session(self, interaction: discord.Interaction):
        """End the active conversation session in this channel.

        Args:
            interaction: Discord interaction
        """
        try:
            channel_id = interaction.channel_id
            if await self.session_manager.is_session_active(channel_id):
                await self.session_manager.end_session(channel_id)
                timeout_minutes = Config.CONVERSATION_TIMEOUT // 60
                await interaction.response.send_message(
                    format_success(
                        f"Conversation session ended. Use @mention or `/chat` to start a new session."
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "No active conversation session in this channel.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"End session failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    async def _disabled_on_message(self, message: discord.Message):
        """Listen for messages to enable auto-reply with text and TTS.

        Supports conversation sessions: once started with @mention or /chat,
        the bot will continue responding to all messages until timeout expires.

        Args:
            message: Discord message
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # NOTE: ambient_mode and naturalness are called from main.py on_message
        # Don't duplicate those calls here to avoid double processing

        # Ignore messages with #ignore tag
        if "#ignore" in message.content.lower():
            return

        # Check if auto-reply is enabled for this channel
        if not Config.AUTO_REPLY_ENABLED:
            return

        if (
            Config.AUTO_REPLY_CHANNELS
            and message.channel.id not in Config.AUTO_REPLY_CHANNELS
        ):
            return

        # Check if there's an active session OR bot is mentioned
        is_session_active = await self.session_manager.is_session_active(
            message.channel.id
        )
        is_mentioned = self.bot.user in message.mentions

        # Only respond if mentioned OR session is active
        if not (is_mentioned or is_session_active):
            return

        # If mentioned, this will start/refresh the session
        # If session is active, this will refresh it

        try:
            # Check for active multi-turn conversations FIRST
            user_content = message.content.replace(f"<@{self.bot.user.id}>", "").strip()

            if self.conversation_manager:
                conversation = self.conversation_manager.get_conversation(
                    message.channel.id
                )
                if conversation:
                    # Process response in multi-turn conversation
                    result = await self.conversation_manager.process_response(
                        message.channel.id, message.author.id, user_content
                    )

                    if result:
                        if result["type"] == "next_step":
                            await message.channel.send(
                                f"**Step {result['step_number']}/{result['total_steps']}**\n{result['prompt']}"
                            )
                        elif result["type"] == "completed":
                            await message.channel.send(result["message"])
                            # Handle completed conversation data here
                        elif result["type"] == "invalid":
                            remaining = result.get("attempts_remaining", 0)
                            await message.channel.send(
                                f"{result['message']}\n*({remaining} attempts remaining)*"
                            )
                        elif result["type"] in ["cancelled", "failed"]:
                            await message.channel.send(result["message"])
                        elif result["type"] == "error":
                            await message.channel.send(result["message"])

                        return  # Multi-turn conversation handled

            # Check for natural language intents
            if self.intent_recognition:
                server_id = message.guild.id if message.guild else None
                intent = self.intent_recognition.detect_intent(
                    user_content, bot_mentioned=is_mentioned, server_id=server_id
                )

                # Handle intents that don't need AI processing
                if intent and self.intent_handler:
                    logger.info(
                        f"Detected intent: {intent.intent_type} (confidence: {intent.confidence}) for message: '{user_content[:50]}'"
                    )
                    handled = await self.intent_handler.handle_intent(intent, message)
                    logger.info(f"Intent {intent.intent_type} handled: {handled}")
                    if handled:
                        # Intent was fully handled, no need for AI response
                        # Report success to learner
                        if self.intent_recognition.learner:
                            self.intent_recognition.report_success(
                                user_content, intent.intent_type
                            )
                        return
                    else:
                        logger.info(
                            f"Intent {intent.intent_type} not handled, falling through to AI"
                        )

            # Load history
            history = []
            if Config.CHAT_HISTORY_ENABLED:
                history = await self.history.load_history(message.channel.id)
            history.append({"role": "user", "content": user_content})

            # Build system prompt with context (TIME FIRST so it's most prominent)
            context_parts = [SystemContextProvider.get_compact_context()]

            # Add user profile context if enabled
            if self.user_profiles and Config.USER_CONTEXT_IN_CHAT:
                user_context = await self.user_profiles.get_user_context(
                    message.author.id
                )
                if (
                    user_context
                    and user_context != "New user - no profile information yet."
                ):
                    context_parts.append(f"\n[User Info: {user_context}]")

                # Add affection/relationship context if enabled
                if Config.USER_AFFECTION_ENABLED:
                    affection_context = self.user_profiles.get_affection_context(
                        message.author.id
                    )
                    if affection_context:
                        context_parts.append(f"\n[Relationship: {affection_context}]")

            # Add web search results if query needs current information
            if self.web_search and await self.web_search.should_search(user_content):
                try:
                    # Extract conversation context (last few messages for topic)
                    conv_context = None
                    if len(history) > 1:
                        # Get last 2-3 messages for context
                        recent_msgs = history[-3:]
                        topics = []
                        for msg in recent_msgs:
                            # Extract potential topic words (proper nouns, capitalized words)
                            import re

                            words = re.findall(
                                r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
                                msg.get("content", ""),
                            )
                            topics.extend(words)

                        if topics:
                            conv_context = " ".join(set(topics))  # Unique topics
                            logger.info(
                                f"Extracted conversation context: {conv_context}"
                            )

                    search_context = await self.web_search.get_context(
                        user_content, max_length=800, conversation_context=conv_context
                    )

                    if search_context:
                        context_parts.append(
                            f"\n\n{'=' * 60}\n[REAL-TIME WEB SEARCH RESULTS - READ THIS EXACTLY]\n{'=' * 60}\n{search_context}\n{'=' * 60}\n[END OF WEB SEARCH RESULTS]\n{'=' * 60}\n\n[CRITICAL INSTRUCTIONS - VIOLATION WILL BE DETECTED]\n1. You MUST ONLY cite information that appears EXACTLY in the search results above\n2. COPY the exact URLs shown - DO NOT modify or create new ones\n3. If search results are irrelevant (e.g., wrong topic, unrelated content), tell the user: 'The search didn't return relevant results'\n4. DO NOT invent Steam pages, Reddit posts, YouTube videos, or patch notes\n5. If you cite a URL, it MUST be copied EXACTLY from the search results\n6. When in doubt, say 'I don't have current information' - DO NOT GUESS\n\nVIOLATING THESE RULES BY INVENTING INFORMATION WILL BE IMMEDIATELY DETECTED."
                        )
                        logger.info(
                            f"Added web search context for: {user_content[:50]}..."
                        )
                    else:
                        # Search returned no quality results
                        logger.info(
                            f"No quality search results for: {user_content[:50]}"
                        )
                except Exception as e:
                    logger.error(f"Web search failed: {e}")

            # Add memory recall from past conversations
            if self.summarizer:
                memory_context = await self.summarizer.build_memory_context(
                    user_content
                )
                if memory_context:
                    context_parts.append(f"\n{memory_context}")

            # Add RAG context from documents (if enabled and has documents)
            if self.rag and Config.RAG_IN_CHAT and self.rag.is_enabled():
                rag_context = self.rag.get_context(user_content, max_length=400)
                if rag_context:
                    context_parts.append(f"\n[Knowledge Base: {rag_context}]")

            # Add response style guidance for natural conversation
            context_parts.append("""
[CONVERSATIONAL STYLE GUIDE - FOLLOW THIS CAREFULLY]
• FLOW NATURALLY - Don't announce yourself, introduce yourself, or explain yourself
• NEVER say "As [character name]..." or "[Character name] here" or "Speaking as..."
• NEVER explain your status/nature mid-conversation ("I'm a god", "being immortal", etc.)
• Just BE the character - respond naturally without meta-commentary
• Avoid filler phrases like "Tell me more...", "How interesting...", "Fascinating..." (sounds fake)
• Talk like a real person, not a formal assistant
• Use contractions (I'm, you're, don't, can't) frequently
• Vary your sentence structure - mix short and long sentences
• Express genuine reactions: "Oh nice!", "Hmm interesting", "Wait really?"
• Don't be overly helpful or formal - be casual and friendly
• Match the user's energy and tone
• Response length: Aim for 2-4 sentences typically. Simple acknowledgments can be 1 sentence, but questions about YOU deserve fuller responses with personality
• NEVER give one-word answers unless it's truly appropriate (rare)
• It's okay to be uncertain or admit when you don't know something
• Use informal language when appropriate: "yeah", "nah", "totally", "pretty much"
• Show personality consistent with your character
• NEVER say "Let me know if you need anything else!" - that's robotic
• USE YOUR MEMORIES & KNOWLEDGE: If you see relevant info in the context, use it naturally as if it's your own memory
]""")

            # Inject all context into system prompt (CHARACTER FIRST, then context)
            # CRITICAL: Put character instructions FIRST so they're not overridden by context
            context_injected_prompt = (
                f"{self.system_prompt}\n\n{''.join(context_parts)}"
            )

            # Update dashboard status
            if hasattr(self.bot, "web_dashboard"):
                self.bot.web_dashboard.set_status(
                    "Thinking", f"Generating response for {message.author.name}"
                )

            # Check for image attachments
            images = []
            if Config.VISION_ENABLED and message.attachments:
                for attachment in message.attachments:
                    if is_image_attachment(attachment.filename):
                        try:
                            logger.info(
                                f"Processing image attachment: {attachment.filename}"
                            )
                            image_data = await download_attachment(attachment.url)
                            image_b64 = image_to_base64(image_data)
                            images.append(image_b64)
                        except Exception as e:
                            logger.error(f"Failed to process image attachment: {e}")
                            await message.channel.send(
                                f"⚠️ Failed to process image: {attachment.filename}"
                            )

            # Get response
            async with message.channel.typing():
                if images:
                    # Use vision model for images
                    logger.info(f"Using vision model with {len(images)} image(s)")
                    response = await self.ollama.chat_with_vision(
                        prompt=user_content,
                        images=images,
                        system_prompt=context_injected_prompt,
                    )
                else:
                    # Regular text chat
                    response = await self.ollama.chat(
                        history, system_prompt=context_injected_prompt
                    )

            # Update dashboard status
            if hasattr(self.bot, "web_dashboard"):
                self.bot.web_dashboard.set_status(
                    "Processing", "Response generated, updating profile..."
                )

            # Update user profile - increment interaction count and learn from conversation
            if self.user_profiles:
                profile = await self.user_profiles.load_profile(message.author.id)
                profile["interaction_count"] += 1
                if not profile.get("username"):
                    profile["username"] = str(message.author.name)
                await self.user_profiles.save_profile(message.author.id)

                # AI-powered learning from conversation (runs in background)
                if Config.USER_PROFILES_AUTO_LEARN:
                    try:
                        await self.user_profiles.learn_from_conversation(
                            user_id=message.author.id,
                            username=str(message.author.name),
                            user_message=user_content,
                            bot_response=response,
                        )
                    except Exception as e:
                        logger.error(f"Profile learning failed: {e}")

                # Update affection score if enabled
                if Config.USER_AFFECTION_ENABLED:
                    try:
                        await self.user_profiles.update_affection(
                            user_id=message.author.id,
                            message=user_content,
                            bot_response=response,
                        )
                    except Exception as e:
                        logger.error(f"Affection update failed: {e}")

            # Smart Summarization Trigger
            # Check if we should summarize based on message count or content
            if self.summarizer and Config.CONVERSATION_SUMMARIZATION_ENABLED:
                # 1. Message Count Trigger (existing)
                if len(history) >= Config.AUTO_SUMMARIZE_THRESHOLD:
                    # Trigger background summarization
                    self._create_background_task(
                        self.summarizer.summarize_and_store(
                            messages=history,
                            channel_id=message.channel.id,
                            participants=[message.author.name],
                            store_in_rag=Config.STORE_SUMMARIES_IN_RAG,
                        )
                    )
                    # Optionally clear history after summary to start fresh context
                    # await self.history.clear_history(message.channel.id)

                # 2. Topic Change / Conclusion Trigger (Smart)
                # If the bot says goodbye or wraps up, it's a good time to summarize
                elif any(
                    phrase in response.lower()
                    for phrase in [
                        "talk to you later",
                        "goodbye",
                        "bye for now",
                        "have a good night",
                        "see you soon",
                    ]
                ):
                    self._create_background_task(
                        self.summarizer.summarize_and_store(
                            messages=history,
                            channel_id=message.channel.id,
                            participants=[message.author.name],
                            store_in_rag=Config.STORE_SUMMARIES_IN_RAG,
                        )
                    )

            # Save to history
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(message.channel.id, "user", user_content)
                await self.history.add_message(
                    message.channel.id, "assistant", response
                )

            # Start or refresh the conversation session
            if is_mentioned:
                # Mentioned - start new session
                await self.session_manager.start_session(
                    message.channel.id, message.author.id
                )
            else:
                # Session active - just refresh
                await self.session_manager.refresh_session(message.channel.id)

            # Apply natural timing delay before responding
            if hasattr(self.bot, "naturalness") and self.bot.naturalness:
                delay = await self.bot.naturalness.get_natural_delay()
                if delay > 0:
                    await asyncio.sleep(delay)

            # Send text response
            chunks = await chunk_message(response)
            for chunk in chunks:
                await message.channel.send(chunk)

            # Track interesting topics for proactive callbacks (runs in background)
            if self.callbacks_system:
                self._create_background_task(
                    self._track_interesting_topic(message, response, history)
                )

            # Track user interaction for learning & adaptation (runs in background)
            if self.pattern_learner:
                self._create_background_task(
                    self._track_user_interaction(
                        message.author.id, user_content, response
                    )
                )

            # Check for curiosity opportunities (runs in background)
            if self.curiosity_system:
                self._create_background_task(
                    self._check_and_ask_followup(message, user_content, history)
                )

            # Also speak in voice channel if bot is connected and feature is enabled
            if Config.AUTO_REPLY_WITH_VOICE:
                # Only generate TTS if actually in a voice channel
                voice_client = message.guild.voice_client
                if voice_client and voice_client.is_connected():
                    if hasattr(self.bot, "web_dashboard"):
                        self.bot.web_dashboard.set_status(
                            "Speaking", "Generating TTS audio..."
                        )
                    await self.voice_integration.speak_response_in_voice(
                        message.guild, response
                    )

            # Reset status to Idle after a short delay
            if hasattr(self.bot, "web_dashboard"):
                # We don't await this, just let it happen
                self._create_background_task(self._reset_status_delayed())

        except Exception as e:
            logger.error(f"Auto-reply failed: {e}")
            await message.channel.send(format_error(e))

    async def _reset_status_delayed(self, delay: float = 5.0):
        """Reset dashboard status to Idle after a delay."""
        await asyncio.sleep(delay)
        if hasattr(self.bot, "web_dashboard"):
            self.bot.web_dashboard.set_status("Idle")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions for naturalness responses.

        Args:
            reaction: The reaction added
            user: User who added the reaction
        """
        if user.bot:
            return

        if hasattr(self.bot, "naturalness") and self.bot.naturalness:
            response = await self.bot.naturalness.on_reaction_add(reaction, user)
            if response:
                await reaction.message.channel.send(response)


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
