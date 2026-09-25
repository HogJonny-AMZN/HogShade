// HogShade core, model 2: the 2017 legacy v2 shading (legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx, pbr.sif),
// ported function by function. The maths is v2's; the interfaces are the core's. NumPy twin in
// hogshade/reference/legacy_v2.py; tests/core/test_legacy_v2_gpu.py compares them on the GPU.
//
// v2 characteristics kept verbatim (they are the look, not bugs):
//   - direct specular is NdotL * D * F * vis (Hable GGX_REF) and is then multiplied by NdotL again
//     with the light term, so specular carries NdotL squared;
//   - the GGX Fresnel takes Cspec0 through a float parameter, so it uses the red channel only; the
//     colour arrives through cSpecLin afterwards;
//   - cSpecLin = mix(Cspec0, base, metalness) * lut.x + lut.y scales the direct specular as well as
//     the environment specular (the reason the per-light function receives EnvironmentSamples);
//   - the final specular is multiplied by the linear base colour (dielectrics included);
//   - diffuse is not scaled by (1 - F): a white furnace returns 1 + (F0 * lut.x + lut.y), a few
//     percent over one facing the camera and up to 0.57 over at grazing (measured, tests/core);
//   - the roughness bias is applied to alpha (roughA * (1 - bias) + bias) for the lobes and to the
//     perceptual roughness for the mip and LUT lookups;
//   - NdotV = abs(n.v) + 1e-4 (Frostbite), never clamped to zero.
//
// Deviations from v2 (each also in Docs/design/2026-09-20-modernization-direction.md):
//   1. Environment: E1 linear cubes and LUT; the RGBM decode, the .bgr swizzle, the exposure of 5,
//      the gamma parameter and the constant nine-mip count are gone. Hosts pass linear values.
//   2. Unbound maps: the host passes defaults (white base, flat normal, roughness and metalness
//      maps of one so the scalars rule, AO and cavity one) instead of v2's "black unless > 0" tests.
//      The unbound-cavity black specular is gone with it.
//   3. Lights: geometry and attenuation come from lighting.wgsl (windowed inverse square, smooth
//      cone) instead of Maya's 1 / (d * decay) and cos(angle) spot; a light's shadow scales that
//      light only, where v2 multiplied the running sum (order-dependent); the "ambient" light kind,
//      which contributed nothing in v2 (NdotL of -n is zero), is dropped.
//   4. Emissive, sampled but never used in v2, is added by models_shade; the specular map, sampled
//      but never used, scales specular_weight (default one keeps v2's output).
//   5. Vertex AO uses the red channel: surface.ao is a scalar.
//   6. POM, self-shadowing, depth peeling, tone mapping and the debug modes that read texels or
//      UVs (see legacy_v2_debug_inputs) live in the host.

// The material's scalar parameters, linear. Flags are u32: 0 off, anything else on.
struct legacy_v2_Material {
    base_color: vec3<f32>,
    roughness: f32,
    metalness: f32,
    specular: f32,              // materialSpecular
    specular_tint: f32,
    ior: f32,
    bump_intensity: f32,
    use_vertex_color: u32,
    use_vertex_ao: u32,
    use_vertex_alpha: u32,
    has_alpha: u32,
    normal_flip: vec3<f32>,     // +1 or -1 per tangent-space axis (v2's NormalCoordsysX/Y/Z)
    flip_backface_normals: u32,
    specular_f0_from_map: u32,
}

// Texel values the host sampled at the shading UV, linear, or the deviation-2 defaults when unbound.
struct legacy_v2_Samples {
    base_color: vec4<f32>,      // default (1, 1, 1, 1)
    roughness: f32,             // default 1: the scalar rules
    metalness: f32,             // default 1
    specular_f0: vec3<f32>,     // used when specular_f0_from_map
    specular_amount: f32,       // default 1
    ao: f32,                    // default 1
    cavity: f32,                // default 1
    emissive: vec3<f32>,        // default 0
    normal_ts: vec3<f32>,       // decoded, texel * 2 - 1; default (0, 0, 1)
}

