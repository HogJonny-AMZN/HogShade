"""
HogShade: core/models/legacy_v1.wgsl on the GPU agrees with hogshade/reference/legacy_v1.py (phase 2 plan, task 18).
Package: tests/core/test_legacy_v1_gpu

Row layouts (float32, one item per thread):
  material 22: base(3) metal subsurface spec rough spec_tint aniso sheen sheen_tint clearcoat cc_gloss
               use_vc_ao has_alpha use_valpha use_cutout flip_back rough_is_gloss use_spec_mask flip(3)
  samples  22: base(4) specular(4) rough metal ao(3) normal_ts(3) use_base use_spec use_rough use_metal use_normal
  geometry 20: n(3) t(3) b(3) v(3) p(3) vertex_color(4) front
  inputs   38: base(3) metal rough ao emissive(3) n(3) v(3) p(3) f0(3) cavity opacity spec_weight t(3) b(3) pa(4) pb(4)
  light    16, env 12: as in test_legacy_v2_gpu
"""

from __future__ import annotations

import numpy as np
import pytest
from gpu_harness import kernel, unit_vectors
from test_legacy_v2_gpu import ENV, LIGHT, _env, _f32, _frame, _lights

from hogshade.reference import legacy_v1 as ref

MATERIAL, SAMPLES, GEOMETRY, INPUTS = 22, 22, 20, 38

