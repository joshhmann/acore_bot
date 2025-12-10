#!/usr/bin/env python3
"""Discord bot with Ollama chat and TTS/RVC voice features.

A simple, clean Discord bot that:
- Uses Ollama for AI-powered conversations
- Generates speech with TTS (Kokoro or Supertonic)
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
from services.core.factory import ServiceFactory
from cogs.chat import ChatCog
from cogs.voice import VoiceCog
from cogs.music import MusicCog
from cogs.reminders import RemindersCog
from cogs.notes import NotesCog

# Setup logging
# Configure logging with rotating file handler
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
log_path = Path(Config.LOG_FILE_PATH)
log_path.parent.mkdir(parents=True, exist_ok=True)

# Set up handlers
handlers = [logging.StreamHandler(sys.stdout)]
if Config.LOG_TO_FILE:
    file_handler = RotatingFileHandler(
        Config.LOG_FILE_PATH,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    handlers.append(file_handler)

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)

# Suppress noisy logs from third-party libraries (unless in DEBUG mode)
if Config.LOG_LEVEL != "DEBUG":
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("nemo_logger").setLevel(logging.WARNING)
    logging.getLogger("nemo").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Log the logging configuration
logger.info(f"Logging configured: Level={Config.LOG_LEVEL}, File={Config.LOG_TO_FILE}, Path={Config.LOG_FILE_PATH}")


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

        # Track background tasks for clean shutdown
        self.background_tasks = set()

        # Initialize services via Factory
        factory = ServiceFactory(self)
        self.services = factory.create_services()

        # Expose key services as attributes for Cogs
        self.ollama = self.services.get('ollama')
        self.tts = self.services.get('tts')
        self.rvc = self.services.get('rvc')
        self.metrics = self.services.get('metrics')

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        logger.info("Setting up bot...")

        # Initialize Web Search if enabled
        if self.services.get('web_search'):
            await self.services['web_search'].initialize()
            logger.info("Web search initialized")

        # Initialize RAG if enabled
        if self.services.get('rag'):
            await self.services['rag'].initialize()
            logger.info("RAG service initialized")

        # Initialize LLM Service
        if self.ollama:
            await self.ollama.initialize()
            if not await self.ollama.check_health():
                logger.warning("LLM Provider check failed - check config/internet.")
            else:
                logger.info(f"Connected to LLM Provider")

        # Load ChatCog (Dependencies injected)
        await self.add_cog(
            ChatCog(
                self,
                ollama=self.ollama,
                history_manager=self.services['history'],
                user_profiles=self.services.get('profiles'),
                summarizer=self.services.get('summarizer'),
                web_search=self.services.get('web_search'),
                rag=self.services.get('rag'),
                conversation_manager=self.services.get('conversation_manager'),
                persona_system=self.services.get('persona_system'),
                compiled_persona=self.services.get('compiled_persona'),
                llm_fallback=self.services.get('llm_fallback'),
                persona_relationships=self.services.get('persona_relationships'),
            )
        )
        logger.info("Loaded ChatCog")

        # Load VoiceCog
        await self.add_cog(
            VoiceCog(
                self,
                tts=self.tts,
                rvc=self.rvc,
                voice_activity_detector=self.services.get('voice_activity_detector'),
                enhanced_voice_listener=self.services.get('enhanced_voice_listener'),
            )
        )
        logger.info("Loaded VoiceCog")

        # Load MusicCog
        await self.add_cog(MusicCog(self))
        logger.info("Loaded MusicCog")

        # Load Feature Cogs
        if self.services.get('reminders'):
            await self.add_cog(RemindersCog(self, self.services['reminders']))

        if self.services.get('notes'):
            await self.add_cog(NotesCog(self, self.services['notes']))

        # Load Modular Extensions
        extensions = [
            "cogs.memory_commands",
            "cogs.character_commands",
            "cogs.profile_commands",
            "cogs.search_commands",
            "cogs.help",
            "cogs.system",
        ]

        for ext in extensions:
            await self.load_extension(ext)

        # Load Event Listeners
        from cogs.event_listeners import EventListenersCog
        await self.add_cog(EventListenersCog(self))

        # Sync commands
        await self.tree.sync()
        logger.info("Synced command tree")

        # Start Background Tasks
        self._start_background_services()

    def _start_background_services(self):
        """Start background maintenance tasks."""
        # Memory Cleanup
        if self.services.get('memory_manager'):
            task = asyncio.create_task(
                self.services['memory_manager'].start_background_cleanup(
                    interval_hours=Config.MEMORY_CLEANUP_INTERVAL_HOURS
                )
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # Profile Saver
        if self.services.get('profiles'):
            # Note: start_background_saver is async but usually creates its own task loop or returns a coroutine
            # Assuming it needs to be awaited if it's async
            asyncio.create_task(self.services['profiles'].start_background_saver())

        # Reminders
        if self.services.get('reminders'):
            asyncio.create_task(self.services['reminders'].start())

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

        # Start metrics auto-save (configurable interval)
        if Config.METRICS_ENABLED:
            try:
                # In DEBUG mode, save more frequently (every 10 minutes) for easier analysis
                if Config.LOG_LEVEL == "DEBUG":
                    interval_minutes = 10
                    logger.info("DEBUG mode detected: Metrics will save every 10 minutes for detailed analysis")
                else:
                    interval_minutes = Config.METRICS_SAVE_INTERVAL_MINUTES

                interval_hours = interval_minutes / 60.0
                metrics_task = self.metrics.start_auto_save(interval_hours=interval_hours)
                self.background_tasks.add(metrics_task)
                logger.info(f"Metrics auto-save started (every {interval_minutes} minutes)")

                # Start hourly reset to prevent memory leak from unbounded active user/channel sets
                reset_task = self.metrics.start_hourly_reset()
                self.background_tasks.add(reset_task)
                logger.info("Metrics hourly reset started (prevents memory leak)")
            except Exception as e:
                logger.error(f"Failed to start metrics auto-save: {e}")
        else:
            logger.info("Metrics auto-save disabled via config")

        logger.info("Bot is ready!")

    async def on_message(self, message):
        """Handle messages via ChatCog."""
        await self.process_commands(message)

        # Hand off to ChatCog logic which includes BehaviorEngine
        chat_cog = self.get_cog("ChatCog")
        if chat_cog:
            await chat_cog.check_and_handle_message(message)



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

        # Cancel all background tasks
        if self.background_tasks:
            logger.info(f"Cancelling {len(self.background_tasks)} background tasks...")
            for task in self.background_tasks:
                task.cancel()

            # Wait for all tasks to complete cancellation
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            logger.info("All background tasks cancelled")

        # Cleanup cog background tasks
        chat_cog = self.get_cog("ChatCog")
        if chat_cog and hasattr(chat_cog, 'cleanup_tasks'):
            await chat_cog.cleanup_tasks()

        # Cleanup services
        if self.services.get('profiles'):
            await self.services['profiles'].stop_background_saver()

        if self.services.get('reminders'):
            await self.services['reminders'].stop()

        if self.ollama:
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
