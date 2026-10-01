"""Documents must not disagree with the code they describe.

WHY THIS EXISTS
---------------
Three separate stale claims were found in this repository in three rounds, each carried forward as
fact by whoever last wrote it:

  - SUBMISSION.md said the demo video was "pending" for eight rounds after it was finished
  - the speech said the browser client "does not seal" after it did
  - the published README said the repo "currently carries only this description" when it carries
    358 tracked files

None of those was a lie when written. All of them became one because **nothing checked**. A claim
that no test reads is a claim that rots, and in a submission the rot is what a judge finds.

So the claims that matter are pinned to the artifacts they describe. This is not a spell-checker;
it is a small number of specific cross-checks between a document and the code.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---- the speech must not understate or overstate sealing ----------------------------------------

def test_the_speech_matches_whether_the_client_actually_seals():
    """If the client seals, the speech must not say it does not - and vice versa.

    This was wrong for four rounds: the code gained a sealing compose path and the speech kept
    telling the room that the field client posts in the clear. Underselling real work is still
    misdescribing the system.
    """
    speech = read("docs/SPEECH.md")
    html = read("web/public/field/index.html")
    client_seals = "sealForTransport" in html and "buildOutgoing(pending)" in html

    if client_seals:
        for stale in ("does not seal", "still posts in the clear",
                      "the field client posts in the clear"):
            assert stale not in speech, (
                f"the client seals, but the speech still says {stale!r} - a judge would hear an "
                f"understatement of work that exists")
        assert "WebCrypto" in speech or "AES-GCM" in speech, \
            "the speech should name how the browser seals"
    else:
        assert "does not seal" in speech or "in the clear" in speech, \
            "the client does not seal, and the speech must say so"


def test_the_speech_does_not_claim_an_audited_end_to_end_system():
    """The one thing it must never claim, because no cryptographer has looked at it."""
    speech = read("docs/SPEECH.md")
    assert "no cryptographer has reviewed" in speech.lower() or \
           "not been reviewed by a cryptographer" in speech.lower(), \
        "the speech must carry the audit gap wherever it discusses sealing"


# ---- the submission must match whether the film exists ------------------------------------------

def test_the_submission_matches_whether_the_demo_film_exists():
    submission = read("SUBMISSION.md")
    film = ROOT / "reports" / "video" / "pahiro-narrated-web.mp4"
    if film.exists():
        assert "recording pending" not in submission, (
            "the film exists, and SUBMISSION.md still says it is pending")
        assert "recorded" in submission
    else:
        assert "pending" in submission, "no film, and the submission promises one"


# ---- documentation must not describe an empty repository ----------------------------------------

def test_no_document_still_describes_this_as_an_empty_repository():
    """A leftover placeholder README is the most misleading file a judge can open.

    The guard checks the ASSERTING sentence, not the bare phrase. The first version looked for
    "when the code arrives" and failed on the very paragraph that corrects it - a naive
    stale-claim check fires on the honest correction, which is its own kind of false positive.
    """
    asserting = (
        "This repository currently carries only this description",
        "When the code arrives it will be accompanied by",
        "the source, the evaluation harness, the cited routing key and the full\n"
        "documentation land here before the showcase",
    )
    for rel in ("docs/README-published.md", "README.md", "SUBMISSION.md"):
        text = read(rel)
        for stale in asserting:
            assert stale not in text, f"{rel} still asserts {stale!r}, and the code is here"


# ---- the numbers a reader would check -----------------------------------------------------------

def test_the_documented_piper_size_is_the_size_of_the_voice_file():
    """63 MB is stated twice; if the artifact disagrees, the docs are wrong."""
    voice = ROOT / "evidence" / "voices" / "ne_NP-chitwan-medium.onnx"
    if not voice.exists():
        pytest.skip("the voice has not been fetched in this checkout")
    mb = voice.stat().st_size / 1_000_000
    assert 60 <= mb <= 66, f"docs say 63 MB, the file is {mb:.1f} MB"


def test_the_speech_fact_sheet_numbers_are_present_in_the_code_they_cite():
    """Spot-check a few load-bearing constants rather than trusting the prose."""
    from pahiro import endurance as E
    from pahiro.mesh import beacon as B, dtn

    speech = read("docs/SPEECH.md")
    assert f"{B.ENCODED_BYTES} bytes" in speech or f"{B.ENCODED_BYTES}" in speech
    assert str(int(dtn.WIFI_AWARE.range_m)) in speech, "the 300 m Wi-Fi figure must appear"
    assert "25" in speech and E.plan(E.State(battery_pct=20)).scan_duty_cycle == 0.25


# ---- the speech's own timings -------------------------------------------------------------------

def _spoken_words(text: str) -> int:
    """Count only what is actually said: no headings, stage directions, tables or markdown."""
    import re

    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ">", "|", "---")) \
                or s.startswith("**〔") or s.startswith("*Slide"):
            continue
        s = re.sub(r"\*\*|\*|`", "", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        out.append(s)
    return len(" ".join(out).split())


WPM = 140.0     # a normal rehearsed pace; the band is 130-150


def test_the_speechs_stated_duration_matches_its_own_word_count():
    """The stated runtime was 5:40-6:10 and the script was ~10:30.

    A presenter who rehearses to the printed number gets cut off on stage, before the close,
    which is the only part that decides anything. So the number is derived here rather than
    asserted in prose.
    """
    import re

    speech = read("docs/SPEECH.md")
    # the six numbered sections, which is what "the full script" means
    body = speech[speech.index("### 1 · Cold open"):speech.index("## The two-minute cut")]
    words = _spoken_words(body)
    minutes = words / WPM
    stated = re.search(r"The full script is ~(\d+):(\d+)", speech)
    assert stated, "the speech must state a measured duration"
    claimed = int(stated.group(1)) * 60 + int(stated.group(2))
    assert abs(claimed - minutes * 60) <= 45, (
        f"the speech says ~{claimed // 60}:{claimed % 60:02d} and measures "
        f"{int(minutes)}:{int((minutes % 1) * 60):02d} at {WPM:.0f} wpm")


def test_the_named_cuts_are_the_length_they_claim():
    """'The 90-second cut' was 2:04. A label nobody timed is a promise nobody kept."""
    import re

    speech = read("docs/SPEECH.md")
    for heading, claim in (("## The two-minute cut", 120), ("## The 45-second version", 45)):
        start = speech.index(heading)
        nxt = speech.find("\n## ", start + 1)
        body = speech[start:nxt if nxt != -1 else len(speech)]
        words = _spoken_words(body)
        seconds = words / WPM * 60
        assert abs(seconds - claim) <= 30, (
            f"{heading!r} claims {claim}s and measures {seconds:.0f}s "
            f"({words} words at {WPM:.0f} wpm)")


def test_the_speech_never_carries_the_old_wrong_duration_as_an_instruction():
    """It may quote the old number while retracting it; it must not instruct with it."""
    speech = read("docs/SPEECH.md")
    assert "The main script runs **5:40" not in speech
    assert "runs **5:40–6:10**." not in speech


# ---- the speech and the film must not contradict each other on numbers --------------------------

def test_the_speech_the_caption_and_the_narration_agree_on_the_load_bearing_numbers():
    """Three artefacts state the same four numbers. A disagreement is a presenter contradicting
    the screen in front of a room, which is worse than a wrong number nobody sees twice."""
    speech = read("docs/SPEECH.md")
    build = read("scripts/build_voiced_video.sh")
    narration = read("reports/video/voice/narration.txt")

    # (label, in the speech, in the captions, in the Nepali narration)
    for label, in_speech, in_caption, in_narration in (
        ("613 slopes", "613", "613", "छ सय तेह्र"),
        # Was ("305 above threshold", "305", "305", "तीन सय पाँच"). All three agreed on a number
        # that was wrong, so the test ENFORCED it - and after round 43 corrected the caption,
        # the caption assertion still passed because the correction COMMENT in the build script
        # contains the string "305". A guard passing for the wrong reason while enforcing a
        # wrong value, which is the failure this file exists to catch.
        ("31 above threshold on the named day", "31", "31 of 613", "एकतीस"),
        ("167 landslides", "167", "167", "एक सय सतसट्ठी"),
        ("27.8% clear", "27.8", "27.8", "सत्ताईस दशमलव आठ"),
    ):
        assert in_speech in speech, f"the speech does not state {label}"
        assert in_caption in build, f"the film captions do not state {label}"
        assert in_narration in narration, f"the narration does not speak {label}"


# ---- the live beats the speech tells the presenter to press must exist --------------------------

def test_every_beat_the_speech_tells_the_presenter_to_press_actually_exists():
    """The speech instructs the presenter to press numbered beats live.

    If a beat does not exist the demo fails on stage, in front of judges, with no recovery - so
    the beat titles in the speech are checked against the array the app actually renders.
    """
    import re

    speech = read("docs/SPEECH.md")
    page = read("web/app/page.tsx")

    titles = re.findall(r'\{ title: "([^"]+)"', page)
    assert titles, "no beats found in web/app/page.tsx"

    live = speech[speech.index("## Running it live"):]
    # The heading is now "The seven that..." - it named three when there were seven. Matched on
    # the part that does not move, so a future count change does not break the slice.
    live = live[:live.index("that make people put their phones down") - 3]

    # every beat title the app defines should be referenced by the speech
    for title in titles:
        number = title.split("·")[0].strip()
        assert number in live, (
            f"the app defines beat {number!r} and the speech never tells the presenter to press it")

    # and the speech must not name a beat number the app does not have.
    # Matched as "**N** ·" - the beat-press form. A bare bolded number is not a beat: the speech
    # also says "**0** above threshold", and the first version of this check read that as beat 0.
    pressed = set(re.findall(r"\*\*(\d+b?)\*\* ·", live))
    defined = {t.split("·")[0].strip() for t in titles}
    assert pressed <= defined, f"the speech presses {sorted(pressed - defined)}, which do not exist"

    # The count it states must be the count there is. Accept the numeral OR the word, because
    # the speech says "nine beats" and prose is allowed to spell a number - the first version of
    # this check demanded "9 beats" and failed on a sentence that was correct.
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
             8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
    n = len(titles)
    assert f"{n} beats" in speech or f"{words.get(n, n)} beats" in speech, (
        f"the speech does not say there are {n} beats")


def test_the_presenter_mode_the_speech_tells_you_to_open_works():
    """`?present=1` is an instruction. If nothing reads that parameter it is a dead instruction."""
    presenter = read("web/components/Presenter.tsx")
    assert 'get("present")' in presenter, "nothing reads ?present"
    assert '"1"' in presenter, "?present is read but not compared to 1"
    assert "arrow" in presenter.lower() or "ArrowRight" in presenter, \
        "the speech promises arrow keys and none are handled"


# ---- the setup instruction exists in three places and must not drift ---------------------------

def test_every_copy_of_the_install_command_asks_for_the_same_extras():
    """The install line appears in SUBMISSION.md, README.md and scripts/demo.sh.

    It omitted the `crypto` extra in all three, so the sealing layer skipped on every fresh
    clone while the suite reported success. Fixing one copy is what let the other two survive:
    a duplicated instruction is a claim that can drift, and this one had.
    """
    import re

    files = ("SUBMISSION.md", "README.md", "scripts/demo.sh")
    found: dict[str, set[str]] = {}
    for rel in files:
        text = read(rel)
        for extras in re.findall(r"-e '\.\[([a-z,]+)\]'", text):
            found.setdefault(rel, set()).update(extras.split(","))

    assert found, "no install command found anywhere - did the wording change?"
    reference = found.get("SUBMISSION.md")
    assert reference, "SUBMISSION.md must carry the install command"
    for rel, extras in found.items():
        assert extras == reference, (
            f"the install line in {rel} asks for {sorted(extras)} and SUBMISSION.md asks for "
            f"{sorted(reference)} - a fresh clone would install a different environment "
            f"depending on which file you read")
    assert "crypto" in reference, (
        "the install command omits the crypto extra, so the sealing layer skips silently "
        "on a fresh clone")


# ---- the trails layer must be reachable, not just written ---------------------------------------

def test_the_trail_layer_is_wired_into_the_map_and_the_bundle_ships():
    """A layer the map never adds is decoration in a source file.

    The trail engine is tested in tests/test_trails.py and the data is committed; this checks the
    other half - that the app actually draws it, that there is a way to turn it on, and that the
    licence notice travels with it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    map_src = read("web/components/SlopeMap.tsx")
    page = read("web/app/page.tsx")

    assert 'addSource("trails"' in map_src, "the map never adds a trails source"
    assert 'id: "trails"' in map_src, "no trails layer is added"
    assert "/data/trails.geojson" in map_src, "the layer is never populated from the bundle"
    assert 'visibility' in map_src, "there is no way to hide the trails again"

    assert "trails" in page and "setTrails" in page, "the page has no trails control"
    assert "OpenStreetMap" in page, (
        "ODbL requires attribution wherever the data is shown; the UI must carry it")
    assert "ODbL" in page

    bundle = root / "web/public/data/trails.geojson"
    assert bundle.exists(), "the trail bundle is not in the repository"
    import json

    d = json.loads(bundle.read_text(encoding="utf-8"))
    assert "OpenStreetMap" in d["attribution"], "attribution must travel in the data too"
    assert len(d["features"]) > 1000


