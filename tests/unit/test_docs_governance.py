from __future__ import annotations

import subprocess

import pytest


pytestmark = pytest.mark.unit


def test_docs_governance_validation() -> None:
    result = subprocess.run(
        ["uv", "run", "python", "scripts/check_docs_governance.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED" in result.stdout
