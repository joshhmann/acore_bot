#!/usr/bin/env python3
"""Verify that create_readonly_grants.sql only grants SELECT permissions."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "sql" / "create_readonly_grants.sql"

bad: list[tuple[int, str]] = []
with SQL_PATH.open("r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        stripped = line.strip().upper()
        if stripped.startswith("GRANT"):
            if "SELECT" not in stripped or re.search(r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b", stripped):
                bad.append((idx, line.rstrip()))

if bad:
    print("Non-read-only grants detected:")
    for ln, content in bad:
        print(f"{SQL_PATH}:{ln}: {content}")
    sys.exit(1)

print("Read-only grants verified for", SQL_PATH)
