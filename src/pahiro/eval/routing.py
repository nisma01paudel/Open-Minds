"""E1: routing accuracy, measured on a labelled scenario set.

Ground truth for each scenario is the expert reading of the reported facts against
the cited legal provisions (see benchmark/routing-scenarios.jsonl, which records the
reasoning for every label). This is deliberately NOT derived from the ontology: a
test whose answers come from the system under test measures nothing.

Three error classes matter, and they are not equally bad:
- MISROUTE   - a confident wrong authority. The worst outcome: it sends a national
               highway failure to a ward, or a ward's road to the ministry.
- OVER-ROUTE - routing when the report identifies nothing. Erodes trust.
- UNDER-ROUTE- abstaining when the facts were sufficient. Misses real hazards.

    python -m pahiro.eval.routing --scenarios benchmark/routing-scenarios.jsonl \
        --out reports/routing-eval.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pahiro.ontology import Ontology
from pahiro.routing.router import LlamaServerBackend, Router


def load_scenarios(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def evaluate(scenarios: list[dict], ontology: Ontology, router: Router,
             evidence_state: str = "", mode: str = "two-stage") -> dict:
    results = []
    call = (router.triage_route_single_call if mode == "single-call" else router.triage_route)
    for sc in scenarios:
        d = call(ontology, sc["facts"], evidence_state=evidence_state)
        expected = sc["case"]
        predicted = d.case_id if d.case_id else "none"
        row = {
            "id": sc["id"],
            "expected_case": expected,
            "predicted_case": predicted,
            "expected_asset": sc["asset"],
            "predicted_asset": d.asset_type or "none",
            "expected_role": sc["role"],
            "predicted_role": d.role or "none",
            "institution": d.institution,
            "legal_basis": d.legal_basis,
            "priority": d.priority,
            "used_model": d.used_model,
            "numeric_claim_withheld": d.numeric_claim_withheld,
            "rationale": d.rationale[:300],
            "case_correct": predicted == expected,
            "asset_correct": (d.asset_type or "none") == sc["asset"],
            "role_correct": (d.role or "none") == sc["role"],
        }
        expected_rule = next((r for r in ontology.rules if r.case_id == expected), None)
        got_rule = next((r for r in ontology.rules if r.case_id == predicted), None)
        row["escalation_correct"] = bool(
            expected_rule and got_rule and expected_rule.escalation and got_rule.escalation
            and expected_rule.escalation[0] == got_rule.escalation[0])
        row["abstained"] = predicted == "none"
        row["should_abstain"] = expected == "none"
        # the dangerous confusion: the two road tiers swapped
        pair = {sc["asset"], d.asset_type or "none"}
        row["misroute_across_tiers"] = pair == {"local-road", "strategic-road"}
        results.append(row)

    n = len(results)
    concrete = [r for r in results if not r["should_abstain"]]
    abstain = [r for r in results if r["should_abstain"]]

    def pct(k, rows):
        return round(100.0 * sum(1 for r in rows if r[k]) / len(rows), 1) if rows else 0.0

    tp = sum(1 for r in abstain if r["abstained"])
    fp = sum(1 for r in concrete if r["abstained"])          # under-route
    fn = sum(1 for r in abstain if not r["abstained"])       # over-route
    precision = 100.0 * tp / (tp + fn) if (tp + fn) else 0.0
    recall = 100.0 * tp / (tp + fp) if (tp + fp) else 0.0

    return {
        "n": n,
        "case_accuracy": pct("case_correct", results),
        "asset_accuracy": pct("asset_correct", results),
        "role_accuracy": pct("role_correct", results),
        "escalation_accuracy": pct("escalation_correct", concrete),
        "case_accuracy_on_routable": pct("case_correct", concrete),
        "abstention_precision": round(precision, 1),
        "abstention_recall": round(recall, 1),
        "under_routes": fp,
        "over_routes": fn,
        "tier_confusions": sum(1 for r in results if r["misroute_across_tiers"]),
        "numeric_claims_withheld": sum(1 for r in results if r["numeric_claim_withheld"]),
        "used_model": sum(1 for r in results if r["used_model"]),
        "results": results,
    }


def markdown(rep: dict) -> str:
    lines = [
        "# E1 — routing accuracy",
        "",
        f"Mode: **{rep.get('mode', 'two-stage')}** · Scenarios: **{rep['n']}** · answered by the open-weight model: {rep['used_model']}/{rep['n']}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Case accuracy (exact `case_id`) | **{rep['case_accuracy']}%** |",
        f"| Case accuracy on routable scenarios | **{rep['case_accuracy_on_routable']}%** |",
        f"| Asset identification | {rep['asset_accuracy']}% |",
        f"| Duty/role identification | {rep['role_accuracy']}% |",
        f"| Escalation first hop correct | {rep['escalation_accuracy']}% |",
        f"| Abstention precision | {rep['abstention_precision']}% |",
        f"| Abstention recall | {rep['abstention_recall']}% |",
        f"| **Misroutes across road tiers** | **{rep['tier_confusions']}** |",
        f"| Under-routes (abstained when routable) | {rep['under_routes']} |",
        f"| Over-routes (routed when unidentifiable) | {rep['over_routes']} |",
        f"| Numeric claims withheld by the guard | {rep['numeric_claims_withheld']} |",
        "",
        "## Per scenario",
        "",
        "| id | expected | predicted | asset | ok |",
        "|---|---|---|---|---|",
    ]
    for r in rep["results"]:
        tick = "✅" if r["case_correct"] else "❌"
        lines.append(f"| {r['id']} | {r['expected_case']} | {r['predicted_case']} "
                     f"| {r['predicted_asset']} | {tick} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure routing accuracy (E1).")
    ap.add_argument("--scenarios", default="benchmark/routing-scenarios.jsonl")
    ap.add_argument("--ontology", default="ontology/nepal-slope-routing.json")
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--mode", default="two-stage", choices=["two-stage", "single-call"],
                    help="two-stage decomposes (asset, duty) then maps deterministically; "
                         "single-call is the ablation arm")
    ap.add_argument("--out", default="reports/routing-eval.json")
    a = ap.parse_args(argv)

    scenarios = load_scenarios(a.scenarios)
    if a.limit:
        scenarios = scenarios[:a.limit]
    ontology = Ontology.load(a.ontology)
    router = Router(LlamaServerBackend(a.url))
    if not router.backend.available():
        print("WARNING: model server not reachable; the harness will measure abstention only",
              file=sys.stderr)

    rep = evaluate(scenarios, ontology, router, mode=a.mode)
    rep["mode"] = a.mode
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    md = out.with_suffix(".md")
    md.write_text(markdown(rep))
    print(f"case accuracy: {rep['case_accuracy']}%  "
          f"(routable: {rep['case_accuracy_on_routable']}%)  "
          f"tier misroutes: {rep['tier_confusions']}")
    print(f"wrote {out} and {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