# ---- the offline cache must list files that exist ------------------------------------------------

def test_every_file_the_service_worker_precaches_actually_exists():
    """`addAll` is atomic: one bad path caches NOTHING, and it was wrapped in a bare catch, so a
    single renamed file produced a silent, empty offline cache that looked fine until the app was
    used with the radio off.

    This is the check that makes the offline claim true rather than stated. It compares the
    worker's list against the files on disk.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sw = read("web/public/sw.js")
    listed = set(re.findall(r'"(/data/[^"]+|/icons/[^"]+|/manifest\.webmanifest)"', sw))
    assert listed, "no precache paths found in the service worker"

    missing = [u for u in sorted(listed) if not (root / "web" / "public" / u.lstrip("/")).exists()]
    assert not missing, (
        f"the service worker precaches paths that do not exist: {missing}. "
        f"With addAll one missing file caches nothing at all.")

    # And the data the app actually reads must be in the list, not merely cacheable on use.
    for required in ("/data/trails.geojson", "/data/terrain.bin", "/data/timeline.json",
                     "/data/advisories.json", "/data/bus-parks.geojson"):
        assert required in listed, (
            f"{required} is not precached, so a browser that goes offline before opening that "
            f"view will not have it")


def test_the_service_worker_does_not_answer_a_binary_file_with_json():
    """The /data/ miss path returned '{}' with a JSON content-type for every path, including
    terrain.bin - a binary grid. A caller reading it as terrain got a two-byte object."""
    sw = read("web/public/sw.js")
    assert 'endsWith(".json")' in sw and 'endsWith(".geojson")' in sw, (
        "the fallback must distinguish JSON from binary before inventing an empty object")


# ---- the "plan a walk" panel must reach the endpoint that exists ---------------------------------

def test_the_plan_panel_calls_the_endpoint_the_api_actually_serves():
    """The UI and the API are in different languages and different directories, so nothing but a
    test stops them drifting apart. The panel compiles perfectly while calling a URL that 404s."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    page = read("web/app/page.tsx")
    api = read("src/pahiro/api.py")

    # the API must serve it
    assert 'path == "/api/v1/plan"' in api, "the API does not serve /api/v1/plan"

    # the panel must call the same path
    assert "/api/v1/plan?" in page, "the panel never calls the plan endpoint"

    # and it must read the fields the endpoint returns, not invented ones
    for field in ("understood", "understood_by", "options", "caveats"):
        assert f"planOut.{field}" in page or f"{field}" in page, (
            f"the panel does not use {field!r} from the response")

    # the bus is the point of the feature: the panel must show the stop and the fare
    assert "o.bus.stop" in page and "o.bus.fare_rs" in page, \
        "the panel does not show how to get there or what it costs"

    # and it must tell the user what to do when the API is not running rather than failing silently
    assert "planErr" in page and "demo.sh" in page, \
        "a failed request must explain how to start the planner"


