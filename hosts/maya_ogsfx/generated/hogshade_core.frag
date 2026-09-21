#version 330 core
struct SurfaceInputs {
    vec3 base_color;
    float metalness;
    float roughness;
    float ao;
    vec3 emissive;
    vec3 normal_ws;
    uint model;
};
struct ShadingInputs {
    SurfaceInputs surface;
    vec3 view_ws;
    vec3 position_ws;
    vec3 specular_f0_;
    float opacity;
};
struct ShadingResult {
    vec3 color;
    vec3 debug;
};
struct LightSource {
    vec3 position_ws;
    uint kind;
    vec3 direction_ws;
    float intensity;
    vec3 color;
    float range;
    vec2 cone_cos;
    float shadow;
    float _pad;
};
struct FixedSlots16_ {
    LightSource light[16];
    uint count;
    uint _pad0_;
    uint _pad1_;
    uint _pad2_;
};
struct EnvironmentIBL {
    float specular_mip_count;
    float exposure;
    uint use_sh9_;
    uint _pad;
    vec4 sh9_[9];
};
struct lighting_Incident {
    vec3 l_ws;
    float attenuation;
    bool valid;
};
struct GBufferLayoutAdr002_ {
    uint layer;
    uint channel_mask;
    uint flags;
};
struct GBufferTargets {
    vec4 gb0_;
    vec4 gb1_;
    uvec4 gb2_;
    vec4 gb3_;
};
const float HOGSHADE_PI = 3.1415927;
const float HOGSHADE_INV_PI = 0.31830987;
const float HOGSHADE_ROUGHNESS_BIAS = 0.005;
const float HOGSHADE_IRRADIANCE_OVER_PI = 1.0;
const float HOGSHADE_SH_A0_ = 3.1415927;
const float HOGSHADE_SH_A1_ = 2.0943952;
const float HOGSHADE_SH_A2_ = 0.7853982;
const float HOGSHADE_DIELECTRIC_F0_ = 0.04;
const uint HOGSHADE_MODEL_LAMBERT = 0u;
const uint HOGSHADE_MODEL_LEGACY_V1_ = 1u;
const uint HOGSHADE_MODEL_LEGACY_V2_ = 2u;
const uint HOGSHADE_MODEL_OPENPBR = 3u;
const uint HOGSHADE_DEBUG_NONE = 0u;

smooth in vec3 _vs2fs_location0;
smooth in vec3 _vs2fs_location1;
layout(location = 0) out vec4 _fs2p_location0;

lighting_Incident lighting_incident(LightSource light, vec3 position_ws) {
    lighting_Incident out_ = lighting_Incident(vec3(0.0), 0.0, false);
    float falloff = 0.0;
    float cone = 1.0;
    out_.l_ws = vec3(0.0, 1.0, 0.0);
    out_.attenuation = 0.0;
    out_.valid = false;
    if ((light.kind == 0u)) {
        lighting_Incident _e15 = out_;
        return _e15;
    }
    if ((light.kind == 1u)) {
        out_.l_ws = normalize(light.direction_ws);
        out_.attenuation = light.shadow;
        out_.valid = true;
        lighting_Incident _e26 = out_;
        return _e26;
    }
    vec3 to_light = (light.position_ws - position_ws);
    float dist2_ = max(dot(to_light, to_light), 1e-8);
    float dist = sqrt(dist2_);
    out_.l_ws = (to_light / vec3(dist));
    falloff = (1.0 / dist2_);
    if ((light.range > 0.0)) {
        float ratio = (dist / light.range);
        float window = clamp((1.0 - (((ratio * ratio) * ratio) * ratio)), 0.0, 1.0);
        float _e52 = falloff;
        falloff = ((_e52 * window) * window);
    }
    if ((light.kind == 3u)) {
        vec3 _e61 = out_.l_ws;
        float cos_angle = dot(-(_e61), normalize(light.direction_ws));
        cone = clamp(((cos_angle - light.cone_cos.y) / max((light.cone_cos.x - light.cone_cos.y), 0.0001)), 0.0, 1.0);
        float _e80 = cone;
        float _e81 = cone;
        cone = (_e80 * _e81);
    }
    float _e84 = falloff;
    float _e85 = cone;
    out_.attenuation = ((_e84 * _e85) * light.shadow);
    out_.valid = true;
    lighting_Incident _e91 = out_;
    return _e91;
}

