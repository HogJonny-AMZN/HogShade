"""
HogShade: how close two pictures are: absolute and relative error, PSNR, SSIM, coverage overlap, fraction within.
Package: hogshade/compare/metrics

Numpy only. There is no global tolerance: a case names its metric and its thresholds, and these functions only
measure. Three rules keep the numbers honest:

- **The data range is an argument, never inferred.** Scene-linear frames are not bounded to [0, 1], so PSNR and SSIM
  take the peak the case states (1.0 for a display-referred picture, the reference's stated peak otherwise); a missing
  or non-positive range is a ``MetricError``.
- **A mask is part of the measurement.** Every metric takes an optional boolean mask and measures only under it; an
  empty mask is a ``MetricError``, not a mean of nothing. Compare the coverage masks (``coverage_overlap``) before
  intersecting them for the shading metrics.
- **Non-finite input is refused**, not propagated: a NaN in a frame is a fault the caller reports, not a number.
"""

from __future__ import annotations

import logging as _logging
import math
import numbers

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.compare.metrics"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: What PSNR reports for identical pictures (the mean squared error is zero, so the ratio is unbounded).
PSNR_IDENTICAL = 200.0

#: The SSIM window: 11 pixels square, Gaussian, sigma 1.5, K1 0.01, K2 0.03 (Wang et al., 2004).
SSIM_WINDOW = 11
SSIM_SIGMA = 1.5
SSIM_K1 = 0.01
SSIM_K2 = 0.03

#: Rec. 709 luma weights, for SSIM on a colour picture.
_LUMA = np.array([0.2126, 0.7152, 0.0722])


class MetricError(ValueError):
    """An input a metric cannot measure; the message says why."""


def _pair(a: NDArray, b: NDArray) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise MetricError(f"the two pictures differ in shape: {a.shape} against {b.shape}")
    if a.ndim not in (2, 3):
        raise MetricError(f"a picture is (H, W) or (H, W, C), got shape {a.shape}")
    return a, b


def _mask(shape: tuple[int, ...], mask: NDArray | None) -> NDArray[np.bool_]:
    height_width = shape[:2]
    if mask is None:
        return np.ones(height_width, dtype=bool)
    mask = np.asarray(mask)
    if mask.dtype != np.bool_ or mask.shape != height_width:
        raise MetricError(f"a mask is bool {height_width}, got {mask.dtype} {mask.shape}")
    if not mask.any():
        raise MetricError("the mask is empty, so there is nothing to measure")
    return mask


def _values(a: NDArray, b: NDArray, mask: NDArray | None) -> tuple[NDArray, NDArray]:
    """The masked values of both pictures, flattened (every channel of every masked pixel)."""
    a, b = _pair(a, b)
    m = _mask(a.shape, mask)
    av, bv = a[m].ravel(), b[m].ravel()
    if av.size == 0:
        raise MetricError("no values to measure: the pictures are empty")
    bad = int((~np.isfinite(av)).sum() + (~np.isfinite(bv)).sum())
    if bad:
        raise MetricError(f"{bad} non-finite value(s) under the mask")
    return av, bv


def _range(data_range: float) -> float:
    if isinstance(data_range, (bool, np.bool_)) or not isinstance(data_range, numbers.Real):
        raise MetricError(f"data_range: a positive number is expected, got {data_range!r}")
    if not math.isfinite(data_range) or data_range <= 0:
        raise MetricError(f"data_range: a positive finite number is expected, got {data_range!r}")
    return float(data_range)


def abs_rel_error(a: NDArray, b: NDArray, mask: NDArray | None = None, rel_floor: float = 1e-6) -> dict[str, float]:
    """
    Absolute error ``|a - b|`` and relative error ``|a - b| / max(|b|, rel_floor)`` (``b`` is the reference) over the
    masked values: the maximum, the mean and the 99th percentile of each, and how many values were measured.
    """
    if (
        isinstance(rel_floor, (bool, np.bool_))
        or not isinstance(rel_floor, numbers.Real)
        or rel_floor <= 0
        or not math.isfinite(rel_floor)
    ):
        raise MetricError(f"rel_floor: a positive finite number is expected, got {rel_floor!r}")
    av, bv = _values(a, b, mask)
    err = np.abs(av - bv)
    rel = err / np.maximum(np.abs(bv), rel_floor)
    return {
        "max_abs": float(err.max()),
        "mean_abs": float(err.mean()),
        "p99_abs": float(np.percentile(err, 99)),
        "max_rel": float(rel.max()),
        "mean_rel": float(rel.mean()),
        "p99_rel": float(np.percentile(rel, 99)),
        "count": int(err.size),
    }


def psnr(a: NDArray, b: NDArray, data_range: float, mask: NDArray | None = None) -> float:
    """``10 log10(data_range^2 / mse)`` in decibels over the masked values; ``PSNR_IDENTICAL`` for identical input."""
    peak = _range(data_range)
    av, bv = _values(a, b, mask)
    mse = float(np.mean((av - bv) ** 2))
    if mse == 0.0:
        return PSNR_IDENTICAL
    return 10.0 * math.log10(peak * peak / mse)


