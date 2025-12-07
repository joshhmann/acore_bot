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
# Intent system removed - now AI-first with LLM tool calling
# from services.intent_recognition import IntentRecognitionService, ConversationalResponder
# from services.intent_handler import IntentHandler
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
from .message_handler import MessageHandler
from .commands import ChatCommandHandler

# New services
from services.context_manager import ContextManager
from services.lorebook_service import LorebookService

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
        self.message_handler = MessageHandler(self)
        self.command_handler = ChatCommandHandler(self)

        # Initialize new services
        self.context_manager = ContextManager()
        self.lorebook_service = LorebookService()

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

        # Intent system removed - LLM handles intents via tool calling now
        self.intent_recognition = None
        self.intent_handler = None

        # AI-powered message batching - feature removed during cleanup
        # from services.message_batcher import MessageBatcher
        # self.message_batcher = MessageBatcher(bot, ollama)
        # logger.info("AI-powered message batching initialized")
        self.message_batcher = None

        # Agentic tool system disabled pending consolidation with enhanced_tools
        # from services.agentic_tools import AgenticToolSystem
        # self.agentic_tools = AgenticToolSystem()
        self.agentic_tools = None  # TODO: Consolidate with enhanced_tools

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

            # --- CONTEXT BUILDING ---

            # 1. Gather all dynamic context strings
            user_context_str = ""
            rag_context_str = ""

            # User Context
            if self.user_profiles and Config.USER_CONTEXT_IN_CHAT:
                user_context = await self.user_profiles.get_user_context(user_id)
                if user_context and user_context != "New user - no profile information yet.":
                    user_context_str += f"User Profile: {user_context}\n"

                    # Special Instructions from Profile
                    profile = await self.user_profiles.load_profile(user.id)
                    special_instructions = []
                    for fact_entry in profile.get("facts", []):
                        fact_text = fact_entry.get("fact", "") if isinstance(fact_entry, dict) else str(fact_entry)
                        fact_lower = fact_text.lower()
                        if any(k in fact_lower for k in ["when you see", "always say", "greet with", "call them", "respond with", "call me"]):
                            special_instructions.append(fact_text)
                    if special_instructions:
                        user_context_str += "\nInstructions:\n" + "\n".join(f"- {inst}" for inst in special_instructions)

                # Affection
                if Config.USER_AFFECTION_ENABLED:
                    affection = self.user_profiles.get_affection_context(user_id)
                    if affection:
                        user_context_str += f"\nRelationship: {affection}"

            # Memory / Summarizer Context
            if self.summarizer:
                memory = await self.summarizer.build_memory_context(message_content)
                if memory:
                    user_context_str += f"\n\nMemories:\n{memory}"

            # RAG Context
            if self.rag and Config.RAG_IN_CHAT and self.rag.is_enabled():
                persona_boost = None
                if self.compiled_persona:
                     # Use framework purpose or character name as boost category logic
                     persona_boost = self.compiled_persona.character.display_name

                rag_content = self.rag.get_context(message_content, max_length=1500, boost_category=persona_boost)
                if rag_content:
                    rag_context_str = rag_content

            # Web Search
            if self.web_search and await self.web_search.should_search(message_content):
                try:
                    search_res = await self.web_search.get_context(message_content, max_length=1000)
                    if search_res:
                        rag_context_str += f"\n\n[WEB SEARCH RESULTS]\n{search_res}"
                except Exception as e:
                    logger.error(f"Web search failed: {e}")

            # Lorebook Scanning
            lore_entries = []
            if self.lorebook_service:
                # Scan full text (history + current)
                scan_text = message_content + "\n" + "\n".join([m['content'] for m in history[-5:]])
                lore_entries = self.lorebook_service.scan_for_triggers(
                    scan_text,
                    self.lorebook_service.get_available_lorebooks()
                )

            # Determine Model for Token Counting
            current_model = self.ollama.get_model_name() or "gpt-3.5-turbo"

            # Build Final Messages with Token Budgeting
            # If we have a compiled persona, use it. Otherwise create a temporary wrapper for legacy system prompt.
            if self.compiled_persona:
                persona_to_use = self.compiled_persona
            else:
                # Fallback: Wrap legacy system prompt in a dummy compiled persona structure
                # This is a bit hacky but ensures compatibility with ContextManager
                from services.persona_system import CompiledPersona, Character, Framework
                dummy_char = Character("legacy", "Assistant", {}, {}, {}, {}, {})
                dummy_fw = Framework("legacy", "Legacy", "Helpful", {}, {}, {}, {}, {}, {}, "")
                persona_to_use = CompiledPersona(
                    "legacy", dummy_char, dummy_fw,
                    system_prompt=self.system_prompt,
                    tools_required=[], config={}
                )

            # Use Context Manager to build optimized history
            final_messages = await self.context_manager.build_context(
                persona=persona_to_use,
                history=history,
                model_name=current_model,
                lore_entries=lore_entries,
                rag_content=rag_context_str,
                user_context=user_context_str
            )

            # Log action for self-awareness
            if self.naturalness:
                self.naturalness.log_action("chat", f"User: {str(user.name)}")

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

                        # Add image to last user message in final_messages
                        # Note: This assumes the last message is from user. ContextManager preserves order.
                        # Ollama expects "images" field in the message dict
                        if final_messages and final_messages[-1]['role'] == 'user':
                             final_messages[-1]['images'] = [image_base64]

                        # Add explicit instruction about the image
                        final_messages[-1]['content'] += "\n\n[Note: User is referencing the attached image]"

                        # Use vision model
                        # Note: standard chat endpoint supports images in Ollama now if model supports it
                        response = await self.ollama.chat(
                            final_messages,
                            temperature=self.ollama.temperature,
                        )

                        logger.info("Successfully processed recent image with vision")
                    else:
                        # Fallback to text-only if download failed
                        response = await self.ollama.chat(
                            final_messages,
                            max_tokens=optimal_max_tokens,
                        )
                except Exception as e:
                    logger.error(f"Vision processing failed for recent image: {e}")
                    # Fallback to text-only
                    response = await self._llm_chat(
                        final_messages,
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

                     # Extract user message from final_messages for tool processing
                     user_msg_content = final_messages[-1]['content']

                     # Extract system prompt from the first message
                     system_prompt = final_messages[0]['content'] if final_messages and final_messages[0]['role'] == 'system' else ""

                     response = await self.agentic_tools.process_with_tools(
                        llm_generate_func=llm_generate,
                        user_message=user_msg_content,
                        system_prompt=system_prompt,
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
                            # Pass final_messages which already includes system prompt
                            llm_stream = self.ollama.chat_stream(
                                final_messages,
                                system_prompt=None, # Already in messages
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
                                final_messages,
                                system_prompt=None,
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
                            final_messages,
                            system_prompt=None,
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
                        final_messages,
                        system_prompt=None,
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
        """Chat with Ollama AI."""
        await self.command_handler.chat(interaction, message)

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
        """Control ambient mode."""
        await self.command_handler.ambient(interaction, action)

    @app_commands.command(
        name="end_session", description="End the current conversation session"
    )
    async def end_session(self, interaction: discord.Interaction):
        """End the active conversation session in this channel."""
        await self.command_handler.end_session(interaction)


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
