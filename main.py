#!/usr/bin/env python3
"""Discord bot with Ollama chat and TTS/RVC voice features.

A simple, clean Discord bot that:
- Uses Ollama for AI-powered conversations
- Generates speech with TTS (Edge TTS or Kokoro)
- Applies voice conversion with RVC
- Plays audio in Discord voice channels
- Manages memory and storage automatically
- Summarizes conversations for long-term memory
- Supports voice activity detection (Whisper STT)
- Streams responses in real-time
"""
import discord
from discord.ext import commands
import logging
import sys
import asyncio
from pathlib import Path

from config import Config
from services.ollama import OllamaService
from services.tts import TTSService
from services.rvc_unified import UnifiedRVCService
from services.user_profiles import UserProfileService
from services.memory_manager import MemoryManager
from services.conversation_summarizer import ConversationSummarizer
from services.rag import RAGService
from services.whisper_stt import WhisperSTTService, VoiceActivityDetector
from services.enhanced_voice_listener import EnhancedVoiceListener
from utils.helpers import ChatHistoryManager
from cogs.chat import ChatCog
from cogs.voice import VoiceCog
from cogs.music import MusicCog
from services.web_dashboard import WebDashboard
from services.ambient_mode import AmbientMode
from services.naturalness import NaturalnessService
from services.reminders import RemindersService
from cogs.reminders import RemindersCog
from services.web_search import WebSearchService
from services.trivia import TriviaService
from cogs.trivia import TriviaCog

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log"),
    ],
)
logger = logging.getLogger(__name__)


