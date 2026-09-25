// HogShade core: the dispatch on the shading-model ID, and the fixed-slot light loop.
//
// A host samples its environment once (environment_sample), then calls models_evaluate_light per
// light (its own buffer) or models_evaluate_slots once (a DCC's 16 bound slots), then
// models_evaluate_env once, adds emissive, and reads models_debug when a debug view is on;
// models_shade does all of that. Every branch here is a model's own function; nothing
// shading-specific lives in this file.

fn models_evaluate_light(i: ShadingInputs, light: LightSource, env: EnvironmentSamples) -> vec3<f32> {
    switch (i.surface.model) {
        case 0u: { return lambert_evaluate_light(i, light, env); }
        case 2u: { return legacy_v2_evaluate_light(i, light, env); }
        default: { return lambert_evaluate_light(i, light, env); }
    }
}

fn models_evaluate_env(i: ShadingInputs, env: EnvironmentSamples) -> vec3<f32> {
    switch (i.surface.model) {
        case 0u: { return lambert_evaluate_env(i, env); }
        case 2u: { return legacy_v2_evaluate_env(i, env); }
        default: { return lambert_evaluate_env(i, env); }
    }
}

fn models_debug(i: ShadingInputs, slots: FixedSlots16, env: EnvironmentSamples, mode: u32) -> vec3<f32> {
    switch (i.surface.model) {
        case 0u: { return lambert_debug(i, slots, env, mode); }
        case 2u: { return legacy_v2_debug(i, slots, env, mode); }
        default: { return lambert_debug(i, slots, env, mode); }
    }
}

// The v2 gather pattern: sum the bound slots. count caps the loop; kind 0 slots contribute nothing.
fn models_evaluate_slots(i: ShadingInputs, slots: FixedSlots16, env: EnvironmentSamples) -> vec3<f32> {
    var sum = vec3<f32>(0.0);
    let n = min(slots.count, 16u);
    for (var k = 0u; k < n; k = k + 1u) {
        sum = sum + models_evaluate_light(i, slots.light[k], env);
    }
    return sum;
}

// Direct plus environment plus emissive, with the debug slot filled: the whole lighting half.
fn models_shade(i: ShadingInputs, slots: FixedSlots16, env: EnvironmentSamples, debug_mode: u32) -> ShadingResult {
    var r: ShadingResult;
    r.color = models_evaluate_slots(i, slots, env) + models_evaluate_env(i, env) + i.surface.emissive;
    r.debug = vec3<f32>(0.0);
    if (debug_mode != HOGSHADE_DEBUG_NONE) {
        r.debug = models_debug(i, slots, env, debug_mode);
    }
    return r;
}
