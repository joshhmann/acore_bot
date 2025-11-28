"""Agentic tool system using ReAct pattern."""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple

logger = logging.getLogger(__name__)


class Tool:
    """Represents a tool the agent can use."""
    
    def __init__(self, name: str, description: str, function: Callable, parameters: Dict[str, str]):
        """Initialize tool.
        
        Args:
            name: Tool name
            description: What the tool does
            function: Function to execute
            parameters: Parameter descriptions
        """
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters
    
    async def execute(self, **kwargs) -> str:
        """Execute the tool with given arguments.
        
        Args:
            **kwargs: Tool arguments
            
        Returns:
            Tool result as string
        """
        try:
            # Check if function is async
            import asyncio
            if asyncio.iscoroutinefunction(self.function):
                result = await self.function(**kwargs)
            else:
                result = self.function(**kwargs)
            return str(result)
        except Exception as e:
            logger.error(f"Tool {self.name} execution failed: {e}")
            return f"Error: {str(e)}"


class AgenticToolSystem:
    """ReAct-based tool calling system for LLM agents."""
    
    def __init__(self):
        """Initialize tool system."""
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default tools."""
        # Time tools
        self.register_tool(
            name="get_current_time",
            description="Get the current time and date. Use this when user asks 'what time is it' or 'what's the date'.",
            function=self._get_current_time,
            parameters={}
        )
        
        self.register_tool(
            name="calculate_time_offset",
            description="Calculate what time it was X minutes/hours ago, or what time it will be in X minutes/hours. Use this for questions like 'what time was it 38 minutes ago' or 'what time will it be in 2 hours'.",
            function=self._calculate_time_offset,
            parameters={
                "offset_minutes": "int - Number of minutes to offset (positive or negative)",
                "direction": "str - Either 'past' or 'future'"
            }
        )
    
    def register_tool(self, name: str, description: str, function: Callable, parameters: Dict[str, str]):
        """Register a new tool.
        
        Args:
            name: Tool name
            description: Tool description
            function: Function to execute
            parameters: Parameter descriptions
        """
        self.tools[name] = Tool(name, description, function, parameters)
        logger.info(f"Registered tool: {name}")
    
    def get_tools_description(self) -> str:
        """Get description of all available tools for the LLM.
        
        Returns:
            Formatted tool descriptions
        """
        descriptions = ["=== AVAILABLE TOOLS ==="]
        descriptions.append("You can use these tools by responding with: TOOL: tool_name(arg1=value1, arg2=value2)")
        descriptions.append("")
        
        for tool in self.tools.values():
            desc = [f"• {tool.name}: {tool.description}"]
            if tool.parameters:
                desc.append("  Parameters:")
                for param, param_desc in tool.parameters.items():
                    desc.append(f"    - {param}: {param_desc}")
            descriptions.append("\n".join(desc))
        
        descriptions.append("")
        descriptions.append("Example usage:")
        descriptions.append('User: "What time was it 30 minutes ago?"')
        descriptions.append('You: TOOL: calculate_time_offset(offset_minutes=30, direction="past")')
        descriptions.append("System: [Tool result: 12:11 AM]")
        descriptions.append('You: "It was 12:11 AM, mortal."')
        descriptions.append("")
        descriptions.append("IMPORTANT: Only use tools when you need real-time data. Don't use tools for things you can answer directly.")
        
        return "\n".join(descriptions)
    
    def parse_tool_call(self, response: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Parse tool call from LLM response.
        
        Args:
            response: LLM response
            
        Returns:
            Tuple of (tool_name, arguments) or None
        """
        # Pattern: TOOL: tool_name(arg1=value1, arg2=value2)
        pattern = r'TOOL:\s*(\w+)\((.*?)\)'
        match = re.search(pattern, response, re.IGNORECASE)
        
        if not match:
            return None
        
        tool_name = match.group(1)
        args_str = match.group(2)
        
        # Parse arguments
        args = {}
        if args_str.strip():
            # Split by comma, but respect quotes
            arg_pattern = r'(\w+)\s*=\s*([^,]+)'
            for arg_match in re.finditer(arg_pattern, args_str):
                key = arg_match.group(1)
                value = arg_match.group(2).strip()
                
                # Remove quotes
                value = value.strip('"').strip("'")
                
                # Try to convert to int
                try:
                    value = int(value)
                except ValueError:
                    pass
                
                args[key] = value
        
        return tool_name, args
    
    async def execute_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool call.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"
        
        tool = self.tools[tool_name]
        result = await tool.execute(**arguments)
        
        logger.info(f"Executed tool {tool_name} with args {arguments}: {result}")
        
        return result
    
    async def process_with_tools(self, llm_generate_func: Callable, user_message: str, system_prompt: str, max_iterations: int = 3) -> str:
        """Process a message with tool support using ReAct pattern.
        
        Args:
            llm_generate_func: Async function to call LLM
            user_message: User's message
            system_prompt: System prompt
            max_iterations: Maximum tool-calling iterations
            
        Returns:
            Final response
        """
        # Add tool descriptions to system prompt
        enhanced_prompt = f"{system_prompt}\n\n{self.get_tools_description()}"
        
        conversation = [
            {"role": "system", "content": enhanced_prompt},
            {"role": "user", "content": user_message}
        ]
        
        for iteration in range(max_iterations):
            # Get LLM response
            response = await llm_generate_func(conversation)
            
            # Check if LLM wants to use a tool
            tool_call = self.parse_tool_call(response)
            
            if not tool_call:
                # No tool call, this is the final response
                return response
            
            tool_name, arguments = tool_call
            
            # Execute tool
            tool_result = await self.execute_tool_call(tool_name, arguments)
            
            # Add tool call and result to conversation
            conversation.append({"role": "assistant", "content": response})
            conversation.append({"role": "user", "content": f"[Tool result: {tool_result}]\n\nNow answer the user's original question using this information."})
        
        # Max iterations reached, get final response
        final_response = await llm_generate_func(conversation)
        return final_response
    
    # ===== Default Tool Implementations =====
    
    @staticmethod
    def _get_current_time() -> str:
        """Get current time and date.
        
        Returns:
            Current time string
        """
        now = datetime.now()
        return f"{now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}"
    
    @staticmethod
    def _calculate_time_offset(offset_minutes: int, direction: str) -> str:
        """Calculate time offset.
        
        Args:
            offset_minutes: Minutes to offset
            direction: 'past' or 'future'
            
        Returns:
            Calculated time string
        """
        now = datetime.now()
        
        if direction.lower() == "past":
            target_time = now - timedelta(minutes=offset_minutes)
        else:  # future
            target_time = now + timedelta(minutes=offset_minutes)
        
        return target_time.strftime('%I:%M %p')
