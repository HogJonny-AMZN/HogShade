"""
HogShade: cube-map directions and the equirectangular mapping, fixed so every host agrees.
Package: hogshade/ibl/cubemap

The conventions here are the spec's (Docs/specs/e1-ibl-cook.md, "Cube from equirect"):

- Texel (x, y) on a face of size N: u = 2 (x + 0.5) / N - 1, v = 2 (y + 0.5) / N - 1, with y = 0
  the first stored row (the top of the face as Direct3D displays it).
- Face directions are the Direct3D cube-map convention (see FACE_DIRECTION).
- Equirect: phi = atan2(dx, -dz), theta = asin(dy); s = 0.5 + phi / 2pi, t = 0.5 - theta / pi.
  Row 0 is +Y, the centre column is -Z, +X is at s = 0.75. s wraps, t clamps. Y is up.
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.ibl.cubemap"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)

FACE_NAMES = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
FACE_CONVENTION = "d3d11-cube-yup-equirect-center-negz-v1"


def face_direction(face: int, u: NDArray, v: NDArray) -> NDArray:
    """Unnormalised direction for face ``face`` at (u, v) in [-1, 1]. Direct3D convention."""
    one = np.ones_like(u)
    if face == 0:
        return np.stack([one, -v, -u], axis=-1)
    if face == 1:
        return np.stack([-one, -v, u], axis=-1)
    if face == 2:
        return np.stack([u, one, v], axis=-1)
    if face == 3:
        return np.stack([u, -one, -v], axis=-1)
    if face == 4:
        return np.stack([u, -v, one], axis=-1)
    if face == 5:
        return np.stack([-u, -v, -one], axis=-1)
    raise ValueError(f"face must be 0..5, got {face}")


def face_directions(n: int) -> NDArray[np.float64]:
    """Normalised directions through every texel centre, shape (6, n, n, 3)."""
    c = (np.arange(n, dtype=np.float64) + 0.5) * (2.0 / n) - 1.0
    u, v = np.meshgrid(c, c, indexing="xy")  # u varies along x (columns), v along y (rows)
    dirs = np.stack([face_direction(f, u, v) for f in range(6)], axis=0)
    return dirs / np.linalg.norm(dirs, axis=-1, keepdims=True)


def direction_to_equirect(dirs: NDArray) -> tuple[NDArray, NDArray]:
    """(s, t) in [0, 1) x [0, 1] for unit directions of shape (..., 3)."""
    dx, dy, dz = dirs[..., 0], dirs[..., 1], dirs[..., 2]
    phi = np.arctan2(dx, -dz)
    theta = np.arcsin(np.clip(dy, -1.0, 1.0))
    s = np.mod(0.5 + phi / (2.0 * np.pi), 1.0)
    t = np.clip(0.5 - theta / np.pi, 0.0, 1.0)
    return s, t


def equirect_texel_directions(width: int, height: int) -> NDArray[np.float64]:
    """Unit direction through every equirect texel centre, shape (height, width, 3). Inverse of the mapping above."""
    s = (np.arange(width, dtype=np.float64) + 0.5) / width
    t = (np.arange(height, dtype=np.float64) + 0.5) / height
    phi = (s - 0.5) * 2.0 * np.pi
    theta = (0.5 - t) * np.pi
    phi_g, theta_g = np.meshgrid(phi, theta, indexing="xy")
    cos_t = np.cos(theta_g)
    return np.stack([cos_t * np.sin(phi_g), np.sin(theta_g), -cos_t * np.cos(phi_g)], axis=-1)


def equirect_texel_solid_angle(width: int, height: int) -> NDArray[np.float64]:
    """Solid angle of every equirect texel, shape (height, width). Sums to 4 pi."""
    t = (np.arange(height, dtype=np.float64) + 0.5) / height
    theta = (0.5 - t) * np.pi
    d_omega_row = (2.0 * np.pi / width) * (np.pi / height) * np.cos(theta)
    return np.repeat(d_omega_row[:, None], width, axis=1)


def sample_equirect(img: NDArray, s: NDArray, t: NDArray) -> NDArray:
    """Bilinear lookup of an (H, W, C) equirect at (s, t); s wraps, t clamps. Returns (..., C)."""
    h, w, _ = img.shape
    x = s * w - 0.5
    y = t * h - 0.5
    x0 = np.floor(x)
    y0 = np.floor(y)
    fx = (x - x0).astype(img.dtype)[..., None]
    fy = (y - y0).astype(img.dtype)[..., None]
    x0i = x0.astype(np.int64) % w
    x1i = (x0i + 1) % w
    y0i = np.clip(y0.astype(np.int64), 0, h - 1)
    y1i = np.clip(y0i + 1, 0, h - 1)
    top = img[y0i, x0i] * (1 - fx) + img[y0i, x1i] * fx
    bot = img[y1i, x0i] * (1 - fx) + img[y1i, x1i] * fx
    return top * (1 - fy) + bot * fy


def equirect_to_cube(img: NDArray, n: int) -> NDArray:
    """Resample an (H, W, C) equirect to a (6, n, n, C) cube by bilinear lookup at texel-centre directions."""
    s, t = direction_to_equirect(face_directions(n))
    return sample_equirect(img, s, t)


def box_downsample(img: NDArray, factor: int = 2) -> NDArray:
    """Average factor x factor blocks of an (H, W, C) image. H and W must divide."""
    h, w, c = img.shape
    if h % factor or w % factor:
        raise ValueError(f"{h}x{w} is not divisible by {factor}")
    return (
        img.reshape(h // factor, factor, w // factor, factor, c).mean(axis=(1, 3), dtype=np.float64).astype(img.dtype)
    )


def equirect_pyramid(img: NDArray, min_width: int = 8) -> list[NDArray]:
    """Box-filtered mip chain of an equirect, level 0 the input, halving until width < min_width * 2."""
    levels = [img]
    while levels[-1].shape[1] >= min_width * 2 and levels[-1].shape[0] % 2 == 0 and levels[-1].shape[1] % 2 == 0:
        levels.append(box_downsample(levels[-1], 2))
    return levels


if __name__ == "__main__":
    d = face_directions(4)
    print("face +X centre-ish texel dir:", d[0, 1, 1])
    s, t = direction_to_equirect(np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]))
    print("s for +X, -Z, +Y:", s, "t:", t)
    print("solid angle sum / 4pi:", equirect_texel_solid_angle(64, 32).sum() / (4 * np.pi))
