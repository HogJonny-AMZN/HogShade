"""
HogShade: GGX specular prefilter (split-sum) and the BRDF LUT.
Package: hogshade/ibl/prefilter

Conventions (spec, "Mathematics"):

- Mip m of M levels has roughness m / (M - 1); alpha = roughness squared.
- N = V = R; samples are GGX-distributed half vectors from a Hammersley sequence, weighted by NdotL.
- Fireflies are suppressed by sampling the source from the pyramid level whose texel solid angle
  matches the sample's, the standard PDF-based level selection.
- The LUT is 2D: x is NdotV, y is roughness, R is the scale and G the bias on F0; GGX with
  height-correlated Smith visibility.
"""

from __future__ import annotations

import logging as _logging
import time

import numpy as np
from numpy.typing import NDArray

from hogshade.ibl.cubemap import direction_to_equirect, equirect_to_cube, face_directions, sample_equirect

_MODULE_NAME = "hogshade.ibl.prefilter"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

ROUGHNESS_TO_MIP = "linear: roughness = mip / (mips - 1)"


def hammersley(count: int) -> NDArray[np.float64]:
    """The 2D Hammersley point set, shape (count, 2). Deterministic."""
    i = np.arange(count, dtype=np.uint32)
    bits = i.copy()
    bits = ((bits << 16) | (bits >> 16)) & 0xFFFFFFFF
    bits = ((bits & 0x55555555) << 1) | ((bits & 0xAAAAAAAA) >> 1)
    bits = ((bits & 0x33333333) << 2) | ((bits & 0xCCCCCCCC) >> 2)
    bits = ((bits & 0x0F0F0F0F) << 4) | ((bits & 0xF0F0F0F0) >> 4)
    bits = ((bits & 0x00FF00FF) << 8) | ((bits & 0xFF00FF00) >> 8)
    radical = bits.astype(np.float64) * 2.3283064365386963e-10
    return np.stack([(i.astype(np.float64) + 0.5) / count, radical], axis=-1)


def ggx_half_vectors(xi: NDArray, alpha: float) -> NDArray[np.float64]:
    """Tangent-space half vectors distributed by GGX D for the given alpha, shape (S, 3), +Z is the normal."""
    phi = 2.0 * np.pi * xi[:, 0]
    a2 = alpha * alpha
    cos_t = np.sqrt((1.0 - xi[:, 1]) / (1.0 + (a2 - 1.0) * xi[:, 1]))
    sin_t = np.sqrt(np.maximum(0.0, 1.0 - cos_t * cos_t))
    return np.stack([sin_t * np.cos(phi), sin_t * np.sin(phi), cos_t], axis=-1)


def ggx_d(n_dot_h: NDArray, alpha: float) -> NDArray:
    a2 = alpha * alpha
    d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0
    return a2 / (np.pi * d * d)


