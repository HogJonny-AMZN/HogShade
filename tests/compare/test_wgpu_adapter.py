"""
HogShade: the wgpu adapter: what it refuses by name, how a request becomes a scene, what it hashes, and (GPU) a capture.
Package: tests/compare/test_wgpu_adapter

The refusals, the mapping and the hashes are pure and run anywhere; the capture needs a GPU adapter and the hydrated
IBL (and the BC feature for the cooked synthetic set) and is skipped without them, which CI does.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from hogshade import wgpu_host
from hogshade.compare import captureset
from hogshade.compare.adapters import wgpu as adapter
from hogshade.compare.adapters.wgpu import UnsupportedRequest
from hogshade.compare.request import CaptureRequest

BASE = {
    "id": "adapter-test",
    "mesh": "quad-sphere",
    "camera": {
        "eye": [0.0, 0.5, 4.0],
        "target": [0.0, 0.0, 0.0],
        "up": [0.0, 1.0, 0.0],
        "fov_y_deg": 32.0,
        "near": wgpu_host.NEAR_PLANE,
        "far": wgpu_host.FAR_PLANE,
    },
    "rig": {"environment": "studio_small_09", "exposure_ev": 1.0},
    "size": [256, 256],
    "debug_mode": 8,
}


def _request(**changes) -> CaptureRequest:
    data = copy.deepcopy(BASE)
    for dotted, value in changes.items():
        node = data
        *head, last = dotted.split("__")
        for key in head:
            node = node[key]
        node[last] = value
    return CaptureRequest.from_dict(data)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"camera__near": 0.05}, "camera.near/far: the wgpu host renders with near 0.1 and far 50.0"),
        ({"camera__far": 100.0}, "camera.near/far"),
        ({"rig__rotation_deg": 90.0}, "rig.rotation_deg: the wgpu host has no environment rotation"),
        ({"view": "agx"}, "view: the wgpu host supports only 'preview'"),
        ({"view": "aces"}, "view: the wgpu host supports only 'preview'"),
        (
            {
                "material": "content/materials/standard/rough/brick_wall_001.material.json",
                "textures": "content/textures/synthetic",
            },
            "material and textures: name a document or a texture set, not both",
        ),
    ],
)
def test_what_the_host_cannot_honour_is_refused_by_name(changes: dict, message: str) -> None:
    with pytest.raises(UnsupportedRequest, match=message):
        adapter.check_supported(_request(**changes))
    with pytest.raises(UnsupportedRequest):
        adapter.scene_for(_request(**changes))  # building the scene checks first, so nothing near is ever produced


def test_a_supported_request_passes_the_check() -> None:
    adapter.check_supported(_request())
    adapter.check_supported(_request(rig__rotation_deg=0))


def test_a_request_becomes_the_scene_it_describes() -> None:
    scene = adapter.scene_for(_request(rig__exposure_ev=2.0))
    assert (scene.width, scene.height, scene.fov_y_deg, scene.debug_mode) == (256, 256, 32.0, 8)
    assert scene.camera == ((0.0, 0.5, 4.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert scene.environment == "studio_small_09" and scene.env_exposure == 4.0  # 2 EV is two stops: x4
    assert scene.light_intensity == 0.0, "a request with no light is lit by the environment alone"
    np.testing.assert_array_equal(scene.view_proj()[1], [0.0, 0.5, 4.0])


def test_a_request_with_a_light_gets_its_direction_intensity_and_colour() -> None:
    lit = _request(rig__light={"direction": [0.2, 0.9, 0.1], "intensity": 2.5, "color": [1.0, 0.9, 0.8]})
    scene = adapter.scene_for(lit)
    assert (scene.light_dir, scene.light_intensity, scene.light_color) == ((0.2, 0.9, 0.1), 2.5, (1.0, 0.9, 0.8))


def test_the_scene_and_the_orbit_agree_when_the_request_is_the_orbit_s_camera() -> None:
    eye = tuple(wgpu_host.orbit_eye(32.0, 18.0, 4.0))
    request = _request(camera__eye=list(eye), camera__target=[0.0, 0.05, 0.0])
    got = adapter.scene_for(request).view_proj()[0]
    want = wgpu_host.Scene(width=256, height=256, yaw_deg=32.0, pitch_deg=18.0, distance=4.0).view_proj()[0]
    np.testing.assert_allclose(got, want, atol=1e-12)


def _fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    ibl = tmp_path / "ibl"
    (ibl / "studio_small_09" / "cooked").mkdir(parents=True)
    for name, text in (
        (ibl / "studio_small_09" / "cooked" / "specular.dds", "spec v1"),
        (ibl / "studio_small_09" / "cooked" / "irradiance.dds", "irr v1"),
        (ibl / "brdf_lut.dds", "lut v1"),
    ):
        name.write_text(text, encoding="utf-8")
    (root / "content" / "materials").mkdir(parents=True)
    (root / "content" / "materials" / "a.material.json").write_text('{"doc": 1}', encoding="utf-8")
    (root / "content" / "textures" / "set" / "cooked").mkdir(parents=True)
    (root / "content" / "textures" / "set" / "T_A.png").write_bytes(b"png a")
    (root / "content" / "textures" / "set" / "cooked" / "T_A.dds").write_bytes(b"dds a")
    return root, ibl


def test_replacing_an_environment_file_in_place_changes_the_manifest_hash_but_not_the_request_hash(
    tmp_path: Path,
) -> None:
    root, ibl = _fake_repo(tmp_path)
    request = _request()
    mesh = wgpu_host.quad_sphere(4)
    before = adapter.input_hashes(request, mesh, root, ibl)
    (ibl / "studio_small_09" / "cooked" / "specular.dds").write_text("spec v2", encoding="utf-8")
    after = adapter.input_hashes(request, mesh, root, ibl)
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"environment:studio_small_09/cooked/specular.dds"}
    assert before["request"] == after["request"] == request.content_hash()
    (ibl / "brdf_lut.dds").write_text("lut v2", encoding="utf-8")
    assert (
        adapter.input_hashes(request, mesh, root, ibl)["environment:brdf_lut.dds"] != before["environment:brdf_lut.dds"]
    )


def test_the_mesh_the_document_and_the_texture_set_are_hashed_by_content(tmp_path: Path) -> None:
    root, ibl = _fake_repo(tmp_path)
    request = _request(material="content/materials/a.material.json")
    mesh = wgpu_host.quad_sphere(4)
    base = adapter.input_hashes(request, mesh, root, ibl)
    assert set(base) == {
        "request",
        "mesh",
        "material",
        "environment:studio_small_09/cooked/specular.dds",
        "environment:studio_small_09/cooked/irradiance.dds",
        "environment:brdf_lut.dds",
    }
    (root / "content" / "materials" / "a.material.json").write_text('{"doc": 2}', encoding="utf-8")
    assert adapter.input_hashes(request, mesh, root, ibl)["material"] != base["material"]
    assert adapter.input_hashes(request, wgpu_host.quad_sphere(6), root, ibl)["mesh"] != base["mesh"]
    assert (
        adapter.input_hashes(request, mesh, root, ibl)["mesh"] == adapter.input_hashes(request, mesh, root, ibl)["mesh"]
    )

    textured = _request(textures="content/textures/set")
    first = adapter.input_hashes(textured, mesh, root, ibl)["textures"]
    (root / "content" / "textures" / "set" / "cooked" / "T_A.dds").write_bytes(b"dds b")  # a nested file changes it
    assert adapter.input_hashes(textured, mesh, root, ibl)["textures"] != first
    with pytest.raises(FileNotFoundError):
        adapter.input_hashes(_request(material="content/materials/missing.material.json"), mesh, root, ibl)


# ---- the GPU path --------------------------------------------------------------------------------------------------

SYNTHETIC = wgpu_host.ROOT / "content" / "textures" / "synthetic"


@pytest.fixture(scope="module")
def wgpu_adapter():
    if not all(
        wgpu_host.lfs_hydrated(p)
        for p in (
            wgpu_host.IBL_ROOT / "studio_small_09" / "cooked" / "specular.dds",
            wgpu_host.IBL_ROOT / "studio_small_09" / "cooked" / "irradiance.dds",
            wgpu_host.IBL_ROOT / "brdf_lut.dds",
            SYNTHETIC / "cooked" / "T_synthetic_ORM.dds",
        )
    ):
        pytest.skip("LFS payloads not hydrated (CI checks out with lfs: false)")
    try:
        import wgpu  # noqa: F401
    except ImportError:
        pytest.skip("wgpu not installed (uv sync --extra gpu)")
    try:
        gpu_adapter, device = wgpu_host.request_device()
    except Exception as e:  # noqa: BLE001 - any adapter failure is a skip, not an error
        pytest.skip(f"no GPU adapter: {e!r}")
    from hogshade.wgpu_textures import BC_FEATURE

    if BC_FEATURE not in set(device.features):
        pytest.skip(f"the device has no {BC_FEATURE}")
    return adapter.WgpuAdapter(device, dict(gpu_adapter.info))


def test_a_capture_writes_a_readable_l2p_set_with_every_input_hashed(wgpu_adapter, tmp_path: Path) -> None:
    request = _request(textures="content/textures/synthetic")
    got = wgpu_adapter.capture(request, tmp_path / "set")
    assert got.level == "L2p" and got.manifest.host == "wgpu" and got.manifest.colour_space == "unspecified"
    assert got.request == request and got.manifest.request_hash == request.content_hash()
    assert got.scene.shape == (256, 256, 3) and got.scene.dtype == np.float32 and got.display.shape == (256, 256, 3)
    assert 0.15 < got.coverage.mean() < 0.6, "the sphere fills a sensible part of the picture"
    assert set(got.manifest.inputs) >= {
        "request",
        "mesh",
        "textures",
        "environment:studio_small_09/cooked/specular.dds",
        "environment:brdf_lut.dds",
    }
    assert "wgpu-py" in got.manifest.versions and got.manifest.wall_seconds > 0
    assert any("L2p" in n for n in got.manifest.notes)


def test_two_captures_of_one_request_have_the_same_pixels(wgpu_adapter, tmp_path: Path) -> None:
    request = _request(textures="content/textures/synthetic")
    one = wgpu_adapter.capture(request, tmp_path / "one")
    two = wgpu_adapter.capture(request, tmp_path / "two")
    assert captureset.pixel_hash(one.path) == captureset.pixel_hash(two.path)


def test_a_refused_request_renders_and_writes_nothing(wgpu_adapter, tmp_path: Path) -> None:
    with pytest.raises(UnsupportedRequest):
        wgpu_adapter.capture(_request(rig__rotation_deg=45.0), tmp_path / "never")
    assert not (tmp_path / "never").exists()


def test_an_exposure_of_one_stop_doubles_the_environment_lit_pixels(wgpu_adapter, tmp_path: Path) -> None:
    """A debug-free view lit by the environment alone scales with env_exposure: the rig reaches the shader."""
    dim = wgpu_adapter.capture(_request(debug_mode=0, rig__exposure_ev=0.0), tmp_path / "dim")
    bright = wgpu_adapter.capture(_request(debug_mode=0, rig__exposure_ev=1.0), tmp_path / "bright")
    covered = dim.coverage & bright.coverage
    ratio = bright.scene[covered].sum() / dim.scene[covered].sum()
    assert 1.5 < ratio < 2.5, ratio
