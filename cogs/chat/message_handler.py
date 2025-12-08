"""Message handler for ChatCog."""

import logging
import discord
from discord.ext import commands
import asyncio
import random
import re
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from config import Config

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, cog: commands.Cog):
        self.cog = cog
        self._processed_messages = {}

    async def _track_interesting_topic(
        self, message: discord.Message, bot_response: str, conversation_history: list
    ):
        """Track interesting topics for proactive callbacks."""
        if not self.cog.callbacks_system:
            return

        try:
            # Build conversation context
            context_messages = conversation_history[-5:] if conversation_history else []
            context = "\n".join(
                [
                    f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:100]}"
                    for msg in context_messages
                ]
            )

            # Ask LLM to extract topic and assess importance
            prompt = f"""Analyze this conversation and determine if there's an interesting topic worth remembering for later.

Conversation:
{context}

Latest message: {message.content[:200]}
Bot response: {bot_response[:200]}

Extract:
1. Topic (brief, 5-10 words)
2. Importance (0.0 to 1.0, where 0.5+ is worth remembering)
3. Sentiment (positive/negative/neutral/excited)
4. Keywords (3-5 relevant keywords)

Respond in JSON format:
{{"topic": "...", "importance": 0.0, "sentiment": "neutral", "keywords": ["..."]}}

If this conversation isn't interesting enough to remember, set importance to 0.0.
JSON only:"""

            response = await self.cog.ollama.generate(prompt, max_tokens=200)

            if not response:
                return

            # Parse JSON response
            try:
                # Try to extract JSON from response
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())

                    topic = data.get("topic", "")
                    importance = float(data.get("importance", 0.0))
                    sentiment = data.get("sentiment", "neutral")
                    keywords = data.get("keywords", [])

                    if importance >= 0.3 and topic:
                        # Store the topic memory
                        self.cog.callbacks_system.add_topic_memory(
                            topic=topic,
                            context=context,
                            users=[message.author.name],
                            channel_id=message.channel.id,
                            importance=importance,
                            sentiment=sentiment,
                            keywords=keywords,
                        )
                        logger.debug(
                            f"Tracked topic (importance {importance:.2f}): {topic}"
                        )

            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse topic extraction JSON: {e}")

        except Exception as e:
            logger.warning(f"Failed to track interesting topic: {e}")

    async def _check_and_ask_followup(
        self, message: discord.Message, user_content: str, conversation_history: list
    ):
        """Check if we should ask a follow-up question and ask it."""
        if not self.cog.curiosity_system:
            return

        try:
            # Give the bot a moment to "think" before asking
            await asyncio.sleep(random.uniform(2.0, 5.0))

            # Build context from history
            context_messages = [
                msg.get("content", "")
                for msg in conversation_history[-5:]
                if msg.get("content")
            ]

            # Check if we should ask a question
            opportunity = await self.cog.curiosity_system.should_ask_question(
                message_content=user_content,
                channel_id=message.channel.id,
                conversation_context=context_messages,
            )

            if not opportunity:
                return

            # Generate the follow-up question
            question = await self.cog.curiosity_system.generate_followup_question(
                opportunity=opportunity, message_content=user_content
            )

            if question:
                # Send the question with typing indicator
                async with message.channel.typing():
                    # Small delay for natural feel
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    await message.channel.send(question)

                # Mark that we asked
                self.cog.curiosity_system.mark_question_asked(
                    message.channel.id, opportunity.topic
                )
                logger.info(f"Asked curious follow-up: {question[:50]}...")

        except Exception as e:
            logger.warning(f"Failed to ask follow-up question: {e}")

    async def _track_user_interaction(
        self, user_id: int, user_message: str, bot_response: str
    ):
        """Track user interaction for learning & adaptation."""
        if not self.cog.pattern_learner:
            return

        try:
            # Track the interaction (reaction detection could be added later)
            self.cog.pattern_learner.learn_user_interaction(
                user_id=user_id,
                user_message=user_message,
                bot_response=bot_response,
                user_reaction=None,  # Could detect reactions/emoji later
            )

        except Exception as e:
            logger.warning(f"Failed to track user interaction: {e}")

    async def _safe_learn_from_conversation(
        self, user_id: int, username: str, user_message: str, bot_response: str
    ):
        """Wrapper to run learning safely in background."""
        try:
            await self.cog.user_profiles.learn_from_conversation(
                user_id=user_id,
                username=username,
                user_message=user_message,
                bot_response=bot_response,
            )
        except Exception as e:
            logger.error(f"Background profile learning failed: {e}")

    async def _safe_update_affection(
        self, user_id: int, message: str, bot_response: str
    ):
        """Wrapper to run affection update safely in background."""
        try:
            await self.cog.user_profiles.update_affection(
                user_id=user_id, message=message, bot_response=bot_response
            )
        except Exception as e:
            logger.error(f"Background affection update failed: {e}")

    async def check_and_handle_message(self, message: discord.Message) -> bool:
        """Check if message should be handled as chat and process it."""
        # Ignore self, bots, and system messages
        logger.debug(
            f"check_and_handle_message: msg_id={message.id}, author={message.author.name} (bot={message.author.bot}), content='{message.content[:50]}'"
        )
        if message.author.bot or message.is_system():
            return False

        # Ignore users in the ignore list
        if message.author.id in Config.IGNORED_USERS:
            logger.debug(
                f"Ignoring message from ignored user: {message.author.name} ({message.author.id})"
            )
            return False

        # Ignore commands (starting with prefix)
        if message.content.startswith(self.cog.bot.command_prefix):
            return False

        # Ignore messages with #ignore tag
        if "#ignore" in message.content.lower():
            return False

        message_key = f"{message.id}_{message.channel.id}"
        if message_key in self._processed_messages:
            logger.debug(f"Skipping duplicate message {message.id}")
            return True

        # Mark as processed
        self._processed_messages[message_key] = True

        # Clean up old entries (keep last 100)
        if len(self._processed_messages) > 100:
            keys = list(self._processed_messages.keys())
            for key in keys[:50]:
                del self._processed_messages[key]

        # Check if we should respond
        should_respond = False
        response_reason = None
        suggested_style = None

        # 1. Direct Mention (ALWAYS respond)
        if self.cog.bot.user in message.mentions:
            should_respond = True
            response_reason = "mentioned"
            suggested_style = "direct"

        # 2. Reply to bot (ALWAYS respond)
        elif message.reference:
            try:
                ref_msg = await message.channel.fetch_message(
                    message.reference.message_id
                )
                if ref_msg.author == self.cog.bot.user:
                    should_respond = True
                    response_reason = "reply_to_bot"
                    suggested_style = "conversational"
            except (discord.NotFound, discord.HTTPException) as e:
                logger.debug(f"Could not fetch referenced message: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error fetching referenced message: {e}")

        # 3. Name trigger (ALWAYS respond)
        if not should_respond:
            # Get bot names (user name, persona name)
            bot_names = [self.cog.bot.user.name.lower(), "bot", "computer", "assistant"]

            # Add first name
            if " " in self.cog.bot.user.name:
                bot_names.append(self.cog.bot.user.name.split(" ")[0].lower())

            # Add nickname if in a guild
            if isinstance(message.channel, discord.TextChannel):
                if message.guild.me.nick:
                    bot_names.append(message.guild.me.nick.lower())

            if self.cog.current_persona:
                bot_names.append(self.cog.current_persona.name.lower())
                # Add persona first name
                if " " in self.cog.current_persona.name:
                    bot_names.append(self.cog.current_persona.name.split(" ")[0].lower())

                if hasattr(self.cog.current_persona, "display_name"):
                    bot_names.append(self.cog.current_persona.display_name.lower())

            content_lower = message.content.lower()
            # Check if name is in message
            if any(name in content_lower for name in bot_names):
                should_respond = True
                response_reason = "name_trigger"
                suggested_style = "direct"
                logger.info(
                    f"Message triggered by name mention: {message.content[:20]}..."
                )

        # 4. Image reference / Question about attachment (ALWAYS respond)
        if not should_respond:
            image_keywords = [
                "what is this",
                "what is that",
                "who is this",
                "who is that",
                "look at this",
                "look at that",
                "describe this",
                "describe that",
                "thoughts?",
                "opinion?",
                "can you see",
                "do you see",
            ]
            content_lower = message.content.lower()
            if any(k in content_lower for k in image_keywords):
                # Case A: Current message has attachment
                if message.attachments or message.embeds:
                    should_respond = True
                    response_reason = "image_question"
                    suggested_style = "descriptive"

                # Case B: Recent message has attachment (User posted image then asked)
                else:
                    try:
                        async for msg in message.channel.history(
                            limit=3, before=message
                        ):
                            if msg.attachments or msg.embeds:
                                should_respond = True
                                response_reason = "image_question"
                                suggested_style = "descriptive"
                                break
                    except Exception:
                        pass

        # 5. Behavior Engine (replaced decision_engine)
        if not should_respond and hasattr(self.cog, 'behavior_engine') and self.cog.behavior_engine:
            try:
                decision_context = {
                    "channel_id": message.channel.id,
                    "user_id": message.author.id,
                    "mentioned": self.cog.bot.user in message.mentions,
                    "has_question": "?" in message.content,
                    "message_length": len(message.content),
                }

                # BehaviorEngine uses handle_message instead of should_respond
                decision = await self.cog.behavior_engine.handle_message(message)

                if decision:
                    # Handle reactions
                    if decision.get("reaction"):
                        try:
                            await message.add_reaction(decision["reaction"])
                            logger.info(f"✨ Behavior Engine: Reacted with {decision['reaction']}")
                        except Exception as e:
                            logger.warning(f"Failed to add reaction: {e}")

                    if decision.get("should_respond"):
                        should_respond = True
                        response_reason = f"behavior_engine:{decision.get('reason', 'unknown')}"
                        suggested_style = decision.get("suggested_style")
                        logger.info(
                            f"✨ Behavior Engine: RESPOND - Reason: {decision.get('reason')}, Style: {suggested_style}"
                        )
                    else:
                        logger.debug(
                            f"Behavior Engine: SKIP - Reason: {decision.get('reason')}"
                        )

            except Exception as e:
                logger.warning(f"AI Decision Engine failed: {e}")

        # 6. Conversation context tracking (Fallback)
        if not should_respond:
            channel_id = message.channel.id

            last_time = self.cog.session_manager.get_last_response_time(channel_id)
            if last_time:
                time_since = datetime.now() - last_time
                if time_since < timedelta(minutes=5):
                    should_respond = True
                    response_reason = "conversation_context"
                    suggested_style = "conversational"
                    logger.info(
                        f"Responding due to recent conversation context ({time_since.seconds}s ago)"
                    )

        # 7. Ambient channel fallback
        if not should_respond and Config.AMBIENT_CHANNELS:
            if message.channel.id in Config.AMBIENT_CHANNELS:
                if len(message.content.strip()) >= 3:
                    should_respond = True
                    response_reason = "ambient_channel"
                    suggested_style = "casual"
                    logger.info(
                        f"Responding in always-respond channel: {message.channel.name}"
                    )

        # 8. AI-powered message detection for ambient channels
        if not should_respond and Config.AMBIENT_CHANNELS:
            if message.channel.id in Config.AMBIENT_CHANNELS:
                try:
                    persona_name = "Dagoth Ur"
                    if self.cog.current_persona:
                        persona_name = self.cog.current_persona.name

                    prompt = f"""Message: "{message.content}"

Is this message likely directed at {persona_name} or asking a question that {persona_name} should answer?
Consider: questions, statements that seem to want a response, or conversational prompts.
Answer ONLY "yes" or "no"."""

                    # Use cog.ollama instead of bot.ollama
                    response = await self.cog.ollama.generate(prompt)

                    if "yes" in response.lower():
                        should_respond = True
                        response_reason = "ai_ambient_detection"
                        suggested_style = "helpful"
                        logger.info(
                            f"AI detected message directed at bot: {message.content[:30]}..."
                        )
                except Exception as e:
                    logger.debug(f"AI message detection failed: {e}")
                    # Fallback
                    content_lower = message.content.lower()
                    if "?" in message.content or any(
                        content_lower.startswith(q)
                        for q in ["what", "why", "how", "when", "where", "who"]
                    ):
                        should_respond = True
                        response_reason = "question_detection"
                        suggested_style = "helpful"
                        logger.info(
                            f"Fallback question detection: {message.content[:30]}..."
                        )

        if should_respond:
            self.cog.session_manager.update_response_time(message.channel.id)

            logger.info(
                f"Responding to message - Reason: {response_reason}, Style: {suggested_style}"
            )

            async def respond_callback(
                combined_content: str, original_message: discord.Message
            ):
                """Callback to handle response after batching decision."""
                async with message.channel.typing():
                    # Call the cog's handle_chat_response
                    await self.cog._handle_chat_response(
                        message_content=combined_content,
                        channel=original_message.channel,
                        user=original_message.author,
                        original_message=original_message,
                        response_reason=response_reason,
                        suggested_style=suggested_style,
                    )

            if hasattr(self.cog, "message_batcher") and self.cog.message_batcher:
                await self.cog.message_batcher.add_message(message, respond_callback)
            else:
                await respond_callback(message.content, message)
            return True

        return False
