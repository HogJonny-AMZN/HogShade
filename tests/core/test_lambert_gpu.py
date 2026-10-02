"""
HogShade: the Lambert model agrees with its NumPy twin for one light and the environment (the standards
pass, 2026-09-27).
Package: tests/core/test_lambert_gpu
"""

from __future__ import annotations

import numpy as np
from gpu_harness import kernel, unit_vectors

from hogshade.reference import lambert as ref

# row layout: base colour (3), ao (1), normal (3), view (3), position (3), light row (16), irradiance/pi (3) = 32
STRIDE = 32
N = 256


def _rows(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rows = np.zeros((N, STRIDE), dtype=np.float32)
    rows[:, 0:3] = rng.uniform(0.05, 1.0, size=(N, 3))
    rows[:, 3] = rng.uniform(0.2, 1.0, size=N)
    rows[:, 4:7] = unit_vectors(N, seed + 1)
    rows[:, 7:10] = unit_vectors(N, seed + 2)
    rows[:, 10:13] = rng.uniform(-2, 2, size=(N, 3))
    light = np.zeros((N, 16), dtype=np.float32)
    light[:, 0] = rng.integers(0, 4, size=N)  # includes kind 0, off
    light[:, 1:4] = rng.uniform(-4, 4, size=(N, 3))
    light[:, 4:7] = unit_vectors(N, seed + 3)
    light[:, 7] = rng.uniform(0.5, 4.0, size=N)
    light[:, 8:11] = rng.uniform(0.2, 1.0, size=(N, 3))
    light[:, 11] = rng.uniform(3.0, 12.0, size=N)
    light[:, 12] = 0.95
    light[:, 13] = 0.80
    light[:, 14] = rng.uniform(0.3, 1.0, size=N)
    rows[:, 13:29] = light
    rows[:, 29:32] = rng.uniform(0.0, 1.0, size=(N, 3))
    return rows


BODY = """
    let i0 = lambert_inputs(
        vec3<f32>(hs_in[base + 0u], hs_in[base + 1u], hs_in[base + 2u]), hs_in[base + 3u], vec3<f32>(0.0),
        vec3<f32>(hs_in[base + 4u], hs_in[base + 5u], hs_in[base + 6u]),
        vec3<f32>(hs_in[base + 7u], hs_in[base + 8u], hs_in[base + 9u]),
        vec3<f32>(hs_in[base + 10u], hs_in[base + 11u], hs_in[base + 12u]));
    var l: LightSource;
    let lb = base + 13u;
    l.kind = u32(hs_in[lb + 0u]);
    l.position_ws = vec3<f32>(hs_in[lb + 1u], hs_in[lb + 2u], hs_in[lb + 3u]);
    l.direction_ws = vec3<f32>(hs_in[lb + 4u], hs_in[lb + 5u], hs_in[lb + 6u]);
    l.intensity = hs_in[lb + 7u];
    l.color = vec3<f32>(hs_in[lb + 8u], hs_in[lb + 9u], hs_in[lb + 10u]);
    l.range = hs_in[lb + 11u];
    l.cone_cos = vec2<f32>(hs_in[lb + 12u], hs_in[lb + 13u]);
    l.shadow = hs_in[lb + 14u];
    l._pad = 0.0;
    var env = environment_samples_none();
    env.irradiance_over_pi = vec3<f32>(hs_in[base + 29u], hs_in[base + 30u], hs_in[base + 31u]);
    let o = i * 8u;
    let direct = lambert_evaluate_light(i0, l, env);
    hs_out[o + 0u] = direct.x; hs_out[o + 1u] = direct.y; hs_out[o + 2u] = direct.z;
    let ambient = lambert_evaluate_env(i0, env);
    hs_out[o + 3u] = ambient.x; hs_out[o + 4u] = ambient.y; hs_out[o + 5u] = ambient.z;
    let look = lambert_env_lookup(i0);
    hs_out[o + 6u] = look.x; hs_out[o + 7u] = look.y;
"""


def test_lambert_matches_the_reference(gpu) -> None:
    rows = _rows(5)
    out = gpu.run(kernel(BODY, STRIDE), rows, 8, N)
    base, ao = rows[:, 0:3].astype(np.float64), rows[:, 3].astype(np.float64)
    normal, view, position = (
        rows[:, 4:7].astype(np.float64),
        rows[:, 7:10].astype(np.float64),
        rows[:, 10:13].astype(np.float64),
    )
    light = rows[:, 13:29].astype(np.float64)
    expected_direct = ref.evaluate_light(base, normal, position, light)
    scale = np.maximum(np.abs(expected_direct), 1e-3)
    np.testing.assert_allclose(out[:, 0:3], expected_direct, rtol=0.0, atol=(2e-4 * scale).max())
    assert (light[:, 0] == 0).any() and (expected_direct[light[:, 0] == 0] == 0.0).all()
    np.testing.assert_allclose(
        out[:, 3:6], ref.evaluate_env(base, ao, rows[:, 29:32].astype(np.float64)), rtol=1e-5, atol=1e-6
    )
    np.testing.assert_allclose(out[:, 6:8], ref.env_lookup(normal, view), rtol=1e-5, atol=1e-6)
