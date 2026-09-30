"""E2 - advisory quality, with the agreement statistic the prior work omitted.

Alruqimi et al. 2026 rated LLM-written landslide reports on a four-label rubric and
reported 58% Very Good / 30% Good / 8% Acceptable / 4% Poor, but explicitly deferred
agreement: "Future evaluations could also further quantify expert consistency using
independent ratings and inter-rater reliability metrics such as Cohen's or Fleiss'
kappa."

A quality distribution without an agreement statistic cannot be distinguished from
one rater's opinion. This module produces the sheet, scores it, and reports kappa
alongside the distribution - plus the disagreements verbatim, because the failure
cases are the useful part.

The rubric is adapted: theirs still reads "caption" in the definition of Very Good,
inherited from image-captioning evaluation. Ours is written for advisories.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from pahiro.eval.kappa import fleiss_kappa, interpret, report

LABELS = ["Very Good", "Good", "Acceptable", "Poor"]

RUBRIC = {
    "Very Good": ("Free of irrelevant information; states what changed, the state of the "
                  "evidence, what to check first and who is responsible, all correctly and "
                  "without overclaiming."),
    "Good": ("Only minor issues - a missing attribute that does not materially affect the "
             "reader, or slightly imprecise wording."),
    "Acceptable": ("Contains irrelevant information, or omits something a reader needs, in a "
                   "way that undermines clarity."),
    "Poor": ("Misstates or invents a fact, names an office without a basis, claims a "
             "confirmation the evidence does not support, or would mislead a reader into the "
             "wrong action."),
}


@dataclass
class AdvisoryItem:
    id: str
    location: str
    state: str                      # the agent's decision state
    text_ne: str
    text_en: str = ""               # a gloss, for raters who do not read Nepali fluently

    @property
    def one_line(self) -> str:
        return " ".join(self.text_ne.split())[:160]


@dataclass
class RatingSheet:
    items: list[AdvisoryItem]
    raters: list[str] = field(default_factory=list)


def export_sheet(items: list[AdvisoryItem], path: str | Path,
                 raters: list[str] | None = None) -> Path:
    """Write the CSV a panel fills in. One row per advisory, one column per rater."""
    raters = raters or ["rater1", "rater2", "rater3"]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "state", "location", "advisory_ne", "english_gloss", *raters, "notes"])
        for it in items:
            w.writerow([it.id, it.state, it.location, it.text_ne, it.text_en,
                        *["" for _ in raters], ""])
    rubric = out.with_name(out.stem + "-RUBRIC.md")
    lines = ["# Rating rubric", "",
             f"Valid labels: {', '.join(LABELS)}", "",
             "Fill one column per rater independently. Do not discuss before scoring.", ""]
    lines += [f"**{k}** — {v}" for k, v in RUBRIC.items()]
    lines += ["", "Rate each advisory on the rubric only. A reader who cannot act on it is "
                  "not Very Good, however well written it is."]
    rubric.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def load_ratings(path: str | Path, raters: list[str] | None = None) -> dict[str, dict[str, str]]:
    """Read a filled sheet into {rater: {item_id: label}}."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    # Any column that is not part of the sheet's metadata is a rater column, so a
    # panel can name themselves anything (r1, rater_ayush, initials) without the
    # loader silently ignoring them.
    metadata = {"id", "state", "location", "advisory_ne", "english_gloss", "notes", ""}
    raters = raters or [c for c in rows[0] if c not in metadata]
    out: dict[str, dict[str, str]] = {}
    for r in raters:
        got: dict[str, str] = {}
        for row in rows:
            label = (row.get(r) or "").strip()
            if label:
                if label not in LABELS:
                    raise ValueError(f"unknown label {label!r} for {r} on item {row.get('id')}")
                got[row["id"]] = label
        if got:
            out[r] = got
    return out


