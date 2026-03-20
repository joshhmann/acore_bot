"""Runtime-backed Discord system status command."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces import PlatformFacts, build_runtime_event_from_facts
from core.schemas import EventKind, ResponseEnvelope, StructuredOutput


logger = logging.getLogger(__name__)


class SystemCog(commands.Cog):
    """Thin Discord system surface over runtime status."""

    def __init__(self, bot: commands.Bot, runtime: Any | None = None) -> None:
        self.bot = bot
        self.gestalt_runtime = runtime

    def _runtime(self) -> Any | None:
        if self.gestalt_runtime is not None:
            return self.gestalt_runtime
        runtime_cog = self.bot.get_cog("RuntimeChatCog")
        if runtime_cog is not None:
            return getattr(runtime_cog, "gestalt_runtime", None)
        chat_cog = self.bot.get_cog("ChatCog")
        if chat_cog is not None:
            return getattr(chat_cog, "gestalt_runtime", None)
        return vars(self.bot).get("runtime")

    @staticmethod
    def _session_id(interaction: discord.Interaction) -> str:
        channel_id = getattr(interaction.channel, "id", getattr(interaction, "channel_id", "discord"))
        user_id = getattr(interaction.user, "id", "discord_user")
        return f"discord:{channel_id}:{user_id}"

    @staticmethod
    def _command_output(
        envelope: ResponseEnvelope, kind: str
    ) -> StructuredOutput | None:
        for output in envelope.outputs:
            if isinstance(output, StructuredOutput) and output.kind == kind:
                return output
        return None

    @app_commands.command(name="botstatus", description="Show runtime status")
    async def botstatus(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        runtime = self._runtime()
        if runtime is None:
            await interaction.followup.send(
                "❌ Runtime not available. System status requires Gestalt runtime.",
                ephemeral=True,
            )
            return

        event = build_runtime_event_from_facts(
            facts=PlatformFacts(
                text="/status",
                user_id=str(getattr(interaction.user, "id", "discord_user")),
                room_id=str(
                    getattr(interaction.channel, "id", getattr(interaction, "channel_id", "discord"))
                ),
            ),
            platform_name="discord",
            kind=EventKind.COMMAND.value,
            session_id=self._session_id(interaction),
        )

        envelope = await runtime.handle_event_envelope(event)
        payload = self._command_output(envelope, "command_status")
        status = payload.data if payload else {}

        embed = discord.Embed(title="🤖 Runtime Status", color=discord.Color.green())
        embed.add_field(name="Persona", value=str(status.get("persona", "default")), inline=True)
        embed.add_field(name="Mode", value=str(status.get("mode", "default")), inline=True)
        embed.add_field(name="Provider", value=str(status.get("provider", "unknown")), inline=True)
        embed.add_field(name="Model", value=str(status.get("model", "unknown")), inline=False)
        embed.add_field(
            name="Budget",
            value=str(status.get("budget_remaining", "unknown")),
            inline=True,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    runtime_cog = bot.get_cog("RuntimeChatCog")
    runtime = getattr(runtime_cog, "gestalt_runtime", None)
    if runtime is None:
        chat_cog = bot.get_cog("ChatCog")
        runtime = getattr(chat_cog, "gestalt_runtime", None)
    if runtime is None:
        runtime = vars(bot).get("runtime")
    await bot.add_cog(SystemCog(bot, runtime=runtime))
