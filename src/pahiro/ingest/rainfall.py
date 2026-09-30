"""Daily rainfall for an area, from CHIRPS. Free, anonymous, no key.

Rainfall is the one signal available every day of the monsoon, which is why the
trigger layer leads with it: optical imagery is blind exactly when landslides kill
(measured: zero usable Sentinel-2 scenes in July and August over eleven years),
and radar gives four to six looks a month. Rain gives a value every single day.

Read straight out of the remote gzip with GDAL's chained virtual filesystems - no
download step, one small window per day.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import math

import numpy as np
import rasterio
from affine import Affine
from rasterio.windows import from_bounds

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".gz,.tif")
os.environ.setdefault("VSI_CACHE", "TRUE")

BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05"


def chirps_url(day: date) -> str:
    return f"{BASE}/{day.year}/chirps-v2.0.{day:%Y.%m.%d}.tif.gz"


@dataclass
class DailyRainfall:
    day: date
    mean_mm: float
    max_mm: float
    p95_mm: float
    pixels: int

    @property
    def usable(self) -> bool:
        return self.pixels > 0


def fetch_day(day: date, bbox: tuple[float, float, float, float],
              timeout: int = 90) -> DailyRainfall | None:
    """Mean/max/p95 rainfall over the bbox for one day. None if unavailable."""
    href = f"/vsigzip//vsicurl/{chirps_url(day)}"
    try:
        with rasterio.open(href) as ds:
            win = from_bounds(*bbox, transform=ds.transform)
            arr = ds.read(1, window=win).astype("float32")
    except Exception:
        return None
    if arr.size == 0:
        return None
    arr[arr < 0] = np.nan          # CHIRPS uses -9999 for no data
    if not np.isfinite(arr).any():
        return None
    return DailyRainfall(
        day=day,
        mean_mm=float(np.nanmean(arr)),
        max_mm=float(np.nanmax(arr)),
        p95_mm=float(np.nanpercentile(arr, 95)),
        pixels=int(np.isfinite(arr).sum()),
    )


def fetch_series(bbox, start: date, end: date, timeout: int = 90) -> list[DailyRainfall]:
    """Every available day in [start, end]. Missing days are skipped, not guessed."""
    out: list[DailyRainfall] = []
    day = start
    while day <= end:
        rec = fetch_day(day, bbox, timeout)
        if rec is not None and rec.usable:
            out.append(rec)
        day += timedelta(days=1)
    return out


DEFAULT_CACHE = "cache/rainfall"


def _cache_key(bbox, day: date) -> str:
    return f"{bbox[0]:.2f}_{bbox[1]:.2f}_{bbox[2]:.2f}_{bbox[3]:.2f}_{day.isoformat()}.json"


def fetch_series_cached(bbox, start: date, end: date,
                        cache_dir: str | Path = DEFAULT_CACHE,
                        timeout: int = 90) -> list[DailyRainfall]:
    """Like fetch_series, but each day is cached to disk.

    A live demo cannot spend minutes re-reading rainfall it has already read. The
    first run warms the cache; every later run - including on stage with no network
    at all - is instant. Cached misses that were genuinely unavailable are recorded
    too, so a failed day is not retried on every run.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    out: list[DailyRainfall] = []
    day = start
    while day <= end:
        path = cache / _cache_key(bbox, day)
        if path.exists():
            payload = json.loads(path.read_text())
            if payload:
                out.append(DailyRainfall(**{**payload, "day": date.fromisoformat(payload["day"])}))
            day += timedelta(days=1)
            continue
        rec = fetch_day(day, bbox, timeout)
        if rec is not None and rec.usable:
            data = asdict(rec); data["day"] = rec.day.isoformat()
            path.write_text(json.dumps(data))
            out.append(rec)
        else:
            path.write_text("null")          # remember the miss
        day += timedelta(days=1)
    return out


# --------------------------------------------------------------------------- #
# Read once, sample many.
#
# Reading a small window per site means one GDAL open per site per day. For a
# country-wide comparison across hundreds of sites that is thousands of opens. The
# CHIRPS tile is global and cheap to read in full over a regional box, so we read the
# whole box once per day and sample every site from memory instead.
# --------------------------------------------------------------------------- #

NEPAL_BBOX = (80.0, 26.0, 89.0, 31.0)


def fetch_window(day: date, bbox: tuple[float, float, float, float] = NEPAL_BBOX,
                 timeout: int = 120):
    """The whole rainfall window for one day as (array, transform). None if unavailable."""
    href = f"/vsigzip//vsicurl/{chirps_url(day)}"
    try:
        with rasterio.open(href) as ds:
            win = from_bounds(*bbox, transform=ds.transform)
            arr = ds.read(1, window=win).astype("float32")
            transform = ds.window_transform(win)
    except Exception:
        return None
    arr[arr < 0] = np.nan
    if not np.isfinite(arr).any():
        return None
    return arr, transform


def fetch_window_cached(day: date, bbox=NEPAL_BBOX, cache_dir: str | Path = "cache/rain-window"):
    """Cached window read, stored as .npy with its transform in the filename sidecar."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    arr_path = cache / f"{bbox[0]:.0f}_{bbox[1]:.0f}_{bbox[2]:.0f}_{bbox[3]:.0f}_{day}.npy"
    meta_path = arr_path.with_suffix(".meta")
    if arr_path.exists() and meta_path.exists():
        arr = np.load(arr_path)
        meta = json.loads(meta_path.read_text())
        if meta.get("missing"):
            return None
        return arr, Affine(*meta["transform"])
    result = fetch_window(day, bbox)
    if result is None:
        np.save(arr_path, np.zeros((1, 1), dtype="float32"))
        meta_path.write_text(json.dumps({"missing": True, "transform": [1, 0, 0, 0, -1, 0]}))
        return None
    arr, transform = result
    np.save(arr_path, arr)
    t = transform
    meta_path.write_text(json.dumps({"missing": False,
                                     "transform": [t.a, t.b, t.c, t.d, t.e, t.f]}))
    return arr, transform


def sample_point(arr: np.ndarray, transform, lon: float, lat: float) -> float:
    """Nearest-pixel rainfall at a coordinate, or NaN if outside the window."""
    if transform.a == 0 or transform.e == 0:
        return float("nan")
    # floor, not int(): int() truncates toward zero, which is wrong west of the
    # window's origin and silently returns a neighbouring cell instead of a miss.
    col = math.floor((lon - transform.c) / transform.a)
    row = math.floor((lat - transform.f) / transform.e)
    if not (0 <= row < arr.shape[0] and 0 <= col < arr.shape[1]):
        return float("nan")
    value = float(arr[row, col])
    return value if np.isfinite(value) else float("nan")
