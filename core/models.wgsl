// HogShade core: the dispatch on the shading-model ID, and the fixed-slot light loop.
//
// A host samples its environment once (environment_sample, at models_env_lookup), then calls models_evaluate_light per
// light (its own buffer) or models_evaluate_slots once (a DCC's 16 bound slots), then
// models_evaluate_env once, adds emissive, and reads models_debug when a debug view is on;
// models_shade does all of that. Every branch here is a model's own function; nothing
// shading-specific lives in this file.
//
// The dispatch is an if-chain, not a switch: FXC (the compiler behind wgpu's D3D12 backend and
// Maya's dx11Shader) fails with "internal error: no storage type for block output" on naga's HLSL
// when a switch selects on a value read from a uint texture, as the deferred light pass does with
// the G-buffer's model ID, in a shader that also passes textures into functions (PR E, 2026-09-26).

fn models_evaluate_light(i: ShadingInputs, light: LightSource, env: EnvironmentSamples) -> vec3<f32> {
    if (i.surface.model == 0u) {
        return lambert_evaluate_light(i, light, env);
    } else if (i.surface.model == 1u) {
        return legacy_v1_evaluate_light(i, light, env);
    } else if (i.surface.model == 2u) {
        return legacy_v2_evaluate_light(i, light, env);
    }
    return lambert_evaluate_light(i, light, env);
}

// The (n.v, roughness) a model wants its LUT and prefiltered-mip lookups made at; a host passes
// the result to environment_sample. v2 uses abs(n.v) + 1e-4 and its biased roughness.
fn models_env_lookup(i: ShadingInputs) -> vec2<f32> {
    if (i.surface.model == 0u) {
        return lambert_env_lookup(i);
    } else if (i.surface.model == 1u) {
        return legacy_v1_env_lookup(i);
    } else if (i.surface.model == 2u) {
        return legacy_v2_env_lookup(i);
    }
    return lambert_env_lookup(i);
}

fn models_evaluate_env(i: ShadingInputs, env: EnvironmentSamples) -> vec3<f32> {
    if (i.surface.model == 0u) {
        return lambert_evaluate_env(i, env);
    } else if (i.surface.model == 1u) {
        return legacy_v1_evaluate_env(i, env);
    } else if (i.surface.model == 2u) {
        return legacy_v2_evaluate_env(i, env);
    }
    return lambert_evaluate_env(i, env);
}

fn models_debug(i: ShadingInputs, slots: FixedSlots16, env: EnvironmentSamples, mode: u32) -> vec3<f32> {
    if (i.surface.model == 0u) {
        return lambert_debug(i, slots, env, mode);
    } else if (i.surface.model == 1u) {
        return legacy_v1_debug(i, slots, env, mode);
    } else if (i.surface.model == 2u) {
        return legacy_v2_debug(i, slots, env, mode);
    }
    return lambert_debug(i, slots, env, mode);
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