vec3 lighting_radiance(LightSource light_1, lighting_Incident incident) {
    return ((light_1.color * light_1.intensity) * incident.attenuation);
}

FixedSlots16_ lighting_slots_empty() {
    FixedSlots16_ slots_1 = FixedSlots16_(LightSource[16](LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0)), 0u, 0u, 0u, 0u);
    uint i = 0u;
    slots_1.count = 0u;
    bool loop_init = true;
    while(true) {
        if (!loop_init) {
            uint _e18 = i;
            i = (_e18 + 1u);
        }
        loop_init = false;
        uint _e5 = i;
        if ((_e5 < 16u)) {
        } else {
            break;
        }
        {
            uint _e9 = i;
            slots_1.light[_e9].kind = 0u;
            uint _e14 = i;
            slots_1.light[_e14].shadow = 1.0;
        }
    }
    FixedSlots16_ _e21 = slots_1;
    return _e21;
}

vec3 environment_specular(samplerCube specular_cube, EnvironmentIBL env, vec3 r_ws, float roughness) {
    float mip = (clamp(roughness, 0.0, 1.0) * max((env.specular_mip_count - 1.0), 0.0));
    vec4 _e14 = textureLod(specular_cube, vec3(r_ws), mip);
    return (_e14.xyz * env.exposure);
}

vec3 environment_irradiance_cube(samplerCube irradiance_cube, EnvironmentIBL env_1, vec3 n_ws) {
    vec4 _e5 = textureLod(irradiance_cube, vec3(n_ws), 0.0);
    return (_e5.xyz * env_1.exposure);
}

vec3 environment_irradiance_sh9_(EnvironmentIBL env_2, vec3 n_ws_1) {
    vec3 e = vec3(0.0);
    float x = n_ws_1.x;
    float y = n_ws_1.y;
    float z = n_ws_1.z;
    e = (env_2.sh9_[0].xyz * 0.88622755);
    vec3 _e11 = e;
    e = (_e11 + (env_2.sh9_[1].xyz * (1.0233277 * y)));
    vec3 _e19 = e;
    e = (_e19 + (env_2.sh9_[2].xyz * (1.0233277 * z)));
    vec3 _e27 = e;
    e = (_e27 + (env_2.sh9_[3].xyz * (1.0233277 * x)));
    vec3 _e35 = e;
    e = (_e35 + (env_2.sh9_[4].xyz * ((0.8580852 * x) * y)));
    vec3 _e44 = e;
    e = (_e44 + (env_2.sh9_[5].xyz * ((0.8580852 * y) * z)));
    vec3 _e53 = e;
    e = (_e53 + (env_2.sh9_[6].xyz * (0.24770829 * (((3.0 * z) * z) - 1.0))));
    vec3 _e66 = e;
    e = (_e66 + (env_2.sh9_[7].xyz * ((0.8580852 * x) * z)));
    vec3 _e75 = e;
    e = (_e75 + (env_2.sh9_[8].xyz * (0.4290426 * ((x * x) - (y * y)))));
    vec3 _e86 = e;
    return (max((_e86 * HOGSHADE_INV_PI), vec3(0.0)) * env_2.exposure);
}

vec2 environment_brdf_lut(sampler2D lut, float n_dot_v, float roughness_1) {
    vec2 uv = vec2(clamp(n_dot_v, 0.0, 1.0), clamp(roughness_1, 0.0, 1.0));
    vec4 _e12 = textureLod(lut, vec2(uv), 0.0);
    return _e12.xy;
}

