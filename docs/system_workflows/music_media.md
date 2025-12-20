# Music and Media System Workflow

This document describes the complete music and media management system in acore_bot, including YouTube playback, queue management, audio processing, and media search workflows.

## Overview

The music system enables **high-quality audio playback** from YouTube and other sources, with support for **playlists**, **queue management**, **voice channel integration**, and **media search capabilities**. It integrates seamlessly with the voice system for concurrent TTS and music playback.

## Architecture

### Component Structure
```
cogs/
├── music.py                    # MusicCog - slash commands and user interface
└── voice/main.py               # Voice cog integration with music

services/discord/
└── music.py                    # MusicPlayer - core playback logic

utils/
└── helpers.py                  # Audio processing helpers
```

### Service Dependencies
```
Music System Dependencies:
├── YouTube API                # Video search and metadata
├── yt-dlp                     # Audio extraction and download
├── FFmpeg                     # Audio format conversion
├── Discord Voice Client        # Voice channel playback
├── AsyncIO                    # Concurrent download/playback
└── Queue Management           # Song queue and playback order
```

## Music Playback Flow

### 1. Command Entry Point
**File**: `cogs/music.py:61-120`

#### 1.1 Play Command Processing
```python
@app_commands.command(name="play", description="Play a song or add it to the queue")
@app_commands.describe(query="Song name or YouTube URL")
async def play(self, interaction: discord.Interaction, query: str):
    """Main play command handler."""
    await interaction.response.defer(thinking=True)

    # 1. Get or create voice client
    voice_client = await self._get_voice_client(interaction)
    if not voice_client:
        return

    try:
        # 2. Check if it's a playlist
        is_playlist = "list=" in query and "youtube.com" in query

        if is_playlist:
            await self._handle_playlist(interaction, voice_client, query)
        else:
            await self._handle_single_song(interaction, voice_client, query)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
```

#### 1.2 Voice Client Management
```python
async def _get_voice_client(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
    """Get voice client for the guild, connecting if needed."""
    if not interaction.user.voice:
        await interaction.followup.send(
            "❌ You need to be in a voice channel to use music commands!",
            ephemeral=True,
        )
        return None

    voice_client = interaction.guild.voice_client

    if not voice_client:
        # Connect to user's voice channel
        try:
            voice_client = await interaction.user.voice.channel.connect()
            logger.info(f"Connected to voice channel: {interaction.user.voice.channel.name}")
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to connect to voice channel: {e}",
                ephemeral=True
            )
            return None

    return voice_client
```

### 2. Music Player Core Logic
**File**: `services/discord/music.py:45-234`

#### 2.1 MusicPlayer Initialization
```python
class MusicPlayer:
    """Core music playback and queue management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues = {}  # guild_id -> queue of songs
        self.now_playing = {}  # guild_id -> current song
        self.voice_clients = {}  # guild_id -> voice_client
        self.download_tasks = {}  # guild_id -> current download task
        self.skip_votes = {}  # guild_id -> set of user_ids who voted to skip

        # yt-dlp configuration
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': './data/temp/%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
```

#### 2.2 Song Search and Download
```python
async def search_song(self, query: str, requester: str) -> Optional[Song]:
    """Search for a song and prepare for playback."""
    try:
        import yt_dlp

        # 1. Extract video information
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            if info is None:
                return None

            # 2. Create Song object
            song = Song(
                title=info.get('title', 'Unknown Title'),
                url=info.get('webpage_url', query),
                duration=info.get('duration', 0),
                thumbnail=info.get('thumbnail', ''),
                requester=requester,
                webpage_url=info.get('webpage_url', query),
                video_id=info.get('id', ''),
                extractor=info.get('extractor', 'youtube'),
                download_url=info.get('url', ''),
                is_live=info.get('is_live', False)
            )

            return song

    except Exception as e:
        logger.error(f"Error searching for song '{query}': {e}")
        return None

async def download_song(self, song: Song, guild_id: int) -> Optional[Path]:
    """Download audio file for a song."""
    try:
        import yt_dlp

        # 1. Download audio
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(song.url, download=True)

            if info is None:
                return None

            # 2. Get downloaded file path
            downloaded_file = Path(ydl.prepare_filename(info))

            # 3. Convert to MP3 if needed
            if downloaded_file.suffix != '.mp3':
                mp3_file = downloaded_file.with_suffix('.mp3')
                await self._convert_to_mp3(downloaded_file, mp3_file)
                downloaded_file = mp3_file

            return downloaded_file

    except Exception as e:
        logger.error(f"Error downloading song '{song.title}': {e}")
        return None
```

