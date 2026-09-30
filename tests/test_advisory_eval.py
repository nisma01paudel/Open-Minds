"""E2 must report agreement, not just a distribution."""
import csv

import pytest

from pahiro.eval.advisory import (LABELS, AdvisoryItem, export_sheet, load_ratings,
                                  markdown, score)


def items():
    return [AdvisoryItem(id="a1", location="Dhading", state="primed-confirmed", text_ne="पाठ १"),
            AdvisoryItem(id="a2", location="Kavre", state="primed-unobserved", text_ne="पाठ २")]


def test_export_writes_a_row_per_item_and_empty_rater_columns(tmp_path):
    p = export_sheet(items(), tmp_path / "sheet.csv", raters=["r1", "r2"])
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert len(rows) == 2 and rows[0]["id"] == "a1"
    assert rows[0]["r1"] == "" and rows[0]["r2"] == ""
    assert (tmp_path / "sheet-RUBRIC.md").exists(), "the rubric must travel with the sheet"


def test_load_ratings_rejects_an_invalid_label(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("id,state,location,advisory_ne,english_gloss,r1,notes\na1,s,l,t,g,Excellent,\n")
    with pytest.raises(ValueError):
        load_ratings(p)


def test_score_reports_distribution_and_agreement(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("id,state,location,advisory_ne,english_gloss,r1,r2,notes\n"
                 "a1,s,l,t,g,Very Good,Very Good,\n"
                 "a2,s,l,t,g,Good,Poor,\n")
    rep = score(load_ratings(p))
    assert rep["n_raters"] == 2 and rep["n_items_common"] == 2
    # 2 of the 4 ratings are Very Good (a1 twice), so 50% - not 25%
    assert rep["mean_distribution_pct"]["Very Good"] == 50.0
    assert rep["n_disagreements"] == 1, "a2 disagrees and must be listed"
    assert rep["fleiss"] is not None


def test_perfect_agreement_gives_kappa_one(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("id,state,location,advisory_ne,english_gloss,r1,r2,notes\n"
                 "a1,s,l,t,g,Very Good,Very Good,\n"
                 "a2,s,l,t,g,Poor,Poor,\n")
    rep = score(load_ratings(p))
    assert rep["agreement"]["mean_pairwise_cohen"] == pytest.approx(1.0)
    assert rep["n_disagreements"] == 0


def test_unanimous_single_label_is_undefined_not_fake(tmp_path):
    """If every item gets one label, chance agreement is 1 and kappa is undefined."""
    p = tmp_path / "s.csv"
    p.write_text("id,state,location,advisory_ne,english_gloss,r1,r2,notes\n"
                 "a1,s,l,t,g,Good,Good,\na2,s,l,t,g,Good,Good,\n")
    rep = score(load_ratings(p))
    assert rep["agreement"]["mean_pairwise_cohen"] is None
    assert rep["interpretation"] == "undefined"


def test_markdown_compares_against_the_published_baseline(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("id,state,location,advisory_ne,english_gloss,r1,r2,notes\n"
                 "a1,s,l,t,g,Very Good,Good,\n")
    md = markdown(score(load_ratings(p)))
    assert "58.0%" in md and "kappa" in md
    assert "did not report an agreement statistic" in md
