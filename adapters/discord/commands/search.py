"""Runtime-backed Discord search and ask commands."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces import PlatformFacts, build_runtime_event_from_facts
from utils.helpers import chunk_message, format_error


logger = logging.getLogger(__name__)


class SearchCommandsCog(commands.Cog):
    """Runtime-only Discord search surfaces."""

    def __init__(
        self,
        bot: commands.Bot,
        web_search: Any,
        system_prompt: str,
        gestalt_runtime: Any | None = None,
    ) -> None:
        self.bot = bot
        self.web_search = web_search
        self.system_prompt = system_prompt
        self.gestalt_runtime = gestalt_runtime

    @staticmethod
    def _ids(interaction: discord.Interaction) -> tuple[str, str]:
        user_id = str(getattr(interaction.user, "id", "discord_user"))
        channel_id = str(
            getattr(interaction, "channel_id", getattr(interaction.channel, "id", "discord"))
        )
        return user_id, channel_id

    def _build_command_event(
        self,
        *,
        interaction: discord.Interaction,
        command: str,
        text: str,
        extra_metadata: dict[str, Any] | None = None,
    ):
        user_id, channel_id = self._ids(interaction)
        event = build_runtime_event_from_facts(
            facts=PlatformFacts(
                text=text,
                user_id=user_id,
                room_id=channel_id,
            ),
            platform_name="discord",
            kind="command",
            session_id=f"discord:{channel_id}:{user_id}",
        )
        event.metadata.update(
            {
                "command": command,
                "user_id": user_id,
                "channel_id": channel_id,
                "system_prompt": self.system_prompt,
            }
        )
        if extra_metadata:
            event.metadata.update(extra_metadata)
        return event

    @app_commands.command(name="ask", description="Ask the AI a question (no history)")
    @app_commands.describe(question="Your question")
    @app_commands.checks.cooldown(1, 3.0)
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        if len(question) > 2000:
            await interaction.response.send_message(
                "❌ Question too long! Please keep questions under 2000 characters.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        if self.gestalt_runtime is None:
            await interaction.followup.send(
                "❌ Runtime not available. Search requires Gestalt runtime."
            )
            return

        try:
            event = self._build_command_event(
                interaction=interaction,
                command="ask",
                text=question,
                extra_metadata={"question": question},
            )
            response = await self.gestalt_runtime.handle_event(event)
            chunks = await chunk_message(response.text)
            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)
        except Exception as exc:
            logger.error("Ask command failed: %s", exc)
            await interaction.followup.send(format_error(exc))

    @app_commands.command(
        name="search", description="Search the web for current information"
    )
    @app_commands.describe(query="What to search for")
    @app_commands.checks.cooldown(1, 5.0)
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(thinking=True)

        if self.gestalt_runtime is None:
            await interaction.followup.send(
                "❌ Runtime not available. Search requires Gestalt runtime."
            )
            return

        try:
            search_context = ""
            prompt = query
            if self.web_search:
                search_context = await self.web_search.get_context(query, max_length=1000)
                if not search_context:
                    await interaction.followup.send(
                        f"❌ No search results found for: **{query}**"
                    )
                    return

                prompt = (
                    "[IMPORTANT - REAL-TIME WEB SEARCH RESULTS - USE THIS CURRENT INFORMATION "
                    f"TO ANSWER THE QUESTION]\n{search_context}\n"
                    "[END WEB SEARCH RESULTS - Base your response on these actual current facts]\n\n"
                    f"User question: {query}"
                )

            event = self._build_command_event(
                interaction=interaction,
                command="search",
                text=prompt,
                extra_metadata={
                    "query": query,
                    "search_context": search_context,
                    "prompt": prompt,
                },
            )
            response = await self.gestalt_runtime.handle_event(event)
            chunks = await chunk_message(response.text)
            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    await interaction.followup.send(
                        f"🔍 **Search results for:** {query}\n\n{chunk}"
                    )
                else:
                    await interaction.channel.send(chunk)
        except Exception as exc:
            logger.error("Search command failed: %s", exc)
            await interaction.followup.send(format_error(exc))

    @app_commands.command(
        name="search_stats", description="View query optimization statistics"
    )
    async def search_stats(self, interaction: discord.Interaction) -> None:
        try:
            if not self.web_search or not getattr(self.web_search, "optimizer", None):
                await interaction.response.send_message(
                    "❌ Query optimization is not enabled.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)
            stats = await self.web_search.optimizer.get_stats()
            embed = discord.Embed(
                title="🧠 Query Optimization Stats",
                description="Statistics about web search query optimization and learning",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="📊 Overview",
                value=(
                    f"**Total Queries:** {stats['total_queries']}\n"
                    f"**Successful:** {stats['successful_queries']}\n"
                    f"**Success Rate:** {stats['success_rate'] * 100:.1f}%"
                ),
                inline=False,
            )
            embed.add_field(
                name="🎯 Optimization Methods",
                value=(
                    f"**Pattern Matches:** {stats['pattern_matches']}\n"
                    f"**Learned Transformations:** {stats['learned_matches']}\n"
                    f"**Fallback Used:** {stats['fallback_used']}"
                ),
                inline=False,
            )
            embed.set_footer(
                text="The bot learns from successful searches to improve future queries"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as exc:
            logger.error("Search stats command failed: %s", exc)
            await interaction.followup.send(format_error(exc), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    runtime_cog = bot.get_cog("RuntimeChatCog")
    runtime = getattr(runtime_cog, "gestalt_runtime", None)
    if runtime is None:
        chat_cog = bot.get_cog("ChatCog")
        runtime = getattr(chat_cog, "gestalt_runtime", None)
    if runtime is None:
        runtime = vars(bot).get("runtime")
    web_search = getattr(runtime_cog, "web_search", None)
    system_prompt = getattr(runtime_cog, "system_prompt", "")
    await bot.add_cog(
        SearchCommandsCog(
            bot=bot,
            web_search=web_search,
            system_prompt=system_prompt,
            gestalt_runtime=runtime,
        )
    )
