"""
HogShade: test helper: frames exactly as the oracles expect them, so the comparison logic is tested without a GPU.
Package: tests/compare/ideal_frames

The frames are built from the oracle's own probe (the geometry is checked separately, against pixels whose answer is
worked out by hand in ``test_oracles``), so a pass means the comparison logic is right; a deliberately wrong frame must
fail. Shared by ``test_oracles`` and ``test_runner``; not a test module.
"""

from __future__ import annotations

import numpy as np

from hogshade.compare import oracles
from hogshade.compare.captureset import CaptureSet
from hogshade.compare.request import CaptureRequest
from hogshade.testdata import synthetic
from hogshade.texture_cook.colour import srgb_to_linear

MAP = synthetic.SIZE

#: The debug view each synthetic map is read in, and whether it shows as grey (a one-channel map) or colour.
VIEWS = {8: ("_R", True), 7: ("_M", True), 9: ("_AO", True), 1: ("_BC", False)}
NORMAL_VIEW = 11


def capture(frame: np.ndarray, coverage: np.ndarray, request: CaptureRequest) -> CaptureSet:
    return CaptureSet(None, request, None, frame.astype(np.float32), None, coverage)  # type: ignore[arg-type]


def all_pixels(request: CaptureRequest) -> oracles.Probe:
    """Every probe-able pixel of the picture (stride 1)."""
    width, height = request.size
    blank = capture(np.zeros((height, width, 3)), np.ones((height, width), dtype=bool), request)
    return oracles.probe(blank, stride=1)


def _filled(request: CaptureRequest, p: oracles.Probe, value: np.ndarray) -> CaptureSet:
    width, height = request.size
    frame = np.zeros((height, width, 3))
    frame[p.rows, p.cols] = value
    coverage = np.zeros((height, width), dtype=bool)
    coverage[p.rows, p.cols] = True
    return capture(frame, coverage, request)


def ideal_texel(request: CaptureRequest, suffix: str, gray: bool, data_range: float = 1.0) -> CaptureSet:
    p = all_pixels(request)
    image = synthetic.render_map(suffix, None, MAP)
    cols, rows = oracles._texels(p.u, p.v, MAP)
    texel = image[rows, cols].astype(np.float64) / 255.0
    value = np.repeat(texel[:, None], 3, axis=1) if gray else srgb_to_linear(texel)
    return _filled(request, p, value * data_range)


def normals(request: CaptureRequest, p: oracles.Probe, flip_green: bool = False) -> np.ndarray:
    """The world normals the authored normal map produces at the probe's pixels (green flipped on request)."""
    image = synthetic.render_map("_N", None, MAP)
    cols, rows = oracles._texels(p.u, p.v, MAP)
    rg = image[rows, cols][:, :2].astype(np.float64) / 255.0 * 2.0 - 1.0
    green = -rg[:, 1] if flip_green else rg[:, 1]
    ts = np.stack([rg[:, 0], green, np.sqrt(np.clip(1.0 - (rg**2).sum(1), 0.0, 1.0))], axis=1)
    b = np.cross(p.normal, p.tangent)
    w = ts[:, :1] * p.tangent + ts[:, 1:2] * b + ts[:, 2:3] * p.normal
    return w / np.linalg.norm(w, axis=1, keepdims=True)


def ideal_normal(request: CaptureRequest, data_range: float = 1.0, flip_green: bool = False) -> CaptureSet:
    p = all_pixels(request)
    return _filled(request, p, (normals(request, p, flip_green) * 0.5 + 0.5) * data_range)


def ideal_for(request: CaptureRequest) -> CaptureSet:
    """The ideal capture of ``request``, chosen by its debug view (the synthetic maps and the shading normal)."""
    if request.debug_mode == NORMAL_VIEW:
        return ideal_normal(request)
    suffix, gray = VIEWS[request.debug_mode]
    return ideal_texel(request, suffix, gray)
