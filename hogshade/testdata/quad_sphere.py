"""
HogShade: a quad sphere (a cube mapped onto a sphere) with a clean 0 to 1 unwrap on every face, for texture renders.
Package: hogshade/testdata/quad_sphere

The owner's reasons (2026-10-04): "a quad sphere is going to be better than a polar sphere for texturing renders and
comparison", and the legacy shader ball's UVs (-1 to 1.66 across 5,060 shells) make a pixel's texel a guess. Here every
face of the cube is one UV tile with u along the face's first axis and v (up, the OBJ convention) along its second, so
every face shows the whole texture once, unmirrored, with no wrap seam; faces do not share vertices, so a corner is
three vertices and the normals are the sphere's own (the tangents are generated from these UVs by
``wgpu_host.with_tangents``). The cube-to-sphere map is the tangent-adjusted one (``tan(x * pi / 4)``), which keeps the
cells close to equal in area.

The sphere is analytic, so ``face_uv`` is exact: the unit direction of a point on it gives its face and its ``(u, v)``,
which is what lets a test read the texel a pixel shows without a vertex proxy. Numpy only; no renderer here.
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.testdata.quad_sphere"
__version__ = "0.1.0"
__updated__ = "2026-10-05"
_LOGGER = _logging.getLogger(_MODULE_NAME)

SUBDIVISIONS = 48
#: The default sphere is framed as ``wgpu_host.normalise_mesh`` leaves the shader ball: centred on the origin, 2 across.
RADIUS = 1.0
CENTRE = (0.0, 0.0, 0.0)

#: Each face as ``(a, b, c)``: the directions u and v increase along and the outward normal, right-handed
#: (``a x b = c``) so the texture reads unmirrored from outside.
FACES: tuple[tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]], ...] = (
    ((0, 0, -1), (0, 1, 0), (1, 0, 0)),  # +X
    ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),  # -X
    ((1, 0, 0), (0, 0, -1), (0, 1, 0)),  # +Y
    ((1, 0, 0), (0, 0, 1), (0, -1, 0)),  # -Y
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),  # +Z
    ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),  # -Z
)
_AXES = np.array(FACES, dtype=np.float64)  # (6, 3, 3): face, (a, b, c), xyz


class QuadSphereError(ValueError):
    """A quad sphere that cannot be built: a subdivision below 1."""


def build(
    subdivisions: int = SUBDIVISIONS, radius: float = RADIUS, centre: tuple[float, float, float] = CENTRE
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.uint32]]:
    """
    ``(positions, normals, uvs, indices)``: ``6 * (n + 1)^2`` vertices, ``12 * n^2`` triangles for ``n`` subdivisions
    per face edge, indices ``(m, 3)`` counter-clockwise seen from outside.
    """
    n = int(subdivisions)
    if n < 1:
        raise QuadSphereError(f"subdivisions is at least 1, got {subdivisions}")
    side = n + 1
    grid = np.linspace(0.0, 1.0, side)
    s, t = np.meshgrid(grid, grid)  # s varies along columns (i), t along rows (j)
    x, y = np.tan((2.0 * s - 1.0) * np.pi / 4.0), np.tan((2.0 * t - 1.0) * np.pi / 4.0)
    positions, normals, uvs, tris = [], [], [], []
    cells = np.arange(n)
    ii, jj = np.meshgrid(cells, cells)
    v00 = (jj * side + ii).ravel()
    v10, v11, v01 = v00 + 1, v00 + side + 1, v00 + side
    for face, (a, b, c) in enumerate(_AXES):
        p = c[None, None, :] + x[..., None] * a + y[..., None] * b
        unit = (p / np.linalg.norm(p, axis=-1, keepdims=True)).reshape(-1, 3)
        positions.append(np.asarray(centre) + radius * unit)
        normals.append(unit)
        uvs.append(np.stack([s.ravel(), t.ravel()], axis=1))
        base = face * side * side
        tris.append(np.concatenate([np.stack([v00, v10, v11], 1), np.stack([v00, v11, v01], 1)]) + base)
    _LOGGER.info(f"quad sphere: {n} subdivision(s) per face edge, {6 * side * side} vertices, {12 * n * n} triangles")
    return (
        np.concatenate(positions),
        np.concatenate(normals),
        np.concatenate(uvs),
        np.concatenate(tris).astype(np.uint32),
    )


def face_uv(directions: NDArray[np.floating]) -> tuple[NDArray[np.int_], NDArray[np.float64], NDArray[np.float64]]:
    """
    The face and ``(u, v)`` of unit directions ``(N, 3)`` from the sphere's centre: the exact inverse of ``build``'s
    map, for a point seen on the sphere.
    """
    d = np.asarray(directions, dtype=np.float64)
    face = np.argmax(np.einsum("fk,nk->nf", _AXES[:, 2, :], d), axis=1)  # the face whose outward axis d leans on most
    a, b, c = _AXES[face, 0], _AXES[face, 1], _AXES[face, 2]
    dc = np.einsum("nk,nk->n", d, c)
    x = np.einsum("nk,nk->n", d, a) / dc
    y = np.einsum("nk,nk->n", d, b) / dc
    return face, (np.arctan(x) * 4.0 / np.pi + 1.0) / 2.0, (np.arctan(y) * 4.0 / np.pi + 1.0) / 2.0


def tangent_at(face: NDArray[np.int_], u: NDArray[np.float64], v: NDArray[np.float64]) -> NDArray[np.float64]:
    """The unit direction of increasing ``u`` on the sphere at ``(face, u, v)``, worked out analytically."""
    a, b, c = _AXES[face, 0], _AXES[face, 1], _AXES[face, 2]
    x, y = np.tan((2.0 * u - 1.0) * np.pi / 4.0), np.tan((2.0 * v - 1.0) * np.pi / 4.0)
    p = c + x[:, None] * a + y[:, None] * b
    r = np.linalg.norm(p, axis=1, keepdims=True)
    dp = a / r - p * (np.einsum("nk,nk->n", p, a)[:, None] / r**3)  # d(p / |p|) / dx
    nrm = p / r
    dp -= nrm * np.einsum("nk,nk->n", dp, nrm)[:, None]
    return dp / np.linalg.norm(dp, axis=1, keepdims=True)


if __name__ == "__main__":
    _pos, _nrm, _uv, _idx = build(8)
    print(_pos.shape, _uv.min(), _uv.max(), _idx.shape)
    _face, _u, _v = face_uv(_nrm[:5])
    print(_face, _u.round(3), _v.round(3))
