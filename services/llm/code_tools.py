"""Code execution tools with sandboxing for the enhanced tool system."""

import asyncio
import hashlib
import io
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import Config

logger = logging.getLogger(__name__)

CODE_CACHE_DIR = Config.DATA_DIR / "code_cache"
CODE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SANDBOX_ENABLED = Config.CODE_SANDBOX_ENABLED
SANDBOX_TIMEOUT = Config.CODE_EXECUTION_TIMEOUT
MAX_OUTPUT_SIZE = Config.CODE_MAX_OUTPUT_SIZE


@dataclass
class CodeResult:
    """Result from code execution."""

    success: bool
    output: str
    error: Optional[str] = None
    execution_time: Optional[float] = None
    memory_used: Optional[int] = None
    return_code: Optional[int] = None


@dataclass
class CommandResult:
    """Result from command execution."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    error: Optional[str] = None


@dataclass
class ExplanationResult:
    """Result from code explanation."""

    summary: str
    complexity: str
    key_points: List[str]
    potential_issues: List[str]
    suggestions: List[str]


@dataclass
class AnalysisResult:
    """Result from code analysis."""

    bugs: List[str]
    security_issues: List[str]
    style_issues: List[str]
    complexity_score: int
    suggestions: List[str]


def _create_sandbox_globals() -> Dict[str, Any]:
    """Create restricted globals for sandboxed execution."""
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "ascii": ascii,
        "bin": bin,
        "bool": bool,
        "bytearray": bytearray,
        "bytes": bytes,
        "callable": callable,
        "chr": chr,
        "complex": complex,
        "dict": dict,
        "divmod": divmod,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "frozenset": frozenset,
        "getattr": getattr,
        "hasattr": hasattr,
        "hash": hash,
        "hex": hex,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "iter": iter,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "object": object,
        "oct": oct,
        "ord": ord,
        "pow": pow,
        "print": print,
        "range": range,
        "repr": repr,
        "reversed": reversed,
        "round": round,
        "set": set,
        "setattr": setattr,
        "slice": slice,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "type": type,
        "zip": zip,
    }

    return {
        "__builtins__": safe_builtins,
        "__name__": "__sandbox__",
        "__doc__": None,
        "__package__": None,
    }


def _create_sandbox_locals() -> Dict[str, Any]:
    """Create restricted locals for sandboxed execution."""
    return {}


class PythonSandbox:
    """Sandboxed Python code execution environment."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._execution_lock = asyncio.Lock()

    async def execute(self, code: str, capture_output: bool = True) -> CodeResult:
        """Execute Python code in sandboxed environment."""
        start_time = datetime.now()

        if not SANDBOX_ENABLED:
            return await self._execute_unsafe(code, capture_output, start_time)

        return await self._execute_sandboxed(code, capture_output, start_time)

    async def _execute_sandboxed(
        self, code: str, capture_output: bool, start_time: datetime
    ) -> CodeResult:
        """Execute code with sandboxing."""
        async with self._execution_lock:
            try:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                globals_dict = _create_sandbox_globals()
                locals_dict = _create_sandbox_locals()

                def run_code():
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    try:
                        exec(code, globals_dict, locals_dict)
                    finally:
                        sys.stdout = sys.__stdout__
                        sys.stderr = sys.__stderr__

                loop = asyncio.get_event_loop()
                future = loop.run_in_executor(None, run_code)

                try:
                    await asyncio.wait_for(future, timeout=self.timeout)
                except asyncio.TimeoutError:
                    return CodeResult(
                        success=False,
                        output="",
                        error=f"Execution timed out after {self.timeout} seconds",
                        execution_time=self.timeout,
                        return_code=-1,
                    )

                execution_time = (datetime.now() - start_time).total_seconds()

                stdout_output = stdout_capture.getvalue()
                stderr_output = stderr_capture.getvalue()

                if len(stdout_output) > MAX_OUTPUT_SIZE:
                    stdout_output = (
                        stdout_output[:MAX_OUTPUT_SIZE]
                        + f"\n... (truncated, {len(stdout_output)} total chars)"
                    )
                if len(stderr_output) > MAX_OUTPUT_SIZE:
                    stderr_output = (
                        stderr_output[:MAX_OUTPUT_SIZE]
                        + f"\n... (truncated, {len(stderr_output)} total chars)"
                    )

                if stderr_output:
                    return CodeResult(
                        success=False,
                        output=stdout_output,
                        error=stderr_output,
                        execution_time=execution_time,
                        return_code=1,
                    )

                return CodeResult(
                    success=True,
                    output=stdout_output,
                    execution_time=execution_time,
                    return_code=0,
                )

            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(f"Code execution error: {e}")
                return CodeResult(
                    success=False,
                    output="",
                    error=str(e),
                    execution_time=execution_time,
                    return_code=1,
                )

    async def _execute_unsafe(
        self, code: str, capture_output: bool, start_time: datetime
    ) -> CodeResult:
        """Execute code without sandboxing (for trusted environments)."""
        try:
            globals_dict = {"__builtins__": __builtins__}
            locals_dict = {}

            if capture_output:
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, globals_dict, locals_dict)

                output = stdout_capture.getvalue()
                error = stderr_capture.getvalue()

                execution_time = (datetime.now() - start_time).total_seconds()

                if error:
                    return CodeResult(
                        success=False,
                        output=output,
                        error=error,
                        execution_time=execution_time,
                        return_code=1,
                    )

                return CodeResult(
                    success=True,
                    output=output,
                    execution_time=execution_time,
                    return_code=0,
                )
            else:
                exec(code, globals_dict, locals_dict)

                execution_time = (datetime.now() - start_time).total_seconds()
                return CodeResult(
                    success=True,
                    output="",
                    execution_time=execution_time,
                    return_code=0,
                )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Code execution error: {e}")
            return CodeResult(
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time,
                return_code=1,
            )


