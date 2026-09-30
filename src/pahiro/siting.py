"""Siting advice: repair in place, or move the alignment above the deformation zone.

Every existing Nepali slope tool ends at a colour on a map. A division road office
cannot act on a colour. It can act on "the deformation zone reaches the road at this
chainage; do not rebuild here; the first stable bench is N metres upslope".

This module turns a terrain window into that recommendation. It is deliberately
honest about what it is: a terrain screen, not a geotechnical design. It reads slope
and aspect from a DEM, finds the steep source zone upslope of the asset, and reports
whether the asset sits in that zone's path. It does not model runout, and it says so
in every result.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

REPAIR_IN_PLACE = "repair-in-place"

# A rise smaller than this is treated as noise rather than as continued ascent.
ASCENT_TOLERANCE_M = 1.0
RELOCATE_UPSLOPE = "relocate-upslope"

CAVEAT = ("terrain screening only: runout is not modelled, geology and drainage are not "
          "considered, and every recommendation requires a geotechnical assessment before "
          "any design or construction decision")


@dataclass
class SitingAdvice:
    recommendation: str
    reason: str
    asset_elevation_m: float | None = None
    source_distance_m: float | None = None
    source_slope_deg: float | None = None
    target_offset_m: float | None = None
    target_elevation_gain_m: float | None = None
    caveats: list[str] = field(default_factory=lambda: [CAVEAT])

    def describe(self) -> str:
        if self.recommendation == RELOCATE_UPSLOPE:
            return (f"relocate the alignment {self.target_offset_m:.0f} m upslope "
                    f"(+{self.target_elevation_gain_m:.0f} m elevation): a source zone at "
                    f"{self.source_distance_m:.0f} m upslope averages "
                    f"{self.source_slope_deg:.0f}°")
        return f"repair in place: {self.reason}"


# A degree of latitude and of longitude at the equator, in metres. Longitude shrinks
# with the cosine of latitude.
_M_PER_DEG_LAT = 110_540.0
_M_PER_DEG_LON = 111_320.0


def _pixel_size_m(transform, crs=None) -> tuple[float, float]:
    """Pixel size in METRES.

    This matters more than it looks. Copernicus DEM is served in EPSG:4326, so the
    transform's units are DEGREES. Treating a degree as a metre understates slope by
    a factor of ~110,000 and would have produced confidently nonsensical terrain
    advice on real data - the worst kind of bug, because nothing crashes.
    """
    dx, dy = abs(transform.a), abs(transform.e)
    if crs is not None and getattr(crs, "is_geographic", False):
        lat = abs(getattr(transform, "f", 0.0))
        return dx * _M_PER_DEG_LON * math.cos(math.radians(lat)), dy * _M_PER_DEG_LAT
    return dx, dy


def slope_aspect_deg(dem: np.ndarray, transform, crs=None) -> tuple[np.ndarray, np.ndarray]:
    """Slope (degrees) and downslope aspect (degrees clockwise from north)."""
    dx, dy = _pixel_size_m(transform, crs)
    dz_dy, dz_dx = np.gradient(dem, dy, dx)          # rows increase southward
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    # Downslope direction: opposite of the gradient (which points uphill).
    aspect = (np.degrees(np.arctan2(-dz_dx, dz_dy)) + 360.0) % 360.0
    return slope.astype("float32"), aspect.astype("float32")


def _sample(arr: np.ndarray, row: float, col: float) -> float:
    """Bilinear sample, clamped to the array."""
    r0 = int(np.clip(np.floor(row), 0, arr.shape[0] - 1))
    c0 = int(np.clip(np.floor(col), 0, arr.shape[1] - 1))
    r1 = min(r0 + 1, arr.shape[0] - 1)
    c1 = min(c0 + 1, arr.shape[1] - 1)
    fr = float(np.clip(row - r0, 0.0, 1.0))
    fc = float(np.clip(col - c0, 0.0, 1.0))
    top = arr[r0, c0] * (1 - fc) + arr[r0, c1] * fc
    bot = arr[r1, c0] * (1 - fc) + arr[r1, c1] * fc
    return float(top * (1 - fr) + bot * fr)


def advise(dem: np.ndarray, transform, row: int, col: int,
           min_source_slope_deg: float = 25.0,
           search_m: float = 300.0,
           step_m: float = 15.0,
           sustain: int = 3,
           margin_m: float = 60.0, crs=None) -> SitingAdvice:
    """Decide whether an asset sitting here should be repaired or moved.

    Walks upslope from the asset sampling the slope. A run of consecutive steep
    samples is a source zone; if one is found within the search distance, the asset
    is considered to be below it and relocation above the zone is advised.
    """
    dx, dy = _pixel_size_m(transform, crs)
    slope, aspect = slope_aspect_deg(dem, transform, crs)
    z_asset = _sample(dem, row, col)
    down = np.radians(_sample(aspect, row, col))
    # Upslope is the OPPOSITE of the downslope aspect: both components negate.
    # Getting this wrong walks downhill and inverts the whole recommendation, so
    # test_a_steep_slope_upslope_forces_relocation pins it.
    up_east, up_north = -np.sin(down), -np.cos(down)
    per_m_row, per_m_col = -up_north / dy, up_east / dx

    steep_run = 0
    z_prev = z_asset
    for step in range(1, int(search_m / step_m) + 1):
        dist = step * step_m
        r = row + per_m_row * dist
        c = col + per_m_col * dist
        if not (0 <= r < dem.shape[0] and 0 <= c < dem.shape[1]):
            break
        z_here = _sample(dem, r, c)
        # Only ground that keeps RISING is above the asset. Past a crest the walk
        # starts descending, and the steep slope it then meets is the far side of
        # the ridge - the next valley's headwall, not a source zone above this asset.
        # Without this check the recommendation inverts on real terrain.
        if z_here < z_prev - ASCENT_TOLERANCE_M:
            return SitingAdvice(
                recommendation=REPAIR_IN_PLACE,
                reason=(f"the walk upslope crosses a crest {dist:.0f} m away and then descends; "
                        "there is no source zone above this asset"),
                asset_elevation_m=round(z_asset, 1),
            )
        z_prev = max(z_prev, z_here)
        s = _sample(slope, r, c)
        steep_run = steep_run + 1 if s >= min_source_slope_deg else 0
        if steep_run >= sustain:
            target_dist = dist + margin_m
            rt = row + per_m_row * target_dist
            ct = col + per_m_col * target_dist
            inside = 0 <= rt < dem.shape[0] and 0 <= ct < dem.shape[1]
            z_target = _sample(dem, rt, ct) if inside else z_asset
            return SitingAdvice(
                recommendation=RELOCATE_UPSLOPE,
                reason=(f"a source zone averaging {s:.0f}° lies {dist:.0f} m upslope; the asset "
                        "is in its path"),
                asset_elevation_m=round(z_asset, 1),
                source_distance_m=round(dist, 0),
                source_slope_deg=round(s, 0),
                target_offset_m=round(target_dist, 0),
                target_elevation_gain_m=round(z_target - z_asset, 1),
            )

    return SitingAdvice(
        recommendation=REPAIR_IN_PLACE,
        reason=(f"no slope at or above {min_source_slope_deg:.0f}° was found within "
                f"{search_m:.0f} m upslope"),
        asset_elevation_m=round(z_asset, 1),
    )
