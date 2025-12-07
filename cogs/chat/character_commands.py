"""Character management commands."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import aiohttp
import io
from pathlib import Path

logger = logging.getLogger(__name__)

class CharacterCommands(commands.Cog):
    """Commands for managing characters and lorebooks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.chat_cog = None

    def _get_chat_cog(self):
        """Helper to get ChatCog instance."""
        if not self.chat_cog:
            self.chat_cog = self.bot.get_cog("ChatCog")
        return self.chat_cog

    @app_commands.command(name="character_list", description="List available characters")
    async def character_list(self, interaction: discord.Interaction):
        """List all available characters."""
        chat_cog = self._get_chat_cog()
        if not chat_cog or not chat_cog.persona_system:
            await interaction.response.send_message("❌ Persona system not available.", ephemeral=True)
            return

        characters = chat_cog.persona_system.list_available_characters()
        if not characters:
            await interaction.response.send_message("No characters found.", ephemeral=True)
            return

        msg = "**Available Characters:**\n"
        for char in characters:
            msg += f"• **{char['name']}** (`{char['id']}`)\n"

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="character_switch", description="Switch to a different character")
    @app_commands.describe(character_id="ID of the character to switch to")
    async def character_switch(self, interaction: discord.Interaction, character_id: str):
        """Switch the active character."""
        chat_cog = self._get_chat_cog()
        if not chat_cog or not chat_cog.persona_system:
            await interaction.response.send_message("❌ Persona system not available.", ephemeral=True)
            return

        await interaction.response.defer()

        # Try to load the character first to verify it exists
        character = chat_cog.persona_system.load_character(character_id)
        if not character:
            await interaction.followup.send(f"❌ Character `{character_id}` not found.", ephemeral=True)
            return

        # Compile persona (using default framework for now, or existing one if we track it)
        # For simplicity, we assume "neuro" or "default" framework
        framework_id = "neuro"

        persona = chat_cog.persona_system.compile_persona(character_id, framework_id)
        if not persona:
             await interaction.followup.send(f"❌ Failed to compile persona for `{character_id}`.", ephemeral=True)
             return

        # Update active persona in ChatCog
        chat_cog.compiled_persona = persona
        chat_cog.current_persona = None # disable legacy tracking

        # Clear history if configured (default behavior for clean switch)
        await chat_cog.history.clear_history(interaction.channel_id)

        # Send greeting
        greeting = character.first_message or f"*{character.display_name} enters the chat.*"

        # Save greeting to history so the bot remembers it said it
        await chat_cog.history.add_message(
            interaction.channel_id,
            "assistant",
            greeting
        )

        await interaction.followup.send(f"✅ Switched to **{character.display_name}**!\n\n{greeting}")

    @app_commands.command(name="character_import", description="Import a V2 Character Card (PNG or JSON)")
    @app_commands.describe(file="The character card file")
    async def character_import(self, interaction: discord.Interaction, file: discord.Attachment):
        """Import a character card."""
        chat_cog = self._get_chat_cog()
        if not chat_cog:
            await interaction.response.send_message("❌ Chat system not ready.", ephemeral=True)
            return

        if not (file.filename.endswith('.png') or file.filename.endswith('.json')):
             await interaction.response.send_message("❌ Please upload a PNG or JSON file.", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True)

        try:
            # Download file
            async with aiohttp.ClientSession() as session:
                async with session.get(file.url) as resp:
                    if resp.status != 200:
                        raise Exception("Failed to download file")
                    data = await resp.read()

            # Save to characters directory
            filename = file.filename
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in "._-").lower()

            save_path = chat_cog.persona_system.characters_dir / filename

            with open(save_path, 'wb') as f:
                f.write(data)

            # Try loading it to verify
            char_id = Path(filename).stem
            character = chat_cog.persona_system.load_character(char_id)

            if character:
                await interaction.followup.send(f"✅ Successfully imported **{character.display_name}** (`{char_id}`)")
            else:
                save_path.unlink() # Delete invalid file
                await interaction.followup.send("❌ Failed to parse character card. File deleted.")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            await interaction.followup.send(f"❌ Import failed: {str(e)}")

    @app_commands.command(name="lorebook_list", description="List available lorebooks")
    async def lorebook_list(self, interaction: discord.Interaction):
        """List available lorebooks."""
        chat_cog = self._get_chat_cog()
        if not chat_cog or not chat_cog.lorebook_service:
            await interaction.response.send_message("❌ Lorebook system not available.", ephemeral=True)
            return

        books = chat_cog.lorebook_service.get_available_lorebooks()
        if not books:
             await interaction.response.send_message("No lorebooks found.", ephemeral=True)
             return

        msg = "**Available Lorebooks:**\n" + "\n".join([f"• {b}" for b in books])
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CharacterCommands(bot))