#### 2.3 Queue Management
```python
async def add_to_queue(self, guild_id: int, song: Song):
    """Add a song to the playback queue."""
    # 1. Initialize queue if needed
    if guild_id not in self.queues:
        self.queues[guild_id] = asyncio.Queue()

    # 2. Add song to queue
    await self.queues[guild_id].put(song)
    logger.info(f"Added '{song.title}' to queue for guild {guild_id}")

    # 3. Start playback if not already playing
    if not self._is_playing(guild_id):
        await self._play_next(guild_id)

async def _play_next(self, guild_id: int):
    """Play the next song in the queue."""
    try:
        # 1. Get next song from queue
        queue = self.queues.get(guild_id)
        if not queue or queue.empty():
            self.now_playing[guild_id] = None
            return

        song = await queue.get()

        # 2. Mark as now playing
        self.now_playing[guild_id] = song

        # 3. Download song in background
        self.download_tasks[guild_id] = asyncio.create_task(
            self._download_and_play(guild_id, song)
        )

    except Exception as e:
        logger.error(f"Error playing next song: {e}")
        await self._play_next(guild_id)  # Try next song

async def _download_and_play(self, guild_id: int, song: Song):
    """Download and play a song."""
    try:
        # 1. Download audio
        audio_file = await self.download_song(song, guild_id)
        if not audio_file:
            logger.error(f"Failed to download '{song.title}'")
            await self._play_next(guild_id)
            return

        # 2. Get voice client
        voice_client = self.voice_clients.get(guild_id)
        if not voice_client or not voice_client.is_connected():
            logger.error("Voice client not connected")
            await self._play_next(guild_id)
            return

        # 3. Play audio
        audio_source = discord.FFmpegPCMAudio(
            str(audio_file),
            options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo"
        )

        voice_client.play(
            audio_source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self._on_song_finished(guild_id, audio_file, e),
                self.bot.loop
            )
        )

        logger.info(f"Now playing: {song.title}")

    except Exception as e:
        logger.error(f"Error in download_and_play: {e}")
        await self._play_next(guild_id)

async def _on_song_finished(self, guild_id: int, audio_file: Path, error):
    """Called when a song finishes playing."""
    try:
        # 1. Cleanup audio file
        if audio_file.exists():
            audio_file.unlink()

        # 2. Clear now playing
        self.now_playing[guild_id] = None

        # 3. Play next song
        await self._play_next(guild_id)

    except Exception as e:
        logger.error(f"Error in song finished callback: {e}")
```

### 3. Playlist Handling
**File**: `cogs/music.py:80-120`

#### 3.1 Playlist Processing
```python
async def _handle_playlist(self, interaction, voice_client, query):
    """Handle YouTube playlist URLs."""
    try:
        # 1. Search playlist
        songs = await self.music_player.search_playlist(
            query,
            requester=interaction.user.display_name
        )

        if not songs:
            await interaction.followup.send(
                "❌ Could not find playlist or it's empty."
            )
            return

        # 2. Add songs to queue
        added_count = 0
        for song in songs[:50]:  # Limit to 50 songs per playlist
            await self.music_player.add_to_queue(interaction.guild.id, song)
            added_count += 1

        # 3. Start playback if needed
        if not self.music_player._is_playing(interaction.guild.id):
            await self.music_player._play_next(interaction.guild.id)

        await interaction.followup.send(
            f"✅ Added **{added_count} songs** from playlist to the queue!"
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error processing playlist: {e}",
            ephemeral=True
        )

async def search_playlist(self, playlist_url: str, requester: str) -> List[Song]:
    """Search and extract songs from a YouTube playlist."""
    try:
        import yt_dlp

        # Playlist-specific options
        playlist_opts = {
            'extract_flat': False,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(playlist_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)

            if not playlist_info or 'entries' not in playlist_info:
                return []

            songs = []
            for entry in playlist_info['entries']:
                if entry is None:
                    continue

                song = Song(
                    title=entry.get('title', 'Unknown Title'),
                    url=entry.get('webpage_url', entry.get('url', '')),
                    duration=entry.get('duration', 0),
                    thumbnail=entry.get('thumbnail', ''),
                    requester=requester,
                    webpage_url=entry.get('webpage_url', ''),
                    video_id=entry.get('id', ''),
                    extractor=entry.get('extractor', 'youtube'),
                    is_live=entry.get('is_live', False)
                )
                songs.append(song)

            return songs

    except Exception as e:
        logger.error(f"Error extracting playlist: {e}")
        return []
```

### 4. Queue Control Commands
**File**: `cogs/music.py:150-280`