def tangent_frames(n: NDArray) -> tuple[NDArray, NDArray]:
    """Orthonormal tangent and bitangent for unit normals of shape (P, 3)."""
    up = np.where(np.abs(n[:, 1:2]) < 0.999, np.array([[0.0, 1.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))
    t = np.cross(up, n)
    t /= np.linalg.norm(t, axis=-1, keepdims=True)
    b = np.cross(n, t)
    return t, b


try:
    from hogshade.ibl import prefilter_numba as _nb

    HAVE_NUMBA = True
except ImportError:  # numba is the optional ``jit`` extra
    _nb = None
    HAVE_NUMBA = False

BACKENDS = ("auto", "numpy", "numba")


def resolve_backend(backend: str = "auto") -> str:
    """Which backend a request resolves to. ``auto`` is numba when it imports, else numpy."""
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}, got {backend!r}")
    if backend == "numba" and not HAVE_NUMBA:
        raise RuntimeError("numba backend requested but numba is not installed (uv sync --extra jit)")
    if backend == "auto":
        return "numba" if HAVE_NUMBA else "numpy"
    return backend


def _prefilter_mip_numpy(pyramid: list[NDArray], dirs: NDArray, h_t: NDArray, levels: NDArray, chunk: int) -> NDArray:
    acc = np.zeros((dirs.shape[0], 3), dtype=np.float64)
    wsum = np.zeros((dirs.shape[0],), dtype=np.float64)
    for start in range(0, dirs.shape[0], chunk):
        nn = dirs[start : start + chunk]
        t, b = tangent_frames(nn)
        h = h_t[None, :, 0:1] * t[:, None, :] + h_t[None, :, 1:2] * b[:, None, :] + h_t[None, :, 2:3] * nn[:, None, :]
        v_dot_h = np.einsum("pj,psj->ps", nn, h)
        l = 2.0 * v_dot_h[..., None] * h - nn[:, None, :]
        n_dot_l = np.einsum("pj,psj->ps", nn, l)
        weight = np.maximum(n_dot_l, 0.0)
        s, tt = direction_to_equirect(l)
        radiance = np.zeros(l.shape, dtype=np.float64)
        for lv in np.unique(levels):
            sel = levels == lv
            radiance[:, sel] = sample_equirect(pyramid[lv].astype(np.float64), s[:, sel], tt[:, sel])
        acc[start : start + chunk] = np.einsum("ps,psc->pc", weight, radiance)
        wsum[start : start + chunk] = weight.sum(axis=1)
    return acc / np.maximum(wsum, 1e-12)[:, None]


def prefilter_specular(
    pyramid: list[NDArray],
    base: int = 256,
    mips: int | None = None,
    samples: int = 1024,
    chunk: int = 4096,
    backend: str = "auto",
    timings: dict | None = None,
) -> list[NDArray]:
    """Prefilter an equirect pyramid into a GGX cube mip chain. Returns ``mips[m]`` of shape (6, n_m, n_m, 3) float32.

    Mip 0 (roughness 0) is a plain resample of the pyramid level whose texel size matches the
    cube's; every other mip integrates ``samples`` GGX-distributed directions per texel.
    ``backend`` is ``auto`` (numba if installed), ``numpy`` or ``numba``; the two agree within
    float accumulation noise and a test pins that. ``timings``, if given, receives seconds per mip.
    """
    resolved = resolve_backend(backend)
    if mips is None:
        mips = int(np.log2(base)) + 1
    src_w, src_h = pyramid[0].shape[1], pyramid[0].shape[0]
    src_omega = 4.0 * np.pi / (src_w * src_h)
    max_level = len(pyramid) - 1
    xi = hammersley(samples)
    packed = _nb.pack_pyramid(pyramid) if resolved == "numba" else None
    out: list[NDArray] = []
    for m in range(mips):
        started = time.perf_counter()
        n = max(base >> m, 1)
        roughness = m / (mips - 1) if mips > 1 else 0.0
        alpha = roughness * roughness
        cube_omega = 4.0 * np.pi / (6.0 * n * n)
        if m == 0:
            level = int(np.clip(round(0.5 * np.log2(cube_omega / src_omega)), 0, max_level))
            out.append(equirect_to_cube(pyramid[level], n).astype(np.float32))
            _LOGGER.info(f"mip 0: resampled pyramid level {level} to {n} cube")
            if timings is not None:
                timings[0] = time.perf_counter() - started
            continue
        h_t = ggx_half_vectors(xi, alpha)  # (S, 3)
        n_dot_h = h_t[:, 2]
        pdf = ggx_d(n_dot_h, alpha) / 4.0  # N = V, so NdotH = VdotH
        sample_omega = 1.0 / (samples * np.maximum(pdf, 1e-12))
        levels = np.clip(np.round(0.5 * np.log2(sample_omega / src_omega) + 1.0), 0, max_level).astype(np.int64)
        if resolved == "numba":
            # per face, so an 8192 cube never holds a 6-face float64 direction array (10 GB) at once
            flat, offsets, heights, widths = packed
            result = np.zeros((6, n, n, 3), dtype=np.float32)
            all_dirs = face_directions(n)
            for face in range(6):
                dirs = np.ascontiguousarray(all_dirs[face].reshape(-1, 3))
                face_out = np.zeros((dirs.shape[0], 3), dtype=np.float64)
                _nb.prefilter_mip(flat, offsets, heights, widths, dirs, h_t, levels, face_out)
                result[face] = face_out.reshape(n, n, 3)
            out.append(result)
        else:
            dirs = face_directions(n).reshape(-1, 3)
            result = _prefilter_mip_numpy(pyramid, dirs, h_t, levels, chunk)
            out.append(result.reshape(6, n, n, 3).astype(np.float32))
        elapsed = time.perf_counter() - started
        if timings is not None:
            timings[m] = elapsed
        _LOGGER.info(
            f"mip {m}: roughness {roughness:.3f}, {n} cube, {samples} samples/texel, {resolved}, {elapsed:.1f} s"
        )
    return out


def brdf_lut(size: int = 256, samples: int = 1024) -> NDArray[np.float32]:
    """Split-sum environment BRDF LUT, shape (size, size, 2): [y = roughness, x = NdotV] -> (scale, bias).

    Row 0 is roughness of the first texel centre; the caller decides image orientation on write.
    """
    xi = hammersley(samples)
    n_dot_v = (np.arange(size, dtype=np.float64) + 0.5) / size
    rough = (np.arange(size, dtype=np.float64) + 0.5) / size
    lut = np.zeros((size, size, 2), dtype=np.float64)
    v = np.stack([np.sqrt(1.0 - n_dot_v * n_dot_v), np.zeros_like(n_dot_v), n_dot_v], axis=-1)  # (X, 3)
    for yi, r in enumerate(rough):
        alpha = r * r
        h = ggx_half_vectors(xi, alpha)  # (S, 3)
        v_dot_h = v @ h.T  # (X, S)
        l_z = 2.0 * v_dot_h * h[None, :, 2] - v[:, None, 2]
        n_dot_l = np.maximum(l_z, 0.0)
        n_dot_h = np.maximum(h[None, :, 2], 0.0)
        v_dot_h = np.maximum(v_dot_h, 0.0)
        nv = n_dot_v[:, None]
        a2 = alpha * alpha
        vis = 0.5 / np.maximum(
            n_dot_l * np.sqrt(nv * nv * (1.0 - a2) + a2) + nv * np.sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2), 1e-12
        )
        g_vis = 4.0 * vis * n_dot_l * v_dot_h / np.maximum(n_dot_h, 1e-12)
        g_vis = np.where(n_dot_l > 0.0, g_vis, 0.0)
        fc = (1.0 - v_dot_h) ** 5
        lut[yi, :, 0] = ((1.0 - fc) * g_vis).sum(axis=1) / samples
        lut[yi, :, 1] = (fc * g_vis).sum(axis=1) / samples
    return lut.astype(np.float32)


if __name__ == "__main__":
    lut = brdf_lut(16, 256)
    print("LUT at NdotV~1, rough~0:", lut[0, -1], " at NdotV~1, rough~1:", lut[-1, -1])
