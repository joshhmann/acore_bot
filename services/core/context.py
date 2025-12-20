"""Context manager for token-aware prompt construction."""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import tiktoken

from config import Config
from services.persona.system import CompiledPersona
from services.persona.lorebook import LoreEntry

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages the construction of the LLM context window with token budgeting."""

    def __init__(self):
        """Initialize context manager."""
        # Cache encoders to avoid re-initialization
        self._encoders = {}
        # T19: Framework Blending (Lazy loaded)
        self.framework_blender = None

    def _get_encoder(self, model_name: str):
        """Get tiktoken encoder for a model."""
        if model_name in self._encoders:
            return self._encoders[model_name]

        try:
            # Try to map common model names to tiktoken encodings
            if "gpt-4" in model_name:
                encoding = tiktoken.encoding_for_model("gpt-4")
            elif "gpt-3.5" in model_name:
                encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            else:
                # Default to cl100k_base (used by GPT-3.5/4/Llama3 usually good approximation)
                encoding = tiktoken.get_encoding("cl100k_base")

            self._encoders[model_name] = encoding
            return encoding
        except Exception as e:
            logger.warning(
                f"Could not get specific encoder for {model_name}, using default: {e}"
            )
            return tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str, model_name: str = "gpt-3.5-turbo") -> int:
        """Count tokens in a string."""
        if not text:
            return 0
        encoder = self._get_encoder(model_name)
        return len(encoder.encode(text))

    def count_message_tokens(
        self, messages: List[Dict[str, str]], model_name: str = "gpt-3.5-turbo"
    ) -> int:
        """Count tokens in a list of messages."""
        count = 0
        encoder = self._get_encoder(model_name)

        for msg in messages:
            # Add tokens for message overhead (role + content)
            # This is an approximation; different APIs have different overheads
            count += 4  # ~4 tokens per message for overhead
            count += len(encoder.encode(msg.get("content", "")))
            if "name" in msg:
                count += len(encoder.encode(msg["name"]))

        return count

    def _get_contagion_prompt_modifier(self, modifier: str, intensity: float) -> str:
        """Generate emotional contagion prompt modifier based on user sentiment.

        T21-T22: Emotional Contagion System

        Args:
            modifier: Type of contagion (empathetic, enthusiastic, balanced)
            intensity: Strength of contagion effect (0.0-1.0)

        Returns:
            Prompt text to inject into system prompt
        """
        if modifier == "empathetic":
            # User is consistently sad/frustrated - be more supportive
            base_text = "\n\n[EMOTIONAL GUIDANCE]\nThe user has been expressing sadness or frustration recently. "
            if intensity > 0.7:
                return base_text + "Be especially gentle, supportive, and understanding in your responses. Offer empathy and encouragement."
            elif intensity > 0.5:
                return base_text + "Be more compassionate and supportive in your responses. Show understanding of their situation."
            else:
                return base_text + "Be somewhat more gentle and understanding in your responses."

        elif modifier == "enthusiastic":
            # User is consistently happy/excited - match their energy
            base_text = "\n\n[EMOTIONAL GUIDANCE]\nThe user has been expressing happiness and energy recently. "
            if intensity > 0.7:
                return base_text + "Match their enthusiasm with energetic, positive, and engaging responses. Share their excitement!"
            elif intensity > 0.5:
                return base_text + "Be more upbeat and energetic in your responses. Share in their positive mood."
            else:
                return base_text + "Be slightly more cheerful and positive in your responses."

        else:  # balanced
            return ""  # No modifier needed for balanced state

    async def build_context(
        self,
        persona: CompiledPersona,
        history: List[Dict[str, str]],
        model_name: str,
        lore_entries: Optional[List[LoreEntry]] = None,
        rag_content: Optional[str] = None,
        user_context: Optional[str] = None,
        max_tokens: Optional[int] = None,
        llm_service=None,  # NEW: pass LLM service to get context_length
    ) -> List[Dict[str, str]]:
        """
        Build the final list of messages for the LLM, respecting the token limit.

        Strategy:
        1. System Prompt (Highest Priority)
        2. User Context / RAG (High Priority)
        3. Lorebook Entries (High Priority)
        4. Chat History (Fill remaining budget, newest to oldest)

        Args:
            persona: Active compiled persona
            history: Full chat history
            model_name: Name of the model (for context limit)
            lore_entries: Active lorebook entries
            rag_content: Content retrieved from RAG
            user_context: User profile information
            max_tokens: Override config limit
            llm_service: LLM service instance (to get context_length)

        Returns:
            List of messages ready for the API
        """
        # Determine Token Limit
        limit = max_tokens

        # Try LLM service's fetched context_length first
        if not limit and llm_service and hasattr(llm_service, "context_length"):
            limit = llm_service.context_length
            if limit:
                logger.debug(f"Using LLM service context limit: {limit}")

        if not limit:
            # Check model specific limit from config
            limit = Config.MODEL_CONTEXT_LIMITS.get(model_name)
        if not limit:
            # Fallback to global default
            limit = Config.MAX_CONTEXT_TOKENS

        # Reserve some tokens for the generation response (output)
        # e.g., if model is 8k, we want to input max 7.5k to leave room for reply
        max_input_tokens = int(limit * 0.9)

        # 1. Build System Prompt Message
        system_content = persona.system_prompt

        # Inject User Context / RAG into System Prompt or as separate System msg
        # Usually appending to system prompt is cleaner for "Context"
        context_additions = []
        if user_context:
            context_additions.append(f"\n[USER INFO]\n{user_context}")

        if rag_content:
            context_additions.append(f"\n[KNOWLEDGE]\n{rag_content}")

        # Inject Lore Entries
        if lore_entries:
            lore_text = "\n[WORLD INFO]\n" + "\n".join(
                [e.content for e in lore_entries]
            )
            context_additions.append(lore_text)

        # Combine all system-level content
        full_system_content = system_content + "\n".join(context_additions)

        # T19: Framework Blending - Apply dynamic behavioral adaptations
        if persona.blend_data:
            try:
                # Lazy load blender
                if not self.framework_blender:
                    from services.persona.framework_blender import FrameworkBlender
                    self.framework_blender = FrameworkBlender()

                # Check context via last user message
                last_user_msg = None
                # Use history to find last user message (skip recent system messages)
                for m in reversed(history):
                    if m.get("role") == "user":
                        last_user_msg = m.get("content", "")
                        break

                if last_user_msg:
                    context = self.framework_blender.detect_context(last_user_msg)
                    if context:
                        # Check rules for this context
                        rules = persona.blend_data.get("rules", [])
                        cached_prompts = persona.blend_data.get("cached_prompts", {})

                        for rule in rules:
                            if rule.get("context") == context:
                                target_fw_id = rule.get("framework")
                                target_prompt = cached_prompts.get(target_fw_id)

                                if target_prompt:
                                    weight = rule.get("weight", 1.0)
                                    full_system_content = self.framework_blender.blend_framework(
                                        full_system_content,
                                        target_prompt,
                                        context,
                                        weight
                                    )
                                    logger.debug(
                                        f"Framework Blending: Applied {target_fw_id} for context {context} "
                                        f"(weight: {weight})"
                                    )
                                    break # Only apply one blend rule priority
            except Exception as e:
                logger.error(f"Error applying framework blending: {e}")

        # T13: Add Character Evolution modifier
        try:
            from services.persona.evolution import PersonaEvolutionTracker

            # Try to get evolution tracker from global state (set by BehaviorEngine)
            # For now, we'll create a temporary instance to check evolution state
            evolution_tracker = PersonaEvolutionTracker()
            evolution_modifier = evolution_tracker.get_evolution_prompt_modifier(
                persona.persona_id
            )
            if evolution_modifier:
                full_system_content += f"\n{evolution_modifier}"
                logger.debug(f"Applied evolution modifier for {persona.persona_id}")
        except Exception as e:
            logger.debug(f"Evolution modifier not applied: {e}")

        # T15: Add Conflict modifiers for persona interactions
        try:
            # Check if we have PersonaRelationships available
            # This would typically be passed through the LLM service or context
            # For now, check if available on bot instance
            if llm_service and hasattr(llm_service, "bot"):
                persona_relationships = getattr(
                    llm_service.bot, "persona_relationships", None
                )
                if persona_relationships:
                    # Check recent history for other persona messages
                    for msg in reversed(history[-5:]):  # Check last 5 messages
                        msg_username = msg.get("username") or msg.get("name", "")
                        if (
                            msg_username
                            and msg_username != persona.character.display_name
                        ):
                            # Found another persona in history - check for conflict
                            conflict_mod = persona_relationships.get_conflict_modifier(
                                persona.character.display_name, msg_username
                            )
                            if conflict_mod["in_conflict"]:
                                full_system_content += conflict_mod["prompt_modifier"]
                                logger.debug(
                                    f"Applied conflict modifier: {persona.character.display_name} vs {msg_username} "
                                    f"(severity: {conflict_mod['severity']:.2f})"
                                )
                                break  # Only apply one conflict modifier
        except Exception as e:
            logger.debug(f"Conflict modifier not applied: {e}")

        # T21-T22: Add Emotional Contagion modifier
        # This adjusts the bot's emotional tone based on user sentiment trends
        try:
            # Access behavior state if available through llm_service
            if llm_service and hasattr(llm_service, "bot"):
                chat_cog = llm_service.bot.get_cog("ChatCog")
                if chat_cog and hasattr(chat_cog, "behavior_engine"):
                    behavior_engine = chat_cog.behavior_engine
                    # Get behavior state from most recent message in history
                    # (assumes behavior_engine tracks state per channel)
                    if history:
                        # Try to infer channel_id from context (not ideal, but works)
                        # Better: pass channel_id explicitly to build_context
                        for channel_id, state in behavior_engine.states.items():
                            if state.contagion_active:
                                contagion_text = self._get_contagion_prompt_modifier(
                                    state.contagion_modifier,
                                    state.contagion_intensity
                                )
                                if contagion_text:
                                    full_system_content += contagion_text
                                    logger.debug(
                                        f"Applied emotional contagion: {state.contagion_modifier} "
                                        f"(intensity: {state.contagion_intensity:.2f})"
                                    )
                                break  # Only apply once
        except Exception as e:
            logger.debug(f"Emotional contagion modifier not applied: {e}")

        # MULTI-PERSONA STABILITY FIX
        # Explicitly instruct the model to ignore identity bleeding from previous turns
        # (e.g. if Dagoth Ur called the user Nerevar, Scav shouldn't start doing it)
        full_system_content += (
            f"\n\n[SYSTEM INSTRUCTION]\n"
            f"Current Date and Time: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"You are currently {persona.character.display_name}.\n"
            f"Note: The chat history may contain messages from other characters/personas.\n"
            f"DO NOT adopt their nicknames for the user (like 'Nerevar') or their speaking style.\n"
            f"Strictly maintain your identity as {persona.character.display_name}."
        )

        # Initial messages list
        final_messages = [{"role": "system", "content": full_system_content}]

        # Check budget usage so far
        current_tokens = self.count_message_tokens(final_messages, model_name)
        remaining_tokens = max_input_tokens - current_tokens

        if remaining_tokens <= 0:
            logger.warning(
                "System prompt exceeds token limit! Truncating not implemented yet."
            )
            return final_messages

        # 2. Add Chat History (Newest first, then reverse)
        history_to_include = []

        # Always try to include the very last message (user's new input)
        # Assuming 'history' includes the new user message at the end

        reversed_history = list(reversed(history))

        for msg in reversed_history:
            msg_tokens = self.count_message_tokens([msg], model_name)

            if remaining_tokens - msg_tokens >= 0:
                # Format message for LLM
                clean_msg = {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }

                # Add name info if available
                username = msg.get("username") or msg.get("name")
                if username:
                    clean_msg["name"] = username
                    # Prepend name to content for stronger identity awareness
                    # (Helpful for models that ignore 'name' field)
                    if clean_msg["role"] == "user":
                        clean_msg["content"] = f"{username}: {clean_msg['content']}"

                history_to_include.append(clean_msg)
                remaining_tokens -= msg_tokens
            else:
                logger.info(
                    f"Context limit reached. Dropping {len(history) - len(history_to_include)} older messages."
                )
                break

        # Re-reverse to get chronological order
        final_messages.extend(reversed(history_to_include))

        return final_messages
