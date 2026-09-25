"""
HogShade: core/brdf.wgsl on the GPU agrees with hogshade/reference/brdf.py (phase 2 plan, task 9).
Package: tests/core/test_brdf_gpu
"""

from __future__ import annotations

import numpy as np
from gpu_harness import kernel, unit_vectors

from hogshade.reference import brdf as ref


def _grid() -> np.ndarray:
    """(n_dot_h, n_dot_v, n_dot_l, v_dot_h, alpha, roughness) over a grid of angles and roughness."""
    # roughness from 0.05: below that the GGX peak (a2 / (pi d^2) with d -> 0) loses float32 digits
    # to cancellation in n_dot_h^2 (a2 - 1) + 1, which is a precision fact, not a shader fact
    cos = np.linspace(0.02, 1.0, 25)
    rough = np.linspace(0.05, 1.0, 12)
    nh, nv, r = np.meshgrid(cos, cos, rough, indexing="ij")
    nh, nv, r = nh.ravel(), nv.ravel(), r.ravel()
    nl = np.clip(nv[::-1], 0.02, 1.0)
    vh = np.clip((nh + nv) * 0.5, 0.02, 1.0)
    return np.stack([nh, nv, nl, vh, r * r, r], axis=-1).astype(np.float32).astype(np.float64)  # what the GPU sees


def test_ggx_d_smith_v_schlick_burley(gpu) -> None:
    g = _grid()
    f0 = np.tile(np.array([[0.04, 0.5, 0.9]]), (len(g), 1))
    inputs = np.concatenate([g, f0], axis=-1)  # stride 9
    body = """
    let n_dot_h = hs_in[base + 0u];
    let n_dot_v = hs_in[base + 1u];
    let n_dot_l = hs_in[base + 2u];
    let v_dot_h = hs_in[base + 3u];
    let alpha = hs_in[base + 4u];
    let rough = hs_in[base + 5u];
    let f0 = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    let o = i * 10u;
    hs_out[o + 0u] = brdf_ggx_d(n_dot_h, alpha);
    hs_out[o + 1u] = brdf_smith_v_height_correlated(n_dot_v, n_dot_l, alpha);
    let f = brdf_fresnel_schlick(f0, v_dot_h);
    hs_out[o + 2u] = f.x; hs_out[o + 3u] = f.y; hs_out[o + 4u] = f.z;
    let b = brdf_burley(f0, rough, n_dot_v, n_dot_l, v_dot_h);
    hs_out[o + 5u] = b.x; hs_out[o + 6u] = b.y; hs_out[o + 7u] = b.z;
    let lam = brdf_lambert(f0);
    hs_out[o + 8u] = lam.x; hs_out[o + 9u] = lam.y;
    """
    out = gpu.run(kernel(body, 9), inputs, 10, len(g))
    nh, nv, nl, vh, alpha, rough = g.T
    # GGX D: d = n_dot_h^2 (a2 - 1) + 1 cancels in float32 as a2 -> 0 (alpha 0.0025 at n_dot_h 1 leaves three
    # digits), so the tight tolerance applies where alpha >= 0.1 and a loose one everywhere else
    d_ref = ref.ggx_d(nh, alpha)
    well_conditioned = alpha >= 0.1
    np.testing.assert_allclose(out[well_conditioned, 0], d_ref[well_conditioned], rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 0], d_ref, rtol=1e-2, atol=1e-6)
    np.testing.assert_allclose(out[:, 1], ref.smith_v_height_correlated(nv, nl, alpha), rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 2:5], ref.fresnel_schlick(f0, vh), rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 5:8], ref.burley(f0, rough, nv, nl, vh), rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(out[:, 8:10], ref.lambert(f0)[:, :2], rtol=1e-6)


def test_fresnel_f82(gpu) -> None:
    vh = np.linspace(0.0, 1.0, 101)
    f0 = np.tile(np.array([[0.95, 0.64, 0.54]]), (len(vh), 1))  # copper-ish
    tint = np.tile(np.array([[1.0, 0.8, 0.6]]), (len(vh), 1))
    inputs = np.concatenate([vh[:, None], f0, tint], axis=-1)  # stride 7
    body = """
    let vh = hs_in[base + 0u];
    let f0 = vec3<f32>(hs_in[base + 1u], hs_in[base + 2u], hs_in[base + 3u]);
    let tint = vec3<f32>(hs_in[base + 4u], hs_in[base + 5u], hs_in[base + 6u]);
    let f = brdf_fresnel_f82(f0, tint, vh);
    hs_out[i * 3u + 0u] = f.x; hs_out[i * 3u + 1u] = f.y; hs_out[i * 3u + 2u] = f.z;
    """
    out = gpu.run(kernel(body, 7), inputs, 3, len(vh))
    np.testing.assert_allclose(out, ref.fresnel_f82(f0, tint, vh), rtol=2e-5, atol=1e-6)
    # tint of one reduces F82 to Schlick: on the GPU, against the Schlick reference, and in the reference itself
    ones = np.ones_like(tint)
    out_unity = gpu.run(kernel(body, 7), np.concatenate([vh[:, None], f0, ones], axis=-1), 3, len(vh))
    np.testing.assert_allclose(out_unity, ref.fresnel_schlick(f0, vh), rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(ref.fresnel_f82(f0, ones, vh), ref.fresnel_schlick(f0, vh), atol=1e-12)


def test_specular_ggx_composite(gpu) -> None:
    n = unit_vectors(2000, 1)
    v = unit_vectors(2000, 2)
    light = unit_vectors(2000, 3)
    # keep v and l in the hemisphere of n so n_dot_l > 0 for most samples
    v = np.where(((n * v).sum(-1) < 0)[:, None], -v, v)
    light = np.where(((n * light).sum(-1) < 0)[:, None], -light, light)
    rough = np.random.default_rng(4).uniform(0.05, 1.0, size=2000)
    f0 = np.tile(np.array([[0.04, 0.3, 0.9]]), (2000, 1))
    inputs = np.concatenate([n, v, light, f0, rough[:, None]], axis=-1)  # stride 13
    body = """
    let n = vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]);
    let v = vec3<f32>(hs_in[base + 3u], hs_in[base + 4u], hs_in[base + 5u]);
    let l = vec3<f32>(hs_in[base + 6u], hs_in[base + 7u], hs_in[base + 8u]);
    let f0 = vec3<f32>(hs_in[base + 9u], hs_in[base + 10u], hs_in[base + 11u]);
    let rough = hs_in[base + 12u];
    let s = brdf_specular_ggx(n, v, l, f0, rough);
    hs_out[i * 3u + 0u] = s.x; hs_out[i * 3u + 1u] = s.y; hs_out[i * 3u + 2u] = s.z;
    """
    out = gpu.run(kernel(body, 13), inputs, 3, 2000)
    expect = ref.specular_ggx(n, v, light, f0, rough)
    scale = np.abs(expect).max(axis=-1, keepdims=True) + 1e-3
    assert np.abs(out - expect).max() / scale.max() < 1e-4, np.abs(out - expect).max()
    np.testing.assert_allclose(out, expect, rtol=1e-3, atol=1e-5)
