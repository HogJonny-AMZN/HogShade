"""
HogShade: core/models/legacy_v2.wgsl on the GPU agrees with hogshade/reference/legacy_v2.py (phase 2 plan, tasks 11 and 12).
Package: tests/core/test_legacy_v2_gpu

Row layouts (float32, one item per thread):
  material 18: base(3) rough metal spec tint ior bump use_vc use_vao use_valpha has_alpha flip(3) flip_back f0_map
  samples  17: base(4) rough metal f0(3) spec_amount ao cavity emissive(3) normal_ts(3)
  geometry 23: n(3) t(3) b(3) v(3) p(3) vertex_color(4) vertex_ao(3) front
  inputs   24: base(3) metal rough ao emissive(3) n(3) v(3) p(3) f0(3) cavity opacity spec_weight
  light    16: kind position(3) direction(3) intensity color(3) range cone_cos(2) shadow pad
  env      12: irradiance(3) specular(3) brdf(2) hemisphere(3) mode
"""

from __future__ import annotations

import numpy as np
import pytest
from gpu_harness import kernel, unit_vectors

from hogshade.reference import legacy_v2 as ref
from hogshade.reference import lighting

MATERIAL, SAMPLES, GEOMETRY, INPUTS, LIGHT, ENV = 18, 17, 23, 24, 16, 12