// Per-fragment geometry from the vertex stage.
struct legacy_v2_Geometry {
    normal_ws: vec3<f32>,
    tangent_ws: vec3<f32>,
    binormal_ws: vec3<f32>,
    view_ws: vec3<f32>,         // unit, surface to eye
    position_ws: vec3<f32>,
    vertex_color: vec4<f32>,
    vertex_ao: vec3<f32>,
    front_face: u32,
}

fn legacy_v2_flag(f: u32) -> bool {
    return f != 0u;
}

// v2: roughnessBiasedA, the alpha the lobes use.
fn legacy_v2_alpha_biased(roughness: f32) -> f32 {
    let rough_a = roughness * roughness;
    return rough_a * (1.0 - HOGSHADE_ROUGHNESS_BIAS) + HOGSHADE_ROUGHNESS_BIAS;
}

// v2: pbrRoughnessBiased, the perceptual roughness the mip and LUT lookups use.
fn legacy_v2_roughness_biased(roughness: f32) -> f32 {
    return roughness * (1.0 - HOGSHADE_ROUGHNESS_BIAS) + HOGSHADE_ROUGHNESS_BIAS;
}

// v2's "luminance approx." of the linear base colour.
fn legacy_v2_luminance(c: vec3<f32>) -> f32 {
    return 0.3 * c.x + 0.6 * c.y + 0.1 * c.z;
}

// The IOR-derived scalar F0 v2 uses when no F0 map is bound: ((1 - ior) / (1 + ior))^2.
fn legacy_v2_f0_from_ior(ior: f32) -> f32 {
    let n_f0 = abs((1.0 - ior) / (1.0 + ior));
    return n_f0 * n_f0;
}

// Tangent-space normal after v2's intensity, derived Z, axis flips and back-face flip.
fn legacy_v2_normal_ts(m: legacy_v2_Material, s: legacy_v2_Samples, front_face: bool) -> vec3<f32> {
    let raw = s.normal_ts;
    let z = sqrt(1.0 - clamp(dot(raw.xy, raw.xy), 0.0, 1.0));
    var n_ts = vec3<f32>(raw.xy * m.bump_intensity, z) * m.normal_flip;
    if (legacy_v2_flag(m.flip_backface_normals) && !front_face) {
        n_ts = -n_ts;
    }
    return n_ts;
}

// The material half: v2's texture stage, from sampled values to ShadingInputs.
fn legacy_v2_inputs(m: legacy_v2_Material, s: legacy_v2_Samples, g: legacy_v2_Geometry) -> ShadingInputs {
    var i: ShadingInputs;
    // colour: material tint times texel, times the vertex colour when enabled
    var base_lin = m.base_color * s.base_color.rgb;
    if (legacy_v2_flag(m.use_vertex_color)) {
        base_lin = base_lin * g.vertex_color.rgb;
    }
    // scalar maps scaled by the material values (v2: lerp(0, tex, material))
    let roughness = s.roughness * m.roughness;
    let metalness = s.metalness * m.metalness;
    // AO: bumpAO = lerp(1, map, bump intensity), times the vertex AO (deviation 5: red channel)
    var ao = mix(1.0, s.ao, m.bump_intensity);
    if (legacy_v2_flag(m.use_vertex_ao)) {
        ao = ao * g.vertex_ao.x;
    }
    // opacity from the base colour alpha and the vertex alpha
    var opacity = 1.0;
    if (legacy_v2_flag(m.has_alpha)) {
        opacity = s.base_color.a;
    }
    if (legacy_v2_flag(m.use_vertex_alpha)) {
        opacity = opacity * g.vertex_color.a;
    }
    // normal: tangent space to world through the vertex frame
    let n_ts = legacy_v2_normal_ts(m, s, legacy_v2_flag(g.front_face));
    let n_ws = normalize(n_ts.x * g.tangent_ws + n_ts.y * g.binormal_ws + n_ts.z * g.normal_ws);
    // F0: from the map when bound, else from the IOR
    var f0 = vec3<f32>(legacy_v2_f0_from_ior(m.ior));
    if (legacy_v2_flag(m.specular_f0_from_map)) {
        f0 = s.specular_f0;
    }
    // Cspec0: the tinted dielectric F0, or the base colour for metals
    let lum = legacy_v2_luminance(base_lin);
    var ctint = vec3<f32>(1.0);
    if (lum > 0.0) {
        ctint = base_lin / lum;
    }
    let cspec0 = mix(m.specular * f0 * mix(vec3<f32>(1.0), ctint, m.specular_tint), base_lin, metalness);

    i.surface.base_color = base_lin;
    i.surface.metalness = metalness;
    i.surface.roughness = roughness;
    i.surface.ao = ao;
    i.surface.emissive = s.emissive;
    i.surface.normal_ws = n_ws;
    i.surface.model = HOGSHADE_MODEL_LEGACY_V2;
    i.view_ws = normalize(g.view_ws);
    i.position_ws = g.position_ws;
    i.specular_f0 = cspec0;
    i.cavity = s.cavity;
    i.opacity = opacity;
    i.specular_weight = m.specular * s.specular_amount;  // deviation 4
    return i;
}