_LOADERS = """
fn hs_material(base: u32) -> legacy_v1_Material {
    var m: legacy_v1_Material;
    m.base_color = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    m.metalness = hs_in[base + 3u]; m.subsurface = hs_in[base + 4u]; m.specular = hs_in[base + 5u];
    m.roughness = hs_in[base + 6u]; m.specular_tint = hs_in[base + 7u]; m.anisotropic = hs_in[base + 8u];
    m.sheen = hs_in[base + 9u]; m.sheen_tint = hs_in[base + 10u]; m.clearcoat = hs_in[base + 11u];
    m.clearcoat_gloss = hs_in[base + 12u];
    m.use_vertex_color_ao = u32(hs_in[base + 13u]); m.has_alpha = u32(hs_in[base + 14u]);
    m.use_vertex_alpha = u32(hs_in[base + 15u]); m.use_cutout_alpha = u32(hs_in[base + 16u]);
    m.flip_backface_normals = u32(hs_in[base + 17u]); m.rough_is_gloss = u32(hs_in[base + 18u]);
    m.use_specular_mask = u32(hs_in[base + 19u]);
    m.normal_flip = vec3<f32>(hs_in[base + 20u], hs_in[base + 21u], 1.0);
    return m;
}
fn hs_samples(base: u32) -> legacy_v1_Samples {
    var s: legacy_v1_Samples;
    s.base_color = vec4<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u], hs_in[base + 3u]);
    s.specular = vec4<f32>(hs_in[base + 4u], hs_in[base + 5u], hs_in[base + 6u], hs_in[base + 7u]);
    s.roughness = hs_in[base + 8u]; s.metalness = hs_in[base + 9u];
    s.ao = vec3<f32>(hs_in[base + 10u], hs_in[base + 11u], hs_in[base + 12u]);
    s.normal_ts = vec3<f32>(hs_in[base + 13u], hs_in[base + 14u], hs_in[base + 15u]);
    s.use_base_map = u32(hs_in[base + 16u]); s.use_specular_map = u32(hs_in[base + 17u]);
    s.use_roughness_map = u32(hs_in[base + 18u]); s.use_metalness_map = u32(hs_in[base + 19u]);
    s.use_normal_map = u32(hs_in[base + 20u]);
    return s;
}
fn hs_geometry(base: u32) -> legacy_v1_Geometry {
    var g: legacy_v1_Geometry;
    g.normal_ws = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    g.tangent_ws = vec3<f32>(hs_in[base + 3u], hs_in[base + 4u], hs_in[base + 5u]);
    g.binormal_ws = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    g.view_ws = vec3<f32>(hs_in[base + 9u], hs_in[base + 10u], hs_in[base + 11u]);
    g.position_ws = vec3<f32>(hs_in[base + 12u], hs_in[base + 13u], hs_in[base + 14u]);
    g.vertex_color = vec4<f32>(hs_in[base + 15u], hs_in[base + 16u], hs_in[base + 17u], hs_in[base + 18u]);
    g.front_face = u32(hs_in[base + 19u]);
    return g;
}
fn hs_inputs(base: u32) -> ShadingInputs {
    var i: ShadingInputs;
    i.surface.base_color = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    i.surface.metalness = hs_in[base + 3u]; i.surface.roughness = hs_in[base + 4u]; i.surface.ao = hs_in[base + 5u];
    i.surface.emissive = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    i.surface.normal_ws = vec3<f32>(hs_in[base + 9u], hs_in[base + 10u], hs_in[base + 11u]);
    i.surface.model = HOGSHADE_MODEL_LEGACY_V1;
    i.view_ws = vec3<f32>(hs_in[base + 12u], hs_in[base + 13u], hs_in[base + 14u]);
    i.position_ws = vec3<f32>(hs_in[base + 15u], hs_in[base + 16u], hs_in[base + 17u]);
    i.specular_f0 = vec3<f32>(hs_in[base + 18u], hs_in[base + 19u], hs_in[base + 20u]);
    i.cavity = hs_in[base + 21u]; i.opacity = hs_in[base + 22u]; i.specular_weight = hs_in[base + 23u];
    i.tangent_ws = vec3<f32>(hs_in[base + 24u], hs_in[base + 25u], hs_in[base + 26u]);
    i.binormal_ws = vec3<f32>(hs_in[base + 27u], hs_in[base + 28u], hs_in[base + 29u]);
    i.model_params_a = vec4<f32>(hs_in[base + 30u], hs_in[base + 31u], hs_in[base + 32u], hs_in[base + 33u]);
    i.model_params_b = vec4<f32>(hs_in[base + 34u], hs_in[base + 35u], hs_in[base + 36u], hs_in[base + 37u]);
    return i;
}
fn hs_light(base: u32) -> LightSource {
    var l: LightSource;
    l.kind = u32(hs_in[base + 0u]);
    l.position_ws = vec3<f32>(hs_in[base + 1u], hs_in[base + 2u], hs_in[base + 3u]);
    l.direction_ws = vec3<f32>(hs_in[base + 4u], hs_in[base + 5u], hs_in[base + 6u]);
    l.intensity = hs_in[base + 7u];
    l.color = vec3<f32>(hs_in[base + 8u], hs_in[base + 9u], hs_in[base + 10u]);
    l.range = hs_in[base + 11u];
    l.cone_cos = vec2<f32>(hs_in[base + 12u], hs_in[base + 13u]);
    l.shadow = hs_in[base + 14u];
    l._pad = 0.0;
    return l;
}
fn hs_env(base: u32) -> EnvironmentSamples {
    var e: EnvironmentSamples;
    e.irradiance_over_pi = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    e.specular = vec3<f32>(hs_in[base + 3u], hs_in[base + 4u], hs_in[base + 5u]);
    e.brdf = vec2<f32>(hs_in[base + 6u], hs_in[base + 7u]);
    e.hemisphere = vec3<f32>(hs_in[base + 8u], hs_in[base + 9u], hs_in[base + 10u]);
    e.hemisphere_mode = u32(hs_in[base + 11u]);
    return e;
}
"""


