struct SpikeLight {
    float3 direction_ws;
    float intensity;
    float3 color;
    float _pad;
};

static const float SPIKE_PI = 3.1415927;

struct FragmentInput_spike_fs {
    float3 normal_ws_1 : LOC0;
};

float brdf_ggx_d(float n_dot_h, float alpha)
{
    float a2_ = (alpha * alpha);
    float d = (((n_dot_h * n_dot_h) * (a2_ - 1.0)) + 1.0);
    return (a2_ / ((SPIKE_PI * d) * d));
}

float brdf_smith_v(float n_dot_v, float n_dot_l, float alpha_1)
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

float3 brdf_specular(float3 n, float3 v, float3 l, float3 f0_1, float roughness)
{
    float3 h = normalize((v + l));
    float n_dot_l_1 = max(dot(n, l), 0.0);
    float n_dot_v_1 = max(dot(n, v), 0.0001);
    float n_dot_h_1 = max(dot(n, h), 0.0);
    float v_dot_h_1 = max(dot(v, h), 0.0);
    float alpha_2 = max((roughness * roughness), 0.001);
    const float _e22 = brdf_ggx_d(n_dot_h_1, alpha_2);
    const float _e23 = brdf_smith_v(n_dot_v_1, n_dot_l_1, alpha_2);
    const float3 _e24 = brdf_fresnel_schlick(f0_1, v_dot_h_1);
    return (((_e22 * _e23) * _e24) * n_dot_l_1);
}

float3 spike_shade(Texture2D<float4> base_color_tex, SamplerState base_color_sampler, SpikeLight light, float3 n_1, float3 v_1, float2 uv, float roughness_1, float metalness)
{
    float4 _e8 = base_color_tex.Sample(base_color_sampler, uv);
    float3 base = _e8.xyz;
    float3 f0_2 = lerp((0.04).xxx, base, metalness);
    float3 l_1 = normalize(light.direction_ws);
    float n_dot_l_2 = max(dot(n_1, l_1), 0.0);
    float3 diffuse = (((base * (1.0 - metalness)) / (3.1415927).xxx) * n_dot_l_2);
    const float3 _e25 = brdf_specular(n_1, v_1, l_1, f0_2, roughness_1);
    return (((diffuse + _e25) * light.color) * light.intensity);
}

float4 spike_fs(FragmentInput_spike_fs fragmentinput_spike_fs) : SV_Target0
{
    float3 normal_ws = fragmentinput_spike_fs.normal_ws_1;
    float3 n_2 = normalize(normal_ws);
    const float3 _e5 = brdf_specular(n_2, n_2, n_2, (0.04).xxx, 0.5);
    return float4(_e5, 1.0);
}
