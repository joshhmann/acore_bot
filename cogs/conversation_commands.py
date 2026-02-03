"""Bot-to-bot conversation commands for Discord."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

from config import Config
from services.conversation.orchestrator import (
    BotConversationOrchestrator,
    ConversationConfig,
)
from services.conversation.review import ConversationReviewService
from utils.helpers import format_error

logger = logging.getLogger(__name__)


class ConversationCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.orchestrator: Optional[BotConversationOrchestrator] = None
        self.review_service: Optional[ConversationReviewService] = None
        logger.info("Conversation commands cog initialized")

    async def cog_load(self):
        from services.core.factory import ServiceFactory

        if hasattr(self.bot, "service_factory"):
            factory: ServiceFactory = self.bot.service_factory
            self.orchestrator = factory.services.get("conversation_orchestrator")

            review_channel_id = getattr(
                Config, "BOT_CONVERSATION_REVIEW_CHANNEL_ID", None
            )
            self.review_service = ConversationReviewService(review_channel_id)

            if self.orchestrator:
                logger.info("Conversation orchestrator loaded successfully")
            else:
                logger.warning("Conversation orchestrator not available")

    @app_commands.command(
        name="bot_conversation",
        description="Start a conversation between two AI personas",
    )
    @app_commands.describe(
        initiator="Persona to start the conversation (e.g. dagoth_ur)",
        target="Persona to respond (e.g. scav)",
        topic="What should they discuss?",
        max_turns="Maximum number of turns (default: 10)",
        enable_tools="Allow personas to use tools (default: false)",
    )
    async def bot_conversation(
        self,
        interaction: discord.Interaction,
        initiator: str,
        target: str,
        topic: str,
        max_turns: int = 10,
        enable_tools: bool = False,
    ):
        await interaction.response.defer(ephemeral=False)

        if not self.orchestrator:
            await interaction.followup.send(
                "❌ Bot conversation system not available. Check that persona system is enabled.",
                ephemeral=True,
            )
            return

        if not Config.BOT_CONVERSATION_ENABLED:
            await interaction.followup.send(
                "❌ Bot conversations are disabled in config.", ephemeral=True
            )
            return

        try:
            participants = [initiator, target]

            config = ConversationConfig(
                max_turns=max_turns,
                turn_timeout_seconds=60,
                enable_tools=enable_tools,
                enable_metrics=True,
            )

            conversation_id = await self.orchestrator.start_conversation(
                participants=participants,
                topic=topic,
                channel=interaction.channel,
                config=config,
            )

            embed = discord.Embed(
                title="🤖 Bot Conversation Started",
                description=f"**Participants:** {initiator} ↔️ {target}\n**Topic:** {topic}",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="Settings",
                value=f"Max turns: {max_turns}\nTools: {'✅' if enable_tools else '❌'}",
                inline=False,
            )

            embed.set_footer(text=f"Conversation ID: {conversation_id}")

            await interaction.followup.send(embed=embed)

            if self.review_service:
                state = await self.orchestrator.get_conversation(conversation_id)
                if state:
                    await self._schedule_review_post(conversation_id)

        except Exception as e:
            logger.error(f"Failed to start bot conversation: {e}", exc_info=True)
            await interaction.followup.send(format_error(e), ephemeral=True)

    async def _schedule_review_post(self, conversation_id: str):
        import asyncio

        async def post_when_complete():
            while True:
                state = await self.orchestrator.get_conversation(conversation_id)

                if not state:
                    from services.conversation.state import ConversationStatus

                    persistence = getattr(self.orchestrator, "persistence", None)
                    if persistence:
                        state = await persistence.load(conversation_id)

                    if state and state.status == ConversationStatus.COMPLETED:
                        channel = self.bot.get_channel(state.metadata.get("channel_id"))
                        if channel and self.review_service:
                            await self.review_service.post_for_review(state, channel)
                        break
                    elif state and state.status == ConversationStatus.FAILED:
                        break

                await asyncio.sleep(5)

        asyncio.create_task(post_when_complete())

    @app_commands.command(
        name="review_conversation",
        description="View review ratings for a bot conversation",
    )
    @app_commands.describe(
        conversation_id="The conversation ID to review (from /bot_conversation)"
    )
    async def review_conversation(
        self, interaction: discord.Interaction, conversation_id: str
    ):
        await interaction.response.defer(ephemeral=True)

        if not self.review_service:
            await interaction.followup.send(
                "❌ Review service not available.", ephemeral=True
            )
            return

        try:
            summary = self.review_service.get_review_summary(conversation_id)

            embed = discord.Embed(
                title="📊 Conversation Review",
                description=summary,
                color=discord.Color.blue(),
            )

            embed.set_footer(text=f"Conversation ID: {conversation_id}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to get conversation review: {e}", exc_info=True)
            await interaction.followup.send(format_error(e), ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not self.review_service:
            return

        if payload.user_id == self.bot.user.id:
            return

        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return

            message = await channel.fetch_message(payload.message_id)

            if not message.embeds:
                return

            embed = message.embeds[0]
            footer_text = embed.footer.text if embed.footer else ""

            if not footer_text.startswith("Conversation ID:"):
                return

            conversation_id = footer_text.replace("Conversation ID:", "").strip()

            for reaction in message.reactions:
                if str(reaction.emoji) == str(payload.emoji):
                    count = reaction.count - 1
                    await self.review_service.update_reaction_count(
                        conversation_id, str(payload.emoji), count
                    )
                    break

        except Exception as e:
            logger.error(f"Failed to process reaction: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not self.review_service:
            return

        if payload.user_id == self.bot.user.id:
            return

        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return

            message = await channel.fetch_message(payload.message_id)

            if not message.embeds:
                return

            embed = message.embeds[0]
            footer_text = embed.footer.text if embed.footer else ""

            if not footer_text.startswith("Conversation ID:"):
                return

            conversation_id = footer_text.replace("Conversation ID:", "").strip()

            for reaction in message.reactions:
                if str(reaction.emoji) == str(payload.emoji):
                    count = reaction.count - 1
                    await self.review_service.update_reaction_count(
                        conversation_id, str(payload.emoji), count
                    )
                    break

        except Exception as e:
            logger.error(f"Failed to process reaction removal: {e}", exc_info=True)


async def setup(bot):
    await bot.add_cog(ConversationCommandsCog(bot))
    logger.info("Conversation commands cog loaded")
