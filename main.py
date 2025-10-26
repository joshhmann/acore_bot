#!/usr/bin/env python3
"""Discord bot with Ollama chat and TTS/RVC voice features.

A simple, clean Discord bot that:
- Uses Ollama for AI-powered conversations
- Generates speech with TTS (Edge TTS)
- Applies voice conversion with RVC
- Plays audio in Discord voice channels
"""
import discord
from discord.ext import commands
import logging
import sys
from pathlib import Path

from config import Config
from services.ollama import OllamaService
from services.tts import TTSService
from services.rvc import RVCService
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
        )

        self.tts = TTSService(
            default_voice=Config.DEFAULT_TTS_VOICE,
            rate=Config.TTS_RATE,
            volume=Config.TTS_VOLUME,
        )

        self.rvc = None
        if Config.RVC_ENABLED:
            self.rvc = RVCService(
                model_path=Config.RVC_MODEL_PATH,
                default_model=Config.DEFAULT_RVC_MODEL,
            )

        self.history_manager = ChatHistoryManager(
            history_dir=Config.CHAT_HISTORY_DIR,
            max_messages=Config.CHAT_HISTORY_MAX_MESSAGES,
        )

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
        await self.add_cog(ChatCog(self, self.ollama, self.history_manager))
        logger.info("Loaded ChatCog")

        await self.add_cog(VoiceCog(self, self.tts, self.rvc))
        logger.info("Loaded VoiceCog")

        # Sync commands (for slash commands)
        await self.tree.sync()
        logger.info("Synced command tree")

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
