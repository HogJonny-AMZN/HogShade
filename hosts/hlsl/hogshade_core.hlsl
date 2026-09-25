struct SurfaceInputs {
    float3 base_color;
    float metalness;
    float roughness;
    float ao;
    int _pad4_0;
    int _pad4_1;
    float3 emissive;
    int _pad5_0;
    float3 normal_ws;
    uint model;
};

struct ShadingInputs {
    SurfaceInputs surface;
    float3 view_ws;
    int _pad2_0;
    float3 position_ws;
    int _pad3_0;
    float3 specular_f0_;
    float cavity;
    float opacity;
    int _end_pad_0;
    int _end_pad_1;
    int _end_pad_2;
};

struct ShadingResult {
    float3 color;
    int _pad1_0;
    float3 debug;
    int _end_pad_0;
};

struct LightSource {
    float3 position_ws;
    uint kind;
    float3 direction_ws;
    float intensity;
    float3 color;
    float range;
    float2 cone_cos;
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
    float4 sh9_[9];
};

struct lighting_Incident {
    float3 l_ws;
    float attenuation;
    bool valid;
    int _end_pad_0;
    int _end_pad_1;
    int _end_pad_2;
};

struct GBufferLayoutAdr002_ {
    uint layer;
    uint channel_mask;
    uint flags;
};

struct GBufferTargets {
    float4 gb0_;
    float4 gb1_;
    uint4 gb2_;
    float4 gb3_;
};

static const float HOGSHADE_PI = 3.1415927;
static const float HOGSHADE_INV_PI = 0.31830987;
static const float HOGSHADE_ROUGHNESS_BIAS = 0.005;
static const float HOGSHADE_IRRADIANCE_OVER_PI = 1.0;
static const float HOGSHADE_SH_A0_ = 3.1415927;
static const float HOGSHADE_SH_A1_ = 2.0943952;
static const float HOGSHADE_SH_A2_ = 0.7853982;
static const float HOGSHADE_DIELECTRIC_F0_ = 0.04;
static const uint HOGSHADE_MODEL_LAMBERT = 0u;
static const uint HOGSHADE_MODEL_LEGACY_V1_ = 1u;
static const uint HOGSHADE_MODEL_LEGACY_V2_ = 2u;
static const uint HOGSHADE_MODEL_OPENPBR = 3u;
static const uint HOGSHADE_DEBUG_NONE = 0u;

struct FragmentInput_hogshade_validate {
    float3 normal_ws_2 : LOC0;
    float3 view_ws_3 : LOC1;
};

float brdf_ggx_d(float n_dot_h, float alpha)
{
    float a2_ = (alpha * alpha);
    float d = (((n_dot_h * n_dot_h) * (a2_ - 1.0)) + 1.0);
    return (a2_ / ((HOGSHADE_PI * d) * d));
}

float brdf_smith_v_height_correlated(float n_dot_v, float n_dot_l, float alpha_1)
{
    float a2_1 = (alpha_1 * alpha_1);
    float gv = (n_dot_l * sqrt((((n_dot_v * n_dot_v) * (1.0 - a2_1)) + a2_1)));
    float gl = (n_dot_v * sqrt((((n_dot_l * n_dot_l) * (1.0 - a2_1)) + a2_1)));
    return (0.5 / max((gv + gl), 1e-5));
}

float3 brdf_fresnel_schlick(float3 f0_, float v_dot_h)
{
    float fc = pow((1.0 - v_dot_h), 5.0);
    return (f0_ + (((1.0).xxx - f0_) * fc));
}

float3 brdf_fresnel_f82_(float3 f0_1, float3 tint, float v_dot_h_1)
{
    float mu = clamp(v_dot_h_1, 0.0, 1.0);
    float denom = (0.14285715 * pow((1.0 - 0.14285715), 6.0));
    float3 f_schlick_bar = (f0_1 + (((1.0).xxx - f0_1) * pow((1.0 - 0.14285715), 5.0)));
    float3 a = ((f_schlick_bar - (f_schlick_bar * tint)) / (max(denom, 1e-6)).xxx);
    float3 f_schlick = (f0_1 + (((1.0).xxx - f0_1) * pow((1.0 - mu), 5.0)));
    return max((f_schlick - ((a * mu) * pow((1.0 - mu), 6.0))), (0.0).xxx);
}

