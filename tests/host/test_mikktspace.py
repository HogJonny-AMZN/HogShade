"""
HogShade: the MikkTSpace generator on arbitrary data (T3b): tangents follow U and are tangent to the surface, the
sign flips on a mirrored island, custom normals are consumed and not recomputed, a corner without UV area falls
back to a perpendicular, and the shapes are checked; then the shader ball against Maya's own frame (the fixture
``hogshade.jobs.maya_mikktspace_dump`` wrote): the corners line up, the handedness is exact, the direction close.
Package: tests/host/test_mikktspace
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    assert np.all(np.abs(s) == 1.0), "every sign is +1 or -1"


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


def test_a_source_basis_is_used_flagged_or_refused(caplog):
    """A source's own tangents: mikktspace as given, unknown flagged and regenerated, another basis refused."""
    from hogshade.wgpu_host import with_tangents

    p, n, uv, tri = _quad()
    given = np.tile([0.0, 1.0, 0.0, -1.0], (4, 1))  # deliberately not what the UVs say: +Y, left-handed
    kept = with_tangents(p, n, uv, tri, tangents=given, tangent_basis="mikktspace")
    assert kept.tangent_basis == "mikktspace" and np.allclose(kept.vertices[:, 8:12], given), "used as given"
    with caplog.at_level("WARNING", logger="hogshade.wgpu_host"):
        redone = with_tangents(p, n, uv, tri, tangents=given, tangent_basis="unknown")
    assert "unknown basis: regenerated as MikkTSpace" in caplog.text
    assert redone.tangent_basis == "mikktspace" and np.allclose(redone.vertices[:, 8:11], [[1, 0, 0]], atol=1e-6)
    assert np.all(redone.vertices[:, 11] == 1.0)
    with pytest.raises(ValueError, match="requires MikkTSpace"):
        with_tangents(p, n, uv, tri, tangents=given, tangent_basis="maya-right-handed")
    with pytest.raises(ValueError, match=r"\(n, 4\)"):
        with_tangents(p, n, uv, tri, tangents=given[:, :3], tangent_basis="mikktspace")


# ----------------------------------------------------------------------------- parity with Maya on the shader ball

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "shaderBall_mikktspace.npz"


@pytest.fixture(scope="module")
def shader_ball_and_maya():
    """``load_obj`` of the shader ball and Maya's per-corner frame (``hogshade.jobs.maya_mikktspace_dump``)."""
    from hogshade import wgpu_host

    if not FIXTURE.exists():
        pytest.skip(f"no fixture {FIXTURE.name}; run hogshade.jobs.maya_mikktspace_dump")
    if not wgpu_host.lfs_hydrated(wgpu_host.SHADER_BALL):
        pytest.skip("shader ball not hydrated (LFS)")
    data = np.load(FIXTURE)
    return wgpu_host.load_obj(wgpu_host.SHADER_BALL), data, json.loads(str(data["meta"]))


def test_the_fixture_lines_up_with_load_obj_corner_for_corner(shader_ball_and_maya):
    """Same OBJ, same corners: face and vertex indices agree and the vertex positions hash the same."""
    from hogshade import wgpu_host

    mesh, data, meta = shader_ball_and_maya
    face, vertex, rows = wgpu_host.obj_corners(wgpu_host.SHADER_BALL)
    assert np.array_equal(face, data["face"]) and np.array_equal(vertex, data["vertex"])
    assert len(rows) == meta["corners"] and rows.max() + 1 == len(mesh.vertices)
    positions = [
        [float(x) for x in line.split()[1:4]]
        for line in wgpu_host.SHADER_BALL.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("v ")
    ]
    digest = hashlib.sha256(np.round(np.asarray(positions), 5).astype(np.float32).tobytes()).hexdigest()
    assert digest == meta["positions_sha256"], "Maya imported the same vertices in the same order"


def test_parity_with_maya_on_the_shader_ball(shader_ball_and_maya):
    """
    Maya 2026.3 exposes no MikkTSpace choice on the mesh (its ``tangentSpace`` enum: detectWindingRightHanded,
    rightHanded, detectWindingLeftHanded, leftHanded), so this is MikkTSpace against Maya's default basis, measured
    on 2026-10-04: the handedness agrees on every one of the 135,792 corners (20,628 mirrored on both sides), the
    direction agrees to a median of 0.8 degrees, 98 percent within 5 degrees, the worst corner 35 degrees (the two
    weight shared corners differently); the bars below hold those numbers with a little room.
    """
    from hogshade import wgpu_host

    mesh, data, _meta = shader_ball_and_maya
    _face, _vertex, rows = wgpu_host.obj_corners(wgpu_host.SHADER_BALL)
    ours_t = mesh.vertices[rows, 8:11]
    ours_sign = mesh.vertices[rows, 11]
    maya_t = data["tangent"].astype(np.float32)
    maya_t /= np.maximum(np.linalg.norm(maya_t, axis=1, keepdims=True), 1e-9)
    normals = mesh.vertices[rows, 3:6]
    assert np.abs(np.sum(ours_t * normals, axis=1)).max() < 1e-3, "our tangent is orthogonal to the given normal"
    assert np.array_equal(np.sign(ours_sign), data["sign"].astype(np.float32)), (
        "the handedness is exact, seams included"
    )
    assert (ours_sign < 0).sum() == 20628 == (data["sign"] < 0).sum()
    angle = np.degrees(np.arccos(np.clip(np.sum(ours_t * maya_t, axis=1), -1.0, 1.0)))
    assert np.median(angle) < 1.0, np.median(angle)
    assert (angle <= 5.0).mean() > 0.97, (angle <= 5.0).mean()
    assert angle.max() < 45.0, angle.max()
    assert not (angle > 90.0).any(), "no corner points the other way"
