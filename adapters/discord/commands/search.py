"""Web search and query commands."""
import discord
from discord import app_commands
from discord.ext import commands
import logging

from utils.helpers import chunk_message, format_error

logger = logging.getLogger(__name__)


class SearchCommandsCog(commands.Cog):
    """Commands for web search and one-off queries."""

    def __init__(self, bot, ollama, web_search, system_prompt):
        """Initialize search commands cog.

        Args:
            bot: Discord bot instance
            ollama: OllamaService instance
            web_search: WebSearch service instance
            system_prompt: System prompt string
        """
        self.bot = bot
        self.ollama = ollama
        self.web_search = web_search
        self.system_prompt = system_prompt

    @app_commands.command(name="ask", description="Ask the AI a question (no history)")
    @app_commands.describe(question="Your question")
    @app_commands.checks.cooldown(1, 3.0)  # 1 use per 3 seconds per user
    async def ask(self, interaction: discord.Interaction, question: str):
        """Ask a one-off question without using conversation history.

        Args:
            interaction: Discord interaction
            question: User's question
        """
        # Input validation
        if len(question) > 2000:
            await interaction.response.send_message(
                "❌ Question too long! Please keep questions under 2000 characters.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            # Get system prompt from ChatCog if it changed
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                system_prompt = chat_cog.system_prompt
            else:
                system_prompt = self.system_prompt

            response = await self.ollama.generate(question, system_prompt=system_prompt)

            # Send response
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)

        except Exception as e:
            logger.error(f"Ask command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="search", description="Search the web for current information")
    @app_commands.describe(query="What to search for")
    @app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user (web searches are expensive)
    async def search(self, interaction: discord.Interaction, query: str):
        """Search the web and get an AI response based on current information.

        Args:
            interaction: Discord interaction
            query: Search query
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.web_search:
                await interaction.followup.send("❌ Web search is not enabled on this bot.", ephemeral=True)
                return

            # Perform web search
            search_context = await self.web_search.get_context(query, max_length=1000)

            if not search_context:
                await interaction.followup.send(f"❌ No search results found for: **{query}**")
                return

            # Build prompt with search results
            prompt = f"[IMPORTANT - REAL-TIME WEB SEARCH RESULTS - USE THIS CURRENT INFORMATION TO ANSWER THE QUESTION]\n{search_context}\n[END WEB SEARCH RESULTS - Base your response on these actual current facts]\n\nUser question: {query}"

            # Get system prompt from ChatCog if it changed
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                system_prompt = chat_cog.system_prompt
            else:
                system_prompt = self.system_prompt

            # Get AI response
            response = await self.ollama.generate(prompt, system_prompt=system_prompt)

            # Send response
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(f"🔍 **Search results for:** {query}\n\n{chunk}")
                else:
                    await interaction.channel.send(chunk)

        except Exception as e:
            logger.error(f"Search command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="search_stats", description="View query optimization statistics")
    async def search_stats(self, interaction: discord.Interaction):
        """Show statistics about query optimization and search success rates.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.web_search or not self.web_search.optimizer:
                await interaction.response.send_message(
                    "❌ Query optimization is not enabled.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)

            # Get stats from optimizer
            stats = await self.web_search.optimizer.get_stats()

            # Create embed
            embed = discord.Embed(
                title="🧠 Query Optimization Stats",
                description="Statistics about web search query optimization and learning",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="📊 Overview",
                value=f"**Total Queries:** {stats['total_queries']}\n"
                      f"**Successful:** {stats['successful_queries']}\n"
                      f"**Success Rate:** {stats['success_rate']*100:.1f}%",
                inline=False
            )

            embed.add_field(
                name="🎯 Optimization Methods",
                value=f"**Pattern Matches:** {stats['pattern_matches']}\n"
                      f"**Learned Transformations:** {stats['learned_matches']}\n"
                      f"**Fallback Used:** {stats['fallback_used']}",
                inline=False
            )

            embed.set_footer(text="The bot learns from successful searches to improve future queries")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Search stats command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    # Get required services from ChatCog
    chat_cog = bot.get_cog("ChatCog")
    if chat_cog:
        await bot.add_cog(SearchCommandsCog(
            bot,
            chat_cog.ollama,
            chat_cog.web_search,
            chat_cog.system_prompt
        ))
        logger.info("Loaded SearchCommandsCog")
    else:
        logger.error("ChatCog not found, cannot load SearchCommandsCog")
