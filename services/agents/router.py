"""Agent router for intelligent request routing to specialized agents."""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from services.agents.base import BaseAgent, AgentResult, AgentType, AgentStats
from services.agents.search_agent import SearchAgent
from services.agents.creative_agent import CreativeAgent
from services.agents.code_agent import CodeAgent
from services.agents.conversation_agent import ConversationAgent

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Strategies for routing requests to agents."""

    HIGHEST_CONFIDENCE = "highest_confidence"
    ROUND_ROBIN = "round_robin"
    PRIORITY_BASED = "priority_based"
    FALLBACK_CHAIN = "fallback_chain"


@dataclass
class RouterStats:
    """Statistics for router performance tracking."""

    total_requests: int = 0
    routed_requests: int = 0
    fallback_requests: int = 0
    avg_routing_time_ms: float = 0.0
    agent_usage: Dict[str, int] = field(default_factory=dict)
    confidence_scores: List[float] = field(default_factory=list)

    @property
    def routing_success_rate(self) -> float:
        """Calculate routing success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.routed_requests / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_requests": self.total_requests,
            "routed_requests": self.routed_requests,
            "fallback_requests": self.fallback_requests,
            "routing_success_rate": self.routing_success_rate,
            "avg_routing_time_ms": self.avg_routing_time_ms,
            "agent_usage": self.agent_usage,
        }


