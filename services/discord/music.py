"""Music player service with YouTube support via yt-dlp."""
import logging
import asyncio
import discord
from typing import Optional, Dict, List, Any
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque
import concurrent.futures
import yt_dlp

from config import Config

logger = logging.getLogger(__name__)

# FFmpeg options with reconnect for stability
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af "volume=0.5"'
}

# yt-dlp options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,  # Allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',  # Search YouTube if not a URL
    'source_address': '0.0.0.0',  # Bind to ipv4
    'extract_flat': False,
}


@dataclass
class Song:
    """Represents a song in the queue."""
    title: str
    url: str
    stream_url: str
    duration: int  # seconds
    thumbnail: Optional[str] = None
    requester: Optional[str] = None

    @property
    def duration_str(self) -> str:
        """Format duration as MM:SS or HH:MM:SS."""
        if self.duration >= 3600:
            hours = self.duration // 3600
            minutes = (self.duration % 3600) // 60
            seconds = self.duration % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            minutes = self.duration // 60
            seconds = self.duration % 60
            return f"{minutes}:{seconds:02d}"


@dataclass
class GuildMusicState:
    """Music state for a single guild."""
    queue: deque = field(default_factory=deque)
    current: Optional[Song] = None
    volume: float = 0.5
    loop: bool = False
    loop_queue: bool = False
    is_playing: bool = False
    skip_votes: set = field(default_factory=set)


