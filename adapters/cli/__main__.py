"""CLI adapter entry point for running with `python -m adapters.cli`."""

import asyncio
import logging
import sys

from adapters.cli.adapter import CLIInputAdapter, CLIOutputAdapter
from core.interfaces import AcoreEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_event(event: AcoreEvent) -> None:
    """Handle incoming events from the CLI input adapter."""
    logger.info(f"Received event: type={event.type}, source={event.source_adapter}")

    if event.type == "message":
        payload = event.payload
        message = payload.get("message")
        persona_id = payload.get("persona_id")

        if message:
            logger.info(f"Message from {message.author_id}: {message.text}")
            logger.info(f"Target persona: {persona_id}")

            # Echo response via output adapter
            output = CLIOutputAdapter()
            response_text = f"Received: '{message.text}' (targeting @{persona_id})"
            await output.send(
                channel_id=message.channel_id,
                text=response_text,
                persona_id="cli_bot",
                display_name="CLI Bot",
            )


async def main() -> None:
    """Main entry point for CLI adapter."""
    logger.info("Starting CLI adapter...")

    # Create input adapter
    input_adapter = CLIInputAdapter()

    # Register event handler
    input_adapter.on_event(handle_event)

    # Start input adapter
    await input_adapter.start()

    try:
        # Wait for input processing to complete (EOF or interrupt)
        while input_adapter._running:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await input_adapter.stop()
        logger.info("CLI adapter stopped")


if __name__ == "__main__":
    asyncio.run(main())
