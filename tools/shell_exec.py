from __future__ import annotations

import asyncio
import json
import re
from time import perf_counter
from typing import Any


_DANGEROUS_PATTERNS = [
    re.compile(r"(^|\s)rm\s+-rf(\s|$)"),
    re.compile(r"(^|\s)(mkfs|shutdown|reboot|halt|poweroff)(\s|$)"),
    re.compile(r"(^|\s)dd\s+"),
    re.compile(r"(^|\s)chmod\s+777(\s|$)"),
    re.compile(r">\s*/"),
    re.compile(r"(^|\s)git\s+reset\s+--hard(\s|$)"),
    re.compile(r"(^|\s)(tee|truncate|sed\s+-i)(\s|$)"),
]


def is_dangerous_command(command: str) -> bool:
    text = command.strip().lower()
    if not text:
        return True
    return any(pattern.search(text) for pattern in _DANGEROUS_PATTERNS)


def redact_command(command: str) -> str:
    redacted = re.sub(
        r"(?i)(api[_-]?key|token|password|secret)=\S+",
        r"\1=<redacted>",
        command,
    )
    if len(redacted) > 160:
        return redacted[:160] + "..."
    return redacted


async def tool_shell_exec(arguments: dict[str, Any]) -> str:
    command = str(arguments.get("command") or "").strip()
    if not command:
        raise ValueError("Missing 'command'")

    allow_dangerous = bool(arguments.get("allow_dangerous", False))
    if is_dangerous_command(command) and not allow_dangerous:
        raise PermissionError("Command blocked by safety policy")

    timeout_seconds = max(1, min(120, int(arguments.get("timeout_seconds") or 20)))
    max_chars = max(200, min(20000, int(arguments.get("max_output_chars") or 4000)))

    started = perf_counter()
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
    except TimeoutError:
        timed_out = True
        proc.kill()
        stdout_raw, stderr_raw = await proc.communicate()
    duration_ms = int((perf_counter() - started) * 1000)

    stdout = (stdout_raw or b"").decode("utf-8", errors="replace")
    stderr = (stderr_raw or b"").decode("utf-8", errors="replace")
    combined = stdout + ("\n" if stdout and stderr else "") + stderr
    truncated = len(combined) > max_chars
    if truncated:
        keep_stdout = stdout[:max_chars]
        remaining = max(0, max_chars - len(keep_stdout))
        keep_stderr = stderr[:remaining]
        stdout = keep_stdout
        stderr = keep_stderr

    exit_code = int(proc.returncode or 0)
    if timed_out:
        exit_code = 124

    payload = {
        "command": redact_command(command),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "truncated": truncated,
        "summary": f"exit={exit_code} stdout={len(stdout)} stderr={len(stderr)}",
    }
    return json.dumps(payload, ensure_ascii=True)
