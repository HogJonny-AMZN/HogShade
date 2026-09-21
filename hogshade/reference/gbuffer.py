"""
HogShade: NumPy mirror of core/gbuffer.wgsl (octahedral normals, ADR-002 encode and decode).
Package: hogshade/reference/gbuffer

The WGSL uses select(false_value, true_value, condition); every branch here is written as np.where
with the same operand order so the two can be read side by side.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from hogshade.core_constants import DIELECTRIC_F0

_MODULE_NAME = "hogshade.reference.gbuffer"
__version__ = "0.1.0"
__updated__ = "2026-09-21"


def oct_encode(n: NDArray) -> NDArray:
    """Unit vectors (..., 3) to octahedral (..., 2) in [0, 1]. Mirrors gbuffer_oct_encode."""
    n = np.asarray(n, dtype=np.float64)
    l1 = np.abs(n).sum(axis=-1, keepdims=True)
    p = n[..., :2] / np.maximum(l1, 1e-8)
    sx = np.where(p[..., 0:1] >= 0.0, 1.0, -1.0)
    sy = np.where(p[..., 1:2] >= 0.0, 1.0, -1.0)
    folded = (1.0 - np.abs(p[..., ::-1])) * np.concatenate([sx, sy], axis=-1)
    p = np.where(n[..., 2:3] < 0.0, folded, p)
    return p * 0.5 + 0.5


def oct_decode(e: NDArray) -> NDArray:
    """Octahedral (..., 2) back to unit vectors (..., 3). Mirrors gbuffer_oct_decode."""
    p = np.asarray(e, dtype=np.float64) * 2.0 - 1.0
    z = 1.0 - np.abs(p[..., 0]) - np.abs(p[..., 1])
    t = np.clip(-z, 0.0, 1.0)
    # WGSL: sx = select(t, -t, n.x >= 0.0)  ->  -t when n.x >= 0, else t
    sx = np.where(p[..., 0] >= 0.0, -t, t)
    sy = np.where(p[..., 1] >= 0.0, -t, t)
    n = np.stack([p[..., 0] + sx, p[..., 1] + sy, z], axis=-1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def reconstruct_specular_f0(base_color: NDArray, metalness: NDArray) -> NDArray:
    """Deferred F0: mix(DIELECTRIC_F0, base_color, metalness). Mirrors gbuffer_reconstruct."""
    base_color = np.asarray(base_color, dtype=np.float64)
    m = np.asarray(metalness, dtype=np.float64)[..., None]
    return DIELECTRIC_F0 * (1.0 - m) + base_color * m


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    v = rng.normal(size=(8, 3))
    v /= np.linalg.norm(v, axis=-1, keepdims=True)
    back = oct_decode(oct_encode(v))
    print("max round-trip error:", np.abs(back - v).max())