def _gaussian_kernel() -> NDArray[np.float64]:
    x = np.arange(SSIM_WINDOW, dtype=np.float64) - (SSIM_WINDOW - 1) / 2.0
    k = np.exp(-(x * x) / (2.0 * SSIM_SIGMA * SSIM_SIGMA))
    return k / k.sum()


def _filter_valid(img: NDArray[np.float64], kernel: NDArray[np.float64]) -> NDArray[np.float64]:
    """Separable correlation with ``kernel`` over the positions where the window lies wholly inside ``img``."""
    n = len(kernel)
    height, width = img.shape
    rows = sum(kernel[i] * img[i : height - n + 1 + i, :] for i in range(n))
    return sum(kernel[i] * rows[:, i : width - n + 1 + i] for i in range(n))


def _luma(img: NDArray[np.float64]) -> NDArray[np.float64]:
    if img.ndim == 2:
        return img
    if img.shape[2] == 1:
        return img[..., 0]
    if img.shape[2] < 3:
        raise MetricError(f"SSIM takes grey, one channel or RGB(A), got {img.shape[2]} channels")
    return img[..., :3] @ _LUMA


def ssim(a: NDArray, b: NDArray, data_range: float, mask: NDArray | None = None) -> float:
    """
    Mean structural similarity of the luma of two pictures (an 11-pixel Gaussian window, sigma 1.5), over the windows
    that lie wholly inside the mask. 1.0 for identical pictures. The pictures must be at least a window across.
    """
    peak = _range(data_range)
    a, b = _pair(a, b)
    m = _mask(a.shape, mask)
    if not (np.isfinite(a[m]).all() and np.isfinite(b[m]).all()):
        raise MetricError("non-finite value(s) under the mask")
    height, width = a.shape[:2]
    if min(height, width) < SSIM_WINDOW:
        raise MetricError(f"SSIM needs at least {SSIM_WINDOW} pixels each way, got {width}x{height}")
    x, y = (
        _luma(np.where(m[..., None] if a.ndim == 3 else m, a, 0.0)),
        _luma(np.where(m[..., None] if b.ndim == 3 else m, b, 0.0)),
    )
    kernel = _gaussian_kernel()
    mu_x, mu_y = _filter_valid(x, kernel), _filter_valid(y, kernel)
    var_x = _filter_valid(x * x, kernel) - mu_x * mu_x
    var_y = _filter_valid(y * y, kernel) - mu_y * mu_y
    cov = _filter_valid(x * y, kernel) - mu_x * mu_y
    c1, c2 = (SSIM_K1 * peak) ** 2, (SSIM_K2 * peak) ** 2
    ssim_map = ((2.0 * mu_x * mu_y + c1) * (2.0 * cov + c2)) / ((mu_x * mu_x + mu_y * mu_y + c1) * (var_x + var_y + c2))
    inside = _filter_valid(m.astype(np.float64), np.full(SSIM_WINDOW, 1.0 / SSIM_WINDOW)) > 1.0 - 1e-9
    if not inside.any():
        raise MetricError("no SSIM window lies wholly inside the mask")
    return float(ssim_map[inside].mean())


def coverage_overlap(a: NDArray, b: NDArray) -> dict[str, float]:
    """
    How much two coverage masks agree: ``iou`` (intersection over union), the counts of pixels in both, only in ``a``
    and only in ``b``, and ``symmetric_difference`` as a fraction of the union. Two empty masks are a ``MetricError``:
    nothing was drawn, so there is nothing to agree about.
    """
    a, b = np.asarray(a), np.asarray(b)
    if a.dtype != np.bool_ or b.dtype != np.bool_ or a.shape != b.shape or a.ndim != 2:
        raise MetricError(
            f"coverage masks are bool (H, W) of one shape, got {a.dtype} {a.shape} and {b.dtype} {b.shape}"
        )
    both, only_a, only_b = int((a & b).sum()), int((a & ~b).sum()), int((~a & b).sum())
    union = both + only_a + only_b
    if union == 0:
        raise MetricError("both coverage masks are empty: nothing was drawn")
    return {
        "iou": both / union,
        "both": both,
        "only_a": only_a,
        "only_b": only_b,
        "symmetric_difference": (only_a + only_b) / union,
    }


def fraction_within(values: NDArray, tolerance: float, mask: NDArray | None = None) -> float:
    """The fraction of ``|values|`` (under an optional mask over the first two axes) that are at most ``tolerance``."""
    if tolerance < 0 or not math.isfinite(tolerance):
        raise MetricError(f"tolerance: a non-negative finite number is expected, got {tolerance!r}")
    v = np.asarray(values, dtype=np.float64)
    if v.ndim < 1:
        raise MetricError("values must be an array")
    selected = v if mask is None else v[_mask(v.shape, mask)]
    if selected.size == 0:
        raise MetricError("no values to measure")
    if not np.isfinite(selected).all():
        raise MetricError("non-finite value(s) in the values")
    return float((np.abs(selected) <= tolerance).mean())