def _material(n: int, seed: int) -> tuple[ref.Material, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, MATERIAL))
    rows[:, 0:3] = rng.uniform(0.0, 1.0, size=(n, 3))
    rows[:, 3:13] = rng.uniform(0.0, 1.0, size=(n, 10))
    rows[:, 6] = rng.uniform(0.05, 1.0, size=n)  # roughness away from zero: GTR2 with alpha^2 -> 0 is a delta
    rows[:, 13:20] = rng.integers(0, 2, size=(n, 7))
    rows[:, 20:22] = rng.choice([-1.0, 1.0], size=(n, 2))
    rows = _f32(rows)
    m = ref.Material(
        base_color=rows[:, 0:3],
        metalness=rows[:, 3],
        subsurface=rows[:, 4],
        specular=rows[:, 5],
        roughness=rows[:, 6],
        specular_tint=rows[:, 7],
        anisotropic=rows[:, 8],
        sheen=rows[:, 9],
        sheen_tint=rows[:, 10],
        clearcoat=rows[:, 11],
        clearcoat_gloss=rows[:, 12],
        use_vertex_color_ao=rows[:, 13].astype(int),
        has_alpha=rows[:, 14].astype(int),
        use_vertex_alpha=rows[:, 15].astype(int),
        use_cutout_alpha=rows[:, 16].astype(int),
        flip_backface_normals=rows[:, 17].astype(int),
        rough_is_gloss=rows[:, 18].astype(int),
        use_specular_mask=rows[:, 19].astype(int),
        normal_flip=np.concatenate([rows[:, 20:22], np.ones((n, 1))], axis=-1),
    )
    return m, rows


def _samples(n: int, seed: int) -> tuple[ref.Samples, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, SAMPLES))
    rows[:, 0:8] = rng.uniform(0.0, 1.0, size=(n, 8))
    rows[:, 8] = rng.uniform(0.05, 0.95, size=n)
    rows[:, 9] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 10:13] = rng.uniform(0.2, 1.0, size=(n, 3))
    xy = rng.uniform(-0.6, 0.6, size=(n, 2))
    rows[:, 13:15] = xy
    rows[:, 15] = np.sqrt(1.0 - (xy * xy).sum(-1))
    rows[:, 16:21] = rng.integers(0, 2, size=(n, 5))
    rows = _f32(rows)
    s = ref.Samples(
        base_color=rows[:, 0:4],
        specular=rows[:, 4:8],
        roughness=rows[:, 8],
        metalness=rows[:, 9],
        ao=rows[:, 10:13],
        normal_ts=rows[:, 13:16],
        use_base_map=rows[:, 16].astype(int),
        use_specular_map=rows[:, 17].astype(int),
        use_roughness_map=rows[:, 18].astype(int),
        use_metalness_map=rows[:, 19].astype(int),
        use_normal_map=rows[:, 20].astype(int),
    )
    return s, rows


def _geometry(n: int, seed: int) -> tuple[ref.Geometry, np.ndarray]:
    rng = np.random.default_rng(seed)
    normal, tangent, binormal = _frame(n, seed)
    rows = np.zeros((n, GEOMETRY))
    rows[:, 0:3], rows[:, 3:6], rows[:, 6:9] = normal, tangent, binormal
    view = unit_vectors(n, seed + 7)
    rows[:, 9:12] = np.where(((normal * view).sum(-1) < 0)[:, None], -view, view)
    rows[:, 12:15] = rng.uniform(-5, 5, size=(n, 3))
    rows[:, 15:19] = rng.uniform(0.0, 1.0, size=(n, 4))
    rows[:, 19] = rng.integers(0, 2, size=n)
    rows = _f32(rows)
    g = ref.Geometry(
        normal_ws=rows[:, 0:3],
        tangent_ws=rows[:, 3:6],
        binormal_ws=rows[:, 6:9],
        view_ws=rows[:, 9:12],
        position_ws=rows[:, 12:15],
        vertex_color=rows[:, 15:19],
        front_face=rows[:, 19].astype(int),
    )
    return g, rows


