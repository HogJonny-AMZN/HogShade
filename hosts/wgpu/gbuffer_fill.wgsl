// HogShade wgpu host, deferred path, first half: the material half into the ADR-002 G-buffer.
// Stitch: core + common.wgsl + this file. Targets, in order: GB0 rgba8unorm-srgb, GB1 rgba16float,
// GB2 rgba8uint, GB3 rg11b10ufloat (core/gbuffer.wgsl).

struct host_VertexIn {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
}

struct host_VertexOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) position_ws: vec3<f32>,
    @location(1) normal_ws: vec3<f32>,
}

struct host_GBufferOut {
    @location(0) gb0: vec4<f32>,
    @location(1) gb1: vec4<f32>,
    @location(2) gb2: vec4<u32>,
    @location(3) gb3: vec4<f32>,
}

@vertex
fn vs_main(v: host_VertexIn) -> host_VertexOut {
    var o: host_VertexOut;
    o.clip = host_frame.view_proj * vec4<f32>(v.position, 1.0);
    o.position_ws = v.position;
    o.normal_ws = v.normal;
    return o;
}

@fragment
fn fs_main(v: host_VertexOut, @builtin(front_facing) front_face: bool) -> host_GBufferOut {
    let i = host_inputs(v.position_ws, v.normal_ws, front_face);
    var layout_meta: GBufferLayoutAdr002;
    layout_meta.layer = 0u;
    layout_meta.channel_mask = 255u;
    layout_meta.flags = 0u;
    let t = gbuffer_encode_from_inputs(i, layout_meta);
    var o: host_GBufferOut;
    o.gb0 = t.gb0;
    o.gb1 = t.gb1;
    o.gb2 = t.gb2;
    o.gb3 = t.gb3;
    return o;
}
