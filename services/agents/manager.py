"""Agent manager for factory creation, lifecycle management, and health monitoring."""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from services.agents.base import BaseAgent, AgentResult, AgentType, AgentStats
from services.agents.router import AgentRouter, RoutingStrategy
from services.agents.search_agent import SearchAgent, SearchAgentFactory
from services.agents.creative_agent import CreativeAgent, CreativeAgentFactory
from services.agents.code_agent import CodeAgent, CodeAgentFactory
from services.agents.conversation_agent import (
    ConversationAgent,
    ConversationAgentFactory,
)
from services.agents.tools import (
    ToolRegistry,
    WebSearchTool,
    CodeExecutionTool,
    SentimentAnalysisTool,
)

logger = logging.getLogger(__name__)


@dataclass
class ManagerStats:
    """Statistics for agent manager."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    agent_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    router_stats: Dict[str, Any] = field(default_factory=dict)
    health_checks: int = 0
    unhealthy_agents: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "agent_stats": self.agent_stats,
            "router_stats": self.router_stats,
            "health_checks": self.health_checks,
            "unhealthy_agents": self.unhealthy_agents,
        }


class AgentManager:
    """Manager for agent lifecycle, factory creation, and health monitoring.

    Responsibilities:
    - Agent factory and initialization
    - Health checks and monitoring
    - Statistics collection
    - Graceful shutdown
    """

    def __init__(
        self,
        routing_strategy: RoutingStrategy = RoutingStrategy.HIGHEST_CONFIDENCE,
        min_confidence: float = 0.3,
        health_check_interval: float = 60.0,
        enable_chaining: bool = True,
    ):
        """Initialize agent manager.

        Args:
            routing_strategy: Strategy for routing requests.
            min_confidence: Minimum confidence threshold for routing.
            health_check_interval: Seconds between health checks.
            enable_chaining: Whether to enable agent chaining.
        """
        self.routing_strategy = routing_strategy
        self.min_confidence = min_confidence
        self.health_check_interval = health_check_interval
        self.enable_chaining = enable_chaining

        self._router: Optional[AgentRouter] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._stats = ManagerStats()
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        self._start_time: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        if not self._start_time:
            return 0.0
        return (datetime.now() - self._start_time).total_seconds()

    def initialize(
        self,
        web_search_service=None,
        llm_service=None,
        chat_cog=None,
        behavior_engine=None,
        persona_router=None,
        image_api_key: str = None,
    ) -> AgentRouter:
        """Initialize all agents and router.

        Args:
            web_search_service: WebSearchService instance.
            llm_service: LLM service instance.
            chat_cog: ChatCog instance.
            behavior_engine: BehaviorEngine instance.
            persona_router: PersonaRouter instance.
            image_api_key: API key for image generation.

        Returns:
            Configured AgentRouter.
        """
        logger.info("Initializing AgentManager...")

        self._start_time = datetime.now()

        # Create tool registry
        self._tool_registry = ToolRegistry()

        # Register tools
        web_tool = WebSearchTool(web_search_service) if web_search_service else None
        if web_tool:
            self._tool_registry.register(web_tool)

        self._tool_registry.register(CodeExecutionTool())
        self._tool_registry.register(SentimentAnalysisTool())

        # Create router
        self._router = AgentRouter(
            strategy=self.routing_strategy,
            min_confidence_threshold=self.min_confidence,
            enable_chaining=self.enable_chaining,
        )

        # Create and register agents

        # Search Agent
        search_agent = SearchAgentFactory.create(web_search_service)
        self._router.register_agent(search_agent)
        logger.info(f"Registered: {search_agent.name}")

        # Creative Agent
        creative_agent = CreativeAgentFactory.create(
            image_api_key=image_api_key,
            llm_service=llm_service,
        )
        self._router.register_agent(creative_agent)
        logger.info(f"Registered: {creative_agent.name}")

        # Code Agent
        code_agent = CodeAgentFactory.create(
            code_tool=self._tool_registry.get("run_code"),
            llm_service=llm_service,
        )
        self._router.register_agent(code_agent)
        logger.info(f"Registered: {code_agent.name}")

        # Conversation Agent (fallback)
        conversation_agent = ConversationAgentFactory.create(
            chat_cog=chat_cog,
            behavior_engine=behavior_engine,
            persona_router=persona_router,
        )
        self._router.register_agent(conversation_agent)
        logger.info(f"Registered: {conversation_agent.name}")

        self._running = True

        logger.info(
            f"AgentManager initialized with {len(self._router.list_agents())} agents"
        )

        return self._router

    def start(self) -> None:
        """Start the agent manager services. Called when bot is ready."""
        self._start_health_check_loop()

    def _start_health_check_loop(self) -> None:
        """Start the background health check loop."""
        if self._health_check_task:
            self._health_check_task.cancel()

        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self.perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform health check on all agents.

        Returns:
            Dict with health status.
        """
        self._stats.health_checks += 1
        unhealthy_count = 0

        health_status = {
            "timestamp": datetime.now().isoformat(),
            "agents": {},
            "router_healthy": False,
        }

        if not self._router:
            health_status["error"] = "Router not initialized"
            return health_status

        # Check router
        health_status["router_healthy"] = self._router.is_healthy()

        # Check each agent
        for agent in self._router.list_agents():
            agent_name = agent.name
            stats = agent.get_stats()

            # Check if agent is healthy
            is_healthy = agent.is_healthy

            # Basic health check - agent has handled requests or is newly created
            if stats.requests_handled == 0 and not is_healthy:
                # Agent hasn't been used yet, assume healthy
                is_healthy = True
                agent.mark_healthy()

            if not is_healthy:
                unhealthy_count += 1

            health_status["agents"][agent_name] = {
                "healthy": is_healthy,
                "requests_handled": stats.requests_handled,
                "success_rate": stats.success_rate,
                "avg_execution_time_ms": stats.avg_execution_time_ms,
                "failures": stats.failures,
                "timeouts": stats.timeouts,
            }

        self._stats.unhealthy_agents = unhealthy_count

        if unhealthy_count > 0:
            logger.warning(f"Health check: {unhealthy_count} agents unhealthy")

        return health_status

    async def route_request(
        self,
        request: str,
        context: Dict[str, Any],
        allow_fallback: bool = True,
    ) -> AgentResult:
        """Route request through the agent router.

        Args:
            request: User request.
            context: Additional context.
            allow_fallback: Whether to use fallback agent.

        Returns:
            AgentResult from routed agent.
        """
        if not self._router or not self._running:
            return AgentResult(
                success=False,
                content="Agent system not available",
                error="AgentManager not running",
            )

        start_time = time.time()

        try:
            result = await self._router.route_request(
                request, context, allow_fallback=allow_fallback
            )

            # Update stats
            self._stats.total_requests += 1
            latency_ms = (time.time() - start_time) * 1000
            self._stats.total_latency_ms += latency_ms

            if result.success:
                self._stats.successful_requests += 1
            else:
                self._stats.failed_requests += 1

            return result

        except Exception as e:
            self._stats.failed_requests += 1
            logger.error(f"AgentManager route error: {e}")
            return AgentResult(
                success=False,
                content=str(e),
                error="Routing failed",
            )

    def get_router(self) -> Optional[AgentRouter]:
        """Get the agent router.

        Returns:
            AgentRouter or None.
        """
        return self._router

    def get_tool_registry(self) -> Optional[ToolRegistry]:
        """Get the tool registry.

        Returns:
            ToolRegistry or None.
        """
        return self._tool_registry

    def get_stats(self) -> ManagerStats:
        """Get manager statistics."""
        # Update with current router stats
        if self._router:
            self._stats.router_stats = self._router.get_stats().to_dict()

            # Update agent stats
            for agent in self._router.list_agents():
                self._stats.agent_stats[agent.name] = agent.get_stats().to_dict()

        return self._stats

    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """Get a specific agent by type.

        Args:
            agent_type: Type of agent.

        Returns:
            Agent or None.
        """
        if self._router:
            return self._router.get_agent(agent_type)
        return None

    def update_agent_dependency(
        self, agent_type: AgentType, dependency_name: str, dependency
    ) -> bool:
        """Update a dependency for a specific agent.

        Args:
            agent_type: Type of agent.
            dependency_name: Name of dependency.
            dependency: Dependency object.

        Returns:
            True if updated successfully.
        """
        agent = self.get_agent(agent_type)
        if not agent:
            return False

        if agent_type == AgentType.SEARCH and dependency_name == "web_search_service":
            if hasattr(agent, "set_web_search_service"):
                agent.set_web_search_service(dependency)
                return True

        elif agent_type == AgentType.CONVERSATION:
            if dependency_name == "chat_cog" and hasattr(agent, "set_chat_cog"):
                agent.set_chat_cog(dependency)
                return True
            elif dependency_name == "behavior_engine" and hasattr(
                agent, "set_behavior_engine"
            ):
                agent.set_behavior_engine(dependency)
                return True

        return False

    async def shutdown(self) -> None:
        """Shutdown all agents and cleanup."""
        logger.info("Shutting down AgentManager...")

        self._running = False

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Shutdown router
        if self._router:
            self._router.shutdown()

        # Close tool registry
        if self._tool_registry:
            # Close any tool connections
            pass

        logger.info("AgentManager shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.create_task(self.shutdown())
