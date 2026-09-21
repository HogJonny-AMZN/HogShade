// HogShade core: image-based lighting from the E1 cook. Textures and samplers are parameters.
//
// Conventions (Docs/specs/e1-ibl-cook.md): the specular cube is GGX-prefiltered with roughness
// linear in mip; the irradiance cube and the SH9 constants store E / pi; the BRDF LUT is indexed
// by (NdotV, roughness) and returns (scale, bias) on F0. Nothing here tonemaps.

// Prefiltered specular radiance in direction r for a perceptual roughness.
fn environment_specular(
    specular_cube: texture_cube<f32>,
    cube_sampler: sampler,
    env: EnvironmentIBL,
    r_ws: vec3<f32>,
    roughness: f32,
) -> vec3<f32> {
    let mip = clamp(roughness, 0.0, 1.0) * max(env.specular_mip_count - 1.0, 0.0);
    return textureSampleLevel(specular_cube, cube_sampler, r_ws, mip).rgb * env.exposure;
}

// Diffuse irradiance over pi from the irradiance cube.
fn environment_irradiance_cube(
    irradiance_cube: texture_cube<f32>,
    cube_sampler: sampler,
    env: EnvironmentIBL,
    n_ws: vec3<f32>,
) -> vec3<f32> {
    return textureSampleLevel(irradiance_cube, cube_sampler, n_ws, 0.0).rgb * env.exposure;
}

// Diffuse irradiance over pi from the SH9 radiance coefficients (Ramamoorthi and Hanrahan).
fn environment_irradiance_sh9(env: EnvironmentIBL, n_ws: vec3<f32>) -> vec3<f32> {
    let x = n_ws.x;
    let y = n_ws.y;
    let z = n_ws.z;
    var e = env.sh9[0].xyz * (HOGSHADE_SH_A0 * 0.282095);
    e = e + env.sh9[1].xyz * (HOGSHADE_SH_A1 * 0.488603 * y);
    e = e + env.sh9[2].xyz * (HOGSHADE_SH_A1 * 0.488603 * z);
    e = e + env.sh9[3].xyz * (HOGSHADE_SH_A1 * 0.488603 * x);
    e = e + env.sh9[4].xyz * (HOGSHADE_SH_A2 * 1.092548 * x * y);
    e = e + env.sh9[5].xyz * (HOGSHADE_SH_A2 * 1.092548 * y * z);
    e = e + env.sh9[6].xyz * (HOGSHADE_SH_A2 * 0.315392 * (3.0 * z * z - 1.0));
    e = e + env.sh9[7].xyz * (HOGSHADE_SH_A2 * 1.092548 * x * z);
    e = e + env.sh9[8].xyz * (HOGSHADE_SH_A2 * 0.546274 * (x * x - y * y));
    return max(e * HOGSHADE_INV_PI, vec3<f32>(0.0)) * env.exposure;
}

// The split-sum environment BRDF: returns (scale, bias) so specular = prefiltered * (f0 * scale + bias).
fn environment_brdf_lut(
    lut: texture_2d<f32>,
    lut_sampler: sampler,
    n_dot_v: f32,
    roughness: f32,
) -> vec2<f32> {
    let uv = vec2<f32>(clamp(n_dot_v, 0.0, 1.0), clamp(roughness, 0.0, 1.0));
    return textureSampleLevel(lut, lut_sampler, uv, 0.0).rg;
}

// A neutral environment description: no exposure change, cube-based irradiance, nine zero coefficients.
fn environment_default(mip_count: f32) -> EnvironmentIBL {
    var env: EnvironmentIBL;
    env.specular_mip_count = mip_count;
    env.exposure = 1.0;
    env.use_sh9 = 0u;
    env._pad = 0u;
    for (var i = 0u; i < 9u; i = i + 1u) {
        env.sh9[i] = vec4<f32>(0.0);
    }
    return env;
}
