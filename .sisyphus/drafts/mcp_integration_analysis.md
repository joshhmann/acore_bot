# Analysis: MCP Tool Integration for RL Autonomy

## Executive Summary
The user asked about "MCP-like tool calling". Research confirms that **Model Context Protocol (MCP)** is a formal standard (Anthropic, late 2024) for standardized tool execution via Client-Server architecture.

### Recommendation: "Hybrid-MCP Architecture"
For this project (RL Behavioral Engine), we should adopt a **Hybrid Approach**:
1.  **Internal Tools**: Use lightweight Python "Skills" (decorators) for speed (e.g., `check_mood`, `roll_dice`). No MCP overhead needed.
2.  **External Tools**: Implement an **MCP Client Interface** to allow the bot to "plug in" to the wider MCP ecosystem (e.g., Search, GitHub, Filesystem) without writing custom wrappers.

## 1. What is MCP?
- **Protocol**: JSON-RPC standard for `AI Application <-> Tool Server` communication.
- **Value**: Standardizes "How to call a tool" so you don't write 50 different API wrappers.
- **Relevance**: Supports the "Neuro-sama" goal of autonomy by giving the bot standardized "hands" to interact with the world.

## 2. Integration Strategy
We will modify the RL Plan to support **Hierarchical Tool Use**:

1.  **Level 1 (RL Brain)**: Decides Strategy.
    - Output: `Action.USE_TOOL` (Generic).
2.  **Level 2 (LLM Actor)**: Decides Specific Tool.
    - Input: "RL says use a tool. Context: User asked about weather."
    - Output: `call_tool(name="weather_mcp", args={"location": "Tokyo"})`
3.  **Level 3 (Execution)**:
    - **Fast Path**: Execute internal Python function.
    - **MCP Path**: Send JSON-RPC request to MCP Server.

## 3. Plan Modifications
We need to add an **MCP Client Service** to the implementation plan.

### New Service: `services/mcp/client.py`
- **Function**: Connects to stdio/SSE MCP servers.
- **Interface**: `list_tools()`, `call_tool(name, args)`.
- **Config**: List of enabled MCP servers in `config.py`.

### Updated Behavior Loop
- **RL Action Space**: Add `USE_TOOL` (Index 4).
- **LLM Prompting**: Inject available tool schemas (from MCP `list_tools`) into the system prompt when `USE_TOOL` is selected.

## 4. Why This Matters
- **Extensibility**: User can add a "Minecraft Server Control" MCP later without changing bot code.
- **Safety**: MCP runs tools in separate processes/containers (sandboxing).
- **Power**: Access to browsing, filesystem, and databases "for free" via community MCP servers.
