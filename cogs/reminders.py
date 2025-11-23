"""Reminders cog for setting time-based reminders."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime

from config import Config
from services.reminders import RemindersService, TimeParser
from utils.helpers import format_error, format_success

logger = logging.getLogger(__name__)


class RemindersCog(commands.Cog):
    """Cog for reminder commands."""

    def __init__(self, bot: commands.Bot, reminders_service: RemindersService):
        """Initialize reminders cog.

        Args:
            bot: Discord bot instance
            reminders_service: Reminders service instance
        """
        self.bot = bot
        self.reminders = reminders_service

    @app_commands.command(name="remind", description="Set a reminder")
    @app_commands.describe(
        reminder="What to remind you about and when (e.g., 'in 30 minutes to check the oven')"
    )
    async def remind(self, interaction: discord.Interaction, reminder: str):
        """Set a reminder.

        Args:
            interaction: Discord interaction
            reminder: Reminder text with time
        """
        try:
            # Parse the time from the reminder text
            trigger_time = TimeParser.parse(reminder)

            if not trigger_time:
                await interaction.response.send_message(
                    "❌ I couldn't understand the time. Try:\n"
                    "• `in 30 minutes to check the oven`\n"
                    "• `in 2 hours to call mom`\n"
                    "• `at 5pm to start cooking`\n"
                    "• `tomorrow at 9am to submit report`",
                    ephemeral=True
                )
                return

            # Extract the message part
            message = TimeParser.extract_message(reminder)

            # Add the reminder
            reminder_id = await self.reminders.add_reminder(
                user_id=interaction.user.id,
                channel_id=interaction.channel_id,
                message=message,
                trigger_time=trigger_time
            )

            if not reminder_id:
                max_reminders = Config.MAX_REMINDERS_PER_USER
                await interaction.response.send_message(
                    f"❌ You've reached the maximum of {max_reminders} reminders. "
                    f"Use `/reminders` to see them or `/cancel_reminder` to remove some.",
                    ephemeral=True
                )
                return

            # Format the time nicely
            time_until = self.reminders.format_time_until(trigger_time)
            time_str = trigger_time.strftime("%I:%M %p on %B %d")

            embed = discord.Embed(
                title="✅ Reminder Set!",
                description=f"**{message}**",
                color=discord.Color.green()
            )
            embed.add_field(name="When", value=f"{time_str}\n(in {time_until})", inline=False)
            embed.set_footer(text=f"ID: {reminder_id}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"User {interaction.user.id} set reminder: {message} for {trigger_time}")

        except Exception as e:
            logger.error(f"Remind command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="reminders", description="List your active reminders")
    async def list_reminders(self, interaction: discord.Interaction):
        """List all reminders for the user.

        Args:
            interaction: Discord interaction
        """
        try:
            user_reminders = self.reminders.get_user_reminders(interaction.user.id)

            if not user_reminders:
                await interaction.response.send_message(
                    "📭 You don't have any active reminders.\n"
                    "Use `/remind` to set one!",
                    ephemeral=True
                )
                return

            # Sort by trigger time
            user_reminders.sort(key=lambda r: r['trigger_time'])

            embed = discord.Embed(
                title=f"⏰ Your Reminders ({len(user_reminders)})",
                color=discord.Color.blue()
            )

            for reminder in user_reminders[:10]:  # Show max 10
                time_until = self.reminders.format_time_until(reminder['trigger_time'])
                time_str = reminder['trigger_time'].strftime("%I:%M %p, %b %d")

                embed.add_field(
                    name=f"`{reminder['id']}` - in {time_until}",
                    value=f"{reminder['message']}\n*{time_str}*",
                    inline=False
                )

            if len(user_reminders) > 10:
                embed.set_footer(text=f"Showing 10 of {len(user_reminders)} reminders")
            else:
                embed.set_footer(text="Use /cancel_reminder <id> to cancel")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List reminders failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="cancel_reminder", description="Cancel a reminder")
    @app_commands.describe(reminder_id="The reminder ID to cancel (from /reminders)")
    async def cancel_reminder(self, interaction: discord.Interaction, reminder_id: str):
        """Cancel a reminder.

        Args:
            interaction: Discord interaction
            reminder_id: ID of the reminder to cancel
        """
        try:
            success = self.reminders.cancel_reminder(reminder_id, interaction.user.id)

            if success:
                await interaction.response.send_message(
                    format_success(f"Reminder `{reminder_id}` cancelled!"),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Reminder `{reminder_id}` not found or doesn't belong to you.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Cancel reminder failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="clear_reminders", description="Clear all your reminders")
    async def clear_reminders(self, interaction: discord.Interaction):
        """Clear all reminders for the user.

        Args:
            interaction: Discord interaction
        """
        try:
            user_reminders = self.reminders.get_user_reminders(interaction.user.id)

            if not user_reminders:
                await interaction.response.send_message(
                    "📭 You don't have any reminders to clear.",
                    ephemeral=True
                )
                return

            # Cancel all
            count = 0
            for reminder in user_reminders:
                if self.reminders.cancel_reminder(reminder['id'], interaction.user.id):
                    count += 1

            await interaction.response.send_message(
                format_success(f"Cleared {count} reminder{'s' if count != 1 else ''}!"),
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Clear reminders failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
