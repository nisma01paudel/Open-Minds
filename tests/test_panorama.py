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
