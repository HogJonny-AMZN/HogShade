"""
HogShade: MikkTSpace tangents on arbitrary data: positions, the normals as the source gives them, UVs and
triangles in; a tangent and a handedness sign per vertex out.
Package: hogshade/mikktspace

The project assumes and requires MikkTSpace tangents (the content standard; the owner, 2026-10-04: "we absolutely
need a way to gen MikkT on arbitrary data"). This is the reference algorithm (Morten S. Mikkelsen, 2008) in numpy,
the shape every host and exporter here agrees on:

1. Per triangle, the tangent and bitangent from the position and UV derivatives (the direction of increasing
   U and V on the surface), and the triangle's handedness from the sign of the UV area.
2. Per corner, the triangle's tangent weighted by the corner's angle, accumulated over the corners that share a
   vertex and lie in the same smoothing group: the same position, the same normal and the same UV. Corners of
   opposite handedness never average together (a mirrored island keeps its own frame), which is what keeps a
   seam from averaging to zero.
3. Per vertex, the accumulated tangent made orthogonal to the given normal (Gram-Schmidt) and normalised; the
   sign is +1 when ``cross(n, t)`` points along the accumulated bitangent, -1 when against it. A corner with no
   UV area (a degenerate triangle) falls back to any tangent perpendicular to its normal, sign +1.

The normals are consumed, never recomputed: custom normals survive (the owner's point), and the frame is built
around whatever the source provides. Welding is by exact equality of position, normal and UV, the reference's
rule; a mesh whose corners were already de-duplicated that way (``wgpu_host.load_obj``) welds to itself.
"""

from __future__ import annotations

import logging as _logging

import numpy as np
from numpy.typing import NDArray

_MODULE_NAME = "hogshade.mikktspace"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: The bases a mesh's tangents can be in: generated here or declared; carried by a file with no record of how;
#: or absent from the file (the host generates).
TANGENT_BASES = ("mikktspace", "unknown", "none")


