"""The dispatch object must refuse to be issued without a cited authority."""
from datetime import date, timedelta

import pytest

from pahiro.advisory.nepali import refusal_text, render
from pahiro.dispatch import MEDIUM, build_dispatch
from pahiro.ontology import AuthorityRule, Ontology, VERIFIED
from pahiro.routing.abstain import OPTICAL, RADAR, Observation, staleness_gate

AS_OF = date(2025, 7, 15)


def days_ago(n):
    return AS_OF - timedelta(days=n)


FRESH = [Observation(OPTICAL, days_ago(5), quality=0.9, scene_id="S2A_X")]
BLIND = [Observation(OPTICAL, days_ago(90), quality=0.9)]


def rule(**kw):
    base = dict(
        case_id="R1", asset_type="local-road", jurisdiction="municipality",
        hazard_type="slope-instability", institution="Rural Municipality",
        office="Ward No. 5", legal_basis="Local Government Operation Act 2074, Sch. 8",
        escalation=["municipality", "district committee"], confidence=VERIFIED,
        source_url="https://example.gov.np/act",
    )
    base.update(kw)
    return AuthorityRule(**base)


def test_abstain_dispatch_is_valid_and_carries_no_authority():
    st = staleness_gate(BLIND, AS_OF)
    d = build_dispatch(location="Dhading", as_of=AS_OF, staleness=st,
                       advisory_ne=refusal_text(st))
    assert d.status == "abstain"
    assert d.validate() == []
    assert d.authority is None and d.priority is None


def test_non_abstaining_dispatch_without_routing_requires_review():
    st = staleness_gate(FRESH, AS_OF)
    d = build_dispatch(location="Dhading", as_of=AS_OF, staleness=st,
                       advisory_ne="advisory", priority=MEDIUM,
                       scenes=["S2A_X"])
    assert d.needs_review is True
    assert d.validate() == []


def test_uncited_rule_is_rejected_at_the_source():
    """A rule with no legal basis can never become an authority block."""
    from pahiro.dispatch import authority_from_rule

    bad = rule(legal_basis="")
    assert not bad.citable
    with pytest.raises(ValueError):
        authority_from_rule(bad)

    unlinked = rule(source_url=None)
    assert not unlinked.citable
    with pytest.raises(ValueError):
        authority_from_rule(unlinked)


def test_dispatch_with_cited_rule_validates():
    st = staleness_gate(FRESH, AS_OF)
    d = build_dispatch(location="Dhading", as_of=AS_OF, staleness=st,
                       advisory_ne="advisory", priority=MEDIUM,
                       rule=rule(), scenes=["S2A_X"])
    assert d.validate() == []
    assert d.authority["legal_basis"].startswith("Local Government")
    assert d.needs_review is False


def test_missing_source_scene_invalidates():
    st = staleness_gate(FRESH, AS_OF)
    d = build_dispatch(location="Dhading", as_of=AS_OF, staleness=st,
                       advisory_ne="advisory", priority=MEDIUM, rule=rule())
    assert any("source scene" in p for p in d.validate())


def test_json_round_trip_preserves_everything():
    st = staleness_gate(FRESH, AS_OF)
    d = build_dispatch(location="Dhading", as_of=AS_OF, staleness=st,
                       advisory_ne="advisory", priority=MEDIUM, rule=rule(),
                       scenes=["S2A_X"])
    back = type(d).from_json(d.to_json())
    assert back.location == d.location and back.as_of == d.as_of
    assert back.authority == d.authority


def test_ontology_lookup_is_ambiguous_safe():
    o = Ontology([rule(case_id="A"), rule(case_id="B")])
    assert o.lookup("local-road") is None, "ambiguity must abstain, not guess"
    assert o.lookup("strategic-road") is None, "no match must abstain"


def test_ontology_lookup_finds_single_rule():
    o = Ontology([rule()])
    found = o.lookup("local-road", jurisdiction="municipality")
    assert found is not None and found.case_id == "R1"


def test_nepali_render_omits_authority_when_uncited():
    txt = render(location="धादिङ", as_of="2025-07-15", what_changed="सतह परिवर्तन",
                 evidence_state="रडार मात्र", why_it_matters="सडक जोखिममा",
                 inspect_first=["सडक खण्ड"], needs_review=True)
    assert "जिम्मेवार निकाय" in txt and "बाँकी" in txt
    assert "कानुनी आधार" not in txt


def test_nepali_render_includes_citation_when_present():
    txt = render(location="धादिङ", as_of="2025-07-15", what_changed="सतह परिवर्तन",
                 evidence_state="रडार", why_it_matters="सडक जोखिममा",
                 inspect_first=["सडक खण्ड"], authority_institution="गाउँपालिका",
                 authority_office="वडा नं. ५", legal_basis="स्थानीय सरकार सञ्चालन ऐन २०७४")
    assert "कानुनी आधार" in txt
