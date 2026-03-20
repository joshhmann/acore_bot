"""Runtime-backed Discord profile and status commands."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from core.interfaces import PlatformFacts, build_runtime_event_from_facts
from utils.helpers import format_error


logger = logging.getLogger(__name__)


class ProfileCommandsCog(commands.Cog):
    """Commands for viewing profile data and runtime status."""

    def __init__(
        self,
        bot: commands.Bot,
        user_profiles: Any,
        gestalt_runtime: Any | None = None,
    ) -> None:
        self.bot = bot
        self.user_profiles = user_profiles
        self.gestalt_runtime = gestalt_runtime

    @staticmethod
    def _interaction_ids(interaction: discord.Interaction) -> tuple[str, str, str]:
        user_id = str(getattr(interaction.user, "id", "discord_user"))
        channel_id = str(getattr(interaction, "channel_id", getattr(interaction.channel, "id", "discord")))
        guild_id = str(getattr(interaction, "guild_id", ""))
        return user_id, channel_id, guild_id

    @app_commands.command(
        name="my_profile", description="View your user profile and affection level"
    )
    async def my_profile(self, interaction: discord.Interaction) -> None:
        try:
            if not self.user_profiles:
                await interaction.response.send_message(
                    "❌ User profiles are not enabled on this bot.",
                    ephemeral=True,
                )
                return

            user_id = interaction.user.id
            profile = await self.user_profiles.load_profile(user_id)

            embed = discord.Embed(
                title=f"📊 Profile: {interaction.user.name}",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="📈 Stats",
                value=(
                    f"**Messages:** {profile.get('interaction_count', 0)}\n"
                    f"**First Met:** {profile.get('first_met', 'Unknown')[:10]}"
                ),
                inline=False,
            )

            if profile.get("traits"):
                embed.add_field(
                    name="🎭 Personality Traits",
                    value=", ".join(profile["traits"][:10]),
                    inline=False,
                )

            if profile.get("interests"):
                embed.add_field(
                    name="❤️ Interests",
                    value=", ".join(profile["interests"][:10]),
                    inline=False,
                )

            if profile.get("preferences"):
                prefs = "\n".join(
                    [
                        f"**{key}:** {value}"
                        for key, value in list(profile["preferences"].items())[:5]
                    ]
                )
                embed.add_field(
                    name="⚙️ Preferences",
                    value=prefs or "None yet",
                    inline=False,
                )

            if profile.get("affection") and Config.USER_AFFECTION_ENABLED:
                affection = profile["affection"]
                level = affection.get("level", 0)
                stage = affection.get("relationship_stage", "stranger")
                bar_length = 10
                filled = int((level / 100) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                embed.add_field(
                    name="💖 Relationship",
                    value=(
                        f"**Stage:** {stage.replace('_', ' ').title()}\n"
                        f"**Affection:** {bar} {level}/100\n"
                        f"**Positive:** {affection.get('positive_interactions', 0)} | "
                        f"**Negative:** {affection.get('negative_interactions', 0)}"
                    ),
                    inline=False,
                )

            if profile.get("memorable_quotes"):
                last_quote = profile["memorable_quotes"][-1]
                embed.add_field(
                    name="💬 Last Memorable Quote",
                    value=f"\"{last_quote['quote']}\"",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            logger.error("My profile failed: %s", exc)
            await interaction.response.send_message(format_error(exc), ephemeral=True)

    @app_commands.command(
        name="relationship", description="Check your relationship status with the bot"
    )
    async def relationship(self, interaction: discord.Interaction) -> None:
        try:
            if not self.user_profiles or not Config.USER_AFFECTION_ENABLED:
                await interaction.response.send_message(
                    "❌ Affection system is not enabled on this bot.",
                    ephemeral=True,
                )
                return

            user_id = interaction.user.id
            profile = await self.user_profiles.load_profile(user_id)
            affection = profile.get("affection", {})

            if not affection:
                await interaction.response.send_message(
                    "❌ No affection data found. Chat with the bot to build a relationship!",
                    ephemeral=True,
                )
                return

            level = affection.get("level", 0)
            stage = affection.get("relationship_stage", "stranger")
            bar_length = 20
            filled = int((level / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)

            embed = discord.Embed(
                title=f"💖 Relationship with {self.bot.user.name}",
                color=discord.Color.from_rgb(255, 105, 180),
            )
            embed.add_field(
                name="Affection Level",
                value=f"{bar}\n**{level}/100** - {stage.replace('_', ' ').title()}",
                inline=False,
            )
            embed.add_field(
                name="Interaction History",
                value=(
                    f"**Total Conversations:** {profile.get('interaction_count', 0)}\n"
                    f"**Positive Interactions:** {affection.get('positive_interactions', 0)}\n"
                    f"**Negative Interactions:** {affection.get('negative_interactions', 0)}"
                ),
                inline=False,
            )
            description = {
                "stranger": "We just met! Keep chatting to get to know each other better.",
                "acquaintance": "We're getting to know each other. I enjoy our conversations!",
                "friend": "We're friends! I look forward to talking with you.",
                "close_friend": "You're a close friend! I really enjoy our time together.",
                "best_friend": "You're my best friend! I genuinely care about you and love our conversations.",
            }.get(stage, "Unknown relationship stage.")
            embed.add_field(name="How I Feel", value=description, inline=False)

            if affection.get("last_interaction"):
                embed.set_footer(text=f"Last interaction: {affection['last_interaction'][:19]}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            logger.error("Relationship command failed: %s", exc)
            await interaction.response.send_message(format_error(exc), ephemeral=True)

    @app_commands.command(name="status", description="Check Gestalt runtime status")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        if self.gestalt_runtime is None:
            await interaction.followup.send(
                "❌ Runtime not available. Status requires Gestalt runtime.",
                ephemeral=True,
            )
            return

        user_id, channel_id, guild_id = self._interaction_ids(interaction)
        event = build_runtime_event_from_facts(
            facts=PlatformFacts(
                text="/status",
                user_id=user_id,
                room_id=channel_id,
            ),
            platform_name="discord",
            kind="command",
            session_id=f"discord:{channel_id}:{user_id}",
        )
        event.metadata.update(
            {
                "command": "status",
                "user_id": user_id,
                "channel_id": channel_id,
                "guild_id": guild_id,
            }
        )

        try:
            response = await self.gestalt_runtime.handle_event(event)
            await interaction.followup.send(response.text or "Status: OK", ephemeral=True)
        except Exception as exc:
            logger.error("Status command failed: %s", exc)
            await interaction.followup.send(format_error(exc), ephemeral=True)

    @app_commands.command(
        name="remember", description="Teach the bot a specific instruction about a user"
    )
    @app_commands.describe(
        user="The user the instruction is about",
        instruction="The instruction to remember",
    )
    async def remember(
        self, interaction: discord.Interaction, user: discord.Member, instruction: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.user_profiles:
                await interaction.followup.send(
                    "❌ User profiles are not enabled.", ephemeral=True
                )
                return

            success = await self.user_profiles.add_fact(
                user.id,
                f"When you see {user.name}: {instruction}",
            )
            if success:
                await interaction.followup.send(
                    f"✅ I will remember that about {user.name}.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to store that memory.", ephemeral=True
                )
        except Exception as exc:
            logger.error("Remember command failed: %s", exc)
            await interaction.followup.send(format_error(exc), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    runtime_cog = bot.get_cog("RuntimeChatCog") or bot.get_cog("ChatCog")
    runtime = getattr(runtime_cog, "gestalt_runtime", None)
    user_profiles = getattr(runtime_cog, "user_profiles", None)
    await bot.add_cog(
        ProfileCommandsCog(
            bot=bot,
            user_profiles=user_profiles,
            gestalt_runtime=runtime,
        )
    )
