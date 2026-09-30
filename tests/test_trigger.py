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