EnvironmentIBL environment_default(float mip_count) {
    EnvironmentIBL env_3 = EnvironmentIBL(0.0, 0.0, 0u, 0u, vec4[9](vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0)));
    uint i_1 = 0u;
    env_3.specular_mip_count = mip_count;
    env_3.exposure = 1.0;
    env_3.use_sh9_ = 0u;
    env_3._pad = 0u;
    bool loop_init_1 = true;
    while(true) {
        if (!loop_init_1) {
            uint _e19 = i_1;
            i_1 = (_e19 + 1u);
        }
        loop_init_1 = false;
        uint _e11 = i_1;
        if ((_e11 < 9u)) {
        } else {
            break;
        }
        {
            uint _e15 = i_1;
            env_3.sh9_[_e15] = vec4(0.0);
        }
    }
    EnvironmentIBL _e22 = env_3;
    return _e22;
}

vec2 gbuffer_oct_encode(vec3 n) {
    vec2 p = vec2(0.0);
    float l1_ = ((abs(n.x) + abs(n.y)) + abs(n.z));
    p = (n.xy / vec2(max(l1_, 1e-8)));
    if ((n.z < 0.0)) {
        float _e19 = p.x;
        float sx = ((_e19 >= 0.0) ? 1.0 : -1.0);
        float _e26 = p.y;
        float sy = ((_e26 >= 0.0) ? 1.0 : -1.0);
        vec2 _e34 = p;
        p = ((vec2(1.0) - abs(_e34.yx)) * vec2(sx, sy));
    }
    vec2 _e40 = p;
    return ((_e40 * 0.5) + vec2(0.5));
}

vec3 gbuffer_oct_decode(vec2 e_1) {
    vec3 n_1 = vec3(0.0);
    vec2 p_1 = ((e_1 * 2.0) - vec2(1.0));
    n_1 = vec3(p_1.x, p_1.y, ((1.0 - abs(p_1.x)) - abs(p_1.y)));
    float _e18 = n_1.z;
    float t_2 = clamp(-(_e18), 0.0, 1.0);
    float _e25 = n_1.x;
    float sx_1 = ((_e25 >= 0.0) ? -(t_2) : t_2);
    float _e31 = n_1.y;
    float sy_1 = ((_e31 >= 0.0) ? -(t_2) : t_2);
    float _e36 = n_1.x;
    float _e39 = n_1.y;
    float _e42 = n_1.z;
    n_1 = vec3((_e36 + sx_1), (_e39 + sy_1), _e42);
    vec3 _e44 = n_1;
    return normalize(_e44);
}

GBufferTargets gbuffer_encode_adr002_(SurfaceInputs s, GBufferLayoutAdr002_ layout_meta_1) {
    GBufferTargets t = GBufferTargets(vec4(0.0), vec4(0.0), uvec4(0u), vec4(0.0));
    t.gb0_ = vec4(clamp(s.base_color, vec3(0.0), vec3(1.0)), clamp(s.ao, 0.0, 1.0));
    vec2 _e18 = gbuffer_oct_encode(normalize(s.normal_ws));
    t.gb1_ = vec4(_e18, clamp(s.roughness, 0.0, 1.0), clamp(s.metalness, 0.0, 1.0));
    t.gb2_ = uvec4((layout_meta_1.layer & 255u), (layout_meta_1.channel_mask & 255u), (s.model & 255u), (layout_meta_1.flags & 255u));
    t.gb3_ = vec4(max(s.emissive, vec3(0.0)), 0.0);
    GBufferTargets _e49 = t;
    return _e49;
}

SurfaceInputs gbuffer_decode_adr002_(GBufferTargets t_1) {
    SurfaceInputs s_1 = SurfaceInputs(vec3(0.0), 0.0, 0.0, 0.0, vec3(0.0), vec3(0.0), 0u);
    s_1.base_color = t_1.gb0_.xyz;
    s_1.ao = t_1.gb0_.w;
    vec3 _e11 = gbuffer_oct_decode(t_1.gb1_.xy);
    s_1.normal_ws = _e11;
    s_1.roughness = t_1.gb1_.z;
    s_1.metalness = t_1.gb1_.w;
    s_1.model = t_1.gb2_.z;
    s_1.emissive = t_1.gb3_.xyz;
    SurfaceInputs _e24 = s_1;
    return _e24;
}

