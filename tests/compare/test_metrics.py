"""
HogShade: the metrics, each against a value worked by hand or by an independent loop.
Package: tests/compare/test_metrics
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from hogshade.compare import metrics
from hogshade.compare.metrics import MetricError

A = np.array([[1.0, 2.0], [3.0, 4.0]])
B = np.array([[1.0, 1.0], [3.0, 2.0]])


def test_absolute_and_relative_error_against_values_worked_by_hand() -> None:
    got = metrics.abs_rel_error(A, B)
    # |a - b| = 0 1 0 2 ; relative to b = 0 1 0 1
    assert got["max_abs"] == 2.0 and got["mean_abs"] == 0.75 and got["count"] == 4
    assert got["p99_abs"] == pytest.approx(1.97)  # between the two largest, 97 percent of the way up
    assert got["max_rel"] == 1.0 and got["mean_rel"] == 0.5


def test_a_mask_limits_the_measurement_to_its_pixels() -> None:
    mask = np.array([[True, True], [False, False]])  # the first row: errors 0 and 1
    got = metrics.abs_rel_error(A, B, mask)
    assert got["max_abs"] == 1.0 and got["mean_abs"] == 0.5 and got["count"] == 2


def test_relative_error_has_a_floor_so_a_zero_reference_does_not_divide_by_zero() -> None:
    got = metrics.abs_rel_error(np.array([[0.5]]), np.array([[0.0]]), rel_floor=0.25)
    assert got["max_rel"] == 2.0  # 0.5 / max(0, 0.25)
    with pytest.raises(MetricError, match="rel_floor"):
        metrics.abs_rel_error(A, B, rel_floor=0.0)


def test_psnr_is_the_decibels_the_data_range_implies() -> None:
    a, b = np.full((4, 4), 0.5), np.full((4, 4), 0.4)  # mse 0.01
    assert metrics.psnr(a, b, 1.0) == pytest.approx(20.0)
    assert metrics.psnr(a, b, 2.0) == pytest.approx(20.0 + 20.0 * math.log10(2.0))  # a range twice as large: +6.02 dB
    assert metrics.psnr(a, b, 0.5) == pytest.approx(20.0 - 20.0 * math.log10(2.0))


def test_identical_pictures_have_the_named_infinite_psnr() -> None:
    assert metrics.psnr(A, A, 1.0) == metrics.PSNR_IDENTICAL == math.inf


@pytest.mark.parametrize("bad", [0, -1.0, float("nan"), float("inf"), None, "1", True])
def test_a_missing_or_unusable_data_range_is_refused(bad) -> None:
    with pytest.raises(MetricError, match="data_range"):
        metrics.psnr(A, B, bad)
    with pytest.raises(MetricError, match="data_range"):
        metrics.ssim(np.zeros((16, 16)), np.zeros((16, 16)), bad)


def _naive_ssim(x: np.ndarray, y: np.ndarray, data_range: float) -> float:
    """SSIM by loops over every window, straight from the definition, to cross-check the separable implementation."""
    n = metrics.SSIM_WINDOW
    axis = np.arange(n) - (n - 1) / 2.0
    k1d = np.exp(-(axis**2) / (2 * metrics.SSIM_SIGMA**2))
    w = np.outer(k1d, k1d)
    w /= w.sum()
    c1, c2 = (metrics.SSIM_K1 * data_range) ** 2, (metrics.SSIM_K2 * data_range) ** 2
    values = []
    for i in range(x.shape[0] - n + 1):
        for j in range(x.shape[1] - n + 1):
            px, py = x[i : i + n, j : j + n], y[i : i + n, j : j + n]
            mx, my = (w * px).sum(), (w * py).sum()
            vx, vy = (w * px * px).sum() - mx * mx, (w * py * py).sum() - my * my
            cv = (w * px * py).sum() - mx * my
            values.append(((2 * mx * my + c1) * (2 * cv + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2)))
    return float(np.mean(values))


def test_ssim_matches_a_loop_over_every_window() -> None:
    rng = np.random.default_rng(3)
    x = rng.random((20, 17))
    y = np.clip(x + rng.normal(0, 0.1, x.shape), 0, 1)
    assert metrics.ssim(x, y, 1.0) == pytest.approx(_naive_ssim(x, y, 1.0), abs=1e-12)
    assert metrics.ssim(x, y, 4.0) == pytest.approx(_naive_ssim(x, y, 4.0), abs=1e-12)


def test_ssim_of_two_flat_pictures_is_the_luminance_term_alone() -> None:
    a, b = np.full((16, 16), 0.5), np.full((16, 16), 0.25)
    c1 = (metrics.SSIM_K1 * 1.0) ** 2
    assert metrics.ssim(a, b, 1.0) == pytest.approx((2 * 0.5 * 0.25 + c1) / (0.5**2 + 0.25**2 + c1))


def test_identical_pictures_have_ssim_one_and_a_noisy_one_less() -> None:
    rng = np.random.default_rng(1)
    x = rng.random((24, 24, 3))
    assert metrics.ssim(x, x, 1.0) == pytest.approx(1.0)
    assert metrics.ssim(x, np.clip(x + rng.normal(0, 0.2, x.shape), 0, 1), 1.0) < 0.9


def test_ssim_of_a_colour_picture_is_taken_on_its_luma() -> None:
    rng = np.random.default_rng(2)
    x, y = rng.random((16, 16, 3)), rng.random((16, 16, 3))
    luma = np.array([0.2126, 0.7152, 0.0722])
    assert metrics.ssim(x, y, 1.0) == pytest.approx(metrics.ssim(x @ luma, y @ luma, 1.0))


def test_ssim_under_a_mask_uses_only_windows_wholly_inside_it() -> None:
    rng = np.random.default_rng(4)
    x = rng.random((24, 24))
    y = x.copy()
    y[:, 12:] += 0.5  # the right half is wrong
    left = np.zeros((24, 24), dtype=bool)
    left[:, :12] = True
    assert metrics.ssim(x, y, 1.0, left) == pytest.approx(1.0)  # windows wholly in the untouched left half
    assert metrics.ssim(x, y, 1.0) < 0.95
    thin = np.zeros((24, 24), dtype=bool)
    thin[:, 10:14] = True
    with pytest.raises(MetricError, match="no SSIM window lies wholly inside the mask"):
        metrics.ssim(x, y, 1.0, thin)


def test_ssim_refuses_a_picture_smaller_than_its_window() -> None:
    with pytest.raises(MetricError, match="at least 11 pixels each way"):
        metrics.ssim(np.zeros((10, 32)), np.zeros((10, 32)), 1.0)


def test_coverage_overlap_counts_both_and_each_side_only() -> None:
    a = np.array([[1, 1, 0, 0], [1, 1, 0, 0]], dtype=bool)  # 4 pixels
    b = np.array([[0, 1, 1, 0], [0, 1, 1, 0]], dtype=bool)  # 4 pixels, 2 shared
    got = metrics.coverage_overlap(a, b)
    assert (got["both"], got["only_a"], got["only_b"]) == (2, 2, 2)
    assert got["iou"] == pytest.approx(2 / 6) and got["symmetric_difference"] == pytest.approx(4 / 6)
    assert metrics.coverage_overlap(a, a)["iou"] == 1.0


def test_a_shifted_silhouette_has_a_low_overlap_though_the_shared_pixels_could_agree() -> None:
    disc = np.zeros((32, 32), dtype=bool)
    disc[8:24, 8:24] = True
    shifted = np.roll(disc, 8, axis=1)
    assert metrics.coverage_overlap(disc, shifted)["iou"] == pytest.approx(1 / 3)


def test_two_empty_coverage_masks_are_a_fault_not_a_perfect_match() -> None:
    empty = np.zeros((4, 4), dtype=bool)
    with pytest.raises(MetricError, match="both coverage masks are empty"):
        metrics.coverage_overlap(empty, empty)
    with pytest.raises(MetricError, match="bool"):
        metrics.coverage_overlap(empty.astype(np.uint8), empty)


def test_fraction_within_counts_the_values_inside_the_tolerance() -> None:
    values = np.array([0.0, -0.05, 0.1, 0.2, -0.3])
    assert metrics.fraction_within(values, 0.1) == pytest.approx(3 / 5)  # 0, -0.05 and 0.1 (inclusive)
    mask = np.array([True, True, False, False, False])
    assert metrics.fraction_within(values, 0.1, mask) == 1.0
    with pytest.raises(MetricError, match="tolerance"):
        metrics.fraction_within(values, -1.0)
    with pytest.raises(MetricError, match="mask is empty"):
        metrics.fraction_within(values, 0.1, np.zeros(5, dtype=bool))


def test_the_inputs_that_cannot_be_measured_are_refused() -> None:
    with pytest.raises(MetricError, match="differ in shape"):
        metrics.abs_rel_error(np.zeros((2, 2)), np.zeros((2, 3)))
    with pytest.raises(MetricError, match="mask is empty"):
        metrics.abs_rel_error(A, B, np.zeros((2, 2), dtype=bool))
    with pytest.raises(MetricError, match="a mask is bool"):
        metrics.abs_rel_error(A, B, np.ones((3, 3), dtype=bool))
    bad = A.copy()
    bad[0, 0] = np.nan
    with pytest.raises(MetricError, match="1 non-finite value"):
        metrics.abs_rel_error(bad, B)
    ok = np.array([[False, True], [True, True]])
    assert metrics.abs_rel_error(bad, B, ok)["count"] == 3  # the NaN is outside the mask, so it is not measured
    with pytest.raises(MetricError, match="a picture is"):
        metrics.psnr(np.zeros(4), np.zeros(4), 1.0)
