"""Staleness gate: the product's honesty mechanism.

An advisory may only be issued when there is fresh evidence. During the monsoon,
optical sensors are blind exactly when landslides happen (verified: zero usable
Sentinel-2 scenes over the Dhading corridor in July and August, 2019-2025, while
Sentinel-1 radar delivered 4-6 looks every month). Rather than guess, the system
reports the gap.

This module is deliberately deterministic and testable. The AI layer chooses
*where to route* and *how to phrase*; it never decides whether we can see.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Sensor names used across the pipeline.
OPTICAL = "sentinel-2"
RADAR = "sentinel-1"
RAINFALL = "rainfall"
CITIZEN = "citizen-report"

# A sensor's observation counts as fresh only inside its own window.
# Values are deliberately conservative: Sentinel-1 revisit is 6-12 days, and
# terrain geometry means not every pass images a given slope.
FRESH_WINDOW_DAYS = {
    OPTICAL: 20,
    RADAR: 14,
    RAINFALL: 3,
    CITIZEN: 30,
}

# An observation must have at least this usable fraction to count at all.
MIN_QUALITY = 0.30

# Below this usable fraction even a fresh optical scene is treated as weak.
WEAK_QUALITY = 0.60


@dataclass(frozen=True)
class Observation:
    sensor: str
    observed_at: date
    quality: float = 1.0          # usable pixel fraction, 0..1
    scene_id: str | None = None


@dataclass
class StalenessDecision:
    status: str                    # 'ok' | 'degraded' | 'abstain'
    confidence: str                # 'high' | 'medium' | 'low' | 'none'
    ages: dict[str, int] = field(default_factory=dict)   # sensor -> days since observation
    fresh: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def may_issue(self) -> bool:
        return self.status != "abstain"

    def banner(self) -> str:
        """One line, safe to show a ward chair."""
        if self.status == "abstain":
            stale = ", ".join(f"{s} {d}d" for s, d in self.ages.items()) or "no observation on record"
            return f"NO FRESH OBSERVATION ({stale}) - no advisory issued."
        freshest = min(self.ages.items(), key=lambda kv: kv[1])
        return (f"Evidence age: {freshest[0]} {freshest[1]} day(s). "
                f"Status: {self.status}. Confidence: {self.confidence}.")


def staleness_gate(
    observations: list[Observation],
    as_of: date,
    fresh_window_days: dict[str, int] | None = None,
    min_quality: float = MIN_QUALITY,
) -> StalenessDecision:
    """Decide whether an advisory may be issued, and at what confidence."""
    windows = dict(FRESH_WINDOW_DAYS if fresh_window_days is None else fresh_window_days)
    ages: dict[str, int] = {}
    usable: dict[str, Observation] = {}

    for obs in observations:
        age = (as_of - obs.observed_at).days
        if age < 0:
            continue  # an observation from the future is not evidence
        # Keep the newest usable observation per sensor.
        if obs.quality < min_quality:
            ages.setdefault(obs.sensor, age)
            continue
        ages[obs.sensor] = min(ages.get(obs.sensor, age), age)
        prev = usable.get(obs.sensor)
        if prev is None or obs.observed_at > prev.observed_at:
            usable[obs.sensor] = obs

    fresh = [
        sensor
        for sensor, obs in usable.items()
        if (as_of - obs.observed_at).days <= windows.get(sensor, 14)
    ]

    reasons: list[str] = []
    has_optical = OPTICAL in fresh
    has_radar = RADAR in fresh

    if not has_optical and not has_radar:
        if ages:
            reasons.append("no optical or radar observation inside the freshness window")
        else:
            reasons.append("no observation on record for this location")
        if RAINFALL in fresh:
            reasons.append("rainfall alone is not evidence of ground change")
        return StalenessDecision("abstain", "none", ages, fresh, reasons)

    if not has_optical and has_radar:
        reasons.append("optical unavailable - monsoon cloud or no recent pass")
        reasons.append("radar-only: reports surface change, cannot resolve ground detail")
        return StalenessDecision("degraded", "medium", ages, fresh, reasons)

    optical_obs = usable[OPTICAL]
    if optical_obs.quality < WEAK_QUALITY:
        reasons.append(f"optical usable fraction {optical_obs.quality:.2f} is weak")
        if has_radar:
            reasons.append("radar corroborates the optical signal")
            return StalenessDecision("ok", "medium", ages, fresh, reasons)
        return StalenessDecision("degraded", "low", ages, fresh, reasons)

    reasons.append("fresh optical observation with adequate usable fraction")
    if has_radar:
        reasons.append("radar corroborates the optical signal")
    if RAINFALL in fresh:
        reasons.append("antecedent rainfall available")
    return StalenessDecision("ok", "high", ages, fresh, reasons)
