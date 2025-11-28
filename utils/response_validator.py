"""Response validation to catch AI hallucinations."""
import re
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Validates AI responses and fixes common hallucinations."""
    
    @staticmethod
    def validate_and_fix_time(response: str) -> Tuple[str, bool]:
        """Check if response contains wrong time and fix it.
        
        Args:
            response: AI-generated response
            
        Returns:
            Tuple of (fixed_response, was_fixed)
        """
        # Get actual current time
        now = datetime.now()
        correct_time_12h = now.strftime('%I:%M %p').lstrip('0')  # Remove leading zero
        correct_time_24h = now.strftime('%H:%M')
        
        # Pattern to match times like "2:47 AM", "11:30 PM", etc.
        time_pattern = r'\b(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)\b'
        
        matches = list(re.finditer(time_pattern, response))
        
        if not matches:
            return response, False
        
        # Check if any mentioned time is wrong
        fixed = False
        fixed_response = response
        
        for match in matches:
            mentioned_time = match.group(0)
            
            # Skip if it's the correct time
            if mentioned_time.upper() == correct_time_12h.upper():
                continue
            
            # Check if it's a relative time calculation (e.g., "38 minutes ago was 11:44 PM")
            # Look for context words before/after
            context_start = max(0, match.start() - 50)
            context_end = min(len(response), match.end() + 50)
            context = response[context_start:context_end].lower()
            
            # If context suggests it's a calculation, leave it alone
            if any(word in context for word in ['ago', 'was', 'will be', 'in', 'at', 'by', 'before', 'after', 'until']):
                continue
            
            # This appears to be claiming the CURRENT time - fix it
            logger.warning(f"AI hallucinated time: '{mentioned_time}' (actual: {correct_time_12h})")
            fixed_response = fixed_response.replace(mentioned_time, correct_time_12h)
            fixed = True
        
        return fixed_response, fixed
    
    @staticmethod
    def check_character_break(response: str) -> Tuple[bool, Optional[str]]:
        """Check if response breaks character (for roleplay personas).

        Args:
            response: AI-generated response

        Returns:
            Tuple of (breaks_character, detected_phrase)
        """
        # Forbidden phrases that break character
        forbidden_phrases = [
            "as an ai",
            "i'm an ai",
            "i am an ai",
            "as a language model",
            "i'm a language model",
            "i don't have the ability",
            "i cannot",
            "my primary function",
            "i'm here to help",
            "i'm here to assist",
            "i'm happy to help but",
            "use your phone's alarm",
            "ask a virtual assistant",
            "let's focus on having productive",
            "let's have a respectful conversation",
            "this is a space for",
            "i don't intend any judgment",
            "that's all part of being human",
        ]

        response_lower = response.lower()

        for phrase in forbidden_phrases:
            if phrase in response_lower:
                logger.warning(f"Character break detected: '{phrase}'")
                return True, phrase

        return False, None

    @staticmethod
    def clean_thinking_process(response: str) -> str:
        """Remove internal thinking process and system artifacts from response.
        
        Removes:
        - <think>...</think> blocks
        - [SPONTANEITY CHANCE: ...] and similar internal state tags
        - Leaked system prompt text
        
        Args:
            response: AI-generated response
            
        Returns:
            Cleaned response
        """
        from config import Config
        
        # Check if cleaning is enabled
        if not Config.CLEAN_THINKING_OUTPUT:
            return response

        # 1. Remove <think>...</think> blocks (DeepSeek R1 style)
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # 2. Remove internal state tags like [SPONTANEITY CHANCE: 5%]
        # Matches [UPPERCASE: Value]
        response = re.sub(r'\[[A-Z_\-\s]+:.*?\]', '', response)
        
        # 3. Remove specific leaked system prompt lines
        # "You're in the Discord voice channel..."
        if "You're in the Discord voice channel" in response:
            response = re.sub(r"You're in the Discord voice channel.*?(?=\n\n|\Z)", "", response, flags=re.DOTALL)
            
        # "You look around the chat channel..."
        if "You look around the chat channel" in response:
            response = re.sub(r"You look around the chat channel.*?(?=\n\n|\Z)", "", response, flags=re.DOTALL)

        # "You can choose to do one of the following:"
        if "You can choose to do one of the following:" in response:
             response = re.sub(r"You can choose to do one of the following:.*?(?=\n\n|\Z)", "", response, flags=re.DOTALL)

        # 4. Remove "System:" or "Assistant:" prefixes if they leak
        response = re.sub(r'^(System|Assistant|Dagoth Ur):', '', response, flags=re.MULTILINE)
        
        return response.strip()

    @staticmethod
    def validate_response(response: str) -> str:
        """Run all validations on a response.

        Args:
            response: AI-generated response

        Returns:
            Validated and potentially fixed response
        """
        # Clean thinking process and artifacts FIRST
        response = ResponseValidator.clean_thinking_process(response)

        # Fix time hallucinations
        response, time_fixed = ResponseValidator.validate_and_fix_time(response)

        if time_fixed:
            logger.info("Fixed AI time hallucination in response")

        # Check for character breaks (just log for now, don't fix)
        breaks_character, phrase = ResponseValidator.check_character_break(response)
        if breaks_character:
            logger.error(f"⚠️ CHARACTER BREAK DETECTED: Response contains '{phrase}'")
            logger.error(f"Response preview: {response[:200]}...")

        return response
