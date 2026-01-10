"""
MCP Commands Cog for Discord Bot

Provides secure, validated access to Model Context Protocol (MCP) tools.
Implements filesystem access, web search, and tool execution commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json

from config import Config, get_logger
from services.mcp.client import MCPClient, SecurityError, TimeoutError

logger = get_logger(__name__)


class MCPCommands(commands.Cog):
    """MCP command cog for Discord bot."""
    
    def __init__(self, bot):
        """Initialize MCP commands."""
        self.bot = bot
        self.mcp_client = None
        
        # Initialize MCP client when enabled
        if Config.MCP_ENABLED:
            self.mcp_client = MCPClient(Config.MCP_SERVERS)
            logger.info("MCP client initialized")
    
    async def cog_load(self):
        """Load MCP cog and register commands."""
        if Config.MCP_ENABLED and self.mcp_client:
            await self.bot.add_cog(self)
            logger.info("MCP commands cog loaded")
    
    @app_commands.command(name="mcp")
    @app_commands.describe(
        operation="Execute MCP tool",
        args=[
            app_commands.Argument(
                name="operation",
                description="MCP tool to execute (e.g., search_web, read_file)",
                required=True
            ),
            app_commands.Argument(
                name="args", 
                description="JSON arguments for the tool (e.g., '{\"query\": \"test\"}')",
                required=False
            )
        ]
    )
    async def mcp_command(self, interaction: discord.Interaction, operation: str, args: Optional[str] = None):
        """Execute an MCP tool with security validation."""
        
        if not Config.MCP_ENABLED:
            await interaction.response.send("❌ MCP is disabled. Enable it by setting MCP_ENABLED=true")
            return
        
        if not self.mcp_client:
            await interaction.response.send("❌ MCP client not initialized")
            return
        
        try:
            # Parse arguments
            tool_args = {}
            if args:
                try:
                    tool_args = json.loads(args)
                except json.JSONDecodeError:
                    await interaction.response.send("❌ Invalid JSON in args argument")
                    return
            except Exception as e:
                await interaction.response.send(f"❌ Error parsing args: {e}")
                return
        
            # Execute MCP tool
            result = await self.mcp_client.execute_tool(
                server_name="tavily-search",
                tool_name="search_web", 
                args=tool_args,
                user_id=interaction.user.id
            )
            
            # Format and send result
            if isinstance(result, dict):
                if "error" in result:
                    await interaction.response.send(f"❌ MCP tool failed: {result['error']}")
                elif "content" in result:
                    content = result["content"][:1000]  # Truncate long results
                    await interaction.response.send(f"🔍 **Search Results:**\n```\n{content}\n```\n📊 **Via:** Tavily Search")
                else:
                    await interaction.response.send(f"✅ **Tool executed successfully!**\n```\n{json.dumps(result, indent=2)}\n```\n📊 **Via:** Tavily MCP Server")
            else:
                await interaction.response.send(f"✅ **Tool executed successfully!**\n```\n{json.dumps(result, indent=2)}")
        
        except SecurityError as e:
            await interaction.response.send(f"🚫 **Security Error:** {e}")
        
        except TimeoutError as e:
            await interaction.response.send(f"⏰ **Timeout Error:** {e}")
        
        except Exception as e:
            logger.error(f"MCP command failed: {e}")
            await interaction.response.send(f"❌ **Unexpected error:** {e}")
    
    @app_commands.command(name="mcp")
    @app_commands.describe(
        operation="List available MCP tools",
        description="Show all available MCP tools and their capabilities"
    )
    async def mcp_list_command(self, interaction: discord.Interaction):
        """List all available MCP tools."""
        
        if not Config.MCP_ENABLED:
            await interaction.response.send("❌ MCP is disabled")
            return
        
        if not self.mcp_client:
            await interaction.response.send("❌ MCP client not initialized")
            return
        
        try:
            tools = await self.mcp_client.get_available_tools()
            
            # Format tool list
            tool_list = []
            for server_name, server_tools in tools.items():
                tool_list.append(f"**{server_name}**")
                for tool in server_tools:
                    tool_list.append(f"  • `{tool.get('name', 'Unknown')}`: {tool.get('description', 'No description')}")
            
            if not tool_list:
                await interaction.response.send("🔧 **No MCP tools available**")
                return
            
            await interaction.response.send(
                f"🔧 **Available MCP Tools:**\n\n"
                f"{chr(10).join(tool_list)}\n\n"
                f"**Usage:** `/mcp <operation> <args>`"
            )
            
        except Exception as e:
            logger.error(f"MCP list failed: {e}")
            await interaction.response.send(f"❌ **Error listing tools:** {e}")


async def setup_mcp_cog(bot):
    """Setup MCP commands cog."""
    if Config.MCP_ENABLED:
        mcp_cog = MCPCommands(bot)
        await bot.add_cog(mcp_cog)
        logger.info("MCP commands cog setup complete")
        return mcp_cog
    
    return None