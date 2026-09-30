"""Read windows from cloud-optimized GeoTIFFs over HTTP, and derive change signals.

Only the pixels inside the area of interest are transferred (HTTP range requests),
so a 100 m x 100 m study patch costs kilobytes, not gigabytes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

# Keep GDAL from listing remote directories and cache range requests.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_HTTP_MULTIPLEX", "YES")

# Sentinel-2 scene classification values that mean "not ground".
SCL_BAD = (0, 1, 3, 8, 9, 10, 11)


@dataclass
class Patch:
    """A small, aligned read of one band (or index) over the area of interest."""
    values: np.ndarray
    valid: np.ndarray
    transform: object
    crs: object

    @property
    def valid_fraction(self) -> float:
        return float(self.valid.mean()) if self.valid.size else 0.0

    @property
    def mean(self) -> float:
        if not self.valid.any():
            return float("nan")
        return float(np.nanmean(self.values[self.valid]))


def _window_for(src, bbox: tuple[float, float, float, float]) -> Window:
    """Translate a lon/lat bbox into a pixel window in the raster's own CRS."""
    if src.crs is not None and src.crs.to_string() != "EPSG:4326":
        bbox = transform_bounds("EPSG:4326", src.crs, *bbox)
    win = from_bounds(*bbox, transform=src.transform)
    win = win.round_offsets().round_lengths()
    # Clamp to the raster extent.
    col0 = max(0, int(win.col_off))
    row0 = max(0, int(win.row_off))
    width = max(1, min(int(win.width), src.width - col0))
    height = max(1, min(int(win.height), src.height - row0))
    return Window(col0, row0, width, height)


def read_band(href: str, bbox, max_pixels: int = 512) -> Patch:
    """Read one band for the bbox, decimated if the window is large."""
    with rasterio.open(href) as src:
        win = _window_for(src, bbox)
        out_shape = None
        if max(win.width, win.height) > max_pixels:
            scale = max_pixels / max(win.width, win.height)
            out_shape = (
                max(1, int(win.height * scale)),
                max(1, int(win.width * scale)),
            )
        arr = src.read(1, window=win, out_shape=out_shape, boundless=True,
                       fill_value=np.nan).astype("float32")
        transform = src.window_transform(win)
        crs = src.crs
    valid = np.isfinite(arr)
    return Patch(values=arr, valid=valid, transform=transform, crs=crs)


def _ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Normalised difference, safe against division by zero."""
    num = a - b
    den = a + b
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(np.abs(den) > 1e-6, num / den, np.nan)
    return out.astype("float32")


def index_patch(hrefs: dict[str, str], bbox, kind: str = "ndvi",
                cloud_mask: bool = True) -> Patch:
    """Compute a spectral index over the bbox from a scene's band hrefs.

    kind: 'ndvi' | 'ndmi' | 'ndwi' | 'bsi'
    """
    needs = {
        "ndvi": ("nir", "red"),
        "ndmi": ("nir", "swir16"),
        "ndwi": ("green", "nir"),
        "bsi": ("swir16", "red"),
    }[kind]
    a_key, b_key = needs
    if a_key not in hrefs or b_key not in hrefs:
        raise KeyError(f"{kind} needs assets {needs}; have {sorted(hrefs)}")

    a = read_band(hrefs[a_key], bbox)
    b = read_band(hrefs[b_key], bbox)
    n = (min(a.values.shape[0], b.values.shape[0]),
         min(a.values.shape[1], b.values.shape[1]))
    values = _ratio(a.values[:n[0], :n[1]], b.values[:n[0], :n[1]])
    valid = (a.valid[:n[0], :n[1]] & b.valid[:n[0], :n[1]] & np.isfinite(values))

    if cloud_mask and "scl" in hrefs:
        try:
            scl = read_band(hrefs["scl"], bbox)
            s = scl.values[:n[0], :n[1]]
            sv = scl.valid[:n[0], :n[1]]
            bad = np.isin(np.nan_to_num(s, nan=0).astype("int16"), SCL_BAD) & sv
            valid = valid & ~bad
        except Exception:
            pass  # no cloud mask available: keep the pixels, report lower confidence

    return Patch(values=values, valid=valid, transform=a.transform, crs=a.crs)
