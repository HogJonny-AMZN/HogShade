// HogShade core, model 1: the 2015 legacy v1 shading (legacy/v1.0/mayaVP2_pbrBRDF.fx, bigdBRDF.fxh,
// functions_structs.fxh), ported function by function. NumPy twin in hogshade/reference/legacy_v1.py;
// tests/core/test_legacy_v1_gpu.py compares them on the GPU.
//
// What v1 actually was, from the record: one Disney "principled" BRDF (the BRDF explorer's
// disney.brdf: Burley diffuse with the Hanrahan-Krueger subsurface blend, anisotropic GTR2
// specular, sheen, a GTR1 clearcoat) evaluated for one light (slot 0, always as a point light at
// its position) and for an ambient dome as the same BRDF with the light along the normal, plus
// RGBM diffuse and specular environment cubes. The Cook-Torrance and "game" BRDF includes in the
// legacy folder were never included by the effect and could not have compiled; they are not v1.
//
// v1 characteristics kept verbatim (they are the look, not bugs):
//   - the specular accumulator is a float, so of the vec3 specular term only the red channel
//     survives (Gs * Fs * Ds and the clearcoat); the direct specular is that scalar times specular
//     amount, uncoloured;
//   - direct light: (diffuse + specular * specular_amount) * light colour * intensity * falloff,
//     with the diffuse already multiplied by (1 - metalness) and NdotL inside the BRDF;
//   - the split-sum lookup uses NdotV = -saturate(n.v): the LUT is always read at its u = 0 column
//     (legacy_v1_env_lookup returns exactly that);
//   - environment specular: prefiltered radiance * (mix(0.04, albedo, metalness) * lut.x + lut.y)
//     * specular amount; environment diffuse: albedo * (1 - metalness) * irradiance;
//   - the ambient dome is the Disney diffuse with L = N times the dome colour;
//   - ambient, environment diffuse and environment specular are multiplied by AO; the direct
//     light is not;
//   - the Disney roughness alpha is roughness squared, no bias; the clearcoat alpha is
//     mix(0.1, 0.001, clearcoat_gloss); the Disney G uses alpha_g = (alpha / 2 + 1 / 2)^2.
//
// Deviations from v1 (each also in Docs/design/2026-09-20-modernization-direction.md):
//   1. Environment: E1 linear cubes and LUT replace RGBM 8-bit cubes; the eight-mip constant, the
//      exposure and gamma parameters are gone; hosts pass linear values.
//   2. Lights: any number of slots and any kind through lighting.wgsl (v1 used slot 0 only, as a
//      point light with a power-law decay 1 / d^k); the core's falloff and cone apply.
//   3. Unbound maps: the host passes defaults, as for v2.
//   4. Vertex-colour AO uses the red channel: surface.ao is a scalar (v1 multiplied rgb).
//   5. In-shader display gamma and the filmic tone map are host concerns and are gone.
//   6. The dead Cook-Torrance and "game" includes are not ported; the "game" GGX is the v2 model's
//      lobe already in the toolbox.

// The material's parameters, linear. Flags are u32: 0 off, anything else on.
struct legacy_v1_Material {
    base_color: vec3<f32>,
    metalness: f32,
    subsurface: f32,
    specular: f32,              // the Disney "specular" 0..1 (0.08 * this is the dielectric F0 at 1)
    roughness: f32,
    specular_tint: f32,
    anisotropic: f32,
    sheen: f32,
    sheen_tint: f32,
    clearcoat: f32,
    clearcoat_gloss: f32,
    use_vertex_color_ao: u32,
    has_alpha: u32,
    use_vertex_alpha: u32,
    use_cutout_alpha: u32,
    flip_backface_normals: u32,
    rough_is_gloss: u32,        // 1: the roughness map stores gloss and is inverted
    use_specular_mask: u32,     // 1: the specular map's alpha is the amount, else its red
    normal_flip: vec3<f32>,     // +1 or -1 per tangent-space axis
}