float3 brdf_lambert(float3 albedo)
{
    return (albedo * HOGSHADE_INV_PI);
}

float3 brdf_burley(float3 albedo_1, float roughness, float n_dot_v_1, float n_dot_l_1, float v_dot_h_2)
{
    float fd90_ = (0.5 + (((2.0 * roughness) * v_dot_h_2) * v_dot_h_2));
    float light_scatter = (1.0 + ((fd90_ - 1.0) * pow((1.0 - n_dot_l_1), 5.0)));
    float view_scatter = (1.0 + ((fd90_ - 1.0) * pow((1.0 - n_dot_v_1), 5.0)));
    return (((albedo_1 * HOGSHADE_INV_PI) * light_scatter) * view_scatter);
}

float3 brdf_specular_ggx(float3 n, float3 v, float3 l, float3 f0_2, float roughness_1)
{
    float3 h = normalize((v + l));
    float n_dot_l_2 = max(dot(n, l), 0.0);
    float n_dot_v_3 = max(dot(n, v), 0.0001);
    float n_dot_h_1 = max(dot(n, h), 0.0);
    float v_dot_h_3 = max(dot(v, h), 0.0);
    float alpha_2 = max(((roughness_1 + HOGSHADE_ROUGHNESS_BIAS) * (roughness_1 + HOGSHADE_ROUGHNESS_BIAS)), 0.0001);
    const float _e26 = brdf_ggx_d(n_dot_h_1, alpha_2);
    const float _e27 = brdf_smith_v_height_correlated(n_dot_v_3, n_dot_l_2, alpha_2);
    const float3 _e28 = brdf_fresnel_schlick(f0_2, v_dot_h_3);
    return (((_e26 * _e27) * _e28) * n_dot_l_2);
}

lighting_Incident lighting_incident(LightSource light, float3 position_ws)
{
    lighting_Incident out_ = (lighting_Incident)0;
    float falloff = (float)0;
    float cone = 1.0;

    out_.l_ws = float3(0.0, 1.0, 0.0);
    out_.attenuation = 0.0;
    out_.valid = false;
    if ((light.kind == 0u)) {
        lighting_Incident _e15 = out_;
        const lighting_Incident lighting_incident_1 = _e15;
        return lighting_incident_1;
    }
    if ((light.kind == 1u)) {
        out_.l_ws = normalize(light.direction_ws);
        out_.attenuation = light.shadow;
        out_.valid = true;
        lighting_Incident _e26 = out_;
        const lighting_Incident lighting_incident_2 = _e26;
        return lighting_incident_2;
    }
    float3 to_light = (light.position_ws - position_ws);
    float dist2_ = max(dot(to_light, to_light), 1e-8);
    float dist = sqrt(dist2_);
    out_.l_ws = (to_light / (dist).xxx);
    falloff = (1.0 / dist2_);
    if ((light.range > 0.0)) {
        float ratio = (dist / light.range);
        float window = clamp((1.0 - (((ratio * ratio) * ratio) * ratio)), 0.0, 1.0);
        float _e52 = falloff;
        falloff = ((_e52 * window) * window);
    }
    if ((light.kind == 3u)) {
        float3 _e61 = out_.l_ws;
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
    const lighting_Incident lighting_incident_3 = _e91;
    return lighting_incident_3;
}

float3 lighting_radiance(LightSource light_1, lighting_Incident incident)
{
    return ((light_1.color * light_1.intensity) * incident.attenuation);
}

FixedSlots16_ lighting_slots_empty()
{
    FixedSlots16_ slots_1 = (FixedSlots16_)0;
    uint i = 0u;

    slots_1.count = 0u;
    uint2 loop_bound = uint2(4294967295u, 4294967295u);
    bool loop_init = true;
    while(true) {
        if (all(loop_bound == uint2(0u, 0u))) { break; }
        loop_bound -= uint2(loop_bound.y == 0u, 1u);
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
            slots_1.light[min(uint(_e9), 15u)].kind = 0u;
            uint _e14 = i;
            slots_1.light[min(uint(_e14), 15u)].shadow = 1.0;
        }
    }
    FixedSlots16_ _e21 = slots_1;
    const FixedSlots16_ fixedslots16_ = _e21;
    return fixedslots16_;
}

