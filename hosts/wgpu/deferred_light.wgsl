// HogShade wgpu host, deferred path, second half: a full-screen pass that decodes the G-buffer,
// reconstructs the view vector and position from depth, and runs the lighting half.
// Stitch: core + common.wgsl + this file.

@group(2) @binding(0) var host_gb0: texture_2d<f32>;
@group(2) @binding(1) var host_gb1: texture_2d<f32>;
@group(2) @binding(2) var host_gb2: texture_2d<u32>;
@group(2) @binding(3) var host_gb3: texture_2d<f32>;
@group(2) @binding(4) var host_depth: texture_depth_2d;

struct host_ScreenOut {
    @builtin(position) clip: vec4<f32>,
}

// One triangle covering the viewport; no vertex buffer.
@vertex
fn vs_main(@builtin(vertex_index) index: u32) -> host_ScreenOut {
    var o: host_ScreenOut;
    let x = f32(i32(index & 1u) * 4 - 1);
    let y = f32(i32(index >> 1u) * 4 - 1);
    o.clip = vec4<f32>(x, y, 0.0, 1.0);
    return o;
}

// World position from the pixel centre and its depth, through the inverse view-projection.
fn host_position_from_depth(pixel: vec2<f32>, depth: f32) -> vec3<f32> {
    let uv = pixel / host_frame.viewport.xy;
    let ndc = vec4<f32>(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0, depth, 1.0);
    let p = host_frame.inv_view_proj * ndc;
    return p.xyz / p.w;
}

@fragment
fn fs_main(v: host_ScreenOut) -> @location(0) vec4<f32> {
    let px = vec2<i32>(v.clip.xy);
    let depth = textureLoad(host_depth, px, 0);
    if (depth >= 1.0) {
        return vec4<f32>(0.0, 0.0, 0.0, 1.0);
    }
    var t: GBufferTargets;
    t.gb0 = textureLoad(host_gb0, px, 0);
    t.gb1 = textureLoad(host_gb1, px, 0);
    t.gb2 = textureLoad(host_gb2, px, 0);
    t.gb3 = textureLoad(host_gb3, px, 0);
    let s = gbuffer_decode_adr002(t);
    let position_ws = host_position_from_depth(v.clip.xy, depth);
    let view_ws = normalize(host_frame.camera_ws.xyz - position_ws);
    let i = gbuffer_reconstruct(s, view_ws, position_ws);
    return vec4<f32>(host_shade(i), 1.0);
}
