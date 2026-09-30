"""Inter-rater reliability: Cohen's and Fleiss' kappa.

Why this module exists: Alruqimi et al. 2026 report expert ratings of
LLM-written landslide reports (58% Very Good / 30% Good / 8% Acceptable /
4% Poor) but explicitly report no agreement statistic, deferring it:
"Future evaluations could also further quantify expert consistency using
independent ratings and inter-rater reliability metrics such as Cohen's or
Fleiss' kappa."

We compute it. A quality score without an agreement statistic cannot be
distinguished from one rater's opinion, so this is the difference between a
claim and a measurement.
"""
from __future__ import annotations

from collections import Counter

# Landis & Koch (1977) conventional bands.
BANDS = (
    (0.81, "almost perfect"),
    (0.61, "substantial"),
    (0.41, "moderate"),
    (0.21, "fair"),
    (0.00, "slight"),
)


def interpret(kappa: float | None) -> str:
    if kappa is None:
        return "undefined"
    if kappa < 0:
        return "poor (worse than chance)"
    for threshold, label in BANDS:
        if kappa >= threshold:
            return label
    return "slight"


def cohen_kappa(a: list, b: list) -> float | None:
    """Agreement between exactly two raters on the same items.

    Returns None when kappa is undefined (fewer than 2 items, or both raters
    used a single identical category so chance agreement is 1).
    """
    if len(a) != len(b):
        raise ValueError("raters scored different numbers of items")
    n = len(a)
    if n < 2:
        return None

    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    categories = set(ca) | set(cb)
    pe = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in categories)

    if abs(1.0 - pe) < 1e-12:
        return None
    return (po - pe) / (1.0 - pe)


def fleiss_kappa(ratings: list[list[int]]) -> float | None:
    """Agreement among a variable number of raters over many items.

    ratings: one row per item, each row a list of category indices, one entry
    per rater (all rows must have the same length = number of raters).
    """
    if not ratings:
        return None
    n_raters = len(ratings[0])
    if n_raters < 2:
        return None
    if any(len(row) != n_raters for row in ratings):
        raise ValueError("every item must be scored by the same number of raters")

    n_items = len(ratings)
    if n_items < 2:
        return None

    categories = sorted({c for row in ratings for c in row})
    counts = [Counter(row) for row in ratings]

    # Agreement within each item.
    p_i = []
    for c in counts:
        total = sum(c.values())
        p_i.append((sum(v * v for v in c.values()) - total) / (total * (total - 1)))
    p_bar = sum(p_i) / n_items

    # Chance agreement from the marginal category proportions.
    p_j = {cat: sum(c.get(cat, 0) for c in counts) / (n_items * n_raters)
           for cat in categories}
    p_e_bar = sum(p * p for p in p_j.values())

    if abs(1.0 - p_e_bar) < 1e-12:
        return None
    return (p_bar - p_e_bar) / (1.0 - p_e_bar)


def report(scores: dict[str, list], labels: list[str]) -> dict:
    """Agreement across a panel, pairwise plus overall, ready to publish."""
    raters = [r for r in scores if scores[r]]
    pair: dict[str, float | None] = {}
    for i, r1 in enumerate(raters):
        for r2 in raters[i + 1:]:
            k = cohen_kappa(scores[r1], scores[r2])
            pair[f"{r1}~{r2}"] = k
    valid = [k for k in pair.values() if k is not None]
    mean_pairwise = sum(valid) / len(valid) if valid else None
    return {
        "n_raters": len(raters),
        "n_items": max((len(v) for v in scores.values()), default=0),
        "pairwise_cohen": pair,
        "mean_pairwise_cohen": mean_pairwise,
        "mean_pairwise_interpretation": interpret(mean_pairwise),
        "fleiss": fleiss_kappa([[labels.index(scores[r][i]) for r in raters]
                                for i in range(min((len(scores[r]) for r in raters), default=0))])
        if len(raters) >= 2 else None,
    }
