"""The rainfall trigger must reproduce published thresholds exactly."""
from datetime import date, timedelta

import pytest

from pahiro.trigger import (APPROACHING, BELOW, DAHAL_REGIONAL, EXCEEDED, HELAMBU,
                            PANCHPOKHARI, assess)

AS_OF = date(2024, 9, 28)


def test_published_24h_thresholds_are_reproduced():
    """The reports quote 118.8 mm/24h for Panchpokhari and 124.4 mm/24h for Helambu."""
    assert PANCHPOKHARI.cumulative_mm(24) == pytest.approx(118.8, abs=0.5)
    assert HELAMBU.cumulative_mm(24) == pytest.approx(124.4, abs=0.5)


def test_intensity_curve_decreases_with_duration():
    assert PANCHPOKHARI.intensity_mm_per_h(24) > PANCHPOKHARI.intensity_mm_per_h(240)


def test_dry_series_is_below():
    rain = {AS_OF - timedelta(days=i): 0.0 for i in range(10)}
    a = assess(rain, AS_OF, PANCHPOKHARI)
    assert a.state == BELOW
    assert len(a.windows) == 4


def test_a_day_above_the_24h_threshold_triggers():
    rain = {AS_OF - timedelta(days=i): 0.0 for i in range(10)}
    rain[AS_OF] = 130.0
    a = assess(rain, AS_OF, PANCHPOKHARI)
    assert a.state == EXCEEDED


def test_approaching_band():
    rain = {AS_OF - timedelta(days=i): 0.0 for i in range(10)}
    rain[AS_OF] = 100.0          # 100/118.8 = 0.84
    a = assess(rain, AS_OF, PANCHPOKHARI)
    assert a.state == APPROACHING


def test_multi_day_accumulation_can_trigger_without_one_big_day():
    """Three moderate days can prime a slope even when no single day is extreme."""
    rain = {AS_OF - timedelta(days=i): 0.0 for i in range(10)}
    for i in range(3):
        rain[AS_OF - timedelta(days=i)] = 55.0
    a = assess(rain, AS_OF, PANCHPOKHARI)
    three_day = next(w for w in a.windows if w.duration_hours == 72)
    assert three_day.accumulation_mm == pytest.approx(165.0)
    assert three_day.accumulation_mm > PANCHPOKHARI.cumulative_mm(72)
    assert three_day.state == EXCEEDED
    # and no single day is extreme on its own
    assert rain[AS_OF] < PANCHPOKHARI.cumulative_mm(24)


def test_patchy_data_is_not_judged():
    """Two missing days out of three is not enough to say anything."""
    rain = {AS_OF: 200.0}
    a = assess(rain, AS_OF, PANCHPOKHARI)
    assert all(w.duration_hours != 72 for w in a.windows)


def test_banner_is_human_readable():
    rain = {AS_OF - timedelta(days=i): 10.0 for i in range(10)}
    a = assess(rain, AS_OF, DAHAL_REGIONAL)
    assert "rainfall trigger" in a.banner()
    assert a.state in (BELOW, APPROACHING, EXCEEDED)


def test_nepali_rainfall_state_has_no_english_leak():
    from pahiro.advisory.nepali import rainfall_state_ne

    rain = {AS_OF - timedelta(days=i): 20.0 for i in range(10)}
    a = assess(rain, AS_OF, PANCHPOKHARI)
    text = rainfall_state_ne(a)
    assert "थ्रेसहोल्ड" in text, "the state must be in Nepali"
    assert "exceeded" not in text and "below" not in text and "approaching" not in text
    assert "Panchpokhari" not in text, "the threshold place name must be Nepali too"
    assert "पाँचपोखरी" in text
    assert "घण्टामा" in text and "मिमि" in text


def test_nepali_rainfall_state_handles_missing_data():
    from pahiro.advisory.nepali import rainfall_state_ne

    assert "उपलब्ध छैन" in rainfall_state_ne(None)


def test_rainfall_cache_avoids_a_second_fetch(tmp_path, monkeypatch):
    """The cache is what makes the live demo instant, so it must actually be used."""
    from datetime import date

    from pahiro.ingest import rainfall

    calls = {"n": 0}

    def fake_fetch(day, bbox, timeout=90):
        calls["n"] += 1
        return rainfall.DailyRainfall(day=day, mean_mm=5.0, max_mm=9.0, p95_mm=7.0, pixels=4)

    monkeypatch.setattr(rainfall, "fetch_day", fake_fetch)
    bbox = (85.0, 27.5, 85.6, 28.0)
    first = rainfall.fetch_series_cached(bbox, date(2024, 9, 1), date(2024, 9, 3), tmp_path)
    assert len(first) == 3 and calls["n"] == 3
    second = rainfall.fetch_series_cached(bbox, date(2024, 9, 1), date(2024, 9, 3), tmp_path)
    assert len(second) == 3
    assert calls["n"] == 3, "the second call must come entirely from disk"
    assert second[0].max_mm == 9.0


def test_rainfall_cache_remembers_a_missing_day(tmp_path, monkeypatch):
    from datetime import date

    from pahiro.ingest import rainfall

    calls = {"n": 0}

    def unavailable(day, bbox, timeout=90):
        calls["n"] += 1
        return None

    monkeypatch.setattr(rainfall, "fetch_day", unavailable)
    bbox = (85.0, 27.5, 85.6, 28.0)
    rainfall.fetch_series_cached(bbox, date(2024, 9, 1), date(2024, 9, 1), tmp_path)
    rainfall.fetch_series_cached(bbox, date(2024, 9, 1), date(2024, 9, 1), tmp_path)
    assert calls["n"] == 1, "a genuinely unavailable day must not be retried every run"


def test_sample_point_reads_the_right_pixel():
    """Read once, sample many - the sampling must land on the right cell."""
    import numpy as np
    from affine import Affine

    from pahiro.ingest.rainfall import sample_point

    arr = np.arange(100, dtype="float32").reshape(10, 10)
    transform = Affine.translation(85.0, 28.0) * Affine.scale(0.05, -0.05)
    # origin is the top-left corner; the first row is the northern edge
    assert sample_point(arr, transform, 85.001, 27.999) == arr[0, 0]
    # 27.851 falls in row 2 (which spans 27.90-27.85), not row 3
    assert sample_point(arr, transform, 85.151, 27.851) == arr[2, 3]
    # outside the window is NaN, never a wrong number
    assert sample_point(arr, transform, 80.0, 20.0) != sample_point(arr, transform, 80.0, 20.0)


def test_trigger_eval_scores_events_against_controls():
    from pahiro.eval.trigger_eval import SiteResult, summarise

    rows = [SiteResult("e1", "event", "2024-09-28", 27.7, 85.3, 130.0, 190.0, "exceeded", True),
            SiteResult("e2", "event", "2024-09-28", 27.8, 85.4, 60.0, 90.0, "below", False),
            SiteResult("c1", "control", "2024-09-28", 27.9, 85.5, 20.0, 30.0, "below", False),
            SiteResult("c2", "control", "2024-09-28", 27.6, 85.6, 10.0, 15.0, "below", False)]
    rep = summarise(rows)
    assert rep["event_trigger_rate_pct"] == 50.0
    assert rep["control_trigger_rate_pct"] == 0.0
    assert rep["difference_pct_points"] == 50.0
    assert any("lower bound" in x for x in rep["limitations"])
    assert "does it discriminate" in __import__("pahiro.eval.trigger_eval", fromlist=["markdown"]).markdown(rep)