def test_the_plan_panel_says_whether_a_model_answered():
    """Different qualities of answer. The UI is where that distinction reaches a person."""
    page = read("web/app/page.tsx")
    assert "understood_by" in page
    assert "keyword" in page, "the UI must handle the no-model case, not only the model case"


def test_the_submission_describes_both_halves_of_the_project():
    """The brief makes documentation a gating item: "without a public repo, a working demo, and
    documentation, there's nothing for judges to evaluate".

    SUBMISSION.md described only the disaster half for seven rounds after the daily-use half was
    built. A judge reading the submission document would not have known it existed.
    """
    sub = read("SUBMISSION.md")
    lowered = sub.lower()
    for needed in ("trail", "hiking", "trip", "walk", "bus"):
        assert needed in lowered, f"SUBMISSION.md never mentions {needed!r}"
    for module in ("trails.py", "access.py", "trip_agent.py", "/api/v1/plan"):
        assert module in sub, f"the submission does not point at {module}"

    # and the same honesty rules must apply to the new half as to the old
    for caveat in ("OpenStreetMap", "1.2 km", "schedules", "never run on a phone"):
        assert caveat.lower() in lowered, f"the daily-use section omits the caveat {caveat!r}"


def test_the_speech_headline_count_matches_the_number_of_beats_it_has():
    """The section heading said "the three that make people put their phones down" and there were
    seven. A count in a heading is a claim, and this project has already shipped four stale ones.
    """
    import re

    speech = read("docs/SPEECH.md")
    beats = re.findall(r"^### (N\d+) ·", speech, re.M)
    assert beats, "no beats found in the speech"
    assert len(set(beats)) == len(beats), f"duplicate beat ids: {beats}"

    m = re.search(r"## The (\w+) that make people put their phones down", speech)
    assert m, "the beats section heading changed shape; this test needs updating with it"
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10}
    claimed = words.get(m.group(1).lower())
    assert claimed is not None, f"unrecognised number word {m.group(1)!r}"
    assert claimed == len(beats), (
        f"the heading claims {claimed} beats and the speech has {len(beats)}: {beats}")


def test_the_speech_covers_the_daily_use_half_as_well_as_the_disaster_half():
    """The pitch described only the disaster half for eleven rounds after the daily-use half was
    built. A judge who hears only about landslides has no reason to think anyone would install it.
    """
    speech = read("docs/SPEECH.md").lower()
    assert "23,726" in speech or "23726" in speech, "the pitch never gives the trail network"
    assert "walk" in speech
    assert "bus" in speech, "the pitch never mentions how you get there"
    assert "dotm" in speech or "transport management" in speech, \
        "the fare is a sourced figure and the pitch should say where it comes from"
    assert "clear saturday" in speech, (
        "the pitch must give the ADOPTION argument for the daily half - a tool nobody opens is a "
        "tool nobody has installed when it is needed")


def test_the_readme_describes_both_halves_too():
    """The README is the first page a judge opens. It described only the disaster half - the same
    gap SUBMISSION.md had - so the daily-use work was invisible from the front door.
    """
    low = read("README.md").lower()
    for needed in ("hiking trail", "bus", "23,726", "openstreetmap"):
        assert needed in low, f"README.md never mentions {needed!r}"
    assert "clear saturday" in low, (
        "the README should carry the adoption argument, not just the feature list")
    assert "incomplete" in low, "and the OSM coverage caveat with it"


# ---- the two halves must ship the same trail data, checked without Flutter ----------------------

