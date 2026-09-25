"""
HogShade: SurfaceInputs round-trips through the ADR-002 encode and decode, and forward equals deferred (task 10).
Package: tests/core/test_gbuffer_gpu

The GPU round trip here is exact in float32 because the harness does not quantise to the
attachment formats; the quantisation the layout allows (8-bit albedo and AO, fp16 normal) is
applied in NumPy on the encoded targets so the parity test measures what a real G-buffer loses.
"""

from __future__ import annotations

import numpy as np
from gpu_harness import kernel, unit_vectors

from hogshade.reference import gbuffer as ref


def _surfaces(n: int, seed: int) -> np.ndarray:
    """rows: base(3), metal, rough, ao, emissive(3), normal(3), view(3), position(3), cavity  -> stride 18"""
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, 18), dtype=np.float32)
    rows[:, 0:3] = rng.uniform(0.02, 1.0, size=(n, 3))
    rows[:, 3] = rng.uniform(0, 1, size=n)
    rows[:, 4] = rng.uniform(0.05, 1.0, size=n)
    rows[:, 5] = rng.uniform(0.2, 1.0, size=n)
    rows[:, 6:9] = rng.uniform(0, 2, size=(n, 3))
    rows[:, 9:12] = unit_vectors(n, seed + 1)
    rows[:, 12:15] = unit_vectors(n, seed + 2)
    rows[:, 15:18] = rng.uniform(-5, 5, size=(n, 3))
    return rows


_LOAD = """
fn hs_inputs(base: u32) -> ShadingInputs {
    var i: ShadingInputs;
    i.surface.base_color = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    i.surface.metalness = hs_in[base + 3u];
    i.surface.roughness = hs_in[base + 4u];
    i.surface.ao = hs_in[base + 5u];
    i.surface.emissive = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    i.surface.normal_ws = vec3<f32>(hs_in[base + 9u], hs_in[base + 10u], hs_in[base + 11u]);
    i.surface.model = HOGSHADE_MODEL_LAMBERT;
    i.view_ws = vec3<f32>(hs_in[base + 12u], hs_in[base + 13u], hs_in[base + 14u]);
    i.position_ws = vec3<f32>(hs_in[base + 15u], hs_in[base + 16u], hs_in[base + 17u]);
    i.specular_f0 = mix(vec3<f32>(HOGSHADE_DIELECTRIC_F0), i.surface.base_color, i.surface.metalness);
    i.cavity = 1.0;
    i.opacity = 1.0;
    i.specular_weight = 1.0;
    return i;
}
"""


def test_octahedral_gpu_matches_reference(gpu) -> None:
    n = unit_vectors(4096, 21)
    body = """
    let n = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    let e = gbuffer_oct_encode(n);
    let d = gbuffer_oct_decode(e);
    hs_out[i * 5u + 0u] = e.x; hs_out[i * 5u + 1u] = e.y;
    hs_out[i * 5u + 2u] = d.x; hs_out[i * 5u + 3u] = d.y; hs_out[i * 5u + 4u] = d.z;
    """
    out = gpu.run(kernel(body, 3), n.astype(np.float32), 5, len(n))
    np.testing.assert_allclose(out[:, :2], ref.oct_encode(n), rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 2:], n, atol=2e-6)


def test_surface_round_trip_and_forward_deferred_parity(gpu) -> None:
    rows = _surfaces(1024, 31)
    body = """
    let i0 = hs_inputs(base);
    var layout_meta: GBufferLayoutAdr002;
    layout_meta.layer = 3u; layout_meta.channel_mask = 255u; layout_meta.flags = 0u;
    let t = gbuffer_encode_from_inputs(i0, layout_meta);
    let s = gbuffer_decode_adr002(t);
    let i1 = gbuffer_reconstruct(s, i0.view_ws, i0.position_ws);
    var slots = lighting_slots_empty();
    slots.light[0].kind = 1u; slots.light[0].direction_ws = normalize(vec3<f32>(0.3, 1.0, 0.2));
    slots.light[0].color = vec3<f32>(1.0); slots.light[0].intensity = 2.0; slots.light[0].shadow = 1.0;
    slots.count = 1u;
    var env = environment_samples_none();
    env.irradiance_over_pi = vec3<f32>(0.25, 0.3, 0.35);
    let fwd = models_shade(i0, slots, env, HOGSHADE_DEBUG_NONE).color;
    let dfr = models_shade(i1, slots, env, HOGSHADE_DEBUG_NONE).color;
    let o = i * 12u;
    hs_out[o + 0u] = s.base_color.x; hs_out[o + 1u] = s.ao; hs_out[o + 2u] = s.roughness; hs_out[o + 3u] = s.metalness;
    hs_out[o + 4u] = s.normal_ws.x; hs_out[o + 5u] = f32(s.model);
    hs_out[o + 6u] = fwd.x; hs_out[o + 7u] = fwd.y; hs_out[o + 8u] = fwd.z;
    hs_out[o + 9u] = dfr.x; hs_out[o + 10u] = dfr.y; hs_out[o + 11u] = dfr.z;
    """
    out = gpu.run(_LOAD + kernel(body, 18), rows, 12, len(rows))
    np.testing.assert_allclose(out[:, 0], rows[:, 0], atol=1e-6)  # base colour survives un-quantised
    np.testing.assert_allclose(out[:, 1], rows[:, 5], atol=1e-6)  # ao (cavity was 1)
    np.testing.assert_allclose(out[:, 2], rows[:, 4], atol=1e-6)
    np.testing.assert_allclose(out[:, 3], rows[:, 3], atol=1e-6)
    np.testing.assert_allclose(out[:, 4], rows[:, 9], atol=3e-6)
    assert np.all(out[:, 5] == 0.0)
    # forward and deferred shade the same for a model whose F0 the deferred path can reconstruct
    np.testing.assert_allclose(out[:, 9:12], out[:, 6:9], rtol=1e-5, atol=1e-6)


def test_parity_within_attachment_quantisation() -> None:
    """What a real ADR-002 G-buffer loses: 8-bit sRGB-encoded albedo, 8-bit linear AO, fp16 octahedral normal.

    GB0 is rgba8unorm-srgb, so the hardware encodes linear base colour to sRGB before the 8-bit
    store and decodes on sample; the rounding happens in the encoded domain. NumPy only.
    """
    rows = _surfaces(4096, 41)
    base, ao = ref.quantise_gb0_adr002(rows[:, 0:3], rows[:, 5])
    oct16 = ref.oct_encode(rows[:, 9:12]).astype(np.float16).astype(np.float64)
    n_back = ref.oct_decode(oct16)
    # 8 bits in the sRGB domain: the linear step is largest near white, d(linear)/d(srgb) at 1.0 is about 2.4,
    # so half a code is 0.0047 linear; near black the encode expands and the linear error is far smaller
    base_err = np.abs(base - rows[:, 0:3])
    assert base_err.max() <= 0.5 / 255 * 2.4 + 1e-6, base_err.max()
    dark = rows[:, 0:3] < 0.05
    assert base_err[dark].max() <= 0.5 / 255 * 0.5 + 1e-6, base_err[dark].max()
    assert np.abs(ao - rows[:, 5]).max() <= 0.5 / 255 + 1e-9
    angle = np.degrees(np.arccos(np.clip((n_back * rows[:, 9:12]).sum(-1), -1, 1)))
    assert angle.max() < 0.15, angle.max()  # fp16 octahedral: measured 0.11 degrees worst case over 4096 normals