def score(ratings: dict[str, dict[str, str]], labels: list[str] = LABELS) -> dict:
    """Distribution per rater, the mean, agreement (kappa), and the disagreements."""
    raters = sorted(ratings)
    if not raters:
        return {"n_raters": 0, "n_items": 0, "error": "no ratings supplied"}

    common = set(ratings[raters[0]])
    for r in raters[1:]:
        common &= set(ratings[r])
    items = sorted(common)

    per_rater = {r: {lab: sum(1 for i in items if ratings[r][i] == lab) for lab in labels}
                 for r in raters}
    n = len(items) or 1
    mean = {lab: round(sum(per_rater[r][lab] for r in raters) / len(raters) / n * 100, 1)
            for lab in labels}
    agree = report({r: [ratings[r][i] for i in items] for r in raters}, labels) if items else {}
    disagreements = [{"id": i, "scores": {r: ratings[r][i] for r in raters}}
                     for i in items if len({ratings[r][i] for r in raters}) > 1]
    return {
        "n_raters": len(raters),
        "n_items_common": len(items),
        "per_rater_counts": per_rater,
        "mean_distribution_pct": mean,
        "agreement": agree,
        "n_disagreements": len(disagreements),
        "disagreements": disagreements,
        "fleiss": fleiss_kappa([[labels.index(ratings[r][i]) for r in raters] for i in items])
        if items and len(raters) >= 2 else None,
        "interpretation": interpret(agree.get("mean_pairwise_cohen") if agree else None),
    }


def markdown(rep: dict, baseline: dict | None = None) -> str:
    """Report the distribution next to the published baseline, with kappa."""
    baseline = baseline or {"Very Good": 58.0, "Good": 30.0, "Acceptable": 8.0, "Poor": 4.0}
    L = ["# E2 — advisory quality, expert-rated", "",
         f"Raters: **{rep.get('n_raters')}** · items scored by all raters: "
         f"**{rep.get('n_items_common')}**", "",
         "| Label | This project | Alruqimi et al. 2026 (English/Italian baseline) |",
         "|---|---|---|"]
    for lab in LABELS:
        L.append(f"| {lab} | **{rep['mean_distribution_pct'][lab]}%** | {baseline[lab]}% |")
    L += ["", f"**Agreement:** mean pairwise Cohen's kappa "
              f"`{rep.get('agreement', {}).get('mean_pairwise_cohen')}` "
              f"({rep.get('interpretation')}), Fleiss' kappa `{rep.get('fleiss')}`.",
          "", "Alruqimi et al. did not report an agreement statistic and deferred it to future "
          "work. Without one, a quality distribution cannot be separated from a single rater's "
          "opinion.", "",
          f"**Disagreements:** {rep.get('n_disagreements')} of {rep.get('n_items_common')} items.",
          "", "The disagreements are the useful part and are kept verbatim below.", ""]
    for d in rep.get("disagreements", []):
        L.append(f"- `{d['id']}`: " + ", ".join(f"{k}={v}" for k, v in d["scores"].items()))
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="E2 advisory-quality tooling.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="write a rating sheet from advisories JSON")
    e.add_argument("--in", dest="src", required=True)
    e.add_argument("--out", default="reports/advisory-sheet.csv")
    s = sub.add_parser("score", help="score a filled sheet")
    s.add_argument("--sheet", required=True)
    s.add_argument("--out", default="reports/advisory-quality.json")
    a = ap.parse_args(argv)

    if a.cmd == "export":
        items = [AdvisoryItem(**{k: v for k, v in r.items()})
                 for r in json.loads(Path(a.src).read_text())]
        path = export_sheet(items, a.out)
        print(f"wrote {path} and its rubric - give it to {3} independent raters")
        return 0

    ratings = load_ratings(a.sheet)
    rep = score(ratings)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    out.with_suffix(".md").write_text(markdown(rep))
    e = rep.get("agreement", {}).get("mean_pairwise_cohen")
    print(f"items scored by all raters: {rep.get('n_items_common')} | "
          f"mean pairwise kappa: {e} ({rep.get('interpretation')})")
    print(f"wrote {out} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
