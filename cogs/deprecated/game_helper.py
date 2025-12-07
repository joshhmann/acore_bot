"""Game Helper cog for analyzing game screenshots and providing advice."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import aiohttp
import base64

from config import Config
from services.ollama import OllamaService
from services.openrouter import OpenRouterService
from services.web_search import WebSearchService
from utils.helpers import format_error, format_success

logger = logging.getLogger(__name__)

class GameHelperCog(commands.Cog):
    """Cog for game assistance using vision and search."""

    def __init__(self, bot: commands.Bot, web_search: WebSearchService):
        self.bot = bot
        self.web_search = web_search

    def _get_llm_service(self):
        """Get the active LLM service (Ollama or OpenRouter)."""
        if Config.LLM_PROVIDER == "openrouter":
            return self.bot.openrouter
        return self.bot.ollama

    async def _download_image(self, url: str) -> str:
        """Download image and convert to base64."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception("Failed to download image")
                data = await resp.read()
                return base64.b64encode(data).decode('utf-8')

    @app_commands.command(name="game_help", description="Get AI help for a game screenshot (meta, tier lists, mechanics)")
    @app_commands.describe(
        image="Screenshot of the game",
        question="What do you want to know? (e.g., 'Who should I pick?', 'What is the meta?')"
    )
    async def game_help(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        question: Optional[str] = "What should I do here? Give me advice based on the current meta."
    ):
        """Analyze a game screenshot and provide advice."""
        await interaction.response.defer()

        try:
            # 1. Validate image
            if not image.content_type.startswith('image/'):
                await interaction.followup.send(format_error("Please upload a valid image file."))
                return

            # 2. Download and encode image
            try:
                img_b64 = await self._download_image(image.url)
            except Exception as e:
                await interaction.followup.send(format_error(f"Failed to process image: {e}"))
                return

            # 3. Perform Web Search if needed (or always for meta/tier lists)
            search_context = ""
            if self.web_search and self.web_search.is_enabled():
                # Extract potential game name or keywords from the question
                # For now, we'll search for the question itself + "game meta tier list"
                # A more advanced approach would be to first ask Vision "What game is this?" then search.
                
                # Let's try a 2-step approach for better results:
                # Step A: Ask Vision to identify the game
                llm = self._get_llm_service()
                identify_prompt = "Identify the video game in this image. Return ONLY the game name."
                game_name = await llm.chat_with_vision(
                    prompt=identify_prompt,
                    images=[img_b64],
                    max_tokens=20
                )
                game_name = game_name.strip().split('\n')[0] # Clean up
                
                # Step B: Search for relevant info
                search_query = f"{game_name} {question} meta tier list guide"
                await interaction.followup.send(f"🔎 Identified game as **{game_name}**. Searching for info...", ephemeral=True)
                
                search_results = await self.web_search.get_context(search_query, max_length=1500)
                if search_results:
                    search_context = f"\n\nContext from Web Search:\n{search_results}"

            # 4. Analyze with Vision + Search Context
            system_prompt = (
                "You are an expert gaming assistant. Your goal is to help the user with their game.\n"
                "1. Analyze the provided screenshot carefully.\n"
                "2. Use the provided Web Search Context to inform your advice about the current meta, tier lists, or mechanics.\n"
                "3. Be specific, practical, and concise.\n"
                "4. If the user asks about a specific character or item, look for it in the image and the search results."
            )

            full_prompt = f"User Question: {question}\n{search_context}"

            llm = self._get_llm_service()
            response = await llm.chat_with_vision(
                prompt=full_prompt,
                images=[img_b64],
                system_prompt=system_prompt
            )

            # 5. Send Response
            embed = discord.Embed(
                title="🎮 Game Helper",
                description=response,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=image.url)
            if game_name:
                embed.set_footer(text=f"Game: {game_name} | Powered by {Config.LLM_PROVIDER}")
            
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Game help failed: {e}")
            await interaction.followup.send(format_error(f"An error occurred: {e}"))

async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # Ensure web_search service is available
    if not hasattr(bot, 'web_search'):
        logger.warning("WebSearchService not found on bot instance. Game Helper will work without search.")
        web_search = None
    else:
        web_search = bot.web_search
        
    await bot.add_cog(GameHelperCog(bot, web_search))
