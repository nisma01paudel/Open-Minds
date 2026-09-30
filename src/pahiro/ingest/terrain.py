"""A DEM window for a site, from Copernicus DEM 30 m.

Two quirks this module exists to absorb, both of which silently produced nothing
before it existed:

- Copernicus DEM items carry a fixed acquisition date, so a date-bounded search for a
  recent year returns zero tiles. The search range here is deliberately wide.
- Their assets are `s3://` URLs rather than HTTPS, which `stac` now normalises.

The DEM is served in EPSG:4326, so it is also the reason `siting` derives pixel size
in metres rather than assuming the transform is metric.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pahiro.ingest import stac, window

# Wide enough to cover the collection's fixed item dates.
DEM_START, DEM_END = "2000-01-01", "2030-01-01"


@dataclass
class TerrainWindow:
    elevation: np.ndarray
    transform: object
    crs: object
    valid_fraction: float

    @property
    def usable(self) -> bool:
        return self.valid_fraction > 0.5


def fetch(bbox: tuple[float, float, float, float], max_pixels: int = 512) -> TerrainWindow | None:
    """Elevation for a bbox, or None if no tile covers it."""
    tiles = stac.search(stac.DEM, bbox, DEM_START, DEM_END, cloud_lt=None)
    if not tiles:
        return None
    href = tiles[0].assets.get("data") or next(iter(tiles[0].assets.values()), None)
    if not href:
        return None
    patch = window.read_band(href, bbox, max_pixels=max_pixels)
    return TerrainWindow(elevation=patch.values.astype("float64"), transform=patch.transform,
                         crs=patch.crs, valid_fraction=patch.valid_fraction)
