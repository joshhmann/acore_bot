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
from services.llm.ollama import OllamaService

# Intent system removed - now AI-first with LLM tool calling
# from services.intent_recognition import IntentRecognitionService, ConversationalResponder
# from services.intent_handler import IntentHandler
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
# response_handler deprecated - using _handle_chat_response method directly
from .message_handler import MessageHandler
from .commands import ChatCommandHandler

# New services
from services.core.context import ContextManager
from services.persona.lorebook import LorebookService
from services.persona.behavior import BehaviorEngine

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
        rag=None,
        conversation_manager=None,
        persona_system=None,
        compiled_persona=None,
        llm_fallback=None,
        persona_relationships=None,
    ):
        """Initialize chat cog."""
        self.bot = bot
        # Core services
        self.session_manager = SessionManager() # Moved up from below
        self.history = history_manager
        # self.context_router = context_router # This is passed in now
        self.user_profiles = user_profiles
        self.llm_fallback = llm_fallback
        self.ollama = ollama # Kept for direct access
        self.summarizer = summarizer
        self.web_search = web_search
        self.rag = rag
        self.conversation_manager = conversation_manager
        self.compiled_persona = compiled_persona # For compiled/default persona logic
        self.persona_relationships = persona_relationships  # Persona-to-persona affinity

        # Behavior Engine (Unified AI Brain)
        # self.behavior_engine = behavior_engine # This is passed in now

        # Persona Router (Multi-Character System)
        from services.persona.router import PersonaRouter
        self.persona_router = PersonaRouter(Config.CHARACTERS_DIR)
        
        # Load active personas
        # Note: We need to await this, but __init__ is sync.
        # We'll do it in cog_load or create a task.
        self._init_task = asyncio.create_task(self._async_init())

        # Compile system prompt (legacy support, will be overridden by Router)
        self.system_prompt = self._load_system_prompt()
        self.system_prompt_last_loaded = time.time()
        self.current_persona = None # Default value until _async_init completes
        
    async def _async_init(self):
        """Asynchronous initialization."""
        # 0. Core properties
        self._background_tasks: set = set()
        
        # 1. Initialize Helpers & Managers
        self.helpers = ChatHelpers()
        self.session_manager = SessionManager()
        self.voice_integration = VoiceIntegration(self.bot, self.helpers.analyze_sentiment)
        self.message_handler = MessageHandler(self)
        self.command_handler = ChatCommandHandler(self)
        
        # 2. Initialize Logic Services
        self.context_manager = ContextManager()
        self.lorebook_service = LorebookService()
        
        from services.memory.context_router import ContextRouter
        self.context_router = ContextRouter(self.history, self.summarizer)

        # 3. Initialize Behavior Engine (Needs ContextManager)
        self.behavior_engine = BehaviorEngine(
            self.bot, self.ollama, self.context_manager, self.lorebook_service
        )

        # 4. Initialize Persona Router (Loads Characters)
        await self.persona_router.initialize()
        
        # 4b. Initialize Persona Relationships (Affinity between characters)
        if self.persona_relationships:
            await self.persona_relationships.initialize()
        
        # 5. Set Initial Persona (Sync Legacy & Router)
        # Try to set Dagoth Ur as default, or first available
        default_p = self.persona_router.get_persona_by_name("Dagoth Ur")
        if not default_p:
            all_p = self.persona_router.get_all_personas()
            if all_p:
                default_p = all_p[0]
        
        if default_p:
            self.behavior_engine.set_persona(default_p)
            self.current_persona = default_p.character # Legacy support for MessageHandler
            # Compatibility shim: MessageHandler expects .name on character object? 
            # Character dataclass has .display_name. 
            # If MessageHandler accesses .name, we might need a wrapper or ignore if it fails.
            # Character dataclass DOES NOT have .name. It has .display_name.
            # MessageHandler lines 270 check .name. This might be another bug.
            logger.info(f"Set initial persona: {default_p.character.display_name}")

        # 6. Start Engines
        self._create_background_task(self.behavior_engine.start())
        self.system_prompt = self._load_system_prompt()

        # 7. cleanup unused placeholders
        self.callbacks_system = None
        self.curiosity_system = None
        self.pattern_learner = None
        self.intent_recognition = None
        self.intent_handler = None
        self.message_batcher = None
        self.agentic_tools = None
        
        logger.info("ChatCog initialization complete.")

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

    def _prepare_response_content(self, response: str, channel) -> tuple[str, str]:
        """Prepare response content for Discord display and TTS.
        
        Args:
            response: Raw LLM response text
            channel: Discord channel context
            
        Returns:
            Tuple of (discord_response, tts_response)
        """
        # 1. Basic Cleaning
        cleaned = ChatHelpers.clean_response(response)
        
        # 2. Get Guild Context
        guild = getattr(channel, "guild", None)
        
        # 3. Restore Mentions (Discord)
        if guild:
            discord_response = self.helpers.restore_mentions(cleaned, guild)
        else:
            discord_response = cleaned
            
        # 4. Clean for TTS
        tts_response = ChatHelpers.clean_for_tts(discord_response, guild)
        
        return discord_response, tts_response

    async def _stream_to_discord(self, content_iterator, interaction, guild):
        """Stream content from an iterator to a Discord interaction."""
        response = ""
        last_update = time.time()
        response_message = None
        
        async for chunk in content_iterator:
            response += chunk
            current_time = time.time()
            if current_time - last_update >= Config.STREAM_UPDATE_INTERVAL:
                # Prepare display text
                display_text = self.helpers.restore_mentions(response, guild) if guild else response
                
                if interaction:
                    if not response_message:
                        response_message = await interaction.followup.send(display_text[:2000])
                    else:
                        try:
                            await response_message.edit(content=display_text[:2000])
                        except discord.HTTPException:
                            pass
                last_update = current_time
                
        # Final update handled by caller or ensures last state
        if interaction and response_message:
             display_text = self.helpers.restore_mentions(response, guild) if guild else response
             try:
                 await response_message.edit(content=display_text[:2000])
             except: pass
        elif interaction:
             # If we never sent a message (short response), send now
             display_text = self.helpers.restore_mentions(response, guild) if guild else response
             await interaction.followup.send(display_text[:2000])
             
        return response

    async def _generate_response(self, final_messages, channel, interaction, optimal_max_tokens, recent_image_url):
        """Generate response using available strategies (Vision, Agentic, Streaming, Standard)."""
        response = ""
        guild = getattr(channel, "guild", None)
        
        # 1. Vision Processing
        if recent_image_url and Config.VISION_ENABLED:
            try:
                # Add explicit instruction about the image
                final_messages[-1]["content"] += "\n\n[Note: User is referencing the attached image]"
                response = await self.ollama.chat(final_messages, temperature=self.ollama.temperature)
                logger.info("Successfully processed recent image with vision")
                return response
            except Exception as e:
                logger.error(f"Vision processing failed: {e}")
                # Fallback continues below
        
        # 2. Agentic Tools (ReAct)
        if self.agentic_tools:
            async def llm_generate(conv):
                return await self._llm_chat(conv, system_prompt=None)
            
            user_msg_content = final_messages[-1]["content"]
            system_prompt = final_messages[0]["content"] if final_messages and final_messages[0]["role"] == "system" else ""
            
            response = await self.agentic_tools.process_with_tools(
                llm_generate_func=llm_generate,
                user_message=user_msg_content,
                system_prompt=system_prompt,
                max_iterations=3,
            )
            return response

        # 3. Streaming (Voice & Text)
        should_stream = Config.RESPONSE_STREAMING_ENABLED
        if should_stream:
            voice_client = getattr(guild, "voice_client", None) if guild else None
            use_streaming_tts = (
                Config.AUTO_REPLY_WITH_VOICE
                and voice_client
                and voice_client.is_connected()
                and not voice_client.is_playing()
            )
            
            if use_streaming_tts:
                 voice_cog = self.bot.get_cog("VoiceCog")
                 if voice_cog:
                     # Sentinel for imports
                     from utils.stream_multiplexer import StreamMultiplexer 
                     from services.voice.streaming_tts import StreamingTTSProcessor # Try import
                     
                     streaming_tts = StreamingTTSProcessor(
                         voice_cog.tts,
                         voice_cog.rvc if hasattr(voice_cog, "rvc") else None,
                     )
                     
                     # Sentiment
                     sentiment = self.helpers.analyze_sentiment(final_messages[-1]["content"])
                     kokoro_speed = 1.1 if sentiment == "positive" else 0.9 if sentiment == "negative" else 1.0
                     edge_rate = "+10%" if sentiment == "positive" else "-10%" if sentiment == "negative" else "+0%"
                     
                     llm_stream = self.ollama.chat_stream(
                         final_messages, system_prompt=None, max_tokens=optimal_max_tokens
                     )
                     multiplexer = StreamMultiplexer(llm_stream)
                     text_stream = multiplexer.create_consumer()
                     tts_stream = multiplexer.create_consumer()
                     
                     # Parallel Execution
                     results = await asyncio.gather(
                         self._stream_to_discord(text_stream, interaction, guild),
                         streaming_tts.process_stream(tts_stream, voice_client, speed=kokoro_speed, rate=edge_rate)
                     )
                     response = results[0] # The text response
                     return response
                     
            # Standard Text Streaming
            stream = self.ollama.chat_stream(final_messages, system_prompt=None, max_tokens=optimal_max_tokens)
            response = await self._stream_to_discord(stream, interaction, guild)
            return response

        # 4. Standard Non-Streaming
        response = await self.ollama.chat(final_messages, system_prompt=None, max_tokens=optimal_max_tokens)
        return response

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
        # Stop behavior engine
        if self.behavior_engine:
            await self.behavior_engine.stop()

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

    async def _prepare_final_messages(self, channel, user, message_content, selected_persona):
        """Prepare context and build final messages for LLM.
        
        Args:
            channel: Discord channel
            user: Discord user
            message_content: Message text
            selected_persona: Selected persona object
            
        Returns:
            List of message dicts (final_messages)
        """
        channel_id = channel.id
        user_id = user.id

        # 1. Load History
        history = []
        context_summary = None
        if Config.CHAT_HISTORY_ENABLED:
            context_result = await self.context_router.get_context(
                channel, user, message_content
            )
            history = context_result.history
            context_summary = context_result.summary
            
            logger.debug(
                f"Context: {len(history)} msgs, "
                f"summary: {len(context_summary) if context_summary else 0} chars, "
                f"strategy: {context_result.strategy.channel_type}"
            )

        # 2. Add current message
        history.append({
            "role": "user", 
            "content": message_content,
            "username": user.display_name
        })

        # 3. Build Context Strings
        user_context_str = ""
        rag_context_str = ""

        # User Profile
        if self.user_profiles and Config.USER_CONTEXT_IN_CHAT:
             user_context = await self.user_profiles.get_user_context(user_id)
             if user_context and user_context != "New user - no profile information yet.":
                 user_context_str += f"User Profile: {user_context}\n"
                 
                 # Special Instructions
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
        
        # Summarizer Context
        if self.summarizer:
            memory = await self.summarizer.build_memory_context(message_content)
            if memory:
                user_context_str += f"\n\nMemories:\n{memory}"
        
        # Conversation Summary
        if context_summary:
            user_context_str += f"\n\n[Earlier Conversation Summary]:\n{context_summary}"
            
        # RAG Context
        use_rag = True
        if use_rag and self.rag and Config.RAG_IN_CHAT and self.rag.is_enabled():
            persona_boost = None
            persona_categories = None
            
            # Use selected_persona for RAG filtering
            if selected_persona:
                persona_boost = getattr(selected_persona.character, "display_name", None)
                if hasattr(selected_persona.character, "knowledge_domain"):
                    kd = selected_persona.character.knowledge_domain
                    cats = kd.get("rag_categories")
                    if isinstance(cats, list):
                        persona_categories = cats
                    elif isinstance(cats, str):
                        persona_categories = [cats]
            
            rag_content = self.rag.get_context(
                message_content, 
                max_length=1500, 
                categories=persona_categories, 
                boost_category=persona_boost
            )
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

        # Lorebook
        lore_entries = []
        if self.lorebook_service:
            scan_text = message_content + "\n" + "\n".join([m["content"] for m in history[-5:]])
            lore_entries = self.lorebook_service.scan_for_triggers(
                scan_text, self.lorebook_service.get_available_lorebooks()
            )

        # 4. Determine Model & Persona
        current_model = self.ollama.get_model_name() or "gpt-3.5-turbo"
        
        if selected_persona:
            persona_to_use = selected_persona
        elif self.compiled_persona:
            persona_to_use = self.compiled_persona
        else:
             # Legacy Fallback
             from services.persona.system import CompiledPersona, Character, Framework
             dummy_char = Character("legacy", "Assistant", {}, {}, {}, {}, {})
             dummy_fw = Framework("legacy", "Legacy", "Helpful", {}, {}, {}, {}, {}, {}, "")
             persona_to_use = CompiledPersona(
                "legacy", dummy_char, dummy_fw, 
                system_prompt=self.system_prompt, 
                tools_required=[], config={}
             )

        # 5. Build Final Messages
        final_messages = await self.context_manager.build_context(
            persona=persona_to_use,
            history=history,
            model_name=current_model,
            lore_entries=lore_entries,
            rag_content=rag_context_str,
            user_context=user_context_str,
            llm_service=self.ollama
        )
        
        return final_messages

    def _select_persona(self, message_content: str, channel_id: int, original_message: Optional[discord.Message], response_reason: Optional[str]):
        """Select the appropriate persona for the response.
        
        Args:
            message_content: The message content
            channel_id: The channel ID
            original_message: The original message object (optional)
            response_reason: The reason for responding (optional)
            
        Returns:
            Selected persona object or None
        """
        # For BANTER responses, pick a DIFFERENT persona (not the one who just spoke)
        if response_reason == "persona_banter" and original_message:
            speaker_name = original_message.author.display_name.lower()
            all_personas = self.persona_router.get_all_personas()
            # Filter out the speaker
            other_personas = [p for p in all_personas 
                             if p.character.display_name.lower() != speaker_name]
            if other_personas:
                # Pick random other persona (could also weight by affinity)
                # Ensure random is imported or use extracted import
                import random
                selected_persona = random.choice(other_personas)
                logger.info(f"Banter: {selected_persona.character.display_name} jumping in on {speaker_name}'s message")
                return selected_persona
        
        # Default selection
        selected_persona = self.persona_router.select_persona(message_content, channel_id=channel_id)
        
        # Fallback
        if not selected_persona:
            if self.behavior_engine.current_persona:
                selected_persona = self.behavior_engine.current_persona
            else:
                selected_persona = self.persona_router.get_persona_by_name("Dagoth Ur")
                
        return selected_persona

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
        channel_id = channel.id if hasattr(channel, 'id') else None
        selected_persona = self._select_persona(message_content, channel_id, original_message, response_reason)

        if not selected_persona:
             logger.error("No persona available for response!")
             return

        # SELF-REPLY PREVENTION:
        # If the selected persona matches the message author (Webhook), ABORT.
        if selected_persona and original_message:
             persona_name = getattr(selected_persona.character, "display_name", "")
             author_name = original_message.author.display_name
             
             # Case-insensitive check
             if persona_name and author_name and persona_name.lower().strip() == author_name.lower().strip():
                 logger.info(f"Self-Reply Prevention: {persona_name} selected to reply to {author_name}. Aborting.")
                 return

        # Update BehaviorEngine context
        self.behavior_engine.set_persona(selected_persona)

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

        # Process with Behavior Engine (Reactions & Proactive Engagement)
        if not interaction and self.behavior_engine and original_message:
            action = await self.behavior_engine.handle_message(original_message)

            # If behavior engine wants to reply proactively (e.g. interrupt), handle it
            if action and action.get("reply"):
                # We can either append it or handle it here
                # But since we are already replying (we got triggered),
                # we usually ignore the proactive suggestion unless it's a "interrupt"
                pass

        if interaction:
            await interaction.response.defer(thinking=True)

        try:
            channel_id = channel.id
            user_id = user.id

            # --- CONTEXT BUILDING ---
            final_messages = await self._prepare_final_messages(channel, user, message_content, selected_persona)

            # Log action for self-awareness
            # Logging handled by BehaviorEngine

            # Determines max tokens based on model
            # Determines max tokens based on model
            optimal_max_tokens = self.helpers.calculate_max_tokens(
                final_messages, self.ollama.get_model_name()
            )

            # 4. Generate Response
            response = await self._generate_response(final_messages, channel, interaction, optimal_max_tokens, recent_image_url)

            # Validate and clean response (remove thinking tags, fix hallucinations)
            response = ResponseValidator.validate_response(response)

            # Enhance response with self-awareness features if enabled
            # BehaviorEngine handles response enhancement

            # BehaviorEngine handles framework effects via handle_message
            # No need for separate enhance_response call here

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
            # BehaviorEngine handles mood updates
            if False:
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
            # OPTIMIZATION: Skip learning for persona/webhook messages to reduce LLM calls
            is_webhook_message = original_message and original_message.webhook_id is not None
            
            if self.user_profiles and not is_webhook_message:
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
            # 1. Start Timing & Setup
            start_time = time.time()
            
            # 2. Persona Selection (Moved to top)
            # selected_persona already set above
            
            system_prompt = selected_persona.system_prompt
            display_name = selected_persona.character.display_name
            avatar_url = selected_persona.character.avatar_url
            
            # 3. Context Management
            # Build conversation context (history + summary + RAG)
            # Build conversation context (history + summary + RAG)
            context_result = await self.context_router.get_context(
                 channel=channel, 
                 user=user,
                 message_content=message_content
            )
            history = context_result.history
            summary = context_result.summary

            # Use Context Manager to build optimized LLM input
            # We construct a dummy/wrapped persona object if needed, or use the selected one
            context = await self.context_manager.build_context(
                persona=selected_persona,
                history=history,
                model_name=self.ollama.get_model_name(),
                lore_entries=[], # TODO: scan lore if needed
                rag_content="", # TODO: fetch RAG if needed
                user_context="", # TODO: fetch user profile if needed
                llm_service=self.ollama
            )
            
            # Add user message to context if not already there (ContextManager typically handles history+current)
            # But ContextManager.build_context expects 'history' which includes previous messages.
            # We need to append the current message OR rely on `build_context` taking `user_message`.
            # The signature of `build_context` above only took `history`. 
            # Let's check `services/core/context.py` if needed.
            # For robustness, let's manually ensure current message is at end of `context` list if missing.
            if not context or context[-1]["role"] != "user":
                context.append({"role": "user", "content": message_content})

            # 4. Generate Response
            response = await self._llm_chat(
                messages=context,
                system_prompt=None, # System prompt is inside context[0]
            )
            
            # 5. Post-Processing & Sending
            # 5. Post-Processing & Sending
            discord_response, tts_response = self._prepare_response_content(response, channel)
            
            # Send via Webhook (Spoofing) or Fallback
            sent_via_webhook = False
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    webhooks = await channel.webhooks()
                    webhook = next((w for w in webhooks if w.name == "PersonaBot_Proxy"), None)
                    if not webhook:
                        webhook = await channel.create_webhook(name="PersonaBot_Proxy")
                    
                    chunks = await chunk_message(discord_response)
                    for chunk in chunks:
                        await webhook.send(
                            content=chunk, 
                            username=display_name, 
                            avatar_url=avatar_url,
                            wait=True
                        )
                    sent_via_webhook = True
                except Exception as e:
                    logger.warning(f"Webhook failed: {e}")

            if not sent_via_webhook:
                prefix = f"**[{display_name}]**: "
                chunks = await chunk_message(prefix + discord_response)
                for chunk in chunks:
                    await channel.send(chunk)

            # 6. Record Interaction Details (Metrics & Learning)
            await self._record_interaction(
                user, channel, message_content, response, start_time, original_message, selected_persona
            )

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





    async def _record_interaction(self, user, channel, message_content, response, start_time, original_message, selected_persona):
        """Record metrics, learning, affection, and other interaction details."""
        channel_id = channel.id
        user_id = user.id
        
        # 1. Sticky Persona Tracking
        if self.persona_router and selected_persona:
            self.persona_router.record_response(channel_id, selected_persona)

        # 2. Persona Relationships (Banter Affinity)
        # Only record if original message was from a persona (webhook)
        if original_message and original_message.webhook_id and self.persona_relationships and selected_persona:
            speaker_name = original_message.author.display_name
            responder_name = selected_persona.character.display_name
            
            # Record interaction (increases affinity by 2)
            self._create_background_task(
                self.persona_relationships.record_interaction(
                    speaker=speaker_name,
                    responder=responder_name,
                    affinity_change=2,
                    memory=None  # Could extract memorable moment with LLM later
                )
            )
            # Save relationships in background
            self._create_background_task(self.persona_relationships.save())
            
        # 3. Voice Reply (Environmental)
        # We need the tts_response. Re-clean it or pass it?
        # Clean response for TTS again (fast enough) or re-calc. 
        # Ideally we should pass tts_response, but let's re-clean for now to keep signature simple or pass it in.
        # Actually, let's just re-clean it.
        guild = getattr(channel, "guild", None)
        tts_response = ChatHelpers.clean_for_tts(response, guild) if guild else response
        
        if Config.AUTO_REPLY_WITH_VOICE:
             voice_client = guild.voice_client if guild else None
             if voice_client and voice_client.is_connected():
                 await self.voice_integration.speak_response_in_voice(
                     guild, tts_response
                 )

        # 4. Metrics
        if hasattr(self.bot, "metrics"):
            duration_ms = (time.time() - start_time) * 1000
            self.bot.metrics.record_response_time(duration_ms)
            self.bot.metrics.record_message(user_id, channel_id)

    async def _safe_learn_from_conversation(self, user_id: int, username: str, user_message: str, bot_response: str):
        """Wrapper to safely call user profile learning."""
        if not self.user_profiles: return
        
        try:
            await self.user_profiles.learn_from_conversation(
                user_id=user_id,
                username=username,
                user_message=user_message,
                bot_response=bot_response
            )
        except Exception as e:
            logger.warning(f"Failed to learn from conversation: {e}")

    async def _safe_update_affection(self, user_id: int, message: str, bot_response: str):
        """Wrapper to safely call affection update."""
        if not self.user_profiles: return
        
        try:
            await self.user_profiles.update_affection(
                user_id=user_id,
                message=message,
                bot_response=bot_response
            )
        except Exception as e:
            logger.warning(f"Failed to update affection: {e}")


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