// Texel values the host sampled, linear, or the unbound defaults.
struct legacy_v1_Samples {
    base_color: vec4<f32>,      // the map texel when use_base_map (v1 replaces the parameter with the map, never multiplies)
    specular: vec4<f32>,        // x amount (a when use_specular_mask); default (1, 1, 1, 1)
    roughness: f32,             // green of the map; default the roughness parameter (host passes it)
    metalness: f32,             // green of the map; default the metalness parameter
    ao: vec3<f32>,              // default 1
    normal_ts: vec3<f32>,       // decoded, texel * 2 - 1; default (0, 0, 1)
    use_base_map: u32,          // v1 replaces, so the host says which value applies
    use_specular_map: u32,
    use_roughness_map: u32,
    use_metalness_map: u32,
    use_normal_map: u32,
}

// Per-fragment geometry from the vertex stage.
struct legacy_v1_Geometry {
    normal_ws: vec3<f32>,
    tangent_ws: vec3<f32>,
    binormal_ws: vec3<f32>,     // cross(n, t) * handedness, as v1 built it
    view_ws: vec3<f32>,
    position_ws: vec3<f32>,
    vertex_color: vec4<f32>,
    front_face: u32,
}

fn legacy_v1_flag(f: u32) -> bool {
    return f != 0u;
}

fn legacy_v1_luminance(c: vec3<f32>) -> f32 {
    return 0.3 * c.x + 0.6 * c.y + 0.1 * c.z;
}

// The material half: v1's texture stage, from sampled values to ShadingInputs. specular_f0 carries
// Cspec0; specular_weight the specular amount; the Disney lobe parameters ride in model_params.
fn legacy_v1_inputs(m: legacy_v1_Material, s: legacy_v1_Samples, g: legacy_v1_Geometry) -> ShadingInputs {
    var i: ShadingInputs;
    var albedo = m.base_color;
    if (legacy_v1_flag(s.use_base_map)) {
        albedo = s.base_color.rgb;
    }
    var spec_a = m.specular;
    if (legacy_v1_flag(s.use_specular_map)) {
        spec_a = select(s.specular.x, s.specular.a, legacy_v1_flag(m.use_specular_mask));
    }
    var rough_a = m.roughness;
    if (legacy_v1_flag(s.use_roughness_map)) {
        rough_a = select(1.0 - s.roughness, s.roughness, legacy_v1_flag(m.rough_is_gloss));
    }
    var metal_a = m.metalness;
    if (legacy_v1_flag(s.use_metalness_map)) {
        metal_a = s.metalness;
    }
    var ao = s.ao;
    if (legacy_v1_flag(m.use_vertex_color_ao)) {
        ao = ao * g.vertex_color.rgb;
    }
    var opacity = 1.0;
    if (legacy_v1_flag(m.use_cutout_alpha)) {
        if (legacy_v1_flag(m.has_alpha)) {
            opacity = s.base_color.a;
        }
        if (legacy_v1_flag(m.use_vertex_alpha)) {
            opacity = opacity * g.vertex_color.a;
        }
    }
    // normal: v1 flips the geometric normal on back faces, then applies the map through (T, B, N)
    var n = normalize(g.normal_ws);
    if (legacy_v1_flag(m.flip_backface_normals) && !legacy_v1_flag(g.front_face)) {
        n = -n;
    }
    let t = normalize(g.tangent_ws);
    let b = g.binormal_ws;
    if (legacy_v1_flag(s.use_normal_map)) {
        let raw = s.normal_ts * m.normal_flip;
        n = normalize(raw.x * t + raw.y * b + raw.z * n);
    }
    // Cspec0 as the BRDF computes it, so evaluate() can read it from specular_f0
    let lum = legacy_v1_luminance(albedo);
    var ctint = vec3<f32>(1.0);
    if (lum > 0.0) {
        ctint = albedo / lum;
    }
    let cspec0 = mix(spec_a * 0.08 * mix(vec3<f32>(1.0), ctint, m.specular_tint), albedo, metal_a);

    i.surface.base_color = albedo;
    i.surface.metalness = metal_a;
    i.surface.roughness = rough_a;
    i.surface.ao = ao.x;                     // deviation 4
    i.surface.emissive = vec3<f32>(0.0);     // v1 had no emissive
    i.surface.normal_ws = n;
    i.surface.model = HOGSHADE_MODEL_LEGACY_V1;
    i.view_ws = normalize(g.view_ws);
    i.position_ws = g.position_ws;
    i.specular_f0 = cspec0;
    i.cavity = 1.0;
    i.opacity = opacity;
    i.specular_weight = spec_a;
    i.tangent_ws = t;
    i.binormal_ws = b;
    i.model_params_a = vec4<f32>(m.subsurface, m.specular_tint, m.anisotropic, m.sheen);
    i.model_params_b = vec4<f32>(m.sheen_tint, m.clearcoat, m.clearcoat_gloss, 0.0);
    return i;
}

