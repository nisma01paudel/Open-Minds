"""The Python mesh and the JavaScript mesh must not drift apart.

The field client carries its own implementation of the protocol because a phone with no
API still has to compose, relay and dedupe. One protocol in two languages will diverge, and
each side will pass its own tests while they disagree - at which point a JavaScript gateway
phone and a Python district server silently lose messages between them.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_python_and_javascript_meshes_agree():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_mesh_parity.py")],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: the Python and JavaScript meshes agree exactly" in proc.stdout
    assert "MISMATCH" not in proc.stdout


def test_the_client_mesh_is_reached_by_the_page():
    """A mesh module the page never loads is dead code."""
    html = (ROOT / "web" / "public" / "field" / "index.html").read_text(encoding="utf-8")
    assert 'src="/field/mesh.js"' in html, "the field page must load the mesh module"
    assert "PahiroMesh" in html, "the page must actually use it"


def test_both_implementations_keep_the_same_limits():
    """Two constants that must not drift silently."""
    from pahiro.mesh.protocol import DEFAULT_TTL, MAX_BODY

    js = (ROOT / "web" / "public" / "field" / "mesh.js").read_text(encoding="utf-8")
    assert f"DEFAULT_TTL = {DEFAULT_TTL}" in js
    assert f"MAX_BODY = {MAX_BODY}" in js


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_cross_tab_transport_carries_a_message_and_hands_it_on():
    """The demo claim is that two browser tabs behave like two phones in range. That is the
    transport the field client actually runs on, so it is tested rather than asserted."""
    proc = subprocess.run(
        ["node", str(ROOT / "tests" / "bc_transport_probe.js"), str(ROOT / "web" / "public" / "field" / "mesh.js")],
        capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["ok"] is True
    assert out["origin"] == "phone-a"      # the sender never changes as it is carried
    assert out["handed"] == 1              # and the carrier passes it on
