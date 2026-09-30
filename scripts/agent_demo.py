#!/usr/bin/env python3
"""Run the slope-change agent end to end on real data, and show its work.

    python scripts/agent_demo.py --report "a rural road on the slope above a highway has failed" \
        --lon 85.05 --lat 27.76 --as-of 2024-07-20
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.agent import SlopeChangeAgent
from pahiro.ontology import Ontology
from pahiro.routing.router import LlamaServerBackend, Router


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--ontology", default="ontology/nepal-slope-routing.json")
    ap.add_argument("--model-url", default="http://127.0.0.1:8081")
    ap.add_argument("--no-model", action="store_true")
    ap.add_argument("--out", help="write the full run as JSON")
    a = ap.parse_args()

    ontology = Ontology.load(a.ontology)
    backend = None if a.no_model else LlamaServerBackend(a.model_url)
    if backend is not None and not backend.available():
        print(f"note: no model server at {a.model_url}; routing will be withheld\n")
        backend = None

    agent = SlopeChangeAgent(ontology=ontology, router=Router(backend))
    run = agent.run(a.report, a.lon, a.lat, date.fromisoformat(a.as_of))

    print("=== agent trace")
    for i, t in enumerate(run.trace, 1):
        mark = "ok " if t.ok else "ERR"
        print(f"  {i}. [{mark}] {t.name:22} {t.ms:>6} ms  {t.result}")
    print(f"\n=== decision: {run.state}   priority: {run.priority}")
    if run.rainfall_banner:
        print(f"    {run.rainfall_banner}")
    if run.staleness is not None:
        print(f"    {run.staleness.banner()}")
    if run.routing is not None:
        print(f"    institution: {run.routing.institution or '(withheld)'}")
        print(f"    legal basis: {(run.routing.legal_basis or '-')[:90]}")
        print(f"    rationale  : {run.routing.rationale[:200]}")

    print("\n=== advisory (Nepali)")
    print(run.advisory_ne)

    if run.dispatch is not None:
        print(f"\n=== dispatch: status={run.dispatch.status} needs_review={run.dispatch.needs_review}")
        print(f"    validate() -> {run.dispatch.validate() or 'OK'}")
    else:
        print("\n=== no dispatch: nothing to issue")

    if a.out:
        Path(a.out).write_text(run.to_json())
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