def _inputs(n: int, seed: int) -> tuple[ref.Inputs, np.ndarray]:
    rng = np.random.default_rng(seed)
    normal, tangent, binormal = _frame(n, seed + 1)
    rows = np.zeros((n, INPUTS))
    rows[:, 0:3] = rng.uniform(0.02, 1.0, size=(n, 3))
    rows[:, 3] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 4] = rng.uniform(0.05, 1.0, size=n)
    rows[:, 5] = rng.uniform(0.2, 1.0, size=n)
    rows[:, 9:12] = normal
    # seed offset 200: the lights helper draws directions at seed + 1, and a view equal to a light direction
    # after the facing flip makes l = -v, a zero half vector, which normalize() cannot represent
    view = unit_vectors(n, seed + 200)
    rows[:, 12:15] = np.where(((normal * view).sum(-1) < 0)[:, None], -view, view)
    rows[:, 15:18] = rng.uniform(-3, 3, size=(n, 3))
    rows[:, 18:21] = rng.uniform(0.02, 1.0, size=(n, 3))
    rows[:, 21] = 1.0
    rows[:, 22] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 23] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 24:27], rows[:, 27:30] = tangent, binormal
    rows[:, 30:38] = rng.uniform(0.0, 1.0, size=(n, 8))
    rows[:, 37] = 0.0
    rows = _f32(rows)
    i = ref.Inputs(
        base_color=rows[:, 0:3],
        metalness=rows[:, 3],
        roughness=rows[:, 4],
        ao=rows[:, 5],
        emissive=rows[:, 6:9],
        normal_ws=rows[:, 9:12],
        view_ws=rows[:, 12:15],
        position_ws=rows[:, 15:18],
        specular_f0=rows[:, 18:21],
        cavity=rows[:, 21],
        opacity=rows[:, 22],
        specular_weight=rows[:, 23],
        tangent_ws=rows[:, 24:27],
        binormal_ws=rows[:, 27:30],
        params_a=rows[:, 30:34],
        params_b=rows[:, 34:38],
    )
    return i, rows


def test_inputs_match_reference(gpu) -> None:
    n = 2048
    m, mr = _material(n, 1)
    s, sr = _samples(n, 2)
    g, gr = _geometry(n, 3)
    body = """
    let i0 = legacy_v1_inputs(hs_material(base), hs_samples(base + 22u), hs_geometry(base + 44u));
    let o = i * 24u;
    hs_out[o + 0u] = i0.surface.base_color.x; hs_out[o + 1u] = i0.surface.base_color.y; hs_out[o + 2u] = i0.surface.base_color.z;
    hs_out[o + 3u] = i0.surface.metalness; hs_out[o + 4u] = i0.surface.roughness; hs_out[o + 5u] = i0.surface.ao;
    hs_out[o + 6u] = i0.surface.normal_ws.x; hs_out[o + 7u] = i0.surface.normal_ws.y; hs_out[o + 8u] = i0.surface.normal_ws.z;
    hs_out[o + 9u] = i0.specular_f0.x; hs_out[o + 10u] = i0.specular_f0.y; hs_out[o + 11u] = i0.specular_f0.z;
    hs_out[o + 12u] = i0.opacity; hs_out[o + 13u] = i0.specular_weight; hs_out[o + 14u] = f32(i0.surface.model);
    hs_out[o + 15u] = i0.model_params_a.x; hs_out[o + 16u] = i0.model_params_a.w; hs_out[o + 17u] = i0.model_params_b.y;
    hs_out[o + 18u] = i0.tangent_ws.x; hs_out[o + 19u] = i0.binormal_ws.y; hs_out[o + 20u] = i0.surface.emissive.x;
    hs_out[o + 21u] = i0.cavity; hs_out[o + 22u] = i0.model_params_b.z; hs_out[o + 23u] = i0.model_params_a.y;
    """
    out = gpu.run(_LOADERS + kernel(body, MATERIAL + SAMPLES + GEOMETRY), np.concatenate([mr, sr, gr], -1), 24, n)
    e = ref.inputs(m, s, g)
    np.testing.assert_allclose(out[:, 0:3], e.base_color, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 3], e.metalness, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 4], e.roughness, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 5], e.ao, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 6:9], e.normal_ws, rtol=1e-4, atol=1e-5)
    np.testing.assert_allclose(out[:, 9:12], e.specular_f0, rtol=1e-4, atol=1e-6)
    np.testing.assert_allclose(out[:, 12], e.opacity, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 13], e.specular_weight, rtol=1e-5, atol=1e-6)
    assert np.all(out[:, 14] == ref.MODEL_LEGACY_V1)
    np.testing.assert_allclose(out[:, 15], e.params_a[:, 0], rtol=1e-6)
    np.testing.assert_allclose(out[:, 16], e.params_a[:, 3], rtol=1e-6)
    np.testing.assert_allclose(out[:, 17], e.params_b[:, 1], rtol=1e-6)
    np.testing.assert_allclose(out[:, 18], e.tangent_ws[:, 0], rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 19], e.binormal_ws[:, 1], rtol=1e-5, atol=1e-6)
    assert np.all(out[:, 20] == 0.0) and np.all(out[:, 21] == 1.0)
    np.testing.assert_allclose(out[:, 22], e.params_b[:, 2], rtol=1e-6)
    np.testing.assert_allclose(out[:, 23], e.params_a[:, 1], rtol=1e-6)


