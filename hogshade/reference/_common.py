"""
HogShade: helpers the NumPy twins share: unit vectors, a column view, the legacy luminance weights.
Package: hogshade/reference/_common
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.reference._common"
__version__ = "0.1.0"
__updated__ = "2026-09-27"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def _unit(v: NDArray) -> NDArray:
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def _col(x: NDArray) -> NDArray:
    return np.asarray(x)[..., None]


def luminance(c: NDArray) -> NDArray:
    return 0.3 * c[..., 0] + 0.6 * c[..., 1] + 0.1 * c[..., 2]
