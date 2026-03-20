"""Runtime-native Discord chat surface for the maintained startup path."""

from __future__ import annotations

import logging
import re
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces import PlatformFacts, build_runtime_event_from_facts


logger = logging.getLogger(__name__)

_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


class RuntimeChatCog(commands.Cog):
    """Thin Discord chat adapter over GestaltRuntime."""

    def __init__(self, bot: commands.Bot, runtime: Any) -> None:
        self.bot = bot
        self.gestalt_runtime = runtime
        self._responding_messages: set[int] = set()

    @staticmethod
    def _session_id(room_id: str, user_id: str) -> str:
        return f"discord:{room_id}:{user_id}"

    def _strip_bot_mention(self, content: str) -> str:
        user = getattr(self.bot, "user", None)
        if user is None:
            return content.strip()
        stripped = _MENTION_PATTERN.sub(
            lambda match: "" if match.group(1) == str(user.id) else match.group(0),
            content,
        )
        return stripped.strip()

    async def _run_runtime_chat(
        self,
        *,
        text: str,
        room_id: str,
        user_id: str,
        message_id: str = "",
        is_direct_mention: bool = False,
        interaction: discord.Interaction | None = None,
        channel: discord.abc.Messageable | None = None,
        reply_to: discord.Message | None = None,
    ) -> None:
        event = build_runtime_event_from_facts(
            facts=PlatformFacts(
                text=text,
                user_id=user_id,
                room_id=room_id,
                message_id=message_id,
                is_direct_mention=is_direct_mention,
            ),
            platform_name="discord",
            session_id=self._session_id(room_id, user_id),
        )
        response = await self.gestalt_runtime.handle_event(event)
        if not response.text.strip():
            return

        if interaction is not None:
            await interaction.followup.send(response.text)
            return

        if channel is not None:
            await channel.send(
                response.text,
                reference=reply_to,
                mention_author=False,
            )

    @app_commands.command(name="chat", description="Chat with Gestalt runtime")
    @app_commands.describe(message="Message to send to the runtime")
    async def chat(self, interaction: discord.Interaction, message: str) -> None:
        await interaction.response.defer(thinking=True)
        room_id = str(
            getattr(interaction.channel, "id", getattr(interaction, "channel_id", "discord"))
        )
        user_id = str(getattr(interaction.user, "id", "discord_user"))
        await self._run_runtime_chat(
            text=message.strip(),
            room_id=room_id,
            user_id=user_id,
            interaction=interaction,
            is_direct_mention=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        bot_user = getattr(self.bot, "user", None)
        if bot_user is None:
            return
        if message.author.id == bot_user.id:
            return
        if message.author.bot:
            return
        if message.is_system():
            return
        if not any(member.id == bot_user.id for member in message.mentions):
            return
        if message.content.startswith(str(getattr(self.bot, "command_prefix", "!"))):
            return
        if message.id in self._responding_messages:
            return

        cleaned = self._strip_bot_mention(message.content)
        if not cleaned:
            return

        self._responding_messages.add(message.id)
        try:
            async with message.channel.typing():
                await self._run_runtime_chat(
                    text=cleaned,
                    room_id=str(message.channel.id),
                    user_id=str(message.author.id),
                    message_id=str(message.id),
                    is_direct_mention=True,
                    channel=message.channel,
                    reply_to=message,
                )
        finally:
            self._responding_messages.discard(message.id)


async def setup(bot: commands.Bot) -> None:
    runtime = getattr(bot, "runtime", None)
    if runtime is None:
        raise RuntimeError("RuntimeChatCog requires bot.runtime")
    await bot.add_cog(RuntimeChatCog(bot, runtime))
