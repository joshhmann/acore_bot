"""Chat cog for Ollama-powered conversations."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, Dict
from pathlib import Path
import uuid
import time
import json
import re
import asyncio

from config import Config
from services.ollama import OllamaService
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
        """
        self.bot = bot
        self.ollama = ollama
        self.history = history_manager
        self.user_profiles = user_profiles
        self.summarizer = summarizer
        self.web_search = web_search
        self.naturalness = naturalness

        # Conversational callbacks
        try:
            from services.conversational_callbacks import ConversationalCallbacks
            self.callbacks = ConversationalCallbacks(history_manager, summarizer)
            logger.info("Conversational callbacks initialized")
        except Exception as e:
            logger.warning(f"Could not load conversational callbacks: {e}")
            self.callbacks = None

        # Load persona configurations
        self.persona_loader = PersonaLoader()

        # Load system prompt from file or env
        self.system_prompt = self._load_system_prompt()

        # Track current persona config
        self.current_persona = None

        # Track active conversation sessions per channel
        # Format: {channel_id: {"user_id": user_id, "last_activity": timestamp}}
        self.active_sessions: Dict[int, Dict] = {}

    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis heuristic."""
        text = text.lower()
        positive_words = ["!", "awesome", "great", "love", "amazing", "excited", "happy", "yay", "wow", "excellent", "good", "haha"]
        negative_words = ["sorry", "sad", "unfortunate", "regret", "bad", "terrible", "awful", "depressed", "grief", "miss", "pain"]
        
        pos_score = sum(1 for w in positive_words if w in text)
        neg_score = sum(1 for w in negative_words if w in text)
        
        if pos_score > neg_score:
            return "positive"
        elif neg_score > pos_score:
            return "negative"
        return "neutral"

    def _load_system_prompt(self) -> str:
        """Load system prompt from file or environment variable.

        Returns:
            System prompt string
        """
        # Check if SYSTEM_PROMPT is set directly in env (takes precedence)
        if Config.SYSTEM_PROMPT:
            logger.info("Using system prompt from environment variable")
            return Config.SYSTEM_PROMPT

        # Try to load from file
        prompt_file = Path(Config.SYSTEM_PROMPT_FILE)
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                    logger.info(f"Loaded system prompt from {prompt_file}")
                    return prompt
            except Exception as e:
                logger.error(f"Failed to load prompt from {prompt_file}: {e}")

        # Fallback to default
        default_prompt = (
            "You are a helpful AI assistant in a Discord server. "
            "Keep your responses concise and friendly. "
            "You can use Discord markdown for formatting."
        )
        logger.warning(f"Using default system prompt (file not found: {prompt_file})")
        return default_prompt

    def _start_session(self, channel_id: int, user_id: int):
        """Start or refresh a conversation session.

        Args:
            channel_id: Discord channel ID
            user_id: User ID who initiated the session
        """
        self.active_sessions[channel_id] = {
            "user_id": user_id,
            "last_activity": time.time()
        }
        logger.info(f"Started conversation session in channel {channel_id} for user {user_id}")

    def _refresh_session(self, channel_id: int):
        """Refresh the timeout for an active session.

        Args:
            channel_id: Discord channel ID
        """
        if channel_id in self.active_sessions:
            self.active_sessions[channel_id]["last_activity"] = time.time()
            logger.debug(f"Refreshed session in channel {channel_id}")

    def _is_session_active(self, channel_id: int) -> bool:
        """Check if a conversation session is still active.

        Args:
            channel_id: Discord channel ID

        Returns:
            True if session is active and hasn't timed out
        """
        if channel_id not in self.active_sessions:
            return False

        session = self.active_sessions[channel_id]
        elapsed = time.time() - session["last_activity"]

        if elapsed > Config.CONVERSATION_TIMEOUT:
            # Session timed out
            logger.info(f"Session timed out in channel {channel_id} after {elapsed:.0f}s")
            del self.active_sessions[channel_id]
            return False

        return True

    def _end_session(self, channel_id: int):
        """Manually end a conversation session.

        Args:
            channel_id: Discord channel ID
        """
        if channel_id in self.active_sessions:
            del self.active_sessions[channel_id]
            logger.info(f"Ended session in channel {channel_id}")

    async def _safe_learn_from_conversation(self, user_id: int, username: str, user_message: str, bot_response: str):
        """Wrapper to run learning safely in background."""
        try:
            await self.user_profiles.learn_from_conversation(
                user_id=user_id,
                username=username,
                user_message=user_message,
                bot_response=bot_response
            )
        except Exception as e:
            logger.error(f"Background profile learning failed: {e}")

    async def _safe_update_affection(self, user_id: int, message: str, bot_response: str):
        """Wrapper to run affection update safely in background."""
        try:
            await self.user_profiles.update_affection(
                user_id=user_id,
                message=message,
                bot_response=bot_response
            )
        except Exception as e:
            logger.error(f"Background affection update failed: {e}")

    @app_commands.command(name="chat", description="Chat with the AI")
    @app_commands.describe(message="Your message to the AI")
    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with Ollama AI.

        Args:
            interaction: Discord interaction
            message: User's message
        """
        await interaction.response.defer(thinking=True)

        try:
            channel_id = interaction.channel_id
            user_id = interaction.user.id

            # Load conversation history
            history = []
            if Config.CHAT_HISTORY_ENABLED:
                history = await self.history.load_history(channel_id)

            # Add user message
            history.append({"role": "user", "content": message})

            # Build system prompt with context (TIME FIRST so it's most prominent)
            context_parts = [SystemContextProvider.get_compact_context()]

            # Add multi-user context
            multi_user_context = self.history.build_multi_user_context(history)
            if multi_user_context:
                context_parts.append(f"\n[Context: {multi_user_context}]")

            # Add user profile context if enabled
            if self.user_profiles and Config.USER_CONTEXT_IN_CHAT:
                user_context = await self.user_profiles.get_user_context(user_id)
                if user_context and user_context != "New user - no profile information yet.":
                    context_parts.append(f"\n[User Info: {user_context}]")

                # Add affection/relationship context if enabled
                if Config.USER_AFFECTION_ENABLED:
                    affection_context = self.user_profiles.get_affection_context(user_id)
                    if affection_context:
                        context_parts.append(f"\n[Relationship: {affection_context}]")

            # Add memory recall from past conversations
            if self.summarizer:
                memory_context = await self.summarizer.build_memory_context(message)
                if memory_context:
                    context_parts.append(f"\n{memory_context}")

            # Track conversation topics for callbacks
            if self.callbacks:
                await self.callbacks.track_conversation_topic(
                    channel_id,
                    message,
                    str(interaction.user.name)
                )

                # Check for callback opportunities
                callback_prompt = await self.callbacks.get_callback_opportunity(channel_id, message)
                if callback_prompt:
                    context_parts.append(f"\n{callback_prompt}")

                # Add recent conversation context
                recent_context = await self.callbacks.get_recent_context(channel_id)
                if recent_context:
                    context_parts.append(f"\n{recent_context}")

            # Track message rhythm
            if self.naturalness:
                self.naturalness.track_message_rhythm(channel_id, len(message))

                # Add rhythm-based style guidance
                rhythm_prompt = self.naturalness.get_rhythm_style_prompt(channel_id)
                if rhythm_prompt:
                    context_parts.append(f"\n{rhythm_prompt}")

                # Add voice context if applicable
                if interaction.guild:
                    voice_context = self.naturalness.get_voice_context(interaction.guild)
                    if voice_context:
                        context_parts.append(f"\n{voice_context}")

            # Add web search results if query needs current information
            if self.web_search and await self.web_search.should_search(message):
                try:
                    search_context = await self.web_search.get_context(message, max_length=800)
                    if search_context:
                        context_parts.append(f"\n\n{'='*60}\n[REAL-TIME WEB SEARCH RESULTS - READ THIS EXACTLY]\n{'='*60}\n{search_context}\n{'='*60}\n[END OF WEB SEARCH RESULTS]\n{'='*60}\n\n[CRITICAL INSTRUCTIONS - VIOLATION WILL BE DETECTED]\n1. You MUST ONLY cite information that appears EXACTLY in the search results above\n2. COPY the exact URLs shown - DO NOT modify or create new ones\n3. If search results are irrelevant (e.g., wrong topic, unrelated content), tell the user: 'The search didn't return relevant results'\n4. DO NOT invent Steam pages, Reddit posts, YouTube videos, or patch notes\n5. If you cite a URL, it MUST be copied EXACTLY from the search results\n6. When in doubt, say 'I don't have current information' - DO NOT GUESS\n\nVIOLATING THESE RULES BY INVENTING INFORMATION WILL BE IMMEDIATELY DETECTED.")
                        logger.info(f"Added web search context for: {message[:50]}...")
                except Exception as e:
                    logger.error(f"Web search failed: {e}")

            # Add mood context if naturalness service is available
            if self.naturalness and Config.MOOD_SYSTEM_ENABLED:
                mood_context = self.naturalness.get_mood_context()
                if mood_context:
                    context_parts.append(f"\n{mood_context}")

            # Add response style guidance
            context_parts.append("\n[Style: Match the conversation's energy. Keep responses natural and conversational - typically 1-2 sentences for simple questions/comments, longer only when genuinely needed for complex topics or storytelling.]")

            # Inject all context into system prompt (TIME at the VERY START)
            context_injected_prompt = f"{''.join(context_parts)}\n\n{self.system_prompt}"

            # Log action for self-awareness
            if self.naturalness:
                self.naturalness.log_action("chat", f"User: {str(interaction.user.name)}")

            # Get AI response with streaming if enabled
            if Config.RESPONSE_STREAMING_ENABLED:
                response = ""
                response_message = None
                last_update = time.time()

                async for chunk in self.ollama.chat_stream(history, system_prompt=context_injected_prompt):
                    response += chunk

                    # Update message periodically to avoid rate limits
                    current_time = time.time()
                    if current_time - last_update >= Config.STREAM_UPDATE_INTERVAL:
                        if not response_message:
                            response_message = await interaction.followup.send(response[:2000])
                        else:
                            try:
                                await response_message.edit(content=response[:2000])
                            except discord.HTTPException:
                                pass  # Rate limit hit, skip this update
                        last_update = current_time

                # Send final update if needed
                if response_message:
                    try:
                        await response_message.edit(content=response[:2000])
                    except discord.HTTPException:
                        pass
                else:
                    await interaction.followup.send(response[:2000])
            else:
                # Non-streaming fallback
                response = await self.ollama.chat(history, system_prompt=context_injected_prompt)

            # Enhance response with self-awareness features if enabled
            if self.naturalness and Config.SELF_AWARENESS_ENABLED:
                response = self.naturalness.enhance_response(response, context="chat")

            # Update mood based on interaction
            if self.naturalness and Config.MOOD_UPDATE_FROM_INTERACTIONS:
                # Analyze sentiment
                sentiment = self._analyze_sentiment(message)
                # Check if conversation is interesting (has questions, details, etc.)
                is_interesting = len(message.split()) > 10 or "?" in message or "how" in message.lower()
                self.naturalness.update_mood(sentiment, is_interesting)

            # Update user profile - increment interaction count and learn from conversation
            if self.user_profiles:
                profile = await self.user_profiles.load_profile(user_id)
                profile["interaction_count"] += 1
                if not profile.get("username"):
                    profile["username"] = str(interaction.user.name)
                await self.user_profiles.save_profile(user_id)

                # AI-powered learning from conversation (runs in background)
                if Config.USER_PROFILES_AUTO_LEARN:
                    # Run in background to avoid blocking response
                    asyncio.create_task(
                        self._safe_learn_from_conversation(
                            user_id=user_id,
                            username=str(interaction.user.name),
                            user_message=message,
                            bot_response=response
                        )
                    )

                # Update affection score if enabled
                if Config.USER_AFFECTION_ENABLED:
                    # Run in background
                    asyncio.create_task(
                        self._safe_update_affection(
                            user_id=user_id,
                            message=message,
                            bot_response=response
                        )
                    )

            # Save to history with user attribution
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(
                    channel_id, "user", message,
                    username=str(interaction.user.name),
                    user_id=interaction.user.id
                )
                await self.history.add_message(channel_id, "assistant", response)

            # Start a conversation session
            self._start_session(channel_id, interaction.user.id)

            # Send response (handle long messages) - only if not streaming
            if not Config.RESPONSE_STREAMING_ENABLED:
                chunks = await chunk_message(response)
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(chunk)
                    else:
                        await interaction.channel.send(chunk)

            # Check if we should auto-summarize
            if self.summarizer and len(history) >= Config.AUTO_SUMMARIZE_THRESHOLD:
                # Summarize in background (don't block)
                participants = self.history.get_conversation_participants(history)
                asyncio.create_task(
                    self.summarizer.summarize_and_store(
                        messages=history,
                        channel_id=channel_id,
                        participants=[p["username"] for p in participants],
                        store_in_rag=Config.STORE_SUMMARIES_IN_RAG,
                    )
                )

            # Also speak in voice channel if bot is connected and feature is enabled
            if Config.AUTO_REPLY_WITH_VOICE:
                # Only generate TTS if actually in a voice channel
                voice_client = interaction.guild.voice_client
                if voice_client and voice_client.is_connected():
                    await self._speak_response_in_voice(interaction.guild, response)

        except Exception as e:
            logger.error(f"Chat command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="ask", description="Ask the AI a question (no history)")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str):
        """Ask a one-off question without using conversation history.

        Args:
            interaction: Discord interaction
            question: User's question
        """
        await interaction.response.defer(thinking=True)

        try:
            response = await self.ollama.generate(question, system_prompt=self.system_prompt)

            # Send response
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)

        except Exception as e:
            logger.error(f"Ask command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="search", description="Search the web for current information")
    @app_commands.describe(query="What to search for")
    async def search(self, interaction: discord.Interaction, query: str):
        """Search the web and get an AI response based on current information.

        Args:
            interaction: Discord interaction
            query: Search query
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.web_search:
                await interaction.followup.send("❌ Web search is not enabled on this bot.", ephemeral=True)
                return

            # Perform web search
            search_context = await self.web_search.get_context(query, max_length=1000)

            if not search_context:
                await interaction.followup.send(f"❌ No search results found for: **{query}**")
                return

            # Build prompt with search results
            prompt = f"[IMPORTANT - REAL-TIME WEB SEARCH RESULTS - USE THIS CURRENT INFORMATION TO ANSWER THE QUESTION]\n{search_context}\n[END WEB SEARCH RESULTS - Base your response on these actual current facts]\n\nUser question: {query}"

            # Get AI response
            response = await self.ollama.generate(prompt, system_prompt=self.system_prompt)

            # Send response
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(f"🔍 **Search results for:** {query}\n\n{chunk}")
                else:
                    await interaction.channel.send(chunk)

        except Exception as e:
            logger.error(f"Search command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="search_stats", description="View query optimization statistics")
    async def search_stats(self, interaction: discord.Interaction):
        """Show statistics about query optimization and search success rates.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.web_search or not self.web_search.optimizer:
                await interaction.response.send_message(
                    "❌ Query optimization is not enabled.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)

            # Get stats from optimizer
            stats = await self.web_search.optimizer.get_stats()

            # Create embed
            embed = discord.Embed(
                title="🧠 Query Optimization Stats",
                description="Statistics about web search query optimization and learning",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="📊 Overview",
                value=f"**Total Queries:** {stats['total_queries']}\n"
                      f"**Successful:** {stats['successful_queries']}\n"
                      f"**Success Rate:** {stats['success_rate']*100:.1f}%",
                inline=False
            )

            embed.add_field(
                name="🎯 Optimization Methods",
                value=f"**Pattern Matches:** {stats['pattern_matches']}\n"
                      f"**Learned Transformations:** {stats['learned_matches']}\n"
                      f"**Fallback Used:** {stats['fallback_used']}",
                inline=False
            )

            embed.set_footer(text="The bot learns from successful searches to improve future queries")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Search stats command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="export_chat", description="Export conversation history to a file")
    async def export_chat(self, interaction: discord.Interaction):
        """Export conversation history for this channel.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True)

        try:
            history = await self.history.load_history(interaction.channel_id)
            if not history:
                await interaction.followup.send("❌ No conversation history found for this channel.", ephemeral=True)
                return

            # Create export file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_export_{interaction.channel_id}_{timestamp}.json"
            filepath = Config.TEMP_DIR / filename
            
            async with aiofiles.open(filepath, "w") as f:
                await f.write(json.dumps(history, indent=2))

            # Send file
            await interaction.followup.send(
                f"✅ Here is the conversation export for <#{interaction.channel_id}>:",
                file=discord.File(filepath, filename=filename),
                ephemeral=True
            )
            
            # Cleanup
            # filepath.unlink() # Keep for a bit or let memory manager handle it

        except Exception as e:
            logger.error(f"Export chat failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="import_chat", description="Import conversation history from a file")
    @app_commands.describe(file="The JSON file to import")
    async def import_chat(self, interaction: discord.Interaction, file: discord.Attachment):
        """Import conversation history from a JSON file.

        Args:
            interaction: Discord interaction
            file: JSON file attachment
        """
        await interaction.response.defer(ephemeral=True)

        try:
            if not file.filename.endswith('.json'):
                await interaction.followup.send("❌ Please upload a JSON file.", ephemeral=True)
                return

            # Read file content
            content = await file.read()
            try:
                history = json.loads(content)
            except json.JSONDecodeError:
                await interaction.followup.send("❌ Invalid JSON file.", ephemeral=True)
                return

            if not isinstance(history, list):
                await interaction.followup.send("❌ Invalid format: Root must be a list of messages.", ephemeral=True)
                return

            # Validate structure (simple check)
            if history and not all(isinstance(m, dict) and "role" in m and "content" in m for m in history):
                await interaction.followup.send("❌ Invalid format: Messages must have 'role' and 'content' fields.", ephemeral=True)
                return

            # Save to history
            await self.history.save_history(interaction.channel_id, history)

            await interaction.followup.send(
                f"✅ Successfully imported {len(history)} messages to <#{interaction.channel_id}>.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Import chat failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="summarize_now", description="Force a summary of the current conversation")
    async def summarize_now(self, interaction: discord.Interaction):
        """Force a summary of the current conversation immediately.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.summarizer:
                await interaction.followup.send("❌ Summarization service is not enabled.", ephemeral=True)
                return

            history = await self.history.load_history(interaction.channel_id)
            if not history:
                await interaction.followup.send("❌ No history to summarize.", ephemeral=True)
                return

            # Trigger summarization
            summary_data = await self.summarizer.summarize_and_store(
                messages=history,
                channel_id=interaction.channel_id,
                participants=[interaction.user.name], # Simple single user assumption for now
                store_in_rag=True,
                store_in_file=True
            )

            if summary_data:
                await interaction.followup.send(
                    f"✅ Conversation summarized and stored in memory!\n\n**Summary:**\n{summary_data['summary']}"
                )
            else:
                await interaction.followup.send("❌ Failed to generate summary (possibly too short).")

        except Exception as e:
            logger.error(f"Summarize now failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="recall", description="Search past conversation summaries")
    @app_commands.describe(query="What to search for")
    async def recall(self, interaction: discord.Interaction, query: str):
        """Search past conversation summaries.

        Args:
            interaction: Discord interaction
            query: Search query
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.summarizer:
                await interaction.followup.send(
                    "❌ Conversation summarization is not enabled.",
                    ephemeral=True
                )
                return

            memories = await self.summarizer.retrieve_relevant_memories(query, max_results=3)

            if not memories:
                await interaction.followup.send(
                    f"❌ No relevant memories found for: **{query}**",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🧠 Memory Recall: {query}",
                color=discord.Color.gold()
            )

            for i, memory in enumerate(memories):
                # Extract summary part if possible to make it cleaner
                content = memory
                if "SUMMARY:" in memory:
                    parts = memory.split("SUMMARY:")
                    if len(parts) > 1:
                        content = parts[1].split("[Stored:")[0].strip()
                
                # Truncate if too long
                if len(content) > 1000:
                    content = content[:997] + "..."

                embed.add_field(
                    name=f"Memory {i+1}",
                    value=content,
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Recall command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="clear_history", description="Clear conversation history for this channel")
    async def clear_history(self, interaction: discord.Interaction):
        """Clear chat history for the current channel.

        Args:
            interaction: Discord interaction
        """
        try:
            channel_id = interaction.channel_id
            await self.history.clear_history(channel_id)
            await interaction.response.send_message(
                format_success("Conversation history cleared!"), ephemeral=True
            )
        except Exception as e:
            logger.error(f"Clear history failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="ambient", description="Toggle or check ambient mode status")
    @app_commands.describe(action="Action to perform")
    @app_commands.choices(action=[
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
    ])
    async def ambient(self, interaction: discord.Interaction, action: str = "status"):
        """Control ambient mode.

        Args:
            interaction: Discord interaction
            action: Action to perform (status/enable/disable)
        """
        try:
            ambient = getattr(self.bot, 'ambient_mode', None)

            if not ambient:
                await interaction.response.send_message(
                    "❌ Ambient mode is not configured.",
                    ephemeral=True
                )
                return

            if action == "status":
                stats = ambient.get_stats()
                embed = discord.Embed(
                    title="🌙 Ambient Mode Status",
                    color=discord.Color.purple()
                )
                embed.add_field(
                    name="Status",
                    value="🟢 Running" if stats["running"] else "🔴 Stopped",
                    inline=True
                )
                embed.add_field(
                    name="Active Channels",
                    value=str(stats["active_channels"]),
                    inline=True
                )
                embed.add_field(
                    name="Trigger Chance",
                    value=f"{int(stats['chance'] * 100)}%",
                    inline=True
                )
                embed.add_field(
                    name="Lull Timeout",
                    value=f"{stats['lull_timeout']}s",
                    inline=True
                )
                embed.add_field(
                    name="Min Interval",
                    value=f"{stats['min_interval']}s",
                    inline=True
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif action == "enable":
                if ambient.running:
                    await interaction.response.send_message(
                        "✅ Ambient mode is already running.",
                        ephemeral=True
                    )
                else:
                    await ambient.start()
                    await interaction.response.send_message(
                        "✅ Ambient mode enabled!",
                        ephemeral=True
                    )

            elif action == "disable":
                if not ambient.running:
                    await interaction.response.send_message(
                        "❌ Ambient mode is already stopped.",
                        ephemeral=True
                    )
                else:
                    await ambient.stop()
                    await interaction.response.send_message(
                        "✅ Ambient mode disabled.",
                        ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Ambient command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="end_session", description="End the current conversation session")
    async def end_session(self, interaction: discord.Interaction):
        """End the active conversation session in this channel.

        Args:
            interaction: Discord interaction
        """
        try:
            channel_id = interaction.channel_id
            if self._is_session_active(channel_id):
                self._end_session(channel_id)
                timeout_minutes = Config.CONVERSATION_TIMEOUT // 60
                await interaction.response.send_message(
                    format_success(f"Conversation session ended. Use @mention or `/chat` to start a new session."),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "No active conversation session in this channel.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"End session failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="set_model", description="Change the Ollama model")
    @app_commands.describe(model="Model name (e.g., llama3.2, mistral, etc.)")
    async def set_model(self, interaction: discord.Interaction, model: str):
        """Change the active Ollama model.

        Args:
            interaction: Discord interaction
            model: Name of the model to use
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if model is available
            models = await self.ollama.list_models()

            if model not in models:
                available = ", ".join(models) if models else "None found"
                await interaction.followup.send(
                    f"❌ Model '{model}' not found.\n\nAvailable models: {available}",
                    ephemeral=True,
                )
                return

            # Update model
            self.ollama.model = model
            await interaction.followup.send(
                format_success(f"Model changed to: **{model}**"), ephemeral=True
            )

        except Exception as e:
            logger.error(f"Set model failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="models", description="List available Ollama models")
    async def models(self, interaction: discord.Interaction):
        """List all available models.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            models = await self.ollama.list_models()

            if not models:
                await interaction.followup.send("❌ No models found on Ollama server.", ephemeral=True)
                return

            current = self.ollama.model
            model_list = "\n".join([f"{'🟢' if m == current else '⚪'} {m}" for m in models])

            embed = discord.Embed(
                title="Available Ollama Models",
                description=model_list,
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Current model: {current}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Models command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="set_persona", description="Change the bot's personality/character")
    @app_commands.describe(persona="Persona name (chief, arbiter, gothmommy, etc.)")
    async def set_persona(self, interaction: discord.Interaction, persona: str):
        """Change the bot's personality using persona configuration.

        Args:
            interaction: Discord interaction
            persona: Name of the persona
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Load persona config
            persona_config = self.persona_loader.get_persona(persona)

            if not persona_config:
                # List available personas
                available = self.persona_loader.list_personas()
                available_str = ", ".join(available) if available else "None found"

                await interaction.followup.send(
                    f"❌ Persona '{persona}' not found.\n\n**Available personas:** {available_str}\n\n"
                    f"Use `/list_personas` for more details.",
                    ephemeral=True,
                )
                return

            if not persona_config.prompt_text:
                await interaction.followup.send(
                    f"❌ Persona '{persona}' has no prompt text.",
                    ephemeral=True,
                )
                return

            # Update the system prompt
            self.system_prompt = persona_config.prompt_text
            self.current_persona = persona_config
            logger.info(f"Changed persona to: {persona_config.display_name}")

            # Switch voice based on config
            voice_cog = self.bot.get_cog("VoiceCog")
            voice_info = []
            if voice_cog and voice_cog.tts:
                # Apply voice settings based on TTS engine
                if Config.TTS_ENGINE == "kokoro":
                    voice_cog.tts.kokoro_voice = persona_config.voice.kokoro_voice
                    voice_cog.tts.kokoro_speed = persona_config.voice.kokoro_speed
                    voice_info.append(f"🎤 Voice: {persona_config.voice.kokoro_voice} (speed: {persona_config.voice.kokoro_speed}x)")
                else:  # Edge TTS
                    voice_cog.tts.default_voice = persona_config.voice.edge_voice
                    voice_cog.tts.rate = persona_config.voice.edge_rate
                    voice_cog.tts.volume = persona_config.voice.edge_volume
                    voice_info.append(f"🎤 Voice: {persona_config.voice.edge_voice}")

                logger.info(f"Applied voice settings for {persona}")

            # Apply RVC settings if enabled
            rvc_info = []
            if voice_cog and voice_cog.rvc and persona_config.rvc.enabled:
                if persona_config.rvc.model:
                    # Note: This sets the default model, actual usage depends on RVC being enabled
                    Config.DEFAULT_RVC_MODEL = persona_config.rvc.model
                    rvc_info.append(f"🔊 RVC Model: {persona_config.rvc.model}")
                    logger.info(f"Set RVC model to: {persona_config.rvc.model}")

            # Clear history if configured
            if persona_config.behavior.clear_history_on_switch:
                await self.history.clear_history(interaction.channel_id)

            # Build response message
            msg_parts = [f"✅ Persona changed to: **{persona_config.display_name}**"]
            if persona_config.description:
                msg_parts.append(f"_{persona_config.description}_")
            if voice_info:
                msg_parts.extend(voice_info)
            if rvc_info:
                msg_parts.extend(rvc_info)
            if persona_config.behavior.clear_history_on_switch:
                msg_parts.append("🗑️ Conversation history cleared")
            if persona_config.tags:
                msg_parts.append(f"🏷️ Tags: {', '.join(persona_config.tags)}")

            await interaction.followup.send(
                "\n".join(msg_parts),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Set persona failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="list_personas", description="List all available bot personalities")
    async def list_personas(self, interaction: discord.Interaction):
        """List all available persona/prompt files.

        Args:
            interaction: Discord interaction
        """
        try:
            prompts_dir = Path("prompts")
            if not prompts_dir.exists():
                await interaction.response.send_message(
                    "❌ Prompts directory not found.",
                    ephemeral=True,
                )
                return

            # Get all .txt files in prompts directory
            prompt_files = sorted(prompts_dir.glob("*.txt"))

            if not prompt_files:
                await interaction.response.send_message(
                    "❌ No persona files found in prompts/ directory.",
                    ephemeral=True,
                )
                return

            # Build embed with persona descriptions
            embed = discord.Embed(
                title="🎭 Available Bot Personas",
                description="Use `/set_persona <name>` to switch personalities",
                color=discord.Color.purple(),
            )

            # Parse each file for description (first 100 chars)
            for prompt_file in prompt_files:
                persona_name = prompt_file.stem
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        # Get first line or first 100 chars as preview
                        preview = content.split('\n')[0][:100]
                        if len(content.split('\n')[0]) > 100:
                            preview += "..."

                        embed.add_field(
                            name=persona_name,
                            value=preview or "No description",
                            inline=False,
                        )
                except Exception as e:
                    embed.add_field(
                        name=persona_name,
                        value=f"Error loading: {e}",
                        inline=False,
                    )

            # Show current persona
            current_prompt_file = Path(Config.SYSTEM_PROMPT_FILE).stem
            embed.set_footer(text=f"Current persona: {current_prompt_file}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List personas failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="add_persona", description="Create a new bot persona")
    @app_commands.describe(
        name="Persona name (lowercase, no spaces)",
        display_name="Display name for the persona",
        description="Short description of the persona",
        prompt="The personality/system prompt for the persona",
        kokoro_voice="Kokoro voice to use (e.g., am_adam, af_bella)",
    )
    async def add_persona(
        self,
        interaction: discord.Interaction,
        name: str,
        display_name: str,
        description: str,
        prompt: str,
        kokoro_voice: Optional[str] = "am_adam",
    ):
        """Create a new persona with configuration.

        Args:
            interaction: Discord interaction
            name: Persona identifier (lowercase, no spaces)
            display_name: Human-readable name
            description: Short description
            prompt: System prompt for the persona
            kokoro_voice: Kokoro voice to use
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Validate name (lowercase, alphanumeric + underscores only)
            if not re.match(r'^[a-z0-9_]+$', name):
                await interaction.followup.send(
                    "❌ Persona name must be lowercase alphanumeric with underscores only (e.g., 'my_persona')",
                    ephemeral=True,
                )
                return

            prompts_dir = Path("prompts")
            prompts_dir.mkdir(parents=True, exist_ok=True)

            # Check if persona already exists
            json_file = prompts_dir / f"{name}.json"
            txt_file = prompts_dir / f"{name}.txt"

            if json_file.exists() or txt_file.exists():
                await interaction.followup.send(
                    f"❌ Persona '{name}' already exists. Use `/edit_persona` to modify it.",
                    ephemeral=True,
                )
                return

            # Create persona JSON configuration
            persona_config = {
                "name": name,
                "display_name": display_name,
                "description": description,
                "prompt_file": f"{name}.txt",
                "voice": {
                    "kokoro_voice": kokoro_voice,
                    "kokoro_speed": 1.0,
                    "edge_voice": "en-US-AriaNeural",
                    "edge_rate": "+0%",
                    "edge_volume": "+0%"
                },
                "rvc": {
                    "enabled": False,
                    "model": None,
                    "pitch_shift": 0
                },
                "behavior": {
                    "clear_history_on_switch": True,
                    "auto_reply_enabled": True,
                    "affection_multiplier": 1.0
                },
                "tags": []
            }

            # Write JSON config
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(persona_config, f, indent=2)

            # Write prompt text file
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(prompt)

            # Reload persona loader to include new persona
            self.persona_loader = PersonaLoader()

            await interaction.followup.send(
                f"✅ Persona **{display_name}** created successfully!\n\n"
                f"**Name:** {name}\n"
                f"**Description:** {description}\n"
                f"**Voice:** {kokoro_voice}\n\n"
                f"Use `/set_persona {name}` to activate it.\n"
                f"Use `/edit_persona {name}` to modify settings.",
                ephemeral=True,
            )

            logger.info(f"Created new persona: {name} ({display_name})")

        except Exception as e:
            logger.error(f"Add persona failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="edit_persona", description="Edit an existing persona's settings")
    @app_commands.describe(
        name="Persona name to edit",
        display_name="New display name (optional)",
        description="New description (optional)",
        kokoro_voice="New Kokoro voice (optional)",
        kokoro_speed="Voice speed multiplier (optional, e.g., 1.0, 1.2)",
    )
    async def edit_persona(
        self,
        interaction: discord.Interaction,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        kokoro_voice: Optional[str] = None,
        kokoro_speed: Optional[float] = None,
    ):
        """Edit an existing persona's configuration.

        Args:
            interaction: Discord interaction
            name: Persona name to edit
            display_name: New display name
            description: New description
            kokoro_voice: New Kokoro voice
            kokoro_speed: New voice speed
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            prompts_dir = Path("prompts")
            json_file = prompts_dir / f"{name}.json"

            if not json_file.exists():
                await interaction.followup.send(
                    f"❌ Persona '{name}' not found. Use `/add_persona` to create it.",
                    ephemeral=True,
                )
                return

            # Load existing config
            with open(json_file, 'r', encoding='utf-8') as f:
                persona_config = json.load(f)

            # Track what was changed
            changes = []

            # Update fields if provided
            if display_name:
                persona_config["display_name"] = display_name
                changes.append(f"Display name → {display_name}")

            if description:
                persona_config["description"] = description
                changes.append(f"Description → {description}")

            if kokoro_voice:
                persona_config["voice"]["kokoro_voice"] = kokoro_voice
                changes.append(f"Kokoro voice → {kokoro_voice}")

            if kokoro_speed is not None:
                persona_config["voice"]["kokoro_speed"] = kokoro_speed
                changes.append(f"Voice speed → {kokoro_speed}x")

            if not changes:
                await interaction.followup.send(
                    "❌ No changes specified. Provide at least one parameter to update.",
                    ephemeral=True,
                )
                return

            # Save updated config
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(persona_config, f, indent=2)

            # Reload persona loader
            self.persona_loader = PersonaLoader()

            changes_text = "\n".join([f"• {c}" for c in changes])
            await interaction.followup.send(
                f"✅ Persona **{name}** updated successfully!\n\n"
                f"**Changes:**\n{changes_text}\n\n"
                f"Use `/set_persona {name}` to apply the changes.",
                ephemeral=True,
            )

            logger.info(f"Updated persona: {name} - {len(changes)} changes")

        except Exception as e:
            logger.error(f"Edit persona failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="my_profile", description="View your user profile and affection level")
    async def my_profile(self, interaction: discord.Interaction):
        """Show the user their profile information.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.user_profiles:
                await interaction.response.send_message(
                    "❌ User profiles are not enabled on this bot.",
                    ephemeral=True
                )
                return

            user_id = interaction.user.id
            profile = await self.user_profiles.load_profile(user_id)

            # Create embed
            embed = discord.Embed(
                title=f"📊 Profile: {interaction.user.name}",
                color=discord.Color.blue(),
            )

            # Basic stats
            embed.add_field(
                name="📈 Stats",
                value=f"**Messages:** {profile.get('interaction_count', 0)}\n"
                      f"**First Met:** {profile.get('first_met', 'Unknown')[:10]}",
                inline=False
            )

            # Traits
            if profile.get("traits"):
                traits_str = ", ".join(profile["traits"][:10])
                embed.add_field(
                    name="🎭 Personality Traits",
                    value=traits_str,
                    inline=False
                )

            # Interests
            if profile.get("interests"):
                interests_str = ", ".join(profile["interests"][:10])
                embed.add_field(
                    name="❤️ Interests",
                    value=interests_str,
                    inline=False
                )

            # Preferences
            if profile.get("preferences"):
                prefs_str = "\n".join([f"**{k}:** {v}" for k, v in list(profile["preferences"].items())[:5]])
                embed.add_field(
                    name="⚙️ Preferences",
                    value=prefs_str or "None yet",
                    inline=False
                )

            # Affection/Relationship
            if profile.get("affection") and Config.USER_AFFECTION_ENABLED:
                affection = profile["affection"]
                level = affection.get("level", 0)
                stage = affection.get("relationship_stage", "stranger")

                # Create affection bar
                bar_length = 10
                filled = int((level / 100) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)

                embed.add_field(
                    name="💖 Relationship",
                    value=f"**Stage:** {stage.replace('_', ' ').title()}\n"
                          f"**Affection:** {bar} {level}/100\n"
                          f"**Positive:** {affection.get('positive_interactions', 0)} | "
                          f"**Negative:** {affection.get('negative_interactions', 0)}",
                    inline=False
                )

            # Memorable quotes
            if profile.get("memorable_quotes"):
                last_quote = profile["memorable_quotes"][-1]
                embed.add_field(
                    name="💬 Last Memorable Quote",
                    value=f"\"{last_quote['quote']}\"",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"My profile failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="relationship", description="Check your relationship status with the bot")
    async def relationship(self, interaction: discord.Interaction):
        """Show detailed relationship/affection info.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.user_profiles or not Config.USER_AFFECTION_ENABLED:
                await interaction.response.send_message(
                    "❌ Affection system is not enabled on this bot.",
                    ephemeral=True
                )
                return

            user_id = interaction.user.id
            profile = await self.user_profiles.load_profile(user_id)
            affection = profile.get("affection", {})

            if not affection:
                await interaction.response.send_message(
                    "❌ No affection data found. Chat with the bot to build a relationship!",
                    ephemeral=True
                )
                return

            level = affection.get("level", 0)
            stage = affection.get("relationship_stage", "stranger")

            # Create embed
            embed = discord.Embed(
                title=f"💖 Relationship with {self.bot.user.name}",
                color=discord.Color.from_rgb(255, 105, 180),  # Pink
            )

            # Affection bar
            bar_length = 20
            filled = int((level / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)

            embed.add_field(
                name="Affection Level",
                value=f"{bar}\n**{level}/100** - {stage.replace('_', ' ').title()}",
                inline=False
            )

            # Interaction stats
            embed.add_field(
                name="Interaction History",
                value=f"**Total Conversations:** {profile.get('interaction_count', 0)}\n"
                      f"**Positive Interactions:** {affection.get('positive_interactions', 0)}\n"
                      f"**Negative Interactions:** {affection.get('negative_interactions', 0)}",
                inline=False
            )

            # Relationship description
            stage_descriptions = {
                "stranger": "We just met! Keep chatting to get to know each other better.",
                "acquaintance": "We're getting to know each other. I enjoy our conversations!",
                "friend": "We're friends! I look forward to talking with you.",
                "close_friend": "You're a close friend! I really enjoy our time together.",
                "best_friend": "You're my best friend! I genuinely care about you and love our conversations.",
            }

            description = stage_descriptions.get(stage, "Unknown relationship stage.")
            embed.add_field(
                name="How I Feel",
                value=description,
                inline=False
            )

            # Last interaction
            if affection.get("last_interaction"):
                last = affection["last_interaction"][:19]
                embed.set_footer(text=f"Last interaction: {last}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Relationship command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="status", description="Check AI status")
    async def status(self, interaction: discord.Interaction):
        """Check Ollama service status.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            healthy = await self.ollama.check_health()

            if healthy:
                embed = discord.Embed(
                    title="🟢 AI Status: Online",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Server", value=self.ollama.host)
                embed.add_field(name="Model", value=self.ollama.model)
                embed.add_field(name="Temperature", value=f"{self.ollama.temperature}")
            else:
                embed = discord.Embed(
                    title="🔴 AI Status: Offline",
                    description=f"Cannot connect to Ollama at {self.ollama.host}",
                    color=discord.Color.red(),
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Status command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages to enable auto-reply with text and TTS.

        Supports conversation sessions: once started with @mention or /chat,
        the bot will continue responding to all messages until timeout expires.

        Args:
            message: Discord message
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Track message for ambient mode (do this before other checks)
        if hasattr(self.bot, 'ambient_mode') and self.bot.ambient_mode:
            await self.bot.ambient_mode.on_message(message)

        # Process for naturalness (reactions, etc.)
        if hasattr(self.bot, 'naturalness') and self.bot.naturalness:
            await self.bot.naturalness.on_message(message)

        # Ignore messages with #ignore tag
        if "#ignore" in message.content.lower():
            return

        # Check if auto-reply is enabled for this channel
        if not Config.AUTO_REPLY_ENABLED:
            return

        if Config.AUTO_REPLY_CHANNELS and message.channel.id not in Config.AUTO_REPLY_CHANNELS:
            return

        # Check if there's an active session OR bot is mentioned
        is_session_active = self._is_session_active(message.channel.id)
        is_mentioned = self.bot.user in message.mentions

        # Only respond if mentioned OR session is active
        if not (is_mentioned or is_session_active):
            return

        # If mentioned, this will start/refresh the session
        # If session is active, this will refresh it

        try:
            # Load history
            history = []
            if Config.CHAT_HISTORY_ENABLED:
                history = await self.history.load_history(message.channel.id)

            # Add user message
            user_content = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            history.append({"role": "user", "content": user_content})

            # Build system prompt with context (TIME FIRST so it's most prominent)
            context_parts = [SystemContextProvider.get_compact_context()]

            # Add user profile context if enabled
            if self.user_profiles and Config.USER_CONTEXT_IN_CHAT:
                user_context = await self.user_profiles.get_user_context(message.author.id)
                if user_context and user_context != "New user - no profile information yet.":
                    context_parts.append(f"\n[User Info: {user_context}]")

                # Add affection/relationship context if enabled
                if Config.USER_AFFECTION_ENABLED:
                    affection_context = self.user_profiles.get_affection_context(message.author.id)
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
                            words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', msg.get('content', ''))
                            topics.extend(words)

                        if topics:
                            conv_context = ' '.join(set(topics))  # Unique topics
                            logger.info(f"Extracted conversation context: {conv_context}")

                    search_context = await self.web_search.get_context(
                        user_content,
                        max_length=800,
                        conversation_context=conv_context
                    )

                    if search_context:
                        context_parts.append(f"\n\n{'='*60}\n[REAL-TIME WEB SEARCH RESULTS - READ THIS EXACTLY]\n{'='*60}\n{search_context}\n{'='*60}\n[END OF WEB SEARCH RESULTS]\n{'='*60}\n\n[CRITICAL INSTRUCTIONS - VIOLATION WILL BE DETECTED]\n1. You MUST ONLY cite information that appears EXACTLY in the search results above\n2. COPY the exact URLs shown - DO NOT modify or create new ones\n3. If search results are irrelevant (e.g., wrong topic, unrelated content), tell the user: 'The search didn't return relevant results'\n4. DO NOT invent Steam pages, Reddit posts, YouTube videos, or patch notes\n5. If you cite a URL, it MUST be copied EXACTLY from the search results\n6. When in doubt, say 'I don't have current information' - DO NOT GUESS\n\nVIOLATING THESE RULES BY INVENTING INFORMATION WILL BE IMMEDIATELY DETECTED.")
                        logger.info(f"Added web search context for: {user_content[:50]}...")
                    else:
                        # Search returned no quality results
                        logger.info(f"No quality search results for: {user_content[:50]}")
                except Exception as e:
                    logger.error(f"Web search failed: {e}")

            # Add response style guidance
            context_parts.append("\n[Style: Match the conversation's energy. Keep responses natural and conversational - typically 1-2 sentences for simple questions/comments, longer only when genuinely needed for complex topics or storytelling.]")

            # Inject all context into system prompt (TIME at the VERY START)
            context_injected_prompt = f"{''.join(context_parts)}\n\n{self.system_prompt}"

            # Update dashboard status
            if hasattr(self.bot, 'web_dashboard'):
                self.bot.web_dashboard.set_status("Thinking", f"Generating response for {message.author.name}")

            # Check for image attachments
            images = []
            if Config.VISION_ENABLED and message.attachments:
                for attachment in message.attachments:
                    if is_image_attachment(attachment.filename):
                        try:
                            logger.info(f"Processing image attachment: {attachment.filename}")
                            image_data = await download_attachment(attachment.url)
                            image_b64 = image_to_base64(image_data)
                            images.append(image_b64)
                        except Exception as e:
                            logger.error(f"Failed to process image attachment: {e}")
                            await message.channel.send(f"⚠️ Failed to process image: {attachment.filename}")

            # Get response
            async with message.channel.typing():
                if images:
                    # Use vision model for images
                    logger.info(f"Using vision model with {len(images)} image(s)")
                    response = await self.ollama.chat_with_vision(
                        prompt=user_content,
                        images=images,
                        system_prompt=context_injected_prompt
                    )
                else:
                    # Regular text chat
                    response = await self.ollama.chat(history, system_prompt=context_injected_prompt)

            # Update dashboard status
            if hasattr(self.bot, 'web_dashboard'):
                self.bot.web_dashboard.set_status("Processing", "Response generated, updating profile...")

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
                            bot_response=response
                        )
                    except Exception as e:
                        logger.error(f"Profile learning failed: {e}")

                # Update affection score if enabled
                if Config.USER_AFFECTION_ENABLED:
                    try:
                        await self.user_profiles.update_affection(
                            user_id=message.author.id,
                            message=user_content,
                            bot_response=response
                        )
                    except Exception as e:
                        logger.error(f"Affection update failed: {e}")

            # Smart Summarization Trigger
            # Check if we should summarize based on message count or content
            if self.summarizer and Config.CONVERSATION_SUMMARIZATION_ENABLED:
                # 1. Message Count Trigger (existing)
                if len(history) >= Config.AUTO_SUMMARIZE_THRESHOLD:
                    # Trigger background summarization
                    asyncio.create_task(self.summarizer.summarize_and_store(
                        messages=history,
                        channel_id=message.channel.id,
                        participants=[message.author.name],
                        store_in_rag=Config.STORE_SUMMARIES_IN_RAG
                    ))
                    # Optionally clear history after summary to start fresh context
                    # await self.history.clear_history(message.channel.id)
                
                # 2. Topic Change / Conclusion Trigger (Smart)
                # If the bot says goodbye or wraps up, it's a good time to summarize
                elif any(phrase in response.lower() for phrase in ["talk to you later", "goodbye", "bye for now", "have a good night", "see you soon"]):
                     asyncio.create_task(self.summarizer.summarize_and_store(
                        messages=history,
                        channel_id=message.channel.id,
                        participants=[message.author.name],
                        store_in_rag=Config.STORE_SUMMARIES_IN_RAG
                    ))

            # Save to history
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(message.channel.id, "user", user_content)
                await self.history.add_message(message.channel.id, "assistant", response)

            # Start or refresh the conversation session
            if is_mentioned:
                # Mentioned - start new session
                self._start_session(message.channel.id, message.author.id)
            else:
                # Session active - just refresh
                self._refresh_session(message.channel.id)

            # Apply natural timing delay before responding
            if hasattr(self.bot, 'naturalness') and self.bot.naturalness:
                delay = await self.bot.naturalness.get_natural_delay()
                if delay > 0:
                    await asyncio.sleep(delay)

            # Send text response
            chunks = await chunk_message(response)
            for chunk in chunks:
                await message.channel.send(chunk)

            # Also speak in voice channel if bot is connected and feature is enabled
            if Config.AUTO_REPLY_WITH_VOICE:
                # Only generate TTS if actually in a voice channel
                voice_client = message.guild.voice_client
                if voice_client and voice_client.is_connected():
                    if hasattr(self.bot, 'web_dashboard'):
                        self.bot.web_dashboard.set_status("Speaking", "Generating TTS audio...")
                    await self._speak_response_in_voice(message.guild, response)
                
            # Reset status to Idle after a short delay
            if hasattr(self.bot, 'web_dashboard'):
                # We don't await this, just let it happen
                asyncio.create_task(self._reset_status_delayed())

        except Exception as e:
            logger.error(f"Auto-reply failed: {e}")
            await message.channel.send(format_error(e))

    async def _speak_response_in_voice(self, guild: discord.Guild, text: str):
        """Speak the response in voice channel if bot is connected.

        Args:
            guild: Discord guild
            text: Text to speak
        """
        try:
            # Get voice cog to access TTS
            voice_cog = self.bot.get_cog("VoiceCog")
            if not voice_cog:
                return

            # Check if bot is in a voice channel in this guild
            voice_client = guild.voice_client
            if not voice_client or not voice_client.is_connected():
                return

            # Don't interrupt if already playing
            if voice_client.is_playing():
                logger.info("Voice client already playing, skipping TTS")
                return

            # Analyze sentiment for voice modulation
            sentiment = self._analyze_sentiment(text)
            kokoro_speed = 1.0
            edge_rate = "+0%"
            
            if sentiment == "positive":
                kokoro_speed = 1.1
                edge_rate = "+10%"
            elif sentiment == "negative":
                kokoro_speed = 0.9
                edge_rate = "-10%"

            # Generate TTS
            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.mp3"
            await voice_cog.tts.generate(
                text, 
                audio_file,
                speed=kokoro_speed,
                rate=edge_rate
            )

            # Apply RVC if enabled
            if voice_cog.rvc and voice_cog.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.mp3"
                await voice_cog.rvc.convert(
                    audio_file, rvc_file,
                    model_name=Config.DEFAULT_RVC_MODEL,
                    pitch_shift=Config.RVC_PITCH_SHIFT,
                    index_rate=Config.RVC_INDEX_RATE,
                    protect=Config.RVC_PROTECT
                )
                audio_file = rvc_file

            # Play audio
            import asyncio
            audio_source = discord.FFmpegPCMAudio(str(audio_file))
            voice_client.play(
                audio_source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._cleanup_audio(audio_file, e), self.bot.loop
                ),
            )
            logger.info(f"Speaking AI response in voice channel: {voice_client.channel.name}")

        except Exception as e:
            logger.error(f"Failed to speak response in voice: {e}")

    async def _cleanup_audio(self, audio_file: Path, error):
        """Clean up audio file after playback.

        Args:
            audio_file: Path to audio file
            error: Playback error if any
        """
        if error:
            logger.error(f"Audio playback error: {error}")

        try:
            if audio_file.exists():
                audio_file.unlink()
                logger.debug(f"Cleaned up audio file: {audio_file}")
        except Exception as e:
            logger.error(f"Failed to cleanup audio file: {e}")

    async def _reset_status_delayed(self, delay: float = 5.0):
        """Reset dashboard status to Idle after a delay."""
        await asyncio.sleep(delay)
        if hasattr(self.bot, 'web_dashboard'):
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

        if hasattr(self.bot, 'naturalness') and self.bot.naturalness:
            response = await self.bot.naturalness.on_reaction_add(reaction, user)
            if response:
                await reaction.message.channel.send(response)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Handle presence updates for activity awareness.

        Args:
            before: Member state before
            after: Member state after
        """
        if hasattr(self.bot, 'naturalness') and self.bot.naturalness:
            comment = await self.bot.naturalness.on_presence_update(before, after)
            if comment:
                # Send to first configured ambient channel
                if Config.AMBIENT_CHANNELS:
                    channel = self.bot.get_channel(Config.AMBIENT_CHANNELS[0])
                    if channel and channel.permissions_for(after.guild.me).send_messages:
                        await channel.send(comment)


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
