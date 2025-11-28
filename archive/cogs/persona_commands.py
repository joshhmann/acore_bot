"""Persona and model management commands."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import re
from typing import Optional
from pathlib import Path

from config import Config
from utils.helpers import format_error, format_success
from utils.persona_loader import PersonaLoader

logger = logging.getLogger(__name__)


class PersonaCommandsCog(commands.Cog):
    """Commands for managing bot personas and models."""

    def __init__(self, bot, ollama, persona_loader, history):
        """Initialize persona commands cog.

        Args:
            bot: Discord bot instance
            ollama: OllamaService instance
            persona_loader: PersonaLoader instance
            history: ChatHistoryManager instance
        """
        self.bot = bot
        self.ollama = ollama
        self.persona_loader = persona_loader
        self.history = history

    @app_commands.command(name="set_model", description="Change the active Ollama model")
    @app_commands.describe(model="Name of the model to use")
    async def set_model(self, interaction: discord.Interaction, model: str):
        """Change the active Ollama model.

        Args:
            interaction: Discord interaction
            model: Name of the model to use
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if model is available
            models = await self.ollama.list_models()

            if model not in models:
                available = ", ".join(models) if models else "None found"
                await interaction.followup.send(
                    f"❌ Model '{model}' not found.\n\nAvailable models: {available}",
                    ephemeral=True,
                )
                return

            # Update model
            self.ollama.model = model
            await interaction.followup.send(
                format_success(f"Model changed to: **{model}**"), ephemeral=True
            )

        except Exception as e:
            logger.error(f"Set model failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="models", description="List available Ollama models")
    async def models(self, interaction: discord.Interaction):
        """List all available models.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            models = await self.ollama.list_models()

            if not models:
                await interaction.followup.send("❌ No models found on Ollama server.", ephemeral=True)
                return

            current = self.ollama.model
            model_list = "\n".join([f"{'🟢' if m == current else '⚪'} {m}" for m in models])

            embed = discord.Embed(
                title="Available Ollama Models",
                description=model_list,
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Current model: {current}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Models command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="set_persona", description="Change the bot's personality/character")
    @app_commands.describe(persona="Persona name (chief, arbiter, gothmommy, etc.)")
    async def set_persona(self, interaction: discord.Interaction, persona: str):
        """Change the bot's personality using persona configuration.

        Args:
            interaction: Discord interaction
            persona: Name of the persona
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Load persona config
            persona_config = self.persona_loader.get_persona(persona)

            if not persona_config:
                # List available personas
                available = self.persona_loader.list_personas()
                available_str = ", ".join(available) if available else "None found"

                await interaction.followup.send(
                    f"❌ Persona '{persona}' not found.\n\n**Available personas:** {available_str}\n\n"
                    f"Use `/list_personas` for more details.",
                    ephemeral=True,
                )
                return

            if not persona_config.prompt_text:
                await interaction.followup.send(
                    f"❌ Persona '{persona}' has no prompt text.",
                    ephemeral=True,
                )
                return

            # Update the system prompt in ChatCog
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                chat_cog.system_prompt = persona_config.prompt_text
                chat_cog.current_persona = persona_config
            logger.info(f"Changed persona to: {persona_config.display_name}")

            # Switch voice based on config
            voice_cog = self.bot.get_cog("VoiceCog")
            voice_info = []
            if voice_cog and voice_cog.tts:
                # Apply voice settings based on TTS engine
                if Config.TTS_ENGINE == "kokoro":
                    voice_cog.tts.kokoro_voice = persona_config.voice.kokoro_voice
                    voice_cog.tts.kokoro_speed = persona_config.voice.kokoro_speed
                    voice_info.append(f"🎤 Voice: {persona_config.voice.kokoro_voice} (speed: {persona_config.voice.kokoro_speed}x)")
                else:  # Edge TTS
                    voice_cog.tts.default_voice = persona_config.voice.edge_voice
                    voice_cog.tts.rate = persona_config.voice.edge_rate
                    voice_cog.tts.volume = persona_config.voice.edge_volume
                    voice_info.append(f"🎤 Voice: {persona_config.voice.edge_voice}")

                logger.info(f"Applied voice settings for {persona}")

            # Apply RVC settings if enabled
            rvc_info = []
            if voice_cog and voice_cog.rvc and persona_config.rvc.enabled:
                if persona_config.rvc.model:
                    # Note: This sets the default model, actual usage depends on RVC being enabled
                    Config.DEFAULT_RVC_MODEL = persona_config.rvc.model
                    rvc_info.append(f"🔊 RVC Model: {persona_config.rvc.model}")
                    logger.info(f"Set RVC model to: {persona_config.rvc.model}")

            # Clear history if configured
            if persona_config.behavior.clear_history_on_switch:
                await self.history.clear_history(interaction.channel_id)

            # Build response message
            msg_parts = [f"✅ Persona changed to: **{persona_config.display_name}**"]
            if persona_config.description:
                msg_parts.append(f"_{persona_config.description}_")
            if voice_info:
                msg_parts.extend(voice_info)
            if rvc_info:
                msg_parts.extend(rvc_info)
            if persona_config.behavior.clear_history_on_switch:
                msg_parts.append("🗑️ Conversation history cleared")
            if persona_config.tags:
                msg_parts.append(f"🏷️ Tags: {', '.join(persona_config.tags)}")

            await interaction.followup.send(
                "\n".join(msg_parts),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Set persona failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="list_personas", description="List all available bot personalities")
    async def list_personas(self, interaction: discord.Interaction):
        """List all available persona/prompt files.

        Args:
            interaction: Discord interaction
        """
        try:
            prompts_dir = Path("prompts")
            if not prompts_dir.exists():
                await interaction.response.send_message(
                    "❌ Prompts directory not found.",
                    ephemeral=True,
                )
                return

            # Get all .txt files in prompts directory
            prompt_files = sorted(prompts_dir.glob("*.txt"))

            if not prompt_files:
                await interaction.response.send_message(
                    "❌ No persona files found in prompts/ directory.",
                    ephemeral=True,
                )
                return

            # Build embed with persona descriptions
            embed = discord.Embed(
                title="🎭 Available Bot Personas",
                description="Use `/set_persona <name>` to switch personalities",
                color=discord.Color.purple(),
            )

            # Parse each file for description (first 100 chars)
            for prompt_file in prompt_files:
                persona_name = prompt_file.stem
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        # Get first line or first 100 chars as preview
                        preview = content.split('\n')[0][:100]
                        if len(content.split('\n')[0]) > 100:
                            preview += "..."

                        embed.add_field(
                            name=persona_name,
                            value=preview or "No description",
                            inline=False,
                        )
                except Exception as e:
                    embed.add_field(
                        name=persona_name,
                        value=f"Error loading: {e}",
                        inline=False,
                    )

            # Show current persona
            current_prompt_file = Path(Config.SYSTEM_PROMPT_FILE).stem
            embed.set_footer(text=f"Current persona: {current_prompt_file}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List personas failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="add_persona", description="Create a new bot persona")
    @app_commands.describe(
        name="Persona name (lowercase, no spaces)",
        display_name="Display name for the persona",
        description="Short description of the persona",
        prompt="The personality/system prompt for the persona",
        kokoro_voice="Kokoro voice to use (e.g., am_adam, af_bella)",
    )
    async def add_persona(
        self,
        interaction: discord.Interaction,
        name: str,
        display_name: str,
        description: str,
        prompt: str,
        kokoro_voice: Optional[str] = "am_adam",
    ):
        """Create a new persona with configuration.

        Args:
            interaction: Discord interaction
            name: Persona identifier (lowercase, no spaces)
            display_name: Human-readable name
            description: Short description
            prompt: System prompt for the persona
            kokoro_voice: Kokoro voice to use
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Validate name (lowercase, alphanumeric + underscores only)
            if not re.match(r'^[a-z0-9_]+$', name):
                await interaction.followup.send(
                    "❌ Persona name must be lowercase alphanumeric with underscores only (e.g., 'my_persona')",
                    ephemeral=True,
                )
                return

            prompts_dir = Path("prompts")
            prompts_dir.mkdir(parents=True, exist_ok=True)

            # Check if persona already exists
            json_file = prompts_dir / f"{name}.json"
            txt_file = prompts_dir / f"{name}.txt"

            if json_file.exists() or txt_file.exists():
                await interaction.followup.send(
                    f"❌ Persona '{name}' already exists. Use `/edit_persona` to modify it.",
                    ephemeral=True,
                )
                return

            # Create persona JSON configuration
            persona_config = {
                "name": name,
                "display_name": display_name,
                "description": description,
                "prompt_file": f"{name}.txt",
                "voice": {
                    "kokoro_voice": kokoro_voice,
                    "kokoro_speed": 1.0,
                    "edge_voice": "en-US-AriaNeural",
                    "edge_rate": "+0%",
                    "edge_volume": "+0%"
                },
                "rvc": {
                    "enabled": False,
                    "model": None,
                    "pitch_shift": 0
                },
                "behavior": {
                    "clear_history_on_switch": True,
                    "auto_reply_enabled": True,
                    "affection_multiplier": 1.0
                },
                "tags": []
            }

            # Write JSON config
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(persona_config, f, indent=2)

            # Write prompt text file
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(prompt)

            # Reload persona loader to include new persona
            self.persona_loader = PersonaLoader()

            await interaction.followup.send(
                f"✅ Persona **{display_name}** created successfully!\n\n"
                f"**Name:** {name}\n"
                f"**Description:** {description}\n"
                f"**Voice:** {kokoro_voice}\n\n"
                f"Use `/set_persona {name}` to activate it.\n"
                f"Use `/edit_persona {name}` to modify settings.",
                ephemeral=True,
            )

            logger.info(f"Created new persona: {name} ({display_name})")

        except Exception as e:
            logger.error(f"Add persona failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="edit_persona", description="Edit an existing persona's settings")
    @app_commands.describe(
        name="Persona name to edit",
        display_name="New display name (optional)",
        description="New description (optional)",
        kokoro_voice="New Kokoro voice (optional)",
        kokoro_speed="Voice speed multiplier (optional, e.g., 1.0, 1.2)",
    )
    async def edit_persona(
        self,
        interaction: discord.Interaction,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        kokoro_voice: Optional[str] = None,
        kokoro_speed: Optional[float] = None,
    ):
        """Edit an existing persona's configuration.

        Args:
            interaction: Discord interaction
            name: Persona name to edit
            display_name: New display name
            description: New description
            kokoro_voice: New Kokoro voice
            kokoro_speed: New voice speed
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            prompts_dir = Path("prompts")
            json_file = prompts_dir / f"{name}.json"

            if not json_file.exists():
                await interaction.followup.send(
                    f"❌ Persona '{name}' not found. Use `/add_persona` to create it.",
                    ephemeral=True,
                )
                return

            # Load existing config
            with open(json_file, 'r', encoding='utf-8') as f:
                persona_config = json.load(f)

            # Track what was changed
            changes = []

            # Update fields if provided
            if display_name:
                persona_config["display_name"] = display_name
                changes.append(f"Display name → {display_name}")

            if description:
                persona_config["description"] = description
                changes.append(f"Description → {description}")

            if kokoro_voice:
                persona_config["voice"]["kokoro_voice"] = kokoro_voice
                changes.append(f"Kokoro voice → {kokoro_voice}")

            if kokoro_speed is not None:
                persona_config["voice"]["kokoro_speed"] = kokoro_speed
                changes.append(f"Voice speed → {kokoro_speed}x")

            if not changes:
                await interaction.followup.send(
                    "❌ No changes specified. Provide at least one parameter to update.",
                    ephemeral=True,
                )
                return

            # Save updated config
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(persona_config, f, indent=2)

            # Reload persona loader
            self.persona_loader = PersonaLoader()

            changes_text = "\n".join([f"• {c}" for c in changes])
            await interaction.followup.send(
                f"✅ Persona **{name}** updated successfully!\n\n"
                f"**Changes:**\n{changes_text}\n\n"
                f"Use `/set_persona {name}` to apply the changes.",
                ephemeral=True,
            )

            logger.info(f"Updated persona: {name} - {len(changes)} changes")

        except Exception as e:
            logger.error(f"Edit persona failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    # Get required services from ChatCog
    chat_cog = bot.get_cog("ChatCog")
    if chat_cog:
        await bot.add_cog(PersonaCommandsCog(
            bot,
            chat_cog.ollama,
            chat_cog.persona_loader,
            chat_cog.history
        ))
        logger.info("Loaded PersonaCommandsCog")
    else:
        logger.error("ChatCog not found, cannot load PersonaCommandsCog")
