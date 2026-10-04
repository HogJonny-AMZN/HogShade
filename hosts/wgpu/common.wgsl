// HogShade wgpu host: the bindings and per-frame data every pass shares. Stitched after the core
// and before a pass file (hosts/wgpu/README.md); WGSL has no include, so the host does it.
//
// Group 0 is the frame, group 1 the E1 environment (cube maps, LUT, samplers). The deferred light
// pass adds group 2 for the G-buffer. Everything the core needs still arrives as function
// parameters; these globals exist only in the host.

struct host_Frame {
    view_proj: mat4x4<f32>,
    inv_view_proj: mat4x4<f32>,
    camera_ws: vec4<f32>,       // xyz: eye position
    light_dir_ws: vec4<f32>,    // xyz: unit, towards the light; w: intensity
    light_color: vec4<f32>,     // rgb: linear; a: shadow term
    base_color: vec4<f32>,      // rgb: linear material colour; a: roughness
    material: vec4<f32>,        // metalness, specular amount, specular tint, ior
    env: vec4<f32>,             // specular mip count, exposure, debug mode, hemisphere mode
    sky: vec4<f32>,             // rgb: hemisphere sky, linear
    ground: vec4<f32>,          // rgb: hemisphere ground, linear
    up_ws: vec4<f32>,           // xyz: the hemisphere up axis
    viewport: vec4<f32>,        // width, height, 0, 0
    model: vec4<f32>,           // x: HOGSHADE_MODEL_* as a float; y: legacy v1 rough-is-gloss flag; z, w: unused
    params_a: vec4<f32>,        // legacy v1: subsurface, specular_tint, anisotropic, sheen
    params_b: vec4<f32>,        // legacy v1: sheen_tint, clearcoat, clearcoat_gloss, unused
    sh9: array<vec4<f32>, 9>,   // radiance coefficients; env.use_sh9 is off in this host, cubes rule
}

@group(0) @binding(0) var<uniform> host_frame: host_Frame;

@group(1) @binding(0) var host_specular_cube: texture_cube<f32>;
@group(1) @binding(1) var host_irradiance_cube: texture_cube<f32>;
@group(1) @binding(2) var host_brdf_lut: texture_2d<f32>;
@group(1) @binding(3) var host_cube_sampler: sampler;
@group(1) @binding(4) var host_lut_sampler: sampler;

// The legacy v2 material of this host: scalar parameters only, every map at its unbound default.
fn host_material() -> legacy_v2_Material {
    var m: legacy_v2_Material;
    m.base_color = host_frame.base_color.rgb;
    m.roughness = host_frame.base_color.a;
    m.metalness = host_frame.material.x;
    m.specular = host_frame.material.y;
    m.specular_tint = host_frame.material.z;
    m.ior = host_frame.material.w;
    m.bump_intensity = 1.0;
    m.use_vertex_color = 0u;
    m.use_vertex_ao = 0u;
    m.use_vertex_alpha = 0u;
    m.has_alpha = 0u;
    m.normal_flip = vec3<f32>(1.0);
    m.flip_backface_normals = 0u;
    m.specular_f0_from_map = 0u;
    return m;
}

fn host_samples() -> legacy_v2_Samples {
    var s: legacy_v2_Samples;
    s.base_color = vec4<f32>(1.0);
    s.roughness = 1.0;
    s.metalness = 1.0;
    s.specular_f0 = vec3<f32>(0.0);
    s.specular_amount = 1.0;
    s.ao = 1.0;
    s.cavity = 1.0;
    s.emissive = vec3<f32>(0.0);
    s.normal_ts = vec3<f32>(0.0, 0.0, 1.0);
    return s;
}

// Any orthonormal frame around n: with a flat tangent-space normal the tangent choice cannot matter.
fn host_tangent_frame(n: vec3<f32>) -> mat3x3<f32> {
    let helper = select(vec3<f32>(1.0, 0.0, 0.0), vec3<f32>(0.0, 0.0, 1.0), abs(n.x) > 0.9);
    let t = normalize(cross(helper, n));
    let b = cross(n, t);
    return mat3x3<f32>(t, b, n);
}

// The tangent frame: MikkTSpace's when the mesh carries one (the tangent orthogonalised against the
// interpolated normal, the bitangent from the handedness sign), else any frame around the normal.
fn host_frame_of(n: vec3<f32>, tangent_ws: vec4<f32>) -> mat3x3<f32> {
    if (dot(tangent_ws.xyz, tangent_ws.xyz) < 1e-8) {
        return host_tangent_frame(n);
    }
    let t = normalize(tangent_ws.xyz - n * dot(n, tangent_ws.xyz));
    let b = cross(n, t) * select(1.0, -1.0, tangent_ws.w < 0.0);
    return mat3x3<f32>(t, b, n);
}

fn host_geometry(position_ws: vec3<f32>, normal_ws: vec3<f32>, tangent_ws: vec4<f32>, front_face: bool) -> legacy_v2_Geometry {
    var g: legacy_v2_Geometry;
    let n = normalize(normal_ws);
    let frame = host_frame_of(n, tangent_ws);
    g.normal_ws = n;
    g.tangent_ws = frame[0];
    g.binormal_ws = frame[1];
    g.view_ws = normalize(host_frame.camera_ws.xyz - position_ws);
    g.position_ws = position_ws;
    g.vertex_color = vec4<f32>(1.0);
    g.vertex_ao = vec3<f32>(1.0);
    g.front_face = select(0u, 1u, front_face);
    return g;
}

