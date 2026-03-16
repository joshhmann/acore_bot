from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config import Config
from core.auth import AuthStore
from core.persona_engine import PersonaEngine
from core.router import Router
from core.runtime import GestaltRuntime
from memory.local_json import LocalJsonMemoryStore
from memory.manager import MemoryManager
from memory.rag import RAGStore
from memory.summary import DeterministicSummary
from personas.loader import load_persona_catalog, resolve_default_persona_id
from providers.openai_compat import OpenAICompatProvider
from providers.registry import PROVIDER_SPECS, canonical_provider_name
from providers.router import LegacyLLMProvider, ProviderRouter
from plugins.context import (
    MemoryPluginRegistry,
    PluginConfig,
    PluginContext,
    ProviderPluginRegistry,
    ToolPluginRegistry,
)
from plugins.loader import PluginLoader
from tools.file_ops import tool_file_list, tool_file_read, tool_file_write
from tools.mcp_source import MCPToolSource
from tools.policy import ToolPolicy
from tools.registry import ToolRegistry
from tools.runner import ToolRunner, tool_current_time, tool_n8n_webhook, tool_web_get
from tools.shell_exec import tool_shell_exec

if TYPE_CHECKING:
    from adapters.tui.app import CommandDeckApp
    from adapters.web.adapter import WebInputAdapter


logger = logging.getLogger(__name__)


