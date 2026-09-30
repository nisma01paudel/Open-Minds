"""Near-real-time rainfall, keyless, so the national view can be about TODAY.

CHIRPS is the long record and it lags roughly four weeks - fine for the evaluation, wrong
for a watch. Open-Meteo serves hourly precipitation from open numerical weather models
(ICON, ECMWF, GFS) for any coordinate, needs no key, and closes that gap.

Two limits discovered by using it, both handled here rather than in the caller:
- asking for ~600 coordinates in one query returns HTTP 414 (URI too large), so requests
  are chunked;
- the free tier throttles, returning HTTP 429 after several chunks in quick succession,
  so chunks are spaced and 429s are retried with backoff.

Results are cached per day: rainfall for a past day does not change, so a re-run costs
nothing and an offline demo still works.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

API = "https://api.open-meteo.com/v1/forecast"
DEFAULT_CACHE = "cache/openmeteo"
CHUNK = 100
SPACING_S = 2.5


class RateLimited(RuntimeError):
    pass


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _query(points: list[tuple[float, float]], api: str = API,
           timeout: int = 90) -> list[dict]:
    """One batch (the caller keeps it under the URI limit)."""
    lats = ",".join(f"{a:.4f}" for a, _ in points)
    lons = ",".join(f"{b:.4f}" for _, b in points)
    params = urllib.parse.urlencode({
        "latitude": lats, "longitude": lons,
        "daily": "precipitation_sum", "past_days": 3, "forecast_days": 1,
        "timezone": "UTC",
    })
    req = urllib.request.Request(f"{api}?{params}", headers={"User-Agent": "pahiro/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data if isinstance(data, list) else [data]


def fetch_daily(points: list[tuple[float, float]], cache_dir: str | Path = DEFAULT_CACHE,
                day: date | None = None, verbose: bool = False) -> list[dict]:
    """Daily precipitation totals for each point, newest last. Cached per day."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    key = (day or date.today()).isoformat()
    path = cache / f"daily-{key}.json"
    if path.exists():
        payload = json.loads(path.read_text())
        if len(payload) == len(points):
            if verbose:
                print(f"  open-meteo: {len(payload)} points from cache")
            return payload

    out: list[dict] = []
    for i, group in enumerate(_chunks(points, CHUNK)):
        if i:
            time.sleep(SPACING_S)
        for attempt in range(4):
            try:
                batch = _query(group)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 3:
                    wait = 5 * (attempt + 1)
                    if verbose:
                        print(f"  open-meteo 429; waiting {wait}s")
                    time.sleep(wait)
                    continue
                raise
            except Exception:
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
        else:
            raise RateLimited("open-meteo throttled after retries")
        out.extend(batch)
        if verbose:
            print(f"  open-meteo: {len(out)}/{len(points)} points")

    if len(out) == len(points):
        path.write_text(json.dumps(out))
    return out


def daily_totals(result: dict) -> dict[str, float]:
    """{'2026-09-28': 12.4, ...} from one location's response."""
    daily = result.get("daily") or {}
    return dict(zip(daily.get("time", []), daily.get("precipitation_sum", [])))


def site_series(points: list[tuple[float, float]], cache_dir: str | Path = DEFAULT_CACHE,
                day: date | None = None, verbose: bool = False) -> list[dict[str, float]]:
    """Per-point {date: mm} series, in the same order as `points`."""
    return [daily_totals(r) for r in fetch_daily(points, cache_dir, day, verbose)]
