"""
HogShade: NumPy mirror of core/lighting.wgsl: incident geometry and radiance for one light per row.
Package: hogshade/reference/lighting

A light is a (n, 16) float array in the test layout tests/core/test_lighting_gpu.py uses:
kind, position(3), direction(3), intensity, color(3), range, cone_cos(2), shadow, pad.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.reference.lighting"
__version__ = "0.1.0"
__updated__ = "2026-09-25"

KIND_OFF, KIND_DIRECTIONAL, KIND_POINT, KIND_SPOT = 0, 1, 2, 3


def light_rows(
    kind: NDArray,
    position: NDArray,
    direction: NDArray,
    intensity: NDArray,
    color: NDArray,
    range_: NDArray,
    cone_cos: NDArray,
    shadow: NDArray,
) -> NDArray:
    """Pack per-light arrays into the (n, 16) test layout."""
    n = len(kind)
    rows = np.zeros((n, 16), dtype=np.float64)
    rows[:, 0] = kind
    rows[:, 1:4] = position
    rows[:, 4:7] = direction
    rows[:, 7] = intensity
    rows[:, 8:11] = color
    rows[:, 11] = range_
    rows[:, 12:14] = cone_cos
    rows[:, 14] = shadow
    return rows


def incident(light: NDArray, position_ws: NDArray) -> tuple[NDArray, NDArray, NDArray]:
    """(l_ws, attenuation, valid) for each row, the lighting_incident struct."""
    kind = light[:, 0].astype(int)
    pos, direction = light[:, 1:4], light[:, 4:7]
    rng_ = light[:, 11]
    inner, outer, shadow = light[:, 12], light[:, 13], light[:, 14]
    unit_dir = direction / np.maximum(np.linalg.norm(direction, axis=-1, keepdims=True), 1e-12)
    to_light = pos - position_ws
    dist2 = np.maximum((to_light * to_light).sum(-1), 1e-8)
    dist = np.sqrt(dist2)
    l_ws = np.where((kind == KIND_DIRECTIONAL)[:, None], unit_dir, to_light / dist[:, None])
    falloff = 1.0 / dist2
    ratio = np.where(rng_ > 0, dist / np.where(rng_ > 0, rng_, 1.0), 0.0)
    window = np.clip(1.0 - ratio**4, 0.0, 1.0)
    falloff = np.where(rng_ > 0, falloff * window * window, falloff)
    cos_angle = (-l_ws * unit_dir).sum(-1)
    cone = np.clip((cos_angle - outer) / np.maximum(inner - outer, 1e-4), 0.0, 1.0) ** 2
    att = np.where(kind == KIND_DIRECTIONAL, shadow, falloff * np.where(kind == KIND_SPOT, cone, 1.0) * shadow)
    valid = kind != KIND_OFF
    return l_ws, np.where(valid, att, 0.0), valid


def radiance(light: NDArray, attenuation: NDArray) -> NDArray:
    """color x intensity x attenuation, (n, 3)."""
    return light[:, 8:11] * (light[:, 7] * attenuation)[:, None]


if __name__ == "__main__":
    row = light_rows(
        np.array([2]),
        np.zeros((1, 3)),
        np.array([[0, -1, 0.0]]),
        np.array([2.0]),
        np.ones((1, 3)),
        np.array([10.0]),
        np.array([[0.95, 0.8]]),
        np.array([1.0]),
    )
    l, a, v = incident(row, np.array([[0, -2, 0.0]]))
    print("point light 2 units away:", l, a, v)
