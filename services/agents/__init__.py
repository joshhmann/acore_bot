"""Agent orchestration system for specialized request handling."""

from services.agents.base import (
    BaseAgent,
    AgentResult,
    AgentType,
    AgentStats,
    AgentConfidence,
)

from services.agents.router import AgentRouter, RouterStats, RoutingStrategy

from services.agents.manager import AgentManager, ManagerStats

from services.agents.search_agent import SearchAgent, SearchAgentFactory

from services.agents.creative_agent import CreativeAgent, CreativeAgentFactory

from services.agents.code_agent import CodeAgent, CodeAgentFactory

from services.agents.conversation_agent import (
    ConversationAgent,
    ConversationAgentFactory,
)

from services.agents.tools import (
    AgentTool,
    ToolRegistry,
    ToolType,
    WebSearchTool,
    ImageGenerationTool,
    CodeExecutionTool,
    SentimentAnalysisTool,
    FactCheckTool,
    SearchResult,
    ImageResult,
    CodeResult,
    SentimentResult,
)

__all__ = [
    # Base
    "BaseAgent",
    "AgentResult",
    "AgentType",
    "AgentStats",
    "AgentConfidence",
    # Router
    "AgentRouter",
    "RouterStats",
    "RoutingStrategy",
    # Manager
    "AgentManager",
    "ManagerStats",
    # Agents
    "SearchAgent",
    "SearchAgentFactory",
    "CreativeAgent",
    "CreativeAgentFactory",
    "CodeAgent",
    "CodeAgentFactory",
    "ConversationAgent",
    "ConversationAgentFactory",
    # Tools
    "AgentTool",
    "ToolRegistry",
    "ToolType",
    "WebSearchTool",
    "ImageGenerationTool",
    "CodeExecutionTool",
    "SentimentAnalysisTool",
    "FactCheckTool",
    "SearchResult",
    "ImageResult",
    "CodeResult",
    "SentimentResult",
]
