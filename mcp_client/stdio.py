from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from .base import MCPToolSpec, MCPTransport


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StdioMCPTransport(MCPTransport):
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    startup_timeout_seconds: float = 10.0

    _process: asyncio.subprocess.Process | None = field(default=None, init=False)
    _request_id: int = field(default=0, init=False)
    _lock: asyncio.Lock | None = field(default=None, init=False)
    _lock_loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)
    _stderr_task: asyncio.Task[None] | None = field(default=None, init=False)

    async def list_tools(self) -> list[MCPToolSpec]:
        result = await self._request(method="tools/list", params={})
        raw_tools = result.get("tools") if isinstance(result, dict) else []
        specs: list[MCPToolSpec] = []
        for item in raw_tools if isinstance(raw_tools, list) else []:
            if not isinstance(item, dict):
                continue
            specs.append(
                MCPToolSpec(
                    name=str(item.get("name") or ""),
                    description=str(item.get("description") or ""),
                    input_schema=dict(item.get("inputSchema") or {}),
                )
            )
        return specs

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._request(
            method="tools/call",
            params={"name": name, "arguments": args},
        )
        if isinstance(result, dict):
            return result
        return {"result": result}

    async def aclose(self) -> None:
        process = self._process
        self._process = None
        self._initialized = False
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            self._stderr_task = None

    async def _ensure_started(self) -> None:
        if self._process and self._process.returncode is None:
            return

        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in self.env.items()})

        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=env,
        )
        if self._process.stderr is not None:
            self._stderr_task = asyncio.create_task(
                self._drain_stderr(self._process.stderr)
            )
        self._initialized = False

    async def _initialize(self) -> None:
        if self._initialized:
            return
        await self._request_locked(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "acore-bot", "version": "0.1.0"},
            },
        )
        await self._notify(method="notifications/initialized", params={})
        self._initialized = True

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        lock = self._current_loop_lock()
        async with lock:
            await self._ensure_started()
            await self._initialize_if_needed(method)
            return await self._request_locked(method=method, params=params)

    def _current_loop_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    async def _request_locked(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        self._require_process()
        self._request_id += 1
        request_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        await self._write_message(payload)

        try:
            response = await asyncio.wait_for(
                self._read_message(),
                timeout=self.startup_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"MCP stdio request timed out for method {method}"
            ) from exc

        if int(response.get("id", -1)) != request_id:
            raise RuntimeError("MCP stdio response id mismatch")
        if "error" in response and response["error"] is not None:
            error = response["error"]
            if isinstance(error, dict):
                message = str(error.get("message") or error)
            else:
                message = str(error)
            raise RuntimeError(f"MCP stdio error for {method}: {message}")

        result = response.get("result")
        return result if isinstance(result, dict) else {"result": result}

    async def _initialize_if_needed(self, method: str) -> None:
        if self._initialized or method == "initialize":
            return
        await self._initialize()

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._write_message(payload)

    async def _write_message(self, payload: dict[str, Any]) -> None:
        process = self._require_process()
        stdin = process.stdin
        if stdin is None:
            raise RuntimeError("MCP stdio stdin unavailable")
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        stdin.write(body + b"\n")
        await stdin.drain()

    async def _read_message(self) -> dict[str, Any]:
        process = self._require_process()
        stdout = process.stdout
        if stdout is None:
            raise RuntimeError("MCP stdio stdout unavailable")

        line = await stdout.readline()
        if not line:
            raise RuntimeError("MCP stdio closed before response")
        stripped = line.strip()

        if stripped.lower().startswith(b"content-length:"):
            content_length = self._parse_content_length(
                stripped.decode("ascii", errors="replace")
            )
            separator = await stdout.readline()
            if separator.strip():
                raise RuntimeError("MCP stdio expected blank separator line")
            body = await stdout.readexactly(content_length)
            message = json.loads(body.decode("utf-8"))
        else:
            message = json.loads(stripped.decode("utf-8"))
        if not isinstance(message, dict):
            raise RuntimeError("MCP stdio message is not a JSON object")
        return message

    @staticmethod
    def _parse_content_length(header_text: str) -> int:
        if header_text.lower().startswith("content-length:"):
            value = header_text.split(":", 1)[1].strip()
            return int(value)
        raise RuntimeError("MCP stdio missing Content-Length header")

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise RuntimeError("MCP stdio process not started")
        if self._process.returncode is not None:
            raise RuntimeError(
                f"MCP stdio process exited with code {self._process.returncode}"
            )
        return self._process

    async def _drain_stderr(self, stream: asyncio.StreamReader) -> None:
        try:
            while True:
                line = await stream.readline()
                if not line:
                    return
                logger.warning(
                    "[mcp-stdio] %s", line.decode("utf-8", errors="replace").rstrip()
                )
        except Exception:
            return
