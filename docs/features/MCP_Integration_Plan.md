# MCP (Model Context Protocol) for acore-bot Discord Bot

**Status:** **ARCHIVED** - Service was planned but never implemented
**Config:** `MCP_ENABLED=false` (disabled by default)

## What MCP Could Provide

MCP would enable the bot to access external tools and resources beyond its built-in capabilities, significantly expanding functionality without requiring direct implementation.

## Recommended MCP Tools for Discord Bot

### **Core Productivity Tools**

| MCP Server | Tool | Bot Use Case | Implementation |
|-------------|------|---------------|----------------|
| **@modelcontextprotocol/server-filesystem** | File System Access | Read config files, user uploads, logs, backup/restore operations |
| **@modelcontextprotocol/server-brave-search** | Web Search | Enhanced Google search, fact-checking, information retrieval |
| **@modelcontextprotocol/server-everything** | Universal Search | Search APIs, databases, document repositories |
| **@modelcontextprotocol/server-database** | Database Operations | SQLite access for analytics, reporting, data persistence |
| **custom-knowledgebase** | RAG Enhancement | Search existing documentation, codebase, API docs |

### **Discord-Specific Tools**

| MCP Server | Tool | Bot Use Case | Implementation |
|-------------|------|---------------|----------------|
| **discord-mcp** | Discord API Enhancement | Bot management, server administration, user analytics |
| **github-mcp** | Repository Integration | Code review, issue management, deployment automation |

### **AI Development Tools**

| MCP Server | Tool | Bot Use Case | Implementation |
|-------------|------|---------------|----------------|
| **context7** | Documentation Access | Search technical docs, API references, coding examples |
| **tavily-mcp** | Enhanced Search | Academic sources, technical papers, current events |

## Implementation Strategy

### **Phase 1: Foundation (Week 1)**
```python
# services/mcp/client.py
class MCPClient:
    def __init__(self, config):
        self.config = config
        self.servers = []
    
    async def connect_server(self, server_config):
        # Connect to MCP server via stdio/HTTP
        
    async def execute_tool(self, tool_name: str, args: dict):
        # Execute MCP tool with proper error handling
```

### **Phase 2: Core Integration (Week 2)**
```python
# cogs/mcp_commands.py
@app_commands.command(name="mcp")
async def mcp_tool_command(interaction, tool_name: str, *, args: str = ""):
    user_args = json.loads(args) if args else {}
    result = await bot.mcp_client.execute_tool(tool_name, user_args)
    await interaction.response.send(f"✅ {tool_name}: {result}")
```

### **Phase 3: Tool Selection (Week 3)**
```python
# services/mcp/tool_registry.py
class ToolRegistry:
    def get_available_tools(self):
        return {
            "search": {
                "name": "web_search",
                "description": "Search the web for information",
                "mcp_server": "tavily-mcp"
            },
            "files": {
                "name": "read_file",
                "description": "Read bot files and configuration",
                "mcp_server": "filesystem-mcp"
            }
        }
```

### **Configuration (config.py additions)**
```python
# MCP Configuration
MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() == "true"
MCP_SERVERS: list = [
    {
        "name": "filesystem",
        "transport_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    },
    {
        "name": "search", 
        "transport_type": "stdio",
        "command": "npx",
        "args": ["-y", "tavily-mcp"],
        "env": {"TAVILY_API_KEY": Config.TAVILY_API_KEY}
    }
]
```

## Use Case Examples

### **Enhanced Bot Administration**
```
User: /mcp files read config.json
Bot: ✅ Reading /data/config.json...
{
  "DISCORD_TOKEN": "••••••••••••••",
  "OLLAMA_MODEL": "llama3.2",
  "BOT_STATUS": "active"
}
```

### **Web Search Integration**
```
User: /mcp search "latest Discord.py update notes"
Bot: ✅ Searching web...
Found: Discord.py v2.4.0 released 2 days ago
Breaking changes: Bot intents system deprecated
```

### **Document Generation**
```
User: /mcp docs create "Bot Status Report"
Bot: ✅ Generating documentation...
Created comprehensive status report with metrics
```

### **Code Review Automation**
```
User: /mcp github list_prs
Bot: ✅ Fetching pull requests...
#3: Fix conversation history bug
#5: Add TTS quality improvements  
```

## Security Considerations

### **Critical Protections Required**
```python
# Secure MCP tool execution
class SecureMCPExecutor:
    async def execute_tool(self, tool_name, args):
        # 1. Input validation
        if not self.validate_tool_input(tool_name, args):
            raise ValueError("Invalid tool arguments")
        
        # 2. Path traversal protection
        if tool_name == "read_file":
            file_path = args.get("path", "")
            if not file_path.startswith(("/data/", "./", "../")):
                raise SecurityError("Path traversal attempt detected")
        
        # 3. Rate limiting
        if not await self.check_rate_limit(interaction.user.id):
            raise RateLimitError("Too many tool requests")
```

### **Recommended Hardening**
- **Sandbox MCP servers** in containers with limited filesystem access
- **Tool whitelisting** - Only pre-approved MCP servers allowed
- **Audit logging** - Log all MCP tool executions for security review
- **User permissions** - Restrict dangerous tools to admin roles only
- **Input sanitization** - Validate all MCP tool inputs before execution

## Benefits vs Direct Implementation

| Aspect | Direct Implementation | MCP Integration | Winner |
|---------|-------------------|----------------|--------|
| **Development Speed** | Slow (build each tool) | **Fast** (instant access) |
| **Maintenance** | High (update code) | **Low** (managed by MCP server) |
| **Ecosystem** | Siloed (custom tools only) | **Connected** (shared tool ecosystem) |
| **Security** | Custom implementation | **Standardized** (battle-tested security) |
| **Reliability** | Variable (custom code) | **High** (maintained by experts) |
| **Features** | Limited by dev time | **Unlimited** (extensive tool library) |

## Recommended Implementation Path

1. **Start Small**: Begin with filesystem and search MCP servers
2. **Security First**: Implement comprehensive validation before enabling tools
3. **User Testing**: Test with trusted users before full rollout
4. **Monitoring**: Add metrics and logging for MCP usage
5. **Documentation**: Create `/mcp help` command for tool discovery

**Priority**: **HIGH** - MCP integration would transform this bot from a standard Discord bot to a powerful AI assistant with access to the entire MCP tool ecosystem.