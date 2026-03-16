from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence

from dotenv import load_dotenv


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_environment_profile(profile: str = "") -> list[Path]:
    """Load `.env` plus an optional `.env.<profile>` file."""
    root = _repo_root()
    loaded: list[Path] = []

    base_file = root / ".env"
    if base_file.exists():
        load_dotenv(base_file, override=False)
        loaded.append(base_file)

    normalized = str(profile or os.getenv("GESTALT_ENV_PROFILE") or "").strip().lower()
    if not normalized:
        return loaded

    os.environ["GESTALT_ENV_PROFILE"] = normalized
    profile_file = root / f".env.{normalized}"
    if profile_file.exists():
        load_dotenv(profile_file, override=True)
        loaded.append(profile_file)

    return loaded


def detect_environment_profile(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Extract an env profile from argv or environment."""
    args = list(argv or [])
    for index, value in enumerate(args):
        current = str(value or "").strip()
        if current == "--env-profile" and index + 1 < len(args):
            return str(args[index + 1] or "").strip().lower()
        if current.startswith("--env-profile="):
            return current.split("=", 1)[1].strip().lower()
    source = environ if environ is not None else os.environ
    return str(source.get("GESTALT_ENV_PROFILE") or "").strip().lower()


def preload_environment_profile(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    """Load env files before config-bound imports based on argv or env."""
    return load_environment_profile(detect_environment_profile(argv, environ))
