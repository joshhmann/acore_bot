"""Thinking Service - Cheap/fast LLM for internal decisions."""
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)


class ThinkingService:
    """Lightweight LLM service for quick internal decisions.
    
    Uses a cheaper/faster model for tasks like:
    - Spam detection
    - Intent classification
    - Yes/No decisions
    - Routing choices
    
    Falls back to main LLM if no thinking model is configured.
    """

    def __init__(self, main_llm=None):
        """Initialize thinking service.
        
        Args:
            main_llm: Main LLM service to fall back to
        """
        self.main_llm = main_llm
        self._thinking_llm = None
        self._initialized = False

    async def initialize(self):
        """Initialize the thinking model if configured."""
        if self._initialized:
            return
            
        if Config.THINKING_MODEL:
            try:
                provider = Config.THINKING_MODEL_PROVIDER or Config.LLM_PROVIDER
                
                if provider == "openrouter":
                    from services.llm.openrouter import OpenRouterService
                    self._thinking_llm = OpenRouterService(
                        api_key=Config.OPENROUTER_API_KEY,
                        model=Config.THINKING_MODEL,
                        base_url=Config.OPENROUTER_URL,
                        temperature=0.3,  # Lower temp for decisions
                        max_tokens=50,    # Short responses
                    )
                    logger.info(f"Thinking model initialized: {Config.THINKING_MODEL} (OpenRouter)")
                    
                elif provider == "ollama":
                    from services.llm.ollama import OllamaService
                    self._thinking_llm = OllamaService(
                        host=Config.OLLAMA_HOST,
                        model=Config.THINKING_MODEL,
                        temperature=0.3,
                        max_tokens=50,
                    )
                    logger.info(f"Thinking model initialized: {Config.THINKING_MODEL} (Ollama)")
                    
            except Exception as e:
                logger.warning(f"Failed to initialize thinking model, using main LLM: {e}")
                self._thinking_llm = None
        else:
            logger.info("No thinking model configured, using main LLM for decisions")
            
        self._initialized = True

    async def decide(self, prompt: str, default: bool = False) -> bool:
        """Make a yes/no decision.
        
        Args:
            prompt: Decision prompt (should ask for YES or NO)
            default: Default value if decision fails
            
        Returns:
            True for YES, False for NO
        """
        try:
            llm = self._thinking_llm or self.main_llm
            if not llm:
                return default
                
            response = await llm.generate(prompt, max_tokens=10)
            response = response.strip().upper()
            
            if "YES" in response:
                return True
            elif "NO" in response:
                return False
            else:
                return default
                
        except Exception as e:
            logger.warning(f"Thinking decision failed: {e}")
            return default

    async def classify(self, prompt: str, options: list[str], default: str = None) -> str:
        """Classify into one of several options.
        
        Args:
            prompt: Classification prompt
            options: List of valid options
            default: Default if classification fails
            
        Returns:
            Selected option string
        """
        try:
            llm = self._thinking_llm or self.main_llm
            if not llm:
                return default or options[0]
            
            # Add options to prompt
            options_str = ", ".join(options)
            full_prompt = f"{prompt}\n\nRespond with ONLY one of: {options_str}"
            
            response = await llm.generate(full_prompt, max_tokens=20)
            response = response.strip().upper()
            
            # Find matching option
            for opt in options:
                if opt.upper() in response:
                    return opt
                    
            return default or options[0]
            
        except Exception as e:
            logger.warning(f"Thinking classification failed: {e}")
            return default or options[0]

    async def quick_generate(self, prompt: str, max_tokens: int = 100) -> str:
        """Quick generation using thinking model.
        
        Args:
            prompt: Generation prompt
            max_tokens: Max tokens to generate
            
        Returns:
            Generated text
        """
        try:
            llm = self._thinking_llm or self.main_llm
            if not llm:
                return ""
                
            return await llm.generate(prompt, max_tokens=max_tokens)
            
        except Exception as e:
            logger.warning(f"Quick generate failed: {e}")
            return ""
