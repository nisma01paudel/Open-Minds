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