def test_the_phone_and_the_browser_ship_byte_identical_trail_data():
    """The Dart test asserts this too, but that needs Flutter installed.

    A judge running the Python suite - which is the documented first step - should be able to check
    the one claim that keeps the two halves honest: that the phone and the browser cannot disagree
    about where a path goes.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    web = (root / "web" / "public" / "data" / "trails.geojson").read_bytes()
    mobile = (root / "mobile" / "assets" / "trails.geojson").read_bytes()
    assert web == mobile, (
        "the browser and the phone ship different trail data - they would disagree about where a "
        "path goes and nobody would find out until a walker did")
    assert len(web) > 500_000, f"the trail bundle is only {len(web)} bytes; is it the real one?"


def test_the_daily_use_modules_are_required_by_the_readiness_check():
    """verify_repo.py listed only the disaster-half files, so a clone that had lost trails.py,
    access.py or the trail bundle still reported OK."""
    check = read("scripts/verify_repo.py")
    for needed in ("src/pahiro/trails.py", "src/pahiro/access.py",
                   "web/public/data/trails.geojson"):
        assert needed in check, f"verify_repo.py does not require {needed}"


def test_the_build_writes_both_copies_of_the_trail_bundle():
    """The phone asset used to be a hand-run `cp` of the web bundle.

    The round that forgot it shipped a browser and a phone with different trail data - caught by a
    byte-identity test, caused by a manual step that had to be remembered. A copy a person has to
    remember is a copy that will eventually be forgotten, so the builder writes both.
    """
    builder = read("scripts/build_trails.py")
    assert "mobile/assets/trails.geojson" in builder, \
        "the builder no longer writes the phone copy, so it is a manual step again"


def test_every_data_file_is_named_in_the_provenance_page():
    """A dataset with no recipe is an artefact somebody made once.

    bus-parks.geojson was exactly that until round 27, and three more files still are. The page
    exists so a reader can tell which files they can rebuild and which rest on a pipeline that was
    not kept - the second kind is a gap, and it should be visible rather than discovered.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data_dir = root / "web" / "public" / "data"
    provenance = (data_dir / "README.md").read_text(encoding="utf-8")

    # Every backticked token in the page is a filename or a pattern ("slopes-chirps-*.geojson"
    # is one row for three files, which is the right way to write it). A file is covered when a
    # token matches it - literally or as a glob.
    import fnmatch
    import re

    tokens = re.findall(r"`([^`]+)`", provenance)
    for f in sorted(data_dir.iterdir()):
        if not f.is_file() or f.name == "README.md":
            continue
        assert any(fnmatch.fnmatch(f.name, tok) for tok in tokens), (
            f"{f.name} ships with the app and is not named in the provenance page, so a reader "
            f"cannot tell whether it can be rebuilt")

    # Whatever CANNOT be rebuilt must SAY so rather than being quietly listed. The list changes as
    # gaps get closed - the observability pair was on it for two rounds and no longer is - so this
    # asserts the property rather than a count.
    # Every file now has a recipe, so the earlier "no committed generator" assertion is the
    # opposite of the truth. The property that holds is: each file's row names how it is made.
    assert "Produced by" in provenance
    assert "terrain-texture.jpg" in provenance, "the backdrop must be named"
    assert "reconstructed" in provenance, (
        "the texture's palette is a reconstruction and the page must say so rather than implying "
        "the served file can be reproduced exactly")
    for closed in ("observability-sites.json", "observability-by-month.json"):
        assert closed in provenance
    assert "build_observability.py" in provenance, (
        "the observability files are reproducible now and the page must say by what")


def test_the_observability_layer_can_be_rebuilt_and_refuses_to_write_a_bad_one():
    """It was listed as unreproducible for two rounds.

    The app serves two files derived from the evaluation report, and the derivation was lost - beat
    5b of the demo rests on them. scripts/build_observability.py reproduces both, and the first
    version of it did NOT: it filtered to 2024 and produced 37 months instead of 5, with August and
    September percentages that would have silently replaced the figures the demo turns on.
    """
    src = read("scripts/build_observability.py")
    assert "reports/observability-monsoon.json" in src, "the source report is not named"
    assert "EXPECTED_SCENES = 2021" in src, "the guard on the season total is gone"
    assert "REFUSING TO WRITE" in src, (
        "the script must refuse to overwrite the demo's figures when its aggregation disagrees "
        "with them, rather than writing a plausible wrong answer")

    # and the served files must still carry the two figures the pitch quotes
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    month = json.loads((root / "web/public/data/observability-by-month.json").read_text())
    assert month["scenes"] == 2021
    assert month["months"]["08"]["pct"] == 16.8, "August is a quoted figure"
    assert month["months"]["09"]["pct"] == 27.8, "September is a quoted figure"
    sites = json.loads((root / "web/public/data/observability-sites.json").read_text())
    assert len(sites["sites"]) == 142
    assert sum(1 for s in sites["sites"] if s["usable"] == 0) == 17, \
        "17 of 142 sites were never seen; that is the beat 5b number"


def test_the_phone_app_declares_every_asset_its_offline_claim_needs():
    """The APK carries its data because pubspec lists it. Verified against a real build: the
    48.5 MB release APK contains terrain.bin, terrain.json and the 5.42 MB trail bundle.

    A test cannot inspect the APK - it is generated and gitignored - so this checks the mechanism
    that puts them there. Without these three lines under `assets:` the app builds, installs, and
    needs the network for everything it claims to do offline.
    """
    pubspec = read("mobile/pubspec.yaml")
    assert "assets:" in pubspec
    for needed in ("assets/terrain.bin", "assets/terrain.json", "assets/trails.geojson",
                   "assets/seasons.json"):
        assert f"- {needed}" in pubspec, (
            f"{needed} is not declared under assets:, so it will not be bundled into the APK - the "
            f"app would install and then need the network")


def test_the_video_caption_states_the_bundle_it_actually_shows():
    """The regression. The trails beat's caption was hardcoded at 20,176 trails across four
    regions in 4.5 MB, and the still beside it computed its own count from the data.

    So when Manaslu and Mustang were added the IMAGE updated and the CAPTION did not: a required
    submission deliverable telling the room a number that had been true three rounds earlier. The
    narration said "twenty thousand" in Nepali for the same reason.

    A number written next to a number that is computed will drift. This compares them.
    """
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "web/public/data/trails.geojson").read_text(encoding="utf-8"))
    n = len(data["features"])
    regions = len({f["properties"].get("r") for f in data["features"]})
    mb = (root / "web/public/data/trails.geojson").stat().st_size / 1_048_576

    build = read("scripts/build_voiced_video.sh")
    cap = re.search(r'cap co "([^"]*)"', build)
    assert cap, "the trails caption is gone from the video build"
    text = cap.group(1)

    assert f"{n:,}" in text, f"the caption does not state the real trail count ({n:,}): {text!r}"
    assert str(regions) in text, f"the caption does not state the real region count ({regions})"
    assert f"{mb:.1f}" in text, f"the caption does not state the real bundle size ({mb:.1f} MB)"

    # and the Nepali narration must not understate it either
    narration = read("reports/video/voice/narration.txt")
    line = [l for l in narration.splitlines() if l.startswith("o|")]
    assert line, "the trails narration line is gone"
    assert "तेईस हजार" in line[0], (
        "the narration says twenty thousand; the bundle is twenty-three thousand")


