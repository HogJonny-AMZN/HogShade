"""
HogShade: the oracle checks, without a GPU: a frame built to be exactly right passes, and the same frame wrong fails.
Package: tests/compare/test_oracles

The instrument is shown to produce both answers. The ideal frames are built from the oracle's own probe (the geometry
is checked separately, against pixels whose answer is worked out by hand), so a pass here means the comparison logic is
right; the controls and the shifted frames show it is not blind.
"""

from __future__ import annotations

import ideal_frames
import numpy as np
import pytest

from hogshade.compare import oracles
from hogshade.compare.captureset import CaptureSet, Manifest
from hogshade.compare.cases import Case, Check
from hogshade.compare.oracles import OracleError
from hogshade.compare.request import CaptureRequest
from hogshade.compare.verdict import Threshold
from hogshade.testdata import synthetic

SIZE = 128
MAP = synthetic.SIZE
REQUEST = CaptureRequest.from_dict(
    {
        "id": "oracle-unit",
        "mesh": "quad-sphere",
        "camera": {
            "eye": [0.0, 0.0, 4.0],
            "target": [0.0, 0.0, 0.0],
            "up": [0.0, 1.0, 0.0],
            "fov_y_deg": 32.0,
            "near": 0.1,
            "far": 50.0,
        },
        "rig": {"environment": "studio_small_09"},
        "size": [SIZE, SIZE],
    }
)


def _capture(frame: np.ndarray, coverage: np.ndarray, request: CaptureRequest = REQUEST) -> CaptureSet:
    return ideal_frames.capture(frame, coverage, request)


def _all_pixels() -> oracles.Probe:
    return ideal_frames.all_pixels(REQUEST)


def _ideal_texel(suffix: str, gray: bool, data_range: float = 1.0) -> CaptureSet:
    return ideal_frames.ideal_texel(REQUEST, suffix, gray, data_range)


def _ideal_normal(data_range: float = 1.0, flip_green: bool = False) -> CaptureSet:
    return ideal_frames.ideal_normal(REQUEST, data_range, flip_green)


def _case(check: str, params: dict, data_range: float = 1.0, expect: str = "pass") -> Case:
    return Case(
        "unit",
        "oracle",
        REQUEST,
        Check(check, data_range, params),
        (Threshold("agreement", 0.99, 0.9),),
        expect,
    )


# ---- the geometry, against pixels whose answer is worked out by hand ------------------------------------------------


