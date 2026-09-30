#!/usr/bin/env python3
"""The phone's fallback computation must agree with the server's.

The field client carries its own copy of the trilateration so it can still answer with no
API. Two implementations of the same maths in two languages WILL drift - one gets a weight
changed, or a clamp, and nobody notices because each is tested alone.

This runs both on identical synthetic readings and compares the answer. It is the only test
here that can catch a divergence between what the board says and what the phone says.

    python scripts/check_client_server_math.py
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pahiro.locate import DEFAULT_TX_POWER, Reading, estimate_position

HTML = ROOT / "web" / "public" / "field" / "index.html"


def extract_js() -> str:
    """Pull the two maths functions out of the page.

    Sliced by their own boundaries rather than evaluating the whole script, which touches
    the DOM at load and has no business running under node.
    """
    src = HTML.read_text(encoding="utf-8")
    m = re.search(r"function rssiToDistance\(.*?\n", src)
    if not m:
        raise SystemExit("rssiToDistance not found in the field client")
    one_liner = m.group(0).strip()

    start = src.index("function localEstimate(rows) {")
    end = src.index("\n}\n", start) + 2
    return one_liner + "\n" + src[start:end]


HARNESS = """
%s
// under `node -e` there is no script path in argv, so take the last argument
var rows = JSON.parse(process.argv[process.argv.length - 1]);
var out = localEstimate(rows);
console.log(JSON.stringify(out));
"""


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("node not installed; skipping the client/server cross-check")
        return 0

    # The same three readings the Python suite uses.
    readings = [(27.76227, 85.05350, -86.5), (27.76160, 85.05350, -95.0),
                (27.76200, 85.05406, -92.3)]

    js_rows = [{"lat": a, "lon": b, "rssi_dbm": c} for a, b, c in readings]
    script = HARNESS % extract_js()
    proc = subprocess.run([node, "-e", script, json.dumps(js_rows)],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        print("node failed:\n" + proc.stderr[-2000:], file=sys.stderr)
        return 2
    js = json.loads(proc.stdout.strip().splitlines()[-1])

    py = estimate_position([Reading(lat=a, lon=b, rssi_dbm=c) for a, b, c in readings])

    print(f"{'':<14}{'client (JS)':>16}{'server (Python)':>18}")
    print(f"{'lat':<14}{js['lat']:>16.5f}{py.lat:>18.5f}")
    print(f"{'lon':<14}{js['lon']:>16.5f}{py.lon:>18.5f}")
    print(f"{'radius_m':<14}{js['radius_m']:>16.1f}{py.radius_m:>18.1f}")
    print(f"{'receivers':<14}{js['receivers']:>16}{py.receivers:>18}")

    # Equirectangular metres, the same conversion both use.
    lat0 = sum(a for a, _b, _c in readings) / 3
    def metres(lat, lon):
        return ((lon - 85.05350) * 111320 * math.cos(math.radians(lat0)),
                (lat - 27.76200) * 111320)
    gap = math.dist(metres(js["lat"], js["lon"]), metres(py.lat, py.lon))
    print(f"\npositions differ by {gap:.1f} m")

    ok = True
    if gap > 5.0:
        print(f"FAIL: the phone and the server disagree by {gap:.1f} m on identical input")
        ok = False
    if abs(js["radius_m"] - py.radius_m) > max(5.0, 0.15 * py.radius_m):
        print(f"FAIL: search radius differs: {js['radius_m']:.1f} vs {py.radius_m:.1f} m")
        ok = False
    if js["method"] != py.method:
        print(f"FAIL: different method: {js['method']} vs {py.method}")
        ok = False

    # Both must refuse in the same situations, or a phone will confidently answer where
    # the board abstains.
    print("\nrefusals:")
    for name, rows in [("two readings", js_rows[:2]),
                       ("collinear", [{"lat": 27.7600, "lon": 85.0500, "rssi_dbm": -70},
                                      {"lat": 27.7620, "lon": 85.0500, "rssi_dbm": -75},
                                      {"lat": 27.7640, "lon": 85.0500, "rssi_dbm": -80}])]:
        p2 = subprocess.run([node, "-e", script, json.dumps(rows)],
                            capture_output=True, text=True, timeout=60)
        j = json.loads(p2.stdout.strip().splitlines()[-1])
        pyr = estimate_position([Reading(lat=r["lat"], lon=r["lon"], rssi_dbm=r["rssi_dbm"])
                                 for r in rows])
        same = (j["method"] != "weighted-least-squares") == \
               (pyr.method != "weighted-least-squares")
        print(f"  {name:<16} client {j['method']:<26} server {pyr.method:<26} "
              f"{'agree' if same else 'DISAGREE'}")
        ok = ok and same

    print("\nOK: client and server agree" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
