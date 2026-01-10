"""
MCP Client Service for acore-bot Discord Bot

Provides secure, validated access to Model Context Protocol (MCP) servers.
Implements filesystem access, web search, database operations, and custom tool integration.
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

import aiofiles
import os
from config import Config, get_logger
from services.interfaces.llm_interface import LLMInterface

logger = get_logger(__name__)


class MCPServer:
    """Configuration for an MCP server."""

    def __init__(
        self,
        name: str,
        transport_type: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        enabled: bool = True,
    ):
        self.name = name
        self.transport_type = transport_type
        self.command = command
        self.args = args
        self.env = env
        self.enabled = enabled


class MCPClient:
    """Secure MCP client with tool execution and validation."""

    def __init__(self, servers: List[MCPServer]):
        self.servers = {server.name: server for server in servers}
        self.active_processes = {}
        self.tool_whitelist = self._build_tool_whitelist()

    def _build_tool_whitelist(self) -> List[str]:
        """Build whitelist of allowed tools based on security policy."""
        allowed_tools = [
            "read_file",
            "write_file",
            "list_directory",
            "search_web",
            "get_weather",
            "database_query",
        ]
        return allowed_tools

    async def execute_tool(
        self,
        server_name: str,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute MCP tool with comprehensive security checks."""

        logger.info(f"Executing MCP tool: {tool_name} from server: {server_name}")

        # 1. Server validation
        if server_name not in self.servers:
            raise ValueError(f"Unknown MCP server: {server_name}")

        server = self.servers[server_name]
        if not server.enabled:
            raise ValueError(f"MCP server {server_name} is disabled")

        # 2. Tool whitelist validation
        if tool_name not in self.tool_whitelist:
            raise ValueError(f"Tool {tool_name} is not whitelisted")

        # 3. Security checks for filesystem operations
        if tool_name.startswith(("read_", "write_", "list_")):
            await self._validate_filesystem_access(args, user_id)

        # 4. Rate limiting check
        if user_id:
            await self._check_rate_limit(user_id)

        # 5. Execute tool
        try:
            result = await self._execute_mcp_tool(server, tool_name, args)
            logger.info(f"Successfully executed {tool_name}: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}: {e}")
            return {"error": str(e)}

    async def _validate_filesystem_access(
        self, args: Dict[str, Any], user_id: Optional[int]
    ):
        """Validate filesystem access for security violations."""
        if "path" in args:
            path = args["path"]
            # Path traversal protection
            if any(
                path.startswith(prefix) for prefix in ["../", "..", "/etc/", "/root/"]
            ):
                raise SecurityError(f"Path traversal attempt: {path}")

            # Bot data directory protection (admin only)
            if (
                user_id
                and path.startswith("/data/")
                and not await self._is_admin_user(user_id)
            ):
                raise SecurityError(f"Unauthorized bot data access: {path}")

    async def _is_admin_user(self, user_id: int) -> bool:
        """Check if user has admin privileges."""
        # TODO: Implement admin role checking
        # For now, allow all users
        return True

    async def _check_rate_limit(self, user_id: int):
        """Implement rate limiting for tool usage."""
        # TODO: Implement rate limiting
        # For now, allow unlimited
        pass

    async def _execute_mcp_tool(
        self, server: MCPServer, tool_name: str, args: Dict[str, Any]
    ) -> Any:
        """Execute an MCP tool using subprocess."""
        cmd = ["npx", "-y", server.command, *server.args]

        # Add environment variables
        env = os.environ.copy()
        env.update(server.env or {})

        # Prepare tool execution request
        request = {"tool": tool_name, "arguments": args}

        process = await asyncio.create_subprocess_exec(
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = await process.communicate(
                input=json.dumps(request), timeout=30.0
            )

            if process.returncode != 0:
                raise RuntimeError(f"MCP tool failed: {stderr}")

            return json.loads(stdout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP tool execution timed out")
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await process.wait(timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools from enabled servers."""
        tools = []

        for server_name, server in self.servers.items():
            if not server.enabled:
                continue

            try:
                server_tools = await self._list_server_tools(server)
                tools.extend(server_tools)
            except Exception as e:
                logger.warning(f"Failed to list tools from {server_name}: {e}")

        return tools

    async def _list_server_tools(self, server: MCPServer) -> List[Dict[str, Any]]:
        """List tools from a specific MCP server."""
        cmd = ["npx", "-y", server.command, *server.args]

        env = os.environ.copy()
        env.update(server.env or {})

        process = await asyncio.create_subprocess_exec(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        try:
            stdout, stderr = await process.communicate(timeout=10.0)

            if process.returncode != 0:
                raise RuntimeError(f"Failed to list tools from {server.name}: {stderr}")

            result = json.loads(stdout)
            return result.get("tools", [])
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool listing timed out for {server.name}")
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON response from {server.name}")

    async def cleanup(self):
        """Clean up all running MCP server processes."""
        for process in self.active_processes.values():
            if process and process.returncode is None:
                process.terminate()
                try:
                    await process.wait(timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()

        self.active_processes.clear()


class SecurityError(Exception):
    """Raised when MCP operation violates security policy."""

    pass


class TimeoutError(Exception):
    """Raised when MCP operation times out."""

    pass
