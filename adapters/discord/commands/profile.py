"""User profile and relationship management commands."""
import discord
from discord import app_commands
from discord.ext import commands
import logging

from config import Config
from utils.helpers import format_error

logger = logging.getLogger(__name__)


class ProfileCommandsCog(commands.Cog):
    """Commands for viewing and managing user profiles."""

    def __init__(self, bot, user_profiles, ollama):
        """Initialize profile commands cog.

        Args:
            bot: Discord bot instance
            user_profiles: UserProfiles service instance
            ollama: OllamaService instance
        """
        self.bot = bot
        self.user_profiles = user_profiles
        self.ollama = ollama

    @app_commands.command(name="my_profile", description="View your user profile and affection level")
    async def my_profile(self, interaction: discord.Interaction):
        """Show the user their profile information.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.user_profiles:
                await interaction.response.send_message(
                    "❌ User profiles are not enabled on this bot.",
                    ephemeral=True
                )
                return

            user_id = interaction.user.id
            profile = await self.user_profiles.load_profile(user_id)

            # Create embed
            embed = discord.Embed(
                title=f"📊 Profile: {interaction.user.name}",
                color=discord.Color.blue(),
            )

            # Basic stats
            embed.add_field(
                name="📈 Stats",
                value=f"**Messages:** {profile.get('interaction_count', 0)}\n"
                      f"**First Met:** {profile.get('first_met', 'Unknown')[:10]}",
                inline=False
            )

            # Traits
            if profile.get("traits"):
                traits_str = ", ".join(profile["traits"][:10])
                embed.add_field(
                    name="🎭 Personality Traits",
                    value=traits_str,
                    inline=False
                )

            # Interests
            if profile.get("interests"):
                interests_str = ", ".join(profile["interests"][:10])
                embed.add_field(
                    name="❤️ Interests",
                    value=interests_str,
                    inline=False
                )

            # Preferences
            if profile.get("preferences"):
                prefs_str = "\n".join([f"**{k}:** {v}" for k, v in list(profile["preferences"].items())[:5]])
                embed.add_field(
                    name="⚙️ Preferences",
                    value=prefs_str or "None yet",
                    inline=False
                )

            # Affection/Relationship
            if profile.get("affection") and Config.USER_AFFECTION_ENABLED:
                affection = profile["affection"]
                level = affection.get("level", 0)
                stage = affection.get("relationship_stage", "stranger")

                # Create affection bar
                bar_length = 10
                filled = int((level / 100) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)

                embed.add_field(
                    name="💖 Relationship",
                    value=f"**Stage:** {stage.replace('_', ' ').title()}\n"
                          f"**Affection:** {bar} {level}/100\n"
                          f"**Positive:** {affection.get('positive_interactions', 0)} | "
                          f"**Negative:** {affection.get('negative_interactions', 0)}",
                    inline=False
                )

            # Memorable quotes
            if profile.get("memorable_quotes"):
                last_quote = profile["memorable_quotes"][-1]
                embed.add_field(
                    name="💬 Last Memorable Quote",
                    value=f"\"{last_quote['quote']}\"",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"My profile failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="relationship", description="Check your relationship status with the bot")
    async def relationship(self, interaction: discord.Interaction):
        """Show detailed relationship/affection info.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.user_profiles or not Config.USER_AFFECTION_ENABLED:
                await interaction.response.send_message(
                    "❌ Affection system is not enabled on this bot.",
                    ephemeral=True
                )
                return

            user_id = interaction.user.id
            profile = await self.user_profiles.load_profile(user_id)
            affection = profile.get("affection", {})

            if not affection:
                await interaction.response.send_message(
                    "❌ No affection data found. Chat with the bot to build a relationship!",
                    ephemeral=True
                )
                return

            level = affection.get("level", 0)
            stage = affection.get("relationship_stage", "stranger")

            # Create embed
            embed = discord.Embed(
                title=f"💖 Relationship with {self.bot.user.name}",
                color=discord.Color.from_rgb(255, 105, 180),  # Pink
            )

            # Affection bar
            bar_length = 20
            filled = int((level / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)

            embed.add_field(
                name="Affection Level",
                value=f"{bar}\n**{level}/100** - {stage.replace('_', ' ').title()}",
                inline=False
            )

            # Interaction stats
            embed.add_field(
                name="Interaction History",
                value=f"**Total Conversations:** {profile.get('interaction_count', 0)}\n"
                      f"**Positive Interactions:** {affection.get('positive_interactions', 0)}\n"
                      f"**Negative Interactions:** {affection.get('negative_interactions', 0)}",
                inline=False
            )

            # Relationship description
            stage_descriptions = {
                "stranger": "We just met! Keep chatting to get to know each other better.",
                "acquaintance": "We're getting to know each other. I enjoy our conversations!",
                "friend": "We're friends! I look forward to talking with you.",
                "close_friend": "You're a close friend! I really enjoy our time together.",
                "best_friend": "You're my best friend! I genuinely care about you and love our conversations.",
            }

            description = stage_descriptions.get(stage, "Unknown relationship stage.")
            embed.add_field(
                name="How I Feel",
                value=description,
                inline=False
            )

            # Last interaction
            if affection.get("last_interaction"):
                last = affection["last_interaction"][:19]
                embed.set_footer(text=f"Last interaction: {last}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Relationship command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="status", description="Check AI status")
    async def status(self, interaction: discord.Interaction):
        """Check Ollama service status.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            healthy = await self.ollama.check_health()

            if healthy:
                embed = discord.Embed(
                    title="🟢 AI Status: Online",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Server", value=self.ollama.host)
                embed.add_field(name="Model", value=self.ollama.model)
                embed.add_field(name="Temperature", value=f"{self.ollama.temperature}")
            else:
                embed = discord.Embed(
                    title="🔴 AI Status: Offline",
                    description=f"Cannot connect to Ollama at {self.ollama.host}",
                    color=discord.Color.red(),
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Status command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="remember", description="Teach the bot a specific instruction about a user")
    @app_commands.describe(
        user="The user the instruction is about",
        instruction="The instruction to remember"
    )
    async def remember(self, interaction: discord.Interaction, user: discord.Member, instruction: str):
        """Teach the bot a specific instruction about a user.

        Args:
            interaction: Discord interaction
            user: The user the instruction is about
            instruction: The instruction to remember
        """
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.user_profiles:
                await interaction.followup.send("❌ User profiles are not enabled.", ephemeral=True)
                return

            # Add the instruction as a fact
            success = await self.user_profiles.add_fact(
                user.id,
                f"When you see {user.name}: {instruction}",
                source="manual_instruction"
            )

            if success:
                await interaction.followup.send(
                    f"✅ Remembered! I will now: **{instruction}** when I see {user.mention}",
                    ephemeral=True
                )
                logger.info(f"Added instruction for user {user.id}: {instruction}")
            else:
                await interaction.followup.send("❌ Failed to save instruction.", ephemeral=True)

        except Exception as e:
            logger.error(f"Remember command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    # Get required services from ChatCog
    chat_cog = bot.get_cog("ChatCog")
    if chat_cog:
        await bot.add_cog(ProfileCommandsCog(
            bot,
            chat_cog.user_profiles,
            chat_cog.ollama
        ))
        logger.info("Loaded ProfileCommandsCog")
    else:
        logger.error("ChatCog not found, cannot load ProfileCommandsCog")
