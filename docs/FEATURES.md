# Feature Status

Canonical product-feature status for the maintained Gestalt surfaces.

Approved status labels:
- `Verified active`
- `Present but not loaded`
- `Present but unused`
- `Deprecated candidate`
- `Not implemented`

## Runtime Core

- Runtime orchestration (`core/runtime.py`): `Verified active`
- Runtime assembly and host lifecycle (`gestalt/runtime_bootstrap.py`): `Verified active`
- Provider routing (`providers/*`): `Verified active`
- Tool registry and policy (`tools/*`): `Verified active`
- Memory isolation and context cache (`memory/*`): `Verified active`
- Persona catalog-driven defaults (`personas/*`): `Verified active`

## Surface Adapters

- Web runtime API and websocket transport (`adapters/web/*`): `Verified active`
- CLI runtime routing (`adapters/cli/*`): `Verified active`
- TUI runtime command deck (`adapters/tui/*`): `Verified active`
- Standalone stdio runtime hosting (`gestalt/cli_entry.py`, `adapters/runtime_stdio.py`): `Verified active`
- Discord runtime-host startup module (`adapters/discord/discord_bot.py`): `Verified active`
- Discord maintained runtime chat surface (`adapters/discord/commands/runtime_chat.py`): `Verified active`
- Discord maintained runtime profile/status surface (`adapters/discord/commands/profile.py`): `Verified active`
- Discord maintained runtime ask/search surface (`adapters/discord/commands/search.py`): `Verified active`
- Discord legacy hybrid chat seam (`adapters/discord/commands/chat/main.py`): `Deprecated candidate`
- Browser/Tauri client (`adapters/desktop/*`): `Present but not loaded`

## Runtime-Native Features

- Runtime session bootstrap/listing: `Verified active`
- Runtime social-state bootstrap/mutation: `Verified active`
- Shared adapter event builder (`core/interfaces.py`): `Verified active`
- Runtime command registry (`core/commands.py`): `Verified active`
- Runtime `/swarm` delegation flow: `Verified active`
- Runtime context cache introspection/reset: `Verified active`

## Transitional and Legacy Areas

- Legacy Discord operator/persona admin seams (`DISCORD_LEGACY_*`): `Present but unused`
- Legacy `main.py` Discord startup path: `Deprecated candidate`
- `services/*` feature ownership in maintained paths: `Deprecated candidate`
- Experimental planner/social-intelligence areas under `core/*`: `Present but unused`

## Deferred Product Areas

- Adapter SDK expansion beyond current contract seed: `Present but unused`
- Voice runtime contract beyond Discord boundary coverage: `Present but unused`
- Surface-adapter HTTP API for Slack/Telegram/Discord-class adapters: `Not implemented`
- Full browser/Tauri productization: `Not implemented`

## Notes

- This file tracks maintained product truth, not every historical or legacy repo capability.
- Historical reports under `docs/reports/` are not canonical product status.
