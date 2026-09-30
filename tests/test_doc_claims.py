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
        ("305 above threshold", "305", "305", "तीन सय पाँच"),
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
    assert "20,176" in speech or "20176" in speech, "the pitch never gives the trail network"
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
    for needed in ("hiking trail", "bus", "20,176", "openstreetmap"):
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
