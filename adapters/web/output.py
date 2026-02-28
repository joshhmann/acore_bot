"""Web output adapter for Gestalt Framework."""

import logging
from typing import Any, Optional, Dict
import asyncio

from core.interfaces import OutputAdapter, EventBus

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebOutputAdapter(OutputAdapter):
    """Output adapter for web API responses."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__()
        self.event_bus = event_bus
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._webhook_client = None

        if HTTPX_AVAILABLE:
            self._webhook_client = httpx.AsyncClient()

    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message."""
        if channel_id in self._pending_responses:
            future = self._pending_responses[channel_id]
            if not future.done():
                future.set_result(
                    {
                        "response": text,
                        "persona_id": options.get("persona_id", "unknown"),
                        "persona_name": options.get("display_name", "Unknown"),
                    }
                )

        webhook_url = options.get("webhook_url")
        if webhook_url and self._webhook_client:
            await self._send_webhook(
                webhook_url,
                {
                    "response": text,
                    "channel_id": channel_id,
                    "persona_id": options.get("persona_id"),
                    "persona_name": options.get("display_name"),
                },
            )

    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content."""
        text = self._format_embed(embed)
        await self.send(channel_id, text)

    async def start(self) -> None:
        """Start the output adapter."""
        logger.info("WebOutputAdapter started")

    async def stop(self) -> None:
        """Stop the output adapter."""
        logger.info("WebOutputAdapter stopped")
        if self._webhook_client:
            await self._webhook_client.aclose()

    def create_response_future(self, channel_id: str) -> asyncio.Future:
        """Create a future to wait for a response."""
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[channel_id] = future

        async def cleanup():
            try:
                await asyncio.wait_for(future, timeout=60.0)
            except asyncio.TimeoutError:
                if channel_id in self._pending_responses:
                    del self._pending_responses[channel_id]

        asyncio.create_task(cleanup())
        return future

    async def _send_webhook(self, url: str, data: dict) -> None:
        """Send data to webhook URL."""
        if not self._webhook_client:
            logger.warning("httpx not available, cannot send webhook")
            return

        try:
            response = await self._webhook_client.post(url, json=data, timeout=30.0)
            response.raise_for_status()
            logger.debug(f"Webhook sent successfully to {url}")
        except Exception as e:
            logger.error(f"Failed to send webhook to {url}: {e}")

    def _format_embed(self, embed: dict) -> str:
        """Format embed dict as text."""
        lines = []
        if "title" in embed:
            lines.append(f"**{embed['title']}**")
        if "description" in embed:
            lines.append(embed["description"])
        if "fields" in embed:
            for field in embed["fields"]:
                name = field.get("name", "")
                value = field.get("value", "")
                lines.append(f"\n{name}:\n{value}")
        return "\n".join(lines) if lines else str(embed)
