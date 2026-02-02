import discord
from discord.ext import commands
import shutil
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RLCommands(commands.Cog):
    """Commands for managing the Reinforcement Learning service."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def rl_service(self):
        """Helper to access the RL service safely."""
        # Using getattr to avoid errors if 'rl' service key is missing
        if hasattr(self.bot, "services"):
            return self.bot.services.get("rl")
        return None

    @commands.command(name="rl_stats")
    async def rl_stats(self, ctx):
        """Show statistics for the Reinforcement Learning system."""
        service = self.rl_service

        if not service:
            await ctx.send("❌ RL Service is not initialized.")
            return

        # Calculate stats
        agent_count = len(service.agents)
        is_enabled = service.enabled

        avg_epsilon = 0.0
        if agent_count > 0:
            avg_epsilon = sum(a.epsilon for a in service.agents.values()) / agent_count

        # Create Embed
        embed = discord.Embed(
            title="🧠 RL System Statistics",
            color=discord.Color.green() if is_enabled else discord.Color.red(),
            timestamp=ctx.message.created_at,
        )

        status_icon = "🟢" if is_enabled else "🔴"
        embed.add_field(
            name="Status",
            value=f"{status_icon} {'Enabled' if is_enabled else 'Disabled'}",
            inline=True,
        )
        embed.add_field(name="Active Agents", value=str(agent_count), inline=True)
        embed.add_field(name="Average Epsilon", value=f"{avg_epsilon:.4f}", inline=True)

        # Add footer
        embed.set_footer(text="RL Service | Acore Bot")

        await ctx.send(embed=embed)

    @commands.command(name="rl_toggle")
    @commands.has_permissions(administrator=True)
    async def rl_toggle(self, ctx):
        """Toggle the RL system on or off (Admin only)."""
        service = self.rl_service

        if not service:
            await ctx.send("❌ RL Service is not initialized.")
            return

        service.enabled = not service.enabled
        status = "ENABLED" if service.enabled else "DISABLED"
        icon = "🟢" if service.enabled else "🔴"

        logger.info(f"RL Service toggled to {status} by {ctx.author}")
        await ctx.send(f"{icon} RL Service is now **{status}**")

    @commands.command(name="rl_reset")
    @commands.is_owner()
    async def rl_reset(self, ctx, confirm: str = ""):
        """
        Reset all RL agents and clear training data.
        Usage: !rl_reset confirm
        """
        if confirm.lower() != "confirm":
            await ctx.send("⚠ **WARNING**: This will wipe all RL training data!")
            await ctx.send("To proceed, type: `!rl_reset confirm`")
            return

        service = self.rl_service
        if not service:
            await ctx.send("❌ RL Service is not initialized.")
            return

        await ctx.send("⏳ Resetting RL system...")

        try:
            # 1. Backup existing data
            data_file = service.storage.file_path
            if data_file.exists():
                backup_path = data_file.with_suffix(".bak")
                await asyncio.to_thread(shutil.copy2, data_file, backup_path)
                await ctx.send(f"📦 Backup created: `{backup_path.name}`")

            # 2. Clear in-memory agents
            agent_count_before = len(service.agents)
            service.agents.clear()
            service.agent_locks.clear()

            # 3. Clear storage file (save empty dict)
            await asyncio.to_thread(service.storage.save, {})

            logger.warning(
                f"RL System reset by {ctx.author}. Cleared {agent_count_before} agents."
            )
            await ctx.send(
                f"✅ RL System reset complete. Cleared {agent_count_before} agents."
            )

        except Exception as e:
            logger.error(f"Failed to reset RL system: {e}", exc_info=True)
            await ctx.send(f"❌ An error occurred during reset: {str(e)}")

    @rl_toggle.error
    async def rl_toggle_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need Administrator permissions to use this command.")

    @rl_reset.error
    async def rl_reset_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Only the bot owner can reset the RL system.")
