"""Interactive Help Cog with Dropdown Navigation."""
import discord
from discord import app_commands
from discord.ext import commands
import logging


logger = logging.getLogger(__name__)

class HelpSelect(discord.ui.Select):
    """Dropdown menu for help categories."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="General", description="Basic bot commands", emoji="🤖"),
            discord.SelectOption(label="Music", description="Music playback commands", emoji="🎵"),
            discord.SelectOption(label="Voice & TTS", description="Voice and Text-to-Speech", emoji="🗣️"),
            discord.SelectOption(label="Games & Fun", description="Trivia, Would You Rather, etc.", emoji="🎮"),
            discord.SelectOption(label="Utility", description="Reminders, Search, Notes", emoji="🛠️"),
            discord.SelectOption(label="System", description="Bot status and settings", emoji="⚙️"),
        ]
        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        category = self.values[0]
        embed = discord.Embed(title=f"📚 Help: {category}", color=discord.Color.blue())
        
        if category == "General":
            embed.description = (
                "**Basic Commands**\n"
                "`/help` - Show this menu\n"
                "`/chat` - Chat with the AI\n"
                "`/clear` - Clear chat history"
            )
        elif category == "Music":
            embed.description = (
                "**Music Commands**\n"
                "`/play <query>` - Play a song from YouTube\n"
                "`/skip` - Skip current song\n"
                "`/stop` - Stop playback and clear queue\n"
                "`/queue` - Show current queue\n"
                "`/volume <0-100>` - Set volume"
            )
        elif category == "Voice & TTS":
            embed.description = (
                "**Voice Commands**\n"
                "`/join` - Join your voice channel\n"
                "`/leave` - Leave voice channel\n"
                "`/tts <text>` - Speak text in voice channel\n"
                "`/voice_settings` - Configure TTS voice"
            )
        elif category == "Games & Fun":
            embed.description = (
                "**Interactive Games**\n"
                "`/game_help <image>` - Get AI advice for a game screenshot\n"
                "`/wouldyourather` - Play 'Would You Rather'\n"
                "`/trivia_start` - Start a trivia game\n"
                "`/trivia_stats` - View your trivia stats"
            )
        elif category == "Utility":
            embed.description = (
                "**Useful Tools**\n"
                "`/remind <time> <message>` - Set a reminder\n"
                "`/search <query>` - Search the web\n"
                "`/note_add <content>` - Save a note\n"
                "`/note_list` - View your notes"
            )
        elif category == "System":
            embed.description = (
                "**System Commands**\n"
                "`/botstatus` - View system health\n"
                "`/metrics` - View performance metrics\n"
                "`/logs` - View recent logs (Admin only)"
            )
            
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    """View containing the help dropdown."""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(bot))

class HelpCog(commands.Cog):
    """Cog for the interactive help system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Remove default help command to use our own
        self.bot.remove_command('help')

    @app_commands.command(name="help", description="Show interactive help menu")
    async def help_command(self, interaction: discord.Interaction):
        """Show the interactive help menu."""
        embed = discord.Embed(
            title="🤖 Bot Help Center",
            description="Select a category below to see available commands.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Use the dropdown menu to navigate")
        
        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(HelpCog(bot))
