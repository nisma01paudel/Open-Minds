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
    live = live[:live.index("## The three that make people put their phones down")]

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
