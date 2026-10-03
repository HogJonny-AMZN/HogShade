"""
HogShade: the sRGB transfer on arrays, the one definition the cook uses for mips in linear space.
Package: hogshade/texture_cook/colour
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.texture_cook.colour"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def srgb_to_linear(x: NDArray) -> NDArray[np.float32]:
    """The sRGB electro-optical transfer on [0, 1] values (IEC 61966-2-1), float32 out."""
    x = np.asarray(x, dtype=np.float32)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(x: NDArray) -> NDArray[np.float32]:
    """The inverse transfer on [0, 1] linear values, float32 out."""
    x = np.clip(np.asarray(x, dtype=np.float32), 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055).astype(np.float32)


def to_unit(image: NDArray) -> NDArray[np.float32]:
    """``uint8`` or ``uint16`` samples as [0, 1] float32; a float array is clipped to [0, 1]."""
    a = np.asarray(image)
    if a.dtype == np.uint8:
        return a.astype(np.float32) / 255.0
    if a.dtype == np.uint16:
        return a.astype(np.float32) / 65535.0
    return np.clip(a.astype(np.float32), 0.0, 1.0)


def to_uint8(unit: NDArray) -> NDArray[np.uint8]:
    """[0, 1] float to ``uint8``, rounded to nearest."""
    return np.clip(np.rint(np.asarray(unit, dtype=np.float32) * 255.0), 0, 255).astype(np.uint8)


def to_uint16(unit: NDArray) -> NDArray[np.uint16]:
    """[0, 1] float to ``uint16``, rounded to nearest."""
    return np.clip(np.rint(np.asarray(unit, dtype=np.float32) * 65535.0), 0, 65535).astype(np.uint16)
