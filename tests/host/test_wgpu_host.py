"""
HogShade: the wgpu host renders the shader ball through both paths and the pictures agree (phase 2 plan,
tasks 13 and 14).
Package: tests/host/test_wgpu_host

Skips without a GPU adapter. The frames are small (96 px) so the test runs in well under a second.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hogshade import wgpu_host


def test_read_obj_names_the_file_and_line_of_a_malformed_record(tmp_path) -> None:
    bad = tmp_path / "bad.obj"
    bad.write_text("v 0 0 0\nv 1 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.obj:2: malformed OBJ record 'v 1 0': 3 numbers expected, 2 given"):
        wgpu_host.read_obj(bad)
    good = tmp_path / "good.obj"
    good.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n", encoding="utf-8")
    mesh = wgpu_host.load_obj(good)
    face, vertex, rows = wgpu_host.obj_corners(good)
    assert mesh.vertices.shape == (3, 12) and mesh.tangent_basis == "mikktspace"
    assert face.tolist() == [0, 0, 0] and vertex.tolist() == [0, 1, 2] and rows.tolist() == [0, 1, 2]


def test_load_obj_keeps_a_mirrored_seam_apart(tmp_path) -> None:
    """An OBJ whose two faces share a seam with mirrored UVs loads the seam vertices twice, one per handedness."""
    obj = tmp_path / "seam.obj"
    obj.write_text(
        "v -1 0 0\nv 0 0 0\nv 1 0 0\nv -1 1 0\nv 0 1 0\nv 1 1 0\n"
        "vt 1 0\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nvt 1 1\nvn 0 0 1\n"
        "f 2/2/1 3/3/1 6/6/1 5/5/1\nf 1/1/1 2/2/1 5/5/1 4/4/1\n",
        encoding="utf-8",
    )
    mesh = wgpu_host.load_obj(obj)
    face, vertex, rows = wgpu_host.obj_corners(obj)
    assert mesh.vertices.shape[0] == 8 and len(set(rows.tolist())) == 8
    assert face.tolist() == [0] * 4 + [1] * 4 and vertex.tolist() == [1, 2, 5, 4, 0, 1, 4, 3]
    signs = mesh.vertices[rows, 11]
    assert signs[:4].tolist() == [1.0] * 4 and signs[4:].tolist() == [-1.0] * 4, "each face's corners carry its sign"


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


def test_a_standard_document_renders_through_the_reverse_table(renderer) -> None:
    """S4a: gold converted to legacy v2 and bound differs from the dielectric parent; both render finite."""
    from hogshade.material import bind, convert, load, resolve

    library = wgpu_host.ROOT / "content" / "materials" / "standard"

    def frame(rel: str):
        doc = load(library / rel, library)
        converted, _ = convert(resolve(doc, library), "hogshade-legacy-v2")
        return renderer.render(wgpu_host.Scene(width=96, height=96, material=bind(resolve(converted), "wgpu"))).forward

    gold, dielectric = frame("metal/gold.material.json"), frame("dielectric/base.material.json")
    assert np.isfinite(gold).all() and np.isfinite(dielectric).all()
    assert np.abs(gold - dielectric).max() > 0.05, "the standard document reached the shader through the table"
    assert gold[..., 0].mean() > gold[..., 2].mean(), "gold is warmer than it is blue"


def test_specular_view_is_nonzero_and_below_the_composite(renderer) -> None:
    full = renderer.render(wgpu_host.Scene(width=96, height=96, debug_mode=0)).forward
    spec = renderer.render(wgpu_host.Scene(width=96, height=96, debug_mode=18)).forward
    assert spec.max() > 0.05, spec.max()
    assert spec.mean() < full.mean()


# ----------------------------------------------------------------------------- T3b: the cooked sets on the device

LIBRARY = wgpu_host.ROOT / "content" / "materials" / "standard"
BRICK = LIBRARY / "rough" / "brick_wall_001.material.json"
METAL = LIBRARY / "metal" / "metal_plate.material.json"
GRID = wgpu_host.ROOT / "content" / "textures" / "grid"
COOKED_HYDRATED = all(
    wgpu_host.lfs_hydrated(p)
    for p in (
        BRICK.parent / "brick_wall_001" / "cooked" / "T_brick_wall_001_BC.dds",
        METAL.parent / "metal_plate" / "cooked" / "T_metal_plate_ORM.dds",
        GRID / "cooked" / "T_grid_C.dds",
    )
)
needs_cooked = pytest.mark.skipif(not COOKED_HYDRATED, reason="cooked DDS not hydrated (LFS)")


def _textured(path, only=None):
    """A standard document converted, bound for wgpu, and its runtime textures (restricted to ``only``)."""
    from hogshade.material import bind, convert, load, resolve, runtime_textures

    doc = load(path, LIBRARY)
    converted, _ = convert(resolve(doc, LIBRARY), "hogshade-legacy-v2")
    binding = bind(resolve(converted), "wgpu")
    runtime = runtime_textures(binding.textures, path.parent)
    if only is not None:
        runtime = {k: v for k, v in runtime.items() if k in only}
    return binding, runtime


def _grid(only=None):
    from hogshade.material import bind, convert, resolve, runtime_textures
    from hogshade.material.sets import document_for_set

    doc = document_for_set(GRID)
    converted, _ = convert(resolve(doc), "hogshade-legacy-v2")
    binding = bind(resolve(converted), "wgpu")
    runtime = runtime_textures(binding.textures, doc.root)
    if only is not None:
        runtime = {k: v for k, v in runtime.items() if k in only}
    return binding, runtime


def _render(renderer, binding, textures, **kw):
    return renderer.render(wgpu_host.Scene(width=96, height=96, material=binding, textures=textures, **kw))


@pytest.fixture(scope="module")
def textured_renderer(renderer):
    if not COOKED_HYDRATED:
        pytest.skip("cooked DDS not hydrated (LFS)")
    from hogshade.wgpu_textures import BC_FEATURE

    if BC_FEATURE not in set(renderer.device.features):
        pytest.skip(f"the device has no {BC_FEATURE}; the committed sets are block-compressed")
    return renderer


def test_a_textured_document_differs_from_its_constants_where_the_map_differs(textured_renderer) -> None:
    binding, runtime = _textured(BRICK)
    bare = _render(textured_renderer, binding, None)
    textured = _render(textured_renderer, binding, runtime)
    assert np.isfinite(textured.forward).all() and np.isfinite(textured.deferred).all()
    assert np.abs(textured.forward - bare.forward).max() > 0.05, "the maps reached the shader"
    # debug mode 1 is the base colour sample: flat for the constants, the brick pattern for the set
    bare_bc = _render(textured_renderer, binding, None, debug_mode=1)
    tex_bc = _render(textured_renderer, binding, runtime, debug_mode=1)
    assert bare_bc.forward[bare_bc.covered].std() < 1e-3
    assert tex_bc.forward[tex_bc.covered].std() > 0.02, "the base colour slot is sampled across the ball"
    # the unbound path is untouched: no textures, or an empty set, is the same picture bit for bit
    np.testing.assert_array_equal(_render(textured_renderer, binding, {}).forward, bare.forward)


def test_the_normal_map_tilts_the_shading(textured_renderer) -> None:
    binding, runtime = _textured(BRICK, only={"normal_map"})
    assert set(runtime) == {"normal_map"}
    flat = _render(textured_renderer, binding, None, debug_mode=11).forward  # the shading normal, world space
    bumped = _render(textured_renderer, binding, runtime, debug_mode=11)
    covered = bumped.covered
    tilt = np.abs(bumped.forward - flat)[covered]
    assert tilt.max() > 0.1 and (tilt.max(axis=1) > 0.02).mean() > 0.2, "the normal slot tilts the shading normal"
    lit_flat = _render(textured_renderer, binding, None).forward
    lit_bumped = _render(textured_renderer, binding, runtime).forward
    assert np.abs(lit_bumped - lit_flat).max() > 0.02, "the tilt reaches the lighting"


def test_orm_channels_land_on_their_parameters_and_roughness_alone_binds_nothing_else(textured_renderer) -> None:
    from hogshade.wgpu_textures import BITS

    binding, runtime = _textured(METAL)
    assert {"roughness", "metalness", "ambient_occlusion_map"} <= set(runtime)
    only_r = {k: v for k, v in runtime.items() if k == "roughness"}
    plan = wgpu_host.Scene(material=binding, textures=only_r).plan()
    assert plan.bound == BITS["roughness"] and set(plan.sources) == {"orm"}
    only_rm = {k: v for k, v in runtime.items() if k in ("roughness", "metalness")}
    only_rao = {k: v for k, v in runtime.items() if k in ("roughness", "ambient_occlusion_map")}

    def view(textures, mode):  # debug modes 7, 8, 9: metalness, roughness, AO as the shader holds them
        frames = _render(textured_renderer, binding, textures, debug_mode=mode)
        return frames.forward[frames.covered][:, 0]

    assert view(None, 8).std() < 1e-3 and view(only_r, 8).std() > 0.02, "green reached roughness"
    assert view(only_r, 7).std() < 1e-3, "roughness alone leaves metalness at its factor (the shell's rule)"
    assert view(only_rm, 7).std() > 0.02, "blue reached metalness when its own parameter is bound"
    ao = view(only_rao, 9)  # the plate's AO is smooth and mostly open: not flat 1.0 is the claim
    assert view(only_r, 9).std() < 1e-3 and (ao.std() > 0.005 or ao.mean() < 0.98), "red reached AO when bound"


def test_the_grid_tile_reads_its_cavity_and_leaves_emission_to_the_factor(textured_renderer) -> None:
    binding, runtime = _grid()
    assert "emission_color" in runtime and "cavity_map" in runtime
    plan = wgpu_host.Scene(material=binding, textures=runtime).plan()
    assert set(plan.sources) == {"base_color", "normal", "orm", "cavity"}, "emission and height are not slots"
    bare = _render(textured_renderer, binding, None, debug_mode=10)  # the cavity term
    cavity = _render(textured_renderer, binding, {"cavity_map": runtime["cavity_map"]}, debug_mode=10)
    carved = cavity.forward[cavity.covered]
    assert bare.forward[bare.covered].std() < 1e-3 and carved.std() > 0.005 and carved.mean() < 0.98


def test_two_documents_over_one_set_share_uploads_and_get_two_bind_groups(textured_renderer) -> None:
    binding, runtime = _textured(BRICK)
    subset = {k: v for k, v in runtime.items() if k in ("normal_map", "roughness")}
    keys = {wgpu_host.Scene(material=binding, textures=tx).plan().key for tx in (runtime, subset)}
    assert len(keys) == 2
    before = set(textured_renderer._material_groups)
    for textures in (runtime, subset, runtime):  # the first plan twice: its group is reused
        _render(textured_renderer, binding, textures)
    after = set(textured_renderer._material_groups)
    assert keys <= after and len(after) == len(before) + len(keys - before)
    resident = [Path(k).name for k in textured_renderer._texture_cache]
    assert resident.count("T_brick_wall_001_N.dds") == 1 and resident.count("T_brick_wall_001_ORM.dds") == 1


def test_the_deferred_path_agrees_on_a_textured_ball(textured_renderer) -> None:
    binding, runtime = _textured(BRICK)
    frames = _render(textured_renderer, binding, runtime)
    mean_diff, max_diff = frames.difference()
    assert mean_diff < 0.02, mean_diff
    assert max_diff < 1.0, max_diff


@needs_cooked
def test_a_block_compressed_set_without_the_feature_is_refused_by_name() -> None:
    from hogshade.wgpu_textures import TextureError, upload_dds

    class NoBC:
        features: frozenset[str] = frozenset()

        def create_texture(self, **kw):  # pragma: no cover - the refusal comes first
            raise AssertionError("no texture is created without the feature")

    with pytest.raises(TextureError, match="--no-compress"):
        upload_dds(NoBC(), BRICK.parent / "brick_wall_001" / "cooked" / "T_brick_wall_001_BC.dds")


# ----------------------------------------------------------------------------- T4 tier 1: the synthetic set on the host

SYNTHETIC = wgpu_host.ROOT / "content" / "textures" / "synthetic"
PROBE = 512  # the render's side, in screen pixels
MAP = 512  # the synthetic maps' side, in texels (``hogshade.testdata.synthetic.SIZE``)


@pytest.fixture(scope="module")
def synthetic_scene(renderer):
    """The synthetic set's document bound for wgpu with its runtime textures; skipped without the cooked set or BC."""
    from hogshade.material import bind, convert, resolve, runtime_textures
    from hogshade.material.sets import document_for_set
    from hogshade.wgpu_textures import BC_FEATURE

    orm = SYNTHETIC / "cooked" / "T_synthetic_ORM.dds"
    if not wgpu_host.lfs_hydrated(orm):
        pytest.skip("the synthetic set's cooked DDS are not hydrated (LFS)")
    if BC_FEATURE not in set(renderer.device.features):
        pytest.skip(f"the device has no {BC_FEATURE}")
    doc = document_for_set(SYNTHETIC)
    converted, _ = convert(resolve(doc), "hogshade-legacy-v2")
    binding = bind(resolve(converted), "wgpu")
    return binding, runtime_textures(binding.textures, doc.root)


