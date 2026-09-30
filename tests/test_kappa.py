"""Kappa must reproduce published values, or the evaluation means nothing."""
import math

import pytest

from pahiro.eval.kappa import cohen_kappa, fleiss_kappa, interpret, report


def test_cohen_known_value():
    a = [1, 1, 0, 0]
    b = [1, 0, 0, 0]
    # po = 0.75, pe = 0.5  ->  kappa = 0.5
    assert cohen_kappa(a, b) == pytest.approx(0.5)


def test_cohen_perfect_agreement():
    a = [1, 0, 1, 1, 0]
    assert cohen_kappa(a, list(a)) == pytest.approx(1.0)


def test_cohen_total_disagreement_is_negative():
    a = [1, 1, 0, 0]
    b = [0, 0, 1, 1]
    assert cohen_kappa(a, b) == pytest.approx(-1.0)


def test_cohen_undefined_when_chance_is_certain():
    assert cohen_kappa([1, 1, 1], [1, 1, 1]) is None


def test_cohen_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        cohen_kappa([1, 0], [1])


def test_fleiss_matches_published_example():
    """Fleiss (1971) 14-rater, 10-subject, 5-category example: kappa ~= 0.210."""
    rows = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    ratings = [[cat for cat, c in enumerate(row) for _ in range(c)] for row in rows]
    assert fleiss_kappa(ratings) == pytest.approx(0.2099, abs=1e-3)


def test_fleiss_perfect_agreement():
    ratings = [[1, 1, 1], [0, 0, 0], [2, 2, 2]]
    assert fleiss_kappa(ratings) == pytest.approx(1.0)


def test_fleiss_requires_rectangular_input():
    with pytest.raises(ValueError):
        fleiss_kappa([[1, 2, 3], [1, 2]])


def test_interpret_bands():
    assert interpret(0.85) == "almost perfect"
    assert interpret(0.65) == "substantial"
    assert interpret(0.45) == "moderate"
    assert interpret(0.25) == "fair"
    assert interpret(0.05) == "slight"
    assert interpret(-0.2).startswith("poor")
    assert interpret(None) == "undefined"


def test_report_aggregates_a_panel():
    labels = ["Very Good", "Good", "Acceptable", "Poor"]
    scores = {
        "rater1": ["Very Good", "Good", "Good", "Acceptable"],
        "rater2": ["Very Good", "Good", "Acceptable", "Acceptable"],
        "rater3": ["Very Good", "Acceptable", "Good", "Poor"],
    }
    out = report(scores, labels)
    assert out["n_raters"] == 3 and out["n_items"] == 4
    assert 0.0 <= out["mean_pairwise_cohen"] <= 1.0
    assert out["mean_pairwise_interpretation"] in {
        "slight", "fair", "moderate", "substantial", "almost perfect"}
    assert out["fleiss"] is not None
