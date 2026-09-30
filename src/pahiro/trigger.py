"""Rainfall trigger: the threshold that says 'the situation is developing'.

Published intensity-duration thresholds for Nepal, used to turn a rainfall series
into a trigger state. The threshold answers one question: has enough rain fallen,
over a long enough period, that the slope is now primed?

This is the layer that leads, because it is available every day of the monsoon.
Ground evidence then disposes: rainfall proposes, the satellite and the citizen
confirm.

Sources: Practical Action (2025) for Helambu and Panchpokhari Thangpal,
Sindhupalchok - the same district as our corrected pilot area - and Dahal &
Hasegawa (2008) for the regional curve. The Panchpokhari fit rests on only 43
landslide events, so it is used as a published reference, not as truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

BELOW, APPROACHING, EXCEEDED = "below", "approaching", "exceeded"
APPROACHING_FRACTION = 0.80   # within 20% of the threshold counts as approaching


@dataclass(frozen=True)
class Threshold:
    """Intensity-duration threshold: I = a * D^(-b), with I in mm/h and D in hours."""
    name: str
    a: float
    b: float
    d_min_hours: float
    d_max_hours: float
    source: str

    def intensity_mm_per_h(self, duration_hours: float) -> float:
        return self.a * duration_hours ** (-self.b)

    def cumulative_mm(self, duration_hours: float) -> float:
        """The rainfall total that would reach the threshold over that duration."""
        return self.intensity_mm_per_h(duration_hours) * duration_hours

    def in_range(self, duration_hours: float) -> bool:
        return self.d_min_hours <= duration_hours <= self.d_max_hours


# Verified from the published studies; see docs/DATA.md.
PANCHPOKHARI = Threshold(
    "Panchpokhari Thangpal, Sindhupalchok", 52.476, 0.743, 13, 300,
    "Practical Action (2025); 43 landslide events")
HELAMBU = Threshold(
    "Helambu, Sindhupalchok", 41.029, 0.651, 14, 450,
    "Practical Action (2025); 44 landslide events")
DAHAL_REGIONAL = Threshold(
    "Dahal & Hasegawa (2008), regional", 73.90, 0.79, 5, 720,
    "Dahal & Hasegawa (2008)")

THRESHOLDS = {t.name: t for t in (PANCHPOKHARI, HELAMBU, DAHAL_REGIONAL)}
DURATIONS_HOURS = (24, 48, 72, 240)


@dataclass
class WindowAssessment:
    duration_hours: int
    accumulation_mm: float
    threshold_mm: float
    state: str

    @property
    def ratio(self) -> float:
        return self.accumulation_mm / self.threshold_mm if self.threshold_mm else 0.0


@dataclass
class TriggerAssessment:
    as_of: date
    threshold: Threshold
    statistic: str
    windows: list[WindowAssessment] = field(default_factory=list)
    assessed_days: int = 0
    missing_days: int = 0

    @property
    def state(self) -> str:
        if any(w.state == EXCEEDED for w in self.windows):
            return EXCEEDED
        if any(w.state == APPROACHING for w in self.windows):
            return APPROACHING
        return BELOW

    def banner(self) -> str:
        parts = [f"{w.duration_hours}h {w.accumulation_mm:.0f}/{w.threshold_mm:.0f}mm"
                 for w in self.windows]
        return f"rainfall trigger {self.state.upper()} ({self.threshold.name}): " + ", ".join(parts)


def assess(rainfall_by_day: dict[date, float], as_of: date, threshold: Threshold,
           statistic: str = "max_mm",
           durations: tuple[int, ...] = DURATIONS_HOURS) -> TriggerAssessment:
    """Compare antecedent rainfall against a published threshold.

    rainfall_by_day maps a day to the chosen statistic (mean, max or p95) for the
    area. Only days present in the mapping are counted; absent days are reported as
    missing rather than silently treated as dry.
    """
    out = TriggerAssessment(as_of=as_of, threshold=threshold, statistic=statistic)
    for hours in durations:
        days = hours // 24
        accum = 0.0
        present = 0
        for i in range(days):
            day = as_of - timedelta(days=i)
            if day in rainfall_by_day:
                accum += rainfall_by_day[day]
                present += 1
        required = max(1, (days + 1) // 2)   # at least half the days, rounded up
        if present < required:
            continue                      # too patchy to judge honestly
        limit = threshold.cumulative_mm(hours)
        ratio = accum / limit if limit else 0.0
        state = EXCEEDED if ratio >= 1.0 else (APPROACHING if ratio >= APPROACHING_FRACTION else BELOW)
        out.windows.append(WindowAssessment(hours, accum, limit, state))
    out.assessed_days = len(rainfall_by_day)
    out.missing_days = max(0, durations[-1] // 24 - out.assessed_days)
    return out
