"""Chat cog for Ollama-powered conversations."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, Dict
from pathlib import Path
import uuid
import time

from config import Config
from services.ollama import OllamaService
from utils.helpers import ChatHistoryManager, chunk_message, format_error, format_success
from utils.persona_loader import PersonaLoader
from utils.system_context import SystemContextProvider

logger = logging.getLogger(__name__)


class ChatCog(commands.Cog):
    """Cog for chat commands using Ollama."""

    def __init__(self, bot: commands.Bot, ollama: OllamaService, history_manager: ChatHistoryManager, user_profiles=None):
        """Initialize chat cog.

        Args:
            bot: Discord bot instance
            ollama: Ollama service instance
            history_manager: Chat history manager
            user_profiles: User profile service (optional)
        """
        self.bot = bot
        self.ollama = ollama
        self.history = history_manager
        self.user_profiles = user_profiles

        # Load persona configurations
        self.persona_loader = PersonaLoader()

        # Load system prompt from file or env
        self.system_prompt = self._load_system_prompt()

        # Track current persona config
        self.current_persona = None

        # Track active conversation sessions per channel
        # Format: {channel_id: {"user_id": user_id, "last_activity": timestamp}}
        self.active_sessions: Dict[int, Dict] = {}

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

            # Build system prompt with context
            context_parts = [SystemContextProvider.get_compact_context()]

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

            # Add response style guidance
            context_parts.append("\n[Style: Match the conversation's energy. Keep responses natural and conversational - typically 1-2 sentences for simple questions/comments, longer only when genuinely needed for complex topics or storytelling.]")

            # Inject all context into system prompt
            context_injected_prompt = f"{''.join(context_parts)}\n\n{self.system_prompt}"

            # Get AI response
            response = await self.ollama.chat(history, system_prompt=context_injected_prompt)

            # Update user profile - increment interaction count and learn from conversation
            if self.user_profiles:
                profile = await self.user_profiles.load_profile(user_id)
                profile["interaction_count"] += 1
                if not profile.get("username"):
                    profile["username"] = str(interaction.user.name)
                await self.user_profiles.save_profile(user_id)

                # AI-powered learning from conversation (runs in background)
                if Config.USER_PROFILES_AUTO_LEARN:
                    try:
                        await self.user_profiles.learn_from_conversation(
                            user_id=user_id,
                            username=str(interaction.user.name),
                            user_message=message,
                            bot_response=response
                        )
                    except Exception as e:
                        logger.error(f"Profile learning failed: {e}")

                # Update affection score if enabled
                if Config.USER_AFFECTION_ENABLED:
                    try:
                        await self.user_profiles.update_affection(
                            user_id=user_id,
                            message=message,
                            bot_response=response
                        )
                    except Exception as e:
                        logger.error(f"Affection update failed: {e}")

            # Save to history
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(channel_id, "user", message)
                await self.history.add_message(channel_id, "assistant", response)

            # Start a conversation session
            self._start_session(channel_id, interaction.user.id)

            # Send response (handle long messages)
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)

            # Also speak in voice channel if bot is connected and feature is enabled
            if Config.AUTO_REPLY_WITH_VOICE:
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

            # Build system prompt with context
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

            # Add response style guidance
            context_parts.append("\n[Style: Match the conversation's energy. Keep responses natural and conversational - typically 1-2 sentences for simple questions/comments, longer only when genuinely needed for complex topics or storytelling.]")

            # Inject all context into system prompt
            context_injected_prompt = f"{''.join(context_parts)}\n\n{self.system_prompt}"

            # Get response
            async with message.channel.typing():
                response = await self.ollama.chat(history, system_prompt=context_injected_prompt)

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

            # Send text response
            chunks = await chunk_message(response)
            for chunk in chunks:
                await message.channel.send(chunk)

            # Also speak in voice channel if bot is connected and feature is enabled
            if Config.AUTO_REPLY_WITH_VOICE:
                await self._speak_response_in_voice(message.guild, response)

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

            # Generate TTS
            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.mp3"
            await voice_cog.tts.generate(text, audio_file)

            # Apply RVC if enabled
            if voice_cog.rvc and voice_cog.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.mp3"
                await voice_cog.rvc.convert(audio_file, rvc_file, model_name=Config.DEFAULT_RVC_MODEL)
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


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
