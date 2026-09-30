"""The flood demo: six steps, every one of them calling the real engine."""
from pahiro import demo


def test_every_step_calls_the_engine_rather_than_miming_it():
    """A demo that mimes the product drifts away from it, and then only the demo works.

    So each step's `computed` block must be the real return of a real function. The strongest
    evidence is internal consistency: step 1's threshold count has to equal what the timeline says,
    and step 3's office has to equal what the complaint drafter resolves for the same point.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    tl = json.loads((root / "web/public/data/timeline.json").read_text(encoding="utf-8"))
    days, th, sites = tl["days"], tl["threshold_mm_24h"], tl["sites"]

    d = demo.flood_scenario(28.35, 83.57)
    steps = {s["n"]: s for s in d["steps"]}
    assert sorted(steps) == [1, 2, 3, 4, 5, 6]

    # step 1 must match the timeline it claims to be reading
    i = days.index(demo.EVENT_DAY)
    real = sum(1 for s in sites if s["r"][i] >= th)
    assert steps[1]["computed"]["above_threshold"] == real, (
        "the demo's headline count does not match the data it says it read")

    # step 3 must agree with the complaint drafter about who is responsible
    assert steps[3]["computed"]["office"] == steps[5]["computed"]["routed_to"] or \
        steps[5]["computed"]["refused"], (
        "routing and the complaint drafter disagree about the duty holder for the same point")


def test_the_escape_step_answers_rather_than_failing():
    """The safety-critical step must work, not report a failure the demo then explains away.

    It once did exactly that: an AttributeError on the wrong field name was caught and reported as
    'the elevation grid is not loaded'. The grid was fine. Now a caught failure reports its own
    type and no cause it did not diagnose.
    """
    d = demo.flood_scenario(28.35, 83.57)
    esc = {s["n"]: s for s in d["steps"]}[4]
    assert "error" not in esc["computed"], f"the escape step failed: {esc['computed']}"
    assert esc["computed"]["reachable"] is True
    assert esc["computed"]["compass"] in ("north", "north-east", "east", "south-east",
                                          "south", "south-west", "west", "north-west")


def test_every_step_says_what_it_cannot_know():
    """The demo is the product's honesty on display, so no step is allowed to be only a claim."""
    d = demo.flood_scenario(28.35, 83.57)
    for s in d["steps"]:
        assert s["cannot_know"], f"step {s['n']} states no limit"
        assert s["depends_on"], f"step {s['n']} names no dependency"


def test_the_demo_says_it_is_not_a_simulation():
    d = demo.flood_scenario(28.35, 83.57)
    assert "not a forecast" in d["what_this_demo_is_not"]
    assert "not a synthetic curve" in d["event"]


def test_the_satellite_step_does_not_render_blank_when_its_data_is_missing():
    """Step 2 is the abstention beat - the one that says the system cannot see.

    Its source returned an empty dict on failure, so the step rendered with no numbers and no reason:
    the demo's most characteristic step, silently blank. It now says why.
    """
    import json
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src/pahiro/demo.py").read_text(encoding="utf-8")
    assert 'return {"unavailable": True' in src, (
        "a failed observability load returns an empty dict again, which renders a blank step")

    d = demo.flood_scenario(28.35, 83.57)
    step2 = {s["n"]: s for s in d["steps"]}[2]
    assert step2["computed"], "step 2 rendered with nothing in it"
    if step2["computed"].get("unavailable"):
        assert step2["computed"].get("why"), "a failed step must say why"
