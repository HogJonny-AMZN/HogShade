// HogShade core: the public interface. These names are exempt from the module-prefix rule because
// every host and every model spells them the same way (core/manifest.toml, [names].exempt).
//
// Two halves (spec, "Two rendering paths"):
//   material half:  textures and parameters  ->  SurfaceInputs / ShadingInputs   (<model>_inputs)
//   lighting half:  ShadingInputs + lights + environment  ->  ShadingResult      (<model>_evaluate_*)
// Forward hosts run both in one shader. Deferred hosts store SurfaceInputs in the G-buffer, then
// reconstruct ShadingInputs in the light pass (gbuffer.wgsl).

// What the G-buffer stores; what inputs() must produce for the deferred path.
struct SurfaceInputs {
    base_color: vec3<f32>,      // linear
    metalness: f32,
    roughness: f32,             // perceptual, before bias
    ao: f32,                    // cavity folded in at encode time
    emissive: vec3<f32>,        // linear radiance
    normal_ws: vec3<f32>,       // unit, world space, after normal mapping
    model: u32,                 // HOGSHADE_MODEL_*
}

// Everything the lighting half consumes: SurfaceInputs plus what forward has and deferred reconstructs.
struct ShadingInputs {
    surface: SurfaceInputs,
    view_ws: vec3<f32>,         // unit, surface to eye
    position_ws: vec3<f32>,
    specular_f0: vec3<f32>,     // forward: from the model; deferred: mix(DIELECTRIC_F0, base_color, metalness)
    cavity: f32,                // forward only: specular occlusion detail; deferred folds it into surface.ao
    opacity: f32,               // forward only; 1.0 after MASK in deferred
    specular_weight: f32,       // forward only: the material's specular amount (v2 materialSpecular, OpenPBR specular_weight); 1.0 in deferred
}

struct ShadingResult {
    color: vec3<f32>,           // scene-linear radiance
    debug: vec3<f32>,           // the intermediate selected by the debug mode, or zero
}

// One punctual light. kind: 0 off, 1 directional, 2 point, 3 spot.
// Field order is the ABI a host packs into a uniform or storage buffer; std140/std430 offsets:
//   position_ws 0, kind 12, direction_ws 16, intensity 28, color 32, range 44, cone_cos 48,
//   shadow 56, _pad 60; size 64. hogshade/core_layout.py mirrors this and a test checks the order.
struct LightSource {
    position_ws: vec3<f32>,
    kind: u32,
    direction_ws: vec3<f32>,    // unit, towards the light for directional; spot axis, from the light, for spot
    intensity: f32,
    color: vec3<f32>,           // linear, in the light-rig unit
    range: f32,                 // point and spot: radiance reaches zero here; <= 0 means unbounded
    cone_cos: vec2<f32>,        // spot: cos(inner), cos(outer)
    shadow: f32,                // 0..1, supplied by the host
    _pad: f32,
}

// The v2 "gather lights" pattern: a DCC binds scene lights into fixed slots. 16 x 64 bytes.
struct FixedSlots16 {
    light: array<LightSource, 16>,
    count: u32,
    _pad0: u32,
    _pad1: u32,
    _pad2: u32,
}

// What the environment contributes at one surface point, sampled by the host (environment_sample)
// and consumed by the models. Numbers, not textures, so the models stay pure and testable.
// The per-light functions receive it too: the v2 model scales its direct specular by the split-sum
// LUT (a v2 characteristic kept verbatim), and the light pass has the LUT bound anyway.
struct EnvironmentSamples {
    irradiance_over_pi: vec3<f32>,  // diffuse: E / pi at the normal (cube or SH9)
    specular: vec3<f32>,            // prefiltered radiance at the reflection vector for the roughness
    brdf: vec2<f32>,                // split-sum LUT (scale, bias) at (n.v, roughness); (1, 0) when a host has no LUT
    hemisphere: vec3<f32>,          // v2 hemispherical ambient dome colour at the normal, linear
    hemisphere_mode: u32,           // 0 none, 1 add the dome to both env terms, 2 multiply them by it
}

// Constants of the E1 cook a host passes with its cube textures; the textures and samplers are
// function parameters (environment.wgsl), never globals.
struct EnvironmentIBL {
    specular_mip_count: f32,    // mips in the prefiltered cube; roughness maps linearly onto them
    exposure: f32,              // multiplier on both cubes, 1.0 for the E1 data
    use_sh9: u32,               // 1: irradiance from sh9 below instead of the irradiance cube
    _pad: u32,
    sh9: array<vec4<f32>, 9>,   // radiance L_lm coefficients, xyz used
}