class BashExecutor:
    """Safe bash command execution."""

    DANGEROUS_PATTERNS = [
        r"rm\s+-rf",
        r"mkfs",
        r"dd\s+if=",
        r":\(\)\s*\{",
        r"curl.*\|\s*sh",
        r"wget.*\|\s*sh",
        r"chmod\s+777",
        r"chown",
        r"userdel",
        r"groupdel",
        r"shutdown",
        r"reboot",
        r"halt",
        r"killall",
        r"pkill\s+-9",
        r">\s*/dev/sda",
        r"&&rm",
        r"\|\|rm",
        r";rm",
        r"`rm`",
        r"\$\(rm\)",
    ]

    BLOCKED_COMMANDS = {
        "rm",
        "del",
        "erase",
        "format",
        "shred",
        "dd",
        "mkfs",
        "chmod",
        "chown",
        "chgrp",
        "useradd",
        "userdel",
        "groupadd",
        "groupdel",
        "passwd",
        "su",
        "sudo",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
        "kill",
        "killall",
        "pkill",
        "xkill",
        "nc",
        "netcat",
        "ncat",
        "socat",
        "ssh",
        "scp",
        "rsync",
        "git",
        "git remote",
        "docker",
        "kubectl",
        "apt-get",
        "apt",
        "yum",
        "dnf",
        "pip install",
        "npm install",
        "composer",
    }

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        import re

        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS
        ]

    def _check_dangerous(self, command: str) -> Optional[str]:
        """Check for dangerous patterns in command."""
        cmd_lower = command.lower()

        for i, pattern in enumerate(self._compiled_patterns):
            try:
                if pattern.search(cmd_lower):
                    return f"Dangerous pattern detected: {self.DANGEROUS_PATTERNS[i]}"
            except:
                pass

        for cmd in self.BLOCKED_COMMANDS:
            if cmd in cmd_lower.split():
                return f"Blocked command detected: {cmd}"

        return None

    async def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Execute bash command safely."""
        start_time = datetime.now()

        danger = self._check_dangerous(command)
        if danger:
            return CommandResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                execution_time=0,
                error=danger,
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                limit=MAX_OUTPUT_SIZE * 2,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout or self.timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return CommandResult(
                    success=False,
                    stdout="",
                    stderr="",
                    return_code=-1,
                    execution_time=timeout or self.timeout,
                    error=f"Command timed out after {timeout or self.timeout} seconds",
                )

            execution_time = (datetime.now() - start_time).total_seconds()

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if len(stdout_text) > MAX_OUTPUT_SIZE:
                stdout_text = (
                    stdout_text[:MAX_OUTPUT_SIZE]
                    + f"\n... (truncated, {len(stdout_text)} total chars)"
                )
            if len(stderr_text) > MAX_OUTPUT_SIZE:
                stderr_text = (
                    stderr_text[:MAX_OUTPUT_SIZE]
                    + f"\n... (truncated, {len(stderr_text)} total chars)"
                )

            return CommandResult(
                success=proc.returncode == 0,
                stdout=stdout_text,
                stderr=stderr_text,
                return_code=proc.returncode or 0,
                execution_time=execution_time,
                error=stderr_text if proc.returncode != 0 else None,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Bash execution error: {e}")
            return CommandResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                execution_time=execution_time,
                error=str(e),
            )


class CodeToolSystem:
    """Code execution tool wrapper for EnhancedToolSystem."""

    def __init__(self):
        self.python_sandbox = PythonSandbox(SANDBOX_TIMEOUT)
        self.bash_executor = BashExecutor()
        self._language_cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, code: str, lang: str) -> str:
        key_string = f"{lang}:{code}"
        return hashlib.md5(key_string.encode()).hexdigest()

    async def run_python(
        self, code: str, timeout: int = 30, capture_output: bool = True
    ) -> str:
        """Execute Python code in sandboxed environment."""
        if not Config.CODE_EXECUTION_ENABLED:
            return "Error: Code execution is disabled."

        result = await self.python_sandbox.execute(code, capture_output)

        if result.success:
            output = (
                result.output.strip()
                if result.output
                else "Code executed successfully (no output)"
            )
            response = (
                f"Output:\n{output}\n\nExecution time: {result.execution_time:.3f}s"
            )
            if result.memory_used:
                response += f", Memory: {result.memory_used}KB"
            return response
        else:
            return f"Error:\n{result.error}\n\nExecution time: {result.execution_time:.3f}s"

    async def run_bash(
        self, command: str, timeout: int = 60, working_dir: Optional[str] = None
    ) -> str:
        """Execute bash command safely."""
        if not Config.CODE_EXECUTION_ENABLED:
            return "Error: Code execution is disabled."

        result = await self.bash_executor.execute(command, working_dir, timeout)

        output_parts = []
        if result.stdout:
            output_parts.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output_parts.append(f"STDERR:\n{result.stderr}")
        output_parts.append(f"Return code: {result.return_code}")
        output_parts.append(f"Execution time: {result.execution_time:.3f}s")

        if result.error:
            output_parts.insert(0, f"BLOCKED: {result.error}")

        return "\n\n".join(output_parts)

    async def explain_code(
        self, code: str, language: str, detail_level: str = "medium"
    ) -> str:
        """Get LLM-powered code explanation."""
        cache_key = self._get_cache_key(code, language)
        cache_file = CODE_CACHE_DIR / f"explain_{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    logger.debug(f"Code explanation cache hit: {cache_key}")
                    result = ExplanationResult(**data)
                    return self._format_explanation(result, detail_level)
            except:
                pass

        explanation = await self._analyze_code_with_llm(code, language, "explain")

        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "summary": explanation.summary,
                        "complexity": explanation.complexity,
                        "key_points": explanation.key_points,
                        "potential_issues": explanation.potential_issues,
                        "suggestions": explanation.suggestions,
                    },
                    f,
                    indent=2,
                )
        except:
            pass

        return self._format_explanation(explanation, detail_level)

    def _format_explanation(self, result: ExplanationResult, detail_level: str) -> str:
        lines = [f"## Code Explanation\n\n**Summary:** {result.summary}\n"]
        lines.append(f"**Complexity:** {result.complexity}\n")

        if detail_level in ["medium", "high"]:
            lines.append("\n**Key Points:**")
            for point in result.key_points:
                lines.append(f"- {point}")

        if detail_level == "high":
            lines.append("\n**Potential Issues:**")
            for issue in result.potential_issues:
                lines.append(f"- {issue}")

            lines.append("\n**Suggestions:**")
            for suggestion in result.suggestions:
                lines.append(f"- {suggestion}")

        return "\n".join(lines)

    async def analyze_code(self, code: str, language: str) -> str:
        """Static analysis for bugs, security issues, style."""
        cache_key = self._get_cache_key(code, language)
        cache_file = CODE_CACHE_DIR / f"analyze_{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    logger.debug(f"Code analysis cache hit: {cache_key}")
                    result = AnalysisResult(**data)
                    return self._format_analysis(result)
            except:
                pass

        analysis = await self._analyze_code_with_llm(code, language, "analyze")

        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "bugs": analysis.bugs,
                        "security_issues": analysis.security_issues,
                        "style_issues": analysis.style_issues,
                        "complexity_score": analysis.complexity_score,
                        "suggestions": analysis.suggestions,
                    },
                    f,
                    indent=2,
                )
        except:
            pass

        return self._format_analysis(analysis)

    def _format_analysis(self, result: AnalysisResult) -> str:
        lines = ["## Code Analysis\n"]

        if result.bugs:
            lines.append("\n**🐛 Bugs:**")
            for bug in result.bugs:
                lines.append(f"- {bug}")
        else:
            lines.append("\n**✅ No obvious bugs detected**")

        if result.security_issues:
            lines.append("\n**🔒 Security Issues:**")
            for issue in result.security_issues:
                lines.append(f"- {issue}")
        else:
            lines.append("\n**✅ No security issues detected**")

        if result.style_issues:
            lines.append("\n**🎨 Style Issues:**")
            for issue in result.style_issues:
                lines.append(f"- {issue}")

        lines.append(f"\n**📊 Complexity Score:** {result.complexity_score}/10")

        if result.suggestions:
            lines.append("\n**💡 Suggestions:**")
            for suggestion in result.suggestions:
                lines.append(f"- {suggestion}")

        return "\n".join(lines)

    async def _analyze_code_with_llm(
        self, code: str, language: str, analysis_type: str
    ) -> Any:
        """Use LLM for code analysis or explanation."""
        from services.llm.openrouter import OpenRouterService

        system_prompt = """You are a code analysis assistant. Analyze the provided code and return a JSON object with your findings.
