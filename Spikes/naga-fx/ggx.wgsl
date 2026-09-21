// HogShade phase 2 spike (plan PR A, task 2): can naga's HLSL of a WGSL module live inside a Maya
// dx11Shader effect? This file is the "core" side and follows the spec's rule that the core
// declares no bindings: the texture, sampler and light arrive as function parameters, and the
// host shell declares them with Maya annotations and passes them in.
//
// First finding (2026-09-20): with @group/@binding globals, naga 30 emits samplers through a
// "sampler heap" (`nagaSamplerHeap[2048] : register(s0, space0)` plus an index buffer in
// space255), which is shader-model 5.1 syntax an fx_5_0 effect cannot bind. Passing handles as
// parameters avoids the heap entirely.
//
// Arithmetic under test: GGX D, height-correlated Smith visibility, Schlick Fresnel, one function
// that combines them for a single light. Integration under test: spike_shade() samples the base
// colour through a caller-supplied texture and sampler and reads a caller-supplied light.

const SPIKE_PI: f32 = 3.14159265358979;

struct SpikeLight {
    direction_ws: vec3<f32>,   // unit, towards the light
    intensity: f32,
    color: vec3<f32>,
    _pad: f32,
};

fn brdf_ggx_d(n_dot_h: f32, alpha: f32) -> f32 {
    let a2 = alpha * alpha;
    let d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0;
    return a2 / (SPIKE_PI * d * d);
}

fn brdf_smith_v(n_dot_v: f32, n_dot_l: f32, alpha: f32) -> f32 {
    let a2 = alpha * alpha;
    let gv = n_dot_l * sqrt(n_dot_v * n_dot_v * (1.0 - a2) + a2);
    let gl = n_dot_v * sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2);
    return 0.5 / max(gv + gl, 1e-5);
}

fn brdf_fresnel_schlick(f0: vec3<f32>, v_dot_h: f32) -> vec3<f32> {
    let fc = pow(1.0 - v_dot_h, 5.0);
    return f0 + (vec3<f32>(1.0) - f0) * fc;
}

fn brdf_specular(n: vec3<f32>, v: vec3<f32>, l: vec3<f32>, f0: vec3<f32>, roughness: f32) -> vec3<f32> {
    let h = normalize(v + l);
    let n_dot_l = max(dot(n, l), 0.0);
    let n_dot_v = max(dot(n, v), 1e-4);
    let n_dot_h = max(dot(n, h), 0.0);
    let v_dot_h = max(dot(v, h), 0.0);
    let alpha = max(roughness * roughness, 1e-3);
    let d = brdf_ggx_d(n_dot_h, alpha);
    let vis = brdf_smith_v(n_dot_v, n_dot_l, alpha);
    let f = brdf_fresnel_schlick(f0, v_dot_h);
    return d * vis * f * n_dot_l;
}

// The integration function: texture, sampler and light are parameters, owned by the host.
fn spike_shade(
    base_color_tex: texture_2d<f32>,
    base_color_sampler: sampler,
    light: SpikeLight,
    n: vec3<f32>,
    v: vec3<f32>,
    uv: vec2<f32>,
    roughness: f32,
    metalness: f32,
) -> vec3<f32> {
    let base = textureSample(base_color_tex, base_color_sampler, uv).rgb;
    let f0 = mix(vec3<f32>(0.04), base, metalness);
    let l = normalize(light.direction_ws);
    let n_dot_l = max(dot(n, l), 0.0);
    let diffuse = base * (1.0 - metalness) / SPIKE_PI * n_dot_l;
    let specular = brdf_specular(n, v, l, f0, roughness);
    return (diffuse + specular) * light.color * light.intensity;
}

// naga wants a module with an entry point. This one touches no bindings so it emits nothing an
// effect cannot swallow; the .fx shell provides the real pixel shader and calls spike_shade.
@fragment
fn spike_fs(@location(0) normal_ws: vec3<f32>) -> @location(0) vec4<f32> {
    let n = normalize(normal_ws);
    let s = brdf_specular(n, n, n, vec3<f32>(0.04), 0.5);
    return vec4<f32>(s, 1.0);
}