float3 environment_specular(TextureCube<float4> specular_cube, SamplerState cube_sampler, EnvironmentIBL env, float3 r_ws, float roughness_2)
{
    float mip = (clamp(roughness_2, 0.0, 1.0) * max((env.specular_mip_count - 1.0), 0.0));
    float4 _e14 = specular_cube.SampleLevel(cube_sampler, r_ws, mip);
    return (_e14.xyz * env.exposure);
}

float3 environment_irradiance_cube(TextureCube<float4> irradiance_cube, SamplerState cube_sampler_1, EnvironmentIBL env_1, float3 n_ws)
{
    float4 _e5 = irradiance_cube.SampleLevel(cube_sampler_1, n_ws, 0.0);
    return (_e5.xyz * env_1.exposure);
}

float3 environment_irradiance_sh9_(EnvironmentIBL env_2, float3 n_ws_1)
{
    float3 e = (float3)0;

    float x = n_ws_1.x;
    float y = n_ws_1.y;
    float z = n_ws_1.z;
    e = (env_2.sh9_[0].xyz * 0.88622755);
    float3 _e11 = e;
    e = (_e11 + (env_2.sh9_[1].xyz * (1.0233277 * y)));
    float3 _e19 = e;
    e = (_e19 + (env_2.sh9_[2].xyz * (1.0233277 * z)));
    float3 _e27 = e;
    e = (_e27 + (env_2.sh9_[3].xyz * (1.0233277 * x)));
    float3 _e35 = e;
    e = (_e35 + (env_2.sh9_[4].xyz * ((0.8580852 * x) * y)));
    float3 _e44 = e;
    e = (_e44 + (env_2.sh9_[5].xyz * ((0.8580852 * y) * z)));
    float3 _e53 = e;
    e = (_e53 + (env_2.sh9_[6].xyz * (0.24770829 * (((3.0 * z) * z) - 1.0))));
    float3 _e66 = e;
    e = (_e66 + (env_2.sh9_[7].xyz * ((0.8580852 * x) * z)));
    float3 _e75 = e;
    e = (_e75 + (env_2.sh9_[8].xyz * (0.4290426 * ((x * x) - (y * y)))));
    float3 _e86 = e;
    return (max((_e86 * HOGSHADE_INV_PI), (0.0).xxx) * env_2.exposure);
}

float2 environment_brdf_lut(Texture2D<float4> lut, SamplerState lut_sampler, float n_dot_v_2, float roughness_3)
{
    float2 uv = float2(clamp(n_dot_v_2, 0.0, 1.0), clamp(roughness_3, 0.0, 1.0));
    float4 _e12 = lut.SampleLevel(lut_sampler, uv, 0.0);
    return _e12.xy;
}

EnvironmentIBL environment_default(float mip_count)
{
    EnvironmentIBL env_3 = (EnvironmentIBL)0;
    uint i_1 = 0u;

    env_3.specular_mip_count = mip_count;
    env_3.exposure = 1.0;
    env_3.use_sh9_ = 0u;
    env_3._pad = 0u;
    uint2 loop_bound_1 = uint2(4294967295u, 4294967295u);
    bool loop_init_1 = true;
    while(true) {
        if (all(loop_bound_1 == uint2(0u, 0u))) { break; }
        loop_bound_1 -= uint2(loop_bound_1.y == 0u, 1u);
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
            env_3.sh9_[min(uint(_e15), 8u)] = (0.0).xxxx;
        }
    }
    EnvironmentIBL _e22 = env_3;
    const EnvironmentIBL environmentibl = _e22;
    return environmentibl;
}

