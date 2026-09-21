// HogShade core: the dispatch on the shading-model ID, and the fixed-slot light loop.
//
// A host calls models_evaluate_light per light (its own buffer) or models_evaluate_slots once (a
// DCC's 16 bound slots), then models_evaluate_env once, adds emissive, and reads models_debug when
// a debug view is on. Every branch here is a model's own function; nothing shading-specific lives
// in this file.

fn models_evaluate_light(i: ShadingInputs, light: LightSource) -> vec3<f32> {
    switch (i.surface.model) {
        case 0u: { return lambert_evaluate_light(i, light); }
        default: { return lambert_evaluate_light(i, light); }
    }
}

fn models_evaluate_env(i: ShadingInputs, irradiance_over_pi: vec3<f32>) -> vec3<f32> {
    switch (i.surface.model) {
        case 0u: { return lambert_evaluate_env(i, irradiance_over_pi); }
        default: { return lambert_evaluate_env(i, irradiance_over_pi); }
    }
}

fn models_debug(i: ShadingInputs, mode: u32) -> vec3<f32> {
    switch (i.surface.model) {
        case 0u: { return lambert_debug(i, mode); }
        default: { return lambert_debug(i, mode); }
    }
}

// The v2 gather pattern: sum the bound slots. count caps the loop; kind 0 slots contribute nothing.
fn models_evaluate_slots(i: ShadingInputs, slots: FixedSlots16) -> vec3<f32> {
    var sum = vec3<f32>(0.0);
    let n = min(slots.count, 16u);
    for (var k = 0u; k < n; k = k + 1u) {
        sum = sum + models_evaluate_light(i, slots.light[k]);
    }
    return sum;
}

// Direct plus environment plus emissive, with the debug slot filled: the whole lighting half.
fn models_shade(i: ShadingInputs, slots: FixedSlots16, irradiance_over_pi: vec3<f32>, debug_mode: u32) -> ShadingResult {
    var r: ShadingResult;
    r.color = models_evaluate_slots(i, slots) + models_evaluate_env(i, irradiance_over_pi) + i.surface.emissive;
    r.debug = vec3<f32>(0.0);
    if (debug_mode != HOGSHADE_DEBUG_NONE) {
        r.debug = models_debug(i, debug_mode);
    }
    return r;
}