// v1's lookup: NdotV = -saturate(v.n), a sign bug kept as the record (the LUT reads its u = 0
// column); the roughness is raw (v1 used roughA for both the mip and the LUT).
fn legacy_v1_env_lookup(i: ShadingInputs) -> vec2<f32> {
    return vec2<f32>(-clamp(dot(i.view_ws, i.surface.normal_ws), 0.0, 1.0), i.surface.roughness);
}

// The two accumulators of v1's lightOutD: the diffuse colour and the scalar specular.
struct legacy_v1_Terms {
    color: vec3<f32>,
    specular: f32,
}

// dBRDF from bigdBRDF.fxh: Disney principled, one light direction, in the tangent frame (X, Y).
fn legacy_v1_dbrdf(i: ShadingInputs, l: vec3<f32>) -> legacy_v1_Terms {
    var t: legacy_v1_Terms;
    t.color = vec3<f32>(0.0);
    t.specular = 0.0;
    let n = i.surface.normal_ws;
    let v = i.view_ws;
    let x = i.tangent_ws;
    let y = i.binormal_ws;
    let subsurface = i.model_params_a.x;
    let anisotropic = i.model_params_a.z;
    let sheen = i.model_params_a.w;
    let sheen_tint = i.model_params_b.x;
    let clearcoat = i.model_params_b.y;
    let clearcoat_gloss = i.model_params_b.z;

    let alpha = i.surface.roughness * i.surface.roughness;
    let h = normalize(l + v);
    let n_dot_l = clamp(dot(n, l), 0.0, 1.0);
    let n_dot_v = clamp(dot(n, v), 0.0, 1.0);
    let n_dot_h = clamp(dot(n, h), 0.0, 1.0);
    let l_dot_h = clamp(dot(l, h), 0.0, 1.0);

    let cdlin = i.surface.base_color;
    let cdlum = legacy_v1_luminance(cdlin);
    var ctint = vec3<f32>(1.0);
    if (cdlum > 0.0) {
        ctint = cdlin / cdlum;
    }
    let cspec0 = i.specular_f0;
    let csheen = mix(vec3<f32>(1.0), ctint, sheen_tint);

    // diffuse: Burley with the Hanrahan-Krueger subsurface blend
    let fl = brdf_schlick_weight(n_dot_l);
    let fv = brdf_schlick_weight(n_dot_v);
    let fd90 = 0.5 + 2.0 * l_dot_h * l_dot_h * alpha;
    let fd = mix(1.0, fd90, fl) * mix(1.0, fd90, fv);
    let fss90 = l_dot_h * l_dot_h * alpha;
    let fss = mix(0.999, fss90, fl) * mix(0.999, fss90, fv);
    let ss = 1.25 * (fss * (1.0 / (n_dot_l + n_dot_v + 0.0001) - 0.5) + 0.5);

    // specular: anisotropic GTR2, Schlick to white, the explorer's Smith G
    let aspect = sqrt(1.0 - anisotropic * 0.9);
    let ax = max(0.001, (alpha * alpha) / aspect);
    let ay = max(0.001, (alpha * alpha) * aspect);
    let ds = brdf_gtr2_aniso(n_dot_h, dot(h, x), dot(h, y), ax, ay);
    let fh = brdf_schlick_weight(l_dot_h);
    let fs = mix(cspec0, vec3<f32>(1.0), fh);
    let roughg = (alpha * 0.5 + 0.5) * (alpha * 0.5 + 0.5);
    let gs = brdf_smith_g_ggx_disney(n_dot_l, roughg) * brdf_smith_g_ggx_disney(n_dot_v, roughg);

    let fsheen = fh * sheen * csheen;

    // clearcoat: GTR1, fixed 4 percent F0, fixed 0.25 G roughness
    let dr = brdf_gtr1(n_dot_h, mix(0.1, 0.001, clearcoat_gloss));
    let fr = mix(0.04, 1.0, fh);
    let gr = brdf_smith_g_ggx_disney(n_dot_l, 0.25) * brdf_smith_g_ggx_disney(n_dot_v, 0.25);

    t.color = (HOGSHADE_INV_PI * mix(fd, ss, subsurface) * cdlin + fsheen) * (1.0 - i.surface.metalness) * n_dot_l;
    // the float accumulator: red channel of the vec3 specular, plus the scalar clearcoat
    let spec_rgb = gs * fs * ds;
    t.specular = (spec_rgb.x + 0.25 * clearcoat * gr * fr * dr) * n_dot_l;
    return t;
}