class MusicPlayer:
    """Handles music playback for Discord voice channels."""

    def __init__(self, bot):
        """Initialize the music player.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.states: Dict[int, GuildMusicState] = {}
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        # Check for cookies file
        self.cookies_path = Config.DATA_DIR / "cookies.txt"
        if self.cookies_path.exists():
            YTDL_OPTIONS['cookiefile'] = str(self.cookies_path)
            logger.info(f"Using cookies file: {self.cookies_path}")

        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        logger.info("Music player initialized")

    def get_state(self, guild_id: int) -> GuildMusicState:
        """Get or create music state for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            GuildMusicState for the guild
        """
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()
        return self.states[guild_id]

    async def search_song(self, query: str, requester: str = None) -> Optional[Song]:
        """Search for a song and return Song object.

        Args:
            query: Search query or URL
            requester: Name of user who requested

        Returns:
            Song object or None if not found
        """
        try:
            # Run yt-dlp in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            # Check if it's a URL or search query
            if not query.startswith(('http://', 'https://')):
                query = f"ytsearch:{query}"

            data = await loop.run_in_executor(
                self.thread_pool,
                lambda: self.ytdl.extract_info(query, download=False)
            )

            if not data:
                return None

            # Handle playlist/search results
            if 'entries' in data:
                # Take first result from search/playlist
                data = data['entries'][0] if data['entries'] else None
                if not data:
                    return None

            song = Song(
                title=data.get('title', 'Unknown'),
                url=data.get('webpage_url', query),
                stream_url=data.get('url', ''),
                duration=data.get('duration', 0) or 0,
                thumbnail=data.get('thumbnail'),
                requester=requester
            )

            logger.info(f"Found song: {song.title} ({song.duration_str})")
            return song

        except Exception as e:
            logger.error(f"Failed to search for song: {e}")
            return None

    async def search_playlist(self, url: str, requester: str = None) -> List[Song]:
        """Search for a playlist and return list of Songs.

        Args:
            url: Playlist URL
            requester: Name of user who requested

        Returns:
            List of Song objects
        """
        try:
            loop = asyncio.get_event_loop()

            # Use flat extraction for playlists to speed up
            playlist_opts = YTDL_OPTIONS.copy()
            playlist_opts['extract_flat'] = 'in_playlist'

            ytdl_playlist = yt_dlp.YoutubeDL(playlist_opts)

            data = await loop.run_in_executor(
                self.thread_pool,
                lambda: ytdl_playlist.extract_info(url, download=False)
            )

            if not data or 'entries' not in data:
                return []

            songs = []
            for entry in data['entries']:
                if entry:
                    # For flat extraction, we need to get full info later
                    # For now, create basic song objects
                    song = Song(
                        title=entry.get('title', 'Unknown'),
                        url=entry.get('url', entry.get('webpage_url', '')),
                        stream_url='',  # Will be fetched when played
                        duration=entry.get('duration', 0) or 0,
                        thumbnail=entry.get('thumbnail'),
                        requester=requester
                    )
                    songs.append(song)

            logger.info(f"Found playlist with {len(songs)} songs")
            return songs

        except Exception as e:
            logger.error(f"Failed to search playlist: {e}")
            return []

    async def add_to_queue(self, guild_id: int, song: Song) -> int:
        """Add a song to the queue.

        Args:
            guild_id: Discord guild ID
            song: Song to add

        Returns:
            Position in queue (0 = playing next)
        """
        state = self.get_state(guild_id)
        state.queue.append(song)
        position = len(state.queue)
        logger.info(f"Added to queue [{guild_id}]: {song.title} (position {position})")
        return position

    async def play_next(self, guild_id: int, voice_client: discord.VoiceClient):
        """Play the next song in the queue.

        Args:
            guild_id: Discord guild ID
            voice_client: Discord voice client
        """
        state = self.get_state(guild_id)

        # Clear skip votes
        state.skip_votes.clear()

        # Handle loop modes
        if state.loop and state.current:
            # Loop current song
            pass
        elif state.loop_queue and state.current:
            # Add current song back to end of queue
            state.queue.append(state.current)
            state.current = None
        else:
            state.current = None

        # Get next song if not looping current
        if not state.loop or not state.current:
            if not state.queue:
                state.is_playing = False
                state.current = None
                logger.info(f"Queue empty for guild {guild_id}")
                return

            state.current = state.queue.popleft()

        # If stream_url is empty (from playlist), fetch it now
        if not state.current.stream_url:
            refreshed = await self.search_song(state.current.url, state.current.requester)
            if refreshed:
                state.current.stream_url = refreshed.stream_url
            else:
                logger.error(f"Failed to get stream URL for {state.current.title}")
                # Try next song
                await self.play_next(guild_id, voice_client)
                return

        try:
            # Create audio source with volume
            source = discord.FFmpegPCMAudio(
                state.current.stream_url,
                **FFMPEG_OPTIONS
            )

            # Apply volume transform
            source = discord.PCMVolumeTransformer(source, volume=state.volume)

            # Play with callback for next song
            def after_playing(error):
                if error:
                    logger.error(f"Playback error: {error}")
                # Schedule next song
                asyncio.run_coroutine_threadsafe(
                    self.play_next(guild_id, voice_client),
                    self.bot.loop
                )

            voice_client.play(source, after=after_playing)
            state.is_playing = True

            logger.info(f"Now playing [{guild_id}]: {state.current.title}")

            # Update dashboard if available
            if hasattr(self.bot, 'web_dashboard'):
                self.bot.web_dashboard.set_status(
                    "Playing Music",
                    f"🎵 {state.current.title}"
                )

        except Exception as e:
            logger.error(f"Failed to play song: {e}")
            state.is_playing = False
            # Try next song
            await self.play_next(guild_id, voice_client)

    async def skip(self, guild_id: int, voice_client: discord.VoiceClient) -> bool:
        """Skip the current song.

        Args:
            guild_id: Discord guild ID
            voice_client: Discord voice client

        Returns:
            True if skipped successfully
        """
        state = self.get_state(guild_id)

        if not state.current:
            return False

        # Disable loop for this skip
        was_looping = state.loop
        state.loop = False

        # Stop current playback (triggers after callback)
        if voice_client.is_playing():
            voice_client.stop()

        # Restore loop state
        state.loop = was_looping

        return True

    async def stop(self, guild_id: int, voice_client: discord.VoiceClient):
        """Stop playback and clear queue.

        Args:
            guild_id: Discord guild ID
            voice_client: Discord voice client
        """
        state = self.get_state(guild_id)

        state.queue.clear()
        state.current = None
        state.is_playing = False
        state.loop = False
        state.loop_queue = False

        if voice_client.is_playing():
            voice_client.stop()

        logger.info(f"Stopped playback for guild {guild_id}")

    async def pause(self, guild_id: int, voice_client: discord.VoiceClient) -> bool:
        """Pause playback.

        Args:
            guild_id: Discord guild ID
            voice_client: Discord voice client

        Returns:
            True if paused successfully
        """
        if voice_client.is_playing():
            voice_client.pause()
            return True
        return False

    async def resume(self, guild_id: int, voice_client: discord.VoiceClient) -> bool:
        """Resume playback.

        Args:
            guild_id: Discord guild ID
            voice_client: Discord voice client

        Returns:
            True if resumed successfully
        """
        if voice_client.is_paused():
            voice_client.resume()
            return True
        return False

    def set_volume(self, guild_id: int, volume: float, voice_client: discord.VoiceClient) -> float:
        """Set playback volume.

        Args:
            guild_id: Discord guild ID
            volume: Volume level (0.0 to 1.0)
            voice_client: Discord voice client

        Returns:
            New volume level
        """
        state = self.get_state(guild_id)
        state.volume = max(0.0, min(1.0, volume))

        # Update current source volume if playing
        if voice_client.source and hasattr(voice_client.source, 'volume'):
            voice_client.source.volume = state.volume

        return state.volume

    def shuffle_queue(self, guild_id: int) -> int:
        """Shuffle the queue.

        Args:
            guild_id: Discord guild ID

        Returns:
            Number of songs shuffled
        """
        import random
        state = self.get_state(guild_id)

        if len(state.queue) < 2:
            return 0

        # Convert to list, shuffle, convert back
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = deque(queue_list)

        return len(queue_list)

    def clear_queue(self, guild_id: int) -> int:
        """Clear the queue (keeps current song).

        Args:
            guild_id: Discord guild ID

        Returns:
            Number of songs cleared
        """
        state = self.get_state(guild_id)
        count = len(state.queue)
        state.queue.clear()
        return count

    def toggle_loop(self, guild_id: int) -> bool:
        """Toggle loop mode for current song.

        Args:
            guild_id: Discord guild ID

        Returns:
            New loop state
        """
        state = self.get_state(guild_id)
        state.loop = not state.loop
        if state.loop:
            state.loop_queue = False  # Disable queue loop
        return state.loop

    def toggle_loop_queue(self, guild_id: int) -> bool:
        """Toggle loop mode for entire queue.

        Args:
            guild_id: Discord guild ID

        Returns:
            New loop queue state
        """
        state = self.get_state(guild_id)
        state.loop_queue = not state.loop_queue
        if state.loop_queue:
            state.loop = False  # Disable single loop
        return state.loop_queue

    def get_queue(self, guild_id: int) -> List[Song]:
        """Get the current queue.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of songs in queue
        """
        state = self.get_state(guild_id)
        return list(state.queue)

    def get_now_playing(self, guild_id: int) -> Optional[Song]:
        """Get the currently playing song.

        Args:
            guild_id: Discord guild ID

        Returns:
            Current song or None
        """
        state = self.get_state(guild_id)
        return state.current

    def cleanup(self, guild_id: int):
        """Clean up state for a guild.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self.states:
            del self.states[guild_id]
            logger.info(f"Cleaned up music state for guild {guild_id}")