def test_the_map_panel_states_the_bundle_it_actually_loads():
    """The map's trails note hardcoded "20,176 ways, 124,202 points, 4.5 MB" and "Kathmandu valley"
    while the layer underneath loads whatever the bundle holds.

    Two rounds after regions were added, the label still described the old one - four regions and a
    count from before Manaslu and Mustang. A sentence about a number that is loaded, written by
    hand, drifts; this compares them.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "web/public/data/trails.geojson").read_text(encoding="utf-8"))
    n = len(data["features"])
    regions = len({f["properties"].get("r") for f in data["features"]})

    page = read("web/app/page.tsx")
    trail_area = page[page.index("hiking trails"):page.index("hiking trails") + 2200]

    assert f"{n:,}" in trail_area, (
        f"the map panel does not state the real trail count ({n:,})")
    assert "Kathmandu valley" not in trail_area, (
        "the panel describes the coverage as the Kathmandu valley; it is several regions")
    assert str(regions) in trail_area or "regions of Nepal" in trail_area, (
        f"the panel should say how many regions ({regions}) the bundle covers")


def test_the_bundle_describes_its_coverage_in_words_not_coordinates():
    """The bundle's `regions` field is metadata a reader or the app can show.

    When `--fetch` was added, the region bbox went into that list by mistake, so the data described
    its own coverage as six coordinate strings - '"27.70,85.22,27.84,85.42"' - which tells nobody
    anything. It is the kind of field no test reads and no screen displays, which is exactly why it
    can be wrong for fifteen rounds without anybody noticing.
    """
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "web/public/data/trails.geojson").read_text(encoding="utf-8"))

    regions = data.get("regions")
    assert isinstance(regions, list) and len(regions) >= 6, \
        f"the bundle should name the regions it covers; got {regions!r}"

    for r in regions:
        assert not re.fullmatch(r"[\d.,\- ]+", r), (
            f"region {r!r} is a bounding box, not a place - the builder is writing the wrong "
            f"field into the human-readable list")
        assert any(c.isalpha() for c in r), f"region {r!r} has no words in it"

    # and the phone must read the key that exists
    dart = read("mobile/lib/trails.dart")
    assert "data['regions']" in dart, (
        "the phone reads `region` (singular), which the bundle stopped emitting - it would parse "
        "to an empty string forever and nothing would notice, because the field is never shown")


def test_the_sixty_second_summary_quotes_numbers_that_are_in_the_reports():
    """The first section of SUBMISSION.md is the only part a judge with ten projects is certain to
    read, so its figures are the most load-bearing in the repository.

    They were checked by hand against the reports, and this makes that permanent: each number the
    summary quotes must appear in the report it comes from. A summary is exactly the kind of
    document that gets edited for rhythm and quietly loses a digit.
    """
    sub = read("SUBMISSION.md")
    summary = sub[sub.index("## If you have sixty seconds"):sub.index("## The five required items")]

    ablation = read("reports/routing-ablation.md")
    evals = read("reports/eval-v1.md")

    # routing accuracy, which the summary calls its weak axis
    for figure in ("52.4%", "61.9%", "76.2%"):
        assert figure in summary, f"the summary no longer quotes {figure}"
        assert figure in ablation, (
            f"the summary quotes {figure} and reports/routing-ablation.md does not contain it")

    # the negative result
    for figure in ("53rd", "55th"):
        assert figure in summary, f"the summary no longer quotes {figure}"
        assert figure in evals, (
            f"the summary quotes {figure} and reports/eval-v1.md does not contain it")

    # and the honesty section must be there, not only the achievements
    assert "does NOT claim" in summary
    for caveat in ("physical handset", "52.4%", "cryptographer"):
        assert caveat in summary, f"the summary dropped the caveat {caveat!r}"

    # The disclosure changed on 2026-10-01: the release APK was installed and run on an Android
    # emulator. "Nothing has run on a real handset" was true for fifty rounds and is now too strong,
    # so the summary has to carry the NARROWER claim instead of either overstating or hiding it.
    assert "emulator" in summary, (
        "the summary no longer mentions that the app runs on an emulator")
    assert "cannot measure a radio" in summary, (
        "the emulator result must not be allowed to imply the radios were verified")


def test_the_presenter_quotes_the_day_counts_the_timeline_holds():
    """The presenter beat said "305 of 613 slopes above the rainfall threshold on one day".

    Checked against the timeline: no day in the 2024 monsoon reaches 305. The peak is 149 of 613,
    and the day the beat names - 28 September, the day Nepal recorded 167 landslides - has 31. The
    305th-largest rainfall that day is 38.6 mm against a 118.8 mm threshold.

    It was the one number left in the repository that a judge could check in ten seconds and find
    wrong, and it was in the beat the presenter is told to say out loud.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    tl = json.loads((root / "web/public/data/timeline.json").read_text(encoding="utf-8"))
    days, th, sites = tl["days"], tl["threshold_mm_24h"], tl["sites"]
    counts = {d: sum(1 for s in sites if s["r"][i] >= th) for i, d in enumerate(days)}

    named = counts["2024-09-28"]
    peak = max(counts.values())

    page = read("web/app/page.tsx")
    beat = page[page.index("4 Â· The day") if "4 Â· The day" in page else page.index("The day \u2014 28 September"):]
    beat = beat[:700]

    assert "305" not in beat, (
        "the presenter still claims 305 slopes; no day in the monsoon reaches it")
    assert str(named) in beat, f"the beat should state the real count for 28 September ({named})"
    assert str(peak) in beat, f"the beat should state the real season peak ({peak})"


