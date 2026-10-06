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

    fd = qs.direction(face, u + 1e-6, v) - qs.direction(face, u - 1e-6, v)
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
    uv = mesh.vertices[:, wgpu_host.COL_UV]
    interior = ((uv > 0.04) & (uv < 0.96)).all(axis=1)
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


def test_build_refuses_what_would_turn_it_inside_out_or_into_a_point():
    for bad in (0, -3, 2.7, "8", None):
        with pytest.raises(qs.QuadSphereError, match="subdivisions is"):
            qs.build(bad)
    for radius in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(qs.QuadSphereError, match="radius is finite and positive"):
            qs.build(4, radius)
    for centre in ((0.0, 0.0), (0.0, 0.0, float("nan")), (1, 2, 3, 4)):
        with pytest.raises(qs.QuadSphereError, match="centre is three finite numbers"):
            qs.build(4, 1.0, centre)
    positions, normals, _uvs, _idx = qs.build(np.int64(4), 2.5, (1.0, -2.0, 3.0))
    np.testing.assert_allclose(positions - np.array([1.0, -2.0, 3.0]), 2.5 * normals, atol=1e-12)


def test_face_uv_refuses_a_zero_or_non_finite_direction_and_resolves_an_edge_to_one_valid_face():
    for bad in ([[0.0, 0.0, 0.0]], [[1.0, np.nan, 0.0]], [[np.inf, 0.0, 0.0]], [1.0, 0.0, 0.0]):
        with pytest.raises(qs.QuadSphereError, match=r"\(N, 3\), finite and nonzero"):
            qs.face_uv(np.array(bad))
    edge = np.array([[1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [-1.0, 0.0, 1.0]]) * 3.0  # an edge, a corner, an edge; not unit
    face, u, v = qs.face_uv(edge)
    assert ((u >= 0.0) & (u <= 1.0) & (v >= 0.0) & (v <= 1.0)).all(), "a tie still lands on its face's tile"
    back = qs.direction(face, u, v)
    np.testing.assert_allclose(back, edge / np.linalg.norm(edge, axis=1, keepdims=True), atol=1e-12)
