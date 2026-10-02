"""
HogShade: the texture-free environment functions agree with their NumPy twins (the standards pass, 2026-09-27).
Package: tests/core/test_environment_gpu
"""

from __future__ import annotations

import numpy as np
from gpu_harness import kernel, unit_vectors

from hogshade.reference import environment as ref

# row layout: sh9 as 9 vec4 (36), normal (3), exposure (1), sky (3), ground (3), up (3) = 49
STRIDE = 49
N = 256


def _rows(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rows = np.zeros((N, STRIDE), dtype=np.float32)
    sh9 = rng.normal(size=(N, 9, 3)) * np.array([1.0, 0.4, 0.4, 0.4, 0.2, 0.2, 0.2, 0.2, 0.2])[None, :, None]
    sh9[:, 0] += 2.0  # a positive dc keeps most rows above the clamp, a few below
    rows[:, 0:36] = np.concatenate([sh9, np.zeros((N, 9, 1))], axis=-1).reshape(N, 36)
    rows[:, 36:39] = unit_vectors(N, seed + 1)
    rows[:, 39] = rng.uniform(0.5, 2.0, size=N)
    rows[:, 40:43] = rng.uniform(0.0, 1.0, size=(N, 3))
    rows[:, 43:46] = rng.uniform(0.0, 1.0, size=(N, 3))
    rows[:, 46:49] = unit_vectors(N, seed + 2)
    rows[::4, 46:49] *= 1.7  # a host may pass a non-unit up; the shader does not normalise, nor may the twin
    return rows


BODY = """
    var env = environment_default(1.0);
    env.exposure = hs_in[base + 39u];
    for (var k = 0u; k < 9u; k = k + 1u) {
        env.sh9[k] = vec4<f32>(
            hs_in[base + k * 4u], hs_in[base + k * 4u + 1u], hs_in[base + k * 4u + 2u], hs_in[base + k * 4u + 3u]
        );
    }
    let n = vec3<f32>(hs_in[base + 36u], hs_in[base + 37u], hs_in[base + 38u]);
    let sky = vec3<f32>(hs_in[base + 40u], hs_in[base + 41u], hs_in[base + 42u]);
    let ground = vec3<f32>(hs_in[base + 43u], hs_in[base + 44u], hs_in[base + 45u]);
    let up = vec3<f32>(hs_in[base + 46u], hs_in[base + 47u], hs_in[base + 48u]);
    let o = i * 18u;
    let e = environment_irradiance_sh9(env, n);
    hs_out[o + 0u] = e.x; hs_out[o + 1u] = e.y; hs_out[o + 2u] = e.z;
    let d = environment_hemisphere(sky, ground, n, up);
    hs_out[o + 3u] = d.x; hs_out[o + 4u] = d.y; hs_out[o + 5u] = d.z;
    let none = environment_samples_none();
    hs_out[o + 6u] = none.brdf.x; hs_out[o + 7u] = none.brdf.y;
    hs_out[o + 8u] = none.irradiance_over_pi.x;
    hs_out[o + 9u] = none.irradiance_over_pi.y;
    hs_out[o + 10u] = none.irradiance_over_pi.z;
    hs_out[o + 11u] = none.specular.x; hs_out[o + 12u] = none.specular.y; hs_out[o + 13u] = none.specular.z;
    hs_out[o + 14u] = none.hemisphere.x; hs_out[o + 15u] = none.hemisphere.y; hs_out[o + 16u] = none.hemisphere.z;
    hs_out[o + 17u] = f32(none.hemisphere_mode);
"""


def test_sh9_irradiance_and_hemisphere_match_the_reference(gpu) -> None:
    rows = _rows(11)
    out = gpu.run(kernel(BODY, STRIDE), rows, 18, N)
    sh9 = rows[:, 0:36].reshape(N, 9, 4)[:, :, :3].astype(np.float64)
    n = rows[:, 36:39].astype(np.float64)
    expected_e = ref.irradiance_sh9(sh9, n, rows[:, 39].astype(np.float64))
    np.testing.assert_allclose(out[:, 0:3], expected_e, rtol=2e-5, atol=1e-5)
    assert (expected_e == 0.0).any(), "the clamp is exercised by at least one row"
    expected_d = ref.hemisphere(rows[:, 40:43], rows[:, 43:46], n, rows[:, 46:49])
    np.testing.assert_allclose(out[:, 3:6], expected_d, rtol=1e-5, atol=1e-6)
    none = ref.samples_none()
    np.testing.assert_allclose(out[:, 6:8], np.tile(none["brdf"], (N, 1)), atol=0.0)
    np.testing.assert_array_equal(out[:, 8:11], np.tile(none["irradiance_over_pi"], (N, 1)))
    np.testing.assert_array_equal(out[:, 11:14], np.tile(none["specular"], (N, 1)))
    np.testing.assert_array_equal(out[:, 14:17], np.tile(none["hemisphere"], (N, 1)))
    np.testing.assert_array_equal(out[:, 17], np.full(N, float(none["hemisphere_mode"])))
    assert (np.linalg.norm(rows[:, 46:49], axis=-1) > 1.5).any(), "a non-unit up vector is in the set"
