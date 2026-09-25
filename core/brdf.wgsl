// HogShade core: the BRDF toolbox every model draws from. Pure functions of angles and parameters;
// no textures, no lights. NumPy twins in hogshade/reference/brdf.py; the GPU harness compares them.
//
// Conventions: n, v, l, h are unit vectors; n_dot_x are clamped by the caller unless stated;
// roughness is perceptual and alpha = roughness squared (after HOGSHADE_ROUGHNESS_BIAS where a
// model applies it). Radiance-scale results: multiply by the light's radiance and n_dot_l outside.

// GGX / Trowbridge-Reitz normal distribution.
fn brdf_ggx_d(n_dot_h: f32, alpha: f32) -> f32 {
    let a2 = alpha * alpha;
    let d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0;
    return a2 / (HOGSHADE_PI * d * d);
}

// Height-correlated Smith visibility, V = G / (4 n.l n.v), so specular = D * V * F * n.l.
fn brdf_smith_v_height_correlated(n_dot_v: f32, n_dot_l: f32, alpha: f32) -> f32 {
    let a2 = alpha * alpha;
    let gv = n_dot_l * sqrt(n_dot_v * n_dot_v * (1.0 - a2) + a2);
    let gl = n_dot_v * sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2);
    return 0.5 / max(gv + gl, 1e-5);
}

// Schlick Fresnel with a colour F0.
fn brdf_fresnel_schlick(f0: vec3<f32>, v_dot_h: f32) -> vec3<f32> {
    let fc = pow(1.0 - v_dot_h, 5.0);
    return f0 + (vec3<f32>(1.0) - f0) * fc;
}

// F82-tint Fresnel for metals (Kutz et al., as in OpenPBR): Schlick plus a correction that lets
// the edge tint drop below one at the 82-degree "F82" angle. tint = 1 reduces to Schlick.
fn brdf_fresnel_f82(f0: vec3<f32>, tint: vec3<f32>, v_dot_h: f32) -> vec3<f32> {
    let mu = clamp(v_dot_h, 0.0, 1.0);
    let mu_bar = 1.0 / 7.0;
    let denom = mu_bar * pow(1.0 - mu_bar, 6.0);
    let f_schlick_bar = f0 + (vec3<f32>(1.0) - f0) * pow(1.0 - mu_bar, 5.0);
    let a = (f_schlick_bar - f_schlick_bar * tint) / max(denom, 1e-6);
    let f_schlick = f0 + (vec3<f32>(1.0) - f0) * pow(1.0 - mu, 5.0);
    return max(f_schlick - a * mu * pow(1.0 - mu, 6.0), vec3<f32>(0.0));
}

// Schlick-GGX G1 with a free k (Hable's G1V): 1 / (n.x (1 - k) + k).
fn brdf_g1_schlick_ggx(n_dot_x: f32, k: f32) -> f32 {
    return 1.0 / max(n_dot_x * (1.0 - k) + k, 1e-5);
}

// Hable's visibility: G1V(n.l) G1V(n.v) with k = alpha / 2, the "vis" of the legacy v2 GGX.
fn brdf_vis_hable(n_dot_l: f32, n_dot_v: f32, alpha: f32) -> f32 {
    let k = alpha * 0.5;
    return brdf_g1_schlick_ggx(n_dot_l, k) * brdf_g1_schlick_ggx(n_dot_v, k);
}

// Lambert diffuse: albedo / pi. The n.l is applied by the caller.
fn brdf_lambert(albedo: vec3<f32>) -> vec3<f32> {
    return albedo * HOGSHADE_INV_PI;
}

// Burley (Disney) diffuse with the roughness-driven retro-reflection lobe.
fn brdf_burley(albedo: vec3<f32>, roughness: f32, n_dot_v: f32, n_dot_l: f32, v_dot_h: f32) -> vec3<f32> {
    let fd90 = 0.5 + 2.0 * roughness * v_dot_h * v_dot_h;
    let light_scatter = 1.0 + (fd90 - 1.0) * pow(1.0 - n_dot_l, 5.0);
    let view_scatter = 1.0 + (fd90 - 1.0) * pow(1.0 - n_dot_v, 5.0);
    return albedo * HOGSHADE_INV_PI * light_scatter * view_scatter;
}

// The composite most models use: GGX with height-correlated Smith and Schlick, times n.l.
fn brdf_specular_ggx(n: vec3<f32>, v: vec3<f32>, l: vec3<f32>, f0: vec3<f32>, roughness: f32) -> vec3<f32> {
    let h = normalize(v + l);
    let n_dot_l = max(dot(n, l), 0.0);
    let n_dot_v = max(dot(n, v), 1e-4);
    let n_dot_h = max(dot(n, h), 0.0);
    let v_dot_h = max(dot(v, h), 0.0);
    let alpha = max((roughness + HOGSHADE_ROUGHNESS_BIAS) * (roughness + HOGSHADE_ROUGHNESS_BIAS), 1e-4);
    let d = brdf_ggx_d(n_dot_h, alpha);
    let vis = brdf_smith_v_height_correlated(n_dot_v, n_dot_l, alpha);
    let f = brdf_fresnel_schlick(f0, v_dot_h);
    return d * vis * f * n_dot_l;
}
