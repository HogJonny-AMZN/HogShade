// HogShade core: SurfaceInputs to and from a G-buffer. One definition the fill pass, the light pass
// and screen-space effects share. The first layout is SpriteJammer's ADR-002:
//
//   GB0  rgba8unorm-srgb   base_color.rgb, ao        (the attachment converts linear -> sRGB on store)
//   GB1  rgba16float       octahedral normal.xy, roughness, metalness
//   GB2  rgba8uint         layer, light-channel mask, shading-model ID, flags
//   GB3  rg11b10ufloat     emissive.rgb
//
// Deferred payload contract (spec, "Interfaces"): view and position are reconstructed by the light
// pass from depth and the camera; specular F0 is derived; opacity is 1 after MASK.

struct GBufferLayoutAdr002 {
    layer: u32,                 // engine-owned classification, passed through
    channel_mask: u32,
    flags: u32,
}

struct GBufferTargets {
    gb0: vec4<f32>,
    gb1: vec4<f32>,
    gb2: vec4<u32>,
    gb3: vec4<f32>,
}

// Octahedral encoding of a unit vector into [0, 1]^2 (Cigolle et al.), exact to the attachment's precision.
fn gbuffer_oct_encode(n: vec3<f32>) -> vec2<f32> {
    let l1 = abs(n.x) + abs(n.y) + abs(n.z);
    var p = n.xy / max(l1, 1e-8);
    if (n.z < 0.0) {
        let sx = select(-1.0, 1.0, p.x >= 0.0);
        let sy = select(-1.0, 1.0, p.y >= 0.0);
        p = (vec2<f32>(1.0) - abs(p.yx)) * vec2<f32>(sx, sy);
    }
    return p * 0.5 + vec2<f32>(0.5);
}

fn gbuffer_oct_decode(e: vec2<f32>) -> vec3<f32> {
    let p = e * 2.0 - vec2<f32>(1.0);
    var n = vec3<f32>(p.x, p.y, 1.0 - abs(p.x) - abs(p.y));
    let t = clamp(-n.z, 0.0, 1.0);
    let sx = select(t, -t, n.x >= 0.0);
    let sy = select(t, -t, n.y >= 0.0);
    n = vec3<f32>(n.x + sx, n.y + sy, n.z);
    return normalize(n);
}

fn gbuffer_encode_adr002(s: SurfaceInputs, layout_meta: GBufferLayoutAdr002) -> GBufferTargets {
    var t: GBufferTargets;
    t.gb0 = vec4<f32>(clamp(s.base_color, vec3<f32>(0.0), vec3<f32>(1.0)), clamp(s.ao, 0.0, 1.0));
    t.gb1 = vec4<f32>(gbuffer_oct_encode(normalize(s.normal_ws)), clamp(s.roughness, 0.0, 1.0), clamp(s.metalness, 0.0, 1.0));
    t.gb2 = vec4<u32>(layout_meta.layer & 255u, layout_meta.channel_mask & 255u, s.model & 255u, layout_meta.flags & 255u);
    t.gb3 = vec4<f32>(max(s.emissive, vec3<f32>(0.0)), 0.0);
    return t;
}

// The fill pass's entry: fold the forward-only cavity into ao, then encode the surface.
fn gbuffer_encode_from_inputs(i: ShadingInputs, layout_meta: GBufferLayoutAdr002) -> GBufferTargets {
    var s = i.surface;
    s.ao = s.ao * i.cavity;
    return gbuffer_encode_adr002(s, layout_meta);
}

fn gbuffer_decode_adr002(t: GBufferTargets) -> SurfaceInputs {
    var s: SurfaceInputs;
    s.base_color = t.gb0.rgb;
    s.ao = t.gb0.a;
    s.normal_ws = gbuffer_oct_decode(t.gb1.xy);
    s.roughness = t.gb1.z;
    s.metalness = t.gb1.w;
    s.model = t.gb2.z;
    s.emissive = t.gb3.rgb;
    return s;
}

// The light pass's reconstruction of the full lighting input from what the G-buffer stored.
fn gbuffer_reconstruct(s: SurfaceInputs, view_ws: vec3<f32>, position_ws: vec3<f32>) -> ShadingInputs {
    var i: ShadingInputs;
    i.surface = s;
    i.view_ws = view_ws;
    i.position_ws = position_ws;
    i.specular_f0 = mix(vec3<f32>(HOGSHADE_DIELECTRIC_F0), s.base_color, s.metalness);
    i.cavity = 1.0;             // folded into ao by gbuffer_encode_from_inputs
    i.opacity = 1.0;
    i.specular_weight = 1.0;
    return i;
}
