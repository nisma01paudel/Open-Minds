"""The router must never let the model invent an institution."""
from pahiro.ontology import Ontology
from pahiro.routing.router import (HIGH, LOW, LlamaServerBackend, Router, build_schema)

ONTOLOGY = "ontology/nepal-slope-routing.json"


class FakeBackend:
    """Stands in for the model so tests need no server."""
    def __init__(self, reply): self.reply = reply; self.calls = 0
    def available(self): return True
    def decide(self, prompt, schema):
        self.calls += 1
        return self.reply


def test_retrieval_is_asset_anchored():
    """Retrieval must NOT offer other asset types - that is the point.

    A local road failing onto a national highway needs TWO routing calls, not one
    menu of every asset in the country.
    """
    o = Ontology.load(ONTOLOGY)
    local = Router().retriever.retrieve(o, "local-road", jurisdiction="municipality")
    assert local[0].case_id == "local-road-maintenance"
    assert "strategic-road-maintenance" not in [c.case_id for c in local]

    highway = Router().retriever.retrieve(o, "strategic-road", jurisdiction="federal")
    assert highway[0].case_id == "strategic-road-maintenance"
    assert "local-road-maintenance" not in [c.case_id for c in highway]


def test_retrieval_never_returns_other_roles():
    o = Ontology.load(ONTOLOGY)
    maint = Router().retriever.retrieve(o, "local-road", role="maintenance")
    emerg = Router().retriever.retrieve(o, "local-road", role="emergency")
    assert all(c.role == "maintenance" for c in maint)
    assert all(c.role == "emergency" for c in emerg)
    assert maint[0].case_id != emerg[0].case_id


def test_schema_enum_locks_the_model_to_retrieved_ids():
    o = Ontology.load(ONTOLOGY)
    cands = Router().retriever.retrieve(o, "local-road", jurisdiction="municipality")
    schema = build_schema(cands)
    enum = schema["properties"]["case_id"]["enum"]
    assert enum == [c.case_id for c in cands]
    assert "strategic-road-maintenance" not in enum


def test_authority_comes_from_the_ontology_not_the_model():
    o = Ontology.load(ONTOLOGY)
    backend = FakeBackend({"case_id": "local-road-maintenance", "priority": "high",
                           "rationale": "the ward clears landslides in local roads"})
    d = Router(backend).route(o, "local-road", jurisdiction="municipality")
    assert d.used_model and not d.fallback_used
    assert d.institution.startswith("Rural/Urban Municipality")
    assert "s.12(2)(c)(23)" in d.legal_basis


def test_invalid_choice_falls_back_to_deterministic():
    o = Ontology.load(ONTOLOGY)
    backend = FakeBackend({"case_id": "invented-ministry-of-nowhere", "priority": "high",
                           "rationale": "x"})
    d = Router(backend).route(o, "local-road", jurisdiction="municipality")
    assert d.fallback_used and not d.used_model


def test_model_failure_falls_back():
    class Broken:
        def available(self): return True
        def decide(self, p, s): raise RuntimeError("server down")
    o = Ontology.load(ONTOLOGY)
    d = Router(Broken()).route(o, "local-road", jurisdiction="municipality")
    assert d.fallback_used and d.case_id == "local-road-maintenance"


def test_numeric_rationale_is_withheld():
    o = Ontology.load(ONTOLOGY)
    backend = FakeBackend({"case_id": "local-road-maintenance", "priority": "high",
                           "rationale": "the slope has increased by 31 degrees"})
    d = Router(backend).route(o, "local-road", jurisdiction="municipality")
    assert d.numeric_claim_withheld
    assert "31" not in d.rationale


def test_ambiguous_asset_withholds_routing():
    o = Ontology.load(ONTOLOGY)
    d = Router(None).route(o, "nonexistent-asset")
    assert d.case_id is None and d.fallback_used
    assert "human review" in d.rationale


def test_emergency_role_picks_a_different_chain_than_maintenance():
    o = Ontology.load(ONTOLOGY)
    maint = Router(None).route(o, "strategic-road", jurisdiction="federal")
    emerg = Router(None).route_emergency(o, "strategic-road", jurisdiction="federal")
    assert maint.institution.startswith("Department of Roads")
    assert emerg.institution.startswith("District Disaster")
    assert maint.case_id != emerg.case_id


def test_without_the_model_nothing_is_routed():
    """The eligibility litmus test, expressed as an executable assertion.

    "If you deleted the AI call from your codebase, would the product still do its
    job? If yes, it doesn't qualify." Here is the proof that it does not: with no
    model, an unstructured report cannot be resolved to an asset and a duty, so no
    authority is selected and nothing is dispatched.
    """
    o = Ontology.load(ONTOLOGY)
    d = Router(None).triage_route(o, "A national highway is blocked by a landslide.")
    assert d.case_id is None
    assert d.institution is None
    assert d.fallback_used
    assert any("load-bearing" in n for n in d.notes)
    assert "requires the open-weight model" in d.rationale


def test_structured_routing_still_works_without_the_model():
    """The deterministic path handles a report that already names the asset.

    That is the honest boundary: structured input is routable without AI, free text
    is not. Both halves are stated in docs/AI-USAGE.md.
    """
    o = Ontology.load(ONTOLOGY)
    d = Router(None).route(o, "local-road", jurisdiction="municipality")
    assert d.case_id == "local-road-maintenance" and d.fallback_used
