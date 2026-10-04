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

The output is per vertex, so a vertex that faces of both handednesses share (the seam of a mirrored island)
cannot carry both signs: ``split_mixed_handedness`` duplicates such a vertex for its mirrored corners first
(the reference's per-corner output, made indexed), ``tangents`` warns when it still meets one and gives it its
first corner's sign. ``wgpu_host.with_tangents`` splits before it generates; ``load_obj`` keys a corner on its
face's handedness as well, so it never builds a mixed vertex.

The normals are consumed, never recomputed: custom normals survive (the owner's point), and the frame is built
around whatever the source provides. Welding is by equality of position, normal and UV rounded to nine decimals
(the reference's rule, with float noise forgiven); a mesh whose corners were already de-duplicated that way
(``wgpu_host.load_obj``) welds to itself.
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


def _normalise(v: NDArray[np.floating], eps: float = 1e-12) -> NDArray[np.float64]:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def _any_perpendicular(n: NDArray[np.floating]) -> NDArray[np.float64]:
    """A unit vector perpendicular to each unit normal (the fallback for a corner with no UV area)."""
    helper = np.where(np.abs(n[:, :1]) > 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    t = np.cross(helper, n)
    return _normalise(t)


def corner_angles(
    p0: NDArray[np.floating], p1: NDArray[np.floating], p2: NDArray[np.floating], eps: float = 1e-12
) -> NDArray[np.float64]:
    """
    The interior angle at ``p0`` of each triangle ``(p0, p1, p2)``, in radians; 0 for a degenerate corner (an
    edge shorter than ``eps``, whose direction is undefined).
    """
    e1, e2 = p1 - p0, p2 - p0
    ok = (np.linalg.norm(e1, axis=-1) > eps) & (np.linalg.norm(e2, axis=-1) > eps)
    a = _normalise(e1)
    b = _normalise(e2)
    return np.where(ok, np.arccos(np.clip(np.sum(a * b, axis=-1), -1.0, 1.0)), 0.0)


def face_handedness(uvs: NDArray[np.floating], indices: NDArray[np.integer]) -> NDArray[np.float64]:
    """Per triangle, +1 or -1 from the sign of its UV area: a mirrored island is negative (zero area counts as +1)."""
    uv = np.asarray(uvs, dtype=np.float64)
    tri = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    d1 = uv[tri[:, 1]] - uv[tri[:, 0]]
    d2 = uv[tri[:, 2]] - uv[tri[:, 0]]
    area = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    return np.where(area < 0.0, -1.0, 1.0)


def mixed_handedness(uvs: NDArray[np.floating], indices: NDArray[np.integer], n_vertices: int) -> NDArray[np.bool_]:
    """Which vertices faces of both handednesses share: the ones a per-vertex sign cannot serve."""
    tri = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    hand = face_handedness(uvs, tri)
    corner_vertex = tri.reshape(-1)
    corner_hand = np.repeat(hand, 3)
    seen_pos = np.zeros(n_vertices, dtype=bool)
    seen_neg = np.zeros(n_vertices, dtype=bool)
    seen_pos[corner_vertex[corner_hand > 0]] = True
    seen_neg[corner_vertex[corner_hand < 0]] = True
    return seen_pos & seen_neg


def split_mixed_handedness(
    positions: NDArray[np.floating],
    normals: NDArray[np.floating],
    uvs: NDArray[np.floating],
    indices: NDArray[np.integer],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.int64], int]:
    """
    The arrays with every vertex that both handednesses share duplicated for its mirrored (negative) corners, which
    then index the copy: ``(positions, normals, uvs, indices, number split)``. Unchanged arrays and 0 when there is
    nothing to split. The order of the original vertices is kept; the copies follow them.
    """
    pos = np.asarray(positions, dtype=np.float64)
    nrm = np.asarray(normals, dtype=np.float64)
    uv = np.asarray(uvs, dtype=np.float64)
    tri = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
    n = pos.shape[0]
    mixed = mixed_handedness(uv, tri, n)
    if not mixed.any():
        return pos, nrm, uv, tri, 0
    mixed_ids = np.nonzero(mixed)[0]
    copy_of = np.full(n, -1, dtype=np.int64)
    copy_of[mixed_ids] = n + np.arange(len(mixed_ids))
    corner_hand = np.repeat(face_handedness(uv, tri), 3)
    flat = tri.reshape(-1).copy()
    move = (corner_hand < 0) & mixed[flat]
    flat[move] = copy_of[flat[move]]
    _LOGGER.info(
        f"split {len(mixed_ids)} vertex/vertices shared by both handednesses into a copy for the mirrored side"
    )
    return (
        np.concatenate([pos, pos[mixed_ids]]),
        np.concatenate([nrm, nrm[mixed_ids]]),
        np.concatenate([uv, uv[mixed_ids]]),
        flat.reshape(-1, 3),
        len(mixed_ids),
    )


def tangents(
    positions: NDArray[np.floating],
    normals: NDArray[np.floating],
    uvs: NDArray[np.floating],
    indices: NDArray[np.integer],
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

    # 3. per vertex: the group it belongs to with the handedness its faces gave it. A vertex shared by both
    # handednesses takes the one its first corner has, and is warned about: the reference splits such a vertex
    # (split_mixed_handedness does it for an indexed mesh; load_obj never builds one)
    mixed = mixed_handedness(uv, tri, n_vertices)
    if mixed.any():
        _LOGGER.warning(
            f"{int(mixed.sum())} vertex/vertices are shared by faces of both handednesses and keep their first "
            f"corner's sign; split them first (split_mixed_handedness) for a correct mirrored seam"
        )
    vertex_group = np.full(n_vertices, -1, dtype=np.int64)
    _, first_corner = np.unique(corner_vertex, return_index=True)  # each vertex's first corner, in one pass
    vertex_group[corner_vertex[first_corner]] = corner_group[first_corner]
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
