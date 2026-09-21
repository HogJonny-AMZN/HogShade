// HogShade core: the validation entry point the build appends so naga has a module to translate and
// fxc and dxc have a pixel shader to compile. It touches the public API so a broken signature is a
// build error, and it declares no bindings, so nothing here shapes the generated artifacts. Hosts
// never use it.

@fragment
fn hogshade_validate(@location(0) normal_ws: vec3<f32>, @location(1) view_ws: vec3<f32>) -> @location(0) vec4<f32> {
    let i = lambert_inputs(vec3<f32>(0.8), 1.0, vec3<f32>(0.0), normal_ws, view_ws, vec3<f32>(0.0));
    var slots = lighting_slots_empty();
    slots.light[0].kind = 1u;
    slots.light[0].direction_ws = vec3<f32>(0.0, 1.0, 0.0);
    slots.light[0].color = vec3<f32>(1.0);
    slots.light[0].intensity = 1.0;
    slots.light[0].shadow = 1.0;
    slots.count = 1u;
    let env = environment_default(9.0);
    let irradiance = environment_irradiance_sh9(env, i.surface.normal_ws);
    let r = models_shade(i, slots, irradiance, HOGSHADE_DEBUG_NONE);
    var layout_meta: GBufferLayoutAdr002;
    layout_meta.layer = 0u;
    layout_meta.channel_mask = 255u;
    layout_meta.flags = 0u;
    let targets = gbuffer_encode_from_inputs(i, layout_meta);
    let back = gbuffer_reconstruct(gbuffer_decode_adr002(targets), i.view_ws, i.position_ws);
    return vec4<f32>(r.color + back.specular_f0 * 0.0, 1.0);
}
