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
import signal
import os
from pathlib import Path
from typing import cast, Optional, Dict, Any, Set
from datetime import datetime

from config import Config
from services.core.factory import ServiceFactory
from services.interfaces.llm_interface import LLMInterface
from cogs.chat import ChatCog
from cogs.voice import VoiceCog
from cogs.music import MusicCog
from cogs.reminders import RemindersCog
from cogs.notes import NotesCog

# Setup logging with structured JSON support
from utils.logging_config import (
    setup_logging,
    log_with_context,
    TraceContext,
    get_trace_id,
    set_trace_id,
)

# Setup production logging configuration
setup_logging(
    log_level=Config.LOG_LEVEL,
    log_to_file=Config.LOG_TO_FILE,
    log_file_path=Config.LOG_FILE_PATH,
    log_format=os.getenv("LOG_FORMAT", "text"),  # json or text
    max_bytes=Config.LOG_MAX_BYTES,
    backup_count=Config.LOG_BACKUP_COUNT,
    compress_old_logs=True,
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
logger.info(
    f"Logging configured: Level={Config.LOG_LEVEL}, File={Config.LOG_TO_FILE}, Path={Config.LOG_FILE_PATH}"
)


class OllamaBot(commands.Bot):
    """Main bot class."""

    def __init__(self) -> None:
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

        # Track bot start time for uptime metrics
        self.start_time: datetime = datetime.now()

        # Track background tasks for clean shutdown
        self.background_tasks: Set[asyncio.Task] = set()

        # Initialize services via Factory
        factory: ServiceFactory = ServiceFactory(self)
        self.services: Dict[str, Any] = factory.create_services()

        # Expose key services as attributes for Cogs
        self.ollama: Optional[Any] = self.services.get("ollama")
        self.tts: Optional[Any] = self.services.get("tts")
        self.rvc: Optional[Any] = self.services.get("rvc")
        self.metrics: Optional[Any] = self.services.get("metrics")

        # Initialize Analytics Dashboard (T23-T24)
        self.dashboard: Optional[Any] = None
        if Config.ANALYTICS_DASHBOARD_ENABLED:
            try:
                from services.analytics.dashboard import AnalyticsDashboard

                self.dashboard = AnalyticsDashboard(
                    port=Config.ANALYTICS_DASHBOARD_PORT,
                    api_key=Config.ANALYTICS_API_KEY,
                    enabled=True,
                )
                self.dashboard.bot = self  # Give dashboard access to bot
                logger.info("Analytics dashboard initialized")
            except Exception as e:
                logger.error(f"Failed to initialize analytics dashboard: {e}")
                self.dashboard = None

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        logger.info("Setting up bot...")

        # Initialize Web Search if enabled
        if self.services.get("web_search"):
            await self.services["web_search"].initialize()
            logger.info("Web search initialized")

        # Initialize RAG if enabled
        if self.services.get("rag"):
            await self.services["rag"].initialize()
            logger.info("RAG service initialized")

        # Initialize LLM Service
        if self.ollama:
            await self.ollama.initialize()
            if not await self.ollama.check_health():
                logger.warning("LLM Provider check failed - check config/internet.")
            else:
                logger.info("Connected to LLM Provider")

        # Load ChatCog (Dependencies injected)

        await self.add_cog(
            ChatCog(
                self,
                ollama=cast("LLMInterface", self.ollama),
                history_manager=self.services["history"],
                user_profiles=self.services.get("profiles"),
                summarizer=self.services.get("summarizer"),
                web_search=self.services.get("web_search"),
                rag=self.services.get("rag"),
                conversation_manager=self.services.get("conversation_manager"),
                persona_system=self.services.get("persona_system"),
                compiled_persona=self.services.get("compiled_persona"),
                llm_fallback=self.services.get("llm_fallback"),
                persona_relationships=self.services.get("persona_relationships"),
            )
        )
        logger.info("Loaded ChatCog")

        # Load VoiceCog (only if TTS is available)
        if self.tts:
            await self.add_cog(
                VoiceCog(
                    self,
                    tts=self.tts,
                    rvc=self.rvc,
                    voice_activity_detector=self.services.get(
                        "voice_activity_detector"
                    ),
                    enhanced_voice_listener=self.services.get(
                        "enhanced_voice_listener"
                    ),
                )
            )
            logger.info("Loaded VoiceCog")
        else:
            logger.warning("TTS service not available - VoiceCog not loaded")

        # Load MusicCog
        await self.add_cog(MusicCog(self))
        logger.info("Loaded MusicCog")

        # Load Feature Cogs
        if self.services.get("reminders"):
            await self.add_cog(RemindersCog(self, self.services["reminders"]))

        if self.services.get("notes"):
            await self.add_cog(NotesCog(self, self.services["notes"]))

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
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")
                # Continue loading other extensions instead of crashing

        # Load Event Listeners
        from cogs.event_listeners import EventListenersCog

        await self.add_cog(EventListenersCog(self))

        # Sync commands (only if connected)
        try:
            await self.tree.sync()
            logger.info("Synced command tree")
        except discord.errors.MissingApplicationID:
            # Bot not connected yet, will sync in on_ready
            logger.info("Commands will sync after Discord connection")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        # Start Background Tasks
        self._start_background_services()

        # Start Analytics Dashboard (T23-T24)
        if self.dashboard:
            await self.dashboard.start()
            logger.info(
                f"Analytics dashboard running on http://localhost:{Config.ANALYTICS_DASHBOARD_PORT}"
            )

    def _start_background_services(self):
        """Start background maintenance tasks."""
        # Memory Cleanup
        if self.services.get("memory_manager"):
            task = asyncio.create_task(
                self.services["memory_manager"].start_background_cleanup(
                    interval_hours=Config.MEMORY_CLEANUP_INTERVAL_HOURS
                )
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # Profile Saver
        if self.services.get("profiles"):
            task = asyncio.create_task(
                self.services["profiles"].start_background_saver()
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        # Reminders
        if self.services.get("reminders"):
            task = asyncio.create_task(self.services["reminders"].start())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

    async def on_ready(self):
        """Called when bot is ready."""
        if self.user:
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set presence
        if self.user:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="/chat | /speak",
                )
            )

        # Start metrics auto-save (configurable interval)
        if Config.METRICS_ENABLED and self.metrics:
            try:
                # In DEBUG mode, save more frequently (every 10 minutes) for easier analysis
                if Config.LOG_LEVEL == "DEBUG":
                    interval_minutes = 10
                    logger.info(
                        "DEBUG mode detected: Metrics will save every 10 minutes for detailed analysis"
                    )
                else:
                    interval_minutes = Config.METRICS_SAVE_INTERVAL_MINUTES

                interval_hours = interval_minutes / 60.0
                if self.metrics:
                    metrics_task = self.metrics.start_auto_save(
                        interval_hours=interval_hours
                    )
                    self.background_tasks.add(metrics_task)
                    logger.info(
                        f"Metrics auto-save started (every {interval_minutes} minutes)"
                    )

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
        if chat_cog and hasattr(chat_cog, "check_and_handle_message"):
            await chat_cog.check_and_handle_message(message)  # type: ignore

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
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
        """Cleanup when bot is shutting down with graceful shutdown sequence."""
        logger.info("=" * 60)
        logger.info("SHUTDOWN INITIATED - Starting graceful shutdown sequence")
        logger.info("=" * 60)

        shutdown_start = asyncio.get_event_loop().time()

        try:
            # Step 1: Stop accepting new requests (set a flag if needed)
            logger.info("[1/8] Stopping new request acceptance...")
            # Discord.py will handle this naturally as we close

            # Step 2: Save all pending metrics data
            logger.info("[2/8] Saving metrics data...")
            if self.metrics:
                try:
                    await asyncio.wait_for(self.metrics.shutdown(), timeout=10.0)
                    logger.info("✓ Metrics service shutdown complete")
                except asyncio.TimeoutError:
                    logger.warning("⚠ Metrics shutdown timed out after 10s")
                except Exception as e:
                    logger.error(f"✗ Metrics shutdown error: {e}")

            # Step 3: Cancel background tasks
            logger.info(
                f"[3/8] Cancelling {len(self.background_tasks)} background tasks..."
            )
            if self.background_tasks:
                for task in self.background_tasks:
                    if not task.done():
                        task.cancel()

                # Wait for cancellation with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.background_tasks, return_exceptions=True),
                        timeout=5.0,
                    )
                    logger.info("✓ All background tasks cancelled")
                except asyncio.TimeoutError:
                    logger.warning("⚠ Some background tasks didn't cancel in time")

            # Step 4: Cleanup cog background tasks
            logger.info("[4/8] Cleaning up cog tasks...")
            chat_cog = self.get_cog("ChatCog")
            if chat_cog and hasattr(chat_cog, "cleanup_tasks"):
                try:
                    await asyncio.wait_for(chat_cog.cleanup_tasks(), timeout=5.0)  # type: ignore
                    logger.info("✓ ChatCog tasks cleaned up")
                except asyncio.TimeoutError:
                    logger.warning("⚠ ChatCog cleanup timed out")
                except Exception as e:
                    logger.error(f"✗ ChatCog cleanup error: {e}")

            # Step 5: Stop and flush service data
            logger.info("[5/8] Stopping and flushing services...")

            # Profiles - save all dirty profiles
            if self.services.get("profiles"):
                try:
                    await asyncio.wait_for(
                        self.services["profiles"].stop_background_saver(), timeout=10.0
                    )
                    logger.info("✓ User profiles saved")
                except asyncio.TimeoutError:
                    logger.warning("⚠ Profile save timed out after 10s")
                except Exception as e:
                    logger.error(f"✗ Profile save error: {e}")

            # Reminders - stop checking loop
            if self.services.get("reminders"):
                try:
                    await asyncio.wait_for(
                        self.services["reminders"].stop(), timeout=3.0
                    )
                    logger.info("✓ Reminders service stopped")
                except asyncio.TimeoutError:
                    logger.warning("⚠ Reminders stop timed out")
                except Exception as e:
                    logger.error(f"✗ Reminders stop error: {e}")

            # Step 6: Shutdown Analytics Dashboard
            logger.info("[6/8] Shutting down analytics dashboard...")
            if self.dashboard:
                try:
                    await asyncio.wait_for(self.dashboard.stop(), timeout=3.0)
                    logger.info("✓ Analytics dashboard stopped")
                except asyncio.TimeoutError:
                    logger.warning("⚠ Dashboard shutdown timed out")
                except Exception as e:
                    logger.error(f"✗ Dashboard shutdown error: {e}")

            # Step 7: Close external connections (LLM, TTS, RVC, Web Search, etc.)
            logger.info("[7/8] Closing external connections...")

            # Close LLM connections
            if self.ollama:
                try:
                    await asyncio.wait_for(self.ollama.close(), timeout=3.0)
                    logger.info("✓ LLM connection closed")
                except asyncio.TimeoutError:
                    logger.warning("⚠ LLM close timed out")
                except Exception as e:
                    logger.error(f"✗ LLM close error: {e}")

            # Close TTS/RVC services
            if self.tts and hasattr(self.tts, "cleanup"):
                try:
                    await asyncio.wait_for(
                        self.tts.cleanup(), timeout=Config.SERVICE_CLEANUP_TIMEOUT
                    )
                    logger.info("✓ TTS service cleaned up")
                except Exception as e:
                    logger.error(f"✗ TTS cleanup error: {e}")

            if self.rvc and hasattr(self.rvc, "close"):
                try:
                    await asyncio.wait_for(
                        self.rvc.close(), timeout=Config.SERVICE_CLEANUP_TIMEOUT
                    )
                    logger.info("✓ RVC service closed")
                except Exception as e:
                    logger.error(f"✗ RVC close error: {e}")

            # Close web search
            if self.services.get("web_search") and hasattr(
                self.services["web_search"], "close"
            ):
                try:
                    await asyncio.wait_for(
                        self.services["web_search"].close(),
                        timeout=Config.SERVICE_CLEANUP_TIMEOUT,
                    )
                    logger.info("✓ Web search closed")
                except Exception as e:
                    logger.error(f"✗ Web search close error: {e}")

            # Close STT service
            if self.services.get("stt") and hasattr(self.services["stt"], "close"):
                try:
                    await asyncio.wait_for(self.services["stt"].close(), timeout=2.0)
                    logger.info("✓ STT service closed")
                except Exception as e:
                    logger.error(f"✗ STT close error: {e}")

            # Step 8: Close Discord connection
            logger.info("[8/8] Closing Discord connection...")
            await super().close()
            logger.info("✓ Discord connection closed")

            # Calculate shutdown time
            shutdown_duration = asyncio.get_event_loop().time() - shutdown_start
            logger.info("=" * 60)
            logger.info(f"SHUTDOWN COMPLETE - Took {shutdown_duration:.2f}s")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            # Still try to close Discord connection
            try:
                await super().close()
            except Exception:
                pass