_LOADERS = """
fn hs_material(base: u32) -> legacy_v2_Material {
    var m: legacy_v2_Material;
    m.base_color = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    m.roughness = hs_in[base + 3u]; m.metalness = hs_in[base + 4u]; m.specular = hs_in[base + 5u];
    m.specular_tint = hs_in[base + 6u]; m.ior = hs_in[base + 7u]; m.bump_intensity = hs_in[base + 8u];
    m.use_vertex_color = u32(hs_in[base + 9u]); m.use_vertex_ao = u32(hs_in[base + 10u]);
    m.use_vertex_alpha = u32(hs_in[base + 11u]); m.has_alpha = u32(hs_in[base + 12u]);
    m.normal_flip = vec3<f32>(hs_in[base + 13u], hs_in[base + 14u], hs_in[base + 15u]);
    m.flip_backface_normals = u32(hs_in[base + 16u]); m.specular_f0_from_map = u32(hs_in[base + 17u]);
    return m;
}
fn hs_samples(base: u32) -> legacy_v2_Samples {
    var s: legacy_v2_Samples;
    s.base_color = vec4<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u], hs_in[base + 3u]);
    s.roughness = hs_in[base + 4u]; s.metalness = hs_in[base + 5u];
    s.specular_f0 = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    s.specular_amount = hs_in[base + 9u]; s.ao = hs_in[base + 10u]; s.cavity = hs_in[base + 11u];
    s.emissive = vec3<f32>(hs_in[base + 12u], hs_in[base + 13u], hs_in[base + 14u]);
    s.normal_ts = vec3<f32>(hs_in[base + 15u], hs_in[base + 16u], 0.0);
    return s;
}
fn hs_geometry(base: u32) -> legacy_v2_Geometry {
    var g: legacy_v2_Geometry;
    g.normal_ws = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    g.tangent_ws = vec3<f32>(hs_in[base + 3u], hs_in[base + 4u], hs_in[base + 5u]);
    g.binormal_ws = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    g.view_ws = vec3<f32>(hs_in[base + 9u], hs_in[base + 10u], hs_in[base + 11u]);
    g.position_ws = vec3<f32>(hs_in[base + 12u], hs_in[base + 13u], hs_in[base + 14u]);
    g.vertex_color = vec4<f32>(hs_in[base + 15u], hs_in[base + 16u], hs_in[base + 17u], hs_in[base + 18u]);
    g.vertex_ao = vec3<f32>(hs_in[base + 19u], hs_in[base + 20u], hs_in[base + 21u]);
    g.front_face = u32(hs_in[base + 22u]);
    return g;
}
fn hs_inputs(base: u32) -> ShadingInputs {
    var i: ShadingInputs;
    i.surface.base_color = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    i.surface.metalness = hs_in[base + 3u]; i.surface.roughness = hs_in[base + 4u]; i.surface.ao = hs_in[base + 5u];
    i.surface.emissive = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    i.surface.normal_ws = vec3<f32>(hs_in[base + 9u], hs_in[base + 10u], hs_in[base + 11u]);
    i.surface.model = HOGSHADE_MODEL_LEGACY_V2;
    i.view_ws = vec3<f32>(hs_in[base + 12u], hs_in[base + 13u], hs_in[base + 14u]);
    i.position_ws = vec3<f32>(hs_in[base + 15u], hs_in[base + 16u], hs_in[base + 17u]);
    i.specular_f0 = vec3<f32>(hs_in[base + 18u], hs_in[base + 19u], hs_in[base + 20u]);
    i.cavity = hs_in[base + 21u]; i.opacity = hs_in[base + 22u]; i.specular_weight = hs_in[base + 23u];
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


def _f32(x: np.ndarray) -> np.ndarray:
    """What the GPU sees: round the inputs to float32 once so both sides start from the same numbers."""
    return np.asarray(x, dtype=np.float32).astype(np.float64)


def _frame(n: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    normal = unit_vectors(n, seed)
    helper = unit_vectors(n, seed + 100)
    tangent = np.cross(normal, helper)
    tangent /= np.linalg.norm(tangent, axis=-1, keepdims=True)
    binormal = np.cross(normal, tangent)
    return normal, tangent, binormal


def _material(n: int, seed: int) -> tuple[ref.Material, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, MATERIAL))
    rows[:, 0:3] = rng.uniform(0.0, 1.0, size=(n, 3))
    rows[:, 3] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 4] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 5] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 6] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 7] = rng.uniform(1.0, 2.5, size=n)
    rows[:, 8] = rng.uniform(0.0, 1.5, size=n)
    rows[:, 9:13] = rng.integers(0, 2, size=(n, 4))
    rows[:, 13:16] = rng.choice([-1.0, 1.0], size=(n, 3))
    rows[:, 16:18] = rng.integers(0, 2, size=(n, 2))
    rows = _f32(rows)
    m = ref.Material(
        base_color=rows[:, 0:3],
        roughness=rows[:, 3],
        metalness=rows[:, 4],
        specular=rows[:, 5],
        specular_tint=rows[:, 6],
        ior=rows[:, 7],
        bump_intensity=rows[:, 8],
        use_vertex_color=rows[:, 9].astype(int),
        use_vertex_ao=rows[:, 10].astype(int),
        use_vertex_alpha=rows[:, 11].astype(int),
        has_alpha=rows[:, 12].astype(int),
        normal_flip=rows[:, 13:16],
        flip_backface_normals=rows[:, 16].astype(int),
        specular_f0_from_map=rows[:, 17].astype(int),
    )
    return m, rows


def _samples(n: int, seed: int) -> tuple[ref.Samples, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, SAMPLES))
    rows[:, 0:4] = rng.uniform(0.0, 1.0, size=(n, 4))
    rows[:, 4:6] = rng.uniform(0.0, 1.0, size=(n, 2))
    rows[:, 6:9] = rng.uniform(0.0, 0.3, size=(n, 3))
    rows[:, 9:12] = rng.uniform(0.2, 1.0, size=(n, 3))
    rows[:, 12:15] = rng.uniform(0.0, 2.0, size=(n, 3))
    xy = rng.uniform(-0.7, 0.7, size=(n, 2))
    rows[:, 15:17] = xy
    rows = _f32(rows)
    s = ref.Samples(
        base_color=rows[:, 0:4],
        roughness=rows[:, 4],
        metalness=rows[:, 5],
        specular_f0=rows[:, 6:9],
        specular_amount=rows[:, 9],
        ao=rows[:, 10],
        cavity=rows[:, 11],
        emissive=rows[:, 12:15],
        normal_ts=np.concatenate([rows[:, 15:17], np.zeros((n, 1))], axis=-1),
    )
    return s, rows


def _geometry(n: int, seed: int) -> tuple[ref.Geometry, np.ndarray]:
    rng = np.random.default_rng(seed)
    normal, tangent, binormal = _frame(n, seed)
    rows = np.zeros((n, GEOMETRY))
    rows[:, 0:3], rows[:, 3:6], rows[:, 6:9] = normal, tangent, binormal
    rows[:, 9:12] = unit_vectors(n, seed + 7)
    rows[:, 12:15] = rng.uniform(-5, 5, size=(n, 3))
    rows[:, 15:19] = rng.uniform(0.0, 1.0, size=(n, 4))
    rows[:, 19:22] = rng.uniform(0.2, 1.0, size=(n, 3))
    rows[:, 22] = rng.integers(0, 2, size=n)
    rows = _f32(rows)
    g = ref.Geometry(
        normal_ws=rows[:, 0:3],
        tangent_ws=rows[:, 3:6],
        binormal_ws=rows[:, 6:9],
        view_ws=rows[:, 9:12],
        position_ws=rows[:, 12:15],
        vertex_color=rows[:, 15:19],
        vertex_ao=rows[:, 19:22],
        front_face=rows[:, 22].astype(int),
    )
    return g, rows


def _inputs(n: int, seed: int) -> tuple[ref.Inputs, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, INPUTS))
    rows[:, 0:3] = rng.uniform(0.02, 1.0, size=(n, 3))
    rows[:, 3] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 4] = rng.uniform(0.05, 1.0, size=n)
    rows[:, 5] = rng.uniform(0.2, 1.0, size=n)
    rows[:, 6:9] = rng.uniform(0.0, 1.0, size=(n, 3))
    rows[:, 9:12] = unit_vectors(n, seed + 1)
    view = unit_vectors(n, seed + 2)
    view = np.where(((rows[:, 9:12] * view).sum(-1) < 0)[:, None], -view, view)
    rows[:, 12:15] = view
    rows[:, 15:18] = rng.uniform(-3, 3, size=(n, 3))
    rows[:, 18:21] = rng.uniform(0.02, 1.0, size=(n, 3))
    rows[:, 21] = rng.uniform(0.3, 1.0, size=n)
    rows[:, 22] = rng.uniform(0.0, 1.0, size=n)
    rows[:, 23] = rng.uniform(0.0, 1.0, size=n)
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
    )
    return i, rows


def _lights(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rows = lighting.light_rows(
        kind=rng.integers(1, 4, size=n),
        position=rng.uniform(-3, 3, size=(n, 3)),
        direction=unit_vectors(n, seed + 1),
        intensity=rng.uniform(0.5, 4.0, size=n),
        color=rng.uniform(0.2, 1.0, size=(n, 3)),
        range_=rng.uniform(4.0, 12.0, size=n),
        cone_cos=np.tile([0.95, 0.80], (n, 1)),
        shadow=rng.uniform(0.3, 1.0, size=n),
    )
    return _f32(rows)


def _env(n: int, seed: int, modes: np.ndarray | None = None) -> tuple[ref.EnvSamples, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, ENV))
    rows[:, 0:3] = rng.uniform(0.0, 1.5, size=(n, 3))
    rows[:, 3:6] = rng.uniform(0.0, 3.0, size=(n, 3))
    rows[:, 6] = rng.uniform(0.3, 1.0, size=n)
    rows[:, 7] = rng.uniform(0.0, 0.2, size=n)
    rows[:, 8:11] = rng.uniform(0.0, 1.0, size=(n, 3))
    rows[:, 11] = np.arange(n) % 3 if modes is None else modes
    rows = _f32(rows)
    e = ref.EnvSamples(
        irradiance_over_pi=rows[:, 0:3],
        specular=rows[:, 3:6],
        brdf=rows[:, 6:8],
        hemisphere=rows[:, 8:11],
        hemisphere_mode=rows[:, 11].astype(int),
    )
    return e, rows


def test_inputs_match_reference(gpu) -> None:
    n = 2048
    m, mr = _material(n, 1)
    s, sr = _samples(n, 2)
    g, gr = _geometry(n, 3)
    body = """
    let i0 = legacy_v2_inputs(hs_material(base), hs_samples(base + 18u), hs_geometry(base + 35u));
    let o = i * 20u;
    hs_out[o + 0u] = i0.surface.base_color.x; hs_out[o + 1u] = i0.surface.base_color.y; hs_out[o + 2u] = i0.surface.base_color.z;
    hs_out[o + 3u] = i0.surface.metalness; hs_out[o + 4u] = i0.surface.roughness; hs_out[o + 5u] = i0.surface.ao;
    hs_out[o + 6u] = i0.surface.emissive.x; hs_out[o + 7u] = i0.surface.emissive.y; hs_out[o + 8u] = i0.surface.emissive.z;
    hs_out[o + 9u] = i0.surface.normal_ws.x; hs_out[o + 10u] = i0.surface.normal_ws.y; hs_out[o + 11u] = i0.surface.normal_ws.z;
    hs_out[o + 12u] = i0.specular_f0.x; hs_out[o + 13u] = i0.specular_f0.y; hs_out[o + 14u] = i0.specular_f0.z;
    hs_out[o + 15u] = i0.cavity; hs_out[o + 16u] = i0.opacity; hs_out[o + 17u] = i0.specular_weight;
    hs_out[o + 18u] = f32(i0.surface.model); hs_out[o + 19u] = i0.view_ws.x;
    """
    out = gpu.run(_LOADERS + kernel(body, MATERIAL + SAMPLES + GEOMETRY), np.concatenate([mr, sr, gr], -1), 20, n)
    expect = ref.inputs(m, s, g)
    np.testing.assert_allclose(out[:, 0:3], expect.base_color, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 3], expect.metalness, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 4], expect.roughness, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 5], expect.ao, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 6:9], expect.emissive, rtol=1e-6)
    np.testing.assert_allclose(out[:, 9:12], expect.normal_ws, rtol=1e-4, atol=1e-5)
    np.testing.assert_allclose(out[:, 12:15], expect.specular_f0, rtol=1e-4, atol=1e-6)
    np.testing.assert_allclose(out[:, 15], expect.cavity, rtol=1e-6)
    np.testing.assert_allclose(out[:, 16], expect.opacity, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 17], expect.specular_weight, rtol=1e-5, atol=1e-6)
    assert np.all(out[:, 18] == ref.MODEL_LEGACY_V2)
    np.testing.assert_allclose(out[:, 19], expect.view_ws[:, 0], rtol=1e-5, atol=1e-6)


def test_evaluate_light_matches_reference(gpu) -> None:
    n = 2048
    i, ir = _inputs(n, 11)
    lr = _lights(n, 12)
    e, er = _env(n, 13)
    body = """
    let c = legacy_v2_evaluate_light(hs_inputs(base), hs_light(base + 24u), hs_env(base + 40u));
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + LIGHT + ENV), np.concatenate([ir, lr, er], -1), 3, n)
    expect = ref.evaluate_light(i, lr, e)
    np.testing.assert_allclose(out, expect, rtol=1e-4, atol=1e-5)
    assert (
        expect.sum(-1) > 0
    ).mean() > 0.2  # random lights on random normals: a third are lit, enough to mean something


