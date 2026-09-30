"""Guards on the documented demo command.

Both of these were real defects on the code path the README tells a reader to run, and
both were invisible to the rest of the suite because they only appear when the script is
executed end to end.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (REPO / "scripts" / "demo_end_to_end.py").read_text(encoding="utf-8")


def test_demo_defaults_to_the_ontology_that_ships_with_the_repo():
    """It used to default to NOTHING, so the README's --report example routed against an
    empty rule set and the model could only abstain. The output even said so - "ontology:
    0 cited rules" - while the shipped file had 14."""
    src = _source()
    assert "nepal-slope-routing.json" in src, "the demo must default to the shipped ontology"
    from pahiro.ontology import Ontology

    ont = Ontology.load(str(REPO / "ontology" / "nepal-slope-routing.json"))
    assert len(ont.rules) >= 10, f"shipped ontology should carry real rules, has {len(ont.rules)}"


def test_demo_does_not_reuse_one_name_for_two_decision_types():
    """`decision` held the staleness gate and was then overwritten by a RoutingDecision,
    which has no `may_issue`. The documented --report command died with AttributeError."""
    src = _source()
    # the routing result must be bound to its own name
    assert re.search(r"^\s*routing = router\.triage_route", src, re.M), \
        "the routing result must not be assigned to `decision`"
    # and no downstream line may read may_issue off the routing object
    for m in re.finditer(r"routing\.may_issue", src):
        raise AssertionError("routing.may_issue does not exist")
    # the staleness gate must survive to the dispatch step
    assert "staleness=decision" in src, "the staleness gate must still reach build_dispatch"


def test_missing_ontology_is_fatal_not_silent(tmp_path):
    """Silently routing against an empty rule set is how the demo abstained for weeks."""
    src = _source()
    assert "refusing to route" in src
    assert "does not exist" in src