def test_evaluate_light_matches_reference(gpu) -> None:
    n = 2048
    i, ir = _inputs(n, 11)
    lr = _lights(n, 12)
    e, er = _env(n, 13)
    body = """
    let c = legacy_v1_evaluate_light(hs_inputs(base), hs_light(base + 38u), hs_env(base + 54u));
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + LIGHT + ENV), np.concatenate([ir, lr, er], -1), 3, n)
    expect = ref.evaluate_light(i, lr, e)
    # the anisotropic GTR2 peaks sharply at low roughness; scale the tolerance by the row's magnitude
    scale = np.abs(expect).max(axis=-1, keepdims=True) + 1e-3
    assert np.all(np.isfinite(out))
    np.testing.assert_allclose(out / scale, expect / scale, rtol=2e-4, atol=2e-4)
    assert (expect.sum(-1) > 0).mean() > 0.2


def test_evaluate_env_matches_reference(gpu) -> None:
    n = 2048
    i, ir = _inputs(n, 21)
    e, er = _env(n, 22)
    body = """
    let c = legacy_v1_evaluate_env(hs_inputs(base), hs_env(base + 38u));
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + ENV), np.concatenate([ir, er], -1), 3, n)
    np.testing.assert_allclose(out, ref.evaluate_env(i, e), rtol=1e-4, atol=1e-5)


def test_env_lookup_is_the_negated_n_dot_v(gpu) -> None:
    """The v1 sign bug, kept as the record: the LUT column is -saturate(n.v)."""
    n = 512
    i, ir = _inputs(n, 31)
    body = """
    let lk = models_env_lookup(hs_inputs(base));
    hs_out[i * 2u + 0u] = lk.x; hs_out[i * 2u + 1u] = lk.y;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS), ir, 2, n)
    np.testing.assert_allclose(out, ref.env_lookup(i), rtol=1e-5, atol=1e-6)
    assert np.all(out[:, 0] <= 0.0)


@pytest.mark.parametrize("mode", range(9))
def test_debug_modes_are_finite_and_match_reference(gpu, mode: int) -> None:
    n = 128
    i, ir = _inputs(n, 41 + mode)
    lr = _lights(n, 42 + mode)
    e, er = _env(n, 43 + mode)
    body = f"""
    var slots = lighting_slots_empty();
    slots.light[0] = hs_light(base + 38u);
    slots.count = 1u;
    let c = legacy_v1_debug(hs_inputs(base), slots, hs_env(base + 54u), {mode}u);
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + LIGHT + ENV), np.concatenate([ir, lr, er], -1), 3, n)
    assert np.all(np.isfinite(out)), mode
    expect = ref.debug(i, [lr], e, mode)
    scale = np.abs(expect).max(axis=-1, keepdims=True) + 1e-3
    np.testing.assert_allclose(out / scale, expect / scale, rtol=2e-4, atol=2e-4, err_msg=ref.DEBUG_MODE_NAMES[mode])