float2 gbuffer_oct_encode(float3 n_1)
{
    float2 p = (float2)0;

    float l1_ = ((abs(n_1.x) + abs(n_1.y)) + abs(n_1.z));
    p = (n_1.xy / (max(l1_, 1e-8)).xx);
    if ((n_1.z < 0.0)) {
        float _e19 = p.x;
        float sx = ((_e19 >= 0.0) ? 1.0 : -1.0);
        float _e26 = p.y;
        float sy = ((_e26 >= 0.0) ? 1.0 : -1.0);
        float2 _e34 = p;
        p = (((1.0).xx - abs(_e34.yx)) * float2(sx, sy));
    }
    float2 _e40 = p;
    return ((_e40 * 0.5) + (0.5).xx);
}

float3 gbuffer_oct_decode(float2 e_1)
{
    float3 n_2 = (float3)0;

    float2 p_1 = ((e_1 * 2.0) - (1.0).xx);
    n_2 = float3(p_1.x, p_1.y, ((1.0 - abs(p_1.x)) - abs(p_1.y)));
    float _e18 = n_2.z;
    float t_2 = clamp(-(_e18), 0.0, 1.0);
    float _e25 = n_2.x;
    float sx_1 = ((_e25 >= 0.0) ? -(t_2) : t_2);
    float _e31 = n_2.y;
    float sy_1 = ((_e31 >= 0.0) ? -(t_2) : t_2);
    float _e36 = n_2.x;
    float _e39 = n_2.y;
    float _e42 = n_2.z;
    n_2 = float3((_e36 + sx_1), (_e39 + sy_1), _e42);
    float3 _e44 = n_2;
    return normalize(_e44);
}

GBufferTargets gbuffer_encode_adr002_(SurfaceInputs s, GBufferLayoutAdr002_ layout_meta_1)
{
    GBufferTargets t = (GBufferTargets)0;

    t.gb0_ = float4(clamp(s.base_color, (0.0).xxx, (1.0).xxx), clamp(s.ao, 0.0, 1.0));
    const float2 _e18 = gbuffer_oct_encode(normalize(s.normal_ws));
    t.gb1_ = float4(_e18, clamp(s.roughness, 0.0, 1.0), clamp(s.metalness, 0.0, 1.0));
    t.gb2_ = uint4((layout_meta_1.layer & 255u), (layout_meta_1.channel_mask & 255u), (s.model & 255u), (layout_meta_1.flags & 255u));
    t.gb3_ = float4(max(s.emissive, (0.0).xxx), 0.0);
    GBufferTargets _e49 = t;
    const GBufferTargets gbuffertargets = _e49;
    return gbuffertargets;
}

GBufferTargets gbuffer_encode_from_inputs(ShadingInputs i_2, GBufferLayoutAdr002_ layout_meta_2)
{
    SurfaceInputs s_1 = (SurfaceInputs)0;

    s_1 = i_2.surface;
    float _e6 = s_1.ao;
    s_1.ao = (_e6 * i_2.cavity);
    SurfaceInputs _e9 = s_1;
    const GBufferTargets _e10 = gbuffer_encode_adr002_(_e9, layout_meta_2);
    const GBufferTargets gbuffertargets_1 = _e10;
    return gbuffertargets_1;
}

SurfaceInputs gbuffer_decode_adr002_(GBufferTargets t_1)
{
    SurfaceInputs s_2 = (SurfaceInputs)0;

    s_2.base_color = t_1.gb0_.xyz;
    s_2.ao = t_1.gb0_.w;
    const float3 _e11 = gbuffer_oct_decode(t_1.gb1_.xy);
    s_2.normal_ws = _e11;
    s_2.roughness = t_1.gb1_.z;
    s_2.metalness = t_1.gb1_.w;
    s_2.model = t_1.gb2_.z;
    s_2.emissive = t_1.gb3_.xyz;
    SurfaceInputs _e24 = s_2;
    const SurfaceInputs surfaceinputs = _e24;
    return surfaceinputs;
}

