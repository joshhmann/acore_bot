# Gestalt Status

**Last Updated**: 2026-03-19

## Current Direction

Gestalt is being realigned around a runtime-first product surface:

- `core/runtime.py`
- `adapters/cli/*`
- `adapters/tui/*`
- `adapters/web/*`
- `providers/*`
- `tools/*`
- `memory/*`

The browser client in `adapters/desktop/*` remains a useful scaffold, but it is not yet the canonical product surface.

## What Is Stable

- Runtime-native CLI command flow
- Textual TUI command deck
- Runtime-backed web HTTP and websocket transport
- Runtime adapter API session and social bootstrap endpoints
- Shared runtime bootstrap and host path for maintained entrypoints through `gestalt/runtime_bootstrap.py`
- Canonical runtime assembly now lives in `gestalt/runtime_bootstrap.py`; `adapters/runtime_factory.py` is now a compatibility shim plus legacy Discord helper exports
- Browser client runtime-backed session and social bootstrap wiring
- Browser client runtime-backed social-mode controls
- Provider routing, tool policy, and memory isolation
- Catalog-driven persona defaults on maintained CLI and web surfaces
- Runtime-native task swarm delegation through `/swarm`, including coordinator summaries and persisted swarm outcomes
- Runtime phase-focused multi-agent swarm presets through `/swarm --phase phaseN`
- Runtime-owned social session state for Discord mode/status surfaces
- Runtime-native Discord slash chat path
- Maintained Discord startup now loads a dedicated runtime-native chat cog (`adapters/discord/commands/runtime_chat.py`)
- Maintained Discord help and `botstatus` commands now route through runtime command/status outputs on the runtime-host startup path
- Maintained Discord profile `status` and ask/search commands now route through runtime-only command surfaces
- Runtime-owned Discord on-message response decision + response path
- Normalized Discord on-message decision-fact payload into runtime
- Discord adapter now sends a thinner normalized fact payload instead of adapter-owned response-policy flags on the maintained on-message path
- Runtime now owns persona name extraction for maintained Discord on-message routing; the adapter no longer derives persona-name trigger semantics locally
- Runtime-owned Discord session/channel response gates
- Runtime now owns ignored-user response gating for the maintained Discord on-message path
- Runtime now owns `#ignore` response gating for the maintained Discord on-message path
- Runtime now owns muted-state and direct-unmute response policy for the maintained Discord on-message path
- Runtime now owns non-persona bot-author response gating for the maintained Discord on-message path
- Discord RL commands are now explicitly opt-in on the legacy startup path via `RL_ENABLED` instead of loading unconditionally
- Discord bot-conversation commands are now explicitly opt-in on the legacy startup path via `BOT_CONVERSATION_ENABLED` instead of reading like a maintained default surface
- Discord voice commands are now explicitly opt-in on the legacy startup path via `DISCORD_VOICE_ENABLED` and still require TTS availability
- Discord loaded ambient chat controls are now explicitly opt-in behind `DISCORD_LEGACY_CHAT_AMBIENT_ENABLED`; runtime-backed social controls remain the maintained mode/status path
- Discord loaded end-session chat controls are now explicitly opt-in behind `DISCORD_LEGACY_CHAT_SESSION_ENABLED`; they are not treated as maintained runtime session control
- Discord local social mode footers are now explicitly opt-in behind `DISCORD_LEGACY_SOCIAL_MODE_FOOTER_ENABLED`; runtime-backed social mode/status remain the maintained social surface
- Discord local facilitator/bandit status insights are now explicitly opt-in behind `DISCORD_LEGACY_SOCIAL_INSIGHTS_ENABLED`; `/social status` defaults to runtime-backed social state instead of adapter-local insight fields
- Maintained Discord on-message runtime and legacy response execution are now explicitly separated; the runtime path no longer mutates legacy persona state
- Maintained Discord message handling now resolves response decisions through one helper and isolates legacy fallback/persona switching behind explicit fallback helpers
- Legacy persona-switching and `BehaviorEngine` mutation for Discord fallback now live behind `ChatCog._handle_legacy_chat_response(...)` instead of inside `MessageHandler`
- Maintained Discord `MessageHandler` no longer carries pending legacy response-persona state; legacy persona lookup and persona-id logging now resolve through `ChatCog`
- Legacy fallback response-decision policy no longer lives in `MessageHandler`; the maintained handler now delegates fallback response decisions through `ChatCog`
- `ChatCog` now fronts an explicit `legacy_chat` delegate for transitional legacy service ownership instead of storing those legacy subsystems directly as peer ownership on the maintained chat path
- Maintained Discord `MessageHandler` now treats self/system/prefixed-command filtering and duplicate suppression as explicit adapter transport hygiene; the rest of the maintained path is fact extraction, decision delegation, batching, and rendering
- Maintained Discord message handling no longer depends on local `SessionManager` response-time tracking in the hot path
- Maintained Discord `ChatCog` no longer initializes local session-manager support by default on the maintained path
- Discord loaded legacy chat fallback is now explicitly opt-in behind `DISCORD_LEGACY_CHAT_FALLBACK_ENABLED`; `ChatCog` no longer initializes legacy chat support by default unless fallback or legacy ambient is enabled
- Discord maintained runtime chat survives optional legacy init failure
- Discord maintained runtime chat uses a dedicated adapter-side runtime response renderer
- Discord maintained on-message runtime decision failures no longer fall through to legacy chat behavior unless legacy fallback is explicitly available and allowed
- Launcher profile-based env loading for maintained startup paths
- Direct `gestalt` and `python -m adapters.cli` entrypoints now apply env profiles before config-bound CLI imports
- `gestalt runtime --stdio` and `gestalt runtime --web --port <port>` are now the maintained standalone runtime-host entrypoints for stdio and web serving
- runtime context caching now uses a stable-prefix model, so persona/mode/provider/tool prompt prefixes can be reused without invalidating on normal turn-by-turn memory growth
- runtime status/session/context surfaces now expose provider cached-input token telemetry when supported by the backing provider