// v2's NdotV: abs plus epsilon, never zero.
fn legacy_v2_n_dot_v(i: ShadingInputs) -> f32 {
    return abs(dot(i.surface.normal_ws, i.view_ws)) + 1e-4;
}

// v2's cSpecLin: the split-sum scale on the (re-)metal-mixed Cspec0.
fn legacy_v2_c_spec(i: ShadingInputs, env: EnvironmentSamples) -> vec3<f32> {
    return mix(i.specular_f0, i.surface.base_color, i.surface.metalness) * env.brdf.x + env.brdf.y;
}

// The two accumulators v2 keeps per light and for the environment.
struct legacy_v2_Terms {
    diffuse: vec3<f32>,
    specular: vec3<f32>,
}

// v2's light loop body for one light: the Disney diffuse and Hable GGX terms times radiance and NdotL.
fn legacy_v2_light_terms(i: ShadingInputs, light: LightSource) -> legacy_v2_Terms {
    var t: legacy_v2_Terms;
    t.diffuse = vec3<f32>(0.0);
    t.specular = vec3<f32>(0.0);
    let inc = lighting_incident(light, i.position_ws);
    if (!inc.valid) {
        return t;
    }
    let n = i.surface.normal_ws;
    let v = i.view_ws;
    let l = inc.l_ws;
    let h = normalize(l + v);
    let n_dot_v = legacy_v2_n_dot_v(i);
    let n_dot_l = clamp(dot(n, l), 0.0, 1.0);
    let l_dot_h = clamp(dot(l, h), 0.0, 1.0);
    let n_dot_h = clamp(dot(n, h), 0.0, 1.0);
    let alpha = legacy_v2_alpha_biased(i.surface.roughness);
    // bigD_DiffuseBRDF(roughA, NdotL, NdotV, LdotH): Burley with alpha in Fd90, albedo applied later
    let diffuse_term = brdf_burley(vec3<f32>(1.0), alpha, n_dot_v, n_dot_l, l_dot_h).x;
    // LightingFuncGGX_REF: D, scalar Schlick on Cspec0.r, Hable vis, times NdotL
    let d = brdf_ggx_d(n_dot_h, alpha);
    let f = brdf_fresnel_schlick(vec3<f32>(i.specular_f0.x), l_dot_h).x;
    let vis = brdf_vis_hable(n_dot_l, n_dot_v, alpha);
    let specular_term = n_dot_l * d * f * vis;
    let radiance = lighting_radiance(light, inc);
    t.diffuse = diffuse_term * radiance * n_dot_l;
    t.specular = specular_term * radiance * n_dot_l;
    return t;
}

// v2's final composite: diffuse on the metal-darkened base with AO; specular through cSpecLin and
// the specular amount, on the base colour with AO and cavity.
fn legacy_v2_composite(i: ShadingInputs, env: EnvironmentSamples, t: legacy_v2_Terms) -> vec3<f32> {
    let base = i.surface.base_color;
    let m_color = base * (1.0 - i.surface.metalness);
    let c_spec = legacy_v2_c_spec(i, env);
    let ao = i.surface.ao;
    return t.diffuse * m_color * ao + t.specular * c_spec * i.specular_weight * base * ao * i.cavity;
}

