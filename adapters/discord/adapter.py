"""
Discord adapters for the Acore Bot framework.

This module provides input and output adapters that bridge Discord events
with the Acore core system using platform-agnostic types.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Union
from datetime import datetime

import discord
from discord.ext import commands

from core.interfaces import InputAdapter, OutputAdapter, AcoreEvent
from core.types import AcoreMessage, AcoreUser, AcoreChannel

logger = logging.getLogger(__name__)


class DiscordInputAdapter(InputAdapter):
    """
    InputAdapter for Discord. Converts Discord events into AcoreEvent.

    Uses discord.py Bot/Client to connect to Discord and listen for events,
    then converts them to platform-agnostic AcoreEvent instances for processing
    by the core system.
    """

    def __init__(
        self,
        token: str,
        command_prefix: str = "!",
        intents: Optional[discord.Intents] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Discord input adapter.

        Args:
            token: Discord bot token for authentication.
            command_prefix: Prefix for text commands (default: "!").
            intents: Discord intents to use. If None, default intents with
                     message_content will be used.
        """
        super().__init__()
        self.token = token
        self._event_callback: Optional[Callable[[AcoreEvent], Any]] = None
        self._running = False

        # Configure intents
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            intents.presences = True
            intents.members = True

        # Create the bot instance
        self.bot = commands.Bot(
            command_prefix=command_prefix,
            intents=intents,
            help_command=None,
        )

        # Register event handlers
        self.bot.event(self._on_ready)
        self.bot.event(self._on_message)
        self.bot.event(self._on_reaction_add)
        self.bot.event(self._on_disconnect)

    async def _on_ready(self) -> None:
        """Called when the bot successfully connects to Discord."""
        logger.info(f"DiscordInputAdapter connected as {self.bot.user}")
        logger.info(f"Connected to {len(self.bot.guilds)} guild(s)")

    async def _on_disconnect(self) -> None:
        """Called when the bot disconnects from Discord."""
        logger.warning("DiscordInputAdapter disconnected from Discord")

    async def _on_message(self, message: discord.Message) -> None:
        """
        Handle incoming Discord messages.

        Converts discord.Message to AcoreMessage and emits an AcoreEvent.
        """
        # Skip messages from the bot itself to prevent loops
        if message.author == self.bot.user:
            return

        # Convert Discord message to AcoreMessage
        acore_message = self._convert_message(message)

        # Create AcoreEvent
        event = AcoreEvent(
            type="message",
            payload={"message": acore_message},
            source_adapter="discord",
            timestamp=message.created_at or datetime.utcnow(),
        )

        # Emit to registered callback
        await self._emit_event(event)

        # Process commands
        await self.bot.process_commands(message)

    async def _on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User
    ) -> None:
        """
        Handle reaction add events.

        Converts discord.Reaction to a reaction event and emits an AcoreEvent.
        """
        # Skip reactions from the bot itself
        if user == self.bot.user:
            return

        # Create reaction event payload
        payload = {
            "emoji": str(reaction.emoji),
            "message_id": str(reaction.message.id),
            "channel_id": str(reaction.message.channel.id),
            "user_id": str(user.id),
            "message_author_id": str(reaction.message.author.id),
            "count": reaction.count,
        }

        event = AcoreEvent(
            type="reaction",
            payload=payload,
            source_adapter="discord",
            timestamp=datetime.utcnow(),
        )

        await self._emit_event(event)

    def _convert_message(self, message: discord.Message) -> AcoreMessage:
        """
        Convert a discord.Message to an AcoreMessage.

        Args:
            message: The Discord message to convert.

        Returns:
            An AcoreMessage with platform-agnostic data.
        """
        # Convert attachments to metadata dictionaries
        attachments = []
        for attachment in message.attachments:
            attachments.append(
                {
                    "url": attachment.url,
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size": attachment.size,
                }
            )

        return AcoreMessage(
            text=message.content or "",
            author_id=str(message.author.id),
            channel_id=str(message.channel.id),
            timestamp=message.created_at or datetime.utcnow(),
            attachments=attachments,
        )

    def _convert_user(self, user: discord.User) -> AcoreUser:
        """
        Convert a discord.User to an AcoreUser.

        Args:
            user: The Discord user to convert.

        Returns:
            An AcoreUser with platform-agnostic data.
        """
        return AcoreUser(
            id=str(user.id),
            display_name=user.display_name,
            metadata={
                "username": user.name,
                "discriminator": getattr(user, "discriminator", None),
                "bot": user.bot,
            },
        )

    def _convert_channel(self, channel: discord.abc.GuildChannel) -> AcoreChannel:
        """
        Convert a discord channel to an AcoreChannel.

        Args:
            channel: The Discord channel to convert.

        Returns:
            An AcoreChannel with platform-agnostic data.
        """
        # Determine channel type
        channel_type = "text"
        if isinstance(channel, discord.DMChannel):
            channel_type = "dm"
        elif isinstance(channel, discord.Thread):
            channel_type = "thread"
        elif isinstance(channel, discord.VoiceChannel):
            channel_type = "voice"

        # Get parent ID for threads
        parent_id = None
        if isinstance(channel, discord.Thread) and channel.parent:
            parent_id = str(channel.parent.id)

        return AcoreChannel(
            id=str(channel.id),
            name=getattr(channel, "name", "dm"),
            type=channel_type,
            parent_id=parent_id,
        )

    async def _emit_event(self, event: AcoreEvent) -> None:
        """Emit an event to the registered callback."""
        if self._event_callback is None:
            logger.debug(f"No event callback registered, dropping event: {event.type}")
            return

        try:
            result = self._event_callback(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Error in event callback for {event.type}: {e}")

    async def start(self) -> None:
        """
        Start the Discord input adapter.

        Connects to Discord and begins listening for events.
        """
        if self._running:
            logger.warning("DiscordInputAdapter is already running")
            return

        logger.info("Starting DiscordInputAdapter...")
        self._running = True

        try:
            await self.bot.start(self.token)
        except discord.LoginFailure as e:
            self._running = False
            logger.error(f"Failed to login to Discord: {e}")
            raise
        except Exception as e:
            self._running = False
            logger.error(f"Error starting DiscordInputAdapter: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the Discord input adapter.

        Gracefully disconnects from Discord and cleans up resources.
        """
        if not self._running:
            logger.warning("DiscordInputAdapter is not running")
            return

        logger.info("Stopping DiscordInputAdapter...")
        self._running = False

        try:
            await self.bot.close()
            logger.info("DiscordInputAdapter stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping DiscordInputAdapter: {e}")
            raise

    def on_event(self, callback: Callable[[AcoreEvent], None]) -> None:
        """
        Register a callback to handle incoming events.

        Args:
            callback: A function that will be called with each AcoreEvent
                     received by this adapter. Can be sync or async.
        """
        self._event_callback = callback
        logger.debug("Event callback registered for DiscordInputAdapter")


class DiscordOutputAdapter(OutputAdapter):
    """OutputAdapter for Discord. Sends messages via Discord bot/webhook."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message to a Discord channel."""
        channel = self.bot.get_channel(int(channel_id))
        if channel and isinstance(channel, discord.abc.Messageable):
            await channel.send(content=text, **options)

    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send an embed to a Discord channel."""
        channel = self.bot.get_channel(int(channel_id))
        if channel and isinstance(channel, discord.abc.Messageable):
            discord_embed = discord.Embed.from_dict(embed)
            await channel.send(embed=discord_embed)
