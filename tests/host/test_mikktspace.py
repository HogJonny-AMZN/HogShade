"""
HogShade: the MikkTSpace generator on arbitrary data (T3b): tangents follow U and are tangent to the surface, the
sign flips on a mirrored island, custom normals are consumed and not recomputed, a corner without UV area falls
back to a perpendicular, and the shapes are checked.
Package: tests/host/test_mikktspace
"""

from __future__ import annotations

import numpy as np
import pytest

from hogshade.mikktspace import TANGENT_BASES, tangents


def _quad(mirror_u: bool = False):
    p = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    n = np.tile([0.0, 0.0, 1.0], (4, 1))
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    if mirror_u:
        uv[:, 0] = 1.0 - uv[:, 0]
    return p, n, uv, np.array([[0, 1, 2], [0, 2, 3]])


def _uv_sphere(rings: int = 12, segments: int = 24):
    us = np.linspace(0.0, 1.0, segments + 1)
    vs = np.linspace(0.0, 1.0, rings + 1)
    uu, vv = np.meshgrid(us, vs)
    theta, phi = uu * 2 * np.pi, vv * np.pi
    x = np.sin(phi) * np.cos(theta)
    y = np.cos(phi)
    z = -np.sin(phi) * np.sin(theta)
    p = np.stack([x, y, z], axis=-1).reshape(-1, 3)
    uv = np.stack([uu, vv], axis=-1).reshape(-1, 2)
    tris = []
    w = segments + 1
    for r in range(rings):
        for s in range(segments):
            a, b, c, d = r * w + s, r * w + s + 1, (r + 1) * w + s, (r + 1) * w + s + 1
            tris += [[a, c, b], [b, c, d]]
    return p, p.copy(), uv, np.array(tris)


def test_a_quad_with_u_along_x_has_tangent_x_and_sign_plus_one():
    t, s = tangents(*_quad())
    assert np.allclose(t, [[1, 0, 0]] * 4, atol=1e-6) and np.all(s == 1.0)
    assert t.dtype == np.float32 and s.dtype == np.float32


def test_a_mirrored_island_flips_the_sign_and_keeps_a_unit_tangent():
    t, s = tangents(*_quad(mirror_u=True))
    assert np.allclose(t, [[-1, 0, 0]] * 4, atol=1e-6) and np.all(s == -1.0)
    assert np.allclose(np.linalg.norm(t, axis=-1), 1.0)


def test_sphere_tangents_are_unit_tangent_to_the_surface_and_follow_u():
    p, n, uv, tri = _uv_sphere()
    t, s = tangents(p, n, uv, tri)
    norms = np.linalg.norm(t, axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-5)
    assert np.allclose(np.sum(t * n, axis=-1), 0.0, atol=1e-5), "orthogonal to the normal"
    # away from the poles, increasing U moves along -z at theta 0 (x=1): the tangent there is close to (0, 0, -1)
    equator = np.isclose(uv[:, 1], 0.5) & np.isclose(uv[:, 0], 0.0)
    assert equator.any()
    assert np.allclose(t[equator], [[0, 0, -1]], atol=1e-3), t[equator]
    assert np.all(s[~np.isin(np.arange(len(p)), [])] != 0)


def test_custom_normals_are_consumed_not_recomputed():
    p, n, uv, tri = _uv_sphere()
    tilted = n @ np.array([[0.96, 0.0, 0.28], [0.0, 1.0, 0.0], [-0.28, 0.0, 0.96]]).T  # every normal rotated 16 degrees
    before = tilted.copy()
    t, _s = tangents(p, tilted, uv, tri)
    assert np.array_equal(tilted, before), "the normals array is not changed"
    assert np.allclose(np.sum(t * tilted / np.linalg.norm(tilted, axis=-1, keepdims=True), axis=-1), 0.0, atol=1e-5), (
        "the frame is built around the given normal, not the geometric one"
    )


def test_a_degenerate_corner_falls_back_to_a_perpendicular_and_shapes_are_checked():
    p = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)  # collinear: no UV area
    n = np.tile([0.0, 1.0, 0.0], (3, 1))
    uv = np.zeros((3, 2))
    t, s = tangents(p, n, uv, np.array([[0, 1, 2]]))
    assert np.allclose(np.linalg.norm(t, axis=-1), 1.0) and np.allclose(np.sum(t * n, axis=-1), 0.0)
    assert np.all(s == 1.0)
    with pytest.raises(ValueError, match="disagree on the vertex count"):
        tangents(p, n[:2], uv, np.array([[0, 1, 2]]))
    with pytest.raises(ValueError, match="outside the vertex array"):
        tangents(p, n, uv, np.array([[0, 1, 7]]))
    assert TANGENT_BASES == ("mikktspace", "unknown", "none")
