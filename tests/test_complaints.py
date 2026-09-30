"""The complaint portal: a report that lands on the office legally obliged to answer it."""
from pahiro import complaints as C

SITES = [
    {"id": "1", "title": "Landslide at Test Ward-3", "lat": 27.70, "lon": 85.31,
     "authority": "Rural/Urban Municipality (Ward Committee)",
     "office": "Ward Committee under the Ward Chair",
     "legal_basis": "LGOA 2074 s.12(2)(c)(23)"},
]


def test_a_nearby_report_is_routed_to_the_office_that_holds_the_duty():
    c = C.draft(27.7005, 85.3105, "crack", "Opened after the rain.", sites=SITES)
    assert c.office == "Ward Committee under the Ward Chair"
    assert "LGOA 2074" in c.legal_basis
    assert c.slope_title == "Landslide at Test Ward-3"
    assert c.refused_because is None


def test_the_letter_cites_the_section_in_both_languages():
    """The citation is the whole point - without it this is a contact form."""
    c = C.draft(27.7005, 85.3105, "crack", "Opened after the rain.", sites=SITES)
    # The English letter cites s.12(2)(c); the Nepali letter writes the same provision in
    # Devanagari - धारा १२(२)(ग) - which is how a Nepali office reads its own statute. Asserting
    # the Latin form in both would have been an English-speaker's test, not a Nepali letter's.
    assert "2074" in c.letter_en and "12(2)(c)" in c.letter_en
    assert "२०७४" in c.letter_ne, "the Nepali letter must date the Act in Devanagari"
    assert "१२(२)(ग)" in c.letter_ne, "the Nepali letter must cite the section in Devanagari"
    assert "जमिन चिरा" in c.letter_ne, "the Nepali letter must be in Nepali"


def test_it_refuses_rather_than_writing_to_the_wrong_office():
    """A letter to the wrong office teaches the citizen that complaining does not work."""
    c = C.draft(29.5, 82.0, "crack", sites=SITES)
    assert c.refused_because is not None
    assert c.letter_en == "" and c.letter_ne == ""
    assert c.office is None
    assert any("wrong office" in x for x in c.caveats)


def test_it_never_claims_to_have_filed_anything():
    """The honest boundary: this drafts. It does not send, sign or receive."""
    c = C.draft(27.7005, 85.3105, "crack", sites=SITES)
    assert any("filed" in x and "receipt" in x for x in c.caveats)
    assert "does not by itself start any legal proceeding" in c.letter_en
    assert "कानुनी कारबाही सुरु गर्दैन" in c.letter_ne


def test_the_default_duty_holder_is_named_as_a_default():
    """The office is the routing key's default for a local road, not a per-parcel determination."""
    c = C.draft(27.7005, 85.3105, "crack", sites=SITES)
    assert any("DEFAULT" in x for x in c.caveats)
    assert any("private" in x or "highway" in x for x in c.caveats)


def test_urgent_changes_the_letter_and_nothing_else():
    calm = C.draft(27.7005, 85.3105, "drain", sites=SITES)
    now = C.draft(27.7005, 85.3105, "drain", sites=SITES, urgent=True)
    assert "URGENT" in now.letter_en and "URGENT" not in calm.letter_en
    assert "अत्यावश्यक" in now.letter_ne
    assert now.office == calm.office, "urgency must not change who is responsible"


def test_an_unknown_category_falls_back_rather_than_failing():
    c = C.draft(27.7005, 85.3105, "meteor", sites=SITES)
    assert c.category == "other"
    assert c.office is not None


def test_every_route_uses_a_response_helper_that_exists():
    """The bug this exists for.

    The complaint module passed all seven of its tests while the HTTP route was dead, because the
    route called `self._json(...)` and the handler only has `self._send(...)`. Every test exercised
    the logic; none went near the wire. A 500 on the only endpoint a citizen would touch is not
    something a unit test of the drafting code can see.

    So this checks the routes call something the class actually defines - which catches a guess at a
    helper name at the moment it is written rather than at the moment it is demonstrated.
    """
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src/pahiro/api.py").read_text(encoding="utf-8")
    defined = set(re.findall(r"def (_[a-z_]+)\(", src))
    called = set(re.findall(r"self\.(_[a-z_]+)\(", src))
    missing = sorted(called - defined)
    assert not missing, (
        f"the API calls helpers it does not define: {missing} - the route would fail at runtime "
        f"while every unit test still passed")
