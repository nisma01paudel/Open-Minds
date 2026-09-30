"""Daily rainfall for an area, from CHIRPS. Free, anonymous, no key.

Rainfall is the one signal available every day of the monsoon, which is why the
trigger layer leads with it: optical imagery is blind exactly when landslides kill
(measured: zero usable Sentinel-2 scenes in July and August over eleven years),
and radar gives four to six looks a month. Rain gives a value every single day.

Read straight out of the remote gzip with GDAL's chained virtual filesystems - no
download step, one small window per day.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import rasterio
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