def test_evaluate_env_matches_reference(gpu) -> None:
    n = 2048
    i, ir = _inputs(n, 21)
    e, er = _env(n, 22)
    body = """
    let c = legacy_v2_evaluate_env(hs_inputs(base), hs_env(base + 24u));
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + ENV), np.concatenate([ir, er], -1), 3, n)
    np.testing.assert_allclose(out, ref.evaluate_env(i, e), rtol=1e-4, atol=1e-5)


def test_furnace_returns_one_plus_the_specular_albedo(gpu) -> None:
    """White environment, white dielectric, no lights: v2 returns 1 + (F0 * scale + bias), not 1.

    v2 never scales its diffuse by (1 - F), so the specular albedo is added on top of a full diffuse
    (a v2 characteristic, kept). The LUT is the E1 cook's; the excess depends on angle and roughness.
    """
    from hogshade.ibl.prefilter import brdf_lut

    n = 64
    rng = np.random.default_rng(5)
    rough = rng.uniform(0.05, 1.0, size=n)
    nv = rng.uniform(0.1, 1.0, size=n)
    lut = brdf_lut(32, 512).astype(np.float64)
    ix = np.clip((nv * 32).astype(int), 0, 31)
    iy = np.clip((rough * 32).astype(int), 0, 31)
    scale, bias = lut[iy, ix, 0], lut[iy, ix, 1]
    normal = np.tile([0.0, 0.0, 1.0], (n, 1))
    view = np.stack([np.sqrt(1 - nv * nv), np.zeros(n), nv], axis=-1)
    f0 = ref.f0_from_ior(np.full(n, 1.5))
    rows = np.zeros((n, INPUTS + ENV))
    rows[:, 0:3] = 1.0
    rows[:, 4] = rough
    rows[:, 5] = 1.0
    rows[:, 9:12] = normal
    rows[:, 12:15] = view
    rows[:, 18:21] = f0[:, None]
    rows[:, 21] = 1.0
    rows[:, 22] = 1.0
    rows[:, 23] = 1.0
    rows[:, 24:27] = 1.0
    rows[:, 27:30] = 1.0
    rows[:, 30] = scale
    rows[:, 31] = bias
    rows = _f32(rows)
    body = """
    let i0 = hs_inputs(base);
    let env = hs_env(base + 24u);
    let c = models_shade(i0, lighting_slots_empty(), env, HOGSHADE_DEBUG_NONE).color;
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + ENV), rows, 3, n)
    excess = f0 * scale + bias
    np.testing.assert_allclose(out, np.repeat(1.0 + excess[:, None], 3, axis=-1), rtol=1e-4, atol=1e-5)
    # measured: a few percent facing the camera, up to 0.57 at grazing where the LUT bias term dominates
    assert 0.0 < excess[nv > 0.7].max() < 0.1, excess[nv > 0.7].max()
    assert excess.max() < 0.7, excess.max()


