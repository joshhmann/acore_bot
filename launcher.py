#!/usr/bin/env python3
"""Gestalt Framework Launcher - Unified entry point for adapters.

This launcher starts the Gestalt framework with enabled adapters (Discord, CLI, Web, etc.)
and wires them to core services via an EventBus.

Usage:
    python launcher.py

Configuration:
    Adapters are enabled/disabled via environment variables or config:
    - ACORE_DISCORD_ENABLED=true/false
    - ACORE_CLI_ENABLED=true/false
    - ACORE_WEB_ENABLED=true/false
    - ACORE_WEB_PORT=8000
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from core.interfaces import SimpleEventBus
from services.core.factory import ServiceFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AcoreLauncher:
    """Main launcher for the Acore framework."""

    def __init__(self):
        self.event_bus = SimpleEventBus()
        self.adapters = {}
        self.services = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the framework with enabled adapters."""
        logger.info("Starting Gestalt Framework...")

        # Load configuration
        discord_enabled = self._get_config("ACORE_DISCORD_ENABLED", "true") == "true"
        cli_enabled = self._get_config("ACORE_CLI_ENABLED", "false") == "true"
        web_enabled = self._get_config("ACORE_WEB_ENABLED", "false") == "true"
        web_port = int(self._get_config("ACORE_WEB_PORT", "8000"))

        # Create services via factory
        logger.info("Creating services...")
        factory = ServiceFactory(bot=None)
        self.services = factory.create_services()

        # Start Discord adapter if enabled
        if discord_enabled:
            logger.info("Starting Discord adapter...")
            try:
                import os
                from adapters.discord.adapter import DiscordInputAdapter
                from adapters.discord.output import DiscordOutputAdapter

                token = os.environ.get("DISCORD_TOKEN")
                if not token:
                    raise ValueError("DISCORD_TOKEN environment variable not set")

                discord_input = DiscordInputAdapter(token=token)

                # Output adapter needs the bot instance from input adapter
                discord_output = DiscordOutputAdapter(
                    bot=discord_input.bot, event_bus=self.event_bus
                )

                def on_discord_event(event):
                    logger.debug(f"Discord event: {event.type}")
                    # TODO: Wire to core services for processing

                discord_input.on_event(on_discord_event)

                # Start Discord in background task (it blocks)
                asyncio.create_task(discord_input.start())
                await discord_output.start()

                self.adapters["discord"] = {
                    "input": discord_input,
                    "output": discord_output,
                }
                logger.info("Discord adapter started")
            except Exception as e:
                logger.error(f"Failed to start Discord adapter: {e}")

        # Start CLI adapter if enabled
        if cli_enabled:
            logger.info("Starting CLI adapter...")
            try:
                from adapters.cli.adapter import CLIInputAdapter, CLIOutputAdapter

                cli_input = CLIInputAdapter()
                cli_output = CLIOutputAdapter()

                # Register callback
                def on_cli_event(event):
                    logger.info(f"CLI event received: {event.type}")
                    # Process through core services here

                cli_input.on_event(on_cli_event)

                await cli_input.start()

                self.adapters["cli"] = {"input": cli_input, "output": cli_output}
                logger.info("CLI adapter started")
            except Exception as e:
                logger.error(f"Failed to start CLI adapter: {e}")

        # Set up signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, self._signal_handler)

        # Start Web adapter if enabled
        if web_enabled:
            logger.info("Starting Web adapter...")
            try:
                from adapters.web.adapter import WebInputAdapter
                from adapters.web.output import WebOutputAdapter

                web_input = WebInputAdapter(port=web_port)
                web_output = WebOutputAdapter(event_bus=self.event_bus)

                def on_web_event(event):
                    logger.debug(f"Web event: {event.type}")
                    # TODO: Wire to core services for processing

                web_input.on_event(on_web_event)

                await web_input.start()
                await web_output.start()

                self.adapters["web"] = {"input": web_input, "output": web_output}
                logger.info(f"Web adapter started on port {web_port}")
            except Exception as e:
                logger.error(f"Failed to start Web adapter: {e}")

        logger.info("Gestalt Framework started. Press Ctrl+C to stop.")
        await self._shutdown_event.wait()

    def _signal_handler(self):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received...")
        self._shutdown_event.set()

    async def stop(self):
        """Stop all adapters gracefully."""
        logger.info("Stopping Acore Framework...")

        for name, adapter in self.adapters.items():
            logger.info(f"Stopping {name} adapter...")
            try:
                if "input" in adapter:
                    await adapter["input"].stop()
                if "output" in adapter:
                    await adapter["output"].stop()
            except Exception as e:
                logger.error(f"Error stopping {name} adapter: {e}")

        logger.info("Acore Framework stopped")

    def _get_config(self, key: str, default: str) -> str:
        """Get configuration from environment."""
        import os

        return os.environ.get(key, default)


async def main():
    """Main entry point."""
    launcher = AcoreLauncher()
    try:
        await launcher.start()
    finally:
        await launcher.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
