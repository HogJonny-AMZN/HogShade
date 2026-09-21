// HogShade core, model 0: Lambert. The floor every host can run, and the placeholder that proves the
// model interface before the legacy ports land. Diffuse only; the specular F0 is ignored.

fn lambert_inputs(
    base_color: vec3<f32>,
    ao: f32,
    emissive: vec3<f32>,
    normal_ws: vec3<f32>,
    view_ws: vec3<f32>,
    position_ws: vec3<f32>,
) -> ShadingInputs {
    var i: ShadingInputs;
    i.surface.base_color = base_color;
    i.surface.metalness = 0.0;
    i.surface.roughness = 1.0;
    i.surface.ao = ao;
    i.surface.emissive = emissive;
    i.surface.normal_ws = normalize(normal_ws);
    i.surface.model = HOGSHADE_MODEL_LAMBERT;
    i.view_ws = normalize(view_ws);
    i.position_ws = position_ws;
    i.specular_f0 = vec3<f32>(HOGSHADE_DIELECTRIC_F0);
    i.opacity = 1.0;
    return i;
}

// Radiance from one light.
fn lambert_evaluate_light(i: ShadingInputs, light: LightSource) -> vec3<f32> {
    let inc = lighting_incident(light, i.position_ws);
    if (!inc.valid) {
        return vec3<f32>(0.0);
    }
    let n_dot_l = max(dot(i.surface.normal_ws, inc.l_ws), 0.0);
    return i.surface.base_color * HOGSHADE_INV_PI * n_dot_l * lighting_radiance(light, inc);
}

// Radiance from the environment, given irradiance over pi (cube or SH9, the caller chooses).
fn lambert_evaluate_env(i: ShadingInputs, irradiance_over_pi: vec3<f32>) -> vec3<f32> {
    return i.surface.base_color * irradiance_over_pi * i.surface.ao;
}

// Intermediates for the debug view: 1 base colour, 2 normal, 3 ao, 4 emissive.
fn lambert_debug(i: ShadingInputs, mode: u32) -> vec3<f32> {
    switch (mode) {
        case 1u: { return i.surface.base_color; }
        case 2u: { return i.surface.normal_ws * 0.5 + vec3<f32>(0.5); }
        case 3u: { return vec3<f32>(i.surface.ao); }
        case 4u: { return i.surface.emissive; }
        default: { return vec3<f32>(0.0); }
    }
}