// The legacy v1 material of this host: the same scalar parameters, plus the Disney lobes from params_a/b.
fn host_material_v1() -> legacy_v1_Material {
    var m: legacy_v1_Material;
    m.base_color = host_frame.base_color.rgb;
    m.metalness = host_frame.material.x;
    m.subsurface = host_frame.params_a.x;
    m.specular = host_frame.material.y;
    m.roughness = host_frame.base_color.a;
    m.specular_tint = host_frame.params_a.y;
    m.anisotropic = host_frame.params_a.z;
    m.sheen = host_frame.params_a.w;
    m.sheen_tint = host_frame.params_b.x;
    m.clearcoat = host_frame.params_b.y;
    m.clearcoat_gloss = host_frame.params_b.z;
    m.use_vertex_color_ao = 0u;
    m.has_alpha = 0u;
    m.use_vertex_alpha = 0u;
    m.use_cutout_alpha = 0u;
    m.flip_backface_normals = 0u;
    m.rough_is_gloss = u32(host_frame.model.y);
    m.use_specular_mask = 0u;
    m.normal_flip = vec3<f32>(1.0);
    return m;
}

fn host_samples_v1() -> legacy_v1_Samples {
    var s: legacy_v1_Samples;
    s.base_color = vec4<f32>(1.0);
    s.specular = vec4<f32>(1.0);
    s.roughness = 1.0;
    s.metalness = 1.0;
    s.ao = vec3<f32>(1.0);
    s.normal_ts = vec3<f32>(0.0, 0.0, 1.0);
    s.use_base_map = 0u;
    s.use_specular_map = 0u;
    s.use_roughness_map = 0u;
    s.use_metalness_map = 0u;
    s.use_normal_map = 0u;
    return s;
}

fn host_geometry_v1(position_ws: vec3<f32>, normal_ws: vec3<f32>, tangent_ws: vec4<f32>, front_face: bool) -> legacy_v1_Geometry {
    let g2 = host_geometry(position_ws, normal_ws, tangent_ws, front_face);
    var g: legacy_v1_Geometry;
    g.normal_ws = g2.normal_ws;
    g.tangent_ws = g2.tangent_ws;
    g.binormal_ws = g2.binormal_ws;
    g.view_ws = g2.view_ws;
    g.position_ws = g2.position_ws;
    g.vertex_color = g2.vertex_color;
    g.front_face = g2.front_face;
    return g;
}

// The material half for whichever model the frame selects (a uniform branch).
fn host_inputs(position_ws: vec3<f32>, normal_ws: vec3<f32>, tangent_ws: vec4<f32>, uv: vec2<f32>, front_face: bool) -> ShadingInputs {
    let model = u32(host_frame.model.x);
    if (model == HOGSHADE_MODEL_LEGACY_V1) {
        return legacy_v1_inputs(host_material_v1(), host_samples_v1(), host_geometry_v1(position_ws, normal_ws, tangent_ws, front_face));
    }
    if (model == HOGSHADE_MODEL_LAMBERT) {
        let g = host_geometry(position_ws, normal_ws, tangent_ws, front_face);
        return lambert_inputs(host_frame.base_color.rgb, 1.0, vec3<f32>(0.0), g.normal_ws, g.view_ws, position_ws);
    }
    return legacy_v2_inputs(host_material(), host_samples(), host_geometry(position_ws, normal_ws, tangent_ws, front_face));
}

fn host_environment_ibl() -> EnvironmentIBL {
    var env = environment_default(host_frame.env.x);
    env.exposure = host_frame.env.y;
    for (var k = 0u; k < 9u; k = k + 1u) {
        env.sh9[k] = host_frame.sh9[k];
    }
    return env;
}

// The single bound light of this host in slot 0.
fn host_slots() -> FixedSlots16 {
    var slots = lighting_slots_empty();
    slots.light[0].kind = 1u;
    slots.light[0].direction_ws = normalize(host_frame.light_dir_ws.xyz);
    slots.light[0].intensity = host_frame.light_dir_ws.w;
    slots.light[0].color = host_frame.light_color.rgb;
    slots.light[0].shadow = host_frame.light_color.a;
    slots.count = 1u;
    return slots;
}

// The lighting half for any ShadingInputs: environment sampled at the model's lookup, one light,
// the hemisphere dome the frame asks for, and the debug view when one is selected.
fn host_shade(i: ShadingInputs) -> vec3<f32> {
    let ibl = host_environment_ibl();
    var env = environment_sample(
        host_specular_cube, host_irradiance_cube, host_brdf_lut, host_cube_sampler, host_lut_sampler,
        ibl, i.surface.normal_ws, i.view_ws, models_env_lookup(i),
    );
    env.hemisphere = environment_hemisphere(host_frame.sky.rgb, host_frame.ground.rgb, i.surface.normal_ws, host_frame.up_ws.xyz);
    env.hemisphere_mode = u32(host_frame.env.w);
    let debug_mode = u32(host_frame.env.z);
    let r = models_shade(i, host_slots(), env, debug_mode);
    return select(r.color, r.debug, debug_mode != HOGSHADE_DEBUG_NONE);
}
