from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from core.schemas import ToolCall, ToolResult
from memory.base import MemoryNamespace


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PlayConfig:
    persona_id: str
    room_id: str
    server_name: str
    bot_name: str
    steps: int = 10
    tick_seconds: float = 1.0
    enable_network_tools: bool = False
    dry_run: bool = False
    verbose: bool = False


class PlayRunner:
    def __init__(self, runtime: Any, config: PlayConfig) -> None:
        self.runtime = runtime
        self.config = config
        self.tool_runner = runtime.tool_runner
        self.policy = runtime.tool_policy
        self.registry = self.tool_runner.registry
        self._tool_get_state = f"mcp:{config.server_name}:get_state"
        self._tool_walk_to = f"mcp:{config.server_name}:walk_to"
        self._tool_interact = f"mcp:{config.server_name}:interact"

    def validate_startup(self) -> tuple[bool, str | None]:
        required = [self._tool_get_state, self._tool_walk_to]
        missing = [name for name in required if self.registry.get(name) is None]
        if missing:
            return (
                False,
                "Missing required MCP tools: "
                + ", ".join(missing)
                + "\nEnsure these are configured and enabled:"
                + "\n- GESTALT_MCP_ENABLED=true"
                + "\n- GESTALT_MCP_SERVERS='[...]'"
                + "\n- GESTALT_MCP_NETWORK_ENABLED=true",
            )
        return True, None

    def validate_network_gating(self) -> tuple[bool, str | None]:
        if self.config.enable_network_tools:
            self.policy.network_enabled = True
        if not self.policy.network_enabled:
            return (
                False,
                "MCP tools are network-tier and currently disabled. "
                "Re-run with --enable-network-tools or set "
                "GESTALT_MCP_NETWORK_ENABLED=true.",
            )
        return True, None

    async def run(self) -> int:
        ok, msg = self.validate_startup()
        if not ok:
            print(msg)
            return 2

        ok, msg = self.validate_network_gating()
        if not ok:
            print(msg)
            return 2

        for step in range(1, max(1, self.config.steps) + 1):
            state_result = await self._get_state()
            state = self._decode_output_json(state_result.output)

            actions = self._choose_actions(state)
            action_results = await self._execute_actions(actions)
            commentary = await self._commentary(
                state=state, action_results=action_results
            )

            print(f"[step {step}/{self.config.steps}] {commentary}")
            if self.config.verbose:
                self._print_verbose(
                    state_result=state_result, actions=actions, results=action_results
                )

            if step < self.config.steps and self.config.tick_seconds > 0:
                await asyncio.sleep(self.config.tick_seconds)

        return 0

    async def _get_state(self) -> ToolResult:
        args = self._build_args_for_tool(self._tool_get_state)
        calls = [ToolCall(name=self._tool_get_state, arguments=args)]
        results = await self.tool_runner.execute(
            persona_id=self.config.persona_id,
            environment="cli",
            tool_calls=calls,
        )
        return (
            results[0]
            if results
            else ToolResult(name=self._tool_get_state, error="No result")
        )

    def _choose_actions(self, state: dict[str, Any]) -> list[ToolCall]:
        actions: list[ToolCall] = []
        interact_exists = self.registry.get(self._tool_interact) is not None

        entities = self._extract_entities(state)
        if interact_exists and entities:
            target = entities[0]
            interact_args = self._build_interact_args(target)
            actions.append(ToolCall(name=self._tool_interact, arguments=interact_args))
        else:
            walk_args = self._build_walk_to_args(state)
            actions.append(ToolCall(name=self._tool_walk_to, arguments=walk_args))

        max_calls = max(1, int(self.policy.max_tool_calls_per_turn))
        return actions[:max_calls]

    async def _execute_actions(self, actions: list[ToolCall]) -> list[ToolResult]:
        if not actions:
            return []
        if self.config.dry_run:
            return [
                ToolResult(
                    name=call.name,
                    output=f"dry-run: {json.dumps(call.arguments, ensure_ascii=True)}",
                )
                for call in actions
            ]
        return await self.tool_runner.execute(
            persona_id=self.config.persona_id,
            environment="cli",
            tool_calls=actions,
        )

    async def _commentary(
        self, state: dict[str, Any], action_results: list[ToolResult]
    ) -> str:
        persona = self.runtime.personas.by_id(self.config.persona_id)
        if persona is None:
            persona_name = self.config.persona_id
            personality = ""
        else:
            persona_name = persona.display_name
            personality = persona.personality

        namespace = MemoryNamespace(
            persona_id=self.config.persona_id, room_id=self.config.room_id
        )
        style_prompt = (
            await self.runtime.persona_engine.build_system_prompt(
                persona=persona
                if persona is not None
                else self.runtime.personas.all()[0],
                namespace=namespace,
                summary="",
                rag_context="",
            )
            if self.runtime.personas.all()
            else ""
        )

        if action_results:
            last = action_results[-1]
            if last.error:
                return f"{persona_name}: The wheel of fate stutters; {last.name} failed ({last.error})."
            action_line = f"{last.name} succeeded"
        else:
            action_line = "I wait, poised"

        has_entities = bool(self._extract_entities(state))
        mood_hint = (
            "with contempt"
            if "dagoth" in self.config.persona_id.lower()
            else "with focus"
        )
        if "dagoth" in self.config.persona_id.lower():
            return (
                f"{persona_name}: {action_line}. Mortals, behold my path {mood_hint}."
            )
        if personality or style_prompt:
            suffix = "entities in sight" if has_entities else "no obvious targets"
            return f"{persona_name}: {action_line}; {suffix}."
        return f"{persona_name}: {action_line}."

    def _print_verbose(
        self,
        state_result: ToolResult,
        actions: list[ToolCall],
        results: list[ToolResult],
    ) -> None:
        print(f"  state_tool={state_result.name} error={state_result.error or 'none'}")
        if actions:
            for call in actions:
                print(
                    f"  call {call.name} args={json.dumps(call.arguments, ensure_ascii=True)}"
                )
        if results:
            for result in results:
                summary = (
                    result.error if result.error else self._truncate(result.output)
                )
                print(f"  result {result.name}: {summary}")

    def _build_args_for_tool(self, tool_name: str) -> dict[str, Any]:
        args: dict[str, Any] = {}
        definition = self.registry.get(tool_name)
        if definition is None:
            return args

        required = self._required_params(definition.schema)
        if "bot_name" in required or "bot_name" in self._all_param_names(
            definition.schema
        ):
            args["bot_name"] = self.config.bot_name
        return args

    def _build_walk_to_args(self, state: dict[str, Any]) -> dict[str, Any]:
        args = self._build_args_for_tool(self._tool_walk_to)
        x, y = self._extract_xy(state)
        if x is not None and y is not None:
            if "x" in self._all_param_names_from_tool(self._tool_walk_to):
                args["x"] = x + 1
            if "y" in self._all_param_names_from_tool(self._tool_walk_to):
                args["y"] = y
        if "target" in self._all_param_names_from_tool(self._tool_walk_to):
            args.setdefault(
                "target",
                {
                    "x": (x + 1) if x is not None else 3200,
                    "y": y if y is not None else 3200,
                },
            )
        return args

    def _build_interact_args(self, target: dict[str, Any]) -> dict[str, Any]:
        args = self._build_args_for_tool(self._tool_interact)
        params = self._all_param_names_from_tool(self._tool_interact)

        if "action" in params:
            args.setdefault("action", "examine")
        if "target" in params:
            args.setdefault(
                "target", target.get("name") or target.get("id") or "unknown"
            )
        if "target_id" in params and "id" in target:
            args.setdefault("target_id", target.get("id"))
        if "target_name" in params:
            args.setdefault("target_name", target.get("name") or "unknown")
        return args

    def _all_param_names_from_tool(self, tool_name: str) -> set[str]:
        definition = self.registry.get(tool_name)
        if definition is None:
            return set()
        return self._all_param_names(definition.schema)

    @staticmethod
    def _required_params(schema: dict[str, Any]) -> set[str]:
        params = schema.get("parameters") if isinstance(schema, dict) else {}
        required = params.get("required") if isinstance(params, dict) else []
        return {str(item) for item in required if isinstance(item, str)}

    @staticmethod
    def _all_param_names(schema: dict[str, Any]) -> set[str]:
        params = schema.get("parameters") if isinstance(schema, dict) else {}
        properties = params.get("properties") if isinstance(params, dict) else {}
        return (
            {str(key) for key in properties.keys()}
            if isinstance(properties, dict)
            else set()
        )

    @staticmethod
    def _decode_output_json(raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {"value": value}
        except Exception:
            return {"raw": text}

    @staticmethod
    def _extract_entities(state: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("entities", "visible_entities", "npcs", "objects"):
            value = state.get(key)
            if isinstance(value, list):
                out: list[dict[str, Any]] = []
                for item in value:
                    if isinstance(item, dict):
                        out.append(item)
                if out:
                    return out
        return []

    @staticmethod
    def _extract_xy(state: dict[str, Any]) -> tuple[int | None, int | None]:
        if isinstance(state.get("position"), dict):
            pos = state["position"]
            return PlayRunner._to_int(pos.get("x")), PlayRunner._to_int(pos.get("y"))
        return PlayRunner._to_int(state.get("x")), PlayRunner._to_int(state.get("y"))

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _truncate(text: str, limit: int = 180) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."
