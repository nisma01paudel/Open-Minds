"""The gap timeline must follow the freshness rule exactly."""
from datetime import date, timedelta

from pahiro.eval.gap import daily_status, longest_blind_streak, monthly_share
from pahiro.routing.abstain import OPTICAL, RADAR, Observation

START = date(2025, 1, 1)


def test_single_observation_covers_its_window():
    obs = [Observation(OPTICAL, START, quality=0.9)]
    tl = daily_status(obs, START, START + timedelta(days=25))
    assert tl[START] is True
    assert tl[START + timedelta(days=19)] is True
    assert tl[START + timedelta(days=21)] is False, "beyond the 20-day optical window"


def test_unusable_observation_never_covers():
    obs = [Observation(OPTICAL, START, quality=0.1)]
    tl = daily_status(obs, START, START + timedelta(days=5))
    assert not any(tl.values()), "a cloud-covered scene is not evidence"


def test_radar_extends_coverage_through_a_cloud_gap():
    optical = [Observation(OPTICAL, START, quality=0.9)]
    radar = [Observation(RADAR, START + timedelta(days=30), quality=1.0)]
    end = START + timedelta(days=40)
    assert not daily_status(optical, START, end)[START + timedelta(days=30)]
    assert daily_status(optical + radar, START, end)[START + timedelta(days=30)]


def test_blind_streak_counts_consecutive_days():
    obs = [Observation(OPTICAL, START, quality=0.9)]
    tl = daily_status(obs, START, START + timedelta(days=30))
    assert longest_blind_streak(tl) == 10   # days 21..30


def test_monthly_share_shape():
    obs = [Observation(OPTICAL, START, quality=0.9)]
    share = monthly_share(daily_status(obs, START, START + timedelta(days=45)))
    assert "2025-01" in share and "2025-02" in share
    assert share["2025-01"] > share["2025-02"]
