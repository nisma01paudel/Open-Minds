#!/usr/bin/env python3
"""End-to-end demo on REAL satellite data.

Reads the observation series built by `pahiro.ingest.series` and asks the
product a single question for a chosen date: may an advisory be issued at all?

    python scripts/demo_dispatch.py --obs evidence/dhading-2024-obs.jsonl --as-of 2024-07-20
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from pahiro.advisory.nepali import refusal_text, render
from pahiro.dispatch import build_dispatch
from pahiro.ontology import Ontology
from pahiro.routing.abstain import Observation, staleness_gate


def load_observations(path: str | Path) -> list[Observation]:
    obs = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        obs.append(
            Observation(
                sensor=r["sensor"],
                observed_at=date.fromisoformat(r["acquired"]),
                quality=float(r.get("usable_fraction") or 0.0),
                scene_id=r.get("scene_id"),
            )
        )
    return obs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obs", required=True)
    ap.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    ap.add_argument("--location", default="धादिङ — ज्याप्ले खोला करिडोर")
    ap.add_argument("--ontology", help="optional ontology JSON")
    a = ap.parse_args()

    as_of = date.fromisoformat(a.as_of)
    all_obs = load_observations(a.obs)

    # CRITICAL: never let a judge see future data in the evidence view. Only
    # observations at or before the reporting date may be shown or cited.
    obs = [o for o in all_obs if o.observed_at <= as_of]
    withheld = len(all_obs) - len(obs)

    decision = staleness_gate(obs, as_of)

    print(f"=== evidence available for {a.location} as of {as_of}")
    if not obs:
        print("    (no observation on or before this date)")
    for o in sorted(obs, key=lambda x: x.observed_at, reverse=True)[:5]:
        print(f"    {o.observed_at}  {o.sensor:<14} usable={o.quality:.3f}  {o.scene_id}")
    if withheld:
        print(f"    [{withheld} later observation(s) withheld - not evidence at this date]")
    print(f"\n    {decision.banner()}")
    for r in decision.reasons:
        print(f"    - {r}")

    ontology = Ontology.load(a.ontology) if a.ontology else Ontology([])
    findings = ["सतह परिवर्तन संकेत"] if decision.may_issue else []

    if decision.may_issue:
        advisory = render(
            location=a.location, as_of=a.as_of,
            what_changed="; ".join(findings) or "परिवर्तन संकेत",
            evidence_state=decision.banner(),
            why_it_matters="यो ढलानसँग जोडिएको सडक खण्ड जोखिममा पर्न सक्छ।",
            inspect_first=["सडकको उक्त खण्ड", "माथिल्लो ढलानको जल-निकास"],
            needs_review=True,
        )
    else:
        advisory = refusal_text(decision)

    d = build_dispatch(
        location=a.location, as_of=as_of, staleness=decision, advisory_ne=advisory,
        findings=findings,
        scenes=[o.scene_id for o in obs if o.scene_id][-3:],
        sensors=sorted({o.sensor for o in obs}),
        ontology_version=ontology.version,
    )

    print("\n=== dispatch object")
    print(f"    status     : {d.status}")
    print(f"    confidence : {d.confidence}")
    print(f"    priority   : {d.priority}")
    print(f"    authority  : {d.authority}")
    print(f"    needs_review: {d.needs_review}")
    problems = d.validate()
    print(f"    validate() -> {problems if problems else 'OK'}")

    print("\n=== NOTE: this demo series is monthly-sampled (best scene per month), so the "
          "freshness window is being exercised on a deliberately sparse record." if len(obs) < 12 else "")

    print("\n=== advisory (Nepali)")
    print(advisory)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
