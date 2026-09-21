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
    opacity: f32,               // forward only; 1.0 after MASK in deferred
}

struct ShadingResult {
    color: vec3<f32>,           // scene-linear radiance
    debug: vec3<f32>,           // the intermediate selected by the debug mode, or zero
}

// One punctual light. kind: 0 off, 1 directional, 2 point, 3 spot.
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

// Constants of the E1 cook a host passes with its cube textures; the textures and samplers are
// function parameters (environment.wgsl), never globals.
struct EnvironmentIBL {
    specular_mip_count: f32,    // mips in the prefiltered cube; roughness maps linearly onto them
    exposure: f32,              // multiplier on both cubes, 1.0 for the E1 data
    use_sh9: u32,               // 1: irradiance from sh9 below instead of the irradiance cube
    _pad: u32,
    sh9: array<vec4<f32>, 9>,   // radiance L_lm coefficients, xyz used
}
