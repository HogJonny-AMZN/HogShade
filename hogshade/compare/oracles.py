"""
HogShade: the oracle checks: the right answer is computable, so nothing is compared against another host.
Package: hogshade/compare/oracles

An oracle reads one capture set and reports measurements; the case's thresholds judge them. The two here are the
quad-sphere probes that proved the wgpu host, moved out of its tests: a ray through each pixel is intersected with the
mesh's own triangles (the barycentric interpolation the rasteriser performs), which gives the face, the texture
coordinate, the normal and the tangent the pixel must show, so the texel it must display is a lookup. No vertex
proxy and no seam to avoid.

**Independence.** The rays come from the *request's* camera by plain basis vectors (forward, right, up, a tangent of the
field of view), not from the host's view-projection matrix, so a handedness or projection fault in the host's camera
shows up as a disagreement instead of cancelling out. The sphere only picks the cell to look in.

**Controls.** Each check takes a parameter that makes its expectation wrong on purpose (``flip_v`` for the texel check,
``flip_expectation`` for the normal check). A case that sets it expects to fail (``"expect": "fail"``); if it passes,
the instrument cannot tell right from wrong and the run says so.
"""

from __future__ import annotations

import functools
import logging as _logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from hogshade.compare.captureset import CaptureSet
from hogshade.compare.cases import Case, CheckSpec
from hogshade.testdata import quad_sphere as qs
from hogshade.testdata import synthetic

_MODULE_NAME = "hogshade.compare.oracles"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

#: A pixel is probed only where the sphere is not grazing and not near a face edge (where two faces' tiles meet).
MIN_FACING = 0.35
EDGE_MARGIN = 0.04


class OracleError(ValueError):
    """A capture the oracle cannot measure (the wrong mesh, no scene frame, no covered pixels); the message says why."""


@dataclass(frozen=True)
class Probe:
    """The pixels an oracle reads and what each must show, all arrays of one length."""

    rows: NDArray[np.int_]
    cols: NDArray[np.int_]
    face: NDArray[np.int_]
    u: NDArray[np.float64]
    v: NDArray[np.float64]
    normal: NDArray[np.float64]
    tangent: NDArray[np.float64]


def _camera_rays(request, stride: int) -> tuple[NDArray, NDArray, NDArray, NDArray]:
    """``(rows, cols, origin, direction)``: a ray through the centre of every ``stride``-th pixel, from the request."""
    width, height = request.size
    cam = request.camera
    eye = np.array(cam.eye, dtype=np.float64)
    forward = np.array(cam.target, dtype=np.float64) - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.array(cam.up, dtype=np.float64))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    half = math.tan(math.radians(cam.fov_y_deg) / 2.0)
    rows, cols = np.mgrid[0:height:stride, 0:width:stride]
    ndc_x = (cols + 0.5) / width * 2.0 - 1.0
    ndc_y = 1.0 - (rows + 0.5) / height * 2.0
    direction = (
        forward[None, None, :]
        + (ndc_x * half * (width / height))[..., None] * right[None, None, :]
        + (ndc_y * half)[..., None] * up[None, None, :]
    )
    direction /= np.linalg.norm(direction, axis=-1, keepdims=True)
    origin = np.broadcast_to(eye, direction.shape)
    return rows, cols, origin, direction


@functools.lru_cache(maxsize=4)
def _mesh(subdivisions: int):
    positions, normals, uvs, _indices = qs.build(subdivisions)
    side = subdivisions + 1
    tangents = qs.tangent_at(np.repeat(np.arange(6), side * side), uvs[:, 0], uvs[:, 1])
    return positions, normals, uvs, tangents


def _mesh_hit(face, u, v, origin, direction, subdivisions: int):
    """
    Where each ray meets the quad sphere's own triangles (Moeller-Trumbore) in the cell of ``(face, u, v)`` and its
    eight neighbours, nearest wins; ``(u, v, normal, tangent)`` interpolated barycentrically there.
    """
    positions, normals, uvs, tangents = _mesh(subdivisions)
    side = subdivisions + 1
    cell_i = np.clip(np.floor(u * subdivisions).astype(int), 0, subdivisions - 1)
    cell_j = np.clip(np.floor(v * subdivisions).astype(int), 0, subdivisions - 1)
    count = len(u)
    best_t = np.full(count, np.inf)
    best = np.zeros((count, 3), dtype=np.int64)
    best_w = np.zeros((count, 3))
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ci, cj = np.clip(cell_i + di, 0, subdivisions - 1), np.clip(cell_j + dj, 0, subdivisions - 1)
            v00 = face * side * side + cj * side + ci
            v10, v11, v01 = v00 + 1, v00 + side + 1, v00 + side
            for tri in ((v00, v10, v11), (v00, v11, v01)):
                p0, p1, p2 = (positions[k] for k in tri)
                e1, e2 = p1 - p0, p2 - p0
                pvec = np.cross(direction, e2)
                det = np.einsum("ij,ij->i", e1, pvec)
                ok = np.abs(det) > 1e-12
                inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
                tvec = origin - p0
                a = np.einsum("ij,ij->i", tvec, pvec) * inv
                qvec = np.cross(tvec, e1)
                b = np.einsum("ij,ij->i", direction, qvec) * inv
                dist = np.einsum("ij,ij->i", e2, qvec) * inv
                inside = ok & (a >= -1e-9) & (b >= -1e-9) & (a + b <= 1.0 + 1e-9) & (dist > 0.0) & (dist < best_t)
                best_t = np.where(inside, dist, best_t)
                best = np.where(inside[:, None], np.stack(tri, axis=1), best)
                best_w = np.where(inside[:, None], np.stack([1.0 - a - b, a, b], axis=1), best_w)
    if not np.isfinite(best_t).all():
        raise OracleError(f"{int((~np.isfinite(best_t)).sum())} rays met no triangle of their cell")

    def lerp(values):
        return np.einsum("ij,ijk->ik", best_w, values[best])

    hit_uv, normal, tangent = lerp(uvs), lerp(normals), lerp(tangents)
    return (
        hit_uv[:, 0],
        hit_uv[:, 1],
        normal / np.linalg.norm(normal, axis=1, keepdims=True),
        tangent / np.linalg.norm(tangent, axis=1, keepdims=True),
    )


