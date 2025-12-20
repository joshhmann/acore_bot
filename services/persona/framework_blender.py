"""Framework Blender - Dynamic behavioral adaptation service.

T19-T20: Framework Blending
Allows personas to seamlessly blend multiple behavioral frameworks based on conversation context.
For example, a 'Neurosama' persona (Neuro framework) can blend 'Caring' framework traits
when the user is sad, or 'Chaotic' traits during creative tasks.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FrameworkBlender:
    """Blends behavioral frameworks based on context triggers."""

    def __init__(self):
        self.context_patterns = {
            "emotional_support": [
                "sad", "depressed", "help me", "crying", "upset", "hurt",
                "lonely", "anxious", "worried", "afraid", "scared", "tired",
                "exhausted", "stressed", "overwhelmed", "support", "vent"
            ],
            "creative_task": [
                "brainstorm", "idea", "create", "invent", "imagine", "story",
                "write", "draw", "design", "compose", "generate", "concept",
                "what if", "scenario", "plot"
            ],
            "analytical_task": [
                "analyze", "calculate", "compute", "solve", "math", "code",
                "program", "debug", "logic", "reason", "puzzle", "explain",
                "how does", "why is"
            ],
            "playful_chat": [
                "joke", "fun", "game", "play", "silly", "meme", "laugh",
                "lol", "haha", "rofl", "lmao", "bored", "entertain"
            ],
            "debate": [
                "disagree", "argue", "debate", "wrong", "false", "opinion",
                "convince", "prove", "evidence", "source"
            ]
        }

    def detect_context(self, message: str) -> Optional[str]:
        """Detect the primary context of a message using keyword matching.

        Args:
            message: User message content

        Returns:
            Context ID (e.g. 'emotional_support') or None
        """
        content = message.lower()

        # Check patterns (order matters for priority)
        # TODO: In future, use ThinkingService for semantic detection
        for context, keywords in self.context_patterns.items():
            for keyword in keywords:
                 # Word boundary check is better but simple containment works for now
                if keyword in content:
                    return context

        return None

    def blend_framework(
        self,
        base_prompt: str,
        target_prompt: str,
        context_name: str,
        weight: float = 1.0
    ) -> str:
        """Merge a target framework prompt into the base system prompt.

        Args:
            base_prompt: Original system prompt
            target_prompt: Framework prompt to blend in
            context_name: Name of the context triggering this
            weight: Influence weight (0.0 to 1.0)

        Returns:
            Modified system prompt
        """
        if weight <= 0:
            return base_prompt

        # Determine instruction intensity based on weight
        intensity_instruction = ""
        if weight >= 0.8:
            intensity_instruction = "PRIORITY: HIGH. These instructions override conflicting base behaviors."
        elif weight >= 0.5:
            intensity_instruction = "PRIORITY: MEDIUM. Integrate these traits with your base personality."
        else:
            intensity_instruction = "PRIORITY: LOW. subtly influence your response with these traits."

        blend_block = f"""
\n
=== DYNAMIC ADAPTATION ACTIVE ===
CONTEXT: {context_name.upper().replace('_', ' ')}
{intensity_instruction}

ADOPT THE FOLLOWING BEHAVIORAL PATTERNS:
{target_framework_prompt_processed(target_prompt)}

MAINTAIN YOUR CORE IDENTITY (NAME/MEMORY) BUT ADAPT YOUR STYLE.
=== END ADAPTATION ===
"""
        return base_prompt + blend_block

def target_framework_prompt_processed(prompt: str) -> str:
    """Clean up target prompt to extract core instructions.

    Often framework prompts contain {{char}} placeholders or template nuances.
    We want to extract the meat of the instructions.
    """
    # Simple pass-through for now, can be sophisticated later
    return prompt.strip()
