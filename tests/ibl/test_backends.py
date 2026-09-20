"""
HogShade: the numba prefilter agrees with the NumPy one (E2 plan, tasks 2 and 3).
Package: tests/ibl/test_backends
"""

from __future__ import annotations

import numpy as np
import pytest

from hogshade.ibl import prefilter
from hogshade.ibl.cook import furnace
from hogshade.ibl.cubemap import equirect_pyramid, equirect_texel_directions

needs_numba = pytest.mark.skipif(not prefilter.HAVE_NUMBA, reason="numba not installed (uv sync --extra jit)")


def _env() -> np.ndarray:
    d = equirect_texel_directions(128, 64)
    img = 0.5 + 0.5 * d[..., 1:2] + 0.3 * np.sign(np.sin(6.0 * np.pi * d[..., 0:1])) * (d[..., 2:3] > 0)
    rgb = np.concatenate([img, img * 0.8, img * 0.6], axis=-1).astype(np.float32)
    rgb[20:24, 60:68] = 40.0  # a small bright source so mip selection matters
    return rgb


def test_resolve_backend() -> None:
    assert prefilter.resolve_backend("numpy") == "numpy"
    assert prefilter.resolve_backend("auto") in ("numpy", "numba")
    with pytest.raises(ValueError):
        prefilter.resolve_backend("cuda")


@needs_numba
def test_numba_matches_numpy() -> None:
    pyramid = equirect_pyramid(_env())
    a = prefilter.prefilter_specular(pyramid, base=32, samples=128, backend="numpy")
    b = prefilter.prefilter_specular(pyramid, base=32, samples=128, backend="numba")
    assert len(a) == len(b)
    for m, (x, y) in enumerate(zip(a, b, strict=True)):
        scale = np.abs(x).max() + 1e-6
        assert np.abs(x - y).max() / scale < 1e-4, f"mip {m} differs by {np.abs(x - y).max() / scale}"


@needs_numba
def test_furnace_on_both_backends() -> None:
    for backend in ("numpy", "numba"):
        white = np.ones((64, 128, 3), dtype=np.float32)
        mips = prefilter.prefilter_specular(equirect_pyramid(white), base=16, samples=128, backend=backend)
        assert max(float(np.abs(m - 1.0).max()) for m in mips) < 1e-4, backend
    assert furnace(base=16, samples=128)["passed"]


@needs_numba
def test_numba_is_deterministic() -> None:
    pyramid = equirect_pyramid(_env())
    a = prefilter.prefilter_specular(pyramid, base=16, samples=256, backend="numba")
    b = prefilter.prefilter_specular(pyramid, base=16, samples=256, backend="numba")
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)
