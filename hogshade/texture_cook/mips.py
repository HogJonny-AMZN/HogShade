"""
HogShade: mip chains by 2x2 box average, in linear space for colour and renormalised for normals.
Package: hogshade/texture_cook/mips

A level's size is the DDS convention, ``max(side // 2, 1)``, so an odd trailing row or column is dropped; a source
that is not a power of two still cooks (the manifest says so); the chain ends at 1x1.
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

from hogshade.texture_cook.colour import linear_to_srgb, srgb_to_linear

_MODULE_NAME = "hogshade.texture_cook.mips"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def halve(level: NDArray[np.float32]) -> NDArray[np.float32]:
    """
    One 2x2 box average of ``(H, W, C)`` float32 to the next DDS mip size, ``max(side // 2, 1)``: an odd trailing
    row or column is dropped (the DDS convention every host assumes when it computes a level's size); a 1-side
    stays 1.
    """
    h, w = level.shape[:2]
    if h == 1 and w == 1:
        return level
    a = level[: (h // 2) * 2 if h > 1 else 1, : (w // 2) * 2 if w > 1 else 1]
    hh, ww = a.shape[0], a.shape[1]
    if hh > 1:
        a = a.reshape(hh // 2, 2, ww, -1).mean(axis=1)
    if ww > 1:
        a = a.reshape(a.shape[0], ww // 2, 2, -1).mean(axis=2)
    return a.astype(np.float32)


def chain(level0: NDArray[np.float32]) -> list[NDArray[np.float32]]:
    """Every level from ``level0`` down to 1x1, each the box average of the one above."""
    levels = [np.asarray(level0, dtype=np.float32)]
    while levels[-1].shape[0] > 1 or levels[-1].shape[1] > 1:
        levels.append(halve(levels[-1]))
    return levels


def colour_chain(srgb_unit: NDArray[np.float32]) -> list[NDArray[np.float32]]:
    """The chain of an sRGB-encoded image, averaged in linear and re-encoded per level (alpha, if any, raw)."""
    rgb, alpha = srgb_unit[..., :3], srgb_unit[..., 3:]
    linear_levels = chain(srgb_to_linear(rgb))
    alpha_levels = chain(alpha) if alpha.shape[-1] else [None] * len(linear_levels)
    out = []
    for lin, a in zip(linear_levels, alpha_levels):
        enc = linear_to_srgb(lin)
        out.append(np.concatenate([enc, a], axis=-1) if a is not None else enc)
    return out


def data_chain(unit: NDArray[np.float32]) -> list[NDArray[np.float32]]:
    """The chain of raw data (roughness, masks, height): a plain box average."""
    return chain(unit)


def normal_chain(xyz: NDArray[np.float32]) -> list[NDArray[np.float32]]:
    """The chain of decoded unit normals ``(H, W, 3)`` in [-1, 1]: averaged, then renormalised per level."""
    levels = [np.asarray(xyz, dtype=np.float32)]
    while levels[-1].shape[0] > 1 or levels[-1].shape[1] > 1:
        avg = halve(levels[-1])
        norm = np.linalg.norm(avg, axis=-1, keepdims=True)
        levels.append(
            np.where(norm > 1e-6, avg / np.maximum(norm, 1e-6), np.array([0.0, 0.0, 1.0], np.float32)).astype(
                np.float32
            )
        )
    return levels