@pytest.mark.parametrize("mode", range(33))
def test_debug_modes_are_finite_and_match_reference(gpu, mode: int) -> None:
    n = 128
    i, ir = _inputs(n, 31 + mode)
    lr = _lights(n, 32 + mode)
    e, er = _env(n, 33 + mode)
    body = f"""
    var slots = lighting_slots_empty();
    slots.light[0] = hs_light(base + 24u);
    slots.count = 1u;
    let c = legacy_v2_debug(hs_inputs(base), slots, hs_env(base + 40u), {mode}u);
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + LIGHT + ENV), np.concatenate([ir, lr, er], -1), 3, n)
    assert np.all(np.isfinite(out)), mode
    np.testing.assert_allclose(
        out, ref.debug(i, [lr], e, mode), rtol=1e-4, atol=1e-5, err_msg=ref.DEBUG_MODE_NAMES[mode]
    )


def test_shade_through_the_dispatcher_equals_the_model(gpu) -> None:
    n = 512
    i, ir = _inputs(n, 41)
    lr = _lights(n, 42)
    e, er = _env(n, 43)
    body = """
    var slots = lighting_slots_empty();
    slots.light[0] = hs_light(base + 24u);
    slots.count = 1u;
    let c = models_shade(hs_inputs(base), slots, hs_env(base + 40u), HOGSHADE_DEBUG_NONE).color;
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    out = gpu.run(_LOADERS + kernel(body, INPUTS + LIGHT + ENV), np.concatenate([ir, lr, er], -1), 3, n)
    np.testing.assert_allclose(out, ref.shade(i, [lr], e), rtol=1e-4, atol=1e-5)