def _run_coroutine_blocking(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_holder: dict[str, Any] = {}
    error_holder: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result_holder["value"] = asyncio.run(coro)
        except BaseException as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder.get("value")


def _register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register_tool(
        name="time",
        schema={
            "name": "time",
            "description": "Get current UTC time",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        handler=tool_current_time,
    )
    registry.register_tool(
        name="web_get",
        schema={
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
        },
        handler=tool_web_get,
    )
    registry.register_tool(
        name="n8n_webhook",
        schema={
            "name": "n8n_webhook",
            "description": "Call an n8n webhook endpoint",
            "parameters": {
                "type": "object",
                "properties": {
                    "webhook_url": {"type": "string"},
                    "payload": {"type": "object"},
                },
                "required": ["webhook_url"],
            },
        },
        handler=tool_n8n_webhook,
    )
    registry.register_tool(
        name="file_read",
        schema={
            "name": "file_read",
            "description": "Read a UTF-8 text file under the project root sandbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer"},
                    "project_root": {"type": "string"},
                },
                "required": ["path"],
            },
        },
        handler=tool_file_read,
    )
    registry.register_tool(
        name="file_list",
        schema={
            "name": "file_list",
            "description": "List files and directories under the project root sandbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "include_hidden": {"type": "boolean"},
                    "project_root": {"type": "string"},
                },
                "required": [],
            },
        },
        handler=tool_file_list,
    )
    registry.register_tool(
        name="file_write",
        schema={
            "name": "file_write",
            "description": "Write UTF-8 text to a file under the project root sandbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                    "project_root": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
        handler=tool_file_write,
    )
    registry.register_tool(
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
    )


def _register_mcp_tools(
    registry: ToolRegistry,
    policy: ToolPolicy,
    allowlist_by_env: dict[str, set[str]],
) -> None:
    mcp_source = MCPToolSource.from_env()
    if not mcp_source.enabled():
        return
    try:
        _run_coroutine_blocking(
            mcp_source.register(
                registry=registry,
                policy=policy,
                allowlists_by_env=allowlist_by_env,
            )
        )
    except Exception as exc:
        logger.warning("Failed to register MCP tools: %s", exc)


def build_gestalt_runtime(legacy_llm: Any | None = None) -> GestaltRuntime:
    personas = load_persona_catalog(Config.CHARACTERS_DIR)
    default_persona_id = resolve_default_persona_id(
        personas,
        preferred_id=str(getattr(Config, "CHARACTER", "")),
    )
    router = Router(default_persona_id=default_persona_id)

    memory_store = LocalJsonMemoryStore(root_dir="data/gestalt_memory")
    summary_engine = DeterministicSummary(max_chars=1200)
    memory_manager = MemoryManager(store=memory_store, summary_engine=summary_engine)
    persona_engine = PersonaEngine(memory_manager=memory_manager)
    rag_store = RAGStore()

    registry = ToolRegistry()

    n8n_enabled = os.getenv("GESTALT_N8N_ENABLED", "false").lower() == "true"
    web_enabled = os.getenv("GESTALT_WEB_TOOL_ENABLED", "false").lower() == "true"
    mcp_network_enabled = (
        os.getenv("GESTALT_MCP_NETWORK_ENABLED", "false").lower() == "true"
    )

    allowlist_by_env = {
        "discord": {"time"}
        | {"file_read", "file_list", "file_write"}
        | ({"web_get"} if web_enabled else set())
        | ({"n8n_webhook"} if n8n_enabled else set()),
        "cli": {
            "time",
            "web_get",
            "shell_exec",
            "file_read",
            "file_list",
            "file_write",
        },
        "web": {"time", "file_read", "file_list", "file_write"}
        | ({"web_get"} if web_enabled else set()),
        "autonomy": {"time", "shell_exec", "file_read", "file_list", "file_write"},
    }

    policy = ToolPolicy(
        allowlist_by_persona={},
        allowlist_by_environment=allowlist_by_env,
        max_tool_calls_per_turn=int(os.getenv("GESTALT_MAX_TOOL_CALLS_PER_TURN", "3")),
        network_enabled=(web_enabled or mcp_network_enabled),
        dangerous_enabled=False,
        tool_risk_tiers={},
    )

    providers: dict[str, Any] = {}
    default_provider_name = "legacy"
    if legacy_llm is not None:
        providers["legacy"] = LegacyLLMProvider(legacy_llm)
    else:
        auth_store = AuthStore()
        requested = str(getattr(Config, "LLM_PROVIDER", "ollama")).strip().lower()
        default_provider_name = canonical_provider_name(requested) or "ollama"

        def _provider_config(name: str) -> tuple[str, str, str]:
            spec = PROVIDER_SPECS[name]
            profile = auth_store.get_provider_config(name)
            fallback = auth_store.get_provider_config("openai")
            auth_secret = str(
                profile.get("api_key") or profile.get("token") or ""
            ).strip()
            if not auth_secret:
                auth_secret = str(
                    fallback.get("api_key") or fallback.get("token") or ""
                ).strip()

            if name == "openrouter":
                base_url = os.getenv(
                    "OPENAI_COMPAT_BASE_URL",
                    str(profile.get("base_url") or "")
                    or getattr(Config, "OPENROUTER_URL", spec.default_base_url),
                )
                model = os.getenv(
                    "OPENAI_COMPAT_MODEL",
                    str(profile.get("model") or "")
                    or getattr(Config, "OPENROUTER_MODEL", spec.default_model),
                )
                api_key = os.getenv(
                    "OPENAI_COMPAT_API_KEY",
                    auth_secret or getattr(Config, "OPENROUTER_API_KEY", ""),
                )
                return base_url, api_key, model

            if name == "ollama":
                base_url = os.getenv(
                    "OPENAI_COMPAT_BASE_URL",
                    str(profile.get("base_url") or "")
                    or f"{getattr(Config, 'OLLAMA_HOST', 'http://localhost:11434').rstrip('/')}/v1",
                )
                model = os.getenv(
                    "OPENAI_COMPAT_MODEL",
                    str(profile.get("model") or "")
                    or getattr(Config, "OLLAMA_MODEL", spec.default_model),
                )
                api_key = os.getenv("OPENAI_COMPAT_API_KEY", auth_secret)
                return base_url, api_key, model

            base_url = os.getenv(
                "OPENAI_COMPAT_BASE_URL",
                str(profile.get("base_url") or "")
                or getattr(Config, "OPENAI_COMPAT_BASE_URL", spec.default_base_url),
            )
            model = os.getenv(
                "OPENAI_COMPAT_MODEL",
                str(profile.get("model") or "")
                or getattr(Config, "OPENAI_COMPAT_MODEL", spec.default_model),
            )
            api_key = os.getenv("OPENAI_COMPAT_API_KEY", auth_secret)
            return base_url, api_key, model

        timeout_seconds = int(os.getenv("OPENAI_COMPAT_TIMEOUT_SECONDS", "60"))
        for provider_name in ["openai", "openrouter", "ollama"]:
            base_url, api_key, model = _provider_config(provider_name)
            provider = OpenAICompatProvider(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout_seconds,
            )
            provider.available_models = list(
                PROVIDER_SPECS[provider_name].available_models
            )
            providers[provider_name] = provider

        if default_provider_name not in providers:
            default_provider_name = "ollama"

    provider_router = ProviderRouter(
        default_provider_name=default_provider_name,
        providers=providers,
        persona_provider_map={},
        provider_specs=dict(PROVIDER_SPECS),
    )

    plugins_enabled = os.getenv("GESTALT_PLUGINS_ENABLED", "true").lower() == "true"
    strict_plugins = os.getenv("GESTALT_STRICT_PLUGINS", "false").lower() == "true"
    if plugins_enabled:
        plugin_ctx = PluginContext(
            tools=ToolPluginRegistry(
                registry=registry, policy=policy, allowlists_by_env=allowlist_by_env
            ),
            providers=ProviderPluginRegistry(provider_router),
            memory=MemoryPluginRegistry(memory_manager=memory_manager),
            config=PluginConfig(),
            logger=logger,
        )
        try:
            _run_coroutine_blocking(
                PluginLoader.load_all(plugin_ctx, Path(__file__).resolve().parents[1])
            )
            _run_coroutine_blocking(plugin_ctx.tools.activate_tool_sources())
        except Exception as exc:
            if strict_plugins:
                raise
            logger.warning("Plugin load failed, continuing: %s", exc)
    else:
        _register_builtin_tools(registry)
        policy.tool_risk_tiers["time"] = "safe"
        policy.tool_risk_tiers["web_get"] = "network"
        policy.tool_risk_tiers["n8n_webhook"] = "network"
        policy.tool_risk_tiers["shell_exec"] = "safe"
        policy.tool_risk_tiers["file_read"] = "safe"
        policy.tool_risk_tiers["file_list"] = "safe"
        policy.tool_risk_tiers["file_write"] = "safe"
        _register_mcp_tools(registry, policy, allowlist_by_env)

    runner = ToolRunner(registry=registry, policy=policy)

    return GestaltRuntime(
        router=router,
        persona_engine=persona_engine,
        provider_router=provider_router,
        tool_runner=runner,
        memory_manager=memory_manager,
        summary_engine=summary_engine,
        rag_store=rag_store,
        personas=personas,
        tool_policy=policy,
    )


@dataclass
class RuntimeHost:
    """Shared maintained runtime host for standalone runtime-first surfaces."""

    legacy_llm: Any | None = None
    _runtime: GestaltRuntime | None = None

    @property
    def runtime(self) -> GestaltRuntime:
        if self._runtime is None:
            self._runtime = build_gestalt_runtime(legacy_llm=self.legacy_llm)
        return self._runtime

    def create_web_adapter(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> "WebInputAdapter":
        from adapters.web.adapter import WebInputAdapter

        return WebInputAdapter(host=host, port=port, runtime=self.runtime)

    def create_tui_app(
        self,
        *,
        flags: dict[str, Any] | None = None,
    ) -> "CommandDeckApp":
        from adapters.tui.app import CommandDeckApp

        return CommandDeckApp(flags=flags, runtime=self.runtime)

    async def close(self) -> None:
        if self._runtime is None:
            return
        await self._runtime.close()
        self._runtime = None


def create_runtime(*, legacy_llm: Any | None = None) -> GestaltRuntime:
    """Build the canonical Gestalt runtime for standalone or adapter use."""
    return create_runtime_host(legacy_llm=legacy_llm).runtime


def create_runtime_host(*, legacy_llm: Any | None = None) -> RuntimeHost:
    """Create a maintained standalone host for the canonical Gestalt runtime."""
    return RuntimeHost(legacy_llm=legacy_llm)
