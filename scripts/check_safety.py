#!/usr/bin/env python3
"""Fail if repository uses subprocess or shell=True."""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
THIS = pathlib.Path(__file__).resolve()

patterns = ["subprocess", "shell=True"]
found_any = False
for pat in patterns:
    cmd = [
        "grep",
        "-R",
        "-n",
        "--include=*.py",
        "--include=*.sh",
        f"--exclude={THIS.name}",
        "--exclude-dir=.git",
        "--exclude-dir=.venv",
        pat,
        str(ROOT),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        print(f"Unsafe usage of '{pat}':")
        print(res.stdout)
        found_any = True

if found_any:
    sys.exit(1)
