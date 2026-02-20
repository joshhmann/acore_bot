"""Memory and history management commands."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import aiofiles
from datetime import datetime

from config import Config
from utils.helpers import format_error, format_success

logger = logging.getLogger(__name__)


class MemoryCommandsCog(commands.Cog):
    """Commands for managing conversation history and memory."""

    def __init__(self, bot, history, summarizer, rag):
        """Initialize memory commands cog.

        Args:
            bot: Discord bot instance
            history: ChatHistoryManager instance
            summarizer: ConversationSummarizer instance
            rag: RAG service instance
        """
        self.bot = bot
        self.history = history
        self.summarizer = summarizer
        self.rag = rag

    @app_commands.command(name="export_chat", description="Export conversation history for this channel")
    async def export_chat(self, interaction: discord.Interaction):
        """Export conversation history for this channel.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True)

        try:
            history = await self.history.load_history(interaction.channel_id)
            if not history:
                await interaction.followup.send("❌ No conversation history found for this channel.", ephemeral=True)
                return

            # Create export file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_export_{interaction.channel_id}_{timestamp}.json"
            filepath = Config.TEMP_DIR / filename

            async with aiofiles.open(filepath, "w") as f:
                await f.write(json.dumps(history, indent=2))

            # Send file
            await interaction.followup.send(
                f"✅ Here is the conversation export for <#{interaction.channel_id}>:",
                file=discord.File(filepath, filename=filename),
                ephemeral=True
            )

            # Cleanup
            # filepath.unlink() # Keep for a bit or let memory manager handle it

        except Exception as e:
            logger.error(f"Export chat failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="import_chat", description="Import conversation history from a file")
    @app_commands.describe(file="The JSON file to import")
    async def import_chat(self, interaction: discord.Interaction, file: discord.Attachment):
        """Import conversation history from a JSON file.

        Args:
            interaction: Discord interaction
            file: JSON file attachment
        """
        await interaction.response.defer(ephemeral=True)

        try:
            if not file.filename.endswith('.json'):
                await interaction.followup.send("❌ Please upload a JSON file.", ephemeral=True)
                return

            # Read file content
            content = await file.read()
            try:
                history = json.loads(content)
            except json.JSONDecodeError:
                await interaction.followup.send("❌ Invalid JSON file.", ephemeral=True)
                return

            if not isinstance(history, list):
                await interaction.followup.send("❌ Invalid format: Root must be a list of messages.", ephemeral=True)
                return

            # Validate structure (simple check)
            if history and not all(isinstance(m, dict) and "role" in m and "content" in m for m in history):
                await interaction.followup.send("❌ Invalid format: Messages must have 'role' and 'content' fields.", ephemeral=True)
                return

            # Save to history
            await self.history.save_history(interaction.channel_id, history)

            await interaction.followup.send(
                f"✅ Successfully imported {len(history)} messages to <#{interaction.channel_id}>.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Import chat failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="summarize_now", description="Force a summary of the current conversation")
    @app_commands.checks.cooldown(1, 30.0)  # 1 use per 30 seconds (expensive operation)
    async def summarize_now(self, interaction: discord.Interaction):
        """Force a summary of the current conversation immediately.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.summarizer:
                await interaction.followup.send("❌ Summarization service is not enabled.", ephemeral=True)
                return

            history = await self.history.load_history(interaction.channel_id)
            if not history:
                await interaction.followup.send("❌ No history to summarize.", ephemeral=True)
                return

            # Trigger summarization
            summary_data = await self.summarizer.summarize_and_store(
                messages=history,
                channel_id=interaction.channel_id,
                participants=[interaction.user.name], # Simple single user assumption for now
                store_in_rag=True,
                store_in_file=True
            )

            if summary_data:
                await interaction.followup.send(
                    f"✅ Conversation summarized and stored in memory!\n\n**Summary:**\n{summary_data['summary']}"
                )
            else:
                await interaction.followup.send("❌ Failed to generate summary (possibly too short).")

        except Exception as e:
            logger.error(f"Summarize now failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="recall", description="Search past conversation summaries")
    @app_commands.describe(query="What to search for")
    async def recall(self, interaction: discord.Interaction, query: str):
        """Search past conversation summaries.

        Args:
            interaction: Discord interaction
            query: Search query
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.summarizer:
                await interaction.followup.send(
                    "❌ Conversation summarization is not enabled.",
                    ephemeral=True
                )
                return

            memories = await self.summarizer.retrieve_relevant_memories(query, max_results=3)

            if not memories:
                await interaction.followup.send(
                    f"❌ No relevant memories found for: **{query}**",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🧠 Memory Recall: {query}",
                color=discord.Color.gold()
            )

            for i, memory in enumerate(memories):
                # Extract summary part if possible to make it cleaner
                content = memory
                if "SUMMARY:" in memory:
                    parts = memory.split("SUMMARY:")
                    if len(parts) > 1:
                        content = parts[1].split("[Stored:")[0].strip()

                # Truncate if too long
                if len(content) > 1000:
                    content = content[:997] + "..."

                embed.add_field(
                    name=f"Memory {i+1}",
                    value=content,
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Recall command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="rag_reload", description="Reload RAG documents from disk")
    @app_commands.checks.cooldown(1, 60.0)  # 1 use per minute (expensive)
    async def rag_reload(self, interaction: discord.Interaction):
        """Reload RAG documents from disk.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.rag:
                await interaction.followup.send("❌ RAG service is not enabled.", ephemeral=True)
                return

            await self.rag.reload()

            doc_count = len(self.rag.documents)
            await interaction.followup.send(f"✅ RAG documents reloaded! Total documents: {doc_count}")

        except Exception as e:
            logger.error(f"RAG reload failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="clear_history", description="Clear conversation history for this channel")
    async def clear_history(self, interaction: discord.Interaction):
        """Clear chat history for the current channel.

        Args:
            interaction: Discord interaction
        """
        try:
            channel_id = interaction.channel_id
            await self.history.clear_history(channel_id)
            await interaction.response.send_message(
                format_success("Conversation history cleared!"), ephemeral=True
            )
        except Exception as e:
            logger.error(f"Clear history failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    # Get required services from bot
    chat_cog = bot.get_cog("ChatCog")
    if chat_cog:
        await bot.add_cog(MemoryCommandsCog(
            bot,
            chat_cog.history,
            chat_cog.summarizer,
            chat_cog.rag
        ))
        logger.info("Loaded MemoryCommandsCog")
    else:
        logger.error("ChatCog not found, cannot load MemoryCommandsCog")