ShadingInputs gbuffer_reconstruct(SurfaceInputs s_2, vec3 view_ws_1, vec3 position_ws_1) {
    ShadingInputs i_2 = ShadingInputs(SurfaceInputs(vec3(0.0), 0.0, 0.0, 0.0, vec3(0.0), vec3(0.0), 0u), vec3(0.0), vec3(0.0), vec3(0.0), 0.0);
    i_2.surface = s_2;
    i_2.view_ws = view_ws_1;
    i_2.position_ws = position_ws_1;
    i_2.specular_f0_ = mix(vec3(0.04), s_2.base_color, s_2.metalness);
    i_2.opacity = 1.0;
    ShadingInputs _e15 = i_2;
    return _e15;
}

ShadingInputs lambert_inputs(vec3 base_color, float ao, vec3 emissive, vec3 normal_ws_1, vec3 view_ws_2, vec3 position_ws_2) {
    ShadingInputs i_3 = ShadingInputs(SurfaceInputs(vec3(0.0), 0.0, 0.0, 0.0, vec3(0.0), vec3(0.0), 0u), vec3(0.0), vec3(0.0), vec3(0.0), 0.0);
    i_3.surface.base_color = base_color;
    i_3.surface.metalness = 0.0;
    i_3.surface.roughness = 1.0;
    i_3.surface.ao = ao;
    i_3.surface.emissive = emissive;
    i_3.surface.normal_ws = normalize(normal_ws_1);
    i_3.surface.model = HOGSHADE_MODEL_LAMBERT;
    i_3.view_ws = normalize(view_ws_2);
    i_3.position_ws = position_ws_2;
    i_3.specular_f0_ = vec3(0.04);
    i_3.opacity = 1.0;
    ShadingInputs _e33 = i_3;
    return _e33;
}

vec3 lambert_evaluate_light(ShadingInputs i_4, LightSource light_2) {
    lighting_Incident _e3 = lighting_incident(light_2, i_4.position_ws);
    if (!(_e3.valid)) {
        return vec3(0.0);
    }
    float n_dot_l = max(dot(i_4.surface.normal_ws, _e3.l_ws), 0.0);
    vec3 _e19 = lighting_radiance(light_2, _e3);
    return (((i_4.surface.base_color * HOGSHADE_INV_PI) * n_dot_l) * _e19);
}

vec3 lambert_evaluate_env(ShadingInputs i_5, vec3 irradiance_over_pi) {
    return ((i_5.surface.base_color * irradiance_over_pi) * i_5.surface.ao);
}

vec3 lambert_debug(ShadingInputs i_6, uint mode) {
    switch(mode) {
        case 1u: {
            return i_6.surface.base_color;
        }
        case 2u: {
            return ((i_6.surface.normal_ws * 0.5) + vec3(0.5));
        }
        case 3u: {
            return vec3(i_6.surface.ao);
        }
        case 4u: {
            return i_6.surface.emissive;
        }
        default: {
            return vec3(0.0);
        }
    }
}

vec3 models_evaluate_light(ShadingInputs i_7, LightSource light_3) {
    switch(i_7.surface.model) {
        case 0u: {
            vec3 _e4 = lambert_evaluate_light(i_7, light_3);
            return _e4;
        }
        default: {
            vec3 _e5 = lambert_evaluate_light(i_7, light_3);
            return _e5;
        }
    }
}

vec3 models_evaluate_env(ShadingInputs i_8, vec3 irradiance_over_pi_1) {
    switch(i_8.surface.model) {
        case 0u: {
            vec3 _e4 = lambert_evaluate_env(i_8, irradiance_over_pi_1);
            return _e4;
        }
        default: {
            vec3 _e5 = lambert_evaluate_env(i_8, irradiance_over_pi_1);
            return _e5;
        }
    }
}