def _probe(renderer, synthetic_scene, mode: int):
    """
    A render of the synthetic set in debug view ``mode`` and the mesh vertices that are *seen* in it: each vertex
    projected through the scene's camera, kept when its depth matches the depth buffer (so nothing hidden), it faces
    the camera, is away from the poles (``|normal.y| < 0.7``) and is off a UV tile seam; one per pixel. Returns
    ``(frames, vertex rows, pixel columns, pixel rows, uv)``. At such a pixel the texture coordinate is the
    vertex's, so the value the host drew can be compared with the map at that coordinate.
    """
    binding, textures = synthetic_scene
    scene = wgpu_host.Scene(width=PROBE, height=PROBE, material=binding, textures=textures, debug_mode=mode)
    frames = renderer.render(scene)
    assert frames.depth is not None and frames.depth.shape == frames.covered.shape, "the render carries its depth"
    verts = renderer.mesh.vertices
    pos = verts[:, wgpu_host.COL_POSITION].astype(np.float64)
    nrm, uv = verts[:, wgpu_host.COL_NORMAL], verts[:, wgpu_host.COL_UV]
    vp, eye = scene.view_proj()
    clip = np.concatenate([pos, np.ones((len(pos), 1))], axis=1) @ vp.T
    ndc = clip[:, :3] / clip[:, 3:4]
    col = np.floor((ndc[:, 0] * 0.5 + 0.5) * PROBE).astype(int)
    row = np.floor((1.0 - (ndc[:, 1] * 0.5 + 0.5)) * PROBE).astype(int)
    to_eye = eye - pos
    dist = np.linalg.norm(to_eye, axis=1)
    inside = (col >= 0) & (col < PROBE) & (row >= 0) & (row < PROBE)
    buffer = frames.depth[np.clip(row, 0, PROBE - 1), np.clip(col, 0, PROBE - 1)]
    seen = np.abs(wgpu_host.linear_depth(ndc[:, 2]) - wgpu_host.linear_depth(buffer))
    facing = np.einsum("ij,ij->i", nrm, to_eye) / dist
    frac = uv % 1.0
    keep = (
        inside
        & (seen < 0.01)
        & (facing > 0.5)
        & (np.abs(nrm[:, 1]) < 0.7)
        & ((frac > 0.04) & (frac < 0.96)).all(axis=1)
    )
    idx = np.nonzero(keep)[0]
    _, first = np.unique(row[idx] * PROBE + col[idx], return_index=True)
    idx = idx[first]
    return frames, idx, col[idx], row[idx], uv[idx]


