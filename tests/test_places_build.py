"""The places builder: it must refuse a partial country and read the DEM correctly.

This feature is NOT delivered. Two attempts to fetch the six regions from Overpass got two
regions, and the file that came out looked complete - an Annapurna list presented as a national
gazetteer. These tests cover the two defects that were mine rather than the network's, so the script
is correct whenever it is next run.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cache: dict):
    import importlib.util
    spec = importlib.util.spec_from_file_location("bp", ROOT / "scripts/build_places.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_refuses_to_write_when_a_region_came_back_empty(monkeypatch, tmp_path):
    """The first run wrote 207 places from two of six regions and said nothing was wrong."""
    mod = _run({})
    cache = tmp_path / "raw.json"
    cache.write_text(json.dumps({"kathmandu": [{"tags": {"name": "x"}, "lat": 27.7, "lon": 85.3}],
                                 "khumbu": [], "annapurna": [], "langtang": [],
                                 "manaslu": [], "mustang": []}))
    monkeypatch.setattr(mod, "CACHE", str(cache))
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "out.geojson"))
    monkeypatch.setattr(sys, "argv", ["build_places.py"])
    assert mod.main() == 1, "a two-region file was allowed to be written as a national gazetteer"
    assert not (tmp_path / "out.geojson").exists()


def test_elevation_is_read_from_the_dem_flat_keys():
    """terrain.json stores west/south/east/north as flat keys; the first version read meta["bounds"]."""
    meta = json.loads((ROOT / "web/public/data/terrain.json").read_text())
    assert "west" in meta and "south" in meta and "east" in meta and "north" in meta
    assert "bounds" not in meta, (
        "if terrain.json gained a bounds array, the builder's fallback comment is stale")
    src = (ROOT / "scripts/build_places.py").read_text()
    assert 'meta.get("bounds")' not in src, "the builder is reading a key the DEM does not have"


def test_the_count_is_not_called_a_trailhead():
    """207 of 207 places were flagged trailheads, because a 5 km box contains dozens of trails."""
    src = (ROOT / "scripts/build_places.py").read_text()
    assert "is_trailhead" not in src, (
        "the meaningless boolean is back; the count measures OSM coverage, not good walking")
    assert "trails_mapped_within_5km" in src
