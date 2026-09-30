"""The peer-reviewed susceptibility layer, and the two bugs that would have shipped with it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web/public/data/susceptibility.json"


def test_it_is_cited_and_licence_clear():
    """It is the first number in this repository that is not ours, so it must say whose it is."""
    d = json.loads(DATA.read_text(encoding="utf-8"))
    assert "Kincey" in d["source"]
    assert "10.5281/zenodo.8307964" in d["source"]
    assert d["licence"] == "CC-BY-4.0"
    assert "not say whether a slope is moving" in d["what_it_is"], (
        "the file must state that susceptibility is not a live measurement")


def test_no_nodata_sentinel_leaked_into_the_range():
    """This raster marks emptiness with the float32 minimum, and isnan does not catch it.

    The first successful run reported a range starting at -3.4e38 and looked like it had worked.
    """
    d = json.loads(DATA.read_text(encoding="utf-8"))
    r = d["range"]
    for k in ("min", "median", "p90", "max"):
        assert abs(r[k]) < 1.0, f"{k} is {r[k]} - that is a nodata sentinel, not a susceptibility"
    assert r["min"] < r["median"] < r["p90"] < r["max"]


def test_most_slopes_matched_and_the_rest_are_counted():
    """534 of 613 fall inside the raster. The 79 that do not are reported, not silently dropped."""
    d = json.loads(DATA.read_text(encoding="utf-8"))
    assert d["sampled"] > 500, f"only {d['sampled']} slopes matched"
    assert d["unmatched"] > 0
    assert d["sampled"] + d["unmatched"] == 613


def test_the_sampler_refuses_when_the_raster_is_absent():
    """It must not write an empty file and call it data."""
    src = (ROOT / "scripts/build_susceptibility.py").read_text(encoding="utf-8")
    assert "REFUSING" in src
    assert "rio_transform" in src, (
        "the CRS transform is gone; the raster is UTM and our coordinates are degrees")