async def run_dashboard_server(bot):
    """Run uvicorn server for analytics dashboard in background."""
    if not Config.ANALYTICS_DASHBOARD_ENABLED or not bot.dashboard:
        return

    try:
        import uvicorn

        config = uvicorn.Config(
            app=bot.dashboard.app,
            host="0.0.0.0",
            port=Config.ANALYTICS_DASHBOARD_PORT,
            log_level="warning",  # Reduce uvicorn noise
        )
        server = uvicorn.Server(config)
        await server.serve()
    except ImportError:
        logger.warning("uvicorn not installed - dashboard server disabled")
    except Exception as e:
        logger.error(f"Dashboard server error: {e}")


def setup_signal_handlers(bot):
    """Setup signal handlers for graceful shutdown."""
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum} - initiating graceful shutdown...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    return shutdown_event


async def run_bot_with_signals(bot):
    """Run bot with signal handling for graceful shutdown."""
    shutdown_event = setup_signal_handlers(bot)

    # Create task for monitoring shutdown signals
    async def monitor_shutdown():
        await shutdown_event.wait()
        logger.info("Shutdown signal received, closing bot...")
        await bot.close()

    shutdown_monitor = asyncio.create_task(monitor_shutdown())

    try:
        if Config.ANALYTICS_DASHBOARD_ENABLED:
            logger.info("Analytics dashboard enabled - running dual services")

            dashboard_task = asyncio.create_task(run_dashboard_server(bot))

            try:
                await bot.start(Config.DISCORD_TOKEN)
            except discord.LoginFailure:
                logger.error(
                    "Invalid Discord token! Please check DISCORD_TOKEN in .env"
                )
                dashboard_task.cancel()
                raise
            except Exception as e:
                logger.error(f"Fatal error: {e}")
                dashboard_task.cancel()
                raise
            finally:
                if not dashboard_task.done():
                    dashboard_task.cancel()
                await asyncio.gather(dashboard_task, return_exceptions=True)
        else:
            await bot.start(Config.DISCORD_TOKEN)

    except asyncio.CancelledError:
        logger.info("Bot task cancelled, initiating shutdown...")
    finally:
        # Cancel shutdown monitor
        shutdown_monitor.cancel()
        try:
            await shutdown_monitor
        except asyncio.CancelledError:
            pass


def main():
    """Main entry point with graceful shutdown support."""
    logger.info("Starting Discord Ollama Bot...")

    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file!")
        sys.exit(1)

    # Create bot
    bot = OllamaBot()

    # Run with signal handling
    try:
        asyncio.run(run_bot_with_signals(bot))
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except discord.LoginFailure:
        logger.error("Invalid Discord token! Please check DISCORD_TOKEN in .env")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    main()
