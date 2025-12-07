"""Voice commands for the bot."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import uuid
import asyncio

from config import Config
from services.voice_commands import VoiceCommandParser, CommandType
from utils.helpers import format_error, format_success, format_info

logger = logging.getLogger(__name__)

class VoiceCommands(commands.Cog):
    """Cog for voice commands."""

    def __init__(self, bot, voice_cog):
        self.bot = bot
        self.voice_cog = voice_cog
        # Shortcuts for cleaner code
        self.manager = voice_cog.voice_manager
        self.tts = voice_cog.tts
        self.rvc = voice_cog.rvc
        self.enhanced_listener = voice_cog.enhanced_listener

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        """Join the user's voice channel."""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel!", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        channel = interaction.user.voice.channel

        try:
            if self.manager.is_connected(interaction.guild.id):
                await interaction.followup.send(
                    "✅ Already connected to a voice channel!"
                )
                return

            voice_client = await self.manager.join_channel(channel, interaction.guild.id)
            if voice_client:
                await interaction.followup.send(
                    format_success(f"Joined **{channel.name}**!")
                )
            else:
                await interaction.followup.send(
                    format_error("Failed to join voice channel")
                )

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="leave", description="Leave voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Leave the current voice channel."""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        if not self.manager.is_connected(guild_id):
            await interaction.followup.send(
                "❌ Not connected to any voice channel!"
            )
            return

        if await self.manager.leave_channel(guild_id):
            await interaction.followup.send(
                format_success("Disconnected from voice channel!")
            )
        else:
            await interaction.followup.send(
                format_error("Failed to leave voice channel")
            )

    @app_commands.command(name="speak", description="Generate speech and play in voice channel")
    @app_commands.describe(text="Text to speak")
    @app_commands.checks.cooldown(1, 3.0)
    async def speak(self, interaction: discord.Interaction, text: str):
        """Generate TTS and play in voice channel."""
        if len(text) > 1000:
            await interaction.response.send_message(
                "❌ Text too long! Please keep speech under 1000 characters.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            guild_id = interaction.guild.id
            if not self.manager.is_connected(guild_id):
                await interaction.followup.send("❌ Not connected to a voice channel! Use `/join` first.")
                return

            voice_client = self.manager.get_voice_client(guild_id)
            if voice_client.is_playing():
                await interaction.followup.send("⏸️ Already playing audio. Please wait...")
                return

            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.wav"
            await self.tts.generate(text, audio_file)

            if self.rvc and self.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.wav"
                await self.rvc.convert(
                    audio_file, rvc_file,
                    model_name=Config.DEFAULT_RVC_MODEL,
                    pitch_shift=Config.RVC_PITCH_SHIFT,
                    index_rate=Config.RVC_INDEX_RATE,
                    protect=Config.RVC_PROTECT
                )
                audio_file = rvc_file

            self.voice_cog.play_audio(guild_id, audio_file)
            await interaction.followup.send(format_success("🔊 Playing audio..."))

        except Exception as e:
            logger.error(f"Speak command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="listen", description="Start smart listening")
    async def listen(self, interaction: discord.Interaction):
        """Start smart listening."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if not self.enhanced_listener:
                await interaction.followup.send("❌ STT not available.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            if not self.manager.is_connected(guild_id):
                await interaction.followup.send("❌ Bot must join voice first.", ephemeral=True)
                return

            if self.enhanced_listener.is_listening(guild_id):
                await interaction.followup.send("⚠️ Already listening.", ephemeral=True)
                return

            voice_client = self.manager.get_voice_client(guild_id)

            # Start listening (callbacks are handled in VoiceCog for simplicity or can be passed)
            # For this refactor, we'll let VoiceCog handle the callbacks logic
            # This is a bit circular, but we want to move commands out of VoiceCog

            # Delegate to VoiceCog's start_listening logic or move it here?
            # It's better to keep complex logic in VoiceCog and call it
            success = await self.voice_cog.start_listening_session(interaction)

            if not success: # if start_listening_session returns False or None (handled inside)
                 pass

        except Exception as e:
            logger.error(f"Listen command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="stop_listening", description="Stop listening")
    async def stop_listening(self, interaction: discord.Interaction):
        """Stop listening."""
        await interaction.response.defer(ephemeral=True)
        await self.voice_cog.stop_listening_session(interaction)

async def setup(bot: commands.Bot):
    # This cog is loaded manually by VoiceCog, so this setup might not be used directly
    # if we want to nest it. But usually we add cogs to bot.
    pass