def test_the_season_guide_says_which_months_it_stands_behind():
    """A twelve-month climate guide built from ERA5 in the Himalaya is mostly extrapolation.

    The cross-check against this repository's own CHIRPS measurement covers June to September. It
    flags Kathmandu as unreliable (ERA5 nearly twice the measured monsoon), and it PASSES Manaslu -
    which is why the flag has to be per month and not per region: Manaslu passes the monsoon test
    while ERA5 gives it 8,228 mm a year and calls April its wettest month, and both are wrong.

    A guide that reported twelve confident months from that model would tell a walker something
    precise and false, which is the failure this project spends its whole length avoiding.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    d = json.loads((root / "web/public/data/seasons.json").read_text(encoding="utf-8"))

    assert len(d["regions"]) == 6
    validated = unreliable = 0
    for r in d["regions"]:
        assert "validation" in r, f"{r['name']} carries no cross-check"
        assert "reliable" in r["validation"]
        if r["validation"]["reliable"]:
            validated += 1
        else:
            unreliable += 1
        months = r["months"]
        assert len(months) == 12
        assert sum(1 for m in months if m.get("validated")) == 4, (
            f"{r['name']} should mark exactly the four months that were cross-checked")
        assert "annual_note" in r

    # Kathmandu is the one the measurement disagrees with; if that ever flips, look again rather
    # than assuming the check is broken.
    kathmandu = next(r for r in d["regions"] if r["key"] == "kathmandu")
    assert kathmandu["validation"]["reliable"] is False, (
        "ERA5 was nearly twice the measured monsoon for Kathmandu; if that changed, re-check")
    assert unreliable >= 1

    # and the file must not claim to be a forecast
    assert "not a forecast" in d["method"]


def test_the_phone_and_the_browser_ship_the_same_season_guide():
    """The season file exists twice, like the trail bundle, and a copy will drift.

    It is generated by scripts/build_seasons.py into web/public/data and hand-copied into the phone
    assets. That is exactly the manual step that shipped a browser and a phone with different trail
    data in round 26, so it is compared rather than trusted.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    web = (root / "web/public/data/seasons.json").read_bytes()
    phone = (root / "mobile/assets/seasons.json").read_bytes()
    assert web == phone, (
        "the web and phone season guides differ - the phone copy is a manual step and it was missed")


def test_the_submission_describes_every_thing_that_exists():
    """The regression, found by grepping the documents after a whole objective of building.

    None of the features added in that stretch were mentioned anywhere a judge reads: panorama 0,
    season 0, complaint 0, demo 0. The submission had been accurate when written and had never been
    revisited - which is the failure this file has caught six times, and the seventh was the worst
    because it was the whole product description rather than one number.
    """
    sub = read("SUBMISSION.md")
    required = {
        "panorama": "the 360 view",
        "season": "when to go",
        "complaint": "the complaint portal",
        "place": "the major-places layer",
        "flood": "the flood scenario",
        "offline": "the offline claim",
    }
    for term, label in required.items():
        assert term in sub.lower(), (
            f"the submission does not mention {label} ({term!r}), so a judge reading it would not "
            f"know the feature exists")

    # and it must point at the device evidence, which is the strongest thing in the repository
    assert "reports/device" in sub, "the submission does not link the on-device frames"


def test_the_submission_states_the_honesty_rather_than_only_the_features():
    """The distinguishing claim. A submission listing features without the abstentions would be an
    accurate description of a different product."""
    sub = read("SUBMISSION.md")
    for claim in ("unvalidated", "not proof that nobody walks here", "nothing is here"):
        assert claim in sub, f"the submission dropped its own honesty: {claim!r}"


def test_the_readme_names_every_feature_by_the_word_a_reader_would_search_for():
    """A feature described but not named is a feature nobody finds.

    The README listed the season guide as "when to go" and the panorama as "a 360-degree render",
    which reads well and means that searching the front page for "panorama" or "season" returns
    nothing. The words matter as much as the description.
    """
    readme = read("README.md")
    for term in ("panorama", "season", "complaint", "places", "flood", "offline"):
        assert term in readme.lower(), (
            f"the README does not contain {term!r} - a reader searching the front page for it "
            f"would conclude the feature does not exist")
    assert "reports/device" in readme, "the README does not link the on-device frames"


def test_the_speech_names_the_four_things_a_judge_will_ask_about():
    """The same defect as the README, in the third document, one round later.

    The speech went seven rounds of building without mentioning the panorama or the complaint portal,
    and when the insert was written for them it described the panorama as "a 360-degree render" and
    never used the word - so searching the speech for "panorama" returned nothing, again, immediately
    after adding a guard that requires exactly that of the README.

    Describing something and naming it are different acts. Only one of them is findable, and a
    presenter searching their own notes for a feature is the same reader as a judge.
    """
    speech = read("docs/SPEECH.md")
    for term in ("panorama", "complaint", "season", "places"):
        assert term in speech.lower(), (
            f"the speech does not contain {term!r}, so a presenter looking for it would not find it")

    # the insert must not silently join the timed script
    assert "Not part of the timed script" in speech, (
        "the optional insert no longer says it is outside the timed script, so the cut table's "
        "numbers may now be wrong")


def test_the_submission_states_what_the_video_does_not_cover():
    """The film is a required submission item and it predates this objective's features.

    A judge watching 2:36 of Nepali narration would see the disaster half and the trip planner, and
    would not see the panorama, the season guide, the complaint portal or the places layer. Saying so
    is better than leaving a reader to notice the omission and wonder what else is missing.
    """
    sub = read("SUBMISSION.md")
    assert "does not show the season guide" in sub, (
        "the submission no longer states what the video omits")
    assert "older than the product it describes" in sub
    assert "reports/device" in sub