def _texels(uv):
    """The ``(col, row)`` of the 512 map each texture coordinate lands in (repeat wrap, V up)."""
    c = np.minimum(((uv[:, 0] % 1.0) * MAP).astype(int), MAP - 1)
    r = np.minimum(((1.0 - uv[:, 1] % 1.0) * MAP).astype(int), MAP - 1)
    return c, r


def _flat_around(image, c, r, spread: int, half: int = 14):
    """Which texels sit in a neighbourhood whose values differ by at most ``spread``: where filtering cannot matter."""
    out = np.zeros(len(c), dtype=bool)
    for i, (cc, rr) in enumerate(zip(c, r, strict=True)):
        win = image[max(rr - half, 0) : rr + half + 1, max(cc - half, 0) : cc + half + 1]
        flat = win.reshape(-1, win.shape[-1] if win.ndim == 3 else 1)
        out[i] = np.ptp(flat.astype(np.int64), axis=0).max() <= spread
    return out


@pytest.mark.parametrize(
    ("mode", "suffix", "spread", "gray"),
    [(8, "_R", 0, True), (7, "_M", 0, True), (9, "_AO", 16, True), (1, "_BC", 0, False)],
    ids=["roughness-bands", "metalness-checker", "ao-radial", "base-colour-patches"],
)
def test_the_host_draws_the_synthetic_maps_where_their_texture_coordinates_say(
    renderer, synthetic_scene, mode, suffix, spread, gray
) -> None:
    """
    The T4 tier-1 proof: at the pixels where the ball's UVs land on a flat part of a synthetic map, the host's debug
    view holds that map's value. The ORM channels (roughness G, metalness B, AO R), the sRGB colour and the V
    orientation (the patch rows differ top and bottom, so a flipped V fails) all reach the shader where they should.
    """
    from hogshade.testdata import synthetic
    from hogshade.texture_cook.colour import srgb_to_linear

    frames, _idx, pc, pr, uv = _probe(renderer, synthetic_scene, mode)
    tc, tr = _texels(uv)
    image = synthetic.render_map(suffix, None, MAP)
    flat = _flat_around(image, tc, tr, spread)
    assert flat.sum() >= 150, f"{suffix}: only {int(flat.sum())} probe pixels sit on a flat part of the map"
    texel = image[tr[flat], tc[flat]].astype(np.float64) / 255.0
    want = srgb_to_linear(texel) if not gray else np.repeat(texel[:, None], 3, axis=1)
    got = frames.forward[pr[flat], pc[flat]]
    close = np.abs(got - want).max(axis=1) < 0.05
    assert close.mean() >= 0.95, f"{suffix}: {close.mean():.1%} of {int(flat.sum())} probe pixels match"