// The environment terms before the composite: E1 samples with the hemispherical ambient applied.
fn legacy_v2_env_terms(env: EnvironmentSamples) -> legacy_v2_Terms {
    var t: legacy_v2_Terms;
    t.diffuse = env.irradiance_over_pi;
    t.specular = env.specular;
    if (env.hemisphere_mode == 1u) {
        t.diffuse = t.diffuse + env.hemisphere;
        t.specular = t.specular + env.hemisphere;
    } else if (env.hemisphere_mode == 2u) {
        t.diffuse = t.diffuse * env.hemisphere;
        t.specular = t.specular * env.hemisphere;
    }
    return t;
}

// Radiance from one light.
fn legacy_v2_evaluate_light(i: ShadingInputs, light: LightSource, env: EnvironmentSamples) -> vec3<f32> {
    return legacy_v2_composite(i, env, legacy_v2_light_terms(i, light));
}

// Radiance from the environment.
fn legacy_v2_evaluate_env(i: ShadingInputs, env: EnvironmentSamples) -> vec3<f32> {
    return legacy_v2_composite(i, env, legacy_v2_env_terms(env));
}

// The v2 debug modes whose value is a texel, a UV or a host effect, which the core cannot see.
// A forward host answers these from legacy_v2_debug_inputs; legacy_v2_debug returns the nearest
// core value so every mode is finite in a deferred host too.
fn legacy_v2_debug_is_inputs_mode(mode: u32) -> bool {
    switch (mode) {
        case 1u, 2u, 5u, 6u, 11u, 12u, 13u, 14u, 15u, 25u, 30u, 31u: { return true; }
        default: { return false; }
    }
}

// The material-stage debug views, exactly as v2 computed them. uv is the shading UV (after POM),
// self_shadow the host's POM self-shadow term, sky and ground the un-linearised dome colours.
fn legacy_v2_debug_inputs(
    m: legacy_v2_Material, s: legacy_v2_Samples, g: legacy_v2_Geometry,
    uv: vec2<f32>, self_shadow: f32, sky: vec3<f32>, ground: vec3<f32>, up_ws: vec3<f32>, mode: u32,
) -> vec3<f32> {
    var base_lin = m.base_color * s.base_color.rgb;
    if (legacy_v2_flag(m.use_vertex_color)) {
        base_lin = base_lin * g.vertex_color.rgb;
    }
    let lum = legacy_v2_luminance(base_lin);
    var ctint = vec3<f32>(1.0);
    if (lum > 0.0) {
        ctint = base_lin / lum;
    }
    var f0 = vec3<f32>(legacy_v2_f0_from_ior(m.ior));
    if (legacy_v2_flag(m.specular_f0_from_map)) {
        f0 = s.specular_f0;
    }
    switch (mode) {
        case 1u: { return s.base_color.rgb; }
        case 2u: { return vec3<f32>(s.base_color.a); }
        case 5u: { return g.vertex_color.rgb; }
        case 6u: { return vec3<f32>(g.vertex_color.a); }
        case 11u: { return s.normal_ts * 0.5 + vec3<f32>(0.5); }
        case 12u: { return s.normal_ts; }
        case 13u: { return vec3<f32>(f0.x); }
        case 14u: { return vec3<f32>(lum); }
        case 15u: { return ctint; }
        case 25u: { return environment_hemisphere(sky, ground, normalize(g.normal_ws), up_ws); }
        case 30u: {
            var c = vec3<f32>(0.0);
            if (uv.x < 0.0) { c = vec3<f32>(0.0, 1.0, 0.0); }
            if (uv.y < 0.0) { c = vec3<f32>(0.0, 0.0, 1.0); }
            if (uv.x > 1.0) { c = vec3<f32>(1.0, 0.0, 0.0); }
            if (uv.y > 1.0) { c = vec3<f32>(1.0, 0.0, 1.0); }
            return c;
        }
        case 31u: { return vec3<f32>(self_shadow); }
        default: { return vec3<f32>(0.0); }
    }
}