def test_the_film_caption_states_the_counts_the_timeline_holds():
    """The 305 that was fixed in the presenter cue and left in the film.

    Round 50 proved against the timeline that no day in the 2024 monsoon has 305 slopes above the
    threshold: the peak is 149 and the named day, 28 September, has 31. The presenter cue in
    web/app/page.tsx was corrected. The caption burned into the required video was not, and it said
    305 for seven more rounds - in the artefact a judge actually watches.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    tl = json.loads((root / "web/public/data/timeline.json").read_text(encoding="utf-8"))
    days, th, sites = tl["days"], tl["threshold_mm_24h"], tl["sites"]
    counts = {d: sum(1 for s in sites if s["r"][i] >= th) for i, d in enumerate(days)}
    named, peak = counts["2024-09-28"], max(counts.values())

    build = read("scripts/build_voiced_video.sh")
    caption = [l for l in build.splitlines() if l.startswith("cap cd ")][0]

    assert "305" not in caption, (
        "the film caption claims 305 slopes; no day in the monsoon reaches it")
    assert str(named) in caption, f"the film caption should state the real count for that day ({named})"
    assert str(peak) in caption, f"the film caption should state the season peak ({peak})"


def test_every_stated_slope_count_matches_the_timeline():
    """The class-level guard, after fixing the same number in four separate artefacts.

    Round 50 corrected the presenter cue. Round 43 found the film caption. This round found the demo
    script, the speech's running-live table, the share page and a superseded build script - six
    places, one number, and each guard I wrote was scoped to the instance in front of it.

    So this does not check a file. It scans every source artefact for the PATTERN "N of 613" and
    requires every N to be a value the timeline actually contains.
    """
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    tl = json.loads((root / "web/public/data/timeline.json").read_text(encoding="utf-8"))
    days, th, sites = tl["days"], tl["threshold_mm_24h"], tl["sites"]
    real = {sum(1 for s in sites if s["r"][i] >= th) for i in range(len(days))}

    exts = (".md", ".py", ".tsx", ".sh", ".dart")
    skip = ("node_modules", "/.git/", "/out/", "/.next/", "__pycache__",
            "/evidence/", "tests/test_doc_claims.py")
    found, bad = 0, []
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix not in exts:
            continue
        sp = str(f)
        if any(x in sp for x in skip):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:                                     # noqa: BLE001
            continue
        # SCOPED, because a bare "N of 613" is not one measure. The first version of this sweep
        # flagged "119 of 613" (slopes with no matchable local unit) and "534 of 613" (slopes with a
        # susceptibility sample) - both correct, both counting the same 613 slopes, neither a claim
        # about rainfall. A guard that cannot say what it is guarding is the defect this session has
        # found five times, and this was the sixth, written by me while fixing it.
        for line in text.splitlines():
            if "threshold" not in line.lower() and "above the rainfall" not in line.lower():
                continue
            for m in re.finditer(r"(\d[\d,]*)\s+of\s+613", line):
                n = int(m.group(1).replace(",", ""))
                found += 1
                if n not in real:
                    bad.append(f"{f.relative_to(root)}: {n} of 613  ({line.strip()[:70]})")

    assert found >= 4, f"the sweep only found {found} counts, so it is not scanning"
    assert not bad, (
        "these state a slope count the timeline does not contain:\n  " + "\n  ".join(bad))


def test_every_headline_count_is_derived_from_its_data_not_remembered():
    """The generalisation, after the same wrong number turned up in six artefacts.

    Last round's guard scanned for "N of 613". This one does not scan for a number at all: it
    DERIVES each headline figure from the file it comes from and requires the reader-facing documents
    to state it. That is the difference between checking an instance and checking the class.

    Found by sweeping: everything agreed this time. The point is that it is now checked rather than
    re-derived by hand each round it occurs to somebody.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    D = root / "web/public/data"

    def n(path, key=None):
        d = json.loads((D / path).read_text(encoding="utf-8"))
        if key:
            for k in key.split("."):
                d = d[k]
            return d
        return len(d["features"])

    headline = {
        "23,726": n("trails.geojson"),                       # 4 regions of Nepal
        "335": n("bus-parks.geojson"),
        "534": n("susceptibility.json", "sampled"),
        "494": n("complaint-index.json", "counts.resolved"),
        "277": n("places.geojson", "counts.places"),
        "753": n("administration.json", "counts.units"),
        "77": n("administration.json", "counts.districts"),
    }
    assert headline["23,726"] == 23726, "the trail count moved; update every document that states it"

    for doc in ("README.md", "SUBMISSION.md"):
        text = read(doc)
        for shown, value in headline.items():
            expected = f"{value:,}" if "," in shown else str(value)
            assert expected in text, (
                f"{doc} does not state {expected}, which is what {shown} is derived as now")


def test_the_readmes_measured_numbers_trace_to_a_report():
    """The same rule as the summary, applied to the front page's own measurement section.

    Everything the README states as measured - 0.0% in July, 90.4% of days, the 34-day silence, the
    +58 points from radar, and the 7,081 BIPAD rows - has to exist in a report, because a front page
    is where a reviewer looks first and where an unsourced number does the most damage.
    """
    readme = read("README.md")

    # the ones that come from the evaluation
    ev = read("reports/eval-v1.md") + read("reports/eval-v0.md")
    # The README writes "34-day silence" and the report writes "34 days" - the same fact hyphenated
    # two ways. Asserting one spelling in both documents is the narrow-pattern mistake this file has
    # now made four times; the check is on the NUMBER.
    assert "90.4" in readme and "90.4" in ev
    assert "34" in readme and "34 days" in ev, "the 34-day silence must trace to the evaluation"
    assert "34-day" in readme or "34 day" in readme, "the README no longer states the silence"

    # and the one that comes from the reporting-chain research, not from us
    chain = read("docs/research/nepal-slope-reporting-chain.md")
    assert "7,081" in readme and "7,081" in chain, (
        "the BIPAD figure must trace to the research that measured it")

    # that research states its own caveat, and the caveat must survive
    assert "count" in chain and "broken" in chain, (
        "the pagination caveat on the 7,081 figure is gone from the research document")


def test_the_speech_timing_claim_still_matches_the_speech():
    """A presenter reads "10:48" and plans the room around it.

    The table states 1,455 words across the six sections at 140 words per minute. Counting the spoken
    text - headings, stage directions and 〔beat〕 markers excluded - gives 1,466, so the claim is
    right to within a percent and belongs to whoever wrote it.

    What matters is that it cannot drift. A round that adds a paragraph to the main script and leaves
    a table saying ten minutes is exactly the stale-number failure this session has fixed in six
    artefacts, and here it would be read aloud by somebody with a clock.
    """
    import re
    from pathlib import Path

    speech = read("docs/SPEECH.md")
    body = re.search(r"## The main script(.*?)## The two-minute cut", speech, re.S).group(1)
    spoken = re.sub(r"^#.*$", "", body, flags=re.M)
    spoken = re.sub(r"^>.*$", "", spoken, flags=re.M)
    spoken = re.sub(r"〔[^〕]*〕", "", spoken)
    words = len([w for w in re.split(r"\s+", spoken) if w.strip()])

    claimed = re.search(r"([\d,]+) words across six sections", speech)
    assert claimed, "the speech no longer states a word count"
    stated = int(claimed.group(1).replace(",", ""))

    drift = abs(words - stated) / stated
    assert drift < 0.05, (
        f"the speech states {stated:,} words and now holds {words:,} ({drift:.0%} apart). "
        f"Either the script changed and the table did not, or the other way round - and a presenter "
        f"reads this number with a clock in front of them.")

    # and the minute figure has to be consistent with the words at the stated pace
    pace = re.search(r"Measured at (\d+) words per minute", speech)
    assert pace, "the speech no longer states its pace"
    minutes = words / int(pace.group(1))
    total = re.search(r"\| \*\*10 min\*\* \| everything \| ([\d:]+) \|", speech)
    if total:
        h, m = (int(x) for x in total.group(1).split(":"))
        assert abs((h * 60 + m) - minutes * 60) < 90, (
            f"the table says {total.group(1)} and the script works out at "
            f"{int(minutes)}m{int(minutes * 60 % 60):02d}s")


