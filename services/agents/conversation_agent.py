"""Conversation agent wrapper around existing persona system."""

import logging
from typing import Dict, List, Any, Optional
from services.agents.base import BaseAgent, AgentResult, AgentType, AgentConfidence

logger = logging.getLogger(__name__)


class ConversationAgent(BaseAgent):
    """Agent that wraps existing persona/chat system for general conversation.

    This is the fallback agent when no specialized agent matches the request.
    It delegates to the existing BehaviorEngine and PersonaRouter system.
    """

    name = "ConversationAgent"
    description = "Handles general conversation using the persona system"
    agent_type = AgentType.CONVERSATION
    capabilities = [
        "persona_chat",
        "general_conversation",
        "contextual_responses",
        "multi_turn_conversation",
        "relationship_building",
    ]

    def __init__(
        self,
        chat_cog=None,
        behavior_engine=None,
        persona_router=None,
        timeout: float = 30.0,
    ):
        """Initialize conversation agent.

        Args:
            chat_cog: ChatCog instance for message handling.
            behavior_engine: BehaviorEngine instance.
            persona_router: PersonaRouter instance.
            timeout: Maximum execution time.
        """
        super().__init__(timeout=timeout)
        self._chat_cog = chat_cog
        self._behavior_engine = behavior_engine
        self._persona_router = persona_router

    async def can_handle(self, request: str) -> float:
        """Determine if conversation agent should handle this request.

        Args:
            request: User request.

        Returns:
            Confidence score 0-1.
        """
        # This is the fallback agent - low confidence unless nothing else matches
        # In practice, the router will call conversation agent when
        # no other agent has sufficient confidence

        # High confidence for general chat that doesn't need special handling
        general_chat_indicators = [
            "hey",
            "hello",
            "hi",
            "how are you",
            "what's up",
            "sup",
            "how do you feel",
            "what do you think",
            "tell me about yourself",
        ]

        request_lower = request.lower()
        matches = sum(1 for ind in general_chat_indicators if ind in request_lower)

        if matches >= 2:
            return AgentConfidence.MEDIUM.value
        elif matches == 1:
            return AgentConfidence.LOW.value

        # Default - conversation agent handles everything else as fallback
        return AgentConfidence.VERY_LOW.value

    async def process(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Process general conversation request via existing persona system.

        Args:
            request: User request.
            context: Additional context (user, channel, etc.).

        Returns:
            AgentResult with persona response.
        """
        try:
            # Use the chat cog's message handling if available
            if self._chat_cog:
                return await self._process_via_chat_cog(request, context)
            elif self._behavior_engine:
                return await self._process_via_behavior_engine(request, context)
            else:
                return self._create_fallback_response(request)

        except Exception as e:
            logger.error(f"Conversation agent error: {e}")
            return AgentResult(
                success=False,
                content="I'm having trouble responding right now. Please try again.",
                agent_type=self.agent_type,
                error=str(e),
            )

    async def _process_via_chat_cog(
        self, request: str, context: Dict[str, Any]
    ) -> AgentResult:
        """Process via ChatCog if available.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult.
        """
        # The ChatCog expects a discord.Message object
        # For agent routing, we need to create a minimal context
        # This is a placeholder - actual implementation would need
        # proper message object handling

        user = context.get("user")
        channel = context.get("channel")

        if not user or not channel:
            return self._create_fallback_response(request)

        # This would call the existing _handle_chat_response logic
        # For now, return a placeholder response

        return AgentResult(
            success=True,
            content=self._generate_conversational_response(request, context),
            agent_type=self.agent_type,
            confidence=0.7,
            metadata={"source": "conversation_agent_fallback"},
        )

    async def _process_via_behavior_engine(
        self, request: str, context: Dict[str, Any]
    ) -> AgentResult:
        """Process via BehaviorEngine if available.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult.
        """
        if not self._behavior_engine:
            return self._create_fallback_response(request)

        # Get current persona if set
        current_persona = getattr(self._behavior_engine, "current_persona", None)

        response = self._generate_conversational_response(request, context)

        return AgentResult(
            success=True,
            content=response,
            agent_type=self.agent_type,
            confidence=0.7,
            metadata={
                "source": "behavior_engine",
                "persona": str(current_persona) if current_persona else None,
            },
        )

    def _generate_conversational_response(
        self, request: str, context: Dict[str, Any]
    ) -> str:
        """Generate a conversational response.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            Response string.
        """
        # Simple conversational response
        # Full implementation would use LLM or existing persona logic

        request_lower = request.lower()

        greetings = ["hello", "hi", "hey", "howdy"]
        if any(greet in request_lower[:20] for greet in greetings):
            responses = [
                "Hey there! How can I help you today?",
                "Hello! What would you like to chat about?",
                "Hi! I'm here to help. What's on your mind?",
            ]
            import random

            return random.choice(responses)

        # Generic responses for unmatched requests
        return (
            "I understand you're saying: "
            + request[:100]
            + "...\n\nIs there something specific I can help you with?"
        )

    def _create_fallback_response(self, request: str) -> AgentResult:
        """Create fallback response when no chat system is available.

        Args:
            request: User request.

        Returns:
            AgentResult.
        """
        return AgentResult(
            success=True,
            content="I'm here and ready to chat! While I don't have my full persona system loaded, I'm happy to have a conversation. What would you like to talk about?",
            agent_type=self.agent_type,
            confidence=0.5,
            metadata={"source": "conversation_agent_fallback"},
        )

    def set_chat_cog(self, chat_cog):
        """Set ChatCog instance.

        Args:
            chat_cog: ChatCog instance.
        """
        self._chat_cog = chat_cog
        logger.info("Conversation agent ChatCog configured")

    def set_behavior_engine(self, behavior_engine):
        """Set BehaviorEngine instance.

        Args:
            behavior_engine: BehaviorEngine instance.
        """
        self._behavior_engine = behavior_engine
        logger.info("Conversation agent BehaviorEngine configured")

    def set_persona_router(self, persona_router):
        """Set PersonaRouter instance.

        Args:
            persona_router: PersonaRouter instance.
        """
        self._persona_router = persona_router
        logger.info("Conversation agent PersonaRouter configured")


class ConversationAgentFactory:
    """Factory for creating ConversationAgent instances."""

    @staticmethod
    def create(
        chat_cog=None,
        behavior_engine=None,
        persona_router=None,
    ) -> ConversationAgent:
        """Create conversation agent.

        Args:
            chat_cog: ChatCog instance.
            behavior_engine: BehaviorEngine instance.
            persona_router: PersonaRouter instance.

        Returns:
            Configured ConversationAgent.
        """
        return ConversationAgent(
            chat_cog=chat_cog,
            behavior_engine=behavior_engine,
            persona_router=persona_router,
        )
