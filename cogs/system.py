"""System cog for bot status and metrics."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import platform
import psutil
import time
from datetime import datetime, timedelta

from config import Config
from utils.helpers import format_error

logger = logging.getLogger(__name__)


class SystemCog(commands.Cog):
    """Cog for system status and metrics."""

    def __init__(self, bot: commands.Bot):
        """Initialize system cog.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="botstatus", description="Check bot system status")
    async def botstatus(self, interaction: discord.Interaction):
        """Check bot system status.

        Args:
            interaction: Discord interaction
        """
        try:
            # Calculate uptime
            uptime_seconds = int(time.time() - self.start_time)
            uptime_str = str(timedelta(seconds=uptime_seconds))

            # System stats
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            # Bot stats
            guilds = len(self.bot.guilds)
            users = sum(g.member_count for g in self.bot.guilds)
            voice_connections = len(self.bot.voice_clients)
            latency = round(self.bot.latency * 1000)

            embed = discord.Embed(
                title="🤖 System Status",
                color=discord.Color.green()
            )
            
            embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
            embed.add_field(name="📶 Latency", value=f"{latency}ms", inline=True)
            embed.add_field(name="🏠 Guilds", value=str(guilds), inline=True)
            
            embed.add_field(name="👥 Users", value=str(users), inline=True)
            embed.add_field(name="🔊 Voice", value=f"{voice_connections} active", inline=True)
            embed.add_field(name="💻 CPU", value=f"{cpu_percent}%", inline=True)
            
            embed.add_field(name="🧠 Memory", value=f"{memory.percent}% ({round(memory.used / 1024 / 1024)}MB)", inline=True)
            embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
            embed.add_field(name="🤖 LLM", value=f"{Config.LLM_PROVIDER} ({Config.OLLAMA_MODEL if Config.LLM_PROVIDER == 'ollama' else Config.OPENROUTER_MODEL})", inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Status command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="metrics", description="View detailed performance metrics")
    async def metrics(self, interaction: discord.Interaction):
        """View detailed performance metrics.

        Args:
            interaction: Discord interaction
        """
        if not hasattr(self.bot, 'metrics'):
            await interaction.response.send_message("❌ Metrics service not available.", ephemeral=True)
            return

        try:
            summary = self.bot.metrics.get_summary()
            
            embed = discord.Embed(
                title="📊 Performance Metrics",
                color=discord.Color.blue()
            )

            # Response Times
            rt = summary['response_times']
            embed.add_field(
                name="⚡ Response Times",
                value=f"Avg: {rt['avg']:.0f}ms\nP95: {rt['p95']:.0f}ms\nMax: {rt['max']:.0f}ms",
                inline=True
            )

            # Token Usage
            tokens = summary['token_usage']
            embed.add_field(
                name="🪙 Token Usage",
                value=f"Total: {tokens['total_tokens']}\nPrompt: {tokens['prompt_tokens']}\nCompletion: {tokens['completion_tokens']}",
                inline=True
            )

            # Errors
            errors = summary['errors']
            error_rate = errors.get('error_rate', 0)
            embed.add_field(
                name="⚠️ Errors",
                value=f"Total: {errors['total_errors']}\nRate: {error_rate:.2f}%",
                inline=True
            )

            # Cache Stats
            cache = summary['cache_stats']
            hist_hit = cache['history_cache']['hit_rate']
            rag_hit = cache['rag_cache']['hit_rate']
            embed.add_field(
                name="💾 Cache Hits",
                value=f"History: {hist_hit:.1f}%\nRAG: {rag_hit:.1f}%",
                inline=True
            )

            # Activity
            active = summary['active_stats']
            embed.add_field(
                name="📈 Activity",
                value=f"Msgs: {active['messages_processed']}\nCmds: {active['commands_executed']}",
                inline=True
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Metrics command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="errors", description="View recent errors")
    async def errors(self, interaction: discord.Interaction):
        """View recent errors.

        Args:
            interaction: Discord interaction
        """
        if not hasattr(self.bot, 'metrics'):
            await interaction.response.send_message("❌ Metrics service not available.", ephemeral=True)
            return

        try:
            summary = self.bot.metrics.get_summary()
            recent_errors = summary['errors']['recent_errors']

            if not recent_errors:
                await interaction.response.send_message("✅ No recent errors recorded.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"⚠️ Recent Errors ({len(recent_errors)})",
                color=discord.Color.red()
            )

            for i, error in enumerate(reversed(recent_errors[-5:])):  # Show last 5
                timestamp = datetime.fromisoformat(error['timestamp']).strftime("%H:%M:%S")
                embed.add_field(
                    name=f"{timestamp} - {error['type']}",
                    value=f"```\n{error['message']}\n```",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Errors command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="logs", description="View recent log lines")
    @app_commands.describe(lines="Number of lines to view (max 50)")
    async def logs(self, interaction: discord.Interaction, lines: int = 20):
        """View recent log lines.

        Args:
            interaction: Discord interaction
            lines: Number of lines
        """
        # Only allow admin/owner to see logs (simple check for now)
        # In a real bot, you'd check permissions or IDs
        
        lines = min(lines, 50)  # Cap at 50

        try:
            log_file = Path(Config.LOG_FILE_PATH)
            if not log_file.exists():
                await interaction.response.send_message("❌ Log file not found.", ephemeral=True)
                return

            # Read last N lines
            # This is a simple implementation, for very large logs it might be slow but we rotate logs
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:]

            log_content = "".join(last_lines)
            
            # Split if too long for Discord (2000 chars)
            if len(log_content) > 1900:
                log_content = log_content[-1900:]
                log_content = "..." + log_content

            await interaction.response.send_message(f"```log\n{log_content}\n```", ephemeral=True)

        except Exception as e:
            logger.error(f"Logs command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(SystemCog(bot))