class OllamaBot(commands.Bot):
    """Main bot class."""

    def __init__(self):
        """Initialize the bot."""
        intents = discord.Intents.default()
        intents.message_content = True  # Required for message events
        intents.voice_states = True  # Required for voice features
        intents.presences = True  # Required for activity awareness
        intents.members = True  # Required for member tracking

        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,  # We'll create our own
        )

        # Initialize services
        self.ollama = OllamaService(
            host=Config.OLLAMA_HOST,
            model=Config.OLLAMA_MODEL,
            temperature=Config.OLLAMA_TEMPERATURE,
            max_tokens=Config.OLLAMA_MAX_TOKENS,
            min_p=Config.OLLAMA_MIN_P,
            top_k=Config.OLLAMA_TOP_K,
            repeat_penalty=Config.OLLAMA_REPEAT_PENALTY,
        )

        self.tts = TTSService(
            engine=Config.TTS_ENGINE,
            default_voice=Config.DEFAULT_TTS_VOICE,
            rate=Config.TTS_RATE,
            volume=Config.TTS_VOLUME,
            kokoro_voice=Config.KOKORO_VOICE,
            kokoro_speed=Config.KOKORO_SPEED,
        )

        self.rvc = None
        if Config.RVC_ENABLED:
            self.rvc = UnifiedRVCService(
                mode=Config.RVC_MODE,
                model_path=Config.RVC_MODEL_PATH,
                default_model=Config.DEFAULT_RVC_MODEL,
                device=Config.RVC_DEVICE,
                webui_url=Config.RVC_WEBUI_URL,
            )

        self.history_manager = ChatHistoryManager(
            history_dir=Config.CHAT_HISTORY_DIR,
            max_messages=Config.CHAT_HISTORY_MAX_MESSAGES,
        )

        # Initialize user profiles if enabled
        self.user_profiles = None
        if Config.USER_PROFILES_ENABLED:
            self.user_profiles = UserProfileService(
                profiles_dir=Config.USER_PROFILES_PATH,
                ollama_service=self.ollama  # Pass ollama for AI-powered learning
            )
            logger.info("User profiles enabled")

        # Initialize RAG service if enabled
        self.rag = None
        if Config.RAG_ENABLED:
            self.rag = RAGService(
                documents_path=Config.RAG_DOCUMENTS_PATH,
                vector_store_path=Config.RAG_VECTOR_STORE,
                top_k=Config.RAG_TOP_K,
            )
            logger.info("RAG service initialized")

        # Initialize memory manager
        self.memory_manager = None
        if Config.MEMORY_CLEANUP_ENABLED:
            self.memory_manager = MemoryManager(
                temp_dir=Config.TEMP_DIR,
                chat_history_dir=Config.CHAT_HISTORY_DIR,
                max_temp_file_age_hours=Config.MAX_TEMP_FILE_AGE_HOURS,
                max_history_age_days=Config.MAX_HISTORY_AGE_DAYS,
            )
            logger.info("Memory manager initialized")

        # Initialize conversation summarizer if enabled
        self.summarizer = None
        if Config.CONVERSATION_SUMMARIZATION_ENABLED and self.rag:
            self.summarizer = ConversationSummarizer(
                ollama=self.ollama,
                rag=self.rag,
                summary_dir=Config.SUMMARY_DIR,
            )
            logger.info("Conversation summarizer initialized")

        # Initialize Whisper STT if enabled
        self.whisper = None
        self.voice_activity_detector = None
        self.enhanced_voice_listener = None
        if Config.WHISPER_ENABLED:
            self.whisper = WhisperSTTService(
                model_size=Config.WHISPER_MODEL_SIZE,
                device=Config.WHISPER_DEVICE,
                language=Config.WHISPER_LANGUAGE,
            )
            if self.whisper.is_available():
                # Legacy voice activity detector (for backwards compatibility)
                self.voice_activity_detector = VoiceActivityDetector(
                    whisper_stt=self.whisper,
                    temp_dir=Config.TEMP_DIR,
                    silence_threshold=Config.WHISPER_SILENCE_THRESHOLD,
                    max_recording_duration=Config.MAX_RECORDING_DURATION,
                )

                # Enhanced voice listener with smart detection
                trigger_words = [w.strip() for w in Config.VOICE_BOT_TRIGGER_WORDS.split(",")]
                self.enhanced_voice_listener = EnhancedVoiceListener(
                    whisper_stt=self.whisper,
                    silence_threshold=Config.WHISPER_SILENCE_THRESHOLD,
                    energy_threshold=Config.VOICE_ENERGY_THRESHOLD,
                    bot_trigger_words=trigger_words,
                )

                logger.info(f"Whisper STT initialized with enhanced voice listener (model: {Config.WHISPER_MODEL_SIZE})")
            else:
                logger.warning("Whisper STT not available - install with: pip install faster-whisper")

        # Initialize Web Dashboard
        self.web_dashboard = WebDashboard(self)

        # Initialize Ambient Mode
        self.ambient_mode = None
        if Config.AMBIENT_MODE_ENABLED:
            self.ambient_mode = AmbientMode(self, self.ollama)
            logger.info("Ambient mode initialized")

        # Initialize Naturalness Service
        self.naturalness = None
        if Config.NATURALNESS_ENABLED:
            self.naturalness = NaturalnessService(self)
            logger.info("Naturalness service initialized (reactions, activity awareness, natural timing)")

        # Initialize Reminders Service
        self.reminders_service = None
        if Config.REMINDERS_ENABLED:
            self.reminders_service = RemindersService(self)
            logger.info("Reminders service initialized")

        # Initialize Web Search Service
        self.web_search = None
        if Config.WEB_SEARCH_ENABLED:
            self.web_search = WebSearchService(
                engine=Config.WEB_SEARCH_ENGINE,
                max_results=Config.WEB_SEARCH_MAX_RESULTS,
            )
            logger.info(f"Web search service created (engine: {Config.WEB_SEARCH_ENGINE})")

        # Initialize Trivia Service
        self.trivia_service = None
        if Config.TRIVIA_ENABLED:
            self.trivia_service = TriviaService(
                data_dir=Config.DATA_DIR,
                web_search=self.web_search,
            )
            logger.info("Trivia service initialized")

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        logger.info("Setting up bot...")

        # Initialize Web Search if enabled
        if self.web_search:
            await self.web_search.initialize()
            logger.info("Web search initialized")

        # Initialize Trivia if enabled
        if self.trivia_service:
            await self.trivia_service.initialize()
            logger.info("Trivia service initialized")

        # Initialize Ollama
        await self.ollama.initialize()
        healthy = await self.ollama.check_health()

        if not healthy:
            logger.warning(
                f"Could not connect to Ollama at {Config.OLLAMA_HOST}. "
                "Make sure Ollama is running!"
            )
        else:
            logger.info(f"Connected to Ollama - Model: {Config.OLLAMA_MODEL}")

        # Load cogs
        await self.add_cog(
            ChatCog(
                self,
                self.ollama,
                self.history_manager,
                self.user_profiles,
                self.summarizer,
                self.web_search,
                self.naturalness,
            )
        )
        logger.info("Loaded ChatCog")

        await self.add_cog(
            VoiceCog(
                self,
                self.tts,
                self.rvc,
                self.voice_activity_detector,
                self.enhanced_voice_listener,
            )
        )
        logger.info("Loaded VoiceCog")

        await self.add_cog(MusicCog(self))
        logger.info("Loaded MusicCog")

        # Load RemindersCog
        if self.reminders_service:
            await self.add_cog(RemindersCog(self, self.reminders_service))
            logger.info("Loaded RemindersCog")

        # Load TriviaCog
        if self.trivia_service:
            await self.add_cog(TriviaCog(self, self.trivia_service))
            logger.info("Loaded TriviaCog")

        # Sync commands (for slash commands)
        await self.tree.sync()
        logger.info("Synced command tree")

        # Start background tasks
        if self.memory_manager:
            asyncio.create_task(
                self.memory_manager.start_background_cleanup(
                    interval_hours=Config.MEMORY_CLEANUP_INTERVAL_HOURS
                )
            )

            logger.info("Started background memory cleanup task")

        # Start background profile saver
        if self.user_profiles:
            await self.user_profiles.start_background_saver()

        # Start Web Dashboard
        await self.web_dashboard.start(port=8080)

        # Start Ambient Mode
        if self.ambient_mode:
            await self.ambient_mode.start()

        # Start Reminders background task
        if self.reminders_service:
            await self.reminders_service.start()

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/chat | /speak",
            )
        )

        logger.info("Bot is ready!")

    async def on_message(self, message):
        """Handle messages for proactive engagement."""
        # Process commands first
        await self.process_commands(message)

        # Don't respond to self
        if message.author == self.user:
            return

        # Don't respond to other bots
        if message.author.bot:
            return

        # Check for proactive engagement
        if self.ambient_mode and Config.PROACTIVE_ENGAGEMENT_ENABLED:
            # Get current mood if available
            current_mood = None
            if self.naturalness and self.naturalness.mood:
                current_mood = self.naturalness.mood.current_mood.mood.value

            # Check if bot should jump in
            engagement = await self.ambient_mode.on_message(message, mood=current_mood)

            if engagement:
                # Bot wants to jump in!
                try:
                    await message.channel.send(engagement)
                    logger.info(f"Proactively engaged in {message.channel.name}")

                    # Update dashboard if available
                    if self.web_dashboard:
                        self.web_dashboard.set_status("Proactive", f"Engaged: {engagement[:30]}...")
                except Exception as e:
                    logger.error(f"Failed to send proactive engagement: {e}")

    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates for environmental awareness."""
        if not self.naturalness:
            return

        # Get environmental comment
        comment = await self.naturalness.on_voice_state_update(member, before, after)

        if comment:
            # Find a text channel to send the comment
            # Try to find the channel the bot is configured for, or the guild's system channel
            guild = member.guild
            target_channel = None

            # Try to find a configured ambient channel
            if Config.AMBIENT_CHANNELS:
                for channel_id in Config.AMBIENT_CHANNELS:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        target_channel = channel
                        break

            # Fallback to system channel
            if not target_channel:
                target_channel = guild.system_channel

            # Send comment
            if target_channel:
                try:
                    await target_channel.send(comment)
                    logger.debug(f"Environmental comment: {comment}")
                except Exception as e:
                    logger.error(f"Failed to send environmental comment: {e}")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands

        logger.error(f"Command error: {error}")

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {error}")
        else:
            await ctx.send(f"❌ An error occurred: {error}")

    async def close(self):
        """Cleanup when bot is shutting down."""
        logger.info("Shutting down bot...")

        # Cleanup services
        if self.user_profiles:
            await self.user_profiles.stop_background_saver()

        if self.ambient_mode:
            await self.ambient_mode.stop()

        if self.web_dashboard:
            await self.web_dashboard.stop()

        await self.ollama.close()

        await super().close()


def main():
    """Main entry point."""
    logger.info("Starting Discord Ollama Bot...")

    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file!")
        sys.exit(1)

    # Create and run bot
    bot = OllamaBot()

    try:
        bot.run(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token! Please check DISCORD_TOKEN in .env")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
