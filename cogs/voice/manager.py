"""Voice client connection and lifecycle management."""
import discord
from discord.ext import voice_recv
import logging
import asyncio
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class VoiceManager:
    """Manages voice client connections and lifecycle across guilds."""

    def __init__(self, bot):
        """Initialize voice manager.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.voice_clients: Dict[int, discord.VoiceClient] = {}  # guild_id -> voice_client
        self.voice_clients_lock = asyncio.Lock()  # Protect from race conditions

    async def join_channel(self, channel: discord.VoiceChannel, guild_id: int) -> Optional[discord.VoiceClient]:
        """Join a voice channel.

        Args:
            channel: Discord voice channel to join
            guild_id: Guild ID

        Returns:
            Voice client if successful, None otherwise
        """
        try:
            async with self.voice_clients_lock:
                if guild_id in self.voice_clients:
                    logger.info(f"Already connected to voice in guild {guild_id}")
                    return self.voice_clients[guild_id]

                voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
                self.voice_clients[guild_id] = voice_client
                logger.info(f"Joined voice channel: {channel.name} in guild {guild_id}")
                return voice_client

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            return None

    async def leave_channel(self, guild_id: int) -> bool:
        """Leave voice channel in a guild.

        Args:
            guild_id: Guild ID

        Returns:
            True if left successfully, False if not connected
        """
        async with self.voice_clients_lock:
            if guild_id not in self.voice_clients:
                logger.warning(f"Not connected to voice in guild {guild_id}")
                return False

            voice_client = self.voice_clients[guild_id]
            del self.voice_clients[guild_id]

        try:
            await voice_client.disconnect()
            logger.info(f"Left voice channel in guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to leave voice channel: {e}")
            return False

    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """Get voice client for a guild.

        Args:
            guild_id: Guild ID

        Returns:
            Voice client if connected, None otherwise
        """
        return self.voice_clients.get(guild_id)

    def is_connected(self, guild_id: int) -> bool:
        """Check if connected to voice in a guild.

        Args:
            guild_id: Guild ID

        Returns:
            True if connected
        """
        return guild_id in self.voice_clients

    async def cleanup_guild(self, guild_id: int):
        """Clean up voice client for a guild.

        Used when bot is removed from a guild or on shutdown.

        Args:
            guild_id: Guild ID
        """
        async with self.voice_clients_lock:
            if guild_id in self.voice_clients:
                try:
                    voice_client = self.voice_clients[guild_id]
                    if voice_client.is_connected():
                        await voice_client.disconnect()

                    del self.voice_clients[guild_id]
                    logger.info(f"Cleaned up voice client for guild {guild_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up voice client for guild {guild_id}: {e}")

    async def cleanup_all(self):
        """Clean up all voice clients on shutdown."""
        async with self.voice_clients_lock:
            guild_ids = list(self.voice_clients.keys())

        for guild_id in guild_ids:
            await self.cleanup_guild(guild_id)

        logger.info("Cleaned up all voice clients")
