"""Runtime-backed Discord help command."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces import PlatformFacts, build_runtime_event_from_facts
from core.schemas import EventKind, ResponseEnvelope, StructuredOutput


logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    """Thin Discord help surface over the runtime command registry."""

    def __init__(self, bot: commands.Bot, runtime: Any | None = None) -> None:
        self.bot = bot
        self.gestalt_runtime = runtime
        self.bot.remove_command("help")

    def _runtime(self) -> Any | None:
        if self.gestalt_runtime is not None:
            return self.gestalt_runtime
        chat_cog = self.bot.get_cog("ChatCog")
        return getattr(chat_cog, "gestalt_runtime", None)

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

    @app_commands.command(name="help", description="Show runtime-available commands")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        runtime = self._runtime()
        if runtime is None:
            await interaction.followup.send(
                "❌ Runtime not available. Help requires Gestalt runtime.",
                ephemeral=True,
            )
            return

        event = build_runtime_event_from_facts(
            facts=PlatformFacts(
                text="/help",
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
        payload = self._command_output(envelope, "command_help")
        commands_data = list((payload.data if payload else {}).get("commands", []))

        embed = discord.Embed(title="Gestalt Commands", color=discord.Color.blue())
        if commands_data:
            rows = [
                f"`{item.get('usage', '')}` - {item.get('description', '')}".strip()
                for item in commands_data
            ]
            embed.add_field(name="Available", value="\n".join(rows[:20]), inline=False)
        else:
            embed.description = "No runtime commands are currently registered."

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    chat_cog = bot.get_cog("ChatCog")
    runtime = getattr(chat_cog, "gestalt_runtime", None)
    await bot.add_cog(HelpCog(bot, runtime=runtime))
