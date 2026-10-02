"""
HogShade: the wgpu host renders the shader ball through both paths and the pictures agree (phase 2 plan, tasks 13 and 14).
Package: tests/host/test_wgpu_host

Skips without a GPU adapter. The frames are small (96 px) so the test runs in well under a second.
"""

from __future__ import annotations

import numpy as np
import pytest

from hogshade import wgpu_host


def test_frame_layout_matches_the_wgsl_struct() -> None:
    assert wgpu_host.FRAME_DTYPE.itemsize == wgpu_host.FRAME_BYTES
    assert len(wgpu_host.Scene(width=32, height=32).frame_bytes(9)) == wgpu_host.FRAME_BYTES
    common = (wgpu_host.HOSTS_WGPU / "common.wgsl").read_text(encoding="utf-8")
    for name in wgpu_host.FRAME_DTYPE.names:
        assert f"    {name}:" in common, name
    # the same fields in the same order: a field inserted on one side only would shift every offset after it
    struct = common.split("struct host_Frame {", 1)[1].split("}", 1)[0]
    wgsl_order = [line.split(":", 1)[0].strip() for line in struct.strip().splitlines() if ":" in line]
    assert wgsl_order == list(wgpu_host.FRAME_DTYPE.names)


V1_LOBES = {
    "model": "legacy-v1",
    "rough_is_gloss": True,
    "specular_tint": 0.25,
    "subsurface": 0.1,
    "anisotropic": 0.2,
    "sheen": 0.3,
    "sheen_tint": 0.4,
    "clearcoat": 0.5,
    "clearcoat_gloss": 0.6,
}


def _frame(scene: wgpu_host.Scene):
    return np.frombuffer(scene.frame_bytes(9), dtype=wgpu_host.FRAME_DTYPE)[0]


def test_frame_packs_the_model_and_the_disney_parameters() -> None:
    frame = _frame(wgpu_host.Scene(width=32, height=32, material=wgpu_host.MaterialBinding(**V1_LOBES)))
    assert wgpu_host.MODELS["legacy-v1"] == 1  # HOGSHADE_MODEL_LEGACY_V1 in the core
    np.testing.assert_array_equal(frame["model"], (1.0, 1.0, 0.0, 0.0))
    np.testing.assert_allclose(frame["params_a"], (0.1, 0.25, 0.2, 0.3), rtol=1e-6)
    np.testing.assert_allclose(frame["params_b"], (0.4, 0.5, 0.6, 0.0), rtol=1e-6)
    assert frame["material"][2] == 0.0, "v1's specular tint lives in params_a[1]; material[2] is v2's (S3)"
    default = _frame(wgpu_host.Scene(width=32, height=32))
    np.testing.assert_array_equal(default["model"], (float(wgpu_host.MODELS["legacy-v2"]), 0.0, 0.0, 0.0))
    np.testing.assert_array_equal(default["params_a"], 0.0)
    np.testing.assert_array_equal(default["params_b"], 0.0)
    # the defaults are the legacy v2 schema's (S3), not the host's old hand-set values
    np.testing.assert_allclose(default["base_color"], (0.6, 0.6, 0.6, 0.5), rtol=1e-6)
    np.testing.assert_allclose(default["material"], (0.0, 1.0, 0.0, 1.45), rtol=1e-6)


def test_a_bound_document_and_the_hand_set_scene_pack_the_same_frame() -> None:
    from hogshade.material import bind, from_data, load, resolve

    doc = load(wgpu_host.ROOT / "content" / "materials" / "legacy-v2" / "default.material.json")
    bound = wgpu_host.Scene(width=32, height=32, material=bind(resolve(doc), "wgpu"))
    assert bound.frame_bytes(9) == wgpu_host.Scene(width=32, height=32).frame_bytes(9)
    values = {k: {"factor": v} for k, v in V1_LOBES.items() if k != "model"}
    v1 = resolve(from_data({"material_type": "hogshade-legacy-v1", "material_type_version": 1, "values": values}))
    bound_v1 = wgpu_host.Scene(width=32, height=32, material=bind(v1, "wgpu"))
    hand_v1 = wgpu_host.Scene(width=32, height=32, material=wgpu_host.MaterialBinding(**V1_LOBES))
    assert bound_v1.frame_bytes(9) == hand_v1.frame_bytes(9)
    assert bound_v1.model == "legacy-v1"