@pytest.mark.parametrize(("mode", "suffix", "gray"), [(7, "_M", True), (1, "_BC", False)], ids=["metalness", "colour"])
def test_the_probe_fails_when_the_expectation_has_v_flipped(renderer, synthetic_scene, mode, suffix, gray) -> None:
    """
    The control that makes the probe worth trusting: read the same views with V flipped in the expectation and the
    agreement collapses (metalness under 1 percent, the colour patches about 60 in the first measurement). The
    roughness view, a function of U alone, is rightly not asked.
    """
    from hogshade.testdata import synthetic
    from hogshade.texture_cook.colour import srgb_to_linear

    frames, _idx, pc, pr, uv = _probe(renderer, synthetic_scene, mode)
    tc, _tr = _texels(uv)
    flipped_rows = np.minimum(((uv[:, 1] % 1.0) * MAP).astype(int), MAP - 1)  # V up taken as the row index: wrong
    image = synthetic.render_map(suffix, None, MAP)
    flat = _flat_around(image, tc, flipped_rows, 0)
    assert flat.sum() >= 50, f"{suffix}: only {int(flat.sum())} probe pixels sit on a flat part of the map"
    texel = image[flipped_rows[flat], tc[flat]].astype(np.float64) / 255.0
    want = srgb_to_linear(texel) if not gray else np.repeat(texel[:, None], 3, axis=1)
    close = np.abs(frames.forward[pr[flat], pc[flat]] - want).max(axis=1) < 0.05
    assert close.mean() < 0.8, (
        f"{suffix}: the flipped expectation still matches {close.mean():.1%}: the probe is blind to V"
    )