ShadingInputs gbuffer_reconstruct(SurfaceInputs s_3, float3 view_ws_1, float3 position_ws_1)
{
    ShadingInputs i_3 = (ShadingInputs)0;

    i_3.surface = s_3;
    i_3.view_ws = view_ws_1;
    i_3.position_ws = position_ws_1;
    i_3.specular_f0_ = lerp((0.04).xxx, s_3.base_color, s_3.metalness);
    i_3.cavity = 1.0;
    i_3.opacity = 1.0;
    ShadingInputs _e17 = i_3;
    const ShadingInputs shadinginputs = _e17;
    return shadinginputs;
}

ShadingInputs lambert_inputs(float3 base_color, float ao, float3 emissive, float3 normal_ws_1, float3 view_ws_2, float3 position_ws_2)
{
    ShadingInputs i_4 = (ShadingInputs)0;

    i_4.surface.base_color = base_color;
    i_4.surface.metalness = 0.0;
    i_4.surface.roughness = 1.0;
    i_4.surface.ao = ao;
    i_4.surface.emissive = emissive;
    i_4.surface.normal_ws = normalize(normal_ws_1);
    i_4.surface.model = HOGSHADE_MODEL_LAMBERT;
    i_4.view_ws = normalize(view_ws_2);
    i_4.position_ws = position_ws_2;
    i_4.specular_f0_ = (0.04).xxx;
    i_4.cavity = 1.0;
    i_4.opacity = 1.0;
    ShadingInputs _e35 = i_4;
    const ShadingInputs shadinginputs_1 = _e35;
    return shadinginputs_1;
}

float3 lambert_evaluate_light(ShadingInputs i_5, LightSource light_2)
{
    const lighting_Incident _e3 = lighting_incident(light_2, i_5.position_ws);
    if (!(_e3.valid)) {
        return (0.0).xxx;
    }
    float n_dot_l_3 = max(dot(i_5.surface.normal_ws, _e3.l_ws), 0.0);
    const float3 _e19 = lighting_radiance(light_2, _e3);
    return (((i_5.surface.base_color * HOGSHADE_INV_PI) * n_dot_l_3) * _e19);
}

float3 lambert_evaluate_env(ShadingInputs i_6, float3 irradiance_over_pi)
{
    return ((i_6.surface.base_color * irradiance_over_pi) * i_6.surface.ao);
}

float3 lambert_debug(ShadingInputs i_7, uint mode)
{
    switch(mode) {
        case 1u: {
            return i_7.surface.base_color;
        }
        case 2u: {
            return ((i_7.surface.normal_ws * 0.5) + (0.5).xxx);
        }
        case 3u: {
            return (i_7.surface.ao).xxx;
        }
        case 4u: {
            return i_7.surface.emissive;
        }
        default: {
            return (0.0).xxx;
        }
    }
}

float3 models_evaluate_light(ShadingInputs i_8, LightSource light_3)
{
    switch(i_8.surface.model) {
        case 0u: {
            const float3 _e4 = lambert_evaluate_light(i_8, light_3);
            return _e4;
        }
        default: {
            const float3 _e5 = lambert_evaluate_light(i_8, light_3);
            return _e5;
        }
    }
}

float3 models_evaluate_env(ShadingInputs i_9, float3 irradiance_over_pi_1)
{
    switch(i_9.surface.model) {
        case 0u: {
            const float3 _e4 = lambert_evaluate_env(i_9, irradiance_over_pi_1);
            return _e4;
        }
        default: {
            const float3 _e5 = lambert_evaluate_env(i_9, irradiance_over_pi_1);
            return _e5;
        }
    }
}

