"""Tests for the staleness gate - the honesty mechanism.

The cases below encode the real conditions over a Nepal slope:
monsoon optical blackout, radar-only fallback, and no evidence at all.
"""
from datetime import date, timedelta

from pahiro.routing.abstain import (
    CITIZEN, OPTICAL, RADAR, RAINFALL,
    Observation, staleness_gate,
)

AS_OF = date(2025, 7, 15)   # peak monsoon


def days_ago(n: int) -> date:
    return AS_OF - timedelta(days=n)


def test_no_observations_abstains():
    d = staleness_gate([], AS_OF)
    assert d.status == "abstain"
    assert d.confidence == "none"
    assert not d.may_issue


def test_fresh_optical_is_high_confidence():
    obs = [Observation(OPTICAL, days_ago(5), quality=0.9, scene_id="S2A_TEST")]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "ok"
    assert d.confidence == "high"
    assert d.may_issue
    assert d.ages[OPTICAL] == 5


def test_monsoon_optical_blackout_falls_back_to_radar():
    """The real July case: last usable optical was 60 days ago, radar is fresh."""
    obs = [
        Observation(OPTICAL, days_ago(60), quality=0.85),
        Observation(RADAR, days_ago(4), quality=1.0),
    ]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "degraded"
    assert d.confidence == "medium"
    assert d.may_issue, "radar alone must still allow a (weaker) advisory"
    assert any("optical unavailable" in r for r in d.reasons)


def test_no_fresh_sensor_abstains_even_with_rainfall():
    """Heavy rain is a trigger, not evidence that the ground moved."""
    obs = [
        Observation(OPTICAL, days_ago(60), quality=0.85),
        Observation(RADAR, days_ago(40), quality=1.0),
        Observation(RAINFALL, days_ago(1), quality=1.0),
    ]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "abstain", "rainfall alone must never be sufficient"
    assert any("rainfall alone" in r for r in d.reasons)


def test_low_quality_optical_does_not_count_as_fresh():
    obs = [Observation(OPTICAL, days_ago(3), quality=0.05)]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "abstain"


def test_weak_but_real_optical_with_radar_is_medium():
    obs = [
        Observation(OPTICAL, days_ago(6), quality=0.45),
        Observation(RADAR, days_ago(3), quality=1.0),
    ]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "ok"
    assert d.confidence == "medium"


def test_weak_optical_without_radar_is_degraded_low():
    obs = [Observation(OPTICAL, days_ago(6), quality=0.45)]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "degraded"
    assert d.confidence == "low"


def test_future_observation_is_ignored():
    obs = [Observation(OPTICAL, AS_OF + timedelta(days=2), quality=0.9)]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "abstain"


def test_newest_usable_observation_wins():
    obs = [
        Observation(OPTICAL, days_ago(30), quality=0.9),   # stale
        Observation(OPTICAL, days_ago(7), quality=0.8),    # fresh
    ]
    d = staleness_gate(obs, AS_OF)
    assert d.ages[OPTICAL] == 7
    assert d.status == "ok"


def test_banner_is_human_readable_when_blind():
    d = staleness_gate([Observation(OPTICAL, days_ago(60), quality=0.9)], AS_OF)
    assert "NO FRESH OBSERVATION" in d.banner()


def test_recent_citizen_report_counts_but_not_alone():
    """A citizen photo is evidence of something, but not of ground change by itself."""
    obs = [Observation(CITIZEN, days_ago(2), quality=1.0)]
    d = staleness_gate(obs, AS_OF)
    assert d.status == "abstain"


def test_unverified_radar_is_weaker_than_verified_radar():
    """An acquisition whose usability we have not measured must not read as strong."""
    opt = Observation(OPTICAL, days_ago(60), quality=0.85)
    verified = staleness_gate([opt, Observation(RADAR, days_ago(4))], AS_OF)
    unverified = staleness_gate(
        [opt, Observation(RADAR, days_ago(4), verified=False)], AS_OF)
    assert verified.confidence == "medium"
    assert unverified.confidence == "low"
    assert any("unverified" in r for r in unverified.reasons)