def test_a_superseded_report_says_so_on_its_own_first_line():
    """eval-v1 declared that it supersedes eval-v0. eval-v0 did not say anything.

    So a reader opening v0 - which still calls itself "first real measurement" - sees a headline
    figure of +10.4 points where the current report says +9.6, and nothing on the page tells them
    which to quote. A supersession recorded only in the newer document is recorded where the reader
    is not.

    Two figures also had to be reconciled, not just flagged: July's +58 agrees in both reports, and
    the overall figure does not, because the pilot area moved.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    v0 = (root / "reports/eval-v0.md").read_text(encoding="utf-8")
    v1 = (root / "reports/eval-v1.md").read_text(encoding="utf-8")

    assert "Supersedes `eval-v0.md`" in v1, "v1 no longer declares the supersession"
    head = v0[:900]
    assert "SUPERSEDED by" in head, "eval-v0 does not say it has been superseded"
    assert "+9.6" in head or "+10.4" in head, (
        "the banner does not name the figure that differs, so a reader cannot tell what changed")
    assert "Do not quote" in head, "the banner must say which figures are no longer current"


def test_the_tracked_file_count_is_counted_and_not_remembered():
    """The last remembered number, found by sweeping for superseded documents.

    docs/README-published.md corrects its own obsolete claims and gave a count to make the correction
    concrete: "it carries 358 tracked files." That was true when written. By this round the repository
    had 463, so the sentence meant to demonstrate how much had been added had itself become an example
    of the thing this project keeps catching - a figure that was right once and was never recomputed.

    A count in a sentence that argues "this has grown" is the one that will always drift, because the
    more the repository grows the more wrong it gets.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=root)
    if r.returncode != 0:
        return                                    # not a checkout; nothing to compare against
    actual = len([l for l in r.stdout.splitlines() if l.strip()])

    text = read("docs/README-published.md")
    import re
    m = re.search(r"it carries ([\d,]+) tracked files", text)
    assert m, "the corrected file count is gone from README-published.md"
    stated = int(m.group(1).replace(",", ""))

    assert stated == actual, (
        f"README-published.md says {stated} tracked files and the repository has {actual}. "
        f"That sentence exists to show how much has been added, so it is wrong in proportion to "
        f"how much it is right about.")


def test_the_film_does_not_SPEAK_a_number_the_caption_contradicts():
    """The caption was fixed in round 43 and the narration was not.

    cap cd reads "31 of 613 slopes above the rainfall threshold ... peaked the day before, at 149".
    The spoken line still said "छ सय तेह्र मध्ये तीन सय पाँच" - three hundred five - so the film showed
    one number and said another in the SAME clip, in a required submission item, for twenty-six rounds.

    The guard I wrote in round 43 checked the caption in the build script. It never looked at
    voice/narration.txt, which is the half a judge HEARS. Seventh time this session that a guard was
    scoped to the instance in front of it rather than to the claim.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    narr = (root / "reports/video/voice/narration.txt").read_text(encoding="utf-8")
    build = (root / "scripts/build_voiced_video.sh").read_text(encoding="utf-8")

    # Devanagari numerals as words, for the numbers this film must not claim
    assert "तीन सय पाँच" not in narr, (
        "the narration still says 305 slopes; the caption says 31 and the peak was 149")
    assert "एकतीस" in narr, "the corrected count is gone from the narration"

    # and the caption must keep agreeing with it
    cap = [l for l in build.splitlines() if l.startswith("cap cd ")][0]
    assert "31 of 613" in cap and "149" in cap, "the caption and the narration have diverged again"


def test_the_submission_quotes_the_video_length_it_actually_has():
    """SUBMISSION.md pastes the eligibility output, and that output contains the film's duration.

    The film is rebuilt whenever a defect like the spoken 305 is fixed, so the duration moves - and
    the pasted line cannot. It said 157 s while the film was 159 s, which is the same drift as every
    other remembered number here, in the one document that is the submission.
    """
    import re
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    film = root / "reports/video/pahiro-narrated-web.mp4"
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(film)], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return                                    # no ffprobe here; nothing to compare
    actual = round(float(r.stdout.strip()))

    text = read("SUBMISSION.md")
    m = re.search(r"the video is 2-3 minutes\s+(\d+) s", text)
    assert m, "the submission no longer quotes the video length"
    assert int(m.group(1)) == actual, (
        f"the submission says {m.group(1)} s and the film is {actual} s - the pasted eligibility "
        f"output drifted, which is what it is there to prevent")


def test_no_jsx_sits_inside_a_promise_callback():
    """The Places toggle was JSX inside a `.then()`, so it was built and discarded every load.

    An arrow-function body is a statement block, not a return, so JSX there can never render. Nothing
    throws, nothing warns, `tsc` is happy and `npm run build` is clean - which is why it survived every
    round, in the layer the brief asks for by name.

    This walks the promise continuations in the web sources and fails on any JSX inside one. It cannot
    be fooled by indentation, unlike a grep: it tracks brace depth from the `.then(` that opens the
    block, and it only looks where a return is impossible.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    web = root / "web"
    files = list((web / "app").rglob("*.tsx")) + list((web / "components").rglob("*.tsx"))
    assert files, "no .tsx files found - the sweep is not looking anywhere"

    offenders = []
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            if re.search(r"\.(then|catch)\(\s*(\([^)]*\)|[A-Za-z_$][\w$]*)?\s*=>\s*\{", lines[i]):
                depth = lines[i].count("{") - lines[i].count("}")
                j = i + 1
                while j < len(lines) and depth > 0:
                    if (re.match(r"\s*<[A-Za-z][\w.]*[\s/>]", lines[j])
                            and "return" not in lines[j]):
                        offenders.append(f"{f.relative_to(root)}:{j + 1}")
                    depth += lines[j].count("{") - lines[j].count("}")
                    j += 1
                i = j
            else:
                i += 1

    assert not offenders, (
        "JSX inside a promise callback can never render - it is constructed and discarded, with no "
        "error anywhere:\n  " + "\n  ".join(offenders))


def test_every_layer_toggle_reaches_the_map():
    """The other half of round 73's failure: a control that renders but changes nothing.

    The Places toggle was dead code, so its state never reached anything. Had it rendered while the
    `places` prop was missing from <SlopeMap>, the checkbox would have looked fine, done nothing, and
    been just as unreachable - with the same absence of any error.

    So: every boolean whose checkbox appears in the sidebar must be passed to the map component.
    """
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / "web/app/page.tsx").read_text(encoding="utf-8")

    toggled = set(re.findall(r'<input type="checkbox" checked=\{(\w+)\}', page))
    assert toggled, "no layer checkboxes found - the sweep is not looking at the sidebar"

    call = re.search(r"<SlopeMap(.*?)/>", page, re.S)
    assert call, "no <SlopeMap ... /> found in page.tsx"
    passed = set(re.findall(r"^\s*(\w+)=", call.group(1), re.M))

    missing = toggled - passed
    assert not missing, (
        "these toggles render a checkbox but their state never reaches the map, so ticking them does "
        f"nothing and says nothing: {sorted(missing)}")
