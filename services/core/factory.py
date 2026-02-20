"""Service factory for initializing bot services."""

import logging
from typing import Optional

from config import Config

# Core interfaces for adapter architecture
from core.interfaces import SimpleEventBus

# Adapters
from adapters.discord import DiscordInputAdapter, DiscordOutputAdapter
from adapters.cli import CLIInputAdapter, CLIOutputAdapter

# LLM domain
from services.llm.ollama import OllamaService
from services.llm.fallback import LLMFallbackManager, ModelConfig

# Voice domain
from services.voice.tts import TTSService
from services.voice.rvc import UnifiedRVCService
from services.voice.listener import EnhancedVoiceListener
from services.clients.stt_client import ParakeetAPIService

# Memory domain
from services.memory.long_term import MemoryManager
from services.memory.summarizer import ConversationSummarizer
from services.memory.rag import RAGService
from services.memory.conversation import MultiTurnConversationManager

# Persona domain
from services.persona.system import PersonaSystem
from services.persona.rl import RLService

# Discord domain
from services.discord.profiles import UserProfileService
from services.discord.web_search import WebSearchService

# Core domain
from services.core.metrics import MetricsService

# LLM tools
from services.llm.tools import EnhancedToolSystem

from utils.helpers import ChatHistoryManager

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory class to initialize and manage services."""

    def __init__(self, bot):
        self.bot = bot
        self.services = {}
        self._event_bus: Optional[SimpleEventBus] = None
        self._adapters: dict = {}

    def create_event_bus(self) -> SimpleEventBus:
        """Create and return the EventBus instance."""
        if self._event_bus is None:
            self._event_bus = SimpleEventBus()
            logger.info("EventBus created")
        return self._event_bus

    def create_discord_adapter(
        self,
        token: Optional[str] = None,
        command_prefix: str = "!",
        existing_bot=None,
    ) -> tuple[DiscordInputAdapter, DiscordOutputAdapter]:
        """Create Discord input/output adapters.

        Args:
            token: Discord bot token. If None, uses Config.DISCORD_TOKEN.
            command_prefix: Prefix for text commands.
            existing_bot: If provided, use this existing bot for output adapter.

        Returns:
            Tuple of (DiscordInputAdapter, DiscordOutputAdapter).
        """
        from discord.ext import commands

        token = token or Config.DISCORD_TOKEN

        if existing_bot:
            input_adapter = DiscordInputAdapter(
                token=token,
                command_prefix=command_prefix,
            )
            output_adapter = DiscordOutputAdapter(bot=existing_bot)
        else:
            input_adapter = DiscordInputAdapter(
                token=token,
                command_prefix=command_prefix,
            )
            output_adapter = DiscordOutputAdapter(bot=input_adapter.bot)

        self._adapters["discord_input"] = input_adapter
        self._adapters["discord_output"] = output_adapter

        logger.info("Discord adapters created")
        return input_adapter, output_adapter

    def create_cli_adapter(self) -> tuple[CLIInputAdapter, CLIOutputAdapter]:
        """Create CLI input/output adapters.

        Returns:
            Tuple of (CLIInputAdapter, CLIOutputAdapter).
        """
        input_adapter = CLIInputAdapter()
        output_adapter = CLIOutputAdapter()

        self._adapters["cli_input"] = input_adapter
        self._adapters["cli_output"] = output_adapter

        logger.info("CLI adapters created")
        return input_adapter, output_adapter

    def create_services(self, event_bus: Optional[SimpleEventBus] = None):
        """Initialize all configured services.

        Args:
            event_bus: Optional EventBus instance for adapter-based mode.
                      If provided, stores EventBus for dependency injection.
        """
        logger.info("Initializing services via ServiceFactory...")

        # Store event_bus if provided (for adapter-based mode)
        if event_bus:
            self._event_bus = event_bus
            logger.info("EventBus wired to ServiceFactory")

        # 1. Metrics (Core)
        self.services["metrics"] = MetricsService()

        # 2. LLM Services
        self._init_llm()

        # 3. Audio Services (TTS, RVC, STT)
        self._init_audio()

        # 4. Data Services (History, Profiles, RAG, Memory)
        self._init_data()

        # 5. Feature Services (Search, Reminders, Notes)
        self._init_features()

        # 6. AI/Persona Systems
        self._init_ai_systems()

        return self.services

    def _init_llm(self):
        """Initialize LLM and related services."""
        # Main LLM Provider
        if Config.LLM_PROVIDER == "openrouter":
            from services.llm.openrouter import OpenRouterService

            self.services["ollama"] = OpenRouterService(
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
        else:
            self.services["ollama"] = OllamaService(
                host=Config.OLLAMA_HOST,
                model=Config.OLLAMA_MODEL,
                temperature=Config.OLLAMA_TEMPERATURE,
                max_tokens=Config.OLLAMA_MAX_TOKENS,
                min_p=Config.OLLAMA_MIN_P,
                top_k=Config.OLLAMA_TOP_K,
                repeat_penalty=Config.OLLAMA_REPEAT_PENALTY,
            )

        # LLM Fallback
        if Config.LLM_FALLBACK_ENABLED and Config.LLM_FALLBACK_MODELS:
            fallback_models = []
            for i, model_spec in enumerate(Config.LLM_FALLBACK_MODELS.split(",")):
                parts = model_spec.strip().split(":")
                model_name = parts[0].strip()
                cost_tier = parts[1].strip() if len(parts) > 1 else "free"
                max_temp = 1.0 if "amazon/nova" in model_name.lower() else None

                fallback_models.append(
                    ModelConfig(
                        name=model_name,
                        provider=Config.LLM_PROVIDER,
                        max_temp=max_temp,
                        cost_tier=cost_tier,
                        priority=i,
                    )
                )
            self.services["llm_fallback"] = LLMFallbackManager(fallback_models)
        else:
            self.services["llm_fallback"] = None

        # Thinking Service (cheap/fast model for decisions)
        from services.llm.thinking import ThinkingService

        self.services["thinking"] = ThinkingService(main_llm=self.services["ollama"])

    def _init_audio(self):
        """Initialize audio services."""
        # TTS
        self.services["tts"] = TTSService(
            engine=Config.TTS_ENGINE,
            kokoro_voice=Config.KOKORO_VOICE,
            kokoro_speed=Config.KOKORO_SPEED,
            kokoro_api_url=Config.KOKORO_API_URL,
            luxtts_api_url=Config.LUXTTS_API_URL,
            luxtts_voice=Config.LUXTTS_VOICE,
            luxtts_speed=Config.LUXTTS_SPEED,
            qwen3tts_api_url=Config.QWEN3TTS_API_URL,
            qwen3tts_voice=Config.QWEN3TTS_VOICE,
            qwen3tts_speed=Config.QWEN3TTS_SPEED,
            qwen3tts_language=Config.QWEN3TTS_LANGUAGE,
            supertonic_voice=Config.SUPERTONIC_VOICE,
            supertonic_steps=Config.SUPERTONIC_STEPS,
            supertonic_speed=Config.SUPERTONIC_SPEED,
        )

        # RVC
        if Config.RVC_ENABLED:
            self.services["rvc"] = UnifiedRVCService(
                mode=Config.RVC_MODE,
                model_path=Config.RVC_MODEL_PATH,
                default_model=Config.DEFAULT_RVC_MODEL,
                device=Config.RVC_DEVICE,
                webui_url=Config.RVC_WEBUI_URL,
            )
        else:
            self.services["rvc"] = None

        # STT (Speech-to-Text) - Parakeet API only
        self.services["stt"] = None
        self.services["enhanced_voice_listener"] = None

        # Parakeet (API)
        if Config.STT_ENGINE == "parakeet" and Config.PARAKEET_ENABLED:
            parakeet = ParakeetAPIService(
                api_url=Config.PARAKEET_API_URL,
                language=Config.PARAKEET_LANGUAGE,
            )
            if parakeet.is_available():
                self.services["stt"] = parakeet

        # Enhanced Listener
        if self.services["stt"]:
            trigger_words = [
                w.strip() for w in Config.VOICE_BOT_TRIGGER_WORDS.split(",")
            ]
            self.services["enhanced_voice_listener"] = EnhancedVoiceListener(
                stt_service=self.services["stt"],
                silence_threshold=Config.WHISPER_SILENCE_THRESHOLD,
                energy_threshold=Config.VOICE_ENERGY_THRESHOLD,
                bot_trigger_words=trigger_words,
            )

    def _init_data(self):
        """Initialize data management services."""
        # Chat History
        self.services["history"] = ChatHistoryManager(
            history_dir=Config.CHAT_HISTORY_DIR,
            max_messages=Config.CHAT_HISTORY_MAX_MESSAGES,
            metrics=self.services.get("metrics"),
        )

        # User Profiles
        if Config.USER_PROFILES_ENABLED:
            self.services["profiles"] = UserProfileService(
                profiles_dir=Config.USER_PROFILES_PATH,
                ollama_service=self.services["ollama"],
            )
        else:
            self.services["profiles"] = None

        # RAG
        if Config.RAG_ENABLED:
            self.services["rag"] = RAGService(
                documents_path=Config.RAG_DOCUMENTS_PATH,
                vector_store_path=Config.RAG_VECTOR_STORE,
                top_k=Config.RAG_TOP_K,
            )
        else:
            self.services["rag"] = None

        # Memory Manager
        if Config.MEMORY_CLEANUP_ENABLED:
            self.services["memory_manager"] = MemoryManager(
                temp_dir=Config.TEMP_DIR,
                chat_history_dir=Config.CHAT_HISTORY_DIR,
                max_temp_file_age_hours=Config.MAX_TEMP_FILE_AGE_HOURS,
                max_history_age_days=Config.MAX_HISTORY_AGE_DAYS,
            )

        # Summarizer
        if Config.CONVERSATION_SUMMARIZATION_ENABLED and self.services.get("rag"):
            self.services["summarizer"] = ConversationSummarizer(
                ollama=self.services["ollama"],
                rag=self.services["rag"],
                summary_dir=Config.SUMMARY_DIR,
            )
        else:
            self.services["summarizer"] = None

    def _init_features(self):
        """Initialize feature services."""
        # Web Search
        if Config.WEB_SEARCH_ENABLED:
            self.services["web_search"] = WebSearchService(
                engine=Config.WEB_SEARCH_ENGINE,
                max_results=Config.WEB_SEARCH_MAX_RESULTS,
            )
        else:
            self.services["web_search"] = None

        # Notes (TODO: NotesService not yet implemented)
        # if Config.NOTES_ENABLED:
        #     self.services["notes"] = NotesService(self.bot)
        # else:
        #     self.services["notes"] = None

        # Conversation Manager
        self.services["conversation_manager"] = MultiTurnConversationManager()

    def _init_ai_systems(self):
        """Initialize high-level AI systems."""
        self.services["persona_system"] = None
        self.services["compiled_persona"] = None
        self.services["tool_system"] = None

        if Config.USE_PERSONA_SYSTEM:
            try:
                persona_system = PersonaSystem()
                tool_system = EnhancedToolSystem()

                # Compile persona
                compiled_persona = persona_system.compile_persona(
                    Config.CHARACTER, Config.FRAMEWORK
                )

                if compiled_persona:
                    self.services["persona_system"] = persona_system
                    self.services["compiled_persona"] = compiled_persona
                    self.services["tool_system"] = tool_system
                    logger.info(
                        f"AI Persona loaded: {compiled_persona.character.display_name}"
                    )
            except Exception as e:
                logger.error(f"Error initializing persona system: {e}")

        # Initialize Agent Orchestration System
        self._init_agents()

        # Initialize Bot-to-Bot Conversation System
        self._init_conversation_system()

        # Initialize RL Service
        self._init_rl_service()

    def _init_rl_service(self):
        """Initialize RL (Reinforcement Learning) Service."""
        if Config.RL_ENABLED:
            try:
                rl_service = RLService(bot=self.bot, config=Config)
                self.services["rl"] = rl_service
                logger.info("RL Service initialized")
            except Exception as e:
                logger.error(f"Error initializing RL service: {e}")
                self.services["rl"] = None
        else:
            self.services["rl"] = None
            logger.info("RL Service disabled (RL_ENABLED=false)")

    def _init_agents(self):
        """Initialize agent orchestration system."""
        from services.agents import AgentManager, RoutingStrategy

        # Map config strategy string to enum
        strategy_map = {
            "highest_confidence": RoutingStrategy.HIGHEST_CONFIDENCE,
            "round_robin": RoutingStrategy.ROUND_ROBIN,
            "priority_based": RoutingStrategy.PRIORITY_BASED,
            "fallback_chain": RoutingStrategy.FALLBACK_CHAIN,
        }
        routing_strategy = strategy_map.get(
            Config.AGENT_ROUTING_STRATEGY.lower(),
            RoutingStrategy.HIGHEST_CONFIDENCE,
        )

        agent_manager = AgentManager(
            routing_strategy=routing_strategy,
            min_confidence=Config.AGENT_MIN_CONFIDENCE,
            health_check_interval=Config.AGENT_HEALTH_CHECK_INTERVAL,
            enable_chaining=Config.AGENT_CHAINING_ENABLED,
        )

        # Get dependencies for agent initialization
        web_search = self.services.get("web_search")
        ollama = self.services.get("ollama")
        conversation_manager = self.services.get("conversation_manager")

        # Initialize agents with dependencies (chat_cog, behavior_engine set later)
        agent_manager.initialize(
            web_search_service=web_search,
            llm_service=ollama,
            chat_cog=None,
            behavior_engine=None,
            persona_router=None,
            image_api_key=Config.IMAGE_GENERATION_API_KEY
            if Config.IMAGE_GENERATION_ENABLED
            else None,
        )

        self.services["agent_manager"] = agent_manager
        logger.info("Agent orchestration system initialized")

    def _init_conversation_system(self):
        """Initialize bot-to-bot conversation system."""
        from services.conversation.orchestrator import BotConversationOrchestrator
        from services.conversation.persistence import ConversationPersistence
        from pathlib import Path

        persistence = ConversationPersistence(Config.DATA_DIR / "bot_conversations")

        persona_router = self.services.get("persona_router")
        behavior_engine = self.services.get("behavior_engine")
        llm_service = self.services.get("ollama")
        rag_service = self.services.get("rag")

        if persona_router and behavior_engine and llm_service:
            orchestrator = BotConversationOrchestrator(
                persona_router=persona_router,
                behavior_engine=behavior_engine,
                llm_service=llm_service,
                rag_service=rag_service,
                persistence=persistence,
            )

            self.services["conversation_orchestrator"] = orchestrator
            self.services["conversation_persistence"] = persistence
            logger.info("Bot-to-bot conversation system initialized")
        else:
            self.services["conversation_orchestrator"] = None
            self.services["conversation_persistence"] = None
            logger.warning(
                "Bot-to-bot conversation system not initialized (missing dependencies)"
            )