For explanations: return {"summary": "...", "complexity": "...", "key_points": [...], "potential_issues": [...], "suggestions": [...]}
For analysis: return {"bugs": [...], "security_issues": [...], "style_issues": [...], "complexity_score": int, "suggestions": [...]}

Return ONLY valid JSON, no markdown formatting."""

        if analysis_type == "explain":
            user_prompt = f"""Explain this {language} code:
```
{code}
```"""
        else:
            user_prompt = f"""Analyze this {language} code for bugs, security issues, and style:
```
{code}
```"""

        try:
            llm = OpenRouterService(
                api_key=Config.OPENROUTER_API_KEY,
                model=Config.OPENROUTER_MODEL,
            )

            response = await llm.generate(system_prompt, user_prompt, max_tokens=1000)

            import json

            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > 0:
                data = json.loads(response[start:end])
            else:
                data = {}

            if analysis_type == "explain":
                return ExplanationResult(
                    summary=data.get("summary", "Unable to analyze code"),
                    complexity=data.get("complexity", "Unknown"),
                    key_points=data.get("key_points", []),
                    potential_issues=data.get("potential_issues", []),
                    suggestions=data.get("suggestions", []),
                )
            else:
                return AnalysisResult(
                    bugs=data.get("bugs", []),
                    security_issues=data.get("security_issues", []),
                    style_issues=data.get("style_issues", []),
                    complexity_score=data.get("complexity_score", 5),
                    suggestions=data.get("suggestions", []),
                )
        except Exception as e:
            logger.error(f"LLM code analysis error: {e}")
            if analysis_type == "explain":
                return ExplanationResult(
                    summary=f"Analysis failed: {str(e)}",
                    complexity="Unknown",
                    key_points=[],
                    potential_issues=[],
                    suggestions=[],
                )
            else:
                return AnalysisResult(
                    bugs=[],
                    security_issues=[],
                    style_issues=[],
                    complexity_score=5,
                    suggestions=[],
                )


code_tool_system = CodeToolSystem()