## Cleanup Progress

Executed cleanup slices:

- Phase 1 repository hygiene is in progress:
  - tracked desktop build artifacts are being removed from source control
  - ignore rules are being tightened for desktop/Tauri and test/build output
  - stale runtime API test monkeypatching has been realigned to the maintained
    `adapters.web.adapter.create_runtime` seam
  - maintained runtime test files (`test_web_runtime_api.py`,
    `test_runtime_stdio.py`, `test_desktop_scaffold.py`,
    `test_cli_productization.py`) are now explicitly unignored so migration
    verification is not hidden behind `test_*.py` ignore patterns
  - legacy `test_discord_social_commands.py` has been quarantined as
    superseded runtime-first coverage so stale adapter-local social state tests
    no longer block unit collection
- Phase 2 web surface consolidation is complete:
  - the legacy simple `/ws` websocket path has been removed
  - `/api/runtime/ws` is now the only maintained runtime websocket surface
- Phase 2 Runtime API formalization has started:
  - `docs/RUNTIME_API.md` now defines the canonical surface-adapter contract
  - runtime session bootstrap/listing is now exposed through maintained web and stdio paths
  - runtime social-state bootstrap/mutation is now exposed through maintained web and stdio paths
  - runtime session listing is now adapter-scoped for maintained usage through platform, room, and optional `user_scope` filters
  - the browser client now consumes runtime session bootstrap/listing and social snapshots instead of relying only on local recent-session approximations
  - the browser client can now apply and reset runtime social-mode state through the same Runtime API
  - browser recent-session inventory is now scoped by a stable browser client `user_scope`
  - maintained web/browser requests now carry a stable `user_id` as well as `user_scope` for request attribution
- maintained launcher, CLI, TUI, web, stdio, and Discord runtime-chat entrypoints now share one canonical runtime assembly/helper module in `gestalt/runtime_bootstrap.py`
- launcher CLI/web startup now uses a maintained `RuntimeHost` seam instead of each surface inventing its own runtime bootstrap
- maintained launcher, CLI, TUI, and stdio now use the shared `RuntimeHost` lifecycle instead of each owning runtime bootstrap/close independently
- maintained standalone runtime hosting no longer requires `launcher.py` for the web serving path; `gestalt runtime --web` now hosts the canonical Runtime API directly
- maintained web/browser clients now propagate a stable client id through HTTP headers and websocket connect payloads
- maintained web/browser paths now derive a server-owned authenticated actor id when API-token auth is enabled instead of trusting caller-supplied `user_id`
- maintained web transport no longer emits local `datetime.utcnow()` fallback warnings in websocket timestamp paths
- Launcher cleanup is complete:
  - CLI and web launcher paths use runtime-first startup without forcing
    `ServiceFactory`
- launcher now has a maintained runtime-host startup path for Discord via
  `GestaltDiscordBot`
- `adapters/discord/discord_bot.py` now exists as the runtime-host-backed
  Discord startup module and now loads runtime-native chat/help/system/social/profile/search cogs
  - maintained Discord startup no longer imports the hybrid `adapters/discord/commands/chat/main.py` seam or legacy character-admin seams
  - `main.py` is deprecated with clear warnings pointing to `launcher.py`
