"""
HogShade: tests for the IBL cook (Docs/plans/e1-ibl-cook.md, tasks 3 to 9). Small sizes; seconds, not minutes.
Package: tests/ibl/test_cook
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from hogshade.ibl import dds
from hogshade.ibl.cook import cook_environment, furnace
from hogshade.ibl.cubemap import (
    FACE_NAMES,
    direction_to_equirect,
    equirect_pyramid,
    equirect_texel_directions,
    equirect_texel_solid_angle,
    equirect_to_cube,
    face_directions,
)
from hogshade.ibl.imageio import read_exr_rgb, write_exr_rgb
from hogshade.ibl.irradiance import irradiance_cube, sh9_irradiance, sh9_project
from hogshade.ibl.prefilter import brdf_lut, prefilter_specular


# ---------------------------------------------------------------- task 3: DDS
def test_dds_cube_round_trip(tmp_path: Path) -> None:
    mips = [np.random.default_rng(m).random((6, 8 >> m, 8 >> m, 3)).astype(np.float32) for m in range(4)]
    p = tmp_path / "cube.dds"
    dds.write_cube_rgba16f(p, mips)
    assert p.stat().st_size == 148 + 6 * sum((8 >> m) ** 2 * 8 for m in range(4))
    back = dds.read_cube_rgba16f(p)
    assert len(back) == 4
    for m, level in enumerate(mips):
        np.testing.assert_allclose(back[m][..., :3], level.astype(np.float16).astype(np.float32))
        np.testing.assert_array_equal(back[m][..., 3], 1.0)


def test_dds_2d_header(tmp_path: Path) -> None:
    p = tmp_path / "lut.dds"
    dds.write_2d_rgba16f(p, np.zeros((4, 8, 3), dtype=np.float32))
    raw = p.read_bytes()
    assert raw[:4] == b"DDS " and len(raw) == 148 + 4 * 8 * 8
    assert int.from_bytes(raw[12:16], "little") == 4 and int.from_bytes(raw[16:20], "little") == 8  # height, width
    assert raw[84:88] == b"DX10" and int.from_bytes(raw[128:132], "little") == dds.DXGI_FORMAT_R16G16B16A16_FLOAT


# ---------------------------------------------------------------- task 4: face convention, asymmetric markers
def _marker_equirect(width: int = 256, height: int = 128) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """A black equirect with a distinct colour splat at each axis and one off-centre marker on the +X face."""
    img = np.zeros((height, width, 3), dtype=np.float32)
    markers = {
        "+X": (np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])),
        "-X": (np.array([-1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])),
        "+Y": (np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])),
        "-Y": (np.array([0.0, -1.0, 0.0]), np.array([1.0, 1.0, 0.0])),
        "+Z": (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 1.0])),
        "-Z": (np.array([0.0, 0.0, -1.0]), np.array([0.0, 1.0, 1.0])),
        # +X face, +u (towards -Z) and -v (towards +Y): direction (1, +0.5, -0.5) normalised
        "+X off": (np.array([1.0, 0.5, -0.5]) / np.sqrt(1.5), np.array([0.5, 0.5, 0.5])),
    }
    dirs = equirect_texel_directions(width, height)
    colours: dict[str, np.ndarray] = {}
    for name, (d, c) in markers.items():
        mask = (dirs @ d) > np.cos(np.radians(4.0))
        img[mask] = c
        colours[name] = c
    return img, colours


def test_face_markers_land_on_expected_faces_and_quadrants() -> None:
    img, colours = _marker_equirect()
    cube = equirect_to_cube(img, 32)
    for face, name in enumerate(FACE_NAMES):
        centre = cube[face, 16, 16]
        np.testing.assert_allclose(centre, colours[name], atol=0.05, err_msg=f"face {face} ({name}) centre")
    # off-centre marker: on the +X face, +u is column index > centre, -v is row index < centre
    off = np.all(np.abs(cube[0] - colours["+X off"]) < 0.05, axis=-1)
    ys, xs = np.nonzero(off)
    assert off.any(), "off-centre marker missing from +X face"
    assert xs.mean() > 16 and ys.mean() < 16, (
        f"marker at cols {xs.mean():.1f} rows {ys.mean():.1f}; face is rotated or mirrored"
    )
    # and nowhere else
    for face in range(1, 6):
        assert not np.all(np.abs(cube[face] - colours["+X off"]) < 0.05, axis=-1).any()


def test_equirect_mapping_anchors() -> None:
    s, t = direction_to_equirect(np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0], [-1.0, 0, 0], [0, 0, 1.0]]))
    np.testing.assert_allclose(s[:4], [0.75, 0.5, 0.0, 0.25], atol=1e-9)
    np.testing.assert_allclose(t[:3], [0.5, 0.5, 0.0], atol=1e-9)
    assert s[4] in (0.0, 1.0) or abs(s[4]) < 1e-9  # +Z is the seam
    # inverse mapping agrees
    d = equirect_texel_directions(64, 32)
    s2, t2 = direction_to_equirect(d)
    np.testing.assert_allclose(s2, (np.arange(64) + 0.5)[None, :] / 64 * np.ones((32, 1)), atol=1e-9)
    np.testing.assert_allclose(t2, (np.arange(32) + 0.5)[:, None] / 32 * np.ones((1, 64)), atol=1e-9)


def test_solid_angle_sums_to_sphere() -> None:
    assert abs(equirect_texel_solid_angle(256, 128).sum() / (4 * np.pi) - 1.0) < 1e-4
    d = face_directions(16)
    np.testing.assert_allclose(np.linalg.norm(d, axis=-1), 1.0)


# ---------------------------------------------------------------- task 5 and 8: prefilter, furnace
def test_prefilter_mip0_is_resample_and_last_mip_is_blur() -> None:
    # 64x32 has the texel solid angle of a 16 cube, so mip 0 resamples pyramid level 0, the source itself
    img, _ = _marker_equirect(64, 32)
    mips = prefilter_specular(equirect_pyramid(img), base=16, samples=64)
    assert len(mips) == 5
    np.testing.assert_allclose(mips[0], equirect_to_cube(img, 16), atol=1e-6)
    # Prefiltering is an average with weights summing to one, so variance cannot grow from mip to mip.
    d = equirect_texel_directions(64, 32)
    smooth = (0.5 + 0.5 * d[..., 1:2] + 0.3 * np.sign(np.sin(8.0 * np.pi * d[..., 0:1]))).astype(np.float32)
    smooth = np.repeat(smooth, 3, axis=-1)
    stds = [float(m.std()) for m in prefilter_specular(equirect_pyramid(smooth), base=16, samples=64)]
    for a, b in itertools.pairwise(stds):
        assert b <= a * 1.05, stds
    assert stds[-1] < stds[0] * 0.9, stds


def test_furnace_white_stays_white() -> None:
    report = furnace(base=16, samples=128)
    assert report["passed"], report


# ---------------------------------------------------------------- task 6: irradiance and SH9
def test_sh9_matches_irradiance_cube_on_a_smooth_environment() -> None:
    d = equirect_texel_directions(128, 64)
    img = (0.5 + 0.5 * d[..., 1:2] + 0.25 * d[..., 0:1]).astype(np.float32) * np.array(
        [1.0, 0.8, 0.6], dtype=np.float32
    )
    cube = irradiance_cube(img, 8)
    coeffs = sh9_project(img)
    recon = sh9_irradiance(coeffs, face_directions(8)).astype(np.float32)
    rms = np.sqrt(np.mean((recon - cube) ** 2)) / cube.mean()
    assert rms < 0.02, rms


# ---------------------------------------------------------------- task 7: BRDF LUT
def test_brdf_lut_corners() -> None:
    lut = brdf_lut(size=16, samples=512)
    scale, bias = lut[0, -1]  # lowest roughness, highest NdotV
    assert abs(scale - 1.0) < 0.01 and bias < 0.01
    assert np.all(lut >= 0) and np.all(lut[..., 0] + lut[..., 1] <= 1.02)
    assert lut[-1, -1, 0] < lut[0, -1, 0]  # rough surfaces lose energy at normal incidence


# ---------------------------------------------------------------- task 9: manifest determinism
def test_cook_is_deterministic(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.mkdir()
    img, _ = _marker_equirect(256, 128)
    write_exr_rgb(env / "source_4k.exr", img)  # name is what the cook expects; size is not enforced
    m1 = cook_environment(env, base=8, samples=32, irradiance_size=4)
    h1 = {n: (env / "cooked" / n).read_bytes() for n in m1["outputs"]}
    prov1 = (env / "cooked" / "provenance.json").read_text()
    m2 = cook_environment(env, base=8, samples=32, irradiance_size=4)
    h2 = {n: (env / "cooked" / n).read_bytes() for n in m2["outputs"]}
    assert m1 == m2 and h1 == h2
    assert json.loads(prov1)["machine"] == json.loads((env / "cooked" / "provenance.json").read_text())["machine"]
    assert (env / "preview.png").read_bytes()[:4] == b"\x89PNG"
    back = dds.read_cube_rgba16f(env / "cooked" / "specular.dds")
    assert len(back) == 4 and back[0].shape == (6, 8, 8, 4)
    assert read_exr_rgb(env / "source_4k.exr").shape == (128, 256, 3)


@pytest.mark.parametrize("size", [1, 2, 4])
def test_dds_rejects_bad_mip_chain(tmp_path: Path, size: int) -> None:
    with pytest.raises(ValueError):
        dds.write_cube_rgba16f(tmp_path / "bad.dds", [np.zeros((6, 8, 8, 3)), np.zeros((6, size + 8, size + 8, 3))])