def probe(captured: CaptureSet, stride: int = 3, subdivisions: int = qs.SUBDIVISIONS) -> Probe:
    """
    The pixels to read in ``captured`` and what each must show: every ``stride``-th covered, non-grazing pixel away from
    a face edge, with the mesh's interpolated face, ``(u, v)``, normal and tangent there. Needs the quad sphere, a
    coverage mask and a scene frame.
    """
    request = captured.request
    if request.mesh != "quad-sphere":
        raise OracleError(f"the quad-sphere oracles need mesh 'quad-sphere', the capture is of {request.mesh!r}")
    if captured.scene is None or captured.coverage is None:
        raise OracleError(f"the capture is level {captured.level}: a scene frame and a coverage mask are needed")
    rows, cols, origin, direction = _camera_rays(request, stride)
    oc = origin - np.array(qs.CENTRE)
    b = np.sum(oc * direction, axis=-1)
    disc = b * b - (np.sum(oc * oc, axis=-1) - qs.RADIUS**2)
    hit = disc >= 0.0
    nearest = -b - np.sqrt(np.maximum(disc, 0.0))
    hit &= nearest > 0.0  # a sphere behind the ray's origin is not a hit
    point = origin + nearest[..., None] * direction
    normal = (point - np.array(qs.CENTRE)) / qs.RADIUS
    facing = np.sum(normal * -direction, axis=-1)
    face, u, v = qs.face_uv(normal.reshape(-1, 3))
    face, u, v = (a.reshape(rows.shape) for a in (face, u, v))
    keep = (
        hit
        & captured.coverage[rows, cols]
        & (facing > MIN_FACING)
        & (u > EDGE_MARGIN)
        & (u < 1 - EDGE_MARGIN)
        & (v > EDGE_MARGIN)
        & (v < 1 - EDGE_MARGIN)
    )
    face, u, v = face[keep], u[keep], v[keep]
    if not len(u):
        raise OracleError("no covered, non-grazing pixel lies on the sphere: nothing to read")
    mesh_u, mesh_v, mesh_normal, mesh_tangent = _mesh_hit(face, u, v, origin[keep], direction[keep], subdivisions)
    return Probe(rows[keep], cols[keep], face, mesh_u, mesh_v, mesh_normal, mesh_tangent)


def _texels(u, v, size: int, flip_v: bool = False) -> tuple[NDArray, NDArray]:
    """The ``(col, row)`` of a ``size`` map each coordinate lands in (V up; ``flip_v``: V as the row index, wrong)."""
    cols = np.minimum(((u % 1.0) * size).astype(int), size - 1)
    rows = np.minimum(((v if flip_v else 1.0 - v % 1.0) * size).astype(int), size - 1)
    return cols, rows


def _flat_around(image: NDArray, cols: NDArray, rows: NDArray, spread: int, half: int = 14) -> NDArray[np.bool_]:
    """Which texels sit in a neighbourhood whose values differ by at most ``spread``: where filtering cannot matter."""
    out = np.zeros(len(cols), dtype=bool)
    for i, (c, r) in enumerate(zip(cols, rows, strict=True)):
        win = image[max(r - half, 0) : r + half + 1, max(c - half, 0) : c + half + 1]
        flat = win.reshape(-1, win.shape[-1] if win.ndim == 3 else 1)
        out[i] = np.ptp(flat.astype(np.int64), axis=0).max() <= spread
    return out


def _frame(captured: CaptureSet, data_range: float) -> NDArray[np.float64]:
    """The captured scene frame as fractions of the case's data range."""
    return np.asarray(captured.scene, dtype=np.float64) / data_range