@pytest.mark.parametrize("mode", sorted(ref.DEBUG_INPUTS_MODES))
def test_debug_inputs_modes_match_reference(gpu, mode: int) -> None:
    n = 256
    m, mr = _material(n, 51 + mode)
    s, sr = _samples(n, 52 + mode)
    g, gr = _geometry(n, 53 + mode)
    rng = np.random.default_rng(54 + mode)
    extra = np.zeros((n, 12))
    extra[:, 0:2] = rng.uniform(-0.5, 1.5, size=(n, 2))
    extra[:, 2] = rng.uniform(0.0, 1.0, size=n)
    extra[:, 3:6] = rng.uniform(0.0, 1.0, size=(n, 3))
    extra[:, 6:9] = rng.uniform(0.0, 1.0, size=(n, 3))
    extra[:, 9:12] = (0.0, 1.0, 0.0)
    extra = _f32(extra)
    body = f"""
    let e = base + 58u;
    let c = legacy_v2_debug_inputs(hs_material(base), hs_samples(base + 18u), hs_geometry(base + 35u),
        vec2<f32>(hs_in[e + 0u], hs_in[e + 1u]), hs_in[e + 2u],
        vec3<f32>(hs_in[e + 3u], hs_in[e + 4u], hs_in[e + 5u]), vec3<f32>(hs_in[e + 6u], hs_in[e + 7u], hs_in[e + 8u]),
        vec3<f32>(hs_in[e + 9u], hs_in[e + 10u], hs_in[e + 11u]), {mode}u);
    hs_out[i * 3u + 0u] = c.x; hs_out[i * 3u + 1u] = c.y; hs_out[i * 3u + 2u] = c.z;
    """
    rows = np.concatenate([mr, sr, gr, extra], -1)
    out = gpu.run(_LOADERS + kernel(body, MATERIAL + SAMPLES + GEOMETRY + 12), rows, 3, n)
    expect = ref.debug_inputs(m, s, g, extra[:, 0:2], extra[:, 2], extra[:, 3:6], extra[:, 6:9], extra[:, 9:12], mode)
    assert np.all(np.isfinite(out))
    np.testing.assert_allclose(out, expect, rtol=1e-5, atol=1e-6, err_msg=ref.DEBUG_MODE_NAMES[mode])
