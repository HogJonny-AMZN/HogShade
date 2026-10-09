"""
HogShade: height maps at the source's precision: a 16-bit PNG, a half or float EXR; the runtime format each gets,
and the opt-in normalisation with its range recorded.
Package: hogshade/texture_cook/height

The T2 spec's "Height": 16-bit PNG to ``R16_UNORM`` with every step kept; half EXR to ``R16_FLOAT``; float EXR to
``R32_FLOAT``; 8-bit to ``R8_UNORM`` (BC4 only there). The cook never squeezes a float into 8 bits, and normalises
to ``R16_UNORM`` only when asked, writing ``min`` and ``max`` into the manifest.
"""

from __future__ import annotations

import logging as _logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from hogshade.texture_cook.mips import chain as _chain

_MODULE_NAME = "hogshade.texture_cook.height"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)


@dataclass(frozen=True)
class Height:
    """A height map as read: the samples, their source precision, and the runtime format they keep."""

    samples: NDArray  # (H, W) uint8, uint16, float16 or float32
    precision: str  # "8-bit", "16-bit", "half", "float"
    runtime: str  # "R8_UNORM", "R16_UNORM", "R16_FLOAT", "R32_FLOAT"


def read_exr_channel(path: Path, channel: str | None = None) -> tuple[NDArray[np.float16] | NDArray[np.float32], str]:
    """
    One channel of an EXR (``channel``, else ``R``, else the first) at its stored precision: ``float16`` for a
    HALF channel, ``float32`` for FLOAT, with the precision name. OpenEXR is a dependency already (the IBL cook);
    ``ImportError`` without it, ``ValueError`` for an EXR without the channel, OpenEXR's own errors for a bad file.
    """
    import OpenEXR

    with OpenEXR.File(str(path)) as f:
        channels = f.channels()
        if not channels:
            raise ValueError(f"EXR {path} has no channels")
        if channel is None:
            channel = "R" if "R" in channels else next(iter(channels))
        if channel not in channels:
            raise ValueError(f"EXR {path} has no channel {channel!r}: {list(channels)}")
        pixels = np.asarray(channels[channel].pixels)
    if pixels.ndim == 3:
        pixels = pixels[..., 0]
    if pixels.dtype == np.float16:
        return pixels, "half"
    return pixels.astype(np.float32), "float"


def from_array(samples: NDArray, precision: str | None = None) -> Height:
    """A ``Height`` from read samples: the precision from the dtype unless stated, the runtime from the table."""
    s = np.asarray(samples)
    if s.ndim == 3:
        s = s[..., 0]
    if precision is None:
        precision = {np.dtype(np.uint8): "8-bit", np.dtype(np.uint16): "16-bit", np.dtype(np.float16): "half"}.get(
            s.dtype, "float"
        )
    runtime = {"8-bit": "R8_UNORM", "16-bit": "R16_UNORM", "half": "R16_FLOAT", "float": "R32_FLOAT"}[precision]
    return Height(samples=s, precision=precision, runtime=runtime)


def normalise(height: Height) -> tuple[Height, dict[str, float]]:
    """
    A float height mapped to ``R16_UNORM`` over its own range (the extremes to 0 and 65535), with the range
    recorded; an integer height is returned as it is with an empty record.
    """
    s = height.samples
    if s.dtype.kind != "f":
        return height, {}
    lo, hi = float(np.nanmin(s)), float(np.nanmax(s))
    span = hi - lo if hi > lo else 1.0
    unit = (s.astype(np.float32) - lo) / span
    out = np.clip(np.rint(unit * 65535.0), 0, 65535).astype(np.uint16)
    _LOGGER.info(f"height normalised from [{lo:g}, {hi:g}] to R16_UNORM")
    return Height(samples=out, precision="16-bit", runtime="R16_UNORM"), {"min": lo, "max": hi}


def chain(height: Height) -> list[NDArray]:
    """The mip chain in the source's precision: box averages, cast back to the samples' dtype."""
    s = height.samples
    if s.dtype.kind == "f":
        levels = _chain(s.astype(np.float32)[..., None])
        return [lvl[..., 0].astype(s.dtype) for lvl in levels]
    scale = 255.0 if s.dtype == np.uint8 else 65535.0
    levels = _chain((s.astype(np.float32) / scale)[..., None])
    return [np.clip(np.rint(lvl[..., 0] * scale), 0, scale).astype(s.dtype) for lvl in levels]
