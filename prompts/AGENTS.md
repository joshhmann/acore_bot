# PROMPTS KNOWLEDGE BASE

**Generated:** 2026-02-28 06:31:42 PM PST
**Parent:** `./AGENTS.md`

## OVERVIEW

Persona content source of truth: character cards, framework presets, and schema documentation used by runtime persona loading.

## STRUCTURE

```
prompts/
├── characters/             # Persona JSON definitions loaded by personas/loader.py
├── frameworks/             # Behavior/framework templates (assistant, caring, chaotic, neuro)
├── compiled/               # Generated/compiled prompt artifacts
└── PERSONA_SCHEMA.md       # Persona schema and extension reference
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add or edit a character | `prompts/characters/*.json` | Runtime persona catalog source |
| Validate schema fields | `prompts/PERSONA_SCHEMA.md` | Canonical field semantics and examples |
| Tune framework defaults | `prompts/frameworks/*.json` | Reusable behavioral templates |
| Inspect compiled artifacts | `prompts/compiled/` | Generated outputs; do not hand-edit |

## CONVENTIONS

Keep persona IDs stable and normalized (loader lowercases and underscores ids/names).
Prefer JSON character cards in `prompts/characters/` for runtime behavior, not `.promptx/personas/`.
Document new extension fields in `PERSONA_SCHEMA.md` when adding behavior knobs.
Treat `compiled/` as derived output; regenerate instead of manual edits.

## ANTI-PATTERNS

Do not place runtime persona cards in `.promptx/personas/` (that directory is for agent personas).
Do not introduce schema fields without loader/runtime handling.
Do not edit compiled artifacts as primary source.
Do not couple character data to platform-specific behavior.

## NOTES

`personas/loader.py` is the runtime loader boundary; ensure prompt changes remain compatible with its normalization and fallback behavior.
