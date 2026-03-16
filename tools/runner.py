from __future__ import annotations

from datetime import datetime, timezone
import json
from time import perf_counter
from typing import Any

import aiohttp

from core.schemas import ToolCall, ToolResult

from .policy import ToolPolicy
from .registry import ToolRegistry


class ToolRunner:
    def __init__(self, registry: ToolRegistry, policy: ToolPolicy) -> None:
        self.registry = registry
        self.policy = policy

    async def execute(
        self,
        persona_id: str,
        environment: str,
        tool_calls: list[ToolCall],
    ) -> list[ToolResult]:
        results, _ = await self.execute_with_trace(
            persona_id=persona_id,
            environment=environment,
            tool_calls=tool_calls,
        )
        return results

    async def execute_with_trace(
        self,
        persona_id: str,
        environment: str,
        tool_calls: list[ToolCall],
    ) -> tuple[list[ToolResult], list[dict[str, Any]]]:
        allowed = self.policy.allowed_tools(
            persona_id=persona_id, environment=environment
        )
        capped_calls = tool_calls[: self.policy.max_tool_calls_per_turn]
        results: list[ToolResult] = []
        traces: list[dict[str, Any]] = []
        for call in capped_calls:
            if not self.policy.is_tool_allowed(call.name, allowed):
                results.append(
                    ToolResult(name=call.name, error="Tool not allowed by policy")
                )
                traces.append(
                    {
                        "trace_type": "decision",
                        "reason": "Tool rejected by allowlist/risk policy",
                        "selected_tool": call.name,
                        "allowed": False,
                        "policy": {
                            "network_enabled": self.policy.network_enabled,
                            "dangerous_enabled": self.policy.dangerous_enabled,
                            "max_tool_calls_per_turn": self.policy.max_tool_calls_per_turn,
                        },
                    }
                )
                continue
            tool = self.registry.get(call.name)
            if tool is None:
                results.append(ToolResult(name=call.name, error="Tool not found"))
                traces.append(
                    {
                        "trace_type": "decision",
                        "reason": "Tool missing from registry",
                        "selected_tool": call.name,
                        "allowed": False,
                    }
                )
                continue
            traces.append(
                {
                    "trace_type": "decision",
                    "reason": "Tool selected for execution",
                    "selected_tool": call.name,
                    "allowed": True,
                    "policy": {
                        "max_tool_calls_per_turn": self.policy.max_tool_calls_per_turn,
                    },
                }
            )
            started = perf_counter()
            try:
                output = await tool.handler(call.arguments)
                duration_ms = int((perf_counter() - started) * 1000)
                result = ToolResult(
                    name=call.name,
                    output=output,
                    metadata={"duration_ms": duration_ms},
                )
                results.append(result)
                safe_args = self._safe_trace_args(
                    name=call.name, arguments=call.arguments
                )
                summary = "success"
                trace_extra: dict[str, Any] = {}
                if call.name == "shell_exec":
                    shell_data = self._shell_result(output)
                    if isinstance(shell_data, dict):
                        exit_code = shell_data.get("exit_code")
                        if isinstance(exit_code, int):
                            trace_extra["exit_code"] = exit_code
                            summary = f"exit={exit_code}"
                        trace_extra["output_summary"] = str(
                            shell_data.get("summary") or summary
                        )
                        trace_extra["truncated"] = bool(
                            shell_data.get("truncated", False)
                        )
                traces.append(
                    {
                        "trace_type": "tool",
                        "name": call.name,
                        "args": safe_args,
                        "duration_ms": duration_ms,
                        "result_summary": summary,
                        **trace_extra,
                    }
                )
            except Exception as exc:
                duration_ms = int((perf_counter() - started) * 1000)
                results.append(
                    ToolResult(
                        name=call.name,
                        error=str(exc),
                        metadata={"duration_ms": duration_ms},
                    )
                )
                safe_args = self._safe_trace_args(
                    name=call.name, arguments=call.arguments
                )
                traces.append(
                    {
                        "trace_type": "tool",
                        "name": call.name,
                        "args": safe_args,
                        "duration_ms": duration_ms,
                        "result_summary": "error",
                        "error": str(exc),
                    }
                )
        return results, traces

    @staticmethod
    def _safe_trace_args(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        safe = dict(arguments)
        if name == "shell_exec" and "command" in safe:
            safe["command"] = "<redacted>"
        return safe

    @staticmethod
    def _shell_result(output: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None


async def tool_current_time(_: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat()


async def tool_web_get(arguments: dict[str, Any]) -> str:
    url = str(arguments.get("url") or "").strip()
    if not url:
        raise ValueError("Missing 'url'")
    timeout = int(arguments.get("timeout_seconds") or 10)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            text = await resp.text()
            return text[:2000]


async def tool_n8n_webhook(arguments: dict[str, Any]) -> str:
    webhook_url = str(arguments.get("webhook_url") or "").strip()
    if not webhook_url:
        raise ValueError("n8n webhook disabled or missing URL")
    payload = arguments.get("payload") or {}
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload) as resp:
            return f"status={resp.status}"
