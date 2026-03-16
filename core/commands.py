from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Any, Callable

from core.schemas import ErrorOutput, StateMutation, StructuredOutput, TextOutput


@dataclass(slots=True)
class CommandSpec:
    name: str
    description: str
    arguments_schema: dict[str, Any]
    examples: list[str]
    aliases: list[str] | None = None


@dataclass(slots=True)
class ParsedCommand:
    name: str
    args: dict[str, Any]
    raw: str


@dataclass(slots=True)
class CommandResult:
    outputs: list[TextOutput | StructuredOutput | ErrorOutput]
    mutations: list[StateMutation]


@dataclass(slots=True)
class CommandContext:
    session_id: str
    persona_id: str
    mode: str
    platform: str
    flags: dict[str, Any]


CommandHandler = Callable[[ParsedCommand, CommandContext], CommandResult]


class CommandRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, CommandSpec] = {}
        self._handlers: dict[str, CommandHandler] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self, spec: CommandSpec, handler: CommandHandler | None = None
    ) -> None:
        self._specs[spec.name] = spec
        for alias in spec.aliases or []:
            clean_alias = alias.strip().lower().lstrip("/")
            if clean_alias:
                self._aliases[clean_alias] = spec.name
        if handler is not None:
            self._handlers[spec.name] = handler

    def specs(self) -> list[CommandSpec]:
        return [self._specs[name] for name in sorted(self._specs.keys())]

    def parse(self, raw: str) -> ParsedCommand | ErrorOutput:
        text = raw.strip()
        if not text.startswith("/"):
            return ErrorOutput(
                code="INVALID_COMMAND_FORMAT",
                message="Commands must start with '/'.",
                hint="Try /help",
            )

        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return ErrorOutput(
                code="COMMAND_PARSE_ERROR",
                message=f"Failed to parse command: {exc}",
                hint="Check quote pairing and try again.",
            )

        if not tokens:
            return ErrorOutput(
                code="EMPTY_COMMAND",
                message="No command provided.",
                hint="Try /help",
            )

        name = tokens[0].lstrip("/").strip().lower()
        if not name:
            return ErrorOutput(
                code="EMPTY_COMMAND",
                message="No command provided.",
                hint="Try /help",
            )

        canonical_name = self._aliases.get(name, name)
        if canonical_name not in self._specs:
            return ErrorOutput(
                code="UNKNOWN_COMMAND",
                message=f"Unknown command '/{name}'.",
                hint="Run /help to list available commands.",
            )

        args: dict[str, Any] = {}
        idx = 1
        while idx < len(tokens):
            token = tokens[idx]
            if token.startswith("--"):
                key = token[2:].strip().replace("-", "_")
                if not key:
                    return ErrorOutput(
                        code="INVALID_FLAG",
                        message=f"Invalid flag '{token}'.",
                        hint="Use --name value or boolean flags.",
                    )
                next_index = idx + 1
                if next_index < len(tokens) and not tokens[next_index].startswith("--"):
                    args[key] = tokens[next_index]
                    idx += 2
                    continue
                args[key] = True
                idx += 1
                continue

            positional = args.get("_positional")
            if isinstance(positional, list):
                positional.append(token)
            else:
                args["_positional"] = [token]
            idx += 1

        return ParsedCommand(name=canonical_name, args=args, raw=text)

    def validate(self, command: ParsedCommand) -> ParsedCommand | ErrorOutput:
        if command.name in {
            "help",
            "status",
            "context",
            "tools",
            "recap",
            "continue",
            "stop",
            "eval",
            "models",
        }:
            if command.name == "context":
                positional = command.args.get("_positional")
                if (
                    not isinstance(command.args.get("action"), str)
                    and isinstance(positional, list)
                    and positional
                ):
                    command.args["action"] = str(positional[0]).strip().lower()
            if command.name == "models":
                positional = command.args.get("_positional")
                if (
                    not isinstance(command.args.get("provider"), str)
                    and isinstance(positional, list)
                    and positional
                ):
                    command.args["provider"] = str(positional[0])
            return command

        if command.name == "trace":
            raw_limit = command.args.get("limit")
            if isinstance(raw_limit, str):
                try:
                    command.args["limit"] = int(raw_limit)
                except ValueError:
                    return ErrorOutput(
                        code="INVALID_LIMIT",
                        message=f"Invalid limit value '{raw_limit}'.",
                        hint="Usage: /trace --limit 20",
                    )
            elif raw_limit is None:
                command.args["limit"] = 10
            elif not isinstance(raw_limit, int):
                return ErrorOutput(
                    code="INVALID_LIMIT",
                    message="Invalid limit value.",
                    hint="Usage: /trace --limit 20",
                )
            return command

        if command.name == "mode":
            mode_name = command.args.get("name")
            if not isinstance(mode_name, str) or not mode_name.strip():
                positional = command.args.get("_positional")
                if isinstance(positional, list) and positional:
                    command.args["name"] = str(positional[0])
                else:
                    return ErrorOutput(
                        code="MODE_REQUIRED",
                        message="Mode name is required.",
                        hint="Usage: /mode <name>",
                    )
            return command

        if command.name in {"persona", "switch"}:
            name = command.args.get("name")
            if not isinstance(name, str) or not name.strip():
                positional = command.args.get("_positional")
                if isinstance(positional, list) and positional:
                    command.args["name"] = str(positional[0])
            return command

        if command.name == "yolo":
            state = command.args.get("state")
            command.args["confirm"] = bool(command.args.get("confirm", False))
            if not isinstance(state, str) or not state.strip():
                positional = command.args.get("_positional")
                if isinstance(positional, list) and positional:
                    command.args["state"] = str(positional[0]).lower()
                return command
            command.args["state"] = state.strip().lower()
            return command

        if command.name == "model":
            spec = command.args.get("spec")
            if not isinstance(spec, str) or not spec.strip():
                positional = command.args.get("_positional")
                if isinstance(positional, list) and positional:
                    command.args["spec"] = str(positional[0])
            return command

        if command.name == "shell":
            value = command.args.get("command")
            if isinstance(value, str) and value.strip():
                return command
            positional = command.args.get("_positional")
            if isinstance(positional, list) and positional:
                command.args["command"] = " ".join(str(item) for item in positional)
                return command
            return ErrorOutput(
                code="SHELL_COMMAND_REQUIRED",
                message="Shell command is required.",
                hint="Usage: /shell --command 'ls -la'",
            )

        if command.name == "swarm":
            tasks_value = command.args.get("tasks")
            if not isinstance(tasks_value, str) or not tasks_value.strip():
                positional = command.args.get("_positional")
                if isinstance(positional, list) and positional:
                    command.args["tasks"] = " ".join(str(item) for item in positional)
                    tasks_value = command.args["tasks"]
                phase_value = command.args.get("phase")
                if phase_value is None and (
                    not isinstance(tasks_value, str) or not tasks_value.strip()
                ):
                    return ErrorOutput(
                        code="TASKS_REQUIRED",
                        message="At least one task or phase preset is required.",
                        hint="Usage: /swarm <task one> | <task two> [--personas a,b] or /swarm --phase phase2",
                    )
                if phase_value is not None and (
                    not isinstance(phase_value, str) or not phase_value.strip()
                ):
                    return ErrorOutput(
                        code="INVALID_PHASE",
                        message="Invalid phase value.",
                        hint="Usage: /swarm --phase phase2",
                    )
            personas_value = command.args.get("personas")
            if personas_value is not None and not isinstance(personas_value, str):
                return ErrorOutput(
                    code="INVALID_PERSONAS",
                    message="Invalid personas value.",
                    hint="Usage: /swarm --personas tai,scav <tasks>",
                )
            return command

        if command.name == "diff":
            path_value = command.args.get("path")
            content_value = command.args.get("content")
            positional = command.args.get("_positional")
            if (
                (not isinstance(path_value, str) or not path_value.strip())
                and isinstance(positional, list)
                and positional
            ):
                command.args["path"] = str(positional[0])
            if (
                (not isinstance(content_value, str) or not content_value)
                and isinstance(positional, list)
                and len(positional) > 1
            ):
                command.args["content"] = " ".join(str(item) for item in positional[1:])
            if (
                not isinstance(command.args.get("path"), str)
                or not str(command.args.get("path")).strip()
            ):
                return ErrorOutput(
                    code="PATH_REQUIRED",
                    message="File path is required.",
                    hint="Usage: /diff --path <relative-path> --content '<text>'",
                )
            if not isinstance(command.args.get("content"), str):
                return ErrorOutput(
                    code="CONTENT_REQUIRED",
                    message="Diff content is required.",
                    hint="Usage: /diff --path <relative-path> --content '<text>'",
                )
            return command

        if command.name in {"apply", "reject"}:
            value = command.args.get("id")
            if isinstance(value, str) and value.strip():
                return command
            positional = command.args.get("_positional")
            if isinstance(positional, list) and positional:
                command.args["id"] = str(positional[0])
                return command
            return ErrorOutput(
                code="CONFIRMATION_ID_REQUIRED",
                message="Confirmation id is required.",
                hint=f"Usage: /{command.name} <id>",
            )

        if command.name == "autopilot":
            raw_steps = command.args.get("steps")
            if isinstance(raw_steps, str):
                try:
                    command.args["steps"] = int(raw_steps)
                except ValueError:
                    return ErrorOutput(
                        code="INVALID_STEPS",
                        message=f"Invalid steps value '{raw_steps}'.",
                        hint="Use an integer between 3 and 7.",
                    )
            elif raw_steps is None:
                command.args["steps"] = 3
            elif not isinstance(raw_steps, int):
                return ErrorOutput(
                    code="INVALID_STEPS",
                    message="Invalid steps value.",
                    hint="Use an integer between 3 and 7.",
                )

            command.args["confirm"] = bool(command.args.get("confirm", False))
            return command

        return command

    def execute(
        self, command: ParsedCommand, context: CommandContext
    ) -> CommandResult | ErrorOutput:
        handler = self._handlers.get(command.name)
        if handler is None:
            return ErrorOutput(
                code="UNKNOWN_COMMAND",
                message=f"No handler registered for '/{command.name}'.",
                hint="Run /help to list available commands.",
            )
        return handler(command, context)