ASSETS_HYDRATED = all(
    wgpu_host.lfs_hydrated(p)
    for p in (
        wgpu_host.SHADER_BALL,
        wgpu_host.IBL_ROOT / "brdf_lut.dds",
        wgpu_host.IBL_ROOT / "studio_small_09" / "cooked" / "specular.dds",
    )
)
NO_ASSETS = "LFS payloads not hydrated (CI checks out with lfs: false)"
needs_assets = pytest.mark.skipif(not ASSETS_HYDRATED, reason=NO_ASSETS)


@needs_assets
def test_shader_ball_loads_and_normalises() -> None:
    mesh = wgpu_host.load_shader_ball()
    assert len(mesh.indices) % 3 == 0 and len(mesh.indices) > 50_000
    extent = mesh.vertices[:, :3].max(0) - mesh.vertices[:, :3].min(0)
    assert abs(extent.max() - 2.0) < 1e-5
    np.testing.assert_allclose(np.linalg.norm(mesh.vertices[:, 3:6], axis=-1), 1.0, atol=1e-5)


@pytest.fixture(scope="module")
def renderer():
    if not ASSETS_HYDRATED:
        pytest.skip(NO_ASSETS)
    try:
        import wgpu  # noqa: F401
    except ImportError:
        pytest.skip("wgpu not installed (uv sync --extra gpu)")
    try:
        _, device = wgpu_host.request_device()
    except Exception as e:  # noqa: BLE001 - any adapter failure is a skip, not an error
        pytest.skip(f"no GPU adapter: {e!r}")
    return wgpu_host.Renderer(device, wgpu_host.load_shader_ball())


def test_forward_and_deferred_agree_on_a_lit_ball(renderer) -> None:
    scene = wgpu_host.Scene(width=96, height=96)
    frames = renderer.render(scene)
    assert frames.covered.sum() > 96 * 96 * 0.15, "the ball should fill a good part of the frame"
    lit = frames.forward[frames.covered]
    assert np.isfinite(frames.forward).all() and np.isfinite(frames.deferred).all()
    assert lit.mean() > 0.05, lit.mean()
    mean_diff, max_diff = frames.difference()
    # the deferred picture differs by the G-buffer's 8-bit sRGB albedo, 8-bit AO and fp16 normal, and by
    # the depth-reconstructed position and view vector; silhouette pixels carry the largest error
    assert mean_diff < 0.02, mean_diff
    assert max_diff < 1.0, max_diff


def test_legacy_v1_renders_and_differs_from_v2(renderer) -> None:
    v2 = renderer.render(wgpu_host.Scene(width=96, height=96)).forward
    v1_material = wgpu_host.MaterialBinding(model="legacy-v1")
    v1 = renderer.render(wgpu_host.Scene(width=96, height=96, material=v1_material)).forward
    assert np.isfinite(v1).all() and v1.max() > 0.05
    assert np.abs(v1 - v2).max() > 0.01, "the selector reached the shader: v1 is not v2"
    sheen_material = wgpu_host.MaterialBinding(model="legacy-v1", sheen=1.0)
    sheen = renderer.render(wgpu_host.Scene(width=96, height=96, material=sheen_material)).forward
    assert np.abs(sheen - v1).max() > 1e-3, "params_a reached the v1 lobes"


def test_documents_render_through_the_binding(renderer) -> None:
    from hogshade.material import bind, from_data, load, resolve

    doc = load(wgpu_host.ROOT / "content" / "materials" / "legacy-v2" / "default.material.json")
    material = bind(resolve(doc), "wgpu")
    bound = renderer.render(wgpu_host.Scene(width=96, height=96, material=material)).forward
    plain = renderer.render(wgpu_host.Scene(width=96, height=96)).forward
    np.testing.assert_array_equal(bound, plain)
    values = {"sheen": {"factor": 1.0}}
    v1 = resolve(from_data({"material_type": "hogshade-legacy-v1", "material_type_version": 1, "values": values}))
    sheen = renderer.render(wgpu_host.Scene(width=96, height=96, material=bind(v1, "wgpu"))).forward
    no_sheen = renderer.render(
        wgpu_host.Scene(width=96, height=96, material=wgpu_host.MaterialBinding(model="legacy-v1"))
    ).forward
    assert np.abs(sheen - no_sheen).max() > 1e-3, "the document's lobe reached the shader through the binding"


def test_specular_view_is_nonzero_and_below_the_composite(renderer) -> None:
    full = renderer.render(wgpu_host.Scene(width=96, height=96, debug_mode=0)).forward
    spec = renderer.render(wgpu_host.Scene(width=96, height=96, debug_mode=18)).forward
    assert spec.max() > 0.05, spec.max()
    assert spec.mean() < full.mean()
