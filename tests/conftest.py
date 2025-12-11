"""Pytest configuration and shared fixtures for all tests."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import discord


# ============================================================================
# Event Loop Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Mock Discord Objects
# ============================================================================

@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = Mock(spec=discord.Client)
    bot.user = Mock(spec=discord.User)
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.user.bot = True
    bot.command_prefix = "!"
    bot.loop = asyncio.get_event_loop()
    return bot


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild."""
    guild = Mock(spec=discord.Guild)
    guild.id = 987654321
    guild.name = "Test Server"
    guild.members = []
    guild.voice_client = None
    return guild


@pytest.fixture
def mock_channel():
    """Create a mock Discord text channel."""
    channel = Mock(spec=discord.TextChannel)
    channel.id = 111222333
    channel.name = "test-channel"
    channel.guild = Mock(spec=discord.Guild)
    channel.guild.id = 987654321
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def mock_user():
    """Create a mock Discord user."""
    user = Mock(spec=discord.User)
    user.id = 555666777
    user.name = "TestUser"
    user.display_name = "TestUser"
    user.bot = False
    return user


@pytest.fixture
def mock_message(mock_user, mock_channel):
    """Create a mock Discord message."""
    message = Mock(spec=discord.Message)
    message.id = 444555666
    message.author = mock_user
    message.channel = mock_channel
    message.guild = mock_channel.guild
    message.content = "Test message"
    message.mentions = []
    message.attachments = []
    message.embeds = []
    message.is_system.return_value = False
    message.reference = None
    return message


@pytest.fixture
def mock_interaction(mock_user, mock_channel):
    """Create a mock Discord interaction (for slash commands)."""
    interaction = Mock(spec=discord.Interaction)
    interaction.user = mock_user
    interaction.channel = mock_channel
    interaction.guild = mock_channel.guild
    interaction.response = Mock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()
    return interaction


# ============================================================================
# Service Mocks
# ============================================================================

@pytest.fixture
def mock_ollama_service():
    """Create a mock Ollama service."""
    from services.interfaces import LLMInterface

    service = AsyncMock(spec=LLMInterface)
    service.chat = AsyncMock(return_value="Mock LLM response")
    service.chat_stream = AsyncMock()
    service.generate = AsyncMock(return_value="Mock generation")
    service.is_available = AsyncMock(return_value=True)
    service.model = "test-model"
    service.host = "http://localhost:11434"

    return service


@pytest.fixture
def mock_tts_service():
    """Create a mock TTS service."""
    from services.interfaces import TTSInterface

    service = AsyncMock(spec=TTSInterface)
    service.generate = AsyncMock(return_value=Path("/tmp/test.mp3"))
    service.list_voices = AsyncMock(return_value=[
        {"name": "voice1", "description": "Test Voice 1"}
    ])
    service.is_available = AsyncMock(return_value=True)

    return service


@pytest.fixture
def mock_stt_service():
    """Create a mock STT service."""
    from services.interfaces import STTInterface

    service = AsyncMock(spec=STTInterface)
    service.transcribe_file = AsyncMock(return_value={
        "text": "Test transcription",
        "language": "en",
        "segments": []
    })
    service.transcribe_audio_data = AsyncMock(return_value={
        "text": "Test transcription",
        "language": "en",
        "segments": []
    })
    service.is_available.return_value = True

    return service


@pytest.fixture
def mock_rvc_service():
    """Create a mock RVC service."""
    from services.interfaces import RVCInterface

    service = AsyncMock(spec=RVCInterface)
    service.convert = AsyncMock(return_value=Path("/tmp/converted.mp3"))
    service.list_models = AsyncMock(return_value=["model1", "model2"])
    service.is_enabled = AsyncMock(return_value=True)
    service.health_check = AsyncMock(return_value=True)

    return service


@pytest.fixture
def mock_history_manager():
    """Create a mock chat history manager."""
    from utils.helpers import ChatHistoryManager

    manager = AsyncMock(spec=ChatHistoryManager)
    manager.load_history = AsyncMock(return_value=[])
    manager.add_message = AsyncMock()
    manager.clear_history = AsyncMock()
    manager.build_multi_user_context = Mock(return_value="")
    manager.get_conversation_participants = Mock(return_value=[])

    return manager


@pytest.fixture
def mock_user_profiles():
    """Create a mock user profiles service."""
    service = AsyncMock()
    service.load_profile = AsyncMock(return_value={
        "user_id": 555666777,
        "username": "TestUser",
        "interaction_count": 0,
        "facts": [],
        "affection": 0.5
    })
    service.save_profile = AsyncMock()
    service.get_user_context = AsyncMock(return_value="Test user context")
    service.get_affection_context = Mock(return_value="")
    service.learn_from_conversation = AsyncMock()
    service.update_affection = AsyncMock()

    return service


# ============================================================================
# Temporary Files & Directories
# ============================================================================

@pytest.fixture
def temp_audio_file(tmp_path):
    """Create a temporary audio file for testing."""
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"fake audio data")
    return audio_file


@pytest.fixture
def temp_text_file(tmp_path):
    """Create a temporary text file for testing."""
    text_file = tmp_path / "test.txt"
    text_file.write_text("Test content")
    return text_file


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


# ============================================================================
# Configuration Overrides
# ============================================================================

@pytest.fixture
def test_config():
    """Provide test configuration overrides."""
    return {
        "OLLAMA_HOST": "http://localhost:11434",
        "OLLAMA_MODEL": "test-model",
        "CHAT_HISTORY_ENABLED": True,
        "CACHE_ENABLED": False,  # Disable caching in tests
        "AUTO_REPLY_ENABLED": False,
        "VISION_ENABLED": False,
        "RVC_ENABLED": False,
    }


# ============================================================================
# Async Helpers
# ============================================================================

@pytest.fixture
def async_return():
    """Helper to create async functions that return values."""
    def _async_return(value):
        async def _inner(*args, **kwargs):
            return value
        return _inner
    return _async_return


@pytest.fixture
def async_raise():
    """Helper to create async functions that raise exceptions."""
    def _async_raise(exception):
        async def _inner(*args, **kwargs):
            raise exception
        return _inner
    return _async_raise