def test_the_probe_reads_the_pixel_the_camera_looks_at_as_the_middle_of_the_face_in_front_of_it() -> None:
    """Camera at +Z looking at the origin: the middle is the +Z face's (0.5, 0.5), normal +Z, u along +X."""
    p = _all_pixels()
    centre = np.argmin((p.rows - SIZE // 2) ** 2 + (p.cols - SIZE // 2) ** 2)
    assert p.face[centre] == 4  # +Z in the face table
    assert abs(p.u[centre] - 0.5) < 0.01 and abs(p.v[centre] - 0.5) < 0.01
    np.testing.assert_allclose(p.normal[centre], [0.0, 0.0, 1.0], atol=0.02)
    np.testing.assert_allclose(p.tangent[centre], [1.0, 0.0, 0.0], atol=0.02)  # u increases towards +X


def test_a_pixel_right_of_centre_has_a_larger_u_and_one_above_it_a_larger_v() -> None:
    p = _all_pixels()
    right = np.argmin((p.rows - SIZE // 2) ** 2 + (p.cols - (SIZE // 2 + 26)) ** 2)
    above = np.argmin((p.rows - (SIZE // 2 - 24)) ** 2 + (p.cols - SIZE // 2) ** 2)
    assert p.u[right] > 0.65 and abs(p.v[right] - 0.5) < 0.02 and p.normal[right][0] > 0.3
    assert p.v[above] > 0.65 and abs(p.u[above] - 0.5) < 0.02 and p.normal[above][1] > 0.3


def test_the_probe_skips_pixels_near_a_face_edge_and_grazing_ones() -> None:
    p = _all_pixels()
    assert p.u.min() > oracles.EDGE_MARGIN - 0.01 and p.u.max() < 1 - oracles.EDGE_MARGIN + 0.01
    assert p.v.min() > oracles.EDGE_MARGIN - 0.01 and p.v.max() < 1 - oracles.EDGE_MARGIN + 0.01
    assert len(set(p.face.tolist())) >= 2, "the picture shows more than one face of the cube"


def test_the_oracle_s_camera_is_not_the_host_s_matrix() -> None:
    """The rays come from basis vectors, and agree with the host's view-projection for the same camera."""
    from hogshade import wgpu_host

    cam = REQUEST.camera
    scene = wgpu_host.Scene(width=SIZE, height=SIZE, fov_y_deg=cam.fov_y_deg, camera=(cam.eye, cam.target, cam.up))
    inverse = np.linalg.inv(scene.view_proj()[0])
    rows, cols, origin, direction = oracles._camera_rays(REQUEST, 16)
    ndc = np.stack(
        [
            (cols + 0.5) / SIZE * 2 - 1,
            1 - (rows + 0.5) / SIZE * 2,
            np.zeros(rows.shape),
            np.ones(rows.shape),
        ],
        axis=-1,
    )
    near = ndc @ inverse.T
    near = near[..., :3] / near[..., 3:4]
    along = (near - origin) / np.linalg.norm(near - origin, axis=-1, keepdims=True)
    np.testing.assert_allclose(along, direction, atol=1e-9)


# ---- the texel check ------------------------------------------------------------------------------------------------

TEXELS = [("_R", True, 0), ("_M", True, 0), ("_AO", True, 16), ("_BC", False, 0)]


@pytest.mark.parametrize(("suffix", "gray", "spread"), TEXELS, ids=["roughness", "metalness", "ao", "colour"])
def test_a_frame_that_shows_exactly_the_texels_passes(suffix: str, gray: bool, spread: int) -> None:
    case = _case("quad-sphere-texel", {"map": suffix, "gray": gray, "spread": spread})
    got = oracles.run(case, _ideal_texel(suffix, gray))
    assert got["agreement"] == 1.0 and got["pixels"] >= 50, got


@pytest.mark.parametrize(("suffix", "gray"), [("_M", True), ("_BC", False)], ids=["metalness", "colour"])
def test_the_v_flipped_control_fails(suffix: str, gray: bool) -> None:
    """The same frame, the expectation wrong on purpose: V taken as the row index. The roughness view (a function of U
    alone) is rightly not asked."""
    control = _case("quad-sphere-texel", {"map": suffix, "gray": gray, "flip_v": True}, expect="fail")
    got = oracles.run(control, _ideal_texel(suffix, gray))
    assert got["pixels"] >= 50 and got["agreement"] < 0.8, got


def test_a_frame_shifted_sideways_fails() -> None:
    ideal = _ideal_texel("_M", True)
    shifted = _capture(np.roll(ideal.scene, 9, axis=1), ideal.coverage)
    got = oracles.run(_case("quad-sphere-texel", {"map": "_M", "gray": True}), shifted)
    assert got["agreement"] < 0.8, got


def test_the_data_range_scales_the_frame_not_the_verdict() -> None:
    case = _case("quad-sphere-texel", {"map": "_R", "gray": True}, data_range=4.0)
    assert oracles.run(case, _ideal_texel("_R", True, data_range=4.0))["agreement"] == 1.0
    wrong_range = _case("quad-sphere-texel", {"map": "_R", "gray": True}, data_range=1.0)
    assert oracles.run(wrong_range, _ideal_texel("_R", True, data_range=4.0))["agreement"] < 0.5


# ---- the normal check -----------------------------------------------------------------------------------------------


def test_a_frame_with_the_authored_normals_passes_and_matches_nowhere_flipped() -> None:
    got = oracles.run(_case("quad-sphere-normal", {}), _ideal_normal())
    for channel in ("green", "red"):
        assert got[f"{channel}_pixels"] >= 50, got
        assert got[f"{channel}_authored"] >= 0.99 and got[f"{channel}_flipped"] <= 0.01, (channel, got)


@pytest.mark.parametrize("channel", ["green", "red", "both"])
def test_the_flipped_expectation_control_fails(channel: str) -> None:
    got = oracles.run(_case("quad-sphere-normal", {"flip_expectation": channel}, expect="fail"), _ideal_normal())
    chans = ("green", "red") if channel == "both" else (channel,)
    for c in chans:
        assert got[f"{c}_authored"] <= 0.01 and got[f"{c}_flipped"] >= 0.99, (c, got)
    if channel != "both":
        other = "red" if channel == "green" else "green"
        assert got[f"{other}_authored"] >= 0.99, "only the named channel's expectation is wrong"


def test_a_frame_with_one_normal_channel_flipped_is_caught() -> None:
    """A host that decodes the green channel the other way: the captured normals flip with the texel's green lean."""
    got = oracles.run(_case("quad-sphere-normal", {}), _ideal_normal(flip_green=True))
    assert got["green_authored"] < 0.5 and got["green_flipped"] > 0.5 and got["red_authored"] >= 0.99, got


# ---- what the oracle refuses -----------------------------------------------------------------------------------------


def test_a_capture_it_cannot_read_is_refused_with_the_reason() -> None:
    ideal = _ideal_texel("_R", True)
    case = _case("quad-sphere-texel", {"map": "_R"})
    ball = CaptureRequest.from_dict({**REQUEST.to_dict(), "mesh": "shader-ball"})
    with pytest.raises(OracleError, match="need mesh 'quad-sphere', the capture is of 'shader-ball'"):
        oracles.run(case, _capture(ideal.scene, ideal.coverage, ball))
    with pytest.raises(OracleError, match="level"):
        l1 = Manifest(host="unit", level="L1", request_hash=REQUEST.content_hash())
        oracles.run(case, CaptureSet(None, REQUEST, l1, None, np.zeros((SIZE, SIZE, 3), np.uint8), None))  # type: ignore[arg-type]
    with pytest.raises(OracleError, match="no covered, non-grazing pixel lies on the sphere"):
        oracles.run(case, _capture(ideal.scene, np.zeros((SIZE, SIZE), dtype=bool)))


def test_a_camera_that_does_not_see_the_sphere_is_refused() -> None:
    away = CaptureRequest.from_dict(
        {
            **REQUEST.to_dict(),
            "camera": {**REQUEST.to_dict()["camera"], "eye": [0.0, 0.0, 4.0], "target": [0.0, 0.0, 9.0]},
        }
    )
    with pytest.raises(OracleError, match="no covered, non-grazing pixel"):
        oracles.run(
            _case("quad-sphere-texel", {"map": "_R"}),
            _capture(np.zeros((SIZE, SIZE, 3)), np.ones((SIZE, SIZE), bool), away),
        )


def test_the_registry_and_the_functions_agree_and_every_check_needs_its_range() -> None:
    assert set(oracles.CHECKS) == set(oracles.FUNCTIONS) == {"quad-sphere-texel", "quad-sphere-normal"}
    assert all(spec.needs_data_range and spec.kinds == ("oracle",) for spec in oracles.CHECKS.values())
    with pytest.raises(KeyError):
        oracles.run(_case("nope", {}), _ideal_texel("_R", True))
