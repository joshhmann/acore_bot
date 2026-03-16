from __future__ import annotations

from tools.runner import tool_current_time, tool_n8n_webhook, tool_web_get
from tools.shell_exec import tool_shell_exec


def register(ctx) -> None:
    web_enabled = ctx.config.env_bool("GESTALT_WEB_TOOL_ENABLED", False)
    n8n_enabled = ctx.config.env_bool("GESTALT_N8N_ENABLED", False)

    ctx.tools.register_tool(
        name="time",
        schema={
            "name": "time",
            "description": "Get current UTC time",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        handler=tool_current_time,
        metadata={"origin": "builtin"},
    )
    ctx.tools.set_risk_tier("time", "safe")

    web_schema = {
        "name": "web_get",
        "description": "Fetch text from a URL",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout_seconds": {"type": "integer"},
            },
            "required": ["url"],
        },
    }
    ctx.tools.register_tool(
        name="web_get",
        schema=web_schema,
        handler=tool_web_get,
        metadata={"origin": "builtin"},
    )
    ctx.tools.set_risk_tier("web_get", "network")

    n8n_schema = {
        "name": "n8n_webhook_stub",
        "description": "Call an n8n webhook endpoint",
        "parameters": {
            "type": "object",
            "properties": {
                "webhook_url": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["webhook_url"],
        },
    }
    ctx.tools.register_tool(
        name="n8n_webhook_stub",
        schema=n8n_schema,
        handler=tool_n8n_webhook,
        metadata={"origin": "builtin"},
    )
    ctx.tools.set_risk_tier("n8n_webhook_stub", "network")

    ctx.tools.register_tool(
        name="n8n_webhook",
        schema={
            **n8n_schema,
            "name": "n8n_webhook",
        },
        handler=tool_n8n_webhook,
        metadata={"origin": "builtin", "alias_of": "n8n_webhook_stub"},
    )
    ctx.tools.set_risk_tier("n8n_webhook", "network")

    ctx.tools.allow_in_environment("discord", "time")
    ctx.tools.allow_in_environment("cli", "time")
    ctx.tools.allow_in_environment("web", "time")
    ctx.tools.allow_in_environment("autonomy", "time")

    ctx.tools.allow_in_environment("cli", "web_get")
    if web_enabled:
        ctx.tools.allow_in_environment("discord", "web_get")
        ctx.tools.allow_in_environment("web", "web_get")

    if n8n_enabled:
        ctx.tools.allow_in_environment("discord", "n8n_webhook")
        ctx.tools.allow_in_environment("discord", "n8n_webhook_stub")

    ctx.tools.register_tool(
        name="shell_exec",
        schema={
            "name": "shell_exec",
            "description": "Execute a shell command with runtime safety guards",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                    "max_output_chars": {"type": "integer"},
                },
                "required": ["command"],
            },
        },
        handler=tool_shell_exec,
        metadata={"origin": "builtin"},
    )
    ctx.tools.set_risk_tier("shell_exec", "safe")
    ctx.tools.allow_in_environment("cli", "shell_exec")
    ctx.tools.allow_in_environment("autonomy", "shell_exec")
