// HogShade phase 2 spike (plan PR A, task 2): the Maya dx11Shader shell around naga's HLSL.
//
// Everything Maya needs to see (annotated parameters, semantics, techniques) lives here. The
// shading maths lives in ggx_sm50.hlsl, which naga generated from ggx.wgsl and which declares no
// bindings of its own: this shell declares the texture, the sampler and the light and passes them
// into spike_shade(). If fxc compiles this and Maya draws a textured, lit sphere, WGSL stays the
// source language.

#include "ggx_sm50.hlsl"

// --- Maya-provided transforms -----------------------------------------------------------------
float4x4 gWorldXf : World < string UIWidget = "None"; >;
float4x4 gWorldITXf : WorldInverseTranspose < string UIWidget = "None"; >;
float4x4 gWvpXf : WorldViewProjection < string UIWidget = "None"; >;
float4x4 gViewIXf : ViewInverse < string UIWidget = "None"; >;

// --- Material parameters, annotated for the Attribute Editor --------------------------------
Texture2D baseColorMap
<
    string ResourceName = "";
    string UIName = "Base Color Map";
    string ResourceType = "2D";
    int mipmaplevels = 0;
    string UIGroup = "Spike";
    int UIOrder = 10;
>;

SamplerState baseColorSampler
{
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = Wrap;
    AddressV = Wrap;
};

float materialRoughness
<
    string UIName = "Roughness";
    string UIWidget = "Slider";
    float UIMin = 0.0;
    float UIMax = 1.0;
    float UIStep = 0.01;
    string UIGroup = "Spike";
    int UIOrder = 11;
> = 0.3;

float materialMetalness
<
    string UIName = "Metalness";
    string UIWidget = "Slider";
    float UIMin = 0.0;
    float UIMax = 1.0;
    float UIStep = 0.01;
    string UIGroup = "Spike";
    int UIOrder = 12;
> = 0.0;

// --- One light, bound by Maya to "Light 0" (the v2 gather pattern, one slot) -----------------
float3 light0Dir : DIRECTION
<
    string Object = "Light 0";
    string UIName = "Light 0 Direction";
    string Space = "World";
    int UIOrder = 20;
> = { 0.0, -1.0, -1.0 };

float3 light0Color : LIGHTCOLOR
<
    string Object = "Light 0";
    string UIName = "Light 0 Color";
    int UIOrder = 21;
> = { 1.0, 1.0, 1.0 };

float light0Intensity : LIGHTINTENSITY
<
    string Object = "Light 0";
    string UIName = "Light 0 Intensity";
    int UIOrder = 22;
> = 1.0;

// --- Vertex stage ---------------------------------------------------------------------------
struct AppData
{
    float3 position : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

struct Varyings
{
    float4 clip : SV_Position;
    float3 normalWs : TEXCOORD1;
    float3 viewWs : TEXCOORD2;
    float2 uv : TEXCOORD0;
};

Varyings vsMain(AppData input)
{
    Varyings o;
    float4 posWs = mul(float4(input.position, 1.0), gWorldXf);
    o.clip = mul(float4(input.position, 1.0), gWvpXf);
    o.normalWs = normalize(mul(float4(input.normal, 0.0), gWorldITXf).xyz);
    o.viewWs = normalize(gViewIXf[3].xyz - posWs.xyz);
    o.uv = input.uv;
    return o;
}

// --- Pixel stage: build the core's light struct and call the core -------------------------
float4 psMain(Varyings input) : SV_Target
{
    SpikeLight light;
    light.direction_ws = normalize(-light0Dir);  // Maya's DIRECTION points from the light; the core wants towards it
    light.intensity = light0Intensity;
    light.color = light0Color;
    light._pad = 0.0;
    float3 n = normalize(input.normalWs);
    float3 v = normalize(input.viewWs);
    float3 c = spike_shade(baseColorMap, baseColorSampler, light, n, v, input.uv, materialRoughness, materialMetalness);
    return float4(c, 1.0);
}

technique11 Main
<
    string index_buffer_type = "PNAndUV";
    string transparency = "opaque";
>
{
    pass p0
    {
        SetVertexShader(CompileShader(vs_5_0, vsMain()));
        SetHullShader(NULL);
        SetDomainShader(NULL);
        SetGeometryShader(NULL);
        SetPixelShader(CompileShader(ps_5_0, psMain()));
    }
}
