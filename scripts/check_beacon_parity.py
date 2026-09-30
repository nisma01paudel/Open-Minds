#!/usr/bin/env python3
"""Prove the Python and JavaScript beacon codecs produce identical bytes.

Same discipline as scripts/check_mesh_parity.py: two implementations of one wire format in two
languages will drift, and each will pass its own tests while they disagree. For a *radio*
format the failure is worse than for JSON, because a disagreement is not a parse error - it is
a frame the other side decodes into a different position, or fails to recognise as a duplicate
and reports twice, or rejects outright as corrupt.

So this drives one fixed set of cases through both and compares the hex.

    python scripts/check_beacon_parity.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pahiro.mesh import beacon as B  # noqa: E402

WHEN = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)

# The cases that must agree. Chosen to cover every branch in the encoder: both kinds of
# position, the optional position, the flags, the extremes of the bit fields, and a UTF-8
# identifier (the JavaScript side hand-rolls its UTF-8 because TextEncoder is not guaranteed).
CASES = [
    ("typical sos", "handset-7f3a", "msg-abc123",
     dict(kind="sos", lat=27.71542, lon=85.31234, people=3, severity="critical",
          low_battery=True)),
    ("no position", "d1", "m1", dict(lat=None, lon=None)),
    ("minimal", "x", "y", dict(ttl=0, hops=0, severity="info", people=0)),
    ("maxed bits", "x", "y", dict(ttl=7, hops=7, severity="critical", people=15)),
    ("negative longitude", "gps-1", "m-2",
     dict(lat=26.12345, lon=-80.54321, severity="concern")),
    ("southern hemisphere", "gps-2", "m-3",
     dict(lat=-33.98765, lon=151.01234, people=1)),
    ("status kind", "relay-9", "m-9", dict(kind="status", lat=27.7, lon=85.3)),
    ("utf8 id", "हाते-फोन", "सन्देश-१", dict(lat=28.2096, lon=83.9856, people=2)),
]


def js_results() -> dict:
    """Run the same cases through node and return its answers as JSON."""
    script = ROOT / "web" / "public" / "field" / "beacon.js"
    case_defs = [
        {"name": n, "dev": d, "msg": m, "opts": o} for n, d, m, o in CASES
    ]
    driver = f"""
