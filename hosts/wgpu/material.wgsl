// HogShade wgpu host, the material bind group (T3b): the four texture slots of a legacy v2 document, the
// sampler they share and the small uniform that says which parameters are bound and where each scalar reads.
// Stitched after common.wgsl into the passes that run the material half (lit_mesh, gbuffer_fill); the light
// pass carries its G-buffer at group 2 instead and a host_samples() that returns the unbound defaults.

struct host_Textures {
    bound: u32,             // a bit per textured parameter: 1 base colour, 2 normal, 4 roughness, 8 metalness, 16 AO, 32 cavity
    sel_a: vec4<u32>,       // roughness (slot, channel), metalness (slot, channel); at offset 16
    sel_b: vec4<u32>,       // AO (slot, channel), cavity (slot, channel); at offset 32
}

@group(2) @binding(0) var host_base_color: texture_2d<f32>;   // slot 0, sRGB: the view decodes
@group(2) @binding(1) var host_normal: texture_2d<f32>;       // slot 1, the two channels of _N
@group(2) @binding(2) var host_orm: texture_2d<f32>;          // slot 2, _ORM: AO r, roughness g, metalness b
@group(2) @binding(3) var host_cavity: texture_2d<f32>;       // slot 3, _C
@group(2) @binding(4) var host_material_sampler: sampler;
@group(2) @binding(5) var<uniform> host_textures: host_Textures;

// One scalar from the slot and channel the uniform names, or the unbound 1.0.
fn host_scalar(texels: array<vec4<f32>, 4>, sel: vec2<u32>, bound: bool) -> f32 {
    return select(1.0, texels[sel.x][sel.y], bound);
}

// Every slot is sampled unconditionally (uniform control flow keeps the derivatives for mip selection valid; a
// neutral 1x1 costs nothing); the bits and selectors decide what is used. The mesh's V is bottom-up (the OBJ
// convention, what the tangents were built from); the DDS's first row is the top, so V is flipped here, as the
// Maya shell negates it.
fn host_samples(uv_in: vec2<f32>) -> legacy_v2_Samples {
    var s = host_samples_unbound();
    let uv = vec2<f32>(uv_in.x, 1.0 - uv_in.y);
    let b = host_textures.bound;
    var texels: array<vec4<f32>, 4>;
    texels[0] = textureSample(host_base_color, host_material_sampler, uv);
    texels[1] = textureSample(host_normal, host_material_sampler, uv);
    texels[2] = textureSample(host_orm, host_material_sampler, uv);
    texels[3] = textureSample(host_cavity, host_material_sampler, uv);
    s.base_color = select(vec4<f32>(1.0), texels[0], (b & 1u) != 0u);
    let n_rg = select(vec2<f32>(0.5), texels[1].rg, (b & 2u) != 0u);
    s.normal_ts = vec3<f32>(n_rg * 2.0 - 1.0, 0.0);   // legacy_v2_normal_ts derives Z (T3's finding)
    s.roughness = host_scalar(texels, host_textures.sel_a.xy, (b & 4u) != 0u);
    s.metalness = host_scalar(texels, host_textures.sel_a.zw, (b & 8u) != 0u);
    s.ao = host_scalar(texels, host_textures.sel_b.xy, (b & 16u) != 0u);
    s.cavity = host_scalar(texels, host_textures.sel_b.zw, (b & 32u) != 0u);
    return s;  // specular F0, specular amount and emissive stay at their unbound defaults: no slot in T3b
}
