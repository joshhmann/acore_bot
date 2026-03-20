from __future__ import annotations

import asyncio
import importlib
import sys
from typing import Sequence

from core.auth import AuthStore
from gestalt.env import load_environment_profile


def _load_cli_main():
    return importlib.import_module("adapters.cli.__main__")


cli_main = _load_cli_main()


def _strip_env_profile(argv: Sequence[str]) -> tuple[str, list[str]]:
    args = list(argv)
    profile = ""
    stripped: list[str] = []
    skip_next = False
    for index, value in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if value == "--env-profile" and index + 1 < len(args):
            profile = str(args[index + 1] or "").strip().lower()
            skip_next = True
            continue
        if str(value).startswith("--env-profile="):
            profile = str(value).split("=", 1)[1].strip().lower()
            continue
        stripped.append(str(value))
    return profile, stripped


def _run_tui(args: Sequence[str]) -> int:
    del args
    return 0


def _auth_interactive_enabled(_args: Sequence[str]) -> bool:
    return sys.stdin.isatty()


def _select_provider_interactive(store: AuthStore) -> str:
    providers = store.list_providers()
    return providers[0] if providers else "openrouter"


def _prompt_with_default(_label: str, default: str) -> str:
    return default


def _prompt_model(_provider: str, default: str) -> str:
    return default


def _redact(secret: str) -> str:
    if not secret:
        return ""
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"****{tail}"


def _handle_auth(argv: Sequence[str]) -> int:
    if not argv:
        print("auth requires a subcommand")
        return 2

    command = str(argv[0])
    store = AuthStore()
    if command == "list":
        detailed = "--long" in argv
        for item in store.list_provider_summaries():
            provider = str(item.get("provider") or "")
            if detailed:
                base_url = str(item.get("base_url") or "")
                model = str(item.get("model") or "")
                has_secret = bool(item.get("has_api_key") or item.get("has_token"))
                print(
                    f"{provider} base_url={base_url} model={model} secret={'yes' if has_secret else 'no'}"
                )
            else:
                has_secret = bool(item.get("has_api_key") or item.get("has_token"))
                marker = _redact("present") if has_secret else "none"
                print(f"{provider} secret={marker}")
        return 0

    if command == "logout":
        if len(argv) < 2:
            print("auth logout requires provider")
            return 2
        provider = str(argv[1])
        removed = store.remove_provider(provider)
        print(f"removed {provider}" if removed else f"missing {provider}")
        return 0

    if command != "login":
        print(f"unknown auth subcommand: {command}")
        return 2

    args = list(argv[1:])
    provider = ""
    api_key = ""
    base_url = ""
    model = ""
    index = 0
    while index < len(args):
        current = str(args[index])
        if current.startswith("--"):
            if current == "--api-key" and index + 1 < len(args):
                api_key = str(args[index + 1])
                index += 2
                continue
            if current == "--base-url" and index + 1 < len(args):
                base_url = str(args[index + 1])
                index += 2
                continue
            if current == "--model" and index + 1 < len(args):
                model = str(args[index + 1])
                index += 2
                continue
            index += 1
            continue
        if not provider:
            provider = current
        index += 1

    interactive = _auth_interactive_enabled(argv)
    if not provider:
        if not interactive:
            print("Non-interactive auth login requires provider")
            return 2
        provider = _select_provider_interactive(store)

    provider = str(provider).strip().lower()
    if provider != "openrouter":
        if interactive and not base_url:
            base_url = _prompt_with_default("base_url", base_url)
        if interactive and not model:
            model = _prompt_model(provider, model)

    store.upsert_provider(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    print(f"saved {provider} {_redact(api_key)}")
    return 0


def _dispatch(argv: Sequence[str]) -> int:
    profile, raw_args = _strip_env_profile(argv)
    load_environment_profile(profile)

    if raw_args[:2] == ["runtime", "--stdio"]:
        from gestalt.runtime_stdio import run_stdio_server

        return asyncio.run(run_stdio_server())

    if raw_args and raw_args[0] == "auth":
        return _handle_auth(raw_args[1:])

    if raw_args and raw_args[0] == "cli":
        return _load_cli_main().cli(raw_args[1:])

    if not raw_args:
        if sys.stdin.isatty():
            return _run_tui(raw_args)
        return cli_main.cli(["--no-interactive"])

    return cli_main.cli(raw_args)