- Discord migration truth is now mapped:
  - maintained Discord startup is now a real runtime-first surface under strict quarantine policy
  - Discord slash chat now uses a thin runtime-native chat path
  - maintained Discord startup now loads a dedicated `RuntimeChatCog` for slash chat and mention-gated on-message chat instead of relying on the hybrid legacy `ChatCog`
  - maintained Discord help and `botstatus` now resolve through runtime command/status outputs on the runtime-host startup path
  - maintained Discord `profile.status` and `search`/`ask` commands are now runtime-only and no longer call legacy Ollama/chat seams directly
  - Discord on-message response generation now uses the same runtime-native chat path
  - on-message response and persona selection now route through runtime after adapter fact extraction
  - remaining adapter-owned pre-runtime work in `MessageHandler` is now explicit transport hygiene instead of hidden response policy
  - maintained on-message trigger facts are now normalized into one adapter payload before runtime decision
  - runtime now owns recent-conversation and channel auto-reply gating instead of the Discord adapter
  - runtime now respects explicit adapter gating for Discord name-trigger decisions
  - runtime now owns muted-state, direct-unmute, and non-persona bot-author response policy for the maintained on-message path
  - `MessageHandler` no longer carries dead pending legacy persona state; `ChatCog` now owns the remaining legacy persona lookup and fallback decision policy through an explicit `legacy_chat` delegate
  - `ChatCog` now separates required maintained runtime-chat init from optional legacy init
  - optional legacy chat init failure no longer blocks maintained slash/on-message runtime chat startup
  - maintained `/list_characters` now reads persona inventory and active persona from runtime instead of legacy bot persona state
  - maintained `interact` persona lookup now reads from the runtime persona catalog instead of `persona_router`
  - Discord RL commands are now explicitly gated behind `RL_ENABLED` on the legacy startup path instead of loading unconditionally
  - Discord bot-conversation commands are now explicitly gated behind `BOT_CONVERSATION_ENABLED` on the legacy startup path instead of reading like a maintained default surface
  - Discord voice commands are now explicitly gated behind `DISCORD_VOICE_ENABLED` and TTS availability on the legacy startup path
  - loaded chat ambient controls are now explicitly gated behind `DISCORD_LEGACY_CHAT_AMBIENT_ENABLED` so they do not compete with runtime-backed social controls by default
  - loaded chat session controls are now explicitly gated behind `DISCORD_LEGACY_CHAT_SESSION_ENABLED` so they do not masquerade as maintained runtime session control
  - local Discord social mode footers are now explicitly gated behind `DISCORD_LEGACY_SOCIAL_MODE_FOOTER_ENABLED` so Discord-local footer UI state does not read like part of the maintained runtime social model
  - local Discord facilitator and bandit status insights are now explicitly gated behind `DISCORD_LEGACY_SOCIAL_INSIGHTS_ENABLED` so `/social status` defaults to runtime-backed state instead of adapter-local analytics
  - launcher Discord startup now has a runtime-first smoke test asserting
    `GestaltDiscordBot` is the active path and `ServiceFactory` is not required
  - `main.py` now has an explicit deprecation/ownership guard test to prevent it
    from silently regaining canonical startup authority
  - `ChatCog` startup now initializes runtime-chat helpers before system-prompt
    loading, eliminating the runtime-first startup crash where `helpers` was
    accessed before initialization
  - runtime lifecycle now includes `GestaltRuntime.close()`, so
    `RuntimeHost.close()` no longer fails on maintained Discord shutdown
  - hard run-gate verification (`launcher.py --discord --no-cli --no-web`)
    now shows clean startup, command sync, ready state, and clean shutdown
  - maintained Discord on-message fact extraction now uses
    `core.interfaces.PlatformFacts` as the normalized adapter fact carrier
    before runtime decision flags are emitted
  - maintained web runtime-event ingress (HTTP + websocket) now uses
    `core.interfaces.PlatformFacts` as the normalized adapter fact carrier
    before runtime decision flags are emitted
  - maintained Discord/Web fact-to-flag conversion now uses shared helper
    `core.interfaces.runtime_flags_from_platform_facts(...)` to reduce
    adapter-layer duplication without changing runtime policy ownership
  - maintained web ingress now uses shared event builder
    `core.interfaces.build_runtime_event_from_facts(...)` for HTTP
    `/api/runtime/event` and websocket `send_event` paths
  - maintained Discord chat runtime handlers now use shared event builder
    `core.interfaces.build_runtime_event_from_facts(...)` for both
    slash/on-message runtime response flows