class AgentRouter:
    """Router that intelligently routes requests to the best-suited agent.

    Features:
    - Confidence-based routing
    - Agent chaining support
    - Fallback handling
    - Performance statistics
    """

    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.HIGHEST_CONFIDENCE,
        min_confidence_threshold: float = 0.3,
        enable_chaining: bool = True,
        max_chain_length: int = 3,
    ):
        """Initialize agent router.

        Args:
            strategy: Routing strategy to use.
            min_confidence_threshold: Minimum confidence to route to specialist.
            enable_chaining: Whether to support agent chaining.
            max_chain_length: Maximum number of agents in a chain.
        """
        self.strategy = strategy
        self.min_confidence = min_confidence_threshold
        self.enable_chaining = enable_chaining
        self.max_chain_length = max_chain_length

        self._agents: Dict[AgentType, BaseAgent] = {}
        self._agent_order: List[AgentType] = []
        self._stats = RouterStats()
        self._round_robin_index = 0
        self._initialized = False

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the router.

        Args:
            agent: Agent to register.
        """
        self._agents[agent.agent_type] = agent
        self._agent_order.append(agent.agent_type)
        self._initialized = True  # Mark as initialized when first agent is registered
        logger.info(f"Registered agent: {agent.name} ({agent.agent_type.value})")

    def unregister_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """Unregister an agent from the router.

        Args:
            agent_type: Type of agent to unregister.

        Returns:
            The unregistered agent or None.
        """
        agent = self._agents.pop(agent_type, None)
        if agent:
            self._agent_order.remove(agent_type)
            logger.info(f"Unregistered agent: {agent.name}")
        return agent

    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """Get a specific agent by type.

        Args:
            agent_type: Type of agent.

        Returns:
            Agent or None.
        """
        return self._agents.get(agent_type)

    def list_agents(self) -> List[BaseAgent]:
        """List all registered agents.

        Returns:
            List of agents.
        """
        return list(self._agents.values())

    def is_healthy(self) -> bool:
        """Check if router and all agents are healthy.

        Returns:
            True if operational.
        """
        if not self._initialized:
            return False

        return all(agent.is_healthy for agent in self._agents.values())

    async def route_request(
        self,
        request: str,
        context: Dict[str, Any],
        allow_fallback: bool = True,
    ) -> AgentResult:
        """Route a request to the best-suited agent.

        Args:
            request: User request string.
            context: Additional context (user, channel, etc.).
            allow_fallback: Whether to use conversation agent as fallback.

        Returns:
            AgentResult from the selected agent.
        """
        start_time = time.time()
        self._stats.total_requests += 1

        try:
            # Get confidence scores from all agents
            agent_scores = await self._get_agent_confidences(request, context)

            if not agent_scores:
                # No agents available, use fallback
                return await self._handle_fallback(request, context)

            # Select agent based on strategy
            selected_agent, confidence = self._select_agent(agent_scores)

            # Check if confidence meets threshold
            if confidence < self.min_confidence and allow_fallback:
                self._stats.fallback_requests += 1
                return await self._handle_fallback(request, context)

            # Execute agent
            result = await selected_agent.execute(request, context)

            # Update stats
            self._stats.routed_requests += 1
            self._stats.confidence_scores.append(confidence)
            agent_name = selected_agent.name
            self._stats.agent_usage[agent_name] = (
                self._stats.agent_usage.get(agent_name, 0) + 1
            )

            # Handle chaining if enabled and result needs followup
            if (
                self.enable_chaining
                and result.needs_followup
                and result.suggested_agent
            ):
                chained_result = await self._handle_chaining(
                    result, context, agent_scores
                )
                if chained_result:
                    result = chained_result

            # Calculate routing time
            routing_time = (time.time() - start_time) * 1000
            self._update_avg_routing_time(routing_time)

            return result

        except Exception as e:
            logger.error(f"Router error: {e}")
            self._stats.fallback_requests += 1
            return await self._handle_fallback(request, context)

    async def _get_agent_confidences(
        self, request: str, context: Dict[str, Any]
    ) -> Dict[AgentType, Tuple[BaseAgent, float]]:
        """Get confidence scores from all agents.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            Dict mapping agent type to (agent, confidence).
        """
        scores = {}

        for agent_type, agent in self._agents.items():
            if agent.is_healthy:
                try:
                    confidence = await agent.can_handle(request)
                    if confidence > 0:
                        scores[agent_type] = (agent, confidence)
                except Exception as e:
                    logger.warning(f"Agent {agent.name} confidence check failed: {e}")

        return scores

    def _select_agent(
        self, agent_scores: Dict[AgentType, Tuple[BaseAgent, float]]
    ) -> Tuple[BaseAgent, float]:
        """Select the best agent based on routing strategy.

        Args:
            agent_scores: Dict of agent scores.

        Returns:
            Tuple of (selected agent, confidence).
        """
        if self.strategy == RoutingStrategy.HIGHEST_CONFIDENCE:
            # Use tuple (confidence, index) as key to avoid tuple comparison issues
            max_entry = max(
                agent_scores.items(),
                key=lambda x: (x[1][1], id(x[1][0])),
            )
            return max_entry[1]
        elif self.strategy == RoutingStrategy.ROUND_ROBIN:
            # Rotate through agents
            available_types = list(agent_scores.keys())
            self._round_robin_index = self._round_robin_index % len(available_types)
            selected_type = available_types[self._round_robin_index]
            self._round_robin_index += 1
            return agent_scores[selected_type]
        elif self.strategy == RoutingStrategy.PRIORITY_BASED:
            # Use agent order (first registered = highest priority)
            for agent_type in self._agent_order:
                if agent_type in agent_scores:
                    return agent_scores[agent_type]
        elif self.strategy == RoutingStrategy.FALLBACK_CHAIN:
            # Try in order until one meets threshold
            for agent_type in self._agent_order:
                if agent_type in agent_scores:
                    agent, confidence = agent_scores[agent_type]
                    if confidence >= self.min_confidence:
                        return agent_scores[agent_type]

        # Fallback to highest confidence
        if agent_scores:
            max_entry = max(
                agent_scores.items(),
                key=lambda x: (x[1][1], id(x[1][0])),
            )
            return max_entry[1]

        return None, 0.0

    async def _handle_fallback(
        self, request: str, context: Dict[str, Any]
    ) -> AgentResult:
        """Handle fallback to conversation agent.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult from fallback agent.
        """
        conversation_agent = self._agents.get(AgentType.CONVERSATION)

        if conversation_agent:
            result = await conversation_agent.execute(request, context)
            result.metadata["routed_via"] = "fallback"
            return result

        # No fallback available
        return AgentResult(
            success=False,
            content="No agents available to handle this request.",
            agent_type=AgentType.CONVERSATION,
            error="No fallback agent available",
        )

    async def _handle_chaining(
        self,
        initial_result: AgentResult,
        context: Dict[str, Any],
        agent_scores: Dict[AgentType, Tuple[BaseAgent, float]],
    ) -> Optional[AgentResult]:
        """Handle agent chaining for followup tasks.

        Args:
            initial_result: Result from first agent.
            context: Additional context.
            agent_scores: Available agents with scores.

        Returns:
            Chained result or None.
        """
        if not initial_result.suggested_agent:
            return None

        suggested = initial_result.suggested_agent
        chain_count = 0

        while (
            initial_result.needs_followup
            and suggested
            and chain_count < self.max_chain_length
        ):
            chain_count += 1

            # Get the next agent
            next_agent, confidence = agent_scores.get(suggested, (None, 0))

            if not next_agent or confidence < self.min_confidence:
                break

            # Execute next agent with previous result as context
            context["previous_result"] = initial_result.content

            next_result = await next_agent.execute(
                initial_result.needs_followup, context
            )

            if next_result.success:
                # Combine results
                initial_result = AgentResult(
                    success=True,
                    content=f"{initial_result.content}\n\n---\n\n{next_result.content}",
                    agent_type=initial_result.agent_type,
                    confidence=(initial_result.confidence + next_result.confidence) / 2,
                    metadata={
                        "chained": True,
                        "chain_count": chain_count,
                        "agents": [initial_result.agent_type.value, suggested.value],
                    },
                )
            else:
                break

        return initial_result

    def _update_avg_routing_time(self, new_time: float) -> None:
        """Update average routing time.

        Args:
            new_time: New routing time in ms.
        """
        total = self._stats.total_requests
        if total == 1:
            self._stats.avg_routing_time_ms = new_time
        else:
            # Running average
            self._stats.avg_routing_time_ms = (
                self._stats.avg_routing_time_ms * (total - 1) + new_time
            ) / total

    def get_stats(self) -> RouterStats:
        """Get router statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset router statistics."""
        self._stats = RouterStats()
        logger.info("Router statistics reset")

    def shutdown(self) -> None:
        """Shutdown all agents and cleanup."""
        for agent in self._agents.values():
            try:
                agent.mark_unhealthy()
            except Exception as e:
                logger.warning(f"Error marking agent unhealthy: {e}")

        logger.info("Agent router shutdown complete")