// Radiance from one light: v1's light0Total with the core's incident geometry.
fn legacy_v1_evaluate_light(i: ShadingInputs, light: LightSource, env: EnvironmentSamples) -> vec3<f32> {
    let inc = lighting_incident(light, i.position_ws);
    if (!inc.valid) {
        return vec3<f32>(0.0);
    }
    let t = legacy_v1_dbrdf(i, inc.l_ws);
    return (t.color + vec3<f32>(t.specular * i.specular_weight)) * lighting_radiance(light, inc);
}

// Ambient dome, environment diffuse and environment specular, all occluded by AO.
fn legacy_v1_evaluate_env(i: ShadingInputs, env: EnvironmentSamples) -> vec3<f32> {
    let albedo = i.surface.base_color;
    let metal = i.surface.metalness;
    // ambientDomeLight = dBRDF(N, V, N, ...): the diffuse term with the light along the normal
    let dome = legacy_v1_dbrdf(i, i.surface.normal_ws);
    let amb_total = dome.color * env.hemisphere;
    let diff_env = albedo * (1.0 - metal) * env.irradiance_over_pi;
    let cspec = mix(vec3<f32>(0.04), albedo, metal) * env.brdf.x + env.brdf.y;
    let spec_env = env.specular * cspec * i.specular_weight;
    return (amb_total + diff_env + spec_env) * i.surface.ao;
}

// v1's g_DebugMode 1..8 over slot 0's direction: NdotL, max(NdotL, 0), NdotV, H, NdotH, LdotH, VdotH,
// and the Hable visibility with k = max(0.001, roughness^2) / 2. Mode 0 is the shaded colour.
fn legacy_v1_debug(i: ShadingInputs, slots: FixedSlots16, env: EnvironmentSamples, mode: u32) -> vec3<f32> {
    if (mode == 0u) {
        var sum = vec3<f32>(0.0);
        let count = min(slots.count, 16u);
        for (var k = 0u; k < count; k = k + 1u) {
            sum = sum + legacy_v1_evaluate_light(i, slots.light[k], env);
        }
        return sum + legacy_v1_evaluate_env(i, env) + i.surface.emissive;
    }
    let n = i.surface.normal_ws;
    let v = i.view_ws;
    var l = vec3<f32>(0.0, 1.0, 0.0);
    if (slots.count > 0u) {
        let inc = lighting_incident(slots.light[0], i.position_ws);
        if (inc.valid) {
            l = inc.l_ws;
        }
    }
    let n_dot_l = dot(n, l);
    let n_dot_v = dot(n, v);
    let h = normalize(l + v);
    let a = max(0.001, i.surface.roughness * i.surface.roughness);
    let vis = brdf_vis_hable(n_dot_l, n_dot_v, a);
    var out = vec3<f32>(0.0);
    if (mode == 1u) { out = vec3<f32>(n_dot_l); }
    if (mode == 2u) { out = vec3<f32>(max(n_dot_l, 0.0)); }
    if (mode == 3u) { out = vec3<f32>(n_dot_v); }
    if (mode == 4u) { out = vec3<f32>(h.x); }
    if (mode == 5u) { out = vec3<f32>(dot(n, h)); }
    if (mode == 6u) { out = vec3<f32>(dot(l, h)); }
    if (mode == 7u) { out = vec3<f32>(dot(v, h)); }
    if (mode == 8u) { out = vec3<f32>(vis); }
    return out;
}
