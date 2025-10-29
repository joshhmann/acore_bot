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

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        logger.info("Setting up bot...")

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