def quad_sphere_texel(captured: CaptureSet, case: Case) -> dict[str, float]:
    """
    The fraction of pixels on a flat part of a synthetic map whose captured value equals that map's texel at the
    pixel's coordinate, within ``tolerance`` of the data range. Parameters: ``map`` (a suffix such as ``_R``),
    ``gray`` (true for a one-channel map shown as grey), ``spread`` (how flat counts as flat, in 8-bit levels),
    ``tolerance`` (default 0.05), ``stride`` (default 3), ``map_size`` (default the generator's) and ``flip_v``
    (the control: take V as the row index).
    """
    from hogshade.texture_cook.colour import srgb_to_linear

    p = case.check.params
    suffix = p["map"]
    size = int(p.get("map_size", synthetic.SIZE))
    flip_v = bool(p.get("flip_v", False))
    data_range = case.check.data_range
    assert data_range is not None  # cases.load refuses a texel check without it
    probed = probe(captured, int(p.get("stride", 3)))
    image = synthetic.render_map(suffix, None, size)
    cols, rows = _texels(probed.u, probed.v, size, flip_v)
    flat = _flat_around(image, cols, rows, int(p.get("spread", 0)))
    texel = image[rows[flat], cols[flat]].astype(np.float64) / 255.0
    want = np.repeat(texel[:, None], 3, axis=1) if p.get("gray", True) else srgb_to_linear(texel)
    got = _frame(captured, data_range)[probed.rows[flat], probed.cols[flat]]
    tolerance = float(p.get("tolerance", 0.05))
    pixels = int(flat.sum())
    agreement = float((np.abs(got - want).max(axis=1) < tolerance).mean()) if pixels else 0.0
    return {"agreement": agreement, "pixels": float(pixels), "probed": float(len(probed.u))}


def quad_sphere_normal(captured: CaptureSet, case: Case) -> dict[str, float]:
    """
    For the texels that lean in V (green) and in U (red), the fraction of pixels whose captured shading normal
    equals the world normal the authored texel produces on the analytic frame (``*_authored``) and the fraction that
    equal it with the channel flipped (``*_flipped``). A debug view of the shading normal is expected (packed
    ``n * 0.5 + 0.5`` times the data range). Parameters: ``stride``, ``map_size`` and ``flip_expectation`` (the control:
    ``green``, ``red`` or ``both`` swaps what counts as authored and flipped for that channel).
    """
    p = case.check.params
    size = int(p.get("map_size", synthetic.SIZE))
    flip = p.get("flip_expectation")
    data_range = case.check.data_range
    assert data_range is not None
    probed = probe(captured, int(p.get("stride", 3)))
    image = synthetic.render_map("_N", None, size)
    cols, rows = _texels(probed.u, probed.v, size)
    flat = _flat_around(image, cols, rows, 2)
    n, t = probed.normal[flat], probed.tangent[flat]
    b = np.cross(n, t)  # every face is right-handed: the handedness sign is +1
    rg = image[rows[flat], cols[flat]][:, :2].astype(np.float64) / 255.0 * 2.0 - 1.0
    ts = np.stack([rg[:, 0], rg[:, 1], np.sqrt(np.clip(1.0 - (rg**2).sum(1), 0.0, 1.0))], axis=1)
    got = _frame(captured, data_range)[probed.rows[flat], probed.cols[flat]] * 2.0 - 1.0
    got /= np.linalg.norm(got, axis=1, keepdims=True)

    def world(tangent_space: NDArray) -> NDArray:
        w = tangent_space[:, :1] * t + tangent_space[:, 1:2] * b + tangent_space[:, 2:3] * n
        return w / np.linalg.norm(w, axis=1, keepdims=True)

    out: dict[str, float] = {}
    for axis, name in ((1, "green"), (0, "red")):
        leans = np.abs(ts[:, axis]) > 0.2
        flipped = ts.copy()
        flipped[:, axis] *= -1.0
        as_authored = np.linalg.norm(got - world(ts), axis=1)[leans] < 0.1
        as_flipped = np.linalg.norm(got - world(flipped), axis=1)[leans] < 0.1
        if flip in (name, "both"):
            as_authored, as_flipped = as_flipped, as_authored  # the control: the expectation is wrong on purpose
        count = int(leans.sum())
        out[f"{name}_pixels"] = float(count)
        out[f"{name}_authored"] = float(as_authored.mean()) if count else 0.0
        out[f"{name}_flipped"] = float(as_flipped.mean()) if count else 1.0
    return out


Check = Callable[[CaptureSet, Case], dict[str, float]]

CHECKS: Mapping[str, CheckSpec] = MappingProxyType(
    {
        "quad-sphere-texel": CheckSpec(
            "quad-sphere-texel",
            ("oracle",),
            True,
            "the fraction of pixels showing the synthetic map's texel at their coordinate (a debug view of the map)",
        ),
        "quad-sphere-normal": CheckSpec(
            "quad-sphere-normal",
            ("oracle",),
            True,
            "the normal map's red and green conventions against the analytic tangent frame (the shading-normal view)",
        ),
    }
)

FUNCTIONS: Mapping[str, Check] = MappingProxyType(
    {"quad-sphere-texel": quad_sphere_texel, "quad-sphere-normal": quad_sphere_normal}
)


def run(case: Case, captured: CaptureSet) -> dict[str, float]:
    """Run the case's check on a capture. ``KeyError``: an unregistered check; ``OracleError``: cannot measure."""
    return FUNCTIONS[case.check.name](captured, case)
