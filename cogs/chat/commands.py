"""Command handler for ChatCog."""

import logging
import discord
from discord.ext import commands

from config import Config
from utils.helpers import format_error, format_success

logger = logging.getLogger(__name__)

class ChatCommandHandler:
    def __init__(self, cog: commands.Cog):
        self.cog = cog

    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with Ollama AI."""
        await self.cog._handle_chat_response(
            message_content=message,
            channel=interaction.channel,
            user=interaction.user,
            interaction=interaction,
        )

    async def ambient(self, interaction: discord.Interaction, action: str = "status"):
        """Control ambient mode."""
        try:
            ambient = getattr(self.cog.bot, "ambient_mode", None)

            if not ambient:
                await interaction.response.send_message(
                    "❌ Ambient mode is not configured.", ephemeral=True
                )
                return

            if action == "status":
                stats = ambient.get_stats()
                embed = discord.Embed(
                    title="🌙 Ambient Mode Status", color=discord.Color.purple()
                )
                embed.add_field(
                    name="Status",
                    value="🟢 Running" if stats["running"] else "🔴 Stopped",
                    inline=True,
                )
                embed.add_field(
                    name="Active Channels",
                    value=str(stats["active_channels"]),
                    inline=True,
                )
                embed.add_field(
                    name="Trigger Chance",
                    value=f"{int(stats['chance'] * 100)}%",
                    inline=True,
                )
                embed.add_field(
                    name="Lull Timeout", value=f"{stats['lull_timeout']}s", inline=True
                )
                embed.add_field(
                    name="Min Interval", value=f"{stats['min_interval']}s", inline=True
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif action == "enable":
                if ambient.running:
                    await interaction.response.send_message(
                        "✅ Ambient mode is already running.", ephemeral=True
                    )
                else:
                    await ambient.start()
                    await interaction.response.send_message(
                        "✅ Ambient mode enabled!", ephemeral=True
                    )

            elif action == "disable":
                if not ambient.running:
                    await interaction.response.send_message(
                        "❌ Ambient mode is already stopped.", ephemeral=True
                    )
                else:
                    await ambient.stop()
                    await interaction.response.send_message(
                        "✅ Ambient mode disabled.", ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Ambient command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    async def end_session(self, interaction: discord.Interaction):
        """End the active conversation session in this channel."""
        try:
            channel_id = interaction.channel_id
            if await self.cog.session_manager.is_session_active(channel_id):
                await self.cog.session_manager.end_session(channel_id)
                await interaction.response.send_message(
                    format_success(
                        f"Conversation session ended. Use @mention or `/chat` to start a new session."
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "No active conversation session in this channel.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"End session failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)
