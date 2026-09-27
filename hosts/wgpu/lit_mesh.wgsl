// HogShade wgpu host, forward path: the material half and the lighting half in one fragment shader.
// Stitch: core + common.wgsl + this file.

struct host_VertexIn {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
}

struct host_VertexOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) position_ws: vec3<f32>,
    @location(1) normal_ws: vec3<f32>,
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
fn fs_main(v: host_VertexOut, @builtin(front_facing) front_face: bool) -> @location(0) vec4<f32> {
    let i = legacy_v2_inputs(host_material(), host_samples(), host_geometry(v.position_ws, v.normal_ws, front_face));
    return vec4<f32>(host_shade(i), 1.0);
}
