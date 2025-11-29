"""Custom intent management commands."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class IntentCommandsCog(commands.Cog):
    """Cog for managing custom intents and pattern learning."""

    def __init__(self, bot):
        """Initialize the cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot

    @app_commands.command(name="add_intent", description="Add a custom intent pattern")
    @app_commands.describe(
        name="Display name for the intent",
        pattern="Regex pattern to match (e.g., 'what are the rules')",
        response="Response template (optional if using AI generation)",
        global_intent="Make this intent available in all servers (admin only)"
    )
    async def add_intent(
        self,
        interaction: discord.Interaction,
        name: str,
        pattern: str,
        response: Optional[str] = None,
        global_intent: bool = False
    ):
        """Add a custom intent to recognize specific patterns."""
        try:
            # Check permissions for global intents
            if global_intent and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Only administrators can create global intents.",
                    ephemeral=True
                )
                return

            # Get custom intent manager from chat cog
            chat_cog = self.bot.get_cog("ChatCog")
            if not chat_cog or not hasattr(chat_cog, 'intent_service'):
                await interaction.response.send_message(
                    "❌ Intent recognition service not available.",
                    ephemeral=True
                )
                return

            custom_intents = chat_cog.intent_service.custom_intents
            if not custom_intents:
                await interaction.response.send_message(
                    "❌ Custom intents manager not initialized.",
                    ephemeral=True
                )
                return

            # Generate intent ID from name
            intent_id = name.lower().replace(" ", "_")

            # Server ID (None for global)
            server_id = None if global_intent else interaction.guild_id

            # Add the intent
            success = custom_intents.add_intent(
                server_id=server_id,
                intent_id=intent_id,
                name=name,
                patterns=[pattern],
                response_template=response,
                response_type="text"
            )

            if success:
                scope = "global" if global_intent else f"server {interaction.guild.name}"
                embed = discord.Embed(
                    title="✅ Custom Intent Added",
                    description=f"Successfully added intent to {scope}",
                    color=discord.Color.green()
                )
                embed.add_field(name="Intent Name", value=name, inline=False)
                embed.add_field(name="Pattern", value=f"`{pattern}`", inline=False)
                if response:
                    embed.add_field(name="Response", value=response[:200], inline=False)

                await interaction.response.send_message(embed=embed)
                logger.info(f"Added custom intent '{name}' for {scope} by {interaction.user}")
            else:
                await interaction.response.send_message(
                    f"❌ Intent '{name}' already exists.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error adding custom intent: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Failed to add intent: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="list_intents", description="List all custom intents")
    @app_commands.describe(
        show_global="Include global intents (default: True)"
    )
    async def list_intents(
        self,
        interaction: discord.Interaction,
        show_global: bool = True
    ):
        """List all custom intents available in this server."""
        try:
            # Get custom intent manager
            chat_cog = self.bot.get_cog("ChatCog")
            if not chat_cog or not hasattr(chat_cog, 'intent_service'):
                await interaction.response.send_message(
                    "❌ Intent recognition service not available.",
                    ephemeral=True
                )
                return

            custom_intents = chat_cog.intent_service.custom_intents
            if not custom_intents:
                await interaction.response.send_message(
                    "❌ Custom intents manager not initialized.",
                    ephemeral=True
                )
                return

            # Get intents
            intents = custom_intents.list_intents(interaction.guild_id)

            if not intents:
                await interaction.response.send_message(
                    "ℹ️ No custom intents configured for this server.",
                    ephemeral=True
                )
                return

            # Separate global and server intents
            global_intents = []
            server_intents = []

            for intent in intents:
                if intent.get('metadata', {}).get('global', False):
                    global_intents.append(intent)
                else:
                    server_intents.append(intent)

            # Create embed
            embed = discord.Embed(
                title="📋 Custom Intents",
                description=f"Configured intents for {interaction.guild.name}",
                color=discord.Color.blue()
            )

            # Add server intents
            if server_intents:
                server_text = "\n".join([
                    f"**{intent['name']}** (`{intent['intent_id']}`)\n"
                    f"  Pattern: `{intent['patterns'][0] if intent['patterns'] else 'None'}`\n"
                    f"  Used: {intent['usage_count']} times"
                    for intent in server_intents[:10]
                ])
                embed.add_field(
                    name=f"Server Intents ({len(server_intents)})",
                    value=server_text or "None",
                    inline=False
                )

            # Add global intents
            if show_global and global_intents:
                global_text = "\n".join([
                    f"**{intent['name']}** (`{intent['intent_id']}`)"
                    for intent in global_intents[:5]
                ])
                embed.add_field(
                    name=f"Global Intents ({len(global_intents)})",
                    value=global_text or "None",
                    inline=False
                )

            if len(server_intents) > 10:
                embed.set_footer(text=f"Showing 10 of {len(server_intents)} server intents")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error listing intents: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Failed to list intents: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="remove_intent", description="Remove a custom intent")
    @app_commands.describe(
        intent_id="ID of the intent to remove",
        global_intent="Remove from global intents (admin only)"
    )
    async def remove_intent(
        self,
        interaction: discord.Interaction,
        intent_id: str,
        global_intent: bool = False
    ):
        """Remove a custom intent."""
        try:
            # Check permissions for global intents
            if global_intent and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Only administrators can remove global intents.",
                    ephemeral=True
                )
                return

            # Get custom intent manager
            chat_cog = self.bot.get_cog("ChatCog")
            if not chat_cog or not hasattr(chat_cog, 'intent_service'):
                await interaction.response.send_message(
                    "❌ Intent recognition service not available.",
                    ephemeral=True
                )
                return

            custom_intents = chat_cog.intent_service.custom_intents
            if not custom_intents:
                await interaction.response.send_message(
                    "❌ Custom intents manager not initialized.",
                    ephemeral=True
                )
                return

            server_id = None if global_intent else interaction.guild_id
            success = custom_intents.remove_intent(server_id, intent_id)

            if success:
                scope = "global" if global_intent else "server"
                await interaction.response.send_message(
                    f"✅ Removed intent `{intent_id}` from {scope}."
                )
                logger.info(f"Removed custom intent '{intent_id}' from {scope} by {interaction.user}")
            else:
                await interaction.response.send_message(
                    f"❌ Intent `{intent_id}` not found.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error removing intent: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Failed to remove intent: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="intent_stats", description="View intent recognition statistics")
    async def intent_stats(self, interaction: discord.Interaction):
        """Display statistics about intent recognition and pattern learning."""
        try:
            # Get intent service
            chat_cog = self.bot.get_cog("ChatCog")
            if not chat_cog or not hasattr(chat_cog, 'intent_service'):
                await interaction.response.send_message(
                    "❌ Intent recognition service not available.",
                    ephemeral=True
                )
                return

            intent_service = chat_cog.intent_service
            stats = intent_service.get_stats()

            # Create embed
            embed = discord.Embed(
                title="📊 Intent Recognition Statistics",
                color=discord.Color.purple()
            )

            # Overall stats
            total_intents = stats.get('total_intents_detected', 0)
            embed.add_field(
                name="Total Intents Detected",
                value=f"**{total_intents:,}**",
                inline=True
            )

            # By type
            by_type = stats.get('by_type', {})
            if by_type:
                top_intents = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:5]
                type_text = "\n".join([
                    f"**{intent_type}**: {count:,}"
                    for intent_type, count in top_intents
                ])
                embed.add_field(
                    name="Top Intent Types",
                    value=type_text,
                    inline=False
                )

            # Pattern learning stats
            if 'pattern_learning' in stats:
                pl_stats = stats['pattern_learning']
                embed.add_field(
                    name="📚 Pattern Learning",
                    value=f"**Patterns Learned**: {pl_stats.get('total_patterns', 0)}\n"
                          f"**Intent Types**: {pl_stats.get('intent_types_learned', 0)}\n"
                          f"**User Corrections**: {pl_stats.get('user_corrections', 0)}",
                    inline=False
                )

                # Top performing
                if 'top_performing' in pl_stats:
                    top_perf = pl_stats['top_performing'][:3]
                    if top_perf:
                        perf_text = "\n".join([
                            f"**{intent}**: {rate:.1%} success"
                            for intent, rate in top_perf
                        ])
                        embed.add_field(
                            name="🏆 Top Performing",
                            value=perf_text,
                            inline=False
                        )

            # Custom intents stats
            if 'custom_intents' in stats:
                ci_stats = stats['custom_intents']
                embed.add_field(
                    name="🎯 Custom Intents",
                    value=f"**Global**: {ci_stats.get('global_intents', 0)}\n"
                          f"**Server-Specific**: {ci_stats.get('total_intents', 0) - ci_stats.get('global_intents', 0)}\n"
                          f"**Total Servers**: {ci_stats.get('total_servers', 0)}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error getting intent stats: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Failed to get statistics: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="pattern_suggestions", description="Get suggestions from pattern learner")
    async def pattern_suggestions(self, interaction: discord.Interaction):
        """Get improvement suggestions from the pattern learning system."""
        try:
            # Get intent service
            chat_cog = self.bot.get_cog("ChatCog")
            if not chat_cog or not hasattr(chat_cog, 'intent_service'):
                await interaction.response.send_message(
                    "❌ Intent recognition service not available.",
                    ephemeral=True
                )
                return

            learner = chat_cog.intent_service.learner
            if not learner:
                await interaction.response.send_message(
                    "❌ Pattern learner not available.",
                    ephemeral=True
                )
                return

            suggestions = learner.suggest_improvements()

            if not suggestions:
                await interaction.response.send_message(
                    "✅ System is performing well! No suggestions at this time.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="💡 Pattern Learning Suggestions",
                description="Recommendations to improve intent recognition",
                color=discord.Color.gold()
            )

            for i, suggestion in enumerate(suggestions[:5], 1):
                embed.add_field(
                    name=f"{i}. Suggestion",
                    value=suggestion,
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error getting suggestions: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Failed to get suggestions: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    """Set up the cog."""
    await bot.add_cog(IntentCommandsCog(bot))
    logger.info("Intent commands cog loaded")
