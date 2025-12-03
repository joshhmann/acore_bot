#!/usr/bin/env python3
"""Discord bot with Ollama chat and TTS/RVC voice features.

A simple, clean Discord bot that:
- Uses Ollama for AI-powered conversations
- Generates speech with TTS (Kokoro or Supertonic)
- Applies voice conversion with RVC
- Plays audio in Discord voice channels
- Manages memory and storage automatically
- Summarizes conversations for long-term memory
- Supports voice activity detection (Whisper STT)
- Streams responses in real-time
"""
import discord
from discord.ext import commands
import logging
import sys
import asyncio
from pathlib import Path

from config import Config
from services.ollama import OllamaService
from services.tts import TTSService
from services.rvc_unified import UnifiedRVCService
from services.user_profiles import UserProfileService
from services.memory_manager import MemoryManager
from services.conversation_summarizer import ConversationSummarizer
from services.rag import RAGService
from services.whisper_stt import WhisperSTTService, VoiceActivityDetector
from services.parakeet_stt import ParakeetSTTService
from services.enhanced_voice_listener import EnhancedVoiceListener
from utils.helpers import ChatHistoryManager
from cogs.chat import ChatCog
from cogs.voice import VoiceCog
from cogs.music import MusicCog
from services.web_dashboard import WebDashboard
from services.ambient_mode import AmbientMode
from services.naturalness import NaturalnessService
from services.reminders import RemindersService
from services.notes import NotesService
from services.proactive_callbacks import ProactiveCallbacksSystem
from services.curiosity_system import CuriositySystem
from services.pattern_learner import PatternLearner
from cogs.reminders import RemindersCog
from cogs.notes import NotesCog
from services.web_search import WebSearchService
from services.trivia import TriviaService
from cogs.trivia import TriviaCog
from services.conversation_manager import MultiTurnConversationManager
from services.persona_system import PersonaSystem
from services.ai_decision_engine import AIDecisionEngine
from services.enhanced_tools import EnhancedToolSystem
from services.metrics import MetricsService

# Setup logging
# Configure logging with rotating file handler
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
log_path = Path(Config.LOG_FILE_PATH)
log_path.parent.mkdir(parents=True, exist_ok=True)

# Set up handlers
handlers = [logging.StreamHandler(sys.stdout)]
if Config.LOG_TO_FILE:
    file_handler = RotatingFileHandler(
        Config.LOG_FILE_PATH,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    handlers.append(file_handler)

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)

# Suppress noisy logs from third-party libraries (unless in DEBUG mode)
if Config.LOG_LEVEL != "DEBUG":
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("nemo_logger").setLevel(logging.WARNING)
    logging.getLogger("nemo").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Log the logging configuration
logger.info(f"Logging configured: Level={Config.LOG_LEVEL}, File={Config.LOG_TO_FILE}, Path={Config.LOG_FILE_PATH}")


