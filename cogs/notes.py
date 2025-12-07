"""Notes cog for saving text notes."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime

from services.discord.notes import NotesService
from utils.helpers import format_error, format_success

logger = logging.getLogger(__name__)


class NotesCog(commands.Cog):
    """Cog for note commands."""

    def __init__(self, bot: commands.Bot, notes_service: NotesService):
        """Initialize notes cog.

        Args:
            bot: Discord bot instance
            notes_service: Notes service instance
        """
        self.bot = bot
        self.notes = notes_service

    @app_commands.command(name="note", description="Save a note")
    @app_commands.describe(
        content="The content of your note",
        category="Optional category (default: general)"
    )
    async def note(self, interaction: discord.Interaction, content: str, category: str = "general"):
        """Save a new note.

        Args:
            interaction: Discord interaction
            content: Note content
            category: Note category
        """
        try:
            note_id = await self.notes.add_note(
                user_id=interaction.user.id,
                content=content,
                category=category
            )

            if not note_id:
                await interaction.response.send_message(
                    "❌ You've reached the maximum number of notes (50). Delete some to add more.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📝 Note Saved",
                description=content,
                color=discord.Color.green()
            )
            embed.set_footer(text=f"ID: {note_id} | Category: {category}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Note command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="notes", description="List your notes")
    @app_commands.describe(category="Filter by category")
    async def list_notes(self, interaction: discord.Interaction, category: str = None):
        """List user notes.

        Args:
            interaction: Discord interaction
            category: Optional category filter
        """
        try:
            user_notes = self.notes.get_user_notes(interaction.user.id, category)

            if not user_notes:
                msg = "📭 You don't have any notes."
                if category:
                    msg = f"📭 You don't have any notes in category '{category}'."
                
                await interaction.response.send_message(msg, ephemeral=True)
                return

            # Sort by creation time (newest first)
            user_notes.sort(key=lambda n: n['created_at'], reverse=True)

            embed = discord.Embed(
                title="📝 Your Notes",
                color=discord.Color.blue()
            )
            
            if category:
                embed.title = f"📝 Your Notes ({category})"

            for note in user_notes[:10]:  # Show max 10
                date_str = note['created_at'].strftime("%b %d, %I:%M %p")
                
                # Truncate long content
                content = note['content']
                if len(content) > 100:
                    content = content[:97] + "..."

                embed.add_field(
                    name=f"`{note['id']}` - {date_str}",
                    value=f"{content}\n*Category: {note['category']}*",
                    inline=False
                )

            if len(user_notes) > 10:
                embed.set_footer(text=f"Showing 10 of {len(user_notes)} notes")
            else:
                embed.set_footer(text="Use /delnote <id> to delete")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List notes failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="delnote", description="Delete a note")
    @app_commands.describe(note_id="The ID of the note to delete")
    async def delete_note(self, interaction: discord.Interaction, note_id: str):
        """Delete a note.

        Args:
            interaction: Discord interaction
            note_id: Note ID
        """
        try:
            success = self.notes.delete_note(note_id, interaction.user.id)

            if success:
                await interaction.response.send_message(
                    format_success(f"Note `{note_id}` deleted!"),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Note `{note_id}` not found or doesn't belong to you.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Delete note failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="clearnotes", description="Clear all your notes")
    async def clear_notes(self, interaction: discord.Interaction):
        """Clear all notes.

        Args:
            interaction: Discord interaction
        """
        try:
            # Confirmation dialog could be added here, but keeping it simple for now
            count = self.notes.clear_user_notes(interaction.user.id)

            if count > 0:
                await interaction.response.send_message(
                    format_success(f"Cleared {count} note{'s' if count != 1 else ''}!"),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "📭 You don't have any notes to clear.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Clear notes failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)
