"""Base agent class for the agent orchestration system."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time
import asyncio

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Types of specialized agents."""

    SEARCH = "search"
    CREATIVE = "creative"
    CODE = "code"
    CONVERSATION = "conversation"


class AgentConfidence(Enum):
    """Confidence levels for agent handling."""

    VERY_LOW = 0.1
    LOW = 0.3
    MEDIUM = 0.5
    HIGH = 0.7
    VERY_HIGH = 0.9
    CERTAIN = 1.0


@dataclass
class AgentResult:
    """Result from agent processing."""

    success: bool
    content: str
    confidence: float = 0.5
    agent_type: AgentType = AgentType.CONVERSATION
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    needs_followup: bool = False
    suggested_agent: Optional[AgentType] = None


@dataclass
class AgentStats:
    """Statistics for agent performance tracking."""

    requests_handled: int = 0
    total_execution_time_ms: float = 0.0
    successes: int = 0
    failures: int = 0
    timeouts: int = 0

    @property
    def avg_execution_time_ms(self) -> float:
        """Calculate average execution time."""
        if self.requests_handled == 0:
            return 0.0
        return self.total_execution_time_ms / self.requests_handled

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.successes + self.failures
        if total == 0:
            return 0.0
        return self.successes / total

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "requests_handled": self.requests_handled,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "success_rate": self.success_rate,
            "successes": self.successes,
            "failures": self.failures,
            "timeouts": self.timeouts,
        }


class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""

    name: str
    description: str
    capabilities: List[str]
    agent_type: AgentType

    def __init__(self, timeout: float = 30.0):
        """Initialize base agent.

        Args:
            timeout: Maximum execution time in seconds.
        """
        self.timeout = timeout
        self.stats = AgentStats()
        self._is_healthy = True

    @property
    def is_healthy(self) -> bool:
        """Check if agent is healthy and operational."""
        return self._is_healthy

    @abstractmethod
    async def can_handle(self, request: str) -> float:
        """Determine confidence score for handling this request.

        Args:
            request: User's request string.

        Returns:
            Confidence score from 0.0 to 1.0.
        """

    @abstractmethod
    async def process(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Process a request and return result.

        Args:
            request: User's request string.
            context: Additional context (user info, channel, etc.).

        Returns:
            AgentResult with content and metadata.
        """

    async def execute(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Execute agent processing with timeout and error handling.

        Args:
            request: User's request string.
            context: Additional context.

        Returns:
            AgentResult from processing.
        """
        start_time = time.time()

        try:
            confidence = await self.can_handle(request)

            if confidence < 0.1:
                return AgentResult(
                    success=False,
                    content="",
                    confidence=confidence,
                    agent_type=self.agent_type,
                    error="Confidence too low to process request",
                )

            async with asyncio.timeout(self.timeout):
                result = await self.process(request, context)

            result.execution_time_ms = (time.time() - start_time) * 1000
            result.agent_type = self.agent_type

            self.stats.requests_handled += 1
            self.stats.total_execution_time_ms += result.execution_time_ms

            if result.success:
                self.stats.successes += 1
            else:
                self.stats.failures += 1

            return result

        except asyncio.TimeoutError:
            self.stats.timeouts += 1
            self.stats.failures += 1
            logger.warning(f"{self.name} timed out after {self.timeout}s")

            return AgentResult(
                success=False,
                content="",
                confidence=0.0,
                agent_type=self.agent_type,
                execution_time_ms=self.timeout * 1000,
                error=f"Agent timed out after {self.timeout} seconds",
            )

        except Exception as e:
            self.stats.failures += 1
            self.stats.requests_handled += 1
            logger.error(f"{self.name} error: {e}", exc_info=True)

            return AgentResult(
                success=False,
                content="",
                confidence=0.0,
                agent_type=self.agent_type,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    def get_stats(self) -> AgentStats:
        """Get agent statistics."""
        return self.stats

    def mark_unhealthy(self):
        """Mark agent as unhealthy."""
        self._is_healthy = False
        logger.warning(f"{self.name} marked as unhealthy")

    def mark_healthy(self):
        """Mark agent as healthy."""
        self._is_healthy = True
        logger.info(f"{self.name} marked as healthy")

    def get_capabilities(self) -> List[str]:
        """Get list of agent capabilities."""
        return self.capabilities