class OllamaBot(commands.Bot):
    """Main bot class."""

    def __init__(self):
        """Initialize the bot."""
        intents = discord.Intents.default()
        intents.message_content = True  # Required for message events
        intents.voice_states = True  # Required for voice features
        intents.presences = True  # Required for activity awareness
        intents.members = True  # Required for member tracking

        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,  # We'll create our own
        )

        # Track background tasks for clean shutdown
        self.background_tasks = set()

        # Initialize metrics service (FIRST so other services can use it)
        self.metrics = MetricsService()
        logger.info("Metrics service initialized")

        # Initialize services
        # Initialize LLM service based on provider
        if Config.LLM_PROVIDER == "openrouter":
            from services.openrouter import OpenRouterService
            self.ollama = OpenRouterService(
                api_key=Config.OPENROUTER_API_KEY,
                model=Config.OPENROUTER_MODEL,
                base_url=Config.OPENROUTER_URL,
                temperature=Config.OLLAMA_TEMPERATURE,
                max_tokens=Config.OLLAMA_MAX_TOKENS,
                min_p=Config.OLLAMA_MIN_P,
                top_k=Config.OLLAMA_TOP_K,
                repeat_penalty=Config.OLLAMA_REPEAT_PENALTY,
                frequency_penalty=Config.LLM_FREQUENCY_PENALTY,
                presence_penalty=Config.LLM_PRESENCE_PENALTY,
                top_p=Config.LLM_TOP_P,
                timeout=Config.OPENROUTER_TIMEOUT,
                stream_timeout=Config.OPENROUTER_STREAM_TIMEOUT,
            )
            logger.info(f"Using OpenRouter Provider with model: {Config.OPENROUTER_MODEL}")
        else:
            self.ollama = OllamaService(
                host=Config.OLLAMA_HOST,
                model=Config.OLLAMA_MODEL,
                temperature=Config.OLLAMA_TEMPERATURE,
                max_tokens=Config.OLLAMA_MAX_TOKENS,
                min_p=Config.OLLAMA_MIN_P,
                top_k=Config.OLLAMA_TOP_K,
                repeat_penalty=Config.OLLAMA_REPEAT_PENALTY,
            )
            logger.info(f"Using Ollama Provider with model: {Config.OLLAMA_MODEL}")

        self.tts = TTSService(
            engine=Config.TTS_ENGINE,
            kokoro_voice=Config.KOKORO_VOICE,
            kokoro_speed=Config.KOKORO_SPEED,
            kokoro_api_url=Config.KOKORO_API_URL,
            supertonic_voice=Config.SUPERTONIC_VOICE,
            supertonic_steps=Config.SUPERTONIC_STEPS,
            supertonic_speed=Config.SUPERTONIC_SPEED,
        )

        self.rvc = None
        if Config.RVC_ENABLED:
            self.rvc = UnifiedRVCService(
                mode=Config.RVC_MODE,
                model_path=Config.RVC_MODEL_PATH,
                default_model=Config.DEFAULT_RVC_MODEL,
                device=Config.RVC_DEVICE,
                webui_url=Config.RVC_WEBUI_URL,
            )

        self.history_manager = ChatHistoryManager(
            history_dir=Config.CHAT_HISTORY_DIR,
            max_messages=Config.CHAT_HISTORY_MAX_MESSAGES,
            metrics=self.metrics,
        )

        # Initialize user profiles if enabled
        self.user_profiles = None
        if Config.USER_PROFILES_ENABLED:
            self.user_profiles = UserProfileService(
                profiles_dir=Config.USER_PROFILES_PATH,
                ollama_service=self.ollama  # Pass ollama for AI-powered learning
            )
            logger.info("User profiles enabled")

        # Initialize RAG service if enabled
        self.rag = None
        if Config.RAG_ENABLED:
            self.rag = RAGService(
                documents_path=Config.RAG_DOCUMENTS_PATH,
                vector_store_path=Config.RAG_VECTOR_STORE,
                top_k=Config.RAG_TOP_K,
            )
            logger.info("RAG service initialized")

        # Initialize memory manager
        self.memory_manager = None
        if Config.MEMORY_CLEANUP_ENABLED:
            self.memory_manager = MemoryManager(
                temp_dir=Config.TEMP_DIR,
                chat_history_dir=Config.CHAT_HISTORY_DIR,
                max_temp_file_age_hours=Config.MAX_TEMP_FILE_AGE_HOURS,
                max_history_age_days=Config.MAX_HISTORY_AGE_DAYS,
            )
            logger.info("Memory manager initialized")

        # Initialize conversation summarizer if enabled
        self.summarizer = None
        if Config.CONVERSATION_SUMMARIZATION_ENABLED and self.rag:
            self.summarizer = ConversationSummarizer(
                ollama=self.ollama,
                rag=self.rag,
                summary_dir=Config.SUMMARY_DIR,
            )
            logger.info("Conversation summarizer initialized")

        # Initialize STT (Speech-to-Text) services
        self.whisper = None
        self.parakeet = None
        self.stt_service = None  # The active STT service
        self.voice_activity_detector = None
        self.enhanced_voice_listener = None

        # Smart STT Initialization: Only load the selected engine to save VRAM
        if Config.STT_ENGINE == "parakeet" and Config.PARAKEET_ENABLED:
            logger.info("Initializing Parakeet STT (Primary)...")
            self.parakeet = ParakeetSTTService(
                model_name=Config.PARAKEET_MODEL,
                device=Config.PARAKEET_DEVICE,
                language=Config.PARAKEET_LANGUAGE,
            )
            if self.parakeet.is_available():
                self.stt_service = self.parakeet
                logger.info(f"Using Parakeet as primary STT engine (model: {Config.PARAKEET_MODEL})")
            else:
                logger.warning("Parakeet STT failed to initialize. Falling back to Whisper if enabled.")
                self.parakeet = None

        # Fallback or Primary Whisper Initialization
        if (not self.stt_service and Config.WHISPER_ENABLED) or (Config.STT_ENGINE == "whisper" and Config.WHISPER_ENABLED):
            logger.info("Initializing Whisper STT...")
            self.whisper = WhisperSTTService(
                model_size=Config.WHISPER_MODEL_SIZE,
                device=Config.WHISPER_DEVICE,
                language=Config.WHISPER_LANGUAGE,
            )
            if self.whisper.is_available():
                self.stt_service = self.whisper
                logger.info(f"Using Whisper as STT engine (model: {Config.WHISPER_MODEL_SIZE})")
            else:
                logger.warning("Whisper STT not available - install with: pip install faster-whisper")
                self.whisper = None

        # Initialize voice listeners if we have an STT service
        if self.stt_service:
            # Legacy voice activity detector (for backwards compatibility with Whisper)
            if self.whisper:
                self.voice_activity_detector = VoiceActivityDetector(
                    whisper_stt=self.whisper,
                    temp_dir=Config.TEMP_DIR,
                    silence_threshold=Config.WHISPER_SILENCE_THRESHOLD,
                    max_recording_duration=Config.MAX_RECORDING_DURATION,
                )

            # Enhanced voice listener with smart detection (works with both engines)
            trigger_words = [w.strip() for w in Config.VOICE_BOT_TRIGGER_WORDS.split(",")]
            self.enhanced_voice_listener = EnhancedVoiceListener(
                stt_service=self.stt_service,
                silence_threshold=Config.WHISPER_SILENCE_THRESHOLD,
                energy_threshold=Config.VOICE_ENERGY_THRESHOLD,
                bot_trigger_words=trigger_words,
            )

            logger.info(f"Enhanced voice listener initialized with {Config.STT_ENGINE} engine")

        # Initialize Web Dashboard
        self.web_dashboard = WebDashboard(self)

        # Initialize Naturalness Service
        self.naturalness = None
        if Config.NATURALNESS_ENABLED:
            self.naturalness = NaturalnessService(self)
            logger.info("Naturalness service initialized (reactions, activity awareness, natural timing)")

        # Initialize Mood System
        self.mood_system = None
        if Config.MOOD_SYSTEM_ENABLED:
            from services.mood_system import MoodSystem
            self.mood_system = MoodSystem()
            # Connect mood system to naturalness if both are enabled
            if self.naturalness:
                self.naturalness.mood = self.mood_system
            logger.info("Mood system initialized (dynamic emotional states)")

        # Initialize Reminders Service
        self.reminders_service = None
        if Config.REMINDERS_ENABLED:
            self.reminders_service = RemindersService(self)
            logger.info("Reminders service initialized")

        # Initialize Notes Service
        self.notes_service = None
        if Config.NOTES_ENABLED:
            self.notes_service = NotesService(self)
            logger.info("Notes service initialized")

        # Initialize Web Search Service
        self.web_search = None
        if Config.WEB_SEARCH_ENABLED:
            self.web_search = WebSearchService(
                engine=Config.WEB_SEARCH_ENGINE,
                max_results=Config.WEB_SEARCH_MAX_RESULTS,
            )
            logger.info(f"Web search service created (engine: {Config.WEB_SEARCH_ENGINE})")

        # Initialize Trivia Service
        self.trivia_service = None
        if Config.TRIVIA_ENABLED:
            self.trivia_service = TriviaService(
                data_dir=Config.DATA_DIR,
                web_search=self.web_search,
            )
            logger.info("Trivia service initialized")

        # Initialize Multi-Turn Conversation Manager
        self.conversation_manager = MultiTurnConversationManager()
        logger.info("Multi-turn conversation manager initialized")

        # Initialize AI-First Persona System
        self.persona_system = None
        self.decision_engine = None
        self.current_persona = None
        self.tool_system = None

        if Config.USE_PERSONA_SYSTEM:
            try:
                self.persona_system = PersonaSystem()
                self.tool_system = EnhancedToolSystem()

                # Compile persona from character + framework
                self.current_persona = self.persona_system.compile_persona(
                    Config.CHARACTER,
                    Config.FRAMEWORK
                )

                if self.current_persona:
                    # Initialize decision engine with persona
                    self.decision_engine = AIDecisionEngine(self.ollama, self.tool_system)
                    self.decision_engine.set_persona(self.current_persona)
                    logger.info(f"✨ AI-First Persona loaded: {self.current_persona.persona_id}")
                    logger.info(f"   Character: {self.current_persona.character.display_name}")
                    logger.info(f"   Framework: {self.current_persona.framework.name}")
                else:
                    logger.error(f"Failed to compile persona: {Config.CHARACTER}_{Config.FRAMEWORK}")
            except Exception as e:
                logger.error(f"Error initializing persona system: {e}")
                logger.info("Falling back to traditional mode")

        # Initialize Proactive Callbacks System
        self.callbacks_system = ProactiveCallbacksSystem()
        logger.info("Proactive callbacks system initialized")

        # Initialize Curiosity System
        self.curiosity_system = CuriositySystem(self.ollama)
        if self.current_persona:
            self.curiosity_system.set_persona(self.current_persona)
        logger.info("Curiosity system initialized")

        # Initialize Pattern Learner (Learning & Adaptation)
        self.pattern_learner = PatternLearner()
        logger.info("Pattern learner initialized with user adaptation")

        # Initialize Ambient Mode (after PersonaSystem so we can pass persona components)
        self.ambient_mode = None
        if Config.AMBIENT_MODE_ENABLED:
            self.ambient_mode = AmbientMode(
                self,
                self.ollama,
                persona_system=self.persona_system,
                compiled_persona=self.current_persona,
                callbacks_system=self.callbacks_system
            )
            logger.info("Ambient mode initialized with persona awareness")

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        logger.info("Setting up bot...")

        # Initialize Web Search if enabled
        if self.web_search:
            await self.web_search.initialize()
            logger.info("Web search initialized")

        # Initialize Trivia if enabled
        if self.trivia_service:
            await self.trivia_service.initialize()
            logger.info("Trivia service initialized")

        # Initialize RAG if enabled
        if self.rag:
            await self.rag.initialize()
            logger.info("RAG service initialized (documents loaded)")

        # Initialize LLM Service
        await self.ollama.initialize()
        healthy = await self.ollama.check_health()

        if not healthy:
            provider_name = "OpenRouter" if Config.LLM_PROVIDER == "openrouter" else "Ollama"
            logger.warning(
                f"Could not connect to {provider_name}. "
                "Check your configuration and internet connection."
            )
        else:
            model_name = Config.OPENROUTER_MODEL if Config.LLM_PROVIDER == "openrouter" else Config.OLLAMA_MODEL
            logger.info(f"Connected to LLM Provider ({Config.LLM_PROVIDER}) - Model: {model_name}")

        # Load cogs
        await self.add_cog(
            ChatCog(
                self,
                self.ollama,
                self.history_manager,
                self.user_profiles,
                self.summarizer,
                self.web_search,
                self.naturalness,
                self.rag,
                self.conversation_manager,
                persona_system=self.persona_system,
                compiled_persona=self.current_persona,
                decision_engine=self.decision_engine,
                callbacks_system=self.callbacks_system,
                curiosity_system=self.curiosity_system,
                pattern_learner=self.pattern_learner,
            )
        )
        logger.info("Loaded ChatCog")

        await self.add_cog(
            VoiceCog(
                self,
                self.tts,
                self.rvc,
                self.voice_activity_detector,
                self.enhanced_voice_listener,
            )
        )
        logger.info("Loaded VoiceCog")

        await self.add_cog(MusicCog(self))
        logger.info("Loaded MusicCog")

        # Load RemindersCog
        if self.reminders_service:
            await self.add_cog(RemindersCog(self, self.reminders_service))
            logger.info("Loaded RemindersCog")

        # Load NotesCog
        if self.notes_service:
            await self.add_cog(NotesCog(self, self.notes_service))
            logger.info("Loaded NotesCog")

        # Load TriviaCog
        if self.trivia_service:
            await self.add_cog(TriviaCog(self, self.trivia_service))
            logger.info("Loaded TriviaCog")

        # Load additional modular cogs
        # These cogs split up the massive chat.py into organized modules
        await self.load_extension("cogs.memory_commands")
        # await self.load_extension("cogs.persona_commands")  # DEPRECATED: Use character_commands instead
        await self.load_extension("cogs.character_commands")  # AI-First character system
        await self.load_extension("cogs.profile_commands")
        await self.load_extension("cogs.search_commands")
        await self.load_extension("cogs.intent_commands")  # Custom intent management

        # Load Interactive Cogs
        await self.load_extension("cogs.game_helper")
        await self.load_extension("cogs.games")
        await self.load_extension("cogs.help")

        # Load EventListenersCog for natural reactions
        from cogs.event_listeners import EventListenersCog
        await self.add_cog(EventListenersCog(self))
        logger.info("Loaded EventListenersCog")

        # Load SystemCog
        await self.load_extension("cogs.system")
        logger.info("Loaded SystemCog")

        # Sync commands (for slash commands)
        await self.tree.sync()
        logger.info("Synced command tree")

        # Start background tasks
        if self.memory_manager:
            task = asyncio.create_task(
                self.memory_manager.start_background_cleanup(
                    interval_hours=Config.MEMORY_CLEANUP_INTERVAL_HOURS
                )
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

            logger.info("Started background memory cleanup task")

        # Start background profile saver
        if self.user_profiles:
            await self.user_profiles.start_background_saver()

        # Start Web Dashboard
        await self.web_dashboard.start(port=8080)

        # Start Ambient Mode
        if self.ambient_mode:
            await self.ambient_mode.start()

        # Start Reminders background task
        if self.reminders_service:
            await self.reminders_service.start()

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/chat | /speak",
            )
        )

        # Start metrics auto-save (configurable interval)
        if Config.METRICS_ENABLED:
            try:
                # In DEBUG mode, save more frequently (every 10 minutes) for easier analysis
                if Config.LOG_LEVEL == "DEBUG":
                    interval_minutes = 10
                    logger.info("DEBUG mode detected: Metrics will save every 10 minutes for detailed analysis")
                else:
                    interval_minutes = Config.METRICS_SAVE_INTERVAL_MINUTES

                interval_hours = interval_minutes / 60.0
                metrics_task = self.metrics.start_auto_save(interval_hours=interval_hours)
                self.background_tasks.add(metrics_task)
                logger.info(f"Metrics auto-save started (every {interval_minutes} minutes)")

                # Start hourly reset to prevent memory leak from unbounded active user/channel sets
                reset_task = self.metrics.start_hourly_reset()
                self.background_tasks.add(reset_task)
                logger.info("Metrics hourly reset started (prevents memory leak)")
            except Exception as e:
                logger.error(f"Failed to start metrics auto-save: {e}")
        else:
            logger.info("Metrics auto-save disabled via config")

        logger.info("Bot is ready!")

    async def on_message(self, message):
        """Handle messages for proactive engagement."""
        # Process commands first
        await self.process_commands(message)

        # Don't respond to self
        if message.author == self.user:
            return

        # Don't respond to other bots
        if message.author.bot:
            return

        # Check if ChatCog should handle this message (implicit chat)
        chat_cog = self.get_cog("ChatCog")
        if chat_cog:
            # We need to check if check_and_handle_message exists (it might not if cog failed to load or old version)
            if hasattr(chat_cog, 'check_and_handle_message'):
                handled = await chat_cog.check_and_handle_message(message)
                if handled:
                    return

        # Check for AI-first spontaneous thoughts (framework-based)
        if self.decision_engine and Config.AMBIENT_CHANNELS:
            if message.channel.id in Config.AMBIENT_CHANNELS:
                try:
                    spontaneous_thought = await self.decision_engine.get_spontaneous_thought()
                    if spontaneous_thought:
                        await message.channel.send(spontaneous_thought)
                        logger.info(f"Sent spontaneous thought: {spontaneous_thought[:50]}...")
                        return  # Don't process other reactions if we sent a thought
                except Exception as e:
                    logger.error(f"Failed to generate spontaneous thought: {e}")

        # Enable natural reactions (emojis)
        if self.naturalness:
            await self.naturalness.on_message(message)

        # Check for proactive engagement
        if self.ambient_mode and Config.PROACTIVE_ENGAGEMENT_ENABLED:
            # Get current mood if available
            current_mood = None
            if self.naturalness and self.naturalness.mood:
                current_mood = self.naturalness.mood.current_mood.mood.value

            # Check if bot should jump in
            engagement = await self.ambient_mode.on_message(message, mood=current_mood)

            if engagement:
                # Bot wants to jump in!
                try:
                    await message.channel.send(engagement)
                    logger.info(f"Proactively engaged in {message.channel.name}")

                    # Update dashboard if available
                    if self.web_dashboard:
                        self.web_dashboard.set_status("Proactive", f"Engaged: {engagement[:30]}...")
                except Exception as e:
                    logger.error(f"Failed to send proactive engagement: {e}")



    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands

        logger.error(f"Command error: {error}")

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {error}")
        else:
            await ctx.send(f"❌ An error occurred: {error}")

    async def close(self):
        """Cleanup when bot is shutting down."""
        logger.info("Shutting down bot...")

        # Cancel all background tasks
        if self.background_tasks:
            logger.info(f"Cancelling {len(self.background_tasks)} background tasks...")
            for task in self.background_tasks:
                task.cancel()

            # Wait for all tasks to complete cancellation
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            logger.info("All background tasks cancelled")

        # Cleanup cog background tasks
        chat_cog = self.get_cog("ChatCog")
        if chat_cog and hasattr(chat_cog, 'cleanup_tasks'):
            await chat_cog.cleanup_tasks()

        # Cleanup services
        if self.user_profiles:
            await self.user_profiles.stop_background_saver()

        if self.ambient_mode:
            await self.ambient_mode.stop()

        if self.web_dashboard:
            await self.web_dashboard.stop()

        if self.reminders_service:
            await self.reminders_service.stop()

        await self.ollama.close()

        await super().close()


def main():
    """Main entry point."""
    logger.info("Starting Discord Ollama Bot...")

    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file!")
        sys.exit(1)

    # Create and run bot
    bot = OllamaBot()

    try:
        bot.run(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token! Please check DISCORD_TOKEN in .env")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
