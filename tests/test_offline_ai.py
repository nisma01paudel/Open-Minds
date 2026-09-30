"""The mobile floor: nothing that saves a life may sit behind the AI.

The test that matters most in this file is `test_the_lifesaving_set_needs_no_model`. It is a
guard against a future change that moves routing or the advisory behind a language model and
quietly makes the app useless on the 2 GB handsets this is built for.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pahiro import offline_ai as O

ROOT = Path(__file__).resolve().parents[1]


# ---- the invariant ---------------------------------------------------------------------------

def test_the_lifesaving_set_needs_no_model():
    """If this fails, someone has moved a life-saving feature behind an LLM. Do not 'fix' it."""
    assert O.LIFESAVING <= O.TIER_NONE.enables
    assert O.TIER_NONE.weights_mb == 0.0
    assert O.TIER_NONE.ram_mb == O.OS_FLOOR_MB, "the floor costs only the operating system"


def test_every_tier_is_additive_and_never_loses_a_capability():
    for tier in O.LADDER:
        assert O.LIFESAVING <= tier.enables, f"{tier.name} dropped a life-saving capability"


def test_the_ladder_is_ordered_by_cost():
    by_size = sorted(O.LADDER, key=lambda t: t.weights_mb)
    assert by_size == list(reversed(O.LADDER)), "LADDER must be largest-first for fit()"
    sizes = [t.weights_mb for t in by_size]
    assert sizes == sorted(sizes)
    assert len(set(sizes)) == len(sizes), "two tiers with the same weight is a mistake"


# ---- the arithmetic is honest about RAM ------------------------------------------------------

def test_a_model_costs_more_than_its_file():
    """Weights plus working memory plus the OS. Assuming otherwise is how an app gets killed."""
    assert O.ram_for(1000.0) > 1000.0
    assert O.ram_for(1000.0) == pytest.approx(1000.0 * O.WORKING_SET_MULTIPLIER + O.OS_FLOOR_MB)
    assert O.ram_for(0.0) == O.OS_FLOOR_MB


def test_the_full_stack_matches_the_measured_documentation():
    """The numbers come from docs/MODELS.md, so they must keep describing the same stack."""
    assert O.TIER_FULL.weights_mb == pytest.approx(
        O.DINOV2_MB + O.DECISION_HEAD_MB + O.SMOLVLM_MB + O.QWEN_1_5B_MB + O.PIPER_NE_MB)
    # The five components sum to about 1.45 GB; the docs' "about 1.7 GB on disk" also counts
    # the inference runtime, which is not a model and is deliberately not in this sum.
    assert 1400 < O.TIER_FULL.weights_mb < 1800, "docs say about 1.7 GB on disk"


def test_the_nepali_voice_is_small_and_local():
    """63 MB and MIT is why the voice needs no API key. It is a design property, not trivia."""
    assert O.PIPER_NE_MB < 100
    assert "piper_ne_np" in O.TIER_VISION.components
    assert O.TTS_RTF < 0.2, "the local voice must be faster than real time"


# ---- choosing, on real handset shapes --------------------------------------------------------

def test_a_two_gigabyte_handset_gets_the_small_language_model_and_not_a_lie():
    """2 GB is the common district handset. It runs the 0.5B tier, and not the vision-only one,
    because 0.5B is small enough to fit alongside the OS once working memory is counted."""
    fit = O.fit(O.Device(ram_mb=2048, storage_free_mb=4000))
    assert fit.tier.name == "mid"
    assert "nepali_voice" in fit.tier.enables
    assert "written_advisory_small" in fit.tier.enables
    assert "image_description" in fit.missing
    assert "written_advisory" in fit.missing
    assert "will not do" in fit.explain()


def test_a_one_gigabyte_handset_still_gets_vision_and_a_voice():
    """The tier that matters for reach: change detection and spoken Nepali for 92 MB."""
    fit = O.fit(O.Device(ram_mb=1024, storage_free_mb=3000))
    assert fit.tier.name == "vision"
    assert fit.tier.weights_mb == pytest.approx(O.DINOV2_MB + O.DECISION_HEAD_MB + O.PIPER_NE_MB)
    assert "nepali_voice" in fit.tier.enables


def test_a_six_gigabyte_phone_can_run_the_laptop_stack():
    fit = O.fit(O.Device(ram_mb=6144, storage_free_mb=20000))
    assert fit.tier.name == "full"


def test_a_full_storage_phone_falls_to_the_floor_rather_than_failing():
    """50 MB free cannot hold even the 92.5 MB vision set. It must degrade, not break."""
    fit = O.fit(O.Device(ram_mb=4096, storage_free_mb=50))
    assert fit.tier is O.TIER_NONE
    assert O.LIFESAVING <= fit.tier.enables
    assert "storage" in fit.reason


def test_a_tiny_phone_still_gets_everything_that_matters():
    fit = O.fit(O.Device(ram_mb=512, storage_free_mb=2000))
    assert fit.tier is O.TIER_NONE
    for capability in ("sos", "mesh_relay", "ble_beacon", "escape_navigation",
                       "statutory_routing", "advisory_template", "offline_map"):
        assert capability in fit.tier.enables


def test_an_unmeasured_device_is_assumed_to_be_a_modest_handset_not_a_flagship():
    d = O.Device.unknown()
    assert d.source.startswith("assumed")
    assert d.ram_mb <= 2048, "the default must not flatter the hardware"
    assert O.fit(d).tier is not O.TIER_NONE, "a modest handset should still get the voice"


def test_asking_for_a_tier_that_does_not_fit_is_refused_and_reported():
    fit = O.fit(O.Device(ram_mb=2048, storage_free_mb=3000), want="full")
    assert fit.tier.name != "full"
    assert any("does not fit" in x for x in fit.limits)


def test_asking_for_a_tier_that_does_fit_honours_the_request():
    fit = O.fit(O.Device(ram_mb=6144, storage_free_mb=20000), want="vision")
    assert fit.tier.name == "vision"


def test_an_unknown_tier_name_is_an_error_not_a_silent_default():
    with pytest.raises(ValueError):
        O.fit(O.Device(ram_mb=8192, storage_free_mb=20000), want="gpt-9")


def test_every_device_class_resolves_to_a_real_tier():
    for ram in (256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 16384):
        fit = O.fit(O.Device(ram_mb=ram, storage_free_mb=32000))
        assert fit.tier.name in {t.name for t in O.LADDER}
        assert O.LIFESAVING <= fit.tier.enables


# ---- the floor actually works, with no model anywhere ---------------------------------------

def test_the_advisory_renders_with_no_model_in_the_loop():
    """The claim of TIER_NONE is that a phone with nothing still produces the warning."""
    from pahiro.advisory import nepali

    text = nepali.render(
        location="Beni, Myagdi",
        as_of="2026-09-30",
        what_changed="rainfall over the 72 h threshold",
        evidence_state="observed",
        why_it_matters="a slope above the road is loaded",
        inspect_first=["the cut slope above the road"],
        authority_institution="Rural/Urban Municipality (Ward Committee)",
        authority_office="Ward Committee under the Ward Chair",
        legal_basis="LGOA 2074 s.12(2)(c)(23)",
    )
    assert text.strip()
    assert any("\u0900" <= ch <= "\u097F" for ch in text), "the advisory must be in Nepali"


def test_the_escape_plan_needs_no_model():
    """The navigator is arithmetic over a DEM, which is exactly why it works on any phone."""
    from pahiro import shelter

    dem = shelter.load_dem(ROOT / "web/public/data/terrain.bin",
                           ROOT / "web/public/data/terrain.json")
    if dem is None:
        pytest.skip("national DEM not built in this checkout")
    e = shelter.plan_escape(dem, 28.35, 83.57, rise_m=5.0)
    assert e.reachable or e.reason
    assert "offline_ai" not in str(type(e))


def test_the_ladder_can_be_listed_for_a_settings_screen():
    rows = O.ladder_summary()
    assert len(rows) == len(O.LADDER)
    assert rows[0]["name"] == "none", "the summary must lead with the floor"
    for row in rows:
        assert row["note"] and row["enables"]
        assert row["ram_mb"] >= row["weights_mb"]


# ---- the voice, actually downloaded -----------------------------------------------------------------

def test_the_nepali_voice_is_downloaded_and_speaks():
    """63 MB and MIT is the claim; this checks the file is real and piper can drive it.

    Skipped rather than failed when the voice has not been fetched, because the model is an
    artifact and not part of the checkout - but a test that silently skips is the false-clean
    this project keeps finding, so verify_repo.py fails when anything skips.
    """
    import wave
    from pathlib import Path
    import shutil
    import subprocess
    import sys

    voice = Path(__file__).resolve().parents[1] / "evidence" / "voices" / "ne_NP-chitwan-medium.onnx"
    if not voice.exists():
        pytest.skip("the Nepali voice has not been downloaded (see docs/MODELS.md)")
    if shutil.which(str(Path(sys.executable))) is None:
        pytest.skip("no python interpreter")

    assert 60_000_000 < voice.stat().st_size < 70_000_000, \
        f"docs say 63 MB, the file is {voice.stat().st_size} bytes"

    out = Path("/tmp/pahiro_voice_test.wav")
    proc = subprocess.run(
        [sys.executable, "-m", "piper", "-m", str(voice), "-f", str(out)],
        input="माथि जानुहोस्।".encode(), capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode()[:400]
    assert out.exists() and out.stat().st_size > 1000, "piper produced no audio"
    w = wave.open(str(out))
    seconds = w.getnframes() / w.getframerate()
    assert seconds > 0.3, f"only {seconds:.2f}s of audio"


def test_the_demo_film_exists_and_its_narration_is_continuous():
    """The submission says "recorded"; this is what makes that true, and keeps it true.

    The note saying "recording pending" sat in SUBMISSION.md long after the film was built,
    because nothing checked it. A claim nobody verifies goes stale, and a stale claim in a
    submission document is the same failure as a wrong number in a commit message.

    Silence is measured rather than assumed: a 3-second gap at -45 dB would mean an unvoiced
    beat.
    """
    import shutil
    import subprocess
    from pathlib import Path

    film = (Path(__file__).resolve().parents[1]
            / "reports" / "video" / "pahiro-narrated-web.mp4")
    if not film.exists():
        pytest.skip("the demo film has not been built in this checkout")
    if shutil.which("ffprobe") is None or shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed, so the film cannot be inspected")

    duration = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(film)], capture_output=True, text=True, timeout=120).stdout.strip())
    assert 120 <= duration <= 190, (
        f"the submission promises 2-3 minutes; the film is {duration:.0f}s")

    audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name",
         "-of", "csv=p=0", str(film)], capture_output=True, text=True, timeout=120).stdout.strip()
    assert audio, "the film has no audio stream, so it is not narrated"

    # A SILENCE CHECK IS NOT ENOUGH, and this is a false-clean that actually happened: the build
    # log said "(no voice)" for four clips, the film still had no 3-second silent stretch, and the
    # silence test passed. Silence detection cannot see a clip that was built captioned-only.
    #
    # So the check is the one that matches the failure: every narration key the build asks for
    # must have a wav in the voice directory it is told to use.
    import re

    # The WAVs are build inputs and are correctly gitignored, so on a fresh clone they are absent
    # and this per-key check cannot run. Asserting on them anyway made the whole suite fail on a
    # clean checkout - the test was right about the risk and wrong about where to look for it.
    # What IS committed is the narration source: every key the build asks for must have a line.
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "build_voiced_video.sh").read_text(encoding="utf-8")
    keys = re.findall(r"^build \S+ \S+ (\w+) ", script, re.M)
    assert keys, "no build lines found in the video script"

    narration = root / "reports" / "video" / "voice" / "narration.txt"
    if narration.exists():
        spoken = {l.split("|", 1)[0].strip()
                  for l in narration.read_text(encoding="utf-8").splitlines() if "|" in l}
        absent = [k for k in keys if k not in spoken]
        assert not absent, (
            f"the build narrates {absent} and narration.txt has no line for them, so those clips "
            f"would ship with a caption and no voice")

    voice = root / "reports" / "video" / "voice"
    if (voice / f"{keys[0]}.wav").exists():
        missing = [k for k in keys if not (voice / f"{k}.wav").exists()]
        assert not missing, f"the build asks for narration {missing} and has no such wav"

    gaps = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(film), "-af", "silencedetect=noise=-45dB:d=3",
         "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    starts = (gaps.stderr or "").count("silence_start")
    assert starts == 0, (
        f"{starts} stretch(es) of 3 s or more with no narration")
