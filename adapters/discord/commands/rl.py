import discord
from discord.ext import commands
import shutil
import asyncio
import logging
from typing import Optional
import discord

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
    async def rl_stats(self, ctx, user: Optional[discord.User] = None):
        """Show statistics for the Reinforcement Learning system.

        Usage: !rl_stats - Show global stats
               !rl_stats @user - Show stats for specific user
        """
        service = self.rl_service

        if not service:
            await ctx.send("❌ RL Service is not initialized.")
            return

        # Calculate stats
        agent_count = len(service.agents)
        is_enabled = service.enabled

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

        # Show specific user stats if requested
        if user:
            ctx_key = (ctx.channel.id, user.id)
            agent = service.agents.get(ctx_key)
            if agent:
                # Calculate Q-table stats
                total_states = len(agent.q_table)
                avg_q = 0.0
                if total_states > 0:
                    all_qs = [q for row in agent.q_table.values() for q in row.values()]
                    avg_q = sum(all_qs) / len(all_qs) if all_qs else 0.0

                # Find best learned state (highest Q-value)
                best_state = None
                best_q = float("-inf")
                for state, q_row in agent.q_table.items():
                    max_q = max(q_row.values())
                    if max_q > best_q:
                        best_q = max_q
                        best_state = state

                embed.add_field(
                    name=f"User: {user.display_name}",
                    value=(
                        f"Epsilon: {agent.epsilon:.4f}\n"
                        f"States Learned: {total_states}\n"
                        f"Avg Q-Value: {avg_q:.2f}\n"
                        f"Best Q: {best_q:.2f} (state {best_state})"
                    ),
                    inline=False,
                )

                # Show top 3 learned states
                if agent.q_table:
                    top_states = sorted(
                        agent.q_table.items(),
                        key=lambda x: max(x[1].values()),
                        reverse=True,
                    )[:3]

                    state_info = []
                    for state, q_row in top_states:
                        best_action = max(q_row.items(), key=lambda x: x[1])
                        state_info.append(
                            f"{state}: {best_action[0].name}={best_action[1]:.1f}"
                        )

                    embed.add_field(
                        name="Top Learned States",
                        value="\n".join(state_info)
                        if state_info
                        else "No learning yet",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=f"User: {user.display_name}",
                    value="No RL data for this user in this channel",
                    inline=False,
                )
        else:
            # Global stats
            avg_epsilon = 0.0
            total_states = 0
            if agent_count > 0:
                avg_epsilon = (
                    sum(a.epsilon for a in service.agents.values()) / agent_count
                )
                total_states = sum(len(a.q_table) for a in service.agents.values())

            embed.add_field(
                name="Average Epsilon", value=f"{avg_epsilon:.4f}", inline=True
            )
            embed.add_field(name="Total States", value=str(total_states), inline=True)

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
