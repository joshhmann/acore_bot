"""Discord-specific output adapter with webhook spoofing capabilities."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

import discord

from core.interfaces import OutputAdapter, EventBus

logger = logging.getLogger(__name__)


class WebhookPool:
    """Manages Discord webhooks to avoid rate limits.

    Discord limits: 10 webhooks per guild, 30 requests/minute per webhook.
    """

    def __init__(self, channel: discord.TextChannel, max_webhooks: int = 10):
        self.channel = channel
        self.max_webhooks = max_webhooks
        self.webhooks: Dict[str, discord.Webhook] = {}
        self.webhook_order: List[str] = []

    async def get_or_create_webhook(
        self, persona_id: str, display_name: str, avatar_url: str
    ) -> discord.Webhook:
        """Get existing webhook or create new one."""

        if persona_id in self.webhooks:
            self.webhook_order.remove(persona_id)
            self.webhook_order.append(persona_id)
            return self.webhooks[persona_id]

        if len(self.webhooks) >= self.max_webhooks:
            lru_persona = self.webhook_order.pop(0)
            old_webhook = self.webhooks.pop(lru_persona)
            await old_webhook.edit(
                name=display_name, avatar=await self._fetch_avatar(avatar_url)
            )
            self.webhooks[persona_id] = old_webhook
            self.webhook_order.append(persona_id)
            return old_webhook

        try:
            webhook = await self.channel.create_webhook(
                name=display_name, avatar=await self._fetch_avatar(avatar_url)
            )
            self.webhooks[persona_id] = webhook
            self.webhook_order.append(persona_id)
            logger.debug(f"Created webhook for {persona_id}")
            return webhook
        except discord.HTTPException as e:
            logger.error(f"Failed to create webhook: {e}")
            raise

    async def _fetch_avatar(self, avatar_url: str) -> Optional[bytes]:
        """Fetch avatar image bytes from URL."""
        if not avatar_url:
            return None

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.warning(f"Failed to fetch avatar from {avatar_url}: {e}")

        return None

    async def send_message(
        self,
        persona_id: str,
        display_name: str,
        avatar_url: str,
        content: str,
        wait: bool = True,
    ) -> Optional[discord.Message]:
        """Send a message via webhook with persona spoofing."""
        webhook = await self.get_or_create_webhook(persona_id, display_name, avatar_url)
        return await webhook.send(
            content=content,
            username=display_name,
            avatar_url=avatar_url,
            wait=wait,
        )


class DiscordOutputAdapter(OutputAdapter):
    """Discord OutputAdapter with webhook spoofing support.

    This adapter handles sending messages to Discord channels and supports
    persona spoofing via webhooks. It listens for conversation events
    and sends messages using the appropriate persona's name and avatar.
    """

    def __init__(
        self,
        bot: discord.Client,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__()
        self.bot = bot
        self.event_bus = event_bus
        self._webhook_pools: Dict[str, WebhookPool] = {}
        self._event_handlers: Dict[str, Callable] = {}

    async def start(self) -> None:
        """Start the adapter and subscribe to events."""
        if self.event_bus:
            self._event_handlers["persona_spoke"] = self._on_persona_spoke
            self._event_handlers["conversation_typing"] = self._on_conversation_typing
            self._event_handlers["conversation_summary"] = self._on_conversation_summary
            
            self.event_bus.subscribe("persona_spoke", self._on_persona_spoke)
            self.event_bus.subscribe("conversation_typing", self._on_conversation_typing)
            self.event_bus.subscribe("conversation_summary", self._on_conversation_summary)
            logger.debug("DiscordOutputAdapter subscribed to conversation events")

    async def stop(self) -> None:
        """Stop the adapter and unsubscribe from events."""
        if self.event_bus:
            for event_type, handler in self._event_handlers.items():
                self.event_bus.unsubscribe(event_type, handler)
            self._event_handlers.clear()

    def _get_or_create_webhook_pool(self, channel: discord.TextChannel) -> WebhookPool:
        """Get or create a webhook pool for a channel."""
        channel_id = str(channel.id)
        if channel_id not in self._webhook_pools:
            self._webhook_pools[channel_id] = WebhookPool(channel)
        return self._webhook_pools[channel_id]

    async def _on_persona_spoke(self, event_payload: dict) -> None:
        """Handle persona_spoke event by sending via webhook."""
        channel_id = event_payload.get("channel_id")
        persona_id = event_payload.get("persona_id")
        display_name = event_payload.get("display_name")
        avatar_url = event_payload.get("avatar_url", "")
        content = event_payload.get("content", "")

        if not all([channel_id, persona_id, display_name]):
            logger.warning("Missing required fields in persona_spoke event")
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.error(f"Channel {channel_id} not found or not a text channel")
                return

            pool = self._get_or_create_webhook_pool(channel)
            await pool.send_message(
                persona_id=persona_id,
                display_name=display_name,
                avatar_url=avatar_url,
                content=content,
                wait=True,
            )
            logger.debug(f"Sent persona message from {display_name}")
        except Exception as e:
            logger.error(f"Failed to send persona message: {e}")

    async def _on_conversation_typing(self, event_payload: dict) -> None:
        """Handle conversation_typing event by showing typing indicator."""
        channel_id = event_payload.get("channel_id")
        
        if not channel_id:
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
            if channel and isinstance(channel, discord.TextChannel):
                async with channel.typing():
                    duration = event_payload.get("duration_seconds", 1.0)
                    await asyncio.sleep(duration)
        except Exception as e:
            logger.debug(f"Failed to show typing indicator: {e}")

    async def _on_conversation_summary(self, event_payload: dict) -> None:
        """Handle conversation_summary event by sending summary to channel."""
        channel_id = event_payload.get("channel_id")
        
        if not channel_id:
            return

        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.error(f"Channel {channel_id} not found")
                return

            conversation_id = event_payload.get("conversation_id", "unknown")
            participants = event_payload.get("participants", [])
            topic = event_payload.get("topic", "")
            turn_count = event_payload.get("turn_count", 0)
            max_turns = event_payload.get("max_turns", 0)
            termination_reason = event_payload.get("termination_reason", "unknown")
            avg_latency = event_payload.get("avg_latency", 0.0)

            summary = f"""
 **Conversation Complete** ({conversation_id})
 - Participants: {", ".join(participants)}
 - Topic: {topic}
 - Turns: {turn_count}/{max_turns}
 - Duration: 0.0s
 - Ending: {termination_reason}
 - Avg Latency: {avg_latency:.2f}s
            """.strip()

            await channel.send(summary)
        except Exception as e:
            logger.error(f"Failed to send conversation summary: {e}")

    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message to a channel."""
        channel = self.bot.get_channel(int(channel_id))
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.error(f"Channel {channel_id} not found")
            return

        if options.get("persona_id"):
            pool = self._get_or_create_webhook_pool(channel)
            await pool.send_message(
                persona_id=options["persona_id"],
                display_name=options.get("display_name", "Bot"),
                avatar_url=options.get("avatar_url", ""),
                content=text,
                wait=options.get("wait", False),
            )
        else:
            await channel.send(text)

    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content to a channel."""
        channel = self.bot.get_channel(int(channel_id))
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.error(f"Channel {channel_id} not found")
            return

        discord_embed = discord.Embed.from_dict(embed)
        await channel.send(embed=discord_embed)

    async def send_typing(self, channel_id: str) -> None:
        """Send typing indicator to a channel."""
        channel = self.bot.get_channel(int(channel_id))
        if channel and isinstance(channel, discord.TextChannel):
            await channel.typing()