- maintained CLI runtime event ingress now uses shared event builder
    `core.interfaces.build_runtime_event_from_facts(...)` for both
    interactive CLI message/command routing and CLI play-mode planner prompts
  - runtime now owns a session-scoped stable-prefix context cache with
    TTL/max-entry controls and cache trace metadata
    (`context_cache` traces include hit/miss reason, stable-prefix scope,
    and token-saved estimates)
  - runtime now separates cached stable prompt prefixes from dynamic memory
    context so normal summary/fact/retrieval changes do not invalidate the
    reusable prefix
  - provider usage telemetry now records cached input tokens where supported
    and surfaces that data through runtime status, session, and context views
  - maintained Runtime API now exposes context-cache snapshot/reset on web and
    stdio transports (`/api/runtime/context`, `/api/runtime/context/reset`,
    `get_context`, `reset_context`)
  - runtime command surface now includes `/context` and `/context reset` for
    operator-side cache introspection and reset
  - runtime-backed Discord help, status, profile, and search command modules are now on the maintained startup path
  - legacy trigger parsing, voice, and conversation paths remain quarantined outside maintained startup
  - Discord social mode/status now use runtime-owned session state instead of local adapter state
- Configuration hardening has started:
  - launcher now supports `--env-profile`
  - `config.py` now loads `.env` plus optional `.env.<profile>` through `gestalt/env.py`
- Documentation pruning is complete:
  - legacy feature packs, setup guides, workflow catalogs, and old production-readiness docs were removed
  - `docs/` now focuses on canonical vision, audit maps, and current runtime/operator references
- Development governance is stricter now:
  - `docs/ENGINEERING_OPERATING_MODEL.md` defines the required product-vs-research cycle
  - `docs/adr/` now exists for architecture decisions that change ownership or contracts
- Canonical architecture is now explicit:
  - `docs/ARCHITECTURE.md` defines the current layered architecture, ownership model, and realistic phase plan
  - `docs/adr/0001-canonical-architecture-layering.md` records the layer and ownership decision
  - `docs/adr/0002-runtime-api-for-surface-adapters.md` records the surface-adapter contract decision
- Maintained persona-default drift was reduced:
  - CLI and web runtime paths now resolve default personas from the loaded catalog/runtime router
  - maintained web API schemas no longer hardcode starter persona ids
  - the maintained browser client no longer hardcodes `tai` as its startup persona and now defers initial persona resolution to runtime bootstrap
- Phase 2 social-state migration has started:
  - `GestaltRuntime` now owns social session state snapshots, overrides, and facilitator decisions
  - `adapters/discord/commands/social.py` now acts as a thin runtime client for mode/status flows
- Phase 2 Discord chat migration is materially advanced:
  - `adapters/discord/commands/chat/commands.py` routes slash chat through a thin runtime-native chat handler
  - maintained on-message chat now routes response decision and response generation through runtime
  - `MessageHandler` is now mostly explicit transport hygiene plus platform fact extraction
  - transitional legacy chat ownership is isolated behind `ChatCog.legacy_chat`
  - maintained Discord chat can now attach to an injected runtime or `RuntimeHost` instead of always creating its own runtime

This is the first executed pruning step from the audit plan.

## What Is Not Yet Stable

- Browser/Tauri productization
- Experimental embodiment code outside the canonical browser client
- Legacy service and cog feature ownership

## Discord Migration Closeout Gate

**Status**: CLOSED under strict quarantine policy (2026-03-19)

Closeout policy: strict quarantine. Legacy Discord surfaces can remain opt-in,
but they are excluded from maintained-path completion criteria.

- [x] Maintained Discord startup path now has a runtime-host-backed entry module
  at `adapters/discord/discord_bot.py` and launcher runtime-host wiring
- [x] Maintained Discord startup no longer imports hybrid chat/service seams
  and instead uses `RuntimeChatCog` plus runtime-native help/system/social/profile/search cogs
- [x] Legacy Discord toggles remain explicit opt-in and default-off
  (`DISCORD_LEGACY_*`)
- [x] Runtime lifecycle close path supports maintained Discord shutdown
  (`RuntimeHost.close()` -> `GestaltRuntime.close()` -> provider cleanup)
- [x] Hard gate verification for runtime-host Discord startup has been re-established
  through startup/runtime boundary tests
- [x] Legacy operator/voice/conversation surfaces are explicitly quarantined and no longer part of maintained startup criteria

### Evidence Block

