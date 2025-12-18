"""Character management commands for AI-First PersonaSystem."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from pathlib import Path

from config import Config
from utils.helpers import format_error

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

    @app_commands.command(
        name="set_character",
        description="Change bot personality using character+framework system",
    )
    @app_commands.describe(
        character="Character to use (dagoth_ur, gothmommy, chief, arbiter)",
        framework="Framework to apply (neuro, caring, chaotic, assistant)",
    )
    async def set_character(
        self,
        interaction: discord.Interaction,
        character: str,
        framework: Optional[str] = None,
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
                    ephemeral=True,
                )
                return

            # Auto-select framework based on character if not specified
            if not framework:
                framework_map = {
                    "dagoth_ur": "neuro",
                    "gothmommy": "caring",
                    "chief": "chaotic",
                    "arbiter": "assistant",
                }
                framework = framework_map.get(character, "neuro")
                logger.info(
                    f"Auto-selected framework '{framework}' for character '{character}'"
                )

            # Compile persona
            compiled_persona = self.bot.persona_system.compile_persona(
                character, framework, force_recompile=True
            )

            if not compiled_persona:
                # List available characters and frameworks
                chars_dir = Path("./prompts/characters")
                frameworks_dir = Path("./prompts/frameworks")

                available_chars = (
                    [f.stem for f in chars_dir.glob("*.json")]
                    if chars_dir.exists()
                    else []
                )
                available_frameworks = (
                    [f.stem for f in frameworks_dir.glob("*.json")]
                    if frameworks_dir.exists()
                    else []
                )

                await interaction.followup.send(
                    f"❌ Failed to compile persona '{character}_{framework}'.\n\n"
                    f"**Available characters:** {', '.join(available_chars) or 'None'}\n"
                    f"**Available frameworks:** {', '.join(available_frameworks) or 'None'}",
                    ephemeral=True,
                )
                return

            # Update bot's current persona
            self.bot.current_persona = compiled_persona

            # Update decision engine
            if self.bot.decision_engine:
                self.bot.decision_engine.set_persona(compiled_persona)
                logger.info(
                    f"Updated decision engine with new persona: {compiled_persona.persona_id}"
                )

            # Update ChatCog
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                chat_cog.compiled_persona = compiled_persona
                chat_cog.system_prompt = compiled_persona.system_prompt
                logger.info(
                    f"Updated ChatCog with new persona: {compiled_persona.persona_id}"
                )

            # Update AmbientMode
            if self.bot.ambient_mode:
                self.bot.ambient_mode.compiled_persona = compiled_persona
                logger.info(
                    f"Updated AmbientMode with new persona: {compiled_persona.persona_id}"
                )

            # Update CuriositySystem
            if self.bot.curiosity_system:
                self.bot.curiosity_system.set_persona(compiled_persona)
                logger.info(
                    f"Updated CuriositySystem with new persona: {compiled_persona.persona_id}"
                )

            # Get legacy config for voice/RVC if available
            character_obj = compiled_persona.character
            legacy_config = None
            if hasattr(character_obj, "legacy_config") and character_obj.legacy_config:
                # Access as dictionary
                import json

                char_dict = json.loads(
                    json.dumps(character_obj, default=lambda o: o.__dict__)
                )
                legacy_config = char_dict.get("legacy_config")

            # Apply voice settings if available
            voice_info = []
            voice_cog = self.bot.get_cog("VoiceCog")
            if (
                voice_cog
                and voice_cog.tts
                and legacy_config
                and "voice" in legacy_config
            ):
                voice_settings = legacy_config["voice"]
                if Config.TTS_ENGINE == "kokoro":
                    if "kokoro_voice" in voice_settings:
                        voice_cog.tts.kokoro_voice = voice_settings["kokoro_voice"]
                        voice_cog.tts.kokoro_speed = voice_settings.get(
                            "kokoro_speed", 1.0
                        )
                        voice_info.append(f"🎤 Voice: {voice_settings['kokoro_voice']}")
                else:  # Edge TTS
                    if "edge_voice" in voice_settings:
                        voice_cog.tts.default_voice = voice_settings["edge_voice"]
                        voice_info.append(f"🎤 Voice: {voice_settings['edge_voice']}")

            # Apply RVC settings if available
            rvc_info = []
            if voice_cog and voice_cog.rvc and legacy_config and "rvc" in legacy_config:
                rvc_settings = legacy_config["rvc"]
                if rvc_settings.get("enabled") and rvc_settings.get("model"):
                    Config.DEFAULT_RVC_MODEL = rvc_settings["model"]
                    rvc_info.append(f"🔊 RVC Model: {rvc_settings['model']}")

            # Build response
            msg_parts = [
                "✅ **Character switched successfully!**\n",
                f"**Persona:** {compiled_persona.persona_id}",
                f"**Character:** {compiled_persona.character.display_name}",
                f"**Framework:** {compiled_persona.framework.name}",
                f"\n_{compiled_persona.framework.purpose}_",
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

    @app_commands.command(
        name="interact", description="Make two characters talk to each other"
    )
    @app_commands.describe(
        initiator="Character starting the conversation (e.g. dagoth_ur)",
        target="Character to speak to (e.g. scav)",
        topic="Topic for them to discuss",
    )
    async def interact(
        self, interaction: discord.Interaction, initiator: str, target: str, topic: str
    ):
        """Force two characters to interact."""
        await interaction.response.defer()

        chat_cog = self.bot.get_cog("ChatCog")
        if not chat_cog:
            await interaction.followup.send("❌ Chat system unavailable.")
            return

        # Helper for fuzzy matching
        def find_persona(name):
            # 1. Try router's lookup (exact or ID)
            p = chat_cog.persona_router.get_persona_by_name(name)
            if p:
                return p

            # 2. Try partial matching
            name_lower = name.lower()
            for p in chat_cog.persona_router.get_all_personas():
                # Check ID
                if name_lower == p.character.character_id.lower():
                    return p
                # Check Display Name parts
                p_name_lower = p.character.display_name.lower()
                if name_lower in p_name_lower:
                    return p

            return None

        # Resolve personas
        p1 = find_persona(initiator)
        p2 = find_persona(target)

        if not p1 or not p2:
            active = [
                p.character.display_name
                for p in chat_cog.persona_router.get_all_personas()
            ]
            missing = []
            if not p1:
                missing.append(initiator)
            if not p2:
                missing.append(target)
            await interaction.followup.send(
                f"❌ Could not find characters: {', '.join(missing)}.\nActive: {active}"
            )
            return

        # Generate Starter
        prompt = f"""You are {p1.character.display_name}.
        Start a conversation with {p2.character.display_name} about: {topic}.
        IMPORTANT: Mention them by name ("{p2.character.display_name}") so they hear you.
        Keep it in character, short (under 200 chars), and engaging."""

        response = await chat_cog.ollama.generate(prompt, max_tokens=200)

        try:
            channel = interaction.channel
            webhooks = await channel.webhooks()
            webhook = next((w for w in webhooks if w.name == "PersonaBot_Proxy"), None)
            if not webhook:
                webhook = await channel.create_webhook(name="PersonaBot_Proxy")

            await webhook.send(
                content=response,
                username=p1.character.display_name,
                avatar_url=p1.character.avatar_url,
            )

            await interaction.followup.send(
                f"🎬 Action! {p1.character.display_name} started talking to {p2.character.display_name}.",
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Error sending webhook: {e}")

            await interaction.followup.send(f"❌ Error sending webhook: {e}")

    @commands.command(name="interact")
    async def interact_cmd(self, ctx, initiator: str, target: str, *, topic: str):
        """Force two characters to interact (Prefix command for immediate use).
        Usage: !interact <char1> <char2> <topic>
        Example: !interact toad dagoth scream at him
        """
        chat_cog = self.bot.get_cog("ChatCog")
        if not chat_cog:
            await ctx.send("❌ Chat system unavailable.")
            return

        # Helper for fuzzy matching
        def find_persona(name):
            # 1. Try router's lookup (exact or ID)
            p = chat_cog.persona_router.get_persona_by_name(name)
            if p:
                return p

            # 2. Try partial matching
            name_lower = name.lower()
            for p in chat_cog.persona_router.get_all_personas():
                # Check ID
                if name_lower == p.character.character_id.lower():
                    return p
                # Check Display Name parts
                p_name_lower = p.character.display_name.lower()
                if name_lower in p_name_lower:
                    return p

            return None

        # Resolve personas
        p1 = find_persona(initiator)
        p2 = find_persona(target)

        if not p1 or not p2:
            active = [
                p.character.display_name
                for p in chat_cog.persona_router.get_all_personas()
            ]
            missing = []
            if not p1:
                missing.append(initiator)
            if not p2:
                missing.append(target)
            await ctx.send(
                f"❌ Could not find characters: {', '.join(missing)}.\nActive: {active}"
            )
            return

        # Generate Starter
        prompt = f"""You are {p1.character.display_name}.
        Start a conversation with {p2.character.display_name} about: {topic}.
        IMPORTANT: Mention them by name ("{p2.character.display_name}") so they hear you.
        Keep it in character, short (under 200 chars), and engaging."""

        try:
            response = await chat_cog.ollama.generate(prompt, max_tokens=200)

            channel = ctx.channel
            webhooks = await channel.webhooks()
            webhook = next((w for w in webhooks if w.name == "PersonaBot_Proxy"), None)
            if not webhook:
                webhook = await channel.create_webhook(name="PersonaBot_Proxy")

            await webhook.send(
                content=response,
                username=p1.character.display_name,
                avatar_url=p1.character.avatar_url,
            )

            # Also try to trigger the auto-reply logic for the SECOND character?
            # The webhook message will trigger on_message -> loop prevention -> strict checks.
            # If target is explicitly mentioned in response, they SHOULD respond.

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @app_commands.command(
        name="list_characters", description="List available characters and frameworks"
    )
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
                color=discord.Color.blue(),
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
                        name="🎭 Characters", value="\n".join(char_list), inline=True
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
                        inline=True,
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
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List characters failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(
        name="import_character_png",
        description="Import a SillyTavern character card (PNG with embedded data)",
    )
    async def import_character_png(self, interaction: discord.Interaction):
        """Import a character card from attached PNG.

        Usage: /import_character (then attach a PNG)
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check for attachment
            if not interaction.message or not interaction.message.attachments:
                # For slash commands, we need to handle this differently
                await interaction.followup.send(
                    "📎 Please use the prefix command `!import` and attach a PNG file.\n"
                    "Example: Send `!import` with a character card PNG attached.",
                    ephemeral=True,
                )
                return

        except Exception as e:
            logger.error(f"Import character failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @commands.command(name="import")
    async def import_character_prefix(self, ctx: commands.Context):
        """Import a SillyTavern character card from attached PNG.

        Usage: !import (attach a PNG file)
        """
        if not ctx.message.attachments:
            await ctx.send(
                "❌ Please attach a SillyTavern character card PNG to import."
            )
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith((".png", ".json")):
            await ctx.send(
                "❌ Please attach a PNG or JSON file (SillyTavern character card)."
            )
            return

        if attachment.size > 10 * 1024 * 1024:  # 10MB limit
            await ctx.send("❌ File size must be less than 10MB")
            return

        await ctx.send("⏳ Importing character card...")

        try:
            from services.persona.character_importer import CharacterCardImporter
            import tempfile
            import os

            # Download the PNG
            temp_dir = Path(tempfile.gettempdir())
            temp_path = temp_dir / attachment.filename
            await attachment.save(temp_path)

            # Import the card (with auto-compile) - run in executor to avoid blocking
            importer = CharacterCardImporter()
            import asyncio

            result = await asyncio.get_event_loop().run_in_executor(
                None, importer.import_card, temp_path, False
            )  # Don't auto-compile yet

            # Clean up temp file
            try:
                os.unlink(temp_path)
            except (OSError, IOError):
                pass

            if result:
                json_path, compiled_path, char_id = result

                # Read the imported character to show details
                import json

                with open(json_path, "r") as f:
                    char_data = json.load(f)

                # Extract data from V2 format
                v2_data = char_data.get("data", char_data)
                char_name = v2_data.get("name", char_id)
                char_desc = v2_data.get("description", "No description")

                embed = discord.Embed(
                    title="✅ Character Imported!",
                    description=f"**{char_name}** is ready to use.",
                    color=discord.Color.green(),
                )
                embed.add_field(name="ID", value=char_id, inline=True)
                embed.add_field(
                    name="Format", value=char_data.get("spec", "V2"), inline=True
                )
                embed.add_field(
                    name="Description",
                    value=char_desc[:200] + ("..." if len(char_desc) > 200 else ""),
                    inline=False,
                )
                embed.add_field(
                    name="Next Steps",
                    value=f'1. Add `"{char_id}.json"` to `ACTIVE_PERSONAS` in config.py\n'
                    f"2. Use `!reload_characters` to load without restart",
                    inline=False,
                )

                await ctx.send(embed=embed)

                # Notify about reloading
                chat_cog = self.bot.get_cog("ChatCog")
                if chat_cog and hasattr(chat_cog, "persona_router"):
                    await ctx.send(
                        "💡 Tip: Use `!reload_characters` to load new characters without restart."
                    )
            else:
                await ctx.send("❌ Failed to import character. Check logs for details.")

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            await ctx.send(f"❌ Import failed: {e}")

    @commands.command(name="reload_characters")
    async def reload_characters(self, ctx: commands.Context):
        """Reload all characters from disk without restarting."""
        chat_cog = self.bot.get_cog("ChatCog")
        if not chat_cog or not hasattr(chat_cog, "persona_router"):
            await ctx.send("❌ Chat system not available.")
            return

        # Get before state
        before_personas = chat_cog.persona_router.personas.copy()
        before_count = len(before_personas)
        before_names = [p.character.display_name for p in before_personas.values()]

        await ctx.send(f"🔄 Reloading characters... (currently loaded: {before_count})")

        try:
            await chat_cog.persona_router.initialize(force_reload=True)
            after_personas = chat_cog.persona_router.personas
            after_count = len(after_personas)
            after_names = [p.character.display_name for p in after_personas.values()]

            new_chars = set(after_names) - set(before_names)
            removed_chars = set(before_names) - set(after_names)

            msg = "✅ Reload complete!\n"
            msg += f"**Before:** {before_count} characters\n"
            msg += f"**After:** {after_count} characters\n"
            if new_chars:
                msg += f"**New:** {', '.join(new_chars)}\n"
            if removed_chars:
                msg += f"**Removed:** {', '.join(removed_chars)}\n"
            msg += f"**Active:** {', '.join(after_names)}"

            await ctx.send(msg)
        except Exception as e:
            logger.error(f"Reload failed: {e}", exc_info=True)
            await ctx.send(f"❌ Reload failed: {e}")

    @app_commands.command(
        name="import_character", description="Import a character card (PNG or JSON)"
    )
    @app_commands.describe(file="Character card file (.png or .json)")
    async def import_character_slash(
        self, interaction: discord.Interaction, file: discord.Attachment
    ):
        """Import a character card and auto-compile."""
        await interaction.response.defer(ephemeral=True)

        # Validate file extension (case-insensitive) and size
        if not file.filename.lower().endswith((".png", ".json")):
            await interaction.followup.send(
                "❌ File must be .png or .json", ephemeral=True
            )
            return

        if file.size > 10 * 1024 * 1024:  # 10MB limit
            await interaction.followup.send(
                "❌ File size must be less than 10MB", ephemeral=True
            )
            return

        try:
            # Download file
            import tempfile
            import os
            from services.persona.character_importer import CharacterCardImporter

            # Create temp file
            fd, tmp_name = tempfile.mkstemp(suffix=Path(file.filename).suffix)
            os.close(fd)  # Close file descriptor
            tmp_path = Path(tmp_name)
            await file.save(tmp_path)

            # Import with normalization and auto-compilation - run in executor to avoid blocking
            importer = CharacterCardImporter()
            import asyncio

            result = await asyncio.get_event_loop().run_in_executor(
                None, importer.import_card, tmp_path, True, True
            )

            # Cleanup temp file
            try:
                tmp_path.unlink()
            except (OSError, IOError):
                pass

            if not result:
                await interaction.followup.send(
                    "❌ Import failed. Check logs.", ephemeral=True
                )
                return

            json_path, compiled_path, char_id = result

            # Hot-reload personas
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog and hasattr(chat_cog, "persona_router"):
                await chat_cog.persona_router.initialize(force_reload=True)

            msg = "✅ **Character imported successfully!**\n"
            msg += f"**ID:** `{char_id}`\n"
            msg += f"**Character File:** `{json_path.name}`\n"
            if compiled_path:
                msg += f"**Compiled:** `{compiled_path.name}`\n"
            msg += "\n**Character is now active!** No restart needed."

            await interaction.followup.send(msg, ephemeral=True)

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Import error: {e}", ephemeral=True)

    @commands.command(name="import_folder")
    async def import_folder(self, ctx: commands.Context):
        """Import all character cards from data/import_cards folder.

        Usage:
        1. Place PNG character cards in: data/import_cards/
        2. Run !import_folder
        """
        import_dir = Path("./data/import_cards")

        if not import_dir.exists():
            import_dir.mkdir(parents=True, exist_ok=True)
            await ctx.send(
                f"📁 Created import folder: `{import_dir}`\n"
                f"Place your PNG character cards there and run `!import_folder` again."
            )
            return

        card_files = list(import_dir.glob("*.png")) + list(import_dir.glob("*.json"))
        if not card_files:
            await ctx.send(
                f"📁 No character cards found in `{import_dir}`\n"
                f"Place SillyTavern character card PNGs or JSONs there and try again."
            )
            return

        await ctx.send(
            f"⏳ Found {len(card_files)} character card files. Importing with auto-compile..."
        )

        try:
            from services.persona.character_importer import CharacterCardImporter

            importer = CharacterCardImporter()
            results = importer.import_from_directory(import_dir, auto_compile=True)

            if results:
                # Extract names from results (json_path, compiled_path, char_id)
                import json

                names = []
                char_ids = []
                compiled_count = 0
                for json_path, compiled_path, char_id in results:
                    with open(json_path, "r") as f:
                        data = json.load(f)
                        names.append(data["data"]["name"])
                        char_ids.append(char_id)
                    if compiled_path:
                        compiled_count += 1

                embed = discord.Embed(
                    title=f"✅ Imported {len(results)} Characters!",
                    description="\n".join(
                        [f"• {name} (`{cid}`)" for name, cid in zip(names, char_ids)]
                    ),
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Auto-Compilation",
                    value=f"{compiled_count}/{len(results)} characters compiled successfully",
                    inline=False,
                )
                embed.add_field(
                    name="Next Steps",
                    value="1. Add character IDs to `ACTIVE_PERSONAS` in config.py\n"
                    "2. Run `!reload_characters` to load without restart",
                    inline=False,
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ No valid character cards found in the PNGs.")

        except Exception as e:
            logger.error(f"Folder import failed: {e}", exc_info=True)
            await ctx.send(f"❌ Import failed: {e}")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(CharacterCommandsCog(bot))
    logger.info("Character commands cog loaded")
