"""Matched control sites: slopes with no recorded failure.

Without controls, a detection rate means nothing - you cannot tell a working system
from one that flags every hillside. The prior-art audit was explicit: no Nepal source
publishes control sites, so they have to be generated, and generated honestly.

Three rules, all designed to make the controls *harder* than they need to be:

1. A control must be far enough from every recorded failure that it is not simply the
   same slope. We exclude by distance to the whole inventory, not just the matched
   event.
2. A control must be a plausible slope, so it is drawn within a similar radius of the
   matched event rather than from flat farmland somewhere convenient.
3. Controls are drawn with a fixed seed, so the benchmark is reproducible and cannot
   be quietly re-rolled until the numbers look good.

The limitation this module cannot fix, and states plainly: **absence of a record is
not evidence of stability.** Nepal's inventory is thin, and a "control" is a slope
nobody has recorded a failure on - not a slope proven not to fail. Any false-alarm
figure derived from these is therefore a *lower bound* on the true rate.
"""
from __future__ import annotations

import csv
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path

EARTH_R_KM = 6371.0088

DISCLAIMER = ("absence of a record is not evidence of stability: a control is a slope with no "
              "recorded failure, not a slope proven not to fail, so any false-alarm rate derived "
              "from these sites is a lower bound on the true rate")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class ControlSite:
    control_id: str
    matched_event_id: str
    event_date: str
    lat: float
    lon: float
    distance_from_event_km: float
    nearest_known_event_km: float
    note: str = DISCLAIMER


def _random_point_near(lat: float, lon: float, min_km: float, max_km: float,
                       rng: random.Random) -> tuple[float, float]:
    """A point at a random bearing and distance from the event."""
    dist = rng.uniform(min_km, max_km)
    bearing = rng.uniform(0, 2 * math.pi)
    dlat = (dist / 111.32) * math.cos(bearing)
    dlon = (dist / (111.32 * max(0.1, math.cos(math.radians(lat))))) * math.sin(bearing)
    return lat + dlat, lon + dlon


def generate_controls(events: list[dict], per_event: int = 3,
                      min_km: float = 1.0, max_km: float = 12.0,
                      exclusion_km: float = 1.0, seed: int = 42,
                      all_events: list[dict] | None = None) -> list[ControlSite]:
    """Draw control slopes near each event, excluding ground close to any failure.

    `all_events` is the full inventory used for exclusion; it defaults to `events`.
    """
    rng = random.Random(seed)
    inventory = all_events if all_events is not None else events
    points = [(float(e["lat"]), float(e["lon"])) for e in inventory]

    out: list[ControlSite] = []
    for event in events:
        elat, elon = float(event["lat"]), float(event["lon"])
        made = 0
        attempts = 0
        while made < per_event and attempts < per_event * 200:
            attempts += 1
            lat, lon = _random_point_near(elat, elon, min_km, max_km, rng)
            if not (-90 <= lat <= 90):
                continue
            nearest = min((haversine_km(lat, lon, p[0], p[1]) for p in points), default=999.0)
            if nearest < exclusion_km:
                continue
            out.append(ControlSite(
                control_id=f"ctl-{event.get('incident_id', 'x')}-{made + 1}",
                matched_event_id=str(event.get("incident_id", "")),
                event_date=str(event.get("date", "")),
                lat=round(lat, 5), lon=round(lon, 5),
                distance_from_event_km=round(haversine_km(lat, lon, elat, elon), 2),
                nearest_known_event_km=round(nearest, 2),
            ))
            made += 1
    return out


def write_csv(controls: list[ControlSite], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(controls[0]).keys()))
        w.writeheader()
        w.writerows(asdict(c) for c in controls)
    return out
