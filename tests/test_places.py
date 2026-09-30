"""The places map: a join of checkable data, with no prose anywhere in it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "web/public/data/places.geojson"


def _d():
    return json.loads(P.read_text(encoding="utf-8"))


def test_every_field_is_something_a_machine_checked():
    """The two earlier attempts failed for opposite reasons, and this is the answer to both.

    The first asked Overpass and got four of six regions back empty. The second derived everything
    correctly and had no coordinates. This one joins the national gazetteer to our own documented
    slopes, so a place is a row of facts and there is no sentence to be wrong.
    """
    d = _d()
    assert d["counts"]["places"] >= 200
    required = {"name", "district", "population", "area_km2", "website",
                "slopes_documented", "trails_mapped_within_10km", "located_by"}
    for f in d["features"]:
        assert required <= set(f["properties"]), (
            f"{f['properties'].get('name')} is missing {required - set(f['properties'])}")
        lon, lat = f["geometry"]["coordinates"]
        assert 80 < lon < 89 and 26 < lat < 31, "a place landed outside Nepal"


def test_it_states_that_positions_are_not_town_centres():
    """A large rural municipality is tens of kilometres across; a menu point is a label.

    Claiming town-centre accuracy would make every distance measured to these points wrong in a way
    nobody could see, which is the failure this whole project keeps refusing.
    """
    d = _d()
    assert "MEAN OF DOCUMENTED SLOPES" in d["accuracy"]
    assert "not town centres" in d["accuracy"]
    assert "not a location" in d["accuracy"]
    for f in d["features"]:
        assert "not a surveyed town centre" in f["properties"]["located_by"]


def test_it_says_how_much_of_the_country_it_covers():
    """277 of 753 units are located, because 613 slopes cluster where the hazards were documented.

    A map that shows 277 dots and implies 753 would be the same class of error as an empty trail
    list read as 'nobody walks here'.
    """
    d = _d()
    admin = json.loads((ROOT / "web/public/data/administration.json").read_text(encoding="utf-8"))
    located = d["counts"]["places"]
    assert located < admin["counts"]["units"], (
        "if every unit is located, the source of the coordinates has changed - check it")
    assert "753" in d["method"] or "gazetteer" in d["method"]


def test_it_carries_the_nepali_name():
    """An app for Nepal names places in Nepali, not only in the language of the map data."""
    d = _d()
    with_ne = sum(1 for f in d["features"] if f["properties"].get("name_ne"))
    assert with_ne > len(d["features"]) * 0.8, f"only {with_ne} places carry a Nepali name"


def test_it_attributes_both_sources():
    d = _d()
    a = d["attribution"]
    assert "NEPAL-QUEST-DATA" in a
    assert "OpenStreetMap" in a and "ODbL" in a, "the slope and trail data must keep its licence line"


def test_the_builder_refuses_rather_than_writing_a_placeless_map():
    """Carried over from the Overpass attempt, which is now gone but whose lesson is not.

    That builder fetched four of six regions as empty and wrote an Annapurna list as a national
    gazetteer. This one takes its coordinates from documented slopes instead, and the equivalent
    failure would be writing a map with no coordinates at all - so it refuses.
    """
    src = (ROOT / "scripts/build_places.py").read_text(encoding="utf-8")
    assert "REFUSING" in src, "the builder no longer refuses to write an empty map"
    assert "no slope title matched a local unit" in src
