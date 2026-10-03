"""
HogShade: tangent-space normal maps: decode and encode, the DirectX to OpenGL flip, renormalisation, the two-channel
runtime form (X, Y; Z reconstructed by the host).
Package: hogshade/texture_cook/normals

The repository's convention is OpenGL +Y (the content standard); a source stated ``directx-y`` in its sidecar has
its green channel inverted here and the manifest records that it was.
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.texture_cook.normals"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

CONVENTIONS = ("opengl+y", "directx-y")


def decode(unit_rgb: NDArray[np.float32]) -> NDArray[np.float32]:
    """[0, 1] encoded XYZ to unit vectors in [-1, 1], renormalised (a flat map decodes to (0, 0, 1))."""
    xyz = np.asarray(unit_rgb[..., :3], dtype=np.float32) * 2.0 - 1.0
    norm = np.linalg.norm(xyz, axis=-1, keepdims=True)
    return np.where(norm > 1e-6, xyz / np.maximum(norm, 1e-6), np.array([0.0, 0.0, 1.0], np.float32)).astype(np.float32)


def encode(xyz: NDArray[np.float32]) -> NDArray[np.float32]:
    """Unit vectors to the [0, 1] encoding."""
    return (np.clip(np.asarray(xyz, dtype=np.float32), -1.0, 1.0) * 0.5 + 0.5).astype(np.float32)


def to_opengl(xyz: NDArray[np.float32], convention: str) -> NDArray[np.float32]:
    """The source's decoded normals in the repository's convention: a DirectX source has its Y inverted."""
    if convention not in CONVENTIONS:
        raise ValueError(f"normal convention {convention!r} is not one of {CONVENTIONS}")
    if convention == "opengl+y":
        return xyz
    out = np.array(xyz, dtype=np.float32, copy=True)
    out[..., 1] *= -1.0
    return out


def to_rg(encoded: NDArray[np.float32]) -> NDArray[np.float32]:
    """The runtime two-channel form: the encoded X and Y; the host reconstructs Z as sqrt(1 - x² - y²)."""
    return np.ascontiguousarray(encoded[..., :2], dtype=np.float32)


def reconstruct_z(rg_unit: NDArray[np.float32]) -> NDArray[np.float32]:
    """What the host does with the two channels: decode, reconstruct Z, the unit normal ``(H, W, 3)``."""
    xy = np.asarray(rg_unit, dtype=np.float32) * 2.0 - 1.0
    z = np.sqrt(np.clip(1.0 - np.sum(xy * xy, axis=-1, keepdims=True), 0.0, 1.0))
    return np.concatenate([xy, z], axis=-1).astype(np.float32)
