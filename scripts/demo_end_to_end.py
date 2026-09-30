#!/usr/bin/env python3
"""End-to-end: a real coordinate, real satellite observations, a real advisory.

    python scripts/demo_end_to_end.py --lon 85.0575 --lat 27.7620 --as-of 2024-07-20 \
        --obs evidence/screen-dhading-2024.jsonl --radar evidence/s1-radar-dates.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.advisory.nepali import evidence_state_ne, refusal_text, render
from pahiro.dispatch import build_dispatch
from pahiro.eval.gap import load_observations
from pahiro.ontology import Ontology
from pahiro.routing.abstain import Observation, staleness_gate
from pahiro.routing.resolve import resolve


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--obs", required=True)
    ap.add_argument("--radar")
    ap.add_argument("--ontology")
    ap.add_argument("--cache", default="cache/ward-cache.json")
    ap.add_argument("--offline", action="store_true", help="use the cache only")
    a = ap.parse_args()

    as_of = date.fromisoformat(a.as_of)

    # 1. Where is this slope? Government data, not a guess.
    ctx = resolve(a.lon, a.lat, cache_path=a.cache, use_cache=a.offline)
    print("=== 1. location resolved from government data")
    print(f"    {ctx.describe()}   [source: {ctx.source}]")
    if ctx.centre:
        print(f"    nearest centre: {ctx.centre}")

    # 2. What do we actually see?
    optical = [o for o in load_observations(a.obs) if o.observed_at <= as_of]
    # Radar usability is NOT yet measured (the Sentinel-1 GRD products also
    # carry a geolocation trap), so radar enters as unverified evidence. The
    # gate must treat it as weaker than a validated observation.
    radar = ([Observation(sensor=o.sensor, observed_at=o.observed_at,
                          quality=1.0, scene_id=o.scene_id, verified=False)
              for o in load_observations(a.radar, sensor="sentinel-1", quality=1.0)
              if o.observed_at <= as_of] if a.radar else [])
    print(f"\n=== 2. evidence as of {as_of}")
    for o in sorted(optical, key=lambda x: x.observed_at, reverse=True)[:3]:
        print(f"    {o.observed_at}  {o.sensor:<14} usable={o.quality:.3f}")
    print(f"    optical observations available: {len(optical)}   radar: {len(radar)}")

    # 3. May we speak at all?
    decision = staleness_gate(optical + radar, as_of)
    print(f"\n=== 3. staleness gate -> {decision.status.upper()} ({decision.confidence})")
    print(f"    {decision.banner()}")
    for r in decision.reasons:
        print(f"    - {r}")

    # 4. Who is responsible? Only with a citation.
    ontology = Ontology.load(a.ontology) if a.ontology else Ontology([])
    rule = ontology.lookup("local-road", hazard_type="slope-instability")
    print(f"\n=== 4. routing")
    print(f"    ontology: {len(ontology)} rule(s) loaded"
          f"{'' if ontology else '  -> no citable rule, dispatch will be marked needs_review'}")

    # 5. Assemble.
    if decision.may_issue:
        advisory = render(
            location=ctx.describe(), as_of=a.as_of,
            what_changed="सतह परिवर्तन संकेत (स्याटेलाइट/रडार)",
            evidence_state=evidence_state_ne(decision),
            why_it_matters="यो ढलानसँग जोडिएको सडक खण्ड जोखिममा पर्न सक्छ।",
            inspect_first=["सडकको उक्त खण्ड", "माथिल्लो ढलानको जल-निकास"],
            recommendation="मर्मत गर्नुअघि ढलानको अवस्था जाँच्नुहोस्।",
            authority_institution=(rule.institution if rule else None),
            authority_office=(rule.office if rule else None),
            legal_basis=(rule.legal_basis if rule else None),
            needs_review=rule is None,
        )
    else:
        advisory = refusal_text(decision)

    d = build_dispatch(
        location=ctx.describe(), as_of=as_of, staleness=decision, advisory_ne=advisory,
        findings=[f"optical observations: {len(optical)}", f"radar observations: {len(radar)}"],
        recommendation=None if not decision.may_issue else "inspect before repairing",
        priority=None if not decision.may_issue else ("high" if optical else "medium"),
        rule=rule, scenes=[o.scene_id for o in optical[-3:] if o.scene_id],
        sensors=sorted({o.sensor for o in optical + radar}),
        ontology_version=ontology.version,
    )
    d.routing_context = {"ward": ctx.ward, "municipality": ctx.municipality,
                         "district": ctx.district, "province": ctx.province,
                         "source": ctx.source}

    print(f"\n=== 5. dispatch object")
    print(f"    status: {d.status}   confidence: {d.confidence}   priority: {d.priority}")
    print(f"    needs_review: {d.needs_review}   authority: {(d.authority or {}).get('institution')}")
    print(f"    validate() -> {d.validate() or 'OK'}")

    print("\n=== 6. advisory (Nepali)")
    print(advisory)

    # 7. The government register payload.
    from pahiro.ingest.bipad import BipadClient, Ward
    ward_obj = Ward(ward=ctx.ward, municipality=ctx.municipality, district=ctx.district,
                    province=ctx.province, centre=ctx.centre, properties=ctx.attributes)
    mapped = BipadClient().to_bipad_highway_payload(d, ward_obj)
    print("\n=== 7. BIPAD highway-register payload (what we can evidence)")
    print(json.dumps(mapped["payload"], ensure_ascii=False, indent=2))
    print(f"    requires_from_office: {mapped['requires_from_office']}")
    return 0 if not d.validate() else 1


if __name__ == "__main__":
    raise SystemExit(main())
