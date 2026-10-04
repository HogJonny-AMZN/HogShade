"""
HogShade: frequency separation as a cook operation, the owner's technique (co3dex, "Image Frequency Separation for
Texture Detail Mapping", 2022): a wrap-padded Gaussian low-pass, the high-pass that recombines exactly under a
linear-light blend, the reconstruction error measured, the macro at a stated low resolution.
Package: hogshade/texture_cook/separate

Everything here is in the image's stored encoding ([0, 1] of the sRGB bytes for a colour map), as the post and
O3DE's ``TextureBlend_LinearLight`` both separate and blend in display space; the shader's recombination then
matches by construction. ``sigma = radius / 2`` reads a Photoshop Gaussian radius; the manifest records both.
"""

from __future__ import annotations

import logging as _logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from hogshade.texture_cook.mips import halve

_MODULE_NAME = "hogshade.texture_cook.separate"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)


@dataclass(frozen=True)
class Separation:
    """The two halves, the recombination and its error."""

    low: NDArray[np.float32]  # the low-pass, full resolution, same encoding as the source
    high: NDArray[np.float32]  # the high-pass about mid-grey, [0, 1], quantised to the 8-bit steps that are written
    recon: NDArray[np.float32]  # saturate(low + 2 * high - 1)
    error_max: float
    error_mean: float
    clipped_texels: int
    sigma: float
    radius: float


def gaussian_kernel(sigma: float) -> NDArray[np.float32]:
    """A normalised 1D Gaussian over ±3 sigma (at least three taps)."""
    if sigma <= 0:
        raise ValueError("sigma is positive")
    half = max(1, int(np.ceil(3.0 * sigma)))
    x = np.arange(-half, half + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / sigma) ** 2).astype(np.float32)
    return k / k.sum()


def lowpass(image: NDArray[np.float32], sigma: float, wrap: bool = True) -> NDArray[np.float32]:
    """
    A separable Gaussian blur of ``(H, W, C)``. With ``wrap`` the image is padded by wrapping before the blur
    (the post's 3x3 tiled canvas), so the result tiles when the source does; otherwise by edge replication.
    """
    k = gaussian_kernel(sigma)
    half = len(k) // 2
    a = np.asarray(image, dtype=np.float32)
    if a.ndim == 2:
        a = a[..., None]
    mode = "wrap" if wrap else "edge"
    padded = np.pad(a, ((half, half), (half, half), (0, 0)), mode=mode)
    # rows then columns; a plain correlation with the symmetric kernel
    h, w, c = a.shape
    tmp = np.zeros((h + 2 * half, w, c), dtype=np.float32)
    scratch = np.empty_like(tmp)  # one temporary for every tap, not one per tap
    for i, kv in enumerate(k):
        np.multiply(padded[:, i : i + w, :], np.float32(kv), out=scratch)
        tmp += scratch
    out = np.zeros((h, w, c), dtype=np.float32)
    scratch = np.empty_like(out)
    for i, kv in enumerate(k):
        np.multiply(tmp[i : i + h, :, :], np.float32(kv), out=scratch)
        out += scratch
    return out


def separate(image: NDArray[np.float32], radius: float, wrap: bool = True) -> Separation:
    """
    The owner's separation of a [0, 1] image: ``low`` is the Gaussian low-pass with ``sigma = radius / 2``;
    ``high = clip((image - low) * 0.5 + 0.5)``; ``recon = clip(low + 2 * high8 - 1)``, the linear-light blend over
    the 8-bit-quantised high-pass; the error is ``|recon - image|``, within one 8-bit step (``1/255``), and
    ``clipped_texels`` counts where the recombination had to clip.
    """
    if radius <= 0:
        raise ValueError("radius is positive")
    src = np.asarray(image, dtype=np.float32)
    if src.ndim == 2:
        src = src[..., None]
    sigma = radius / 2.0
    low = lowpass(src, sigma, wrap)
    # in [0, 1] floats the offset-and-scale cannot leave [0, 1]; what costs is the 8-bit quantisation of the
    # high-pass that is written, so the error is measured through it, as the shader will see it
    high = np.clip((src - low) * 0.5 + 0.5, 0.0, 1.0).astype(np.float32)
    high_q = np.rint(high * 255.0) / 255.0
    recon_raw = low + 2.0 * high_q - 1.0
    clipped = int(np.count_nonzero(np.any((recon_raw < 0.0) | (recon_raw > 1.0), axis=-1)))
    recon = np.clip(recon_raw, 0.0, 1.0)
    err = np.abs(recon - src)
    return Separation(
        low=low,
        high=high_q.astype(np.float32),
        recon=recon.astype(np.float32),
        error_max=float(err.max()),
        error_mean=float(err.mean()),
        clipped_texels=clipped,
        sigma=sigma,
        radius=float(radius),
    )


def macro(low: NDArray[np.float32], size: int) -> NDArray[np.float32]:
    """The low-pass box-downsampled until its longer side is at most ``size`` (a power-of-two step each time)."""
    out = np.asarray(low, dtype=np.float32)
    if size < 1:
        raise ValueError("macro size is at least 1")
    while max(out.shape[0], out.shape[1]) > size:
        out = halve(out)
    return out


def recombine(low: NDArray[np.float32], high: NDArray[np.float32]) -> NDArray[np.float32]:
    """What the shader does: ``saturate(low + 2 * high - 1)``, O3DE's linear light."""
    return np.clip(np.asarray(low, np.float32) + 2.0 * np.asarray(high, np.float32) - 1.0, 0.0, 1.0)
