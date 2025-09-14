Agent Guide for acore-bot

Scope

- This file applies to the entire repository.

Overview

- Python 3.10 Discord bot for AzerothCore using SOAP, optional DB metrics, and local LLMs (Ollama/Arliai) with RAG.
- Slash commands live in `commands/`; utilities in `utils/`; SOAP/DB/LLM helpers at repo root.
- Keep changes minimal, focused, and consistent with current patterns.

Workspace Rules

- Do not commit secrets. `.env` holds runtime configuration (Discord token, SOAP/DB creds, provider settings).
- Stay within the workspace; avoid network installs unless requested. Prefer offline, surgical edits.
- Preserve public APIs used by commands/tests; avoid wide refactors unless explicitly asked.

Project Layout

- `bot.py`: Main Discord bot, env config, SOAP + LLM orchestration, auto‑reply logic.
- `commands/`: Slash commands (e.g., `health.py`, `kpi.py`). Add new commands here and expose a `setup_*` function.
- `utils/`: Helpers for formatting, caching, intents, and tool logging.
- `bot/tools/`: Lightweight tools exposed to LLMs (e.g., time, named queries registry).
- `ac_db.py`, `ac_metrics.py`: DB config and realm metrics snapshot functions.
- `soap.py`: SOAP client wrapper. `ollama.py`: LLM client. `rag_store.py`: local KB/docs + retrieval.
- `kb.json`, `server_info.json`: Optional local data used for FAQs/RAG.
- `docs/`: Curated `.md`/`.txt` (and optional `.yaml`) docs for search/RAG.
- `tests/`: Pytest suite for formatters, metrics, and slum queries.
- Note: There are two `slum_queries.py` variants: one at repo root (imported by tests) and one under `bot/tools/`. When editing queries for tests, modify the root `slum_queries.py`.

Coding Conventions

- Follow PEP 8 style and keep functions small and predictable.
- Prefer clear names over brevity; avoid one‑letter variables.
- Type hints where practical; do not introduce new dependencies for typing.
- Input validation and helpful error messages over silent failures.
- Keep changes limited to the task; do not rename/move modules unless requested.

Common Tasks

- Add a slash command:
  - Create `commands/<name>.py` with a `setup_<name>(tree: app_commands.CommandTree)` function.
  - Register the command(s) inside that function; follow patterns in `commands/health.py` and `commands/kpi.py`.
  - Import and call the setup from `bot.py` alongside other `setup_*` calls.

- Add an LLM‑exposed tool:
  - Implement under `bot/tools/` and register it in `bot.py` (`OLLAMA_TOOLS` or `LLM_TOOLS`).
  - Keep tool I/O JSON‑serializable; handle timeouts and errors gracefully.

Tests & Validation

- Run tests: `pytest -q` (configured via `pyproject.toml`).
- Focus tests around changed modules first; do not rewrite unrelated tests.
- `tests/test_slum_queries.py` imports the root `slum_queries.py`.
- `tests/test_metrics.py` targets `utils/formatters.py` (copper → g/s/c formatting).

DB & Metrics

- Use read‑only DB access for metrics (see `sql/create_readonly_grants.sql`).
- Queries and timeouts live in `slum_queries.py` (root) and `bot/tools/slum_queries.py` (tools). Keep circuit‑breaker behavior intact.

RAG & Documents

- `rag_store.py` indexes `docs/` and optional KB files (`kb.json` or YAML). Keep chunk sizes and scoring thresholds configurable via env.
- When adding new doc types, prefer pure‑Python parsers already listed in `pyproject.toml` (no network installs by default).

Local Run (summary)

- Create `.env` (see `README.md` for all variables) and run:
  - Linux/macOS: `.venv/bin/python bot.py`
  - Windows (PowerShell): `.venv\Scripts\python.exe bot.py`
- LLMs:
  - Ollama: run `ollama serve` and pull a model (e.g., `llama3`), then set `OLLAMA_ENABLED=true`.
  - Arliai: set `ARLIAI_*` env vars and `ARLIAI_ENABLED=true`.

Gotchas

- Don’t leak secrets in logs or commits; `.env` is git‑ignored.
- Guild/channel command restrictions are enforced; many commands are ephemeral by design.
- Tests assume local imports; if moving files, update import paths and tests accordingly (only when explicitly requested).
