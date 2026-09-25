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
    float specular_weight;
    int _end_pad_0;
    int _end_pad_1;
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

struct EnvironmentSamples {
    float3 irradiance_over_pi;
    int _pad1_0;
    float3 specular;
    int _pad2_0;
    float2 brdf;
    int _pad3_0;
    int _pad3_1;
    float3 hemisphere;
    uint hemisphere_mode;
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

struct legacy_v2_Material {
    float3 base_color;
    float roughness;
    float metalness;
    float specular;
    float specular_tint;
    float ior;
    float bump_intensity;
    uint use_vertex_color;
    uint use_vertex_ao;
    uint use_vertex_alpha;
    uint has_alpha;
    int _pad11_0;
    int _pad11_1;
    int _pad11_2;
    float3 normal_flip;
    uint flip_backface_normals;
    uint specular_f0_from_map;
    int _end_pad_0;
    int _end_pad_1;
    int _end_pad_2;
};

struct legacy_v2_Samples {
    float4 base_color;
    float roughness;
    float metalness;
    int _pad3_0;
    int _pad3_1;
    float3 specular_f0_;
    float specular_amount;
    float ao;
    float cavity;
    int _pad7_0;
    int _pad7_1;
    float3 emissive;
    int _pad8_0;
    float3 normal_ts;
    int _end_pad_0;
};

struct legacy_v2_Geometry {
    float3 normal_ws;
    int _pad1_0;
    float3 tangent_ws;
    int _pad2_0;
    float3 binormal_ws;
    int _pad3_0;
    float3 view_ws;
    int _pad4_0;
    float3 position_ws;
    int _pad5_0;
    float4 vertex_color;
    float3 vertex_ao;
    uint front_face;
};

struct legacy_v2_Terms {
    float3 diffuse;
    int _pad1_0;
    float3 specular;
    int _end_pad_0;
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
    float3 view_ws_4 : LOC1;
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

float brdf_g1_schlick_ggx(float n_dot_x, float k)
{
    return (1.0 / max(((n_dot_x * (1.0 - k)) + k), 1e-5));
}

float brdf_vis_hable(float n_dot_l_1, float n_dot_v_1, float alpha_2)
{
    float k_4 = (alpha_2 * 0.5);
    const float _e5 = brdf_g1_schlick_ggx(n_dot_l_1, k_4);
    const float _e6 = brdf_g1_schlick_ggx(n_dot_v_1, k_4);
    return (_e5 * _e6);
}

float3 brdf_lambert(float3 albedo)
{
    return (albedo * HOGSHADE_INV_PI);
}

float3 brdf_burley(float3 albedo_1, float roughness, float n_dot_v_2, float n_dot_l_2, float v_dot_h_2)
{
    float fd90_ = (0.5 + (((2.0 * roughness) * v_dot_h_2) * v_dot_h_2));
    float light_scatter = (1.0 + ((fd90_ - 1.0) * pow((1.0 - n_dot_l_2), 5.0)));
    float view_scatter = (1.0 + ((fd90_ - 1.0) * pow((1.0 - n_dot_v_2), 5.0)));
    return (((albedo_1 * HOGSHADE_INV_PI) * light_scatter) * view_scatter);
}

float3 brdf_specular_ggx(float3 n, float3 v, float3 l, float3 f0_2, float roughness_1)
{
    float3 h = normalize((v + l));
    float n_dot_l_3 = max(dot(n, l), 0.0);
    float n_dot_v_4 = max(dot(n, v), 0.0001);
    float n_dot_h_1 = max(dot(n, h), 0.0);
    float v_dot_h_3 = max(dot(v, h), 0.0);
    float alpha_3 = max(((roughness_1 + HOGSHADE_ROUGHNESS_BIAS) * (roughness_1 + HOGSHADE_ROUGHNESS_BIAS)), 0.0001);
    const float _e26 = brdf_ggx_d(n_dot_h_1, alpha_3);
    const float _e27 = brdf_smith_v_height_correlated(n_dot_v_4, n_dot_l_3, alpha_3);
    const float3 _e28 = brdf_fresnel_schlick(f0_2, v_dot_h_3);
    return (((_e26 * _e27) * _e28) * n_dot_l_3);
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

float2 environment_brdf_lut(Texture2D<float4> lut, SamplerState lut_sampler, float n_dot_v_3, float roughness_3)
{
    float2 uv_1 = float2(clamp(n_dot_v_3, 0.0, 1.0), clamp(roughness_3, 0.0, 1.0));
    float4 _e12 = lut.SampleLevel(lut_sampler, uv_1, 0.0);
    return _e12.xy;
}

float3 environment_hemisphere(float3 sky, float3 ground, float3 n_ws_2, float3 up_ws)
{
    return lerp(ground, sky, clamp(((dot(n_ws_2, up_ws) * 0.5) + 0.5), 0.0, 1.0));
}

EnvironmentSamples environment_samples_none()
{
    EnvironmentSamples s = (EnvironmentSamples)0;

    s.irradiance_over_pi = (0.0).xxx;
    s.specular = (0.0).xxx;
    s.brdf = float2(1.0, 0.0);
    s.hemisphere = (0.0).xxx;
    s.hemisphere_mode = 0u;
    EnvironmentSamples _e16 = s;
    const EnvironmentSamples environmentsamples = _e16;
    return environmentsamples;
}

EnvironmentSamples environment_sample(TextureCube<float4> specular_cube_1, TextureCube<float4> irradiance_cube_1, Texture2D<float4> lut_1, SamplerState cube_sampler_2, SamplerState lut_sampler_1, EnvironmentIBL env_3, float3 n_ws_3, float3 view_ws_1, float roughness_4)
{
    EnvironmentSamples s_1 = (EnvironmentSamples)0;

    const EnvironmentSamples _e9 = environment_samples_none();
    s_1 = _e9;
    float3 r_ws_1 = reflect(-(view_ws_1), n_ws_3);
    float n_dot_v_5 = max(dot(n_ws_3, view_ws_1), 0.0);
    if ((env_3.use_sh9_ != 0u)) {
        const float3 _e20 = environment_irradiance_sh9_(env_3, n_ws_3);
        s_1.irradiance_over_pi = _e20;
    } else {
        const float3 _e22 = environment_irradiance_cube(irradiance_cube_1, cube_sampler_2, env_3, n_ws_3);
        s_1.irradiance_over_pi = _e22;
    }
    const float3 _e24 = environment_specular(specular_cube_1, cube_sampler_2, env_3, r_ws_1, roughness_4);
    s_1.specular = _e24;
    const float2 _e26 = environment_brdf_lut(lut_1, lut_sampler_1, n_dot_v_5, roughness_4);
    s_1.brdf = _e26;
    EnvironmentSamples _e27 = s_1;
    const EnvironmentSamples environmentsamples_1 = _e27;
    return environmentsamples_1;
}

EnvironmentIBL environment_default(float mip_count)
{
    EnvironmentIBL env_4 = (EnvironmentIBL)0;
    uint i_1 = 0u;

    env_4.specular_mip_count = mip_count;
    env_4.exposure = 1.0;
    env_4.use_sh9_ = 0u;
    env_4._pad = 0u;
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
            env_4.sh9_[min(uint(_e15), 8u)] = (0.0).xxxx;
        }
    }
    EnvironmentIBL _e22 = env_4;
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
    float t_5 = clamp(-(_e18), 0.0, 1.0);
    float _e25 = n_2.x;
    float sx_1 = ((_e25 >= 0.0) ? -(t_5) : t_5);
    float _e31 = n_2.y;
    float sy_1 = ((_e31 >= 0.0) ? -(t_5) : t_5);
    float _e36 = n_2.x;
    float _e39 = n_2.y;
    float _e42 = n_2.z;
    n_2 = float3((_e36 + sx_1), (_e39 + sy_1), _e42);
    float3 _e44 = n_2;
    return normalize(_e44);
}

GBufferTargets gbuffer_encode_adr002_(SurfaceInputs s_2, GBufferLayoutAdr002_ layout_meta_1)
{
    GBufferTargets t = (GBufferTargets)0;

    t.gb0_ = float4(clamp(s_2.base_color, (0.0).xxx, (1.0).xxx), clamp(s_2.ao, 0.0, 1.0));
    const float2 _e18 = gbuffer_oct_encode(normalize(s_2.normal_ws));
    t.gb1_ = float4(_e18, clamp(s_2.roughness, 0.0, 1.0), clamp(s_2.metalness, 0.0, 1.0));
    t.gb2_ = uint4((layout_meta_1.layer & 255u), (layout_meta_1.channel_mask & 255u), (s_2.model & 255u), (layout_meta_1.flags & 255u));
    t.gb3_ = float4(max(s_2.emissive, (0.0).xxx), 0.0);
    GBufferTargets _e49 = t;
    const GBufferTargets gbuffertargets = _e49;
    return gbuffertargets;
}

GBufferTargets gbuffer_encode_from_inputs(ShadingInputs i_2, GBufferLayoutAdr002_ layout_meta_2)
{
    SurfaceInputs s_3 = (SurfaceInputs)0;

    s_3 = i_2.surface;
    float _e6 = s_3.ao;
    s_3.ao = (_e6 * i_2.cavity);
    SurfaceInputs _e9 = s_3;
    const GBufferTargets _e10 = gbuffer_encode_adr002_(_e9, layout_meta_2);
    const GBufferTargets gbuffertargets_1 = _e10;
    return gbuffertargets_1;
}

SurfaceInputs gbuffer_decode_adr002_(GBufferTargets t_1)
{
    SurfaceInputs s_4 = (SurfaceInputs)0;

    s_4.base_color = t_1.gb0_.xyz;
    s_4.ao = t_1.gb0_.w;
    const float3 _e11 = gbuffer_oct_decode(t_1.gb1_.xy);
    s_4.normal_ws = _e11;
    s_4.roughness = t_1.gb1_.z;
    s_4.metalness = t_1.gb1_.w;
    s_4.model = t_1.gb2_.z;
    s_4.emissive = t_1.gb3_.xyz;
    SurfaceInputs _e24 = s_4;
    const SurfaceInputs surfaceinputs = _e24;
    return surfaceinputs;
}

ShadingInputs gbuffer_reconstruct(SurfaceInputs s_5, float3 view_ws_2, float3 position_ws_1)
{
    ShadingInputs i_3 = (ShadingInputs)0;

    i_3.surface = s_5;
    i_3.view_ws = view_ws_2;
    i_3.position_ws = position_ws_1;
    i_3.specular_f0_ = lerp((0.04).xxx, s_5.base_color, s_5.metalness);
    i_3.cavity = 1.0;
    i_3.opacity = 1.0;
    i_3.specular_weight = 1.0;
    ShadingInputs _e19 = i_3;
    const ShadingInputs shadinginputs = _e19;
    return shadinginputs;
}

ShadingInputs lambert_inputs(float3 base_color, float ao, float3 emissive, float3 normal_ws_1, float3 view_ws_3, float3 position_ws_2)
{
    ShadingInputs i_4 = (ShadingInputs)0;

    i_4.surface.base_color = base_color;
    i_4.surface.metalness = 0.0;
    i_4.surface.roughness = 1.0;
    i_4.surface.ao = ao;
    i_4.surface.emissive = emissive;
    i_4.surface.normal_ws = normalize(normal_ws_1);
    i_4.surface.model = HOGSHADE_MODEL_LAMBERT;
    i_4.view_ws = normalize(view_ws_3);
    i_4.position_ws = position_ws_2;
    i_4.specular_f0_ = (0.04).xxx;
    i_4.cavity = 1.0;
    i_4.opacity = 1.0;
    i_4.specular_weight = 1.0;
    ShadingInputs _e37 = i_4;
    const ShadingInputs shadinginputs_1 = _e37;
    return shadinginputs_1;
}

float3 lambert_evaluate_light(ShadingInputs i_5, LightSource light_2, EnvironmentSamples env_5)
{
    const lighting_Incident _e4 = lighting_incident(light_2, i_5.position_ws);
    if (!(_e4.valid)) {
        return (0.0).xxx;
    }
    float n_dot_l_4 = max(dot(i_5.surface.normal_ws, _e4.l_ws), 0.0);
    const float3 _e20 = lighting_radiance(light_2, _e4);
    return (((i_5.surface.base_color * HOGSHADE_INV_PI) * n_dot_l_4) * _e20);
}

float3 lambert_evaluate_env(ShadingInputs i_6, EnvironmentSamples env_6)
{
    return ((i_6.surface.base_color * env_6.irradiance_over_pi) * i_6.surface.ao);
}

float3 lambert_debug(ShadingInputs i_7, FixedSlots16_ slots_2, EnvironmentSamples env_7, uint mode)
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

bool legacy_v2_flag(uint f)
{
    return (f != 0u);
}

float legacy_v2_alpha_biased(float roughness_5)
{
    float rough_a = (roughness_5 * roughness_5);
    return ((rough_a * 0.995) + HOGSHADE_ROUGHNESS_BIAS);
}

float legacy_v2_roughness_biased(float roughness_6)
{
    return ((roughness_6 * 0.995) + HOGSHADE_ROUGHNESS_BIAS);
}

float legacy_v2_luminance(float3 c)
{
    return (((0.3 * c.x) + (0.6 * c.y)) + (0.1 * c.z));
}

float legacy_v2_f0_from_ior(float ior)
{
    float n_f0_ = abs(((1.0 - ior) / (1.0 + ior)));
    return (n_f0_ * n_f0_);
}

float3 legacy_v2_normal_ts(legacy_v2_Material m, legacy_v2_Samples s_6, bool front_face)
{
    float3 n_ts = (float3)0;
    bool local = (bool)0;

    float3 raw = s_6.normal_ts;
    float z_1 = sqrt((1.0 - clamp(dot(raw.xy, raw.xy), 0.0, 1.0)));
    n_ts = (float3((raw.xy * m.bump_intensity), z_1) * m.normal_flip);
    const bool _e21 = legacy_v2_flag(m.flip_backface_normals);
    if (_e21) {
        local = !(front_face);
    } else {
        local = false;
    }
    bool _e26 = local;
    if (_e26) {
        float3 _e27 = n_ts;
        n_ts = -(_e27);
    }
    float3 _e29 = n_ts;
    return _e29;
}

ShadingInputs legacy_v2_inputs(legacy_v2_Material m_1, legacy_v2_Samples s_7, legacy_v2_Geometry g)
{
    ShadingInputs i_8 = (ShadingInputs)0;
    float3 base_lin = (float3)0;
    float ao_1 = (float)0;
    float opacity = 1.0;
    float3 f0_3 = (float3)0;
    float3 ctint = (1.0).xxx;

    base_lin = (m_1.base_color * s_7.base_color.xyz);
    const bool _e10 = legacy_v2_flag(m_1.use_vertex_color);
    if (_e10) {
        float3 _e11 = base_lin;
        base_lin = (_e11 * g.vertex_color.xyz);
    }
    float roughness_7 = (s_7.roughness * m_1.roughness);
    float metalness = (s_7.metalness * m_1.metalness);
    ao_1 = lerp(1.0, s_7.ao, m_1.bump_intensity);
    const bool _e27 = legacy_v2_flag(m_1.use_vertex_ao);
    if (_e27) {
        float _e28 = ao_1;
        ao_1 = (_e28 * g.vertex_ao.x);
    }
    const bool _e35 = legacy_v2_flag(m_1.has_alpha);
    if (_e35) {
        opacity = s_7.base_color.w;
    }
    const bool _e39 = legacy_v2_flag(m_1.use_vertex_alpha);
    if (_e39) {
        float _e40 = opacity;
        opacity = (_e40 * g.vertex_color.w);
    }
    const bool _e45 = legacy_v2_flag(g.front_face);
    const float3 _e46 = legacy_v2_normal_ts(m_1, s_7, _e45);
    float3 n_ws_5 = normalize((((_e46.x * g.tangent_ws) + (_e46.y * g.binormal_ws)) + (_e46.z * g.normal_ws)));
    const float _e60 = legacy_v2_f0_from_ior(m_1.ior);
    f0_3 = (_e60).xxx;
    const bool _e64 = legacy_v2_flag(m_1.specular_f0_from_map);
    if (_e64) {
        f0_3 = s_7.specular_f0_;
    }
    float3 _e66 = base_lin;
    const float _e67 = legacy_v2_luminance(_e66);
    if ((_e67 > 0.0)) {
        float3 _e73 = base_lin;
        ctint = (_e73 / (_e67).xxx);
    }
    float3 _e77 = f0_3;
    float3 _e81 = ctint;
    float3 _e85 = base_lin;
    float3 cspec0_ = lerp(((m_1.specular * _e77) * lerp((1.0).xxx, _e81, m_1.specular_tint)), _e85, metalness);
    float3 _e89 = base_lin;
    i_8.surface.base_color = _e89;
    i_8.surface.metalness = metalness;
    i_8.surface.roughness = roughness_7;
    float _e96 = ao_1;
    i_8.surface.ao = _e96;
    i_8.surface.emissive = s_7.emissive;
    i_8.surface.normal_ws = n_ws_5;
    i_8.surface.model = HOGSHADE_MODEL_LEGACY_V2_;
    i_8.view_ws = normalize(g.view_ws);
    i_8.position_ws = g.position_ws;
    i_8.specular_f0_ = cspec0_;
    i_8.cavity = s_7.cavity;
    float _e114 = opacity;
    i_8.opacity = _e114;
    i_8.specular_weight = (m_1.specular * s_7.specular_amount);
    ShadingInputs _e119 = i_8;
    const ShadingInputs shadinginputs_2 = _e119;
    return shadinginputs_2;
}

float legacy_v2_n_dot_v(ShadingInputs i_9)
{
    return (abs(dot(i_9.surface.normal_ws, i_9.view_ws)) + 0.0001);
}

float3 legacy_v2_c_spec(ShadingInputs i_10, EnvironmentSamples env_8)
{
    return ((lerp(i_10.specular_f0_, i_10.surface.base_color, i_10.surface.metalness) * env_8.brdf.x) + (env_8.brdf.y).xxx);
}

legacy_v2_Terms legacy_v2_light_terms(ShadingInputs i_11, LightSource light_3)
{
    legacy_v2_Terms t_2 = (legacy_v2_Terms)0;

    t_2.diffuse = (0.0).xxx;
    t_2.specular = (0.0).xxx;
    const lighting_Incident _e10 = lighting_incident(light_3, i_11.position_ws);
    if (!(_e10.valid)) {
        legacy_v2_Terms _e13 = t_2;
        const legacy_v2_Terms legacy_v2_terms = _e13;
        return legacy_v2_terms;
    }
    float3 n_3 = i_11.surface.normal_ws;
    float3 v_1 = i_11.view_ws;
    float3 l_1 = _e10.l_ws;
    float3 h_1 = normalize((l_1 + v_1));
    const float _e20 = legacy_v2_n_dot_v(i_11);
    float n_dot_l_5 = clamp(dot(n_3, l_1), 0.0, 1.0);
    float l_dot_h = clamp(dot(l_1, h_1), 0.0, 1.0);
    float n_dot_h_2 = clamp(dot(n_3, h_1), 0.0, 1.0);
    const float _e35 = legacy_v2_alpha_biased(i_11.surface.roughness);
    const float3 _e38 = brdf_burley((1.0).xxx, _e35, _e20, n_dot_l_5, l_dot_h);
    float diffuse_term = _e38.x;
    const float _e40 = brdf_ggx_d(n_dot_h_2, _e35);
    const float3 _e44 = brdf_fresnel_schlick((i_11.specular_f0_.x).xxx, l_dot_h);
    float f_1 = _e44.x;
    const float _e46 = brdf_vis_hable(n_dot_l_5, _e20, _e35);
    float specular_term = (((n_dot_l_5 * _e40) * f_1) * _e46);
    const float3 _e50 = lighting_radiance(light_3, _e10);
    t_2.diffuse = ((diffuse_term * _e50) * n_dot_l_5);
    t_2.specular = ((specular_term * _e50) * n_dot_l_5);
    legacy_v2_Terms _e57 = t_2;
    const legacy_v2_Terms legacy_v2_terms_1 = _e57;
    return legacy_v2_terms_1;
}

float3 legacy_v2_composite(ShadingInputs i_12, EnvironmentSamples env_9, legacy_v2_Terms t_3)
{
    float3 base = i_12.surface.base_color;
    float3 m_color = (base * (1.0 - i_12.surface.metalness));
    const float3 _e10 = legacy_v2_c_spec(i_12, env_9);
    float ao_2 = i_12.surface.ao;
    return (((t_3.diffuse * m_color) * ao_2) + (((((t_3.specular * _e10) * i_12.specular_weight) * base) * ao_2) * i_12.cavity));
}

legacy_v2_Terms legacy_v2_env_terms(EnvironmentSamples env_10)
{
    legacy_v2_Terms t_4 = (legacy_v2_Terms)0;

    t_4.diffuse = env_10.irradiance_over_pi;
    t_4.specular = env_10.specular;
    if ((env_10.hemisphere_mode == 1u)) {
        float3 _e11 = t_4.diffuse;
        t_4.diffuse = (_e11 + env_10.hemisphere);
        float3 _e16 = t_4.specular;
        t_4.specular = (_e16 + env_10.hemisphere);
    } else {
        if ((env_10.hemisphere_mode == 2u)) {
            float3 _e24 = t_4.diffuse;
            t_4.diffuse = (_e24 * env_10.hemisphere);
            float3 _e29 = t_4.specular;
            t_4.specular = (_e29 * env_10.hemisphere);
        }
    }
    legacy_v2_Terms _e32 = t_4;
    const legacy_v2_Terms legacy_v2_terms_2 = _e32;
    return legacy_v2_terms_2;
}

float3 legacy_v2_evaluate_light(ShadingInputs i_13, LightSource light_4, EnvironmentSamples env_11)
{
    const legacy_v2_Terms _e3 = legacy_v2_light_terms(i_13, light_4);
    const float3 _e4 = legacy_v2_composite(i_13, env_11, _e3);
    return _e4;
}

float3 legacy_v2_evaluate_env(ShadingInputs i_14, EnvironmentSamples env_12)
{
    const legacy_v2_Terms _e2 = legacy_v2_env_terms(env_12);
    const float3 _e3 = legacy_v2_composite(i_14, env_12, _e2);
    return _e3;
}

bool legacy_v2_debug_is_inputs_mode(uint mode_1)
{
    switch(mode_1) {
        case 1u:
        case 2u:
        case 5u:
        case 6u:
        case 11u:
        case 12u:
        case 13u:
        case 14u:
        case 15u:
        case 25u:
        case 30u:
        case 31u: {
            return true;
        }
        default: {
            return false;
        }
    }
}

float3 legacy_v2_debug_inputs(legacy_v2_Material m_2, legacy_v2_Samples s_8, legacy_v2_Geometry g_1, float2 uv, float self_shadow, float3 sky_1, float3 ground_1, float3 up_ws_1, uint mode_2)
{
    float3 base_lin_1 = (float3)0;
    float3 ctint_1 = (1.0).xxx;
    float3 f0_4 = (float3)0;
    float3 c_1 = (0.0).xxx;

    base_lin_1 = (m_2.base_color * s_8.base_color.xyz);
    const bool _e15 = legacy_v2_flag(m_2.use_vertex_color);
    if (_e15) {
        float3 _e16 = base_lin_1;
        base_lin_1 = (_e16 * g_1.vertex_color.xyz);
    }
    float3 _e20 = base_lin_1;
    const float _e21 = legacy_v2_luminance(_e20);
    if ((_e21 > 0.0)) {
        float3 _e27 = base_lin_1;
        ctint_1 = (_e27 / (_e21).xxx);
    }
    const float _e31 = legacy_v2_f0_from_ior(m_2.ior);
    f0_4 = (_e31).xxx;
    const bool _e35 = legacy_v2_flag(m_2.specular_f0_from_map);
    if (_e35) {
        f0_4 = s_8.specular_f0_;
    }
    switch(mode_2) {
        case 1u: {
            return s_8.base_color.xyz;
        }
        case 2u: {
            return (s_8.base_color.w).xxx;
        }
        case 5u: {
            return g_1.vertex_color.xyz;
        }
        case 6u: {
            return (g_1.vertex_color.w).xxx;
        }
        case 11u: {
            return ((s_8.normal_ts * 0.5) + (0.5).xxx);
        }
        case 12u: {
            return s_8.normal_ts;
        }
        case 13u: {
            float _e55 = f0_4.x;
            return (_e55).xxx;
        }
        case 14u: {
            return (_e21).xxx;
        }
        case 15u: {
            float3 _e58 = ctint_1;
            return _e58;
        }
        case 25u: {
            const float3 _e61 = environment_hemisphere(sky_1, ground_1, normalize(g_1.normal_ws), up_ws_1);
            return _e61;
        }
        case 30u: {
            if ((uv.x < 0.0)) {
                c_1 = float3(0.0, 1.0, 0.0);
            }
            if ((uv.y < 0.0)) {
                c_1 = float3(0.0, 0.0, 1.0);
            }
            if ((uv.x > 1.0)) {
                c_1 = float3(1.0, 0.0, 0.0);
            }
            if ((uv.y > 1.0)) {
                c_1 = float3(1.0, 0.0, 1.0);
            }
            float3 _e93 = c_1;
            return _e93;
        }
        case 31u: {
            return (self_shadow).xxx;
        }
        default: {
            return (0.0).xxx;
        }
    }
}

float3 legacy_v2_triplanar_weights(float3 n_ws_4)
{
    float3 a_1 = abs(normalize(n_ws_4));
    return smoothstep((0.57357645).xxx, (0.81915206).xxx, a_1);
}

float3 legacy_v2_debug(ShadingInputs i_15, FixedSlots16_ slots_3, EnvironmentSamples env_13, uint mode_3)
{
    float3 sum = (0.0).xxx;
    uint k_1 = 0u;
    legacy_v2_Terms direct = (legacy_v2_Terms)0;
    uint k_2 = 0u;

    float3 base_1 = i_15.surface.base_color;
    float rough = i_15.surface.roughness;
    float rough_a_1 = (rough * rough);
    const float _e9 = legacy_v2_alpha_biased(rough);
    float3 n_vis = ((i_15.surface.normal_ws * 0.5) + (0.5).xxx);
    const float _e17 = legacy_v2_luminance(base_1);
    switch(mode_3) {
        case 0u: {
            uint n_4 = min(slots_3.count, 16u);
            uint2 loop_bound_2 = uint2(4294967295u, 4294967295u);
            bool loop_init_2 = true;
            while(true) {
                if (all(loop_bound_2 == uint2(0u, 0u))) { break; }
                loop_bound_2 -= uint2(loop_bound_2.y == 0u, 1u);
                if (!loop_init_2) {
                    uint _e34 = k_1;
                    k_1 = (_e34 + 1u);
                }
                loop_init_2 = false;
                uint _e26 = k_1;
                if ((_e26 < n_4)) {
                } else {
                    break;
                }
                {
                    float3 _e28 = sum;
                    uint _e30 = k_1;
                    const float3 _e32 = legacy_v2_evaluate_light(i_15, slots_3.light[min(uint(_e30), 15u)], env_13);
                    sum = (_e28 + _e32);
                }
            }
            float3 _e37 = sum;
            const float3 _e38 = legacy_v2_evaluate_env(i_15, env_13);
            return ((_e37 + _e38) + i_15.surface.emissive);
        }
        case 1u:
        case 3u: {
            return base_1;
        }
        case 2u:
        case 6u: {
            return (i_15.opacity).xxx;
        }
        case 4u: {
            return (base_1 * (1.0 - i_15.surface.metalness));
        }
        case 5u: {
            return (1.0).xxx;
        }
        case 7u: {
            return (i_15.surface.metalness).xxx;
        }
        case 8u:
        case 19u: {
            return (rough).xxx;
        }
        case 9u: {
            return (i_15.surface.ao).xxx;
        }
        case 10u: {
            return (i_15.cavity).xxx;
        }
        case 11u:
        case 12u: {
            return n_vis;
        }
        case 13u: {
            return (i_15.specular_f0_.x).xxx;
        }
        case 14u: {
            return (_e17).xxx;
        }
        case 15u: {
            if ((_e17 > 0.0)) {
                return (base_1 / (_e17).xxx);
            }
            return (1.0).xxx;
        }
        case 16u: {
            return i_15.specular_f0_;
        }
        case 17u:
        case 18u: {
            direct.diffuse = (0.0).xxx;
            direct.specular = (0.0).xxx;
            uint n_5 = min(slots_3.count, 16u);
            uint2 loop_bound_3 = uint2(4294967295u, 4294967295u);
            bool loop_init_3 = true;
            while(true) {
                if (all(loop_bound_3 == uint2(0u, 0u))) { break; }
                loop_bound_3 -= uint2(loop_bound_3.y == 0u, 1u);
                if (!loop_init_3) {
                    uint _e100 = k_2;
                    k_2 = (_e100 + 1u);
                }
                loop_init_3 = false;
                uint _e84 = k_2;
                if ((_e84 < n_5)) {
                } else {
                    break;
                }
                {
                    uint _e87 = k_2;
                    const legacy_v2_Terms _e89 = legacy_v2_light_terms(i_15, slots_3.light[min(uint(_e87), 15u)]);
                    float3 _e92 = direct.diffuse;
                    direct.diffuse = (_e92 + _e89.diffuse);
                    float3 _e97 = direct.specular;
                    direct.specular = (_e97 + _e89.specular);
                }
            }
            const legacy_v2_Terms _e103 = legacy_v2_env_terms(env_13);
            if ((mode_3 == 17u)) {
                float3 _e107 = direct.diffuse;
                return (_e107 + _e103.diffuse);
            }
            float3 _e111 = direct.specular;
            const float3 _e114 = legacy_v2_c_spec(i_15, env_13);
            return (((_e111 + _e103.specular) * _e114) * i_15.specular_weight);
        }
        case 20u: {
            return (rough_a_1).xxx;
        }
        case 21u: {
            return ((rough_a_1 * rough_a_1)).xxx;
        }
        case 22u: {
            return (_e9).xxx;
        }
        case 23u: {
            return ((_e9 * _e9)).xxx;
        }
        case 24u: {
            const float _e124 = legacy_v2_n_dot_v(i_15);
            return (_e124).xxx;
        }
        case 25u:
        case 26u: {
            return env_13.hemisphere;
        }
        case 27u: {
            const legacy_v2_Terms _e127 = legacy_v2_env_terms(env_13);
            return _e127.diffuse;
        }
        case 28u: {
            const legacy_v2_Terms _e129 = legacy_v2_env_terms(env_13);
            return _e129.specular;
        }
        case 29u: {
            const float3 _e131 = legacy_v2_c_spec(i_15, env_13);
            return _e131;
        }
        case 30u: {
            return (0.0).xxx;
        }
        case 31u: {
            return (1.0).xxx;
        }
        case 32u: {
            const float3 _e138 = legacy_v2_triplanar_weights(i_15.surface.normal_ws);
            return _e138;
        }
        default: {
            return (0.0).xxx;
        }
    }
}

float3 models_evaluate_light(ShadingInputs i_16, LightSource light_5, EnvironmentSamples env_14)
{
    switch(i_16.surface.model) {
        case 0u: {
            const float3 _e5 = lambert_evaluate_light(i_16, light_5, env_14);
            return _e5;
        }
        case 2u: {
            const float3 _e6 = legacy_v2_evaluate_light(i_16, light_5, env_14);
            return _e6;
        }
        default: {
            const float3 _e7 = lambert_evaluate_light(i_16, light_5, env_14);
            return _e7;
        }
    }
}

float3 models_evaluate_env(ShadingInputs i_17, EnvironmentSamples env_15)
{
    switch(i_17.surface.model) {
        case 0u: {
            const float3 _e4 = lambert_evaluate_env(i_17, env_15);
            return _e4;
        }
        case 2u: {
            const float3 _e5 = legacy_v2_evaluate_env(i_17, env_15);
            return _e5;
        }
        default: {
            const float3 _e6 = lambert_evaluate_env(i_17, env_15);
            return _e6;
        }
    }
}

float3 models_debug(ShadingInputs i_18, FixedSlots16_ slots_4, EnvironmentSamples env_16, uint mode_4)
{
    switch(i_18.surface.model) {
        case 0u: {
            const float3 _e6 = lambert_debug(i_18, slots_4, env_16, mode_4);
            return _e6;
        }
        case 2u: {
            const float3 _e7 = legacy_v2_debug(i_18, slots_4, env_16, mode_4);
            return _e7;
        }
        default: {
            const float3 _e8 = lambert_debug(i_18, slots_4, env_16, mode_4);
            return _e8;
        }
    }
}

float3 models_evaluate_slots(ShadingInputs i_19, FixedSlots16_ slots_5, EnvironmentSamples env_17)
{
    float3 sum_1 = (0.0).xxx;
    uint k_3 = 0u;

    uint n_6 = min(slots_5.count, 16u);
    uint2 loop_bound_4 = uint2(4294967295u, 4294967295u);
    bool loop_init_4 = true;
    while(true) {
        if (all(loop_bound_4 == uint2(0u, 0u))) { break; }
        loop_bound_4 -= uint2(loop_bound_4.y == 0u, 1u);
        if (!loop_init_4) {
            uint _e19 = k_3;
            k_3 = (_e19 + 1u);
        }
        loop_init_4 = false;
        uint _e11 = k_3;
        if ((_e11 < n_6)) {
        } else {
            break;
        }
        {
            float3 _e13 = sum_1;
            uint _e15 = k_3;
            const float3 _e17 = models_evaluate_light(i_19, slots_5.light[min(uint(_e15), 15u)], env_17);
            sum_1 = (_e13 + _e17);
        }
    }
    float3 _e22 = sum_1;
    return _e22;
}

ShadingResult models_shade(ShadingInputs i_20, FixedSlots16_ slots_6, EnvironmentSamples env_18, uint debug_mode)
{
    ShadingResult r = (ShadingResult)0;

    const float3 _e6 = models_evaluate_slots(i_20, slots_6, env_18);
    const float3 _e7 = models_evaluate_env(i_20, env_18);
    r.color = ((_e6 + _e7) + i_20.surface.emissive);
    r.debug = (0.0).xxx;
    if ((debug_mode != HOGSHADE_DEBUG_NONE)) {
        const float3 _e18 = models_debug(i_20, slots_6, env_18, debug_mode);
        r.debug = _e18;
    }
    ShadingResult _e19 = r;
    const ShadingResult shadingresult = _e19;
    return shadingresult;
}

float4 hogshade_validate(FragmentInput_hogshade_validate fragmentinput_hogshade_validate) : SV_Target0
{
    float3 normal_ws = fragmentinput_hogshade_validate.normal_ws_2;
    float3 view_ws = fragmentinput_hogshade_validate.view_ws_4;
    FixedSlots16_ slots = (FixedSlots16_)0;
    EnvironmentSamples samples = (EnvironmentSamples)0;
    ShadingInputs v2_ = (ShadingInputs)0;
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
    const EnvironmentSamples _e40 = environment_samples_none();
    samples = _e40;
    const float3 _e45 = environment_irradiance_sh9_(_e39, _e9.surface.normal_ws);
    samples.irradiance_over_pi = _e45;
    FixedSlots16_ _e46 = slots;
    EnvironmentSamples _e47 = samples;
    const ShadingResult _e49 = models_shade(_e9, _e46, _e47, HOGSHADE_DEBUG_NONE);
    v2_ = _e9;
    v2_.surface.model = HOGSHADE_MODEL_LEGACY_V2_;
    ShadingInputs _e54 = v2_;
    FixedSlots16_ _e55 = slots;
    EnvironmentSamples _e56 = samples;
    const ShadingResult _e58 = models_shade(_e54, _e55, _e56, 16u);
    layout_meta.layer = 0u;
    layout_meta.channel_mask = 255u;
    layout_meta.flags = 0u;
    GBufferLayoutAdr002_ _e66 = layout_meta;
    const GBufferTargets _e67 = gbuffer_encode_from_inputs(_e9, _e66);
    const SurfaceInputs _e68 = gbuffer_decode_adr002_(_e67);
    const ShadingInputs _e71 = gbuffer_reconstruct(_e68, _e9.view_ws, _e9.position_ws);
    return float4(((_e49.color + (_e71.specular_f0_ * 0.0)) + (_e58.debug * 0.0)), 1.0);
}
