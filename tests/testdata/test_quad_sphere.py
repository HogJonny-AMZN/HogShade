"""
HogShade: the quad sphere (a cube on a sphere with a clean 0 to 1 unwrap per face): the counts, every UV in the unit
square, the winding outward, the exact inverse of its map, the analytic tangent against a finite difference, and the
MikkTSpace tangents the host generates from its UVs against that analytic tangent, with no vertex split.
Package: tests/testdata/test_quad_sphere
"""

from __future__ import annotations

import numpy as np
import pytest

from hogshade import wgpu_host
from hogshade.testdata import quad_sphere as qs


def test_the_counts_and_the_unit_square_unwrap():
    n = 8
    positions, normals, uvs, indices = qs.build(n)
    side = n + 1
    assert positions.shape == normals.shape == (6 * side * side, 3) and uvs.shape == (6 * side * side, 2)
    assert indices.shape == (12 * n * n, 3) and indices.dtype == np.uint32
    assert uvs.min() == 0.0 and uvs.max() == 1.0, "every face is one 0 to 1 tile, nothing outside it"
    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1.0, atol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(positions - np.array(qs.CENTRE), axis=1), qs.RADIUS, atol=1e-12)
    for face in range(6):  # each face holds the whole tile once
        tile = uvs[face * side * side : (face + 1) * side * side]
        assert len(np.unique(tile, axis=0)) == side * side


def test_every_triangle_is_wound_outward_and_the_cells_are_nearly_equal_in_area():
    positions, _normals, _uvs, indices = qs.build(16)
    p0, p1, p2 = (positions[indices[:, k]] for k in range(3))
    cross = np.cross(p1 - p0, p2 - p0)
    outward = (p0 + p1 + p2) / 3 - np.array(qs.CENTRE)
    assert (np.einsum("ij,ij->i", cross, outward) > 0).all()
    area = np.linalg.norm(cross, axis=1) / 2
    assert area.max() / area.min() < 1.8, "the tangent-adjusted cube map keeps the cells close to equal"


def test_the_inverse_map_recovers_face_and_uv_at_every_interior_vertex():
    n = 16
    _positions, normals, uvs, _indices = qs.build(n)
    side = n + 1
    face, u, v = qs.face_uv(normals)
    s, t = uvs[:, 0], uvs[:, 1]
    interior = (s > 0) & (s < 1) & (t > 0) & (t < 1)  # an edge vertex belongs to two or three faces at once
    assert (face[interior] == np.repeat(np.arange(6), side * side)[interior]).all()
    np.testing.assert_allclose(u[interior], s[interior], atol=1e-9)
    np.testing.assert_allclose(v[interior], t[interior], atol=1e-9)


def test_the_analytic_tangent_is_the_derivative_along_u():
    rng = np.random.default_rng(3)
    face = rng.integers(0, 6, 200)
    u, v = rng.uniform(0.05, 0.95, 200), rng.uniform(0.05, 0.95, 200)

    def point(uc):
        a, b, c = (qs._AXES[face, k] for k in range(3))
        x, y = np.tan((2 * uc - 1) * np.pi / 4), np.tan((2 * v - 1) * np.pi / 4)
        p = c + x[:, None] * a + y[:, None] * b
        return p / np.linalg.norm(p, axis=1, keepdims=True)

    fd = point(u + 1e-6) - point(u - 1e-6)
    fd /= np.linalg.norm(fd, axis=1, keepdims=True)
    np.testing.assert_allclose(qs.tangent_at(face, u, v), fd, atol=1e-6)


def test_the_hosts_mikktspace_tangents_follow_u_without_a_split_and_are_all_right_handed():
    n = 24
    mesh = wgpu_host.quad_sphere(n)
    side = n + 1
    assert mesh.vertices.shape == (6 * side * side, wgpu_host.VERTEX_FLOATS), "no vertex was split: no mirrored island"
    assert mesh.tangent_basis == "mikktspace"
    assert (mesh.vertices[:, wgpu_host.COL_TANGENT_SIGN] == 1.0).all(), "every face reads unmirrored from outside"
    normals = mesh.vertices[:, wgpu_host.COL_NORMAL]
    face, u, v = qs.face_uv(normals)
    interior = (mesh.vertices[:, 6] > 0.04) & (mesh.vertices[:, 6] < 0.96) & (mesh.vertices[:, 7] > 0.04)
    interior &= mesh.vertices[:, 7] < 0.96
    ours = mesh.vertices[:, wgpu_host.COL_TANGENT][interior]
    exact = qs.tangent_at(face[interior], u[interior], v[interior])
    angle = np.degrees(np.arccos(np.clip(np.sum(ours * exact, axis=1), -1.0, 1.0)))
    assert np.median(angle) < 0.5 and angle.max() < 3.0, (np.median(angle), angle.max())


def test_a_subdivision_below_one_is_refused_and_a_mesh_name_that_does_not_exist_names_the_choices():
    with pytest.raises(qs.QuadSphereError, match="at least 1"):
        qs.build(0)
    with pytest.raises(ValueError, match="no mesh named 'nope'; one of \\['quad-sphere', 'shader-ball'\\]"):
        wgpu_host.load_mesh("nope")
    assert wgpu_host.load_mesh("quad-sphere").vertices.shape[1] == wgpu_host.VERTEX_FLOATS
