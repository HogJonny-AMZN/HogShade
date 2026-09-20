"""
HogShade: the numba kernel for the GGX prefilter. Same algorithm as the NumPy path, one texel per parallel iteration.
Package: hogshade/ibl/prefilter_numba

Importing this module requires numba; ``hogshade.ibl.prefilter`` imports it lazily and falls back
to NumPy when it is absent. The maths is duplicated deliberately, line for line with
``prefilter.prefilter_specular`` and ``cubemap.sample_equirect``, and a parity test pins the two.
"""

from __future__ import annotations

import logging as _logging
import math

import numpy as np
from numba import njit, prange
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.ibl.prefilter_numba"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def pack_pyramid(pyramid: list[NDArray]) -> tuple[NDArray, NDArray, NDArray, NDArray]:
    """Flatten a list of (H, W, 3) levels into one float32 array plus per-level offset, height and width."""
    flat = np.concatenate([np.ascontiguousarray(lv, dtype=np.float32).reshape(-1) for lv in pyramid])
    sizes = np.array([lv.shape[0] * lv.shape[1] * 3 for lv in pyramid], dtype=np.int64)
    offsets = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64)
    heights = np.array([lv.shape[0] for lv in pyramid], dtype=np.int64)
    widths = np.array([lv.shape[1] for lv in pyramid], dtype=np.int64)
    return flat, offsets, heights, widths


@njit(cache=True, parallel=True)
def prefilter_mip(flat, offsets, heights, widths, dirs, h_t, levels, out):
    """Integrate ``h_t`` half vectors per texel direction; writes (P, 3) into ``out``. Sequential per texel."""
    n_tex = dirs.shape[0]
    n_samp = h_t.shape[0]
    for p in prange(n_tex):
        nx = dirs[p, 0]
        ny = dirs[p, 1]
        nz = dirs[p, 2]
        # tangent frame, identical to prefilter.tangent_frames
        if abs(ny) < 0.999:
            ux, uy, uz = 0.0, 1.0, 0.0
        else:
            ux, uy, uz = 1.0, 0.0, 0.0
        tx = uy * nz - uz * ny
        ty = uz * nx - ux * nz
        tz = ux * ny - uy * nx
        tl = math.sqrt(tx * tx + ty * ty + tz * tz)
        tx /= tl
        ty /= tl
        tz /= tl
        bx = ny * tz - nz * ty
        by = nz * tx - nx * tz
        bz = nx * ty - ny * tx
        acc_r = 0.0
        acc_g = 0.0
        acc_b = 0.0
        wsum = 0.0
        for s in range(n_samp):
            hx = h_t[s, 0] * tx + h_t[s, 1] * bx + h_t[s, 2] * nx
            hy = h_t[s, 0] * ty + h_t[s, 1] * by + h_t[s, 2] * ny
            hz = h_t[s, 0] * tz + h_t[s, 1] * bz + h_t[s, 2] * nz
            vdh = nx * hx + ny * hy + nz * hz
            lx = 2.0 * vdh * hx - nx
            ly = 2.0 * vdh * hy - ny
            lz = 2.0 * vdh * hz - nz
            ndl = nx * lx + ny * ly + nz * lz
            if ndl <= 0.0:
                continue
            # direction_to_equirect
            phi = math.atan2(lx, -lz)
            dy = ly
            if dy > 1.0:
                dy = 1.0
            elif dy < -1.0:
                dy = -1.0
            theta = math.asin(dy)
            sq = (0.5 + phi / (2.0 * math.pi)) % 1.0
            tq = 0.5 - theta / math.pi
            if tq < 0.0:
                tq = 0.0
            elif tq > 1.0:
                tq = 1.0
            # sample_equirect on the chosen level
            lv = levels[s]
            h = heights[lv]
            w = widths[lv]
            base = offsets[lv]
            x = sq * w - 0.5
            y = tq * h - 0.5
            x0 = math.floor(x)
            y0 = math.floor(y)
            fx = x - x0
            fy = y - y0
            x0i = int(x0) % w
            x1i = (x0i + 1) % w
            y0i = int(y0)
            if y0i < 0:
                y0i = 0
            elif y0i > h - 1:
                y0i = h - 1
            y1i = y0i + 1
            y1i = min(y1i, h - 1)
            i00 = base + (y0i * w + x0i) * 3
            i01 = base + (y0i * w + x1i) * 3
            i10 = base + (y1i * w + x0i) * 3
            i11 = base + (y1i * w + x1i) * 3
            for c in range(3):
                top = flat[i00 + c] * (1.0 - fx) + flat[i01 + c] * fx
                bot = flat[i10 + c] * (1.0 - fx) + flat[i11 + c] * fx
                v = top * (1.0 - fy) + bot * fy
                if c == 0:
                    acc_r += ndl * v
                elif c == 1:
                    acc_g += ndl * v
                else:
                    acc_b += ndl * v
            wsum += ndl
        wsum = max(wsum, 1e-12)
        out[p, 0] = acc_r / wsum
        out[p, 1] = acc_g / wsum
        out[p, 2] = acc_b / wsum


if __name__ == "__main__":
    import time

    from hogshade.ibl.cubemap import equirect_pyramid, face_directions
    from hogshade.ibl.prefilter import ggx_half_vectors, hammersley

    img = np.random.default_rng(0).random((64, 128, 3)).astype(np.float32)
    flat, offsets, heights, widths = pack_pyramid(equirect_pyramid(img))
    dirs = face_directions(16).reshape(-1, 3)
    h_t = ggx_half_vectors(hammersley(64), 0.25)
    levels = np.zeros(64, dtype=np.int64)
    out = np.zeros((dirs.shape[0], 3))
    t0 = time.perf_counter()
    prefilter_mip(flat, offsets, heights, widths, dirs, h_t, levels, out)
    print("first call (includes compile):", round(time.perf_counter() - t0, 2), "s; mean", out.mean())