def _normalise(v: NDArray, eps: float = 1e-12) -> NDArray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def _any_perpendicular(n: NDArray) -> NDArray:
    """A unit vector perpendicular to each unit normal (the fallback for a corner with no UV area)."""
    helper = np.where(np.abs(n[:, :1]) > 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    t = np.cross(helper, n)
    return _normalise(t)


def corner_angles(p0: NDArray, p1: NDArray, p2: NDArray) -> NDArray:
    """The interior angle at ``p0`` of each triangle ``(p0, p1, p2)``, in radians; 0 for a degenerate corner."""
    a = _normalise(p1 - p0)
    b = _normalise(p2 - p0)
    return np.arccos(np.clip(np.sum(a * b, axis=-1), -1.0, 1.0))


def tangents(
    positions: NDArray,
    normals: NDArray,
    uvs: NDArray,
    indices: NDArray,
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """
    MikkTSpace tangents for ``(n, 3)`` positions, ``(n, 3)`` normals (as given), ``(n, 2)`` UVs and ``(m, 3)`` or
    ``(3m,)`` triangle indices: ``(tangent (n, 3) float32, sign (n,) float32 of +1 or -1)``. The normals are
    normalised for the projection only; the array passed in is not changed.
    """
    pos = np.asarray(positions, dtype=np.float64)
    nrm = _normalise(np.asarray(normals, dtype=np.float64))
    uv = np.asarray(uvs, dtype=np.float64)
    tri = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    n_vertices = pos.shape[0]
    if nrm.shape != pos.shape or uv.shape != (n_vertices, 2):
        raise ValueError(f"positions {pos.shape}, normals {nrm.shape}, uvs {uv.shape} disagree on the vertex count")
    if tri.size and (tri.min() < 0 or tri.max() >= n_vertices):
        raise ValueError("a triangle index is outside the vertex array")

    # 1. per triangle: tangent and bitangent from the UV derivatives, handedness from the UV area's sign
    p0, p1, p2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    t0, t1, t2 = uv[tri[:, 0]], uv[tri[:, 1]], uv[tri[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = t1 - t0, t2 - t0
    area = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]  # twice the signed UV area
    ok = np.abs(area) > 1e-20
    inv = np.where(ok, 1.0 / np.where(ok, area, 1.0), 0.0)[:, None]
    face_t = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) * inv
    face_b = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) * inv
    face_t = _normalise(face_t)
    face_b = _normalise(face_b)
    hand = np.where(area < 0.0, -1.0, 1.0)  # the triangle's handedness: a mirrored island is negative

    # 2. per corner, weighted by the corner angle; accumulated by smoothing group (position, normal, uv, handedness)
    angles = np.stack(
        [corner_angles(p0, p1, p2), corner_angles(p1, p2, p0), corner_angles(p2, p0, p1)], axis=1
    )  # (m, 3)
    corner_vertex = tri.reshape(-1)  # (3m,)
    corner_face = np.repeat(np.arange(tri.shape[0]), 3)
    corner_w = angles.reshape(-1)
    key_cols = np.concatenate([pos, nrm, uv], axis=1)  # the weld key per vertex: position, normal, uv
    _, group_of_vertex = np.unique(np.round(key_cols, 9), axis=0, return_inverse=True)
    group_of_vertex = group_of_vertex.reshape(-1)
    corner_group = group_of_vertex[corner_vertex] * 2 + (hand[corner_face] < 0).astype(np.int64)
    n_groups = int(group_of_vertex.max()) * 2 + 2 if n_vertices else 0
    acc_t = np.zeros((n_groups, 3))
    acc_b = np.zeros((n_groups, 3))
    np.add.at(acc_t, corner_group, face_t[corner_face] * corner_w[:, None])
    np.add.at(acc_b, corner_group, face_b[corner_face] * corner_w[:, None])

    # 3. per vertex: the group it belongs to with the handedness its faces gave it (a vertex shared by both
    # handednesses takes the one its first corner has: the reference splits such a vertex, and so does a loader
    # that keys corners on position, uv and normal)
    vertex_group = np.full(n_vertices, -1, dtype=np.int64)
    first = {}
    for c, v in enumerate(corner_vertex):
        if v not in first:
            first[v] = corner_group[c]
    for v, g in first.items():
        vertex_group[v] = g
    t_out = np.zeros((n_vertices, 3))
    b_out = np.zeros((n_vertices, 3))
    has = vertex_group >= 0
    t_out[has] = acc_t[vertex_group[has]]
    b_out[has] = acc_b[vertex_group[has]]
    # Gram-Schmidt against the given normal
    t_out = t_out - nrm * np.sum(t_out * nrm, axis=-1, keepdims=True)
    length = np.linalg.norm(t_out, axis=-1)
    degenerate = length < 1e-9
    t_out = _normalise(t_out)
    if degenerate.any():
        t_out[degenerate] = _any_perpendicular(nrm[degenerate])
        _LOGGER.debug(f"{int(degenerate.sum())} vertex tangent(s) had no UV area; a perpendicular was chosen")
    sign = np.where(np.sum(np.cross(nrm, t_out) * b_out, axis=-1) < 0.0, -1.0, 1.0)
    sign[degenerate] = 1.0
    _LOGGER.info(
        f"mikktspace: {n_vertices} vertices, {tri.shape[0]} triangles, {int((sign < 0).sum())} mirrored, "
        f"{int(degenerate.sum())} without UV area"
    )
    return t_out.astype(np.float32), sign.astype(np.float32)


if __name__ == "__main__":
    # smoke run: a quad in the XY plane with U along X and V along Y; the tangent is +X, the sign +1
    _p = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    _n = np.tile([0.0, 0.0, 1.0], (4, 1))
    _uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    _t, _s = tangents(_p, _n, _uv, np.array([[0, 1, 2], [0, 2, 3]]))
    print(_t, _s)