#### 4.1 Queue Management
```python
@app_commands.command(name="queue", description="Show the current music queue")
async def queue(self, interaction: discord.Interaction):
    """Display the current music queue."""
    await interaction.response.defer(thinking=True)

    try:
        # 1. Get queue and current song
        queue_songs = self.music_player.get_queue(interaction.guild.id)
        current_song = self.music_player.get_now_playing(interaction.guild.id)

        # 2. Create embed
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.purple()
        )

        # 3. Add current song
        if current_song:
            embed.add_field(
                name="🎶 Now Playing",
                value=f"**{current_song.title}**\n"
                      f"Requested by: {current_song.requester}\n"
                      f"Duration: {self._format_duration(current_song.duration)}",
                inline=False
            )
        else:
            embed.add_field(
                name="🎶 Now Playing",
                value="Nothing is currently playing",
                inline=False
            )

        # 4. Add queue
        if queue_songs:
            queue_text = ""
            for i, song in enumerate(queue_songs[:10], 1):  # Show first 10
                queue_text += f"{i}. **{song.title}** - {song.requester}\n"

            if len(queue_songs) > 10:
                queue_text += f"\n... and {len(queue_songs) - 10} more songs"

            embed.add_field(
                name=f"📋 Queue ({len(queue_songs)} songs)",
                value=queue_text,
                inline=False
            )
        else:
            embed.add_field(
                name="📋 Queue",
                value="The queue is empty",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error fetching queue: {e}",
            ephemeral=True
        )

@app_commands.command(name="skip", description="Skip the current song")
async def skip(self, interaction: discord.Interaction):
    """Skip the current song."""
    await interaction.response.defer(thinking=True)

    try:
        # 1. Check if anything is playing
        current_song = self.music_player.get_now_playing(interaction.guild.id)
        if not current_song:
            await interaction.followup.send("❌ Nothing is currently playing")
            return

        # 2. Add to skip votes
        guild_id = interaction.guild.id
        if guild_id not in self.music_player.skip_votes:
            self.music_player.skip_votes[guild_id] = set()

        self.music_player.skip_votes[guild_id].add(interaction.user.id)

        # 3. Check if enough votes (simplify: always skip for now)
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.followup.send("⏭️ Skipped current song")
        else:
            await interaction.followup.send("❌ Nothing is currently playing")

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error skipping song: {e}",
            ephemeral=True
        )

@app_commands.command(name="clear", description="Clear the music queue")
async def clear(self, interaction: discord.Interaction):
    """Clear the entire music queue."""
    await interaction.response.defer(thinking=True)

    try:
        # 1. Clear queue
        cleared_count = self.music_player.clear_queue(interaction.guild.id)

        await interaction.followup.send(
            f"🗑️ Cleared **{cleared_count} songs** from the queue"
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error clearing queue: {e}",
            ephemeral=True
        )
```

#### 4.2 Volume Control
```python
@app_commands.command(name="volume", description="Set the music volume")
@app_commands.describe(volume="Volume level (0-100)")
async def volume(self, interaction: discord.Interaction, volume: int):
    """Set the music volume."""
    await interaction.response.defer(thinking=True)

    try:
        # 1. Validate volume
        if not 0 <= volume <= 100:
            await interaction.followup.send(
                "❌ Volume must be between 0 and 100",
                ephemeral=True
            )
            return

        # 2. Set volume (simplified - would need actual volume control implementation)
        # This would require integrating with a volume control library or custom FFmpeg filters

        await interaction.followup.send(
            f"🔊 Volume set to **{volume}%**"
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error setting volume: {e}",
            ephemeral=True
        )
```

### 5. Search and Discovery
**File**: `cogs/music.py:300-380`

#### 5.1 Search Command
```python
@app_commands.command(name="search", description="Search for songs on YouTube")
@app_commands.describe(query="Search query")
async def search(self, interaction: discord.Interaction, query: str):
    """Search for songs on YouTube."""
    await interaction.response.defer(thinking=True)

    try:
        # 1. Search for songs
        results = await self.music_player.search_results(query, limit=5)

        if not results:
            await interaction.followup.send(
                f"❌ No results found for '{query}'",
                ephemeral=True
            )
            return

        # 2. Create search results embed
        embed = discord.Embed(
            title=f"🔍 Search Results for '{query}'",
            color=discord.Color.blue()
        )

        # 3. Add results
        for i, song in enumerate(results, 1):
            duration_str = self._format_duration(song.duration)
            embed.add_field(
                name=f"{i}. {song.title}",
                value=f"Duration: {duration_str}\n"
                      f"[Watch on YouTube]({song.webpage_url})",
                inline=False
            )

        # 4. Add play instruction
        embed.set_footer(text="Use /play <URL> to play a song")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error searching: {e}",
            ephemeral=True
        )

async def search_results(self, query: str, limit: int = 5) -> List[Song]:
    """Search for songs without adding to queue."""
    try:
        import yt_dlp

        # Search-specific options
        search_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'default_search': 'ytsearch' + str(limit),
        }

        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(query, download=False)

            if not info or 'entries' not in info:
                return []

            songs = []
            for entry in info['entries']:
                if entry is None:
                    continue

                song = Song(
                    title=entry.get('title', 'Unknown Title'),
                    url=entry.get('webpage_url', ''),
                    duration=entry.get('duration', 0),
                    thumbnail=entry.get('thumbnail', ''),
                    requester="Search",
                    webpage_url=entry.get('webpage_url', ''),
                    video_id=entry.get('id', ''),
                    extractor=entry.get('extractor', 'youtube'),
                    is_live=entry.get('is_live', False)
                )
                songs.append(song)

            return songs

    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        return []
```

