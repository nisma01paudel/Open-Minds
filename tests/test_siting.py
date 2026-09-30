"""Siting advice must be right on terrain we can reason about by hand."""
import numpy as np
import pytest
from affine import Affine

from pahiro.siting import REPAIR_IN_PLACE, RELOCATE_UPSLOPE, advise, slope_aspect_deg

# A projected transform with 1 m pixels: row 0 is the TOP (north) of the scene.
TRANSFORM = Affine.translation(500_000.0, 3_070_000.0) * Affine.scale(1.0, -1.0)


class _Geographic:
    """Minimal stand-in for a rasterio CRS in a geographic coordinate system."""
    is_geographic = True


# The same terrain served in EPSG:4326, where the transform units are DEGREES.
GEO_TRANSFORM = Affine.translation(85.0, 27.8) * Affine.scale(1 / 111_320, -1 / 110_540)


def test_geographic_pixel_size_is_converted_to_metres():
    """A degree must not be treated as a metre: Copernicus DEM is EPSG:4326."""
    from pahiro.siting import _pixel_size_m

    dx, dy = _pixel_size_m(GEO_TRANSFORM, _Geographic())
    assert dy == pytest.approx(1.0, abs=0.15), "one degree of latitude is ~110.5 km"
    assert dx < dy, "a degree of longitude is shorter than a degree of latitude"
    # without the CRS we would be off by five orders of magnitude
    raw_dx, raw_dy = _pixel_size_m(GEO_TRANSFORM, None)
    assert raw_dy < 1e-4


def test_slope_is_identical_in_projected_and_geographic_form():
    """The same hillside must yield the same slope whichever CRS it arrives in."""
    projected = ramp(0.5)
    geographic = ramp(0.5)
    s_proj, _ = slope_aspect_deg(projected, TRANSFORM, None)
    s_geo, _ = slope_aspect_deg(geographic, GEO_TRANSFORM, _Geographic())
    assert s_proj[10, 10] == pytest.approx(s_geo[10, 10], abs=1.0)


def flat():
    return np.full((200, 200), 1000.0, dtype="float64")


def ramp(grade=0.5):
    """Ground rising to the north: row 0 highest, so upslope is north (row decreasing)."""
    dem = flat()
    for r in range(200):
        dem[r, :] = 1000.0 - grade * r
    return dem


def test_flat_ground_is_repair_in_place():
    a = advise(flat(), TRANSFORM, row=150, col=100)
    assert a.recommendation == REPAIR_IN_PLACE
    assert "no slope" in a.reason
    assert a.caveats and "geotechnical" in a.caveats[0]


def test_a_steep_slope_upslope_forces_relocation():
    """The asset sits at the foot of a 50% ramp: the source zone is directly upslope."""
    a = advise(ramp(0.5), TRANSFORM, row=180, col=100)
    assert a.recommendation == RELOCATE_UPSLOPE
    assert a.source_distance_m and 0 < a.source_distance_m <= 300
    assert a.target_offset_m > a.source_distance_m, "the target must clear the source zone"
    assert a.target_elevation_gain_m > 0, "moving upslope must gain elevation"
    assert a.source_slope_deg >= 25


def test_a_gentle_slope_stays_in_place():
    a = advise(ramp(0.05), TRANSFORM, row=180, col=100)
    assert a.recommendation == REPAIR_IN_PLACE


def test_slope_and_aspect_point_downhill():
    slope, aspect = slope_aspect_deg(ramp(0.5), TRANSFORM)
    assert slope[10, 10] == pytest.approx(26.6, abs=1.5)
    # ground falls toward the south, so the downslope aspect points ~180 degrees
    assert aspect[10, 10] == pytest.approx(180.0, abs=5.0)


def test_advice_is_always_caveated():
    for dem in (flat(), ramp(0.5)):
        a = advise(dem, TRANSFORM, 150, 100)
        assert a.caveats and "not modelled" in a.caveats[0]


def test_describe_is_readable_and_specific():
    a = advise(ramp(0.5), TRANSFORM, row=180, col=100)
    text = a.describe()
    assert "relocate the alignment" in text and "upslope" in text and "°" in text


def ridge():
    """A gentle south approach (5.7 deg) rising to a crest at row 100, then a steep
    north face (45 deg). The asset sits on the gentle side, so relocating it would
    move it onto the far side of its own ridge."""
    dem = np.full((200, 200), 1000.0, dtype="float64")
    for r in range(200):
        dem[r, :] = (1000.0 - 1.0 * (100 - r)) if r < 100 else (1000.0 - 0.1 * (r - 100))
    return dem


def test_the_ridge_fixture_is_the_shape_it_claims():
    dem = ridge()
    assert dem[100].mean() > dem[180].mean(), "the crest is above the asset"
    assert dem[100].mean() > dem[20].mean(), "the far side falls away steeply"
    slope, _ = slope_aspect_deg(dem, TRANSFORM)
    assert slope[180, 100] < 15, "the approach is gentle"
    assert slope[20, 100] > 40, "the far face is steep"


def test_a_slope_beyond_a_crest_is_not_a_source_zone():
    """The flaw this pins: past a crest, the walk meets the NEXT valley's headwall.

    Without the continuous-ascent rule the asset is told to relocate upslope onto the
    far side of its own ridge - advice that is not just wrong but inverted, and it was
    found only by running on real terrain.
    """
    a = advise(ridge(), TRANSFORM, row=180, col=100)
    assert a.recommendation == REPAIR_IN_PLACE
    assert "crest" in a.reason


def test_a_source_zone_on_rising_ground_still_relocates_with_positive_gain():
    a = advise(ramp(0.5), TRANSFORM, row=180, col=100)
    assert a.recommendation == RELOCATE_UPSLOPE
    assert a.target_elevation_gain_m > 0