// v2's mode 32: unnormalised triplanar weights from the normal (cos 55 to cos 35 degrees).
fn legacy_v2_triplanar_weights(n_ws: vec3<f32>) -> vec3<f32> {
    let a = abs(normalize(n_ws));
    return smoothstep(vec3<f32>(0.57357644), vec3<f32>(0.81915204), a);
}

// The 33 v2 debug views (g_DebugMode 0..32) over the lighting-stage values. Mode 0 is the shaded
// colour. Inputs-stage modes return the nearest ShadingInputs value here; see legacy_v2_debug_inputs.
fn legacy_v2_debug(i: ShadingInputs, slots: FixedSlots16, env: EnvironmentSamples, mode: u32) -> vec3<f32> {
    let base = i.surface.base_color;
    let rough = i.surface.roughness;
    let rough_a = rough * rough;
    let alpha = legacy_v2_alpha_biased(rough);
    let n_vis = i.surface.normal_ws * 0.5 + vec3<f32>(0.5);
    let lum = legacy_v2_luminance(base);
    switch (mode) {
        case 0u: {
            var sum = vec3<f32>(0.0);
            let n = min(slots.count, 16u);
            for (var k = 0u; k < n; k = k + 1u) {
                sum = sum + legacy_v2_evaluate_light(i, slots.light[k], env);
            }
            return sum + legacy_v2_evaluate_env(i, env) + i.surface.emissive;
        }
        case 1u, 3u: { return base; }
        case 2u, 6u: { return vec3<f32>(i.opacity); }
        case 4u: { return base * (1.0 - i.surface.metalness); }
        case 5u: { return vec3<f32>(1.0); }
        case 7u: { return vec3<f32>(i.surface.metalness); }
        case 8u, 19u: { return vec3<f32>(rough); }
        case 9u: { return vec3<f32>(i.surface.ao); }
        case 10u: { return vec3<f32>(i.cavity); }
        case 11u, 12u: { return n_vis; }
        case 13u: { return vec3<f32>(i.specular_f0.x); }
        case 14u: { return vec3<f32>(lum); }
        case 15u: {
            if (lum > 0.0) { return base / lum; }
            return vec3<f32>(1.0);
        }
        case 16u: { return i.specular_f0; }
        case 17u, 18u: {
            // v2's accumulators at debug time: direct sums with the environment folded in
            var direct: legacy_v2_Terms;
            direct.diffuse = vec3<f32>(0.0);
            direct.specular = vec3<f32>(0.0);
            let n = min(slots.count, 16u);
            for (var k = 0u; k < n; k = k + 1u) {
                let t = legacy_v2_light_terms(i, slots.light[k]);
                direct.diffuse = direct.diffuse + t.diffuse;
                direct.specular = direct.specular + t.specular;
            }
            let e = legacy_v2_env_terms(env);
            if (mode == 17u) {
                return direct.diffuse + e.diffuse;
            }
            return (direct.specular + e.specular) * legacy_v2_c_spec(i, env) * i.specular_weight;
        }
        case 20u: { return vec3<f32>(rough_a); }
        case 21u: { return vec3<f32>(rough_a * rough_a); }
        case 22u: { return vec3<f32>(alpha); }
        case 23u: { return vec3<f32>(alpha * alpha); }
        case 24u: { return vec3<f32>(legacy_v2_n_dot_v(i)); }
        case 25u, 26u: { return env.hemisphere; }
        case 27u: { return legacy_v2_env_terms(env).diffuse; }
        case 28u: { return legacy_v2_env_terms(env).specular; }
        case 29u: { return legacy_v2_c_spec(i, env); }
        case 30u: { return vec3<f32>(0.0); }
        case 31u: { return vec3<f32>(1.0); }
        case 32u: { return legacy_v2_triplanar_weights(i.surface.normal_ws); }
        default: { return vec3<f32>(0.0); }
    }
}
