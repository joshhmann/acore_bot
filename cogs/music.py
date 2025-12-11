"""Music cog for Discord bot with YouTube playback support."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import asyncio

from services.discord.music import MusicPlayer
from utils.helpers import format_error

logger = logging.getLogger(__name__)


class MusicCog(commands.Cog):
    """Cog for music playback commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize the music cog.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.music_player = MusicPlayer(bot)
        logger.info("Music cog initialized")

    async def _get_voice_client(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceClient]:
        """Get voice client for the guild, connecting if needed.

        Args:
            interaction: Discord interaction

        Returns:
            Voice client or None if user not in voice
        """
        if not interaction.user.voice:
            await interaction.followup.send(
                "❌ You need to be in a voice channel to use music commands!",
                ephemeral=True,
            )
            return None

        voice_client = interaction.guild.voice_client

        if not voice_client:
            # Connect to user's channel
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Failed to connect to voice channel: {e}", ephemeral=True
                )
                return None

        return voice_client

    @app_commands.command(name="play", description="Play a song or add it to the queue")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song from YouTube.

        Args:
            interaction: Discord interaction
            query: Search query or URL
        """
        await interaction.response.defer(thinking=True)

        voice_client = await self._get_voice_client(interaction)
        if not voice_client:
            return

        try:
            # Check if it's a playlist
            is_playlist = "list=" in query and "youtube.com" in query

            if is_playlist:
                # Handle playlist
                songs = await self.music_player.search_playlist(
                    query, requester=interaction.user.display_name
                )

                if not songs:
                    await interaction.followup.send(
                        "❌ Could not find playlist or it's empty."
                    )
                    return

                # Add all songs to queue
                for song in songs:
                    await self.music_player.add_to_queue(interaction.guild.id, song)

                await interaction.followup.send(
                    f"✅ Added **{len(songs)} songs** from playlist to the queue!"
                )

                # Start playing if not already
                state = self.music_player.get_state(interaction.guild.id)
                if not state.is_playing:
                    await self.music_player.play_next(
                        interaction.guild.id, voice_client
                    )

            else:
                # Single song
                song = await self.music_player.search_song(
                    query, requester=interaction.user.display_name
                )

                if not song:
                    await interaction.followup.send(f"❌ Could not find: **{query}**")
                    return

                # Add to queue
                position = await self.music_player.add_to_queue(
                    interaction.guild.id, song
                )

                # Create embed
                embed = discord.Embed(
                    title="🎵 Added to Queue",
                    description=f"[{song.title}]({song.url})",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Duration", value=song.duration_str, inline=True)
                embed.add_field(name="Position", value=str(position), inline=True)
                embed.add_field(name="Requested by", value=song.requester, inline=True)

                if song.thumbnail:
                    embed.set_thumbnail(url=song.thumbnail)

                await interaction.followup.send(embed=embed)

                # Start playing if not already
                state = self.music_player.get_state(interaction.guild.id)
                if not state.is_playing:
                    await self.music_player.play_next(
                        interaction.guild.id, voice_client
                    )

        except Exception as e:
            logger.error(f"Play command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song.

        Args:
            interaction: Discord interaction
        """
        voice_client = interaction.guild.voice_client

        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message(
                "❌ Nothing is playing right now.", ephemeral=True
            )
            return

        current = self.music_player.get_now_playing(interaction.guild.id)
        title = current.title if current else "current song"

        await self.music_player.skip(interaction.guild.id, voice_client)

        await interaction.response.send_message(f"⏭️ Skipped **{title}**")

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        """Stop playback and clear queue.

        Args:
            interaction: Discord interaction
        """
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message(
                "❌ Not connected to a voice channel.", ephemeral=True
            )
            return

        await self.music_player.stop(interaction.guild.id, voice_client)
        await interaction.response.send_message("⏹️ Stopped playback and cleared queue.")

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        """Pause playback.

        Args:
            interaction: Discord interaction
        """
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message(
                "❌ Not connected to a voice channel.", ephemeral=True
            )
            return

        if await self.music_player.pause(interaction.guild.id, voice_client):
            await interaction.response.send_message("⏸️ Paused playback.")
        else:
            await interaction.response.send_message(
                "❌ Nothing is playing right now.", ephemeral=True
            )

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        """Resume playback.

        Args:
            interaction: Discord interaction
        """
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message(
                "❌ Not connected to a voice channel.", ephemeral=True
            )
            return

        if await self.music_player.resume(interaction.guild.id, voice_client):
            await interaction.response.send_message("▶️ Resumed playback.")
        else:
            await interaction.response.send_message(
                "❌ Nothing is paused right now.", ephemeral=True
            )

    @app_commands.command(
        name="nowplaying", description="Show the currently playing song"
    )
    async def nowplaying(self, interaction: discord.Interaction):
        """Show current song info.

        Args:
            interaction: Discord interaction
        """
        current = self.music_player.get_now_playing(interaction.guild.id)

        if not current:
            await interaction.response.send_message(
                "❌ Nothing is playing right now.", ephemeral=True
            )
            return

        state = self.music_player.get_state(interaction.guild.id)

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{current.title}]({current.url})",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Duration", value=current.duration_str, inline=True)
        embed.add_field(
            name="Requested by", value=current.requester or "Unknown", inline=True
        )
        embed.add_field(
            name="Loop",
            value="🔂 Song"
            if state.loop
            else ("🔁 Queue" if state.loop_queue else "Off"),
            inline=True,
        )

        if current.thumbnail:
            embed.set_thumbnail(url=current.thumbnail)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="Show the music queue")
    async def queue(self, interaction: discord.Interaction):
        """Show the current queue.

        Args:
            interaction: Discord interaction
        """
        state = self.music_player.get_state(interaction.guild.id)
        queue = self.music_player.get_queue(interaction.guild.id)

        embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.purple())

        # Current song
        if state.current:
            embed.add_field(
                name="Now Playing",
                value=f"🎵 [{state.current.title}]({state.current.url}) - {state.current.duration_str}",
                inline=False,
            )

        # Queue
        if queue:
            queue_text = ""
            for i, song in enumerate(queue[:10], 1):
                queue_text += (
                    f"`{i}.` [{song.title}]({song.url}) - {song.duration_str}\n"
                )

            if len(queue) > 10:
                queue_text += f"\n*...and {len(queue) - 10} more songs*"

            embed.add_field(
                name=f"Up Next ({len(queue)} songs)", value=queue_text, inline=False
            )

            # Total duration
            total_duration = sum(s.duration for s in queue)
            if state.current:
                total_duration += state.current.duration
            hours = total_duration // 3600
            minutes = (total_duration % 3600) // 60
            embed.set_footer(text=f"Total duration: {hours}h {minutes}m")
        else:
            if not state.current:
                embed.description = "The queue is empty. Use `/play` to add songs!"

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set the playback volume")
    @app_commands.describe(level="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, level: int):
        """Set playback volume.

        Args:
            interaction: Discord interaction
            level: Volume level 0-100
        """
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message(
                "❌ Not connected to a voice channel.", ephemeral=True
            )
            return

        # Convert 0-100 to 0.0-1.0
        volume = level / 100.0
        new_volume = self.music_player.set_volume(
            interaction.guild.id, volume, voice_client
        )

        await interaction.response.send_message(
            f"🔊 Volume set to **{int(new_volume * 100)}%**"
        )

    @app_commands.command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, interaction: discord.Interaction):
        """Shuffle the queue.

        Args:
            interaction: Discord interaction
        """
        count = self.music_player.shuffle_queue(interaction.guild.id)

        if count > 0:
            await interaction.response.send_message(
                f"🔀 Shuffled **{count}** songs in the queue!"
            )
        else:
            await interaction.response.send_message(
                "❌ Not enough songs in queue to shuffle.", ephemeral=True
            )

    @app_commands.command(name="clear_queue", description="Clear the music queue")
    async def clear_queue(self, interaction: discord.Interaction):
        """Clear the queue.

        Args:
            interaction: Discord interaction
        """
        count = self.music_player.clear_queue(interaction.guild.id)

        if count > 0:
            await interaction.response.send_message(
                f"🗑️ Cleared **{count}** songs from the queue."
            )
        else:
            await interaction.response.send_message(
                "❌ Queue is already empty.", ephemeral=True
            )

    @app_commands.command(name="loop", description="Toggle loop mode")
    @app_commands.describe(mode="Loop mode: song, queue, or off")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Song (repeat current)", value="song"),
            app_commands.Choice(name="Queue (repeat all)", value="queue"),
            app_commands.Choice(name="Off", value="off"),
        ]
    )
    async def loop(self, interaction: discord.Interaction, mode: str):
        """Toggle loop mode.

        Args:
            interaction: Discord interaction
            mode: Loop mode
        """
        state = self.music_player.get_state(interaction.guild.id)

        if mode == "song":
            state.loop = True
            state.loop_queue = False
            await interaction.response.send_message("🔂 Now looping the current song.")
        elif mode == "queue":
            state.loop = False
            state.loop_queue = True
            await interaction.response.send_message("🔁 Now looping the entire queue.")
        else:
            state.loop = False
            state.loop_queue = False
            await interaction.response.send_message("➡️ Loop disabled.")

    @app_commands.command(name="remove", description="Remove a song from the queue")
    @app_commands.describe(position="Position in queue (1, 2, 3...)")
    async def remove(self, interaction: discord.Interaction, position: int):
        """Remove a song from the queue.

        Args:
            interaction: Discord interaction
            position: Queue position (1-indexed)
        """
        state = self.music_player.get_state(interaction.guild.id)
        queue = list(state.queue)

        if position < 1 or position > len(queue):
            await interaction.response.send_message(
                f"❌ Invalid position. Queue has {len(queue)} songs.", ephemeral=True
            )
            return

        # Remove the song
        removed = queue.pop(position - 1)
        state.queue = type(state.queue)(queue)

        await interaction.response.send_message(
            f"🗑️ Removed **{removed.title}** from the queue."
        )

    @app_commands.command(
        name="disconnect", description="Disconnect bot from voice channel"
    )
    async def disconnect(self, interaction: discord.Interaction):
        """Disconnect from voice channel.

        Args:
            interaction: Discord interaction
        """
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message(
                "❌ Not connected to a voice channel.", ephemeral=True
            )
            return

        # Clean up music state
        self.music_player.cleanup(interaction.guild.id)

        await voice_client.disconnect()
        await interaction.response.send_message("👋 Disconnected from voice channel.")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice state updates (e.g., bot left alone).

        Args:
            member: Member whose voice state changed
            before: Previous voice state
            after: New voice state
        """
        # Check if bot was disconnected
        if member == self.bot.user and before.channel and not after.channel:
            self.music_player.cleanup(member.guild.id)
            return

        # Check if bot is alone in voice channel
        voice_client = member.guild.voice_client
        if voice_client and voice_client.channel:
            # Count non-bot members
            members = [m for m in voice_client.channel.members if not m.bot]
            if len(members) == 0:
                # All users left, disconnect after a delay
                await asyncio.sleep(30)  # Wait 30 seconds

                # Check again
                if voice_client.is_connected():
                    members = [m for m in voice_client.channel.members if not m.bot]
                    if len(members) == 0:
                        self.music_player.cleanup(member.guild.id)
                        await voice_client.disconnect()
                        logger.info(
                            f"Auto-disconnected from {member.guild.name} (empty channel)"
                        )


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(MusicCog(bot))
    logger.info("Music cog loaded")
