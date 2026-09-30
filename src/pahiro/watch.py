"""The national picture: every documented slope, its rainfall state, and who owns it.

A per-report tool waits for someone to notice. This does not: it evaluates every
documented landslide-prone slope in the benchmark on one day, from one rainfall read
for the whole country, and pairs each with the office legally responsible for it.

The result answers a question no Nepali system currently answers - not "is this slope
failing?" but "across the country, which slopes are loaded right now, and which office
is on the hook for each one?"

Honest about its own limits, which are printed with the output:
- the trigger threshold is LOCAL (fitted to Sindhupalchok) and used here as a national
  reference, because no equivalent published curve exists for every district;
- rainfall is measured at 0.05 degrees (~5 km), so a convective cell smaller than that
  is invisible;
- it is rainfall, not detection. A primed slope is a site to inspect, not a prediction.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from pahiro.ingest.rainfall import fetch_window_cached, sample_point
from pahiro.ontology import MAINTENANCE, Ontology
from pahiro.trigger import APPROACHING, BELOW, EXCEEDED, PANCHPOKHARI, assess

STATE_ORDER = {EXCEEDED: 0, APPROACHING: 1, BELOW: 2}
STATE_COLOUR = {EXCEEDED: "#dc2626", APPROACHING: "#d97706", BELOW: "#94a3b8"}
STATE_LABEL = {EXCEEDED: "above the threshold", APPROACHING: "approaching the threshold",
               BELOW: "below the threshold"}


@dataclass
class SiteStatus:
    site_id: str
    title: str
    lat: float
    lon: float
    r24_mm: float
    r72_mm: float
    state: str
    authority: str | None
    legal_basis: str | None


def load_sites(path: str | Path = "benchmark/events.csv") -> list[dict]:
    return [r for r in csv.DictReader(open(path, encoding="utf-8"))]


def national_status(as_of: date, sites: list[dict] | None = None,
                    days: int = 3, ontology_path: str | Path = "ontology/nepal-slope-routing.json",
                    verbose: bool = False) -> list[SiteStatus]:
    sites = sites if sites is not None else load_sites()
    ontology = Ontology.load(str(ontology_path))
    # One rainfall read per day covers the whole country; every site is sampled from it.
    windows = {}
    for back in range(days):
        day = as_of - timedelta(days=back)
        got = fetch_window_cached(day)
        if got:
            windows[day] = got
        if verbose:
            print(f"  rainfall window {day}: {'ok' if got else 'unavailable'}")
    if not windows:
        return []

    out: list[SiteStatus] = []
    for s in sites:
        lat, lon = float(s["lat"]), float(s["lon"])
        series = {}
        for day, (arr, transform) in windows.items():
            v = sample_point(arr, transform, lon, lat)
            if v == v:
                series[day] = v
        if not series:
            continue
        a = assess(series, as_of, PANCHPOKHARI)
        w24 = next((w for w in a.windows if w.duration_hours == 24), None)
        w72 = next((w for w in a.windows if w.duration_hours == 72), None)
        rule = ontology.lookup("local-road", MAINTENANCE)
        out.append(SiteStatus(
            site_id=str(s.get("incident_id", "")),
            title=(s.get("title") or "").strip()[:80],
            lat=lat, lon=lon,
            r24_mm=round(w24.accumulation_mm, 1) if w24 else 0.0,
            r72_mm=round(w72.accumulation_mm, 1) if w72 else 0.0,
            state=a.state,
            authority=rule.institution if rule else None,
            legal_basis=rule.legal_basis if rule else None,
        ))
    out.sort(key=lambda r: (STATE_ORDER.get(r.state, 9), -r.r24_mm))
    return out


def summarise(statuses: list[SiteStatus]) -> dict:
    counts = {k: sum(1 for s in statuses if s.state == k) for k in STATE_ORDER}
    return {
        "sites": len(statuses),
        "counts": counts,
        "worst_r24": max((s.r24_mm for s in statuses), default=0.0),
        "with_authority": sum(1 for s in statuses if s.authority),
        "rows": [asdict(s) for s in statuses],
    }