const B = require({json.dumps(str(script))});
const cases = {json.dumps(case_defs)};
const WHEN = new Date({int(WHEN.timestamp())} * 1000);
const out = {{}};
out.truncate = {{}};
for (const a of ["handset-7f3a", "d1", "x", "gps-1", "\\u0939\\u093e\\u0924\\u0947-\\u092b\\u094b\\u0928", "shesh-9f2c"]) {{
  out.truncate[a] = B.truncate16(a);
}}
out.encoded = cases.map(c => {{
  const o = Object.assign({{when: WHEN}}, c.opts);
  if (o.low_battery !== undefined) {{ o.lowBattery = o.low_battery; delete o.low_battery; }}
  return {{name: c.name, hex: Array.from(B.encode(c.dev, c.msg, o)).map(x => x.toString(16).padStart(2,"0")).join("")}};
}});
out.decoded = out.encoded.map(e => {{
  const raw = e.hex.match(/../g).map(h => parseInt(h,16));
  const b = B.decode(raw);
  if (!b) return {{name: e.name, null: true}};
  return {{name: e.name, dev16: b.dev16, msg_id16: b.msg_id16, kind: b.kind, ttl: b.ttl,
          hops: b.hops, severity: b.severity, people: b.people, lat: b.lat, lon: b.lon,
          created: Math.floor(b.created.getTime()/1000), lowBattery: b.lowBattery,
          origin: b.origin(), messageId: b.messageId()}};
}});
out.relayed = out.encoded.map(e => {{
  const raw = e.hex.match(/../g).map(h => parseInt(h,16));
  const r = B.relay(raw);
  return {{name: e.name, hex: r ? Array.from(r).map(x => x.toString(16).padStart(2,"0")).join("") : null}};
}});
out.rejected = [
  {{name: "bad crc", null: B.decode(new Uint8Array(B.encode("a","b",{{when:WHEN}}).map((v,i,arr) => i === arr.length-1 ? v ^ 0xFF : v))) === null}},
  {{name: "short", null: B.decode(new Uint8Array([1,2,3])) === null}},
  {{name: "garbage", null: B.decode(new Uint8Array(20)) === null}},
];
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(["node", "-e", driver], capture_output=True, text=True,
                          timeout=120, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit("node failed:\n" + proc.stdout + proc.stderr)
    return json.loads(proc.stdout)


def main() -> int:
    js = js_results()
    failures: list[str] = []

    def check(label, py, jsv):
        if py != jsv:
            failures.append(f"MISMATCH {label}\n    python: {py}\n    node:   {jsv}")

    for name, dev, msg, opts in CASES:
        py_bytes = B.encode(dev, msg, when=WHEN, **opts)
        py_hex = py_bytes.hex()
        # the JS driver passes low_battery -> lowBattery, so mirror that mapping for comparison
        js_hex = next(e["hex"] for e in js["encoded"] if e["name"] == name)
        check(f"encode[{name}]", py_hex, js_hex)

        py_b = B.decode(py_bytes)
        js_b = next(d for d in js["decoded"] if d["name"] == name)
        check(f"decode[{name}].dev16", py_b.dev16, js_b["dev16"])
        check(f"decode[{name}].msg_id16", py_b.msg_id16, js_b["msg_id16"])
        check(f"decode[{name}].kind", py_b.kind, js_b["kind"])
        check(f"decode[{name}].severity", py_b.severity, js_b["severity"])
        check(f"decode[{name}].people", py_b.people, js_b["people"])
        check(f"decode[{name}].ttl/hops", [py_b.ttl, py_b.hops], [js_b["ttl"], js_b["hops"]])
        check(f"decode[{name}].lat/lon", [py_b.lat, py_b.lon], [js_b["lat"], js_b["lon"]])
        check(f"decode[{name}].created",
              int(py_b.created.timestamp()), js_b["created"])
        check(f"decode[{name}].lowBattery", py_b.low_battery, js_b["lowBattery"])
        check(f"decode[{name}].origin", py_b.origin, js_b["origin"])
        check(f"decode[{name}].messageId", py_b.message_id, js_b["messageId"])

        py_relay = B.relay(py_bytes)
        js_relay = next(r for r in js["relayed"] if r["name"] == name)["hex"]
        check(f"relay[{name}]", py_relay.hex() if py_relay else None, js_relay)

    for ident in ("handset-7f3a", "d1", "x", "gps-1", "हाते-फोन", "shesh-9f2c"):
        check(f"truncate16[{ident!r}]", B.truncate16(ident), js["truncate"][ident])

    for label, payload in (("bad crc", None), ("short", None), ("garbage", None)):
        if label == "bad crc":
            good = B.encode("a", "b", when=WHEN)
            bad = good[:-1] + bytes([good[-1] ^ 0xFF])
            py_null = B.decode(bad) is None
        elif label == "short":
            py_null = B.decode(bytes([1, 2, 3])) is None
        else:
            py_null = B.decode(bytes(20)) is None
        js_null = next(x["null"] for x in js["rejected"] if x["name"] == label)
        check(f"reject[{label}]", py_null, js_null)

    if failures:
        print("MISMATCH between the Python and JavaScript beacon codecs:")
        for f in failures:
            print("  " + f)
        return 1

    total = len(CASES) * 12
    print(f"OK: the Python and JavaScript beacon codecs agree exactly "
          f"({len(CASES)} frames, {total} field comparisons, "
          f"{len(CASES)} relays, rejection cases identical)")
    print(f"frame size: {B.ENCODED_BYTES} bytes of {B.MAX_AD_BYTES} available "
          f"({B.MAX_AD_BYTES - B.ENCODED_BYTES} unused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
