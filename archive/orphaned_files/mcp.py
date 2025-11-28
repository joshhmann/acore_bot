"""MCP (Model Context Protocol) service for extended context and tool use."""
import logging
import aiohttp
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class MCPService:
    """Service for MCP (Model Context Protocol) integration.

    MCP allows the bot to:
    - Access external tools and APIs
    - Retrieve real-time data
    - Execute functions
    - Extend context beyond conversation history
    """

    def __init__(self, server_url: str):
        """Initialize MCP service.

        Args:
            server_url: URL of the MCP server
        """
        self.server_url = server_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self.available_tools: List[Dict] = []

    async def initialize(self):
        """Initialize the MCP client session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            await self._fetch_tools()

    async def close(self):
        """Close the MCP client session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _fetch_tools(self):
        """Fetch available tools from MCP server."""
        try:
            url = f"{self.server_url}/tools"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.available_tools = data.get("tools", [])
                    logger.info(f"MCP: Loaded {len(self.available_tools)} tools")
                else:
                    logger.warning(f"MCP: Failed to fetch tools (status {resp.status})")
        except Exception as e:
            logger.error(f"MCP: Failed to connect to server: {e}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict]:
        """Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool response or None if failed
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.server_url}/call"
            payload = {
                "tool": tool_name,
                "arguments": arguments
            }

            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(f"MCP: Tool '{tool_name}' executed successfully")
                    return result
                else:
                    logger.error(f"MCP: Tool '{tool_name}' failed (status {resp.status})")
                    return None

        except Exception as e:
            logger.error(f"MCP: Tool call failed: {e}")
            return None

    async def get_context(self, query: str) -> Optional[str]:
        """Get additional context from MCP server.

        Args:
            query: User query

        Returns:
            Additional context string or None
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.server_url}/context"
            payload = {"query": query}

            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("context", "")
                return None

        except Exception as e:
            logger.error(f"MCP: Context retrieval failed: {e}")
            return None

    def get_tools_description(self) -> str:
        """Get a description of available tools for the AI.

        Returns:
            Formatted string describing available tools
        """
        if not self.available_tools:
            return ""

        tools_desc = ["Available tools:"]
        for tool in self.available_tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            params = tool.get("parameters", [])

            tool_info = f"- {name}: {description}"
            if params:
                param_str = ", ".join([f"{p['name']} ({p.get('type', 'any')})" for p in params])
                tool_info += f" [Parameters: {param_str}]"

            tools_desc.append(tool_info)

        return "\n".join(tools_desc)

    async def check_health(self) -> bool:
        """Check if MCP server is reachable.

        Returns:
            True if healthy, False otherwise
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.server_url}/health"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"MCP health check failed: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if MCP has tools available.

        Returns:
            True if tools are loaded
        """
        return len(self.available_tools) > 0


# Example MCP Server Implementation (for reference)
"""
To create an MCP server, you can use FastAPI:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": [
            {"name": "location", "type": "string", "required": True}
        ]
    },
    {
        "name": "search_web",
        "description": "Search the web for information",
        "parameters": [
            {"name": "query", "type": "string", "required": True}
        ]
    }
]

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/tools")
async def get_tools():
    return {"tools": tools}

class ToolCall(BaseModel):
    tool: str
    arguments: dict

@app.post("/call")
async def call_tool(call: ToolCall):
    # Implement tool logic here
    if call.tool == "get_weather":
        location = call.arguments.get("location")
        # Call weather API...
        return {"result": f"Weather in {location}: Sunny, 72°F"}

    elif call.tool == "search_web":
        query = call.arguments.get("query")
        # Call search API...
        return {"result": f"Search results for: {query}..."}

    return {"error": "Unknown tool"}

# Run with: uvicorn mcp_server:app --port 8080
```
"""
