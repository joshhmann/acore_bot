"""Response handling logic for chat - extracted from main.py for maintainability.

This module contains the core _handle_chat_response method which handles:
- Message validation and preprocessing
- Context building (RAG, history, user profiles)
- LLM response generation
- Post-processing (TTS, naturalness enhancement)
- Response delivery

Usage:
    In main.py, import and bind to the ChatCog instance:
    
    from .response_handler import _handle_chat_response
    
    class ChatCog:
        def __init__(self, ...):
            ...
            self._handle_chat_response = _handle_chat_response.__get__(self)
"""

import discord
import logging
import asyncio
import time
import json
import re
import random
from typing import Optional
from datetime import datetime

from config import Config
from utils.response_validator import ResponseValidator
from utils.helpers import (
    chunk_message,
    format_error,
    format_success,
    download_attachment,
    image_to_base64,
    is_image_attachment,
)

logger = logging.getLogger(__name__)

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

        # Build system prompt with context using ContextBuilder
        context_injected_prompt = await self.context_builder.build_context(
            user=user,
            channel=channel,
            user_content=message_content,
            history=history,
            suggested_style=suggested_style
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

                # FIXME: Streaming TTS disabled. Missing StreamingTTSProcessor and StreamMultiplexer.
                if use_streaming_tts and False:
                    pass
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

