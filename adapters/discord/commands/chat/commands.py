"""Command handler for ChatCog."""

import logging
import discord
from discord.ext import commands

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
            # Use BehaviorEngine instead of legacy AmbientMode
            engine = getattr(self.cog, "behavior_engine", None)

            if not engine:
                await interaction.response.send_message(
                    "❌ Behavior Engine is not configured.", ephemeral=True
                )
                return

            if action == "status":
                running = getattr(engine, "_running", False)
                active_count = len(engine.states)

                embed = discord.Embed(
                    title="🌙 Ambient Mode (Behavior Engine)",
                    color=discord.Color.purple(),
                )
                embed.add_field(
                    name="Status",
                    value="🟢 Running" if running else "🔴 Stopped",
                    inline=True,
                )
                embed.add_field(
                    name="Active Channels",
                    value=str(active_count),
                    inline=True,
                )
                embed.add_field(
                    name="Trigger Chance",
                    value=f"{int(engine.ambient_chance * 100)}%",
                    inline=True,
                )
                embed.add_field(
                    name="Min Interval",
                    value=f"{engine.ambient_interval_min}s",
                    inline=True,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif action == "enable":
                if getattr(engine, "_running", False):
                    await interaction.response.send_message(
                        "✅ Ambient mode is already running.", ephemeral=True
                    )
                else:
                    await engine.start()
                    await interaction.response.send_message(
                        "✅ Ambient mode enabled!", ephemeral=True
                    )

            elif action == "disable":
                if not getattr(engine, "_running", False):
                    await interaction.response.send_message(
                        "❌ Ambient mode is already stopped.", ephemeral=True
                    )
                else:
                    await engine.stop()
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

                # Also clear the chat history to ensure a fresh start
                if hasattr(self.cog, "history"):
                    await self.cog.history.clear_history(channel_id)

                await interaction.response.send_message(
                    format_success(
                        "Conversation session ended & history cleared. Use @mention or `/chat` to start a new session."
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "No active conversation session in this channel.", ephemeral=True
                )
        except Exception as e:
            logger.error(f"End session command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    async def mode(self, interaction: discord.Interaction, new_mode: str):
        from config import Config

        try:
            if new_mode.lower() not in Config.BOT_MODE_CHOICES:
                await interaction.response.send_message(
                    f"❌ Invalid mode. Choose from: {', '.join(Config.BOT_MODE_CHOICES)}",
                    ephemeral=True,
                )
                return

            Config.BOT_MODE = new_mode.lower()

            mode_descriptions = {
                "roleplay": "🎭 Full character immersion - roleplay only",
                "assistant": "🤖 Helpful AI assistant - utility focused",
                "hybrid": "🎭 + 🤖 Balanced blend of roleplay and assistance",
            }

            embed = discord.Embed(
                title=f"🔄 Bot Mode Changed",
                description=mode_descriptions.get(new_mode.lower(), ""),
                color=discord.Color.blue(),
            )
            embed.add_field(name="Current Mode", value=new_mode.lower(), inline=True)
            embed.add_field(
                name="Effect",
                value="Context building adjusted based on mode",
                inline=True,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(
                f"Bot mode changed to {new_mode.lower()} by {interaction.user.display_name}"
            )

        except Exception as e:
            logger.error(f"Mode command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)
