"""
HogShade: sixteen bound slots sum to sixteen single-light calls; light geometry matches the reference (task 10).
Package: tests/core/test_lighting_gpu
"""

from __future__ import annotations

import numpy as np
from gpu_harness import kernel, unit_vectors


def _lights(n: int, seed: int) -> np.ndarray:
    """(count, 16) rows: kind, position(3), direction(3), intensity, color(3), range, cone_cos(2), shadow, pad."""
    rng = np.random.default_rng(seed)
    rows = np.zeros((n, 16), dtype=np.float32)
    rows[:, 0] = rng.integers(1, 4, size=n)
    rows[:, 1:4] = rng.uniform(-3, 3, size=(n, 3))
    rows[:, 4:7] = unit_vectors(n, seed + 1)
    rows[:, 7] = rng.uniform(0.5, 4.0, size=n)
    rows[:, 8:11] = rng.uniform(0.2, 1.0, size=(n, 3))
    rows[:, 11] = rng.uniform(4.0, 12.0, size=n)
    rows[:, 12] = 0.95
    rows[:, 13] = 0.80
    rows[:, 14] = rng.uniform(0.3, 1.0, size=n)
    return rows


_SLOT_FILL = """
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
"""


def test_slots_equal_sum_of_single_lights(gpu) -> None:
    lights = _lights(16, 7)
    # one surface point, lambert, evaluated per slot and as a slot set. input: 16 lights then the surface (7)
    surface = np.array([0.8, 0.6, 0.4, 0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # base colour, normal(3), padding
    inputs = np.concatenate([lights.reshape(-1), surface])
    body = """
    let i0 = lambert_inputs(vec3<f32>(hs_in[256u], hs_in[257u], hs_in[258u]), 1.0, vec3<f32>(0.0),
                            vec3<f32>(hs_in[259u], hs_in[260u], hs_in[261u]), vec3<f32>(0.0, 0.0, 1.0), vec3<f32>(0.0));
    var slots = lighting_slots_empty();
    for (var k = 0u; k < 16u; k = k + 1u) {
        slots.light[k] = hs_light(k * 16u);
    }
    slots.count = 16u;
    let env = environment_samples_none();
    let total = models_evaluate_slots(i0, slots, env);
    var single = vec3<f32>(0.0);
    for (var k = 0u; k < 16u; k = k + 1u) {
        single = single + models_evaluate_light(i0, hs_light(k * 16u), env);
    }
    hs_out[0u] = total.x; hs_out[1u] = total.y; hs_out[2u] = total.z;
    hs_out[3u] = single.x; hs_out[4u] = single.y; hs_out[5u] = single.z;
    """
    src = _SLOT_FILL + kernel(body, 263)
    out = gpu.run(src, inputs, 6, 1)[0]
    np.testing.assert_allclose(out[:3], out[3:], rtol=1e-6, atol=1e-7)
    assert out[:3].sum() > 0.0


def test_incident_geometry_matches_reference(gpu) -> None:
    lights = _lights(200, 11)
    points = np.random.default_rng(12).uniform(-2, 2, size=(200, 3)).astype(np.float32)
    inputs = np.concatenate([lights, points], axis=-1)  # stride 19
    body = """
    let l = hs_light(base);
    let p = vec3<f32>(hs_in[base + 16u], hs_in[base + 17u], hs_in[base + 18u]);
    let inc = lighting_incident(l, p);
    hs_out[i * 4u + 0u] = inc.l_ws.x; hs_out[i * 4u + 1u] = inc.l_ws.y; hs_out[i * 4u + 2u] = inc.l_ws.z;
    hs_out[i * 4u + 3u] = inc.attenuation;
    """
    out = gpu.run(_SLOT_FILL + kernel(body, 19), inputs, 4, 200)
    kind = lights[:, 0].astype(int)
    pos, direction = lights[:, 1:4], lights[:, 4:7]
    rng_ = lights[:, 11]
    inner, outer, shadow = lights[:, 12], lights[:, 13], lights[:, 14]
    to_light = pos - points
    dist = np.linalg.norm(to_light, axis=-1)
    l_ws = np.where((kind == 1)[:, None], direction, to_light / dist[:, None])
    falloff = 1.0 / np.maximum(dist * dist, 1e-8)
    ratio = dist / rng_
    window = np.clip(1.0 - ratio**4, 0.0, 1.0)
    falloff = falloff * window * window
    cos_angle = (-l_ws * direction).sum(-1)
    cone = np.clip((cos_angle - outer) / np.maximum(inner - outer, 1e-4), 0.0, 1.0) ** 2
    att = np.where(kind == 1, shadow, falloff * np.where(kind == 3, cone, 1.0) * shadow)
    np.testing.assert_allclose(out[:, :3], l_ws, rtol=1e-4, atol=1e-5)
    np.testing.assert_allclose(out[:, 3], att, rtol=2e-4, atol=1e-6)