vec3 models_debug(ShadingInputs i_9, uint mode_1) {
    switch(i_9.surface.model) {
        case 0u: {
            vec3 _e4 = lambert_debug(i_9, mode_1);
            return _e4;
        }
        default: {
            vec3 _e5 = lambert_debug(i_9, mode_1);
            return _e5;
        }
    }
}

vec3 models_evaluate_slots(ShadingInputs i_10, FixedSlots16_ slots_2) {
    vec3 sum = vec3(0.0);
    uint k = 0u;
    uint n_2 = min(slots_2.count, 16u);
    bool loop_init_2 = true;
    while(true) {
        if (!loop_init_2) {
            uint _e18 = k;
            k = (_e18 + 1u);
        }
        loop_init_2 = false;
        uint _e10 = k;
        if ((_e10 < n_2)) {
        } else {
            break;
        }
        {
            vec3 _e12 = sum;
            uint _e14 = k;
            vec3 _e16 = models_evaluate_light(i_10, slots_2.light[_e14]);
            sum = (_e12 + _e16);
        }
    }
    vec3 _e21 = sum;
    return _e21;
}

ShadingResult models_shade(ShadingInputs i_11, FixedSlots16_ slots_3, vec3 irradiance_over_pi_2, uint debug_mode) {
    ShadingResult r = ShadingResult(vec3(0.0), vec3(0.0));
    vec3 _e6 = models_evaluate_slots(i_11, slots_3);
    vec3 _e7 = models_evaluate_env(i_11, irradiance_over_pi_2);
    r.color = ((_e6 + _e7) + i_11.surface.emissive);
    r.debug = vec3(0.0);
    if ((debug_mode != HOGSHADE_DEBUG_NONE)) {
        vec3 _e18 = models_debug(i_11, debug_mode);
        r.debug = _e18;
    }
    ShadingResult _e19 = r;
    return _e19;
}

void main() {
    vec3 normal_ws = _vs2fs_location0;
    vec3 view_ws = _vs2fs_location1;
    FixedSlots16_ slots = FixedSlots16_(LightSource[16](LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0), LightSource(vec3(0.0), 0u, vec3(0.0), 0.0, vec3(0.0), 0.0, vec2(0.0), 0.0, 0.0)), 0u, 0u, 0u, 0u);
    GBufferLayoutAdr002_ layout_meta = GBufferLayoutAdr002_(0u, 0u, 0u);
    ShadingInputs _e9 = lambert_inputs(vec3(0.8), 1.0, vec3(0.0), normal_ws, view_ws, vec3(0.0));
    FixedSlots16_ _e10 = lighting_slots_empty();
    slots = _e10;
    slots.light[0].kind = 1u;
    slots.light[0].direction_ws = vec3(0.0, 1.0, 0.0);
    slots.light[0].color = vec3(1.0);
    slots.light[0].intensity = 1.0;
    slots.light[0].shadow = 1.0;
    slots.count = 1u;
    EnvironmentIBL _e39 = environment_default(9.0);
    vec3 _e42 = environment_irradiance_sh9_(_e39, _e9.surface.normal_ws);
    FixedSlots16_ _e43 = slots;
    ShadingResult _e45 = models_shade(_e9, _e43, _e42, HOGSHADE_DEBUG_NONE);
    layout_meta.layer = 0u;
    layout_meta.channel_mask = 255u;
    layout_meta.flags = 0u;
    GBufferLayoutAdr002_ _e54 = layout_meta;
    GBufferTargets _e55 = gbuffer_encode_adr002_(_e9.surface, _e54);
    SurfaceInputs _e56 = gbuffer_decode_adr002_(_e55);
    ShadingInputs _e59 = gbuffer_reconstruct(_e56, _e9.view_ws, _e9.position_ws);
    _fs2p_location0 = vec4((_e45.color + (_e59.specular_f0_ * 0.0)), 1.0);
    return;
}