def test_the_normal_maps_green_and_red_channels_tilt_the_shading_normal_the_authored_way(
    renderer, synthetic_scene
) -> None:
    """
    The T3b finding made a test (the conventions were eyeballed on the brick): through the mesh's MikkTSpace frame
    the texel's tangent-space normal gives the world shading normal the host shows in view 11. On the texels that
    lean in V (green) and in U (red) the authored reading matches the render and the channel-flipped reading matches
    nowhere, so the instrument can tell the conventions apart. The 0.55 floor sits under the measured 66 percent
    (green) and 85 percent (red): the rest is a residual of a median 0.03 with a tail past 0.1 that no viewing-angle
    or handedness split explained (the red channel is flat across angle; the green samples are all one quadrant), so
    the floor is a guard against a gross break and the flipped control is what carries the proof.
    """
    from hogshade.testdata import synthetic

    frames, idx, pc, pr, uv = _probe(renderer, synthetic_scene, 11)
    tc, tr = _texels(uv)
    image = synthetic.render_map("_N", None, MAP)
    flat = _flat_around(image, tc, tr, 2)
    verts = renderer.mesh.vertices[idx][flat]
    n = verts[:, wgpu_host.COL_NORMAL].astype(np.float64)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    tangent = verts[:, wgpu_host.COL_TANGENT].astype(np.float64)
    t = tangent - n * (n * tangent).sum(1, keepdims=True)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    b = np.cross(n, t) * verts[:, wgpu_host.COL_TANGENT_SIGN : wgpu_host.COL_TANGENT_SIGN + 1].astype(np.float64)
    rg = image[tr[flat], tc[flat]][:, :2].astype(np.float64) / 255.0 * 2.0 - 1.0
    ts = np.stack([rg[:, 0], rg[:, 1], np.sqrt(np.clip(1.0 - (rg**2).sum(1), 0.0, 1.0))], axis=1)
    got = frames.forward[pr[flat], pc[flat]] * 2.0 - 1.0
    got /= np.linalg.norm(got, axis=1, keepdims=True)

    def world(tangent_space):
        w = tangent_space[:, :1] * t + tangent_space[:, 1:2] * b + tangent_space[:, 2:3] * n
        return w / np.linalg.norm(w, axis=1, keepdims=True)

    for axis, name in ((1, "green, the V lean"), (0, "red, the U lean")):
        leans = np.abs(ts[:, axis]) > 0.2
        flipped = ts.copy()
        flipped[:, axis] *= -1.0
        as_authored = np.linalg.norm(got - world(ts), axis=1)[leans] < 0.1
        as_flipped = np.linalg.norm(got - world(flipped), axis=1)[leans] < 0.1
        assert leans.sum() >= 80, f"{name}: only {int(leans.sum())} probe pixels lean"
        assert as_authored.mean() >= 0.55, f"{name}: {as_authored.mean():.1%} match as authored"
        assert as_flipped.mean() <= 0.05, f"{name}: {as_flipped.mean():.1%} still match with the channel flipped"