def test_shade_through_the_dispatcher_equals_the_model(gpu) -> None:
    n = 512
    i, ir = _inputs(n, 51)
    lr = _lights(n, 52)
    e, er = _env(n, 53)
    body = """
    var slots = lighting_slots_empty();
    slots.light[0] = hs_light(base + 38u);
    slots.count = 1u;
    let c = models_shade(hs_inputs(base), slots, hs_env(base + 54u), HOGSHADE_DEBUG_NONE).color;
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + LIGHT + ENV), np.concatenate([ir, lr, er], -1), 3, n)
    expect = ref.shade(i, [lr], e)
    scale = np.abs(expect).max(axis=-1, keepdims=True) + 1e-3
    np.testing.assert_allclose(out / scale, expect / scale, rtol=2e-4, atol=2e-4)


def test_furnace_records_the_v1_response(gpu) -> None:
    """White environment, white dielectric, no lights, no extra lobes: v1's Disney diffuse returns its Burley
    value (not 1), plus the dome term and the specular albedo read at the LUT's u = 0 column. The GPU must
    equal the reference; the value itself is recorded, not judged."""
    n = 64
    rng = np.random.default_rng(6)
    rough = rng.uniform(0.05, 1.0, size=n)
    nv = rng.uniform(0.1, 1.0, size=n)
    normal = np.tile([0.0, 0.0, 1.0], (n, 1))
    tangent = np.tile([1.0, 0.0, 0.0], (n, 1))
    binormal = np.tile([0.0, 1.0, 0.0], (n, 1))
    view = np.stack([np.sqrt(1 - nv * nv), np.zeros(n), nv], axis=-1)
    rows = np.zeros((n, INPUTS + ENV))
    rows[:, 0:3] = 1.0
    rows[:, 4] = rough
    rows[:, 5] = 1.0
    rows[:, 9:12] = normal
    rows[:, 12:15] = view
    rows[:, 18:21] = 0.5 * 0.08  # Cspec0 for specular 0.5, no tint, dielectric
    rows[:, 21] = 1.0
    rows[:, 22] = 1.0
    rows[:, 23] = 0.5
    rows[:, 24:27], rows[:, 27:30] = tangent, binormal
    rows[:, 38:41] = 1.0
    rows[:, 41:44] = 1.0
    rows[:, 44] = 1.0
    rows[:, 45] = 0.0
    rows[:, 46:49] = 1.0
    rows = _f32(rows)
    body = """
    let c = models_shade(hs_inputs(base), lighting_slots_empty(), hs_env(base + 38u), HOGSHADE_DEBUG_NONE).color;
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + ENV), rows, 3, n)
    i = ref.Inputs(
        base_color=rows[:, 0:3],
        metalness=rows[:, 3],
        roughness=rows[:, 4],
        ao=rows[:, 5],
        emissive=rows[:, 6:9],
        normal_ws=rows[:, 9:12],
        view_ws=rows[:, 12:15],
        position_ws=rows[:, 15:18],
        specular_f0=rows[:, 18:21],
        cavity=rows[:, 21],
        opacity=rows[:, 22],
        specular_weight=rows[:, 23],
        tangent_ws=rows[:, 24:27],
        binormal_ws=rows[:, 27:30],
        params_a=rows[:, 30:34],
        params_b=rows[:, 34:38],
    )
    e = ref.EnvSamples(
        irradiance_over_pi=rows[:, 38:41],
        specular=rows[:, 41:44],
        brdf=rows[:, 44:46],
        hemisphere=rows[:, 46:49],
        hemisphere_mode=rows[:, 49].astype(int),
    )
    expect = ref.shade(i, [], e)
    np.testing.assert_allclose(out, expect, rtol=1e-4, atol=1e-5)
    assert 1.0 < expect.mean() < 3.0, expect.mean()  # dome plus environment plus the u = 0 specular albedo
