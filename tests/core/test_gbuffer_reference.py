"""
HogShade: the octahedral mapping round-trips on both hemispheres, and the NumPy mirror matches the WGSL text.
Package: tests/core/test_gbuffer_reference

Settles the review question on gbuffer_oct_decode's select operand order with numbers: if the
folded-hemisphere signs were reversed, every normal with z < 0 would decode to the wrong direction
and the round-trip below would fail.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from hogshade.reference import gbuffer as ref

ROOT = Path(__file__).resolve().parents[2]


def _unit(n: int, seed: int = 0) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def test_octahedral_round_trip_both_hemispheres() -> None:
    v = _unit(20000)
    back = ref.oct_decode(ref.oct_encode(v))
    err = np.abs(back - v).max()
    assert err < 1e-9, err
    lower = v[v[:, 2] < 0]
    assert len(lower) > 5000
    assert np.abs(ref.oct_decode(ref.oct_encode(lower)) - lower).max() < 1e-9


def test_octahedral_axes_and_corners() -> None:
    axes = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=np.float64)
    assert np.abs(ref.oct_decode(ref.oct_encode(axes)) - axes).max() < 1e-9
    # +Z is the centre of the square, -Z the corners
    assert np.allclose(ref.oct_encode(axes[4]), [0.5, 0.5])


def test_reversed_signs_would_fail() -> None:
    """The alternative the review proposed: +t for non-negative components. It does not round-trip."""
    v = _unit(2000, seed=1)
    v = v[v[:, 2] < 0]
    p = ref.oct_encode(v) * 2.0 - 1.0
    z = 1.0 - np.abs(p[:, 0]) - np.abs(p[:, 1])
    t = np.clip(-z, 0.0, 1.0)
    sx = np.where(p[:, 0] >= 0.0, t, -t)  # reversed
    sy = np.where(p[:, 1] >= 0.0, t, -t)
    n = np.stack([p[:, 0] + sx, p[:, 1] + sy, z], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    assert np.abs(n - v).max() > 0.5


def test_wgsl_decode_uses_the_same_operand_order() -> None:
    wgsl = (ROOT / "core" / "gbuffer.wgsl").read_text(encoding="utf-8")
    body = wgsl[wgsl.index("fn gbuffer_oct_decode") : wgsl.index("fn gbuffer_encode_adr002")]
    assert re.search(r"select\(t,\s*-t,\s*n\.x\s*>=\s*0\.0\)", body), "sx must be -t when n.x >= 0"
    assert re.search(r"select\(t,\s*-t,\s*n\.y\s*>=\s*0\.0\)", body), "sy must be -t when n.y >= 0"


def test_deferred_f0_reconstruction() -> None:
    base = np.array([[0.8, 0.2, 0.1]])
    assert np.allclose(ref.reconstruct_specular_f0(base, np.array([0.0])), [[0.04, 0.04, 0.04]])
    assert np.allclose(ref.reconstruct_specular_f0(base, np.array([1.0])), base)