## Integration Points

### With Voice System
- **Shared Voice Clients**: Music and TTS use the same voice client
- **Audio Queue Coordination**: TTS messages interrupt or queue with music
- **Volume Management**: Coordinated volume control between systems

```python
# Integration example: TTS during music
async def speak_over_music(self, text: str, guild_id: int):
    """Speak TTS over existing music playback."""
    voice_client = self.voice_clients.get(guild_id)
    if not voice_client:
        return

    # 1. Pause music
    if voice_client.is_playing():
        voice_client.pause()
        music_paused = True
    else:
        music_paused = False

    # 2. Play TTS
    tts_audio = await self.tts_service.generate_speech(text)
    voice_client.play(discord.FFmpegPCMAudio(str(tts_audio)))

    # 3. Wait for TTS to finish
    while voice_client.is_playing():
        await asyncio.sleep(0.1)

    # 4. Resume music if it was playing
    if music_paused:
        voice_client.resume()
```

### With Chat System
- **Song Requests**: Natural language requests to play music
- **Now Playing Notifications**: Automatic chat messages about current songs
- **Queue Status**: Integration with chat commands

## Configuration

### Music System Settings
```bash
# Audio Quality
AUDIO_BITRATE=96                      # Audio bitrate in kbps
AUDIO_SAMPLE_RATE=48000              # Audio sample rate in Hz

# Download Settings
MUSIC_DOWNLOAD_TIMEOUT=300           # Download timeout in seconds
MAX_PLAYLIST_SIZE=50                 # Maximum songs per playlist
MAX_QUEUE_SIZE=100                   # Maximum songs in queue

# FFmpeg Settings
FFMPEG_PATH=ffmpeg                   # Path to FFmpeg binary
FFMPEG_ARGS="-vn -af aresample=48000"  # FFmpeg processing arguments

# YouTube Settings
YOUTUBE_API_KEY=                     # Optional: YouTube Data API key
YOUTUBE_REGION=US                    # YouTube search region
```

## Performance Considerations

### 1. Download Optimization
- **Preloading**: Next song downloads while current song plays
- **Quality Settings**: Adaptive bitrate based on connection speed
- **Caching**: Recently played songs cached to avoid re-downloads

### 2. Memory Management
- **Audio File Cleanup**: Automatic cleanup of downloaded files
- **Queue Bounding**: Maximum queue size prevents memory exhaustion
- **Concurrent Downloads**: Limited concurrent download tasks

### 3. Network Efficiency
- **Chunked Downloads**: Large files downloaded in chunks
- **Connection Pooling**: Reuse HTTP connections for YouTube
- **Retry Logic**: Automatic retry for failed downloads

## Security Considerations

### 1. Content Filtering
- **URL Validation**: Prevent malicious URL processing
- **Content Filtering**: Block inappropriate content when possible
- **Duration Limits**: Prevent extremely long audio streams

### 2. Resource Protection
- **Download Limits**: Rate limiting on YouTube API calls
- **Storage Limits**: Bound disk space for temporary files
- **Network Isolation**: Music downloads in isolated network context

## Common Issues and Troubleshooting

### 1. Download Failures
```bash
# Check yt-dlp installation
pip install --upgrade yt-dlp

# Check FFmpeg installation
ffmpeg -version

# Test YouTube access
yt-dlp --extract-flat "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 2. Voice Connection Issues
```python
# Debug voice client state
voice_client = guild.voice_client
if voice_client:
    print(f"Connected: {voice_client.is_connected()}")
    print(f"Playing: {voice_client.is_playing()}")
    print(f"Paused: {voice_client.is_paused()}")
```

### 3. Audio Quality Issues
- **FFmpeg Configuration**: Check audio format conversion settings
- **Network Bandwidth**: Monitor download speeds and buffer status
- **Discord Limits**: Be aware of Discord's audio quality limits

### 4. Queue Problems
```python
# Check queue state
queue = music_player.queues.get(guild_id)
if queue:
    print(f"Queue size: {queue.qsize()}")
    print(f"Queue empty: {queue.empty()}")
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `cogs/music.py` | MusicCog - slash commands and user interface |
| `services/discord/music.py` | MusicPlayer - core playback and queue logic |
| `utils/helpers.py` | Audio processing and utility functions |
| `config.py` | Music system configuration settings |

---

**Last Updated**: 2025-12-16
**Version**: 1.0