"""The phone's maths must match the server's.

Two implementations of the same trilateration in two languages will drift, and each will
pass its own tests while they disagree. A rescuer holding a phone with no API would then be
given a different place to dig than the board would give them.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_field_client_and_server_agree_on_the_same_readings():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_client_server_math.py")],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: client and server agree" in proc.stdout
    # the check must have actually compared something
    assert "positions differ by" in proc.stdout
