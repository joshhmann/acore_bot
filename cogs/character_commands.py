"""Character management commands for AI-First PersonaSystem."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from pathlib import Path

from config import Config
from utils.helpers import format_error, format_success, format_info

logger = logging.getLogger(__name__)


class CharacterCommandsCog(commands.Cog):
    """Commands for managing character+framework personas."""

    def __init__(self, bot: commands.Bot):
        """Initialize character commands cog.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        logger.info("Character commands cog initialized")

    @app_commands.command(name="set_character", description="Change bot personality using character+framework system")
    @app_commands.describe(
        character="Character to use (dagoth_ur, gothmommy, chief, arbiter)",
        framework="Framework to apply (neuro, caring, chaotic, assistant)"
    )
    async def set_character(
        self,
        interaction: discord.Interaction,
        character: str,
        framework: Optional[str] = None
    ):
        """Change the bot's personality using character+framework system.

        Args:
            interaction: Discord interaction
            character: Character ID
            framework: Framework ID (optional, uses smart default)
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Get PersonaSystem from bot
            if not self.bot.persona_system:
                await interaction.followup.send(
                    "❌ PersonaSystem not initialized. Enable USE_PERSONA_SYSTEM in .env",
                    ephemeral=True
                )
                return

            # Auto-select framework based on character if not specified
            if not framework:
                framework_map = {
                    "dagoth_ur": "neuro",
                    "gothmommy": "caring",
                    "chief": "chaotic",
                    "arbiter": "assistant"
                }
                framework = framework_map.get(character, "neuro")
                logger.info(f"Auto-selected framework '{framework}' for character '{character}'")

            # Compile persona
            compiled_persona = self.bot.persona_system.compile_persona(
                character,
                framework,
                force_recompile=True
            )

            if not compiled_persona:
                # List available characters and frameworks
                chars_dir = Path("./prompts/characters")
                frameworks_dir = Path("./prompts/frameworks")

                available_chars = [f.stem for f in chars_dir.glob("*.json")] if chars_dir.exists() else []
                available_frameworks = [f.stem for f in frameworks_dir.glob("*.json")] if frameworks_dir.exists() else []

                await interaction.followup.send(
                    f"❌ Failed to compile persona '{character}_{framework}'.\n\n"
                    f"**Available characters:** {', '.join(available_chars) or 'None'}\n"
                    f"**Available frameworks:** {', '.join(available_frameworks) or 'None'}",
                    ephemeral=True
                )
                return

            # Update bot's current persona
            self.bot.current_persona = compiled_persona

            # Update decision engine
            if self.bot.decision_engine:
                self.bot.decision_engine.set_persona(compiled_persona)
                logger.info(f"Updated decision engine with new persona: {compiled_persona.persona_id}")

            # Update ChatCog
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                chat_cog.compiled_persona = compiled_persona
                chat_cog.system_prompt = compiled_persona.system_prompt
                logger.info(f"Updated ChatCog with new persona: {compiled_persona.persona_id}")

            # Update AmbientMode
            if self.bot.ambient_mode:
                self.bot.ambient_mode.compiled_persona = compiled_persona
                logger.info(f"Updated AmbientMode with new persona: {compiled_persona.persona_id}")

            # Update CuriositySystem
            if self.bot.curiosity_system:
                self.bot.curiosity_system.set_persona(compiled_persona)
                logger.info(f"Updated CuriositySystem with new persona: {compiled_persona.persona_id}")

            # Get legacy config for voice/RVC if available
            character_obj = compiled_persona.character
            legacy_config = None
            if hasattr(character_obj, 'legacy_config') and character_obj.legacy_config:
                # Access as dictionary
                import json
                char_dict = json.loads(json.dumps(character_obj, default=lambda o: o.__dict__))
                legacy_config = char_dict.get('legacy_config')

            # Apply voice settings if available
            voice_info = []
            voice_cog = self.bot.get_cog("VoiceCog")
            if voice_cog and voice_cog.tts and legacy_config and 'voice' in legacy_config:
                voice_settings = legacy_config['voice']
                if Config.TTS_ENGINE == "kokoro":
                    if 'kokoro_voice' in voice_settings:
                        voice_cog.tts.kokoro_voice = voice_settings['kokoro_voice']
                        voice_cog.tts.kokoro_speed = voice_settings.get('kokoro_speed', 1.0)
                        voice_info.append(f"🎤 Voice: {voice_settings['kokoro_voice']}")
                else:  # Edge TTS
                    if 'edge_voice' in voice_settings:
                        voice_cog.tts.default_voice = voice_settings['edge_voice']
                        voice_info.append(f"🎤 Voice: {voice_settings['edge_voice']}")

            # Apply RVC settings if available
            rvc_info = []
            if voice_cog and voice_cog.rvc and legacy_config and 'rvc' in legacy_config:
                rvc_settings = legacy_config['rvc']
                if rvc_settings.get('enabled') and rvc_settings.get('model'):
                    Config.DEFAULT_RVC_MODEL = rvc_settings['model']
                    rvc_info.append(f"🔊 RVC Model: {rvc_settings['model']}")

            # Build response
            msg_parts = [
                f"✅ **Character switched successfully!**\n",
                f"**Persona:** {compiled_persona.persona_id}",
                f"**Character:** {compiled_persona.character.display_name}",
                f"**Framework:** {compiled_persona.framework.name}",
                f"\n_{compiled_persona.framework.purpose}_"
            ]

            if voice_info:
                msg_parts.extend(["\n"] + voice_info)
            if rvc_info:
                msg_parts.extend(rvc_info)

            # Add tools info
            if compiled_persona.tools_required:
                tools_str = ", ".join(compiled_persona.tools_required[:5])
                if len(compiled_persona.tools_required) > 5:
                    tools_str += f" (+{len(compiled_persona.tools_required) - 5} more)"
                msg_parts.append(f"\n🛠️ Tools: {tools_str}")

            await interaction.followup.send("\n".join(msg_parts), ephemeral=True)
            logger.info(f"✨ Character switched to: {compiled_persona.persona_id}")

        except Exception as e:
            logger.error(f"Failed to set character: {e}", exc_info=True)
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="list_characters", description="List available characters and frameworks")
    async def list_characters(self, interaction: discord.Interaction):
        """List all available characters and frameworks."""
        await interaction.response.defer(ephemeral=True)

        try:
            chars_dir = Path("./prompts/characters")
            frameworks_dir = Path("./prompts/frameworks")

            # Build embed
            embed = discord.Embed(
                title="📚 Available Characters & Frameworks",
                description="Use `/set_character` to switch personas",
                color=discord.Color.blue()
            )

            # List characters
            if chars_dir.exists():
                char_files = sorted(chars_dir.glob("*.json"))
                char_list = []
                for char_file in char_files:
                    char_id = char_file.stem
                    char_list.append(f"• `{char_id}`")

                if char_list:
                    embed.add_field(
                        name="🎭 Characters",
                        value="\n".join(char_list),
                        inline=True
                    )

            # List frameworks
            if frameworks_dir.exists():
                framework_files = sorted(frameworks_dir.glob("*.json"))
                framework_list = []
                for fw_file in framework_files:
                    fw_id = fw_file.stem
                    framework_list.append(f"• `{fw_id}`")

                if framework_list:
                    embed.add_field(
                        name="⚙️ Frameworks",
                        value="\n".join(framework_list),
                        inline=True
                    )

            # Show current persona
            if self.bot.current_persona:
                embed.set_footer(text=f"Current: {self.bot.current_persona.persona_id}")
            else:
                embed.set_footer(text="Current: Legacy persona system")

            # Add examples
            embed.add_field(
                name="📖 Examples",
                value=(
                    "`/set_character dagoth_ur neuro` - Dagoth with Neuro framework\n"
                    "`/set_character gothmommy caring` - Goth Mommy with caring framework\n"
                    "`/set_character chief chaotic` - Chief with chaotic framework\n"
                    "`/set_character arbiter` - Arbiter (auto-selects assistant framework)"
                ),
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List characters failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(CharacterCommandsCog(bot))
    logger.info("Character commands cog loaded")
