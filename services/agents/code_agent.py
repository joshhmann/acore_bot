"""Code agent for code execution, analysis, and explanation."""

import logging
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from services.agents.base import BaseAgent, AgentResult, AgentType, AgentConfidence
from services.agents.tools import CodeExecutionTool, ToolRegistry, CodeResult

logger = logging.getLogger(__name__)


class CodeAgent(BaseAgent):
    """Agent specialized in code-related tasks.

    Capabilities:
    - Safe code execution (sandboxed)
    - Code analysis and explanation
    - Bug detection and fixes
    - Multi-language support (Python, JS, Rust, Go)
    - Code review and optimization suggestions
    """

    name = "CodeAgent"
    description = "Executes and analyzes code in multiple programming languages"
    agent_type = AgentType.CODE
    capabilities = [
        "code_execution",
        "code_analysis",
        "bug_detection",
        "code_explanation",
        "code_optimization",
        "multi_language",
    ]

    def __init__(
        self,
        code_tool: CodeExecutionTool = None,
        llm_service=None,
        timeout: float = 30.0,
    ):
        """Initialize code agent.

        Args:
            code_tool: Code execution tool.
            llm_service: LLM service for analysis.
            timeout: Maximum execution time.
        """
        super().__init__(timeout=timeout)
        self._code_tool = code_tool
        self._llm = llm_service

        self._language_patterns = {
            "python": r"(python|py\b|pyton)",
            "javascript": r"(javascript|js\b|node\.?js|nodejs)",
            "typescript": r"(typescript|ts\b)",
            "rust": r"(rust\b|rs\b)",
            "go": r"(golang|go\b)",
            "java": r"(java\b)",
            "c++": r"(c\+\+|cpp|c plus plus)",
            "c#": r"(c#|csharp|dot net)",
        }

    async def can_handle(self, request: str) -> float:
        """Determine if code agent should handle this request.

        Args:
            request: User request.

        Returns:
            Confidence score 0-1.
        """
        request_lower = request.lower()

        # Explicit code execution patterns
        explicit_patterns = [
            r"run\s+(this|the|my)?\s*code",
            r"execute\s+(this|the|my)?\s*code",
            r"run\s+python",
            r"run\s+javascript",
            r"test\s+this\s+code",
            r"execute\s+this\s+snippet",
        ]

        for pattern in explicit_patterns:
            if re.search(pattern, request_lower):
                return AgentConfidence.CERTAIN.value

        # Language detection
        detected_language = self._detect_language(request_lower)

        # Code analysis patterns
        analysis_patterns = [
            r"explain\s+(this|the|my)?\s*code",
            r"analyze\s+(this|the|my)?\s*code",
            r"what\s+does\s+(this|the|my)?\s*code\s+do",
            r"debug\s+(this|the|my)?\s*code",
            r"fix\s+(this|the|my)?\s*code",
            r"optimize\s+(this|the|my)?\s*code",
            r"review\s+(this|the|my)?\s*code",
            r"write\s+(some|a)?\s*code",
            r"create\s+(some|a)?\s*code",
            r"how\s+to\s+[a-z]+\s+in\s+[a-z]+",
        ]

        has_analysis = any(re.search(p, request_lower) for p in analysis_patterns)

        # Check for code blocks
        has_code_blocks = "```" in request or "`" * 3 in request

        # Check for function/class definitions
        has_definitions = any(
            kw in request_lower
            for kw in ["def ", "class ", "function ", "const ", "let ", "fn ", "func "]
        )

        if detected_language:
            if has_code_blocks or has_definitions:
                return AgentConfidence.CERTAIN.value
            elif has_analysis:
                return AgentConfidence.HIGH.value
            else:
                return AgentConfidence.MEDIUM.value

        if has_code_blocks:
            return AgentConfidence.HIGH.value

        if has_analysis and (detected_language or has_definitions):
            return AgentConfidence.HIGH.value

        # Programming question pattern
        programming_question = r"(how|what|why|when|where)\s+.*(?:in\s+)?(?:python|javascript|rust|go|java|c\+\+|c#)"

        if re.search(programming_question, request_lower):
            return AgentConfidence.MEDIUM.value

        return AgentConfidence.VERY_LOW.value

    async def process(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Process code request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with code analysis or execution result.
        """
        # Extract code and detect language
        code, language = self._extract_code(request)

        if code:
            return await self._handle_code_execution(request, code, language, context)
        else:
            return await self._handle_code_question(request, context)

    def _detect_language(self, request: str) -> Optional[str]:
        """Detect programming language in request.

        Args:
            request: Request string.

        Returns:
            Language string or None.
        """
        request_lower = request.lower()

        for lang, pattern in self._language_patterns.items():
            if re.search(pattern, request_lower):
                return lang

        # Try to detect from code blocks
        code_block_match = re.search(r"```(\w+)", request)
        if code_block_match:
            detected = code_block_match.group(1).lower()
            if detected in ["js", "javascript"]:
                return "javascript"
            elif detected in ["ts", "typescript"]:
                return "typescript"
            elif detected in ["py", "python"]:
                return "python"
            elif detected in ["rs", "rust"]:
                return "rust"
            elif detected == "go":
                return "go"
            return detected

        return None

    def _extract_code(self, request: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract code and detect language from request.

        Args:
            request: User request.

        Returns:
            Tuple of (code, language).
        """
        # Check for code blocks
        code_block_match = re.search(r"```(\w+)?\n([\s\S]*?)```", request)

        if code_block_match:
            language = code_block_match.group(1) or self._detect_language(request)
            code = code_block_match.group(2).strip()
            return code, language

        # Check for inline code
        inline_match = re.search(r"`([^`]+)`", request)

        if inline_match:
            code = inline_match.group(1).strip()
            language = self._detect_language(request)
            return code, language

        return None, None

    async def _handle_code_execution(
        self,
        request: str,
        code: str,
        language: Optional[str],
        context: Dict[str, Any],
    ) -> AgentResult:
        """Handle code execution request.

        Args:
            request: User request.
            code: Code to execute.
            language: Programming language.
            context: Additional context.

        Returns:
            AgentResult with execution result.
        """
        if not self._code_tool:
            return AgentResult(
                success=False,
                content="Code execution is not available.",
                agent_type=self.agent_type,
                error="Code execution tool not available",
            )

        # Determine language if not detected
        if not language:
            language = self._detect_language(request)
            if not language:
                # Try to detect from code content
                language = self._detect_from_code(code)

        if not language:
            return AgentResult(
                success=False,
                content="Could not detect programming language. Please specify.",
                agent_type=self.agent_type,
                error="Language not detected",
            )

        # Execute code
        result = await self._code_tool.execute(language=language, code=code)

        # Format response
        if result.success:
            content = self._format_success_response(result, code)
        else:
            content = self._format_error_response(result, code)

        return AgentResult(
            success=result.success,
            content=content,
            agent_type=self.agent_type,
            confidence=0.9 if result.success else 0.7,
            metadata={
                "language": language,
                "execution_time_ms": result.execution_time_ms,
                "return_code": result.return_code,
            },
        )

    async def _handle_code_question(
        self, request: str, context: Dict[str, Any]
    ) -> AgentResult:
        """Handle code-related question.

        Args:
            request: User question.
            context: Additional context.

        Returns:
            AgentResult with explanation.
        """
        if not self._llm:
            return AgentResult(
                success=False,
                content="Code analysis requires LLM service.",
                agent_type=self.agent_type,
                error="LLM not available",
            )

        # Detect language
        language = self._detect_language(request)

        system_prompt = """You are a helpful programming assistant. Explain code
        concepts clearly, help debug issues, and provide working code examples.
        Be concise but thorough."""

        user_prompt = request

        if language:
            user_prompt += f"\n\n(Using {language} context)"

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=1000,
            )

            return AgentResult(
                success=True,
                content=response,
                agent_type=self.agent_type,
                confidence=0.8,
                metadata={"language": language},
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content=f"Code analysis failed: {str(e)}",
                agent_type=self.agent_type,
                error=str(e),
            )

    def _detect_from_code(self, code: str) -> Optional[str]:
        """Detect language from code content.

        Args:
            code: Code string.

        Returns:
            Language string or None.
        """
        code_lower = code.lower()

        # Python indicators
        if any(
            ind in code
            for ind in ["import ", "from ", "def ", "class ", "print(", "if __name__"]
        ):
            return "python"

        # JavaScript/TypeScript indicators
        if any(
            ind in code
            for ind in [
                "function ",
                "const ",
                "let ",
                "=>",
                "console.log",
                "module.exports",
            ]
        ):
            return (
                "javascript"
                if "interface " not in code and "type " not in code
                else "typescript"
            )

        # Rust indicators
        if any(
            ind in code
            for ind in ["fn main", "let mut", "println!", "struct ", "impl "]
        ):
            return "rust"

        # Go indicators
        if any(
            ind in code for ind in ["package main", "func ", "fmt.", "var ", "const "]
        ):
            return "go"

        return None

    def _format_success_response(self, result: CodeResult, code: str) -> str:
        """Format successful execution response.

        Args:
            result: CodeResult.
            code: Original code.

        Returns:
            Formatted response string.
        """
        parts = ["**Execution Result:**"]

        if result.stdout:
            parts.append("```\n" + result.stdout.strip() + "\n```")

        if result.execution_time_ms > 0:
            parts.append(f"\n*Executed in {result.execution_time_ms:.0f}ms*")

        return "\n".join(parts)

    def _format_error_response(self, result: CodeResult, code: str) -> str:
        """Format error response.

        Args:
            result: CodeResult.
            code: Original code.

        Returns:
            Formatted error response.
        """
        parts = ["**Execution Error:**"]

        if result.stderr:
            parts.append("```\n" + result.stderr.strip() + "\n```")
        elif result.error:
            parts.append(result.error)

        parts.append(f"\n*Return code: {result.return_code}*")

        return "\n".join(parts)


class CodeAgentFactory:
    """Factory for creating CodeAgent instances."""

    @staticmethod
    def create(
        code_tool: CodeExecutionTool = None,
        llm_service=None,
    ) -> CodeAgent:
        """Create code agent.

        Args:
            code_tool: Code execution tool.
            llm_service: LLM service instance.

        Returns:
            Configured CodeAgent.
        """
        if code_tool is None:
            code_tool = CodeExecutionTool()

        return CodeAgent(
            code_tool=code_tool,
            llm_service=llm_service,
        )