float3 models_debug(ShadingInputs i_10, uint mode_1)
{
    switch(i_10.surface.model) {
        case 0u: {
            const float3 _e4 = lambert_debug(i_10, mode_1);
            return _e4;
        }
        default: {
            const float3 _e5 = lambert_debug(i_10, mode_1);
            return _e5;
        }
    }
}

float3 models_evaluate_slots(ShadingInputs i_11, FixedSlots16_ slots_2)
{
    float3 sum = (0.0).xxx;
    uint k = 0u;

    uint n_3 = min(slots_2.count, 16u);
    uint2 loop_bound_2 = uint2(4294967295u, 4294967295u);
    bool loop_init_2 = true;
    while(true) {
        if (all(loop_bound_2 == uint2(0u, 0u))) { break; }
        loop_bound_2 -= uint2(loop_bound_2.y == 0u, 1u);
        if (!loop_init_2) {
            uint _e18 = k;
            k = (_e18 + 1u);
        }
        loop_init_2 = false;
        uint _e10 = k;
        if ((_e10 < n_3)) {
        } else {
            break;
        }
        {
            float3 _e12 = sum;
            uint _e14 = k;
            const float3 _e16 = models_evaluate_light(i_11, slots_2.light[min(uint(_e14), 15u)]);
            sum = (_e12 + _e16);
        }
    }
    float3 _e21 = sum;
    return _e21;
}

ShadingResult models_shade(ShadingInputs i_12, FixedSlots16_ slots_3, float3 irradiance_over_pi_2, uint debug_mode)
{
    ShadingResult r = (ShadingResult)0;

    const float3 _e6 = models_evaluate_slots(i_12, slots_3);
    const float3 _e7 = models_evaluate_env(i_12, irradiance_over_pi_2);
    r.color = ((_e6 + _e7) + i_12.surface.emissive);
    r.debug = (0.0).xxx;
    if ((debug_mode != HOGSHADE_DEBUG_NONE)) {
        const float3 _e18 = models_debug(i_12, debug_mode);
        r.debug = _e18;
    }
    ShadingResult _e19 = r;
    const ShadingResult shadingresult = _e19;
    return shadingresult;
}

float4 hogshade_validate(FragmentInput_hogshade_validate fragmentinput_hogshade_validate) : SV_Target0
{
    float3 normal_ws = fragmentinput_hogshade_validate.normal_ws_2;
    float3 view_ws = fragmentinput_hogshade_validate.view_ws_3;
    FixedSlots16_ slots = (FixedSlots16_)0;
    GBufferLayoutAdr002_ layout_meta = (GBufferLayoutAdr002_)0;

    const ShadingInputs _e9 = lambert_inputs((0.8).xxx, 1.0, (0.0).xxx, normal_ws, view_ws, (0.0).xxx);
    const FixedSlots16_ _e10 = lighting_slots_empty();
    slots = _e10;
    slots.light[0].kind = 1u;
    slots.light[0].direction_ws = float3(0.0, 1.0, 0.0);
    slots.light[0].color = (1.0).xxx;
    slots.light[0].intensity = 1.0;
    slots.light[0].shadow = 1.0;
    slots.count = 1u;
    const EnvironmentIBL _e39 = environment_default(9.0);
    const float3 _e42 = environment_irradiance_sh9_(_e39, _e9.surface.normal_ws);
    FixedSlots16_ _e43 = slots;
    const ShadingResult _e45 = models_shade(_e9, _e43, _e42, HOGSHADE_DEBUG_NONE);
    layout_meta.layer = 0u;
    layout_meta.channel_mask = 255u;
    layout_meta.flags = 0u;
    GBufferLayoutAdr002_ _e53 = layout_meta;
    const GBufferTargets _e54 = gbuffer_encode_from_inputs(_e9, _e53);
    const SurfaceInputs _e55 = gbuffer_decode_adr002_(_e54);
    const ShadingInputs _e58 = gbuffer_reconstruct(_e55, _e9.view_ws, _e9.position_ws);
    return float4((_e45.color + (_e58.specular_f0_ * 0.0)), 1.0);
}
