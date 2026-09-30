#!/usr/bin/env python3
"""The Python mesh and the JavaScript mesh must behave identically.

The field client carries its own implementation of the protocol, because a phone with no
API still has to compose, relay and dedupe messages. That means one protocol in two
languages, which WILL drift - and each side will pass its own tests while the two disagree.

A gateway phone running JavaScript and a district server running Python must agree about
hop counts, TTL, dedupe and eviction, or messages quietly vanish between them.

This runs one deterministic scenario through both and compares the resulting state exactly.

    python scripts/check_mesh_parity.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pahiro.mesh.node import MeshNode
from pahiro.mesh.protocol import MeshMessage

MESH_JS = ROOT / "web" / "public" / "field" / "mesh.js"

# Fixed ids and timestamps so both sides produce comparable output; the scenario is data,
# not code, so it cannot drift between the two harnesses.
SCENARIO = [
    {"id": "s1", "k": "sos", "b": "buried, two of us", "o": "a", "t": "2026-01-01T00:00:00Z",
     "ttl": 7, "y": 27.762, "x": 85.0535},
    {"id": "c1", "k": "chat", "b": "on my way", "o": "b", "t": "2026-01-01T00:01:00Z", "ttl": 7},
    {"id": "c2", "k": "chat", "b": "road is blocked", "o": "c", "t": "2026-01-01T00:02:00Z",
     "ttl": 2},
    {"id": "s2", "k": "sos", "b": "third house", "o": "d", "t": "2026-01-01T00:03:00Z", "ttl": 1},
    {"id": "c3", "k": "chat", "b": "second one", "o": "b", "t": "2026-01-01T00:04:00Z", "ttl": 7},
]

# (operation, args) - executed in order by both harnesses
STEPS = [
    ["receive", "a", "s1"], ["receive", "b", "c1"], ["receive", "c", "c2"],
    ["receive", "d", "s2"], ["receive", "b", "c3"],
    ["sync", "a", "b"], ["sync", "b", "c"], ["sync", "c", "d"], ["sync", "d", "a"],
    ["sync", "a", "c"], ["sync", "b", "d"], ["sync", "a", "d"],
]

JS_HARNESS = """
var M = require(process.argv[process.argv.length - 2]);
var scenario = JSON.parse(process.argv[process.argv.length - 1]);
var nodes = {};
["a","b","c","d"].forEach(function (n) { nodes[n] = new M.MeshNode(n, { capacity: 200 }); });
var byId = {};
scenario.frames.forEach(function (f) { byId[f.id] = M.MeshMessage.fromDict(f); });
scenario.steps.forEach(function (s) {
  if (s[0] === "receive") { nodes[s[1]].receive(byId[s[2]]); }
  else { nodes[s[1]].syncWith(nodes[s[2]]); }
});
var out = {};
Object.keys(nodes).sort().forEach(function (n) {
  var node = nodes[n];
  out[n] = {
    store: Object.keys(node.store).sort().map(function (k) {
      var m = node.store[k];
      return [m.id, m.hops, m.ttl, m.path.join(">"), m.kind];
    }),
    stats: node.stats,
    distress: node.distress().map(function (m) { return m.id; }),
    inbox: node.transcript().map(function (m) { return m.id; })
  };
});
console.log(JSON.stringify(out));
"""


def run_python() -> dict:
    nodes = {n: MeshNode(n, capacity=200) for n in "abcd"}
    by_id = {f["id"]: MeshMessage.from_dict(f) for f in SCENARIO}
    for step in STEPS:
        if step[0] == "receive":
            nodes[step[1]].receive(by_id[step[2]])
        else:
            nodes[step[1]].sync_with(nodes[step[2]])
    out = {}
    for n in sorted(nodes):
        node = nodes[n]
        out[n] = {
            "store": sorted([[m.id, m.hops, m.ttl, ">".join(m.path), m.kind]
                             for m in node.store.values()]),
            "stats": node.stats.as_dict(),
            "distress": [m.id for m in node.distress()],
            "inbox": [m.id for m in node.transcript()],
        }
    return out


def run_javascript() -> dict:
    node = shutil.which("node")
    if not node:
        raise SystemExit("node not installed")
    payload = json.dumps({"frames": SCENARIO, "steps": STEPS})
    proc = subprocess.run([node, "-e", JS_HARNESS, str(MESH_JS), payload],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise SystemExit("node failed:\n" + proc.stderr[-3000:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    py, js = run_python(), run_javascript()

    print(f"{'node':<6}{'store':>22}{'distress':>10}")
    for n in sorted(py):
        print(f"{n:<6}{len(py[n]['store']):>22}{len(py[n]['distress']):>10}")

    ok = True
    for n in sorted(py):
        for field in ("store", "stats", "distress", "inbox"):
            if py[n][field] != js[n][field]:
                ok = False
                print(f"\nMISMATCH  node {n}, field {field}")
                print(f"  python: {json.dumps(py[n][field])[:400]}")
                print(f"  js    : {json.dumps(js[n][field])[:400]}")

    # And the properties the protocol actually promises, asserted on the JS side too.
    print("\nproperties, checked on the JS mesh:")
    checks = [
        ("the SOS reached every node",
         all(any(row[0] == "s1" for row in js[n]["store"]) for n in "abcd")),
        ("the TTL-1 message did not propagate",
         sum(1 for n in "abcd" for row in js[n]["store"] if row[0] == "s2") <= 2),
        ("hop counts rose as it was carried",
         max([row[1] for n in "abcd" for row in js[n]["store"] if row[0] == "s1"] or [0]) >= 1),
        ("one distress row per origin device",
         len(js["a"]["distress"]) == len(set(js["a"]["distress"]))),
    ]
    for label, good in checks:
        print(f"  [{'ok' if good else 'FAIL'}] {label}")
        ok = ok and good

    print("\nOK: the Python and JavaScript meshes agree exactly" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
