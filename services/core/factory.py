"""Service factory for initializing bot services."""
import logging
from config import Config

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

# Discord domain
from services.discord.profiles import UserProfileService
from services.discord.web_search import WebSearchService
from services.discord.reminders import RemindersService
from services.discord.notes import NotesService

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

    def create_services(self):
        """Initialize all configured services."""
        logger.info("Initializing services via ServiceFactory...")

        # 1. Metrics (Core)
        self.services['metrics'] = MetricsService()

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
            self.services['ollama'] = OpenRouterService(
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
            self.services['ollama'] = OllamaService(
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
            for i, model_spec in enumerate(Config.LLM_FALLBACK_MODELS.split(',')):
                parts = model_spec.strip().split(':')
                model_name = parts[0].strip()
                cost_tier = parts[1].strip() if len(parts) > 1 else "free"
                max_temp = 1.0 if "amazon/nova" in model_name.lower() else None

                fallback_models.append(ModelConfig(
                    name=model_name,
                    provider=Config.LLM_PROVIDER,
                    max_temp=max_temp,
                    cost_tier=cost_tier,
                    priority=i
                ))
            self.services['llm_fallback'] = LLMFallbackManager(fallback_models)
        else:
            self.services['llm_fallback'] = None

    def _init_audio(self):
        """Initialize audio services."""
        # TTS
        self.services['tts'] = TTSService(
            engine=Config.TTS_ENGINE,
            kokoro_voice=Config.KOKORO_VOICE,
            kokoro_speed=Config.KOKORO_SPEED,
            kokoro_api_url=Config.KOKORO_API_URL,
            supertonic_voice=Config.SUPERTONIC_VOICE,
            supertonic_steps=Config.SUPERTONIC_STEPS,
            supertonic_speed=Config.SUPERTONIC_SPEED,
        )

        # RVC
        if Config.RVC_ENABLED:
            self.services['rvc'] = UnifiedRVCService(
                mode=Config.RVC_MODE,
                model_path=Config.RVC_MODEL_PATH,
                default_model=Config.DEFAULT_RVC_MODEL,
                device=Config.RVC_DEVICE,
                webui_url=Config.RVC_WEBUI_URL,
            )
        else:
            self.services['rvc'] = None

        # STT (Speech-to-Text) - Parakeet API only
        self.services['stt'] = None
        self.services['enhanced_voice_listener'] = None

        # Parakeet (API)
        if Config.STT_ENGINE == "parakeet" and Config.PARAKEET_ENABLED:
            parakeet = ParakeetAPIService(
                api_url=Config.PARAKEET_API_URL,
                language=Config.PARAKEET_LANGUAGE,
            )
            if parakeet.is_available():
                self.services['stt'] = parakeet

        # Enhanced Listener
        if self.services['stt']:
            trigger_words = [w.strip() for w in Config.VOICE_BOT_TRIGGER_WORDS.split(",")]
            self.services['enhanced_voice_listener'] = EnhancedVoiceListener(
                stt_service=self.services['stt'],
                silence_threshold=Config.WHISPER_SILENCE_THRESHOLD,
                energy_threshold=Config.VOICE_ENERGY_THRESHOLD,
                bot_trigger_words=trigger_words,
            )

    def _init_data(self):
        """Initialize data management services."""
        # Chat History
        self.services['history'] = ChatHistoryManager(
            history_dir=Config.CHAT_HISTORY_DIR,
            max_messages=Config.CHAT_HISTORY_MAX_MESSAGES,
            metrics=self.services.get('metrics'),
        )

        # User Profiles
        if Config.USER_PROFILES_ENABLED:
            self.services['profiles'] = UserProfileService(
                profiles_dir=Config.USER_PROFILES_PATH,
                ollama_service=self.services['ollama']
            )
        else:
            self.services['profiles'] = None

        # RAG
        if Config.RAG_ENABLED:
            self.services['rag'] = RAGService(
                documents_path=Config.RAG_DOCUMENTS_PATH,
                vector_store_path=Config.RAG_VECTOR_STORE,
                top_k=Config.RAG_TOP_K,
            )
        else:
            self.services['rag'] = None

        # Memory Manager
        if Config.MEMORY_CLEANUP_ENABLED:
            self.services['memory_manager'] = MemoryManager(
                temp_dir=Config.TEMP_DIR,
                chat_history_dir=Config.CHAT_HISTORY_DIR,
                max_temp_file_age_hours=Config.MAX_TEMP_FILE_AGE_HOURS,
                max_history_age_days=Config.MAX_HISTORY_AGE_DAYS,
            )

        # Summarizer
        if Config.CONVERSATION_SUMMARIZATION_ENABLED and self.services.get('rag'):
            self.services['summarizer'] = ConversationSummarizer(
                ollama=self.services['ollama'],
                rag=self.services['rag'],
                summary_dir=Config.SUMMARY_DIR,
            )
        else:
            self.services['summarizer'] = None

    def _init_features(self):
        """Initialize feature services."""
        # Web Search
        if Config.WEB_SEARCH_ENABLED:
            self.services['web_search'] = WebSearchService(
                engine=Config.WEB_SEARCH_ENGINE,
                max_results=Config.WEB_SEARCH_MAX_RESULTS,
            )
        else:
            self.services['web_search'] = None

        # Reminders
        if Config.REMINDERS_ENABLED:
            self.services['reminders'] = RemindersService(self.bot)
        else:
            self.services['reminders'] = None

        # Notes
        if Config.NOTES_ENABLED:
            self.services['notes'] = NotesService(self.bot)
        else:
            self.services['notes'] = None

        # Conversation Manager
        self.services['conversation_manager'] = MultiTurnConversationManager()

    def _init_ai_systems(self):
        """Initialize high-level AI systems."""
        self.services['persona_system'] = None
        self.services['compiled_persona'] = None
        self.services['tool_system'] = None

        if Config.USE_PERSONA_SYSTEM:
            try:
                persona_system = PersonaSystem()
                tool_system = EnhancedToolSystem()

                # Compile persona
                compiled_persona = persona_system.compile_persona(
                    Config.CHARACTER,
                    Config.FRAMEWORK
                )

                if compiled_persona:
                    self.services['persona_system'] = persona_system
                    self.services['compiled_persona'] = compiled_persona
                    self.services['tool_system'] = tool_system
                    logger.info(f"AI Persona loaded: {compiled_persona.character.display_name}")
            except Exception as e:
                logger.error(f"Error initializing persona system: {e}")
