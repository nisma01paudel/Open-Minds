"""The 360-degree panorama: real terrain shape, and honest about being a silhouette."""
import numpy as np
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rp", ROOT / "scripts/render_panorama.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_sky_does_not_depend_on_the_horizon():
    """The artefact this exists for.

    The first render tied sky brightness to the horizon height, so every column came out a different
    shade and the whole sky was covered in hard vertical stripes. It looked like a rendering of
    something; it was a bug in the shader presented as the mountain.
    """
    src = (ROOT / "scripts/render_panorama.py").read_text()
    assert "sky_frac = np.clip((rows - top)" in src, (
        "the sky is tied to the horizon again, which bands it by column")
    assert "lat_frac" not in src or "sky" not in src.split("lat_frac")[1][:200], (
        "a horizon-dependent factor is back in the sky")


def test_it_renders_the_shape_of_the_ground_not_a_flat_line():
    """A panorama of a real valley must have a horizon that varies, or the DEM is not being read."""
    m = _mod()
    meta, grid = m.load_dem()
    img, horizon, eye = m.render(meta, grid, 28.35, 83.57, width=360)
    assert 0 < eye < 9000, f"eye elevation {eye} m is not plausible for Nepal"
    assert horizon.max() - horizon.min() > 5.0, (
        "the horizon is nearly flat - that is a failed ray march, not a valley")
    assert img.shape == (180, 360, 3)
    assert img.dtype == np.uint8


def test_it_is_two_to_one_so_a_vr_viewer_can_open_it():
    """Equirectangular is 2:1. Anything else will be distorted on a sphere."""
    m = _mod()
    meta, grid = m.load_dem()
    img, _, _ = m.render(meta, grid, 28.35, 83.57, width=512)
    assert img.shape[1] == 2 * img.shape[0]


def test_it_says_it_is_a_silhouette():
    """It shows shape from a ~1 km grid. It is not a photograph and must not imply one."""
    src = (ROOT / "scripts/render_panorama.py").read_text()
    assert "silhouette" in src
    assert "no trees, no buildings" in src


def test_it_does_not_sample_closer_than_the_grid_resolves():
    """The bug that made Manaslu a vertical cliff.

    The ray march began about 25 m from the eye. On a ~1 km grid, one adjacent cell standing 100 m
    higher reads as a wall at 76 degrees, so the Manaslu panorama came out with an 85-degree
    horizon - not a valley, the quantisation of the grid mistaken for a cliff. Beni hid it; only
    checking all six exposed it.
    """
    m = _mod()
    assert m.MIN_RANGE_M >= 400.0, "the ray march is sampling below the grid's own resolution"
    meta, grid = m.load_dem()
    for name, lat, lon in [("kathmandu", 27.75, 85.32), ("manaslu", 28.60, 84.65),
                           ("annapurna", 28.50, 84.00), ("mustang", 28.85, 83.90),
                           ("khumbu", 27.80, 86.80), ("langtang", 28.15, 85.50)]:
        _, hz, eye = m.render(meta, grid, lat, lon, width=360)
        assert hz.max() < 75.0, (
            f"{name} has a horizon at {hz.max():.0f} degrees - that is grid quantisation, "
            f"not terrain")


def test_the_six_regions_are_ordered_as_the_country_is():
    """A sanity check on the whole set, because one plausible-looking point proves nothing.

    Kathmandu sits in a broad low valley; Annapurna and Manaslu sit in deep high gorges. If the
    renderer ever reports the valley as steeper than the gorges, something is wrong with it.
    """
    m = _mod()
    meta, grid = m.load_dem()
    _, kath, _ = m.render(meta, grid, 27.75, 85.32, width=360)
    _, manaslu, _ = m.render(meta, grid, 28.60, 84.65, width=360)
    assert manaslu.max() > kath.max(), (
        "the Manaslu gorge renders flatter than the Kathmandu valley")