```bash
# Startup truth tests
$ uv run pytest tests/unit/test_launcher_runtime_split.py -q --tb=no
$ uv run pytest tests/unit/test_cli_runtime_routing.py -q --tb=no

# Results summary
# launcher + CLI runtime routing now pass on the maintained startup slice

# Test files covered:
# - test_discord_chat_runtime_path.py (runtime-first chat path)
# - test_discord_chat_fallback_seam.py (legacy fallback isolation)
# - test_discord_social_runtime.py (runtime-owned social state)
# - test_discord_startup_boundaries.py (legacy opt-in enforcement)
# - test_discord_character_runtime.py (runtime persona catalog)
# - test_discord_help_runtime.py (runtime-backed help)
# - test_discord_system_runtime.py (runtime-backed status)
# - test_discord_operator_boundaries.py (legacy operator quarantine)
# - test_discord_voice_runtime.py (voice surface boundaries)
# - test_discord_profile_runtime.py (profile runtime path)
# - test_discord_search_runtime.py (search runtime path)

# Live smoke verification
$ uv run python launcher.py --discord --no-cli --no-web
# Startup: GestaltDiscordBot initialized with RuntimeHost
# Ready: Command sync complete, bot ready
# Shutdown: Clean RuntimeHost.close() -> GestaltRuntime.close()
```

## Phase 2 Next Tasks

- `P6: Startup Consolidation for Discord migration` is now **completed under strict quarantine policy**:
  runtime-host launcher wiring is canonical, and maintained Discord startup now uses runtime-native chat/help/system/social/profile/search cogs.
- ~~Move persona name extraction from Discord adapter into runtime-owned decision~~ **Completed**: runtime now owns `_extract_mentioned_persona_ids_from_text()` and the maintained Discord adapter no longer sends persona-name trigger semantics in its fact payload.
- ~~Move facilitator logic from Discord adapter into runtime~~ **Completed**: `ModeFacilitator` removed from `SocialCommandsCog`; runtime now owns social state via `get_social_state_snapshot()`, `set_social_mode()`, `reset_social_state()`, and `record_social_routing_decision()`; Discord adapter calls runtime for mode selection.
- ~~Remove maintained Discord chat dependence on legacy `BehaviorEngine`, `ContextManager`, and persona-router ownership from the remaining trigger and orchestration path~~ **Completed**: `_LegacyChatSupport` class moved to `adapters/discord/commands/chat/legacy_support.py`; `main.py` no longer imports legacy services at module level; runtime-only path has zero service dependencies.
- ~~Move remaining Discord persona-management commands onto runtime-owned persona/catalog state~~ **Completed for maintained startup**: runtime-native help/system/profile/search surfaces are on startup; legacy character import/reload remains quarantined outside maintained startup.
- ~~Live-run hardening fixes~~ **Completed**: 
  - Added `_is_visual_question()` method to `GestaltRuntime` (fixes AttributeError in decision path)
  - Added idempotency guard in `MessageHandler._respond_via_runtime()` with `_responding_messages` set to prevent duplicate/parallel responses for same Discord message ID
  - Added shutdown safety checks in `_handle_runtime_chat_response()` to gracefully skip sends when bot is closed (prevents "Session is closed" exceptions)
- Quarantine Discord legacy/research-only surfaces on startup. Partial: RL, bot-conversation, and voice are now explicit opt-in on the transitional `main.py` path, but the underlying surfaces are still legacy/transitional when enabled.
- Apply the Discord salvage matrix in code. Completed for maintained startup: runtime-backed Discord command modules are now the only maintained startup surface; remaining voice/conversation/operator/persona-admin modules are explicitly quarantined.
- Replace Discord-local operator surfaces with runtime-first equivalents. Partial: Discord help and `botstatus` now use runtime command/status truth, and legacy Discord operator tooling is now disabled by default behind `DISCORD_LEGACY_OPERATOR_ENABLED`, but runtime-native memory/admin replacements do not exist yet.
- Tighten Runtime API identity from stable adapter-generated `user_id` toward authenticated actor identity when auth is enabled. Completed for maintained web/browser HTTP and websocket paths.
- Keep web/browser as the reference Runtime API client while Discord continues migrating toward the same contract.

## Multi-Agent Note

- `/swarm --phase phase2` is now useful for bounded runtime-native delegation.
- Swarm output is not ground truth by itself; code, tests, and canonical docs
  still decide product truth.

## Current Rule

When there is a conflict between historical reports and code/tests, trust code and tests.
Canonical audit checkpoint: `.sisyphus/VISION_REALIGNMENT_AUDIT.md`.

Use [FEATURES.md](/root/acore_bot/docs/FEATURES.md) as the current platform maturity source of truth.
