"""
HogShade: NumPy mirror of core/models/lambert.wgsl, the floor model, row by row.
Package: hogshade/reference/lambert

Diffuse only: radiance from one light is albedo / pi times the clamped cosine times the light's radiance;
the environment term is albedo times the irradiance over pi times AO. tests/core/test_lambert_gpu.py
compares these with the GPU.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from hogshade.core_constants import INV_PI
from hogshade.reference import lighting
from hogshade.reference._common import _unit

_MODULE_NAME = "hogshade.reference.lambert"
__version__ = "0.1.0"
__updated__ = "2026-09-27"


def env_lookup(normal_ws: NDArray, view_ws: NDArray) -> NDArray:
    """(n.v clamped, roughness 1): Lambert reports the unbiased roughness of one."""
    n_dot_v = np.maximum((_unit(normal_ws) * _unit(view_ws)).sum(-1), 0.0)
    return np.stack([n_dot_v, np.ones_like(n_dot_v)], axis=-1)


def evaluate_light(base_color: NDArray, normal_ws: NDArray, position_ws: NDArray, light: NDArray) -> NDArray:
    """lambert_evaluate_light for (n, 16) light rows at (n, 3) positions: (n, 3) radiance."""
    l_ws, attenuation, valid = lighting.incident(light, position_ws)
    n_dot_l = np.maximum((_unit(normal_ws) * l_ws).sum(-1), 0.0)
    radiance = lighting.radiance(light, attenuation)
    out = base_color * INV_PI * n_dot_l[:, None] * radiance
    return np.where(valid[:, None], out, 0.0)


def evaluate_env(base_color: NDArray, ao: NDArray, irradiance_over_pi: NDArray) -> NDArray:
    """lambert_evaluate_env: albedo times E/pi times AO."""
    return base_color * irradiance_over_pi * ao[:, None]


if __name__ == "__main__":
    row = lighting.light_rows(
        np.array([1]),
        np.zeros((1, 3)),
        np.array([[0.0, -1.0, 0.0]]),
        np.array([3.0]),
        np.ones((1, 3)),
        np.array([0.0]),
        np.array([[0.95, 0.8]]),
        np.array([1.0]),
    )
    print(
        "directional from above on a flat grey:",
        evaluate_light(np.full((1, 3), 0.5), np.array([[0, 1.0, 0]]), np.zeros((1, 3)), row),
    )
