"""One call, everything about a point - and the honesty of what it cannot answer."""
from pahiro import place


def test_it_answers_with_every_layer_this_app_has():
    d = place.place(27.7047, 85.3146).as_dict()
    assert d["region"]["key"] == "kathmandu"
    assert d["panorama"].endswith("kathmandu.png")
    assert len(d["seasons"]) == 12
    assert d["duty"]["office"] and d["duty"]["legal_basis"]
    assert d["trails"], "the Kathmandu valley has trails and the lookup found none"
    assert "sources" in d and len(d["sources"]) >= 5


def test_it_measures_to_every_vertex_not_to_the_first_one():
    """The bug this exists for.

    Proximity used each trail's OPENING point, so Beni - a town the Annapurna trail network passes
    through - came back with no trails at all, because no trail happens to begin within five
    kilometres of it. A trail 100 m away whose first node is 20 km up the valley was invisible.
    """
    src = (__import__("pathlib").Path(__file__).resolve().parents[1] /
           "src/pahiro/place.py").read_text(encoding="utf-8")
    assert "np.asarray(c, dtype=float)" in src, "proximity is measuring only one vertex again"
    assert '"distance_m": round(d0)' not in src


def test_an_empty_answer_says_why_rather_than_nothing():
    """A gap in the map and 'nobody walks here' are different statements.

    Beni is the gateway to the Dhaulagiri circuit; the Annapurna extract starts at longitude 83.65
    and Beni is at 83.57, a few kilometres outside. Returning an empty list would read as a fact
    about the ground instead of a fact about the data.
    """
    d = place.place(28.35, 83.57).as_dict()
    assert d.get("unresolved"), "an empty result was returned with no explanation"
    joined = " ".join(d["unresolved"])
    assert "gap in the map" in joined
    assert "not proof that nobody walks here" in joined


def test_a_distant_bus_stop_is_not_offered_as_a_bus_option():
    """The bus file covers three regions; elsewhere the nearest stop is in another world."""
    d = place.place(28.35, 83.57).as_dict()
    assert "bus" not in d, "a bus stop 28 km away was reported as the local bus option"
    assert any("another region" in u for u in d["unresolved"])


def test_the_one_place_screen_exists_and_shows_its_gaps():
    """The screen the objective was pointing at, and the part of it that matters most.

    A lookup that hides its gaps reads as complete when it is not. The page must print what it could
    not answer next to what it could, or a user cannot tell "nothing is there" from "we have not
    looked there".
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "web/app/place/page.tsx").read_text(encoding="utf-8")
    assert "/api/v1/place" in src, "the page no longer calls the aggregate endpoint"
    assert "What this could not answer" in src, (
        "the screen dropped the section that says what it does not know")
    assert "No month is labelled good or bad" in src, (
        "the season view must leave the decision with the walker")
    assert "Where each number came from" in src, (
        "every figure on the screen must name its source")
    assert "Kincey" in src, "the peer-reviewed layer must be attributed on screen"
