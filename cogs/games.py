"""Social games cog for Discord."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
import re
from typing import Optional

from config import Config
from services.ollama import OllamaService
from services.openrouter import OpenRouterService
from utils.helpers import format_error, format_success

logger = logging.getLogger(__name__)

class GamesCog(commands.Cog):
    """Cog for social games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_llm_service(self):
        """Get the active LLM service."""
        if Config.LLM_PROVIDER == "openrouter":
            return self.bot.openrouter
        return self.bot.ollama

    @app_commands.command(name="wouldyourather", description="Play 'Would You Rather' with AI-generated scenarios")
    @app_commands.describe(theme="Optional theme for the scenarios (e.g., 'horror', 'funny', 'philosophical')")
    async def would_you_rather(self, interaction: discord.Interaction, theme: Optional[str] = None):
        """Start a 'Would You Rather' game."""
        await interaction.response.defer()

        try:
            # Generate scenarios using LLM
            llm = self._get_llm_service()
            
            theme_prompt = f"Theme: {theme}" if theme else "Theme: General/Random"
            prompt = (
                f"Generate a 'Would You Rather' scenario. {theme_prompt}\n"
                "Provide two difficult, contrasting options.\n"
                "Format EXACTLY like this:\n"
                "Option A: [First option]\n"
                "Option B: [Second option]\n"
                "Do not include any other text."
            )

            response = await llm.generate(prompt)
            
            # Parse response
            option_a = "Option A"
            option_b = "Option B"
            
            # Simple parsing logic
            lines = response.strip().split('\n')
            for line in lines:
                if line.startswith("Option A:"):
                    option_a = line.replace("Option A:", "").strip()
                elif line.startswith("Option B:"):
                    option_b = line.replace("Option B:", "").strip()

            # Create Embed
            embed = discord.Embed(
                title="🤔 Would You Rather...",
                color=discord.Color.purple()
            )
            embed.add_field(name="🅰️ Option A", value=option_a, inline=False)
            embed.add_field(name="🅱️ Option B", value=option_b, inline=False)
            embed.set_footer(text=f"React to vote! | Powered by {Config.LLM_PROVIDER}")

            message = await interaction.followup.send(embed=embed)
            
            # Add reactions
            await message.add_reaction("🅰️")
            await message.add_reaction("🅱️")

            # Wait for votes (optional: reveal results after time)
            # For now, we just let users vote. 
            # A future enhancement could be to wait 30s and then show the winner.

        except Exception as e:
            logger.error(f"Would You Rather failed: {e}")
            await interaction.followup.send(format_error(f"Failed to generate scenario: {e}"))

async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(GamesCog(bot))
