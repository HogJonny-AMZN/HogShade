"""
HogShade: diffuse irradiance by exact convolution, and its SH L2 projection.
Package: hogshade/ibl/irradiance

Both outputs are the cosine-convolved radiance divided by pi (E / pi), so a white environment
yields exactly 1 and a shader multiplies by albedo directly. The SH9 file stores the radiance
coefficients L_lm; reconstruction applies the Ramamoorthi and Hanrahan weights and divides by pi.
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

from hogshade.ibl.cubemap import equirect_texel_directions, equirect_texel_solid_angle, face_directions

_MODULE_NAME = "hogshade.ibl.irradiance"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SH_A = (np.pi, 2.0 * np.pi / 3.0, np.pi / 4.0)  # cosine-lobe band weights, l = 0, 1, 2


def sh9_basis(d: NDArray) -> NDArray:
    """The nine real SH basis functions at unit directions (..., 3), shape (..., 9)."""
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    return np.stack(
        [
            np.full_like(x, 0.282095),
            0.488603 * y,
            0.488603 * z,
            0.488603 * x,
            1.092548 * x * y,
            1.092548 * y * z,
            0.315392 * (3.0 * z * z - 1.0),
            1.092548 * x * z,
            0.546274 * (x * x - y * y),
        ],
        axis=-1,
    )


def _solid_angle_weighted(img: NDArray) -> tuple[NDArray, NDArray, NDArray]:
    h, w, _ = img.shape
    dirs = equirect_texel_directions(w, h).reshape(-1, 3)
    d_omega = equirect_texel_solid_angle(w, h).reshape(-1)
    return img.reshape(-1, img.shape[-1]).astype(np.float64), dirs, d_omega


def irradiance_cube(img: NDArray, n: int = 32) -> NDArray[np.float32]:
    """Exact cosine convolution of a small equirect (e.g. 128x64) onto a (6, n, n, 3) cube, divided by pi."""
    rad, dirs, d_omega = _solid_angle_weighted(img)
    normals = face_directions(n).reshape(-1, 3)
    cos = np.maximum(normals @ dirs.T, 0.0)  # (P, T)
    e = (cos * d_omega[None, :]) @ rad  # (P, 3)
    return (e / np.pi).reshape(6, n, n, 3).astype(np.float32)


def sh9_project(img: NDArray) -> NDArray[np.float64]:
    """Radiance SH coefficients L_lm, shape (9, 3), from a solid-angle-weighted equirect."""
    rad, dirs, d_omega = _solid_angle_weighted(img)
    basis = sh9_basis(dirs)  # (T, 9)
    return (basis * d_omega[:, None]).T @ rad


def sh9_irradiance(coeffs: NDArray, normals: NDArray) -> NDArray:
    """E(n) / pi from L_lm coefficients (9, 3) at unit normals (..., 3). Returns (..., 3)."""
    a = np.array([SH_A[0]] + [SH_A[1]] * 3 + [SH_A[2]] * 5)
    basis = sh9_basis(normals)
    return np.maximum((basis * a) @ coeffs / np.pi, 0.0)


if __name__ == "__main__":
    white = np.ones((32, 64, 3), dtype=np.float32)
    print("white cube irradiance/pi:", irradiance_cube(white, 4)[0, 0, 0])
    c = sh9_project(white)
    print("white sh9 dc:", c[0], "reconstruct:", sh9_irradiance(c, np.array([[0.0, 1.0, 0.0]])))
