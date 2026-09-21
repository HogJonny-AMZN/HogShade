// HogShade core: punctual light geometry, shared by every model.
//
// A model implements <model>_evaluate_light(inputs, light) for one light; the loop over a
// FixedSlots16 lives here (lighting_accumulate_slots in models.wgsl calls the dispatcher), and an
// engine loops its own culled buffer calling the same per-light function. No function pointers in
// WGSL, so the loop is per provider; the maths is not.

// Direction to the light, distance attenuation and spot cone, for any light kind.
struct lighting_Incident {
    l_ws: vec3<f32>,            // unit, surface to light
    attenuation: f32,           // radiance scale: distance falloff x cone x shadow
    valid: bool,                // false for an off slot
}

fn lighting_incident(light: LightSource, position_ws: vec3<f32>) -> lighting_Incident {
    var out: lighting_Incident;
    out.l_ws = vec3<f32>(0.0, 1.0, 0.0);
    out.attenuation = 0.0;
    out.valid = false;
    if (light.kind == 0u) {
        return out;
    }
    if (light.kind == 1u) {
        out.l_ws = normalize(light.direction_ws);
        out.attenuation = light.shadow;
        out.valid = true;
        return out;
    }
    let to_light = light.position_ws - position_ws;
    let dist2 = max(dot(to_light, to_light), 1e-8);
    let dist = sqrt(dist2);
    out.l_ws = to_light / dist;
    var falloff = 1.0 / dist2;
    if (light.range > 0.0) {
        // windowed inverse square (Karis): smooth to zero at range, no discontinuity
        let ratio = dist / light.range;
        let window = clamp(1.0 - ratio * ratio * ratio * ratio, 0.0, 1.0);
        falloff = falloff * window * window;
    }
    var cone = 1.0;
    if (light.kind == 3u) {
        let cos_angle = dot(-out.l_ws, normalize(light.direction_ws));
        cone = clamp((cos_angle - light.cone_cos.y) / max(light.cone_cos.x - light.cone_cos.y, 1e-4), 0.0, 1.0);
        cone = cone * cone;
    }
    out.attenuation = falloff * cone * light.shadow;
    out.valid = true;
    return out;
}

// Radiance arriving from the light, before the BRDF: colour x intensity x attenuation.
fn lighting_radiance(light: LightSource, incident: lighting_Incident) -> vec3<f32> {
    return light.color * light.intensity * incident.attenuation;
}

// An empty slot set, for hosts and tests that have no lights.
fn lighting_slots_empty() -> FixedSlots16 {
    var slots: FixedSlots16;
    slots.count = 0u;
    for (var i = 0u; i < 16u; i = i + 1u) {
        slots.light[i].kind = 0u;
        slots.light[i].shadow = 1.0;
    }
    return slots;
}
