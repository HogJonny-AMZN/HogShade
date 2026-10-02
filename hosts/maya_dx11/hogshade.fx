// HogShade Maya dx11Shader host: the effect shell around the generated shader-model 5 core.
//
// Everything Maya needs to see lives here: annotated parameters, semantics, samplers, the vertex
// stage, the transparency and shadow passes, the techniques. The shading maths lives in
// generated/hogshade_core_sm5.hlsl, which tools/build_shaders.py produced from core/*.wgsl with
// naga; it declares no bindings, so this shell declares the textures, samplers and lights and
// passes them into the core (Docs/superpowers/specs/phase-2-restructure.md, "Hosts in this phase").
//
// The parameter set is the legacy v2 shader's (legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx), same names,
// so scenes and the check tool carry over; the differences are the port's documented deviations
// (core/models/legacy_v2.wgsl header): linear inputs, per-map "use" flags instead of sampling
// black, plain cube slots (no `environment` semantic), sixteen light slots, the core's light
// falloff, and no in-shader tone mapping (Maya's colour management displays the scene-linear
// result). Parallax occlusion mapping stays in this shell as v2 wrote it, marked below, until the
// core's surface module lands in phase 4.
//
// Compile check: fxc /T fx_5_0 /D _MAYA_=1 hogshade.fx (tests/compile/test_build.py).

#include "generated/hogshade_core_sm5.hlsl"

// ------------------------------------------------------------------------------------- Maya

cbuffer UpdatePerFrame : register(b0)
{
    float4x4 viewInv : ViewInverse < string UIWidget = "None"; >;
    float4x4 view : View < string UIWidget = "None"; >;
    float4x4 viewPrj : ViewProjection < string UIWidget = "None"; >;
    bool IsSwatchRender : MayaSwatchRender < string UIWidget = "None"; > = false;
    bool MayaFullScreenGamma : MayaGammaCorrection < string UIWidget = "None"; > = false;
}

cbuffer UpdatePerObject : register(b1)
{
    float4x4 World : World < string UIWidget = "None"; >;
    float4x4 WorldIT : WorldInverseTranspose < string UIWidget = "None"; >;
    float4x4 WorldViewProj : WorldViewProjection < string UIWidget = "None"; >;
}

Texture2D transpDepthTexture : transpdepthtexture < string UIWidget = "None"; >;
Texture2D opaqueDepthTexture : opaquedepthtexture < string UIWidget = "None"; >;

BlendState PMAlphaBlending
{
    AlphaToCoverageEnable = FALSE;
    BlendEnable[0] = TRUE;
    SrcBlend = ONE;
    DestBlend = INV_SRC_ALPHA;
    BlendOp = ADD;
    SrcBlendAlpha = ONE;
    DestBlendAlpha = INV_SRC_ALPHA;
    BlendOpAlpha = ADD;
    RenderTargetWriteMask[0] = 0x0F;
};

// ------------------------------------------------------------------------------------- samplers

SamplerState SamplerAnisoWrap { Filter = ANISOTROPIC; AddressU = Wrap; AddressV = Wrap; };
SamplerState SamplerCubeMap { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; AddressW = Clamp; };
SamplerState SamplerBrdfLUT { Filter = MIN_MAG_MIP_LINEAR; AddressU = Clamp; AddressV = Clamp; };
SamplerState SamplerShadowDepth
{
    Filter = MIN_MAG_MIP_POINT;
    AddressU = Border;
    AddressV = Border;
    BorderColor = float4(1.0f, 1.0f, 1.0f, 1.0f);
};

// ------------------------------------------------------------------------------------- environment

bool useEnvMaps < string UIGroup = "Environment Lighting"; string UIName = "Use Environment Maps"; int UIOrder = 130; > = true;

Texture2D brdfTextureMap
<
    string UIGroup = "Environment Lighting"; string UIName = "BRDF LUT (content/ibl/brdf_lut.dds)";
    string ResourceType = "2D"; string ResourceName = ""; int mipmaplevels = 1; int UIOrder = 131; string ColorSpace = "Raw";
>;

// Plain cube slots (deviation: v2 gave both the `environment` semantic, which bound them to Maya's
// scene environment instead of the cooked cubes). Linear fp16 DDS from hogshade.ibl.
TextureCube diffuseEnvTextureCube
<
    string UIGroup = "Environment Lighting"; string UIName = "Irradiance Cube (E over pi)";
    string ResourceType = "Cube"; string ResourceName = ""; int mipmaplevels = 1; int UIOrder = 132; string ColorSpace = "Raw";
>;
TextureCube specularEnvTextureCube
<
    string UIGroup = "Environment Lighting"; string UIName = "Prefiltered Specular Cube";
    string ResourceType = "Cube"; string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 133; string ColorSpace = "Raw";
>;

float envExposure
<
    string UIGroup = "Environment Lighting"; string UIName = "Environment Exposure (linear, 1 = cooked)";
    string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 16.0; float UIStep = 0.01; int UIOrder = 134;
> = 1.0;

int hemisphericalAmbientMode
<
    string UIGroup = "Environment Lighting"; string UIName = "Hemispherical Ambient";
    string UIFieldNames = "None:Add:Multiply"; int UIOrder = 135;
> = 0;
float3 ambientSkyColor < string UIGroup = "Environment Lighting"; string UIName = "Sky Color"; string UIWidget = "Color"; int UIOrder = 136; > = { 0.0, 1.0, 1.0 };
float ambientSkyIntensity < string UIGroup = "Environment Lighting"; string UIName = "Sky Intensity"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 10.0; float UIStep = 0.01; int UIOrder = 137; > = 0.5;
float3 ambientGroundColor < string UIGroup = "Environment Lighting"; string UIName = "Ground Color"; string UIWidget = "Color"; int UIOrder = 138; > = { 0.087, 0.064, 0.032 };
float ambientGrndIntensity < string UIGroup = "Environment Lighting"; string UIName = "Ground Intensity"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 10.0; float UIStep = 0.01; int UIOrder = 139; > = 0.1;

// ------------------------------------------------------------------------------------- display and model (hand-written; host-only parameters, never material)

int shadingModel
<
    string UIGroup = "Material Properties"; string UIName = "Shading Model";
    string UIFieldNames = "Lambert:Legacy v1 (2015 Disney):Legacy v2 (2017)"; int UIOrder = 149;
> = 2;
bool linearSpaceLighting < string UIGroup = "Material Properties"; string UIName = "Linearise Color Swatches and Vertex Colors (gamma below)"; int UIOrder = 168; > = true;
float gammaCorrectionValue < string UIGroup = "Material Properties"; string UIName = "Swatch Gamma"; string UIWidget = "Slider"; float UIMin = 1.0; float UIMax = 3.0; float UIStep = 0.001; int UIOrder = 169; > = 2.2;

// The material UI below is generated from hogshade/material/schema by tools/generate_material_ui.py
// (the S2 spec); CI checks it. Edit the schema or the host map hogshade/material/hosts/maya_dx11.json.
// BEGIN hogshade.material generated (tools/generate_material_ui.py --write); do not edit
// ------------------------------------------------------------------------------------- material maps (generated)

Texture2D baseColorMap
<
    string UIGroup = "Material Maps"; string UIName = "Base Color Map"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 100; string ColorSpace = "sRGB";
>;
bool useBaseColorMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Base Color Map"; int UIOrder = 101;
> = false;
Texture2D baseNormalMap
<
    string UIGroup = "Material Maps"; string UIName = "Normal Map (tangent, +Y up)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 102; string ColorSpace = "Raw";
>;
bool useNormalMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Normal Map (tangent, +Y up)"; int UIOrder = 103;
> = false;
Texture2D roughnessMap
<
    string UIGroup = "Material Maps"; string UIName = "Roughness Map (green)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 104; string ColorSpace = "Raw";
>;
bool useRoughnessMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Roughness Map (green)"; int UIOrder = 105;
> = false;
Texture2D metalnessMap
<
    string UIGroup = "Material Maps"; string UIName = "Metalness Map (green)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 106; string ColorSpace = "Raw";
>;
bool useMetalnessMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Metalness Map (green)"; int UIOrder = 107;
> = false;
Texture2D specularF0Map
<
    string UIGroup = "Material Maps"; string UIName = "Specular F0 Map (rgb)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 108; string ColorSpace = "Raw";
>;
bool useSpecularF0Map
<
    string UIGroup = "Material Maps"; string UIName = "Use Specular F0 Map (rgb)"; int UIOrder = 109;
> = false;
Texture2D specularMap
<
    string UIGroup = "Material Maps"; string UIName = "Specular Amount Map (red)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 110; string ColorSpace = "Raw";
>;
bool useSpecularMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Specular Amount Map (red)"; int UIOrder = 111;
> = false;
Texture2D heightMap
<
    string UIGroup = "Material Maps"; string UIName = "Height Map (red, parallax)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 112; string ColorSpace = "Raw";
>;
bool useHeightMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Height Map (red, parallax)"; int UIOrder = 113;
> = false;
Texture2D ambOccMap
<
    string UIGroup = "Material Maps"; string UIName = "Ambient Occlusion Map (red)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 114; string ColorSpace = "Raw";
>;
bool useAmbOccMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Ambient Occlusion Map (red)"; int UIOrder = 115;
> = false;
Texture2D cavityMap
<
    string UIGroup = "Material Maps"; string UIName = "Cavity Map (red)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 116; string ColorSpace = "Raw";
>;
bool useCavityMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Cavity Map (red)"; int UIOrder = 117;
> = false;
Texture2D emissiveMap
<
    string UIGroup = "Material Maps"; string UIName = "Emissive Map (rgb)"; string ResourceType = "2D";
    string ResourceName = ""; int mipmaplevels = 0; int UIOrder = 118; string ColorSpace = "sRGB";
>;
bool useEmissiveMap
<
    string UIGroup = "Material Maps"; string UIName = "Use Emissive Map (rgb)"; int UIOrder = 119;
> = false;

// ------------------------------------------------------------------------------------- Material Properties (generated)

float3 materialBaseColor < string UIGroup = "Material Properties"; string UIName = "Base Color"; string UIWidget = "Color"; int UIOrder = 150; > = { 0.6, 0.6, 0.6 };
float materialRoughness < string UIGroup = "Material Properties"; string UIName = "Roughness"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 151; > = 0.5;
float materialMetalness < string UIGroup = "Material Properties"; string UIName = "Metalness"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 152; > = 0.0;
float materialSpecular < string UIGroup = "Material Properties"; string UIName = "Specular Amount"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 153; > = 1.0;
float materialSpecTint < string UIGroup = "Material Properties"; string UIName = "Specular Tint"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 154; > = 0.0;
float materialIOR < string UIGroup = "Material Properties"; string UIName = "Index of Refraction"; string UIWidget = "Slider"; float UIMin = 1.0; float UIMax = 3.0; float UIStep = 0.001; int UIOrder = 155; > = 1.45;
float materialBumpIntensity < string UIGroup = "Material Properties"; string UIName = "Bump Intensity"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 4.0; float UIStep = 0.001; int UIOrder = 156; > = 1.0;
float3 materialEmissive < string UIGroup = "Material Properties"; string UIName = "Emissive Color"; string UIWidget = "Color"; int UIOrder = 157; > = { 0.0, 0.0, 0.0 };
float materialEmissiveIntensity < string UIGroup = "Material Properties"; string UIName = "Emissive Intensity"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 100.0; float UIStep = 0.001; int UIOrder = 158; > = 0.0;
bool useVertexC0_RGBA < string UIGroup = "Material Properties"; string UIName = "Vertex Color Set 0 (RGB tint)"; int UIOrder = 160; > = false;
bool hasVertexAlpha < string UIGroup = "Material Properties"; string UIName = "Vertex Color Set 0 Alpha (opacity)"; int UIOrder = 161; > = false;
bool useVertexC1_AO < string UIGroup = "Material Properties"; string UIName = "Vertex Color Set 1 (AO)"; int UIOrder = 162; > = false;
bool hasAlpha < string UIGroup = "Material Properties"; string UIName = "Base Color Alpha (opacity)"; int UIOrder = 163; > = false;
bool useCutoutAlpha < string UIGroup = "Material Properties"; string UIName = "Cutout Alpha"; int UIOrder = 164; > = false;
float opacityMaskBias < string UIGroup = "Material Properties"; string UIName = "Cutout Threshold"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 165; > = 0.1;
float opacity : OPACITY < string UIGroup = "Material Properties"; string UIName = "Opacity"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 166; > = 1.0;
bool flipBackfaceNormals < string UIGroup = "Material Properties"; string UIName = "Flip Backface Normals"; int UIOrder = 167; > = true;

// ------------------------------------------------------------------------------------- Legacy v1 Disney (generated)

float materialSubsurface < string UIGroup = "Legacy v1 Disney"; string UIName = "Subsurface"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 180; > = 0.0;
float materialAnisotropic < string UIGroup = "Legacy v1 Disney"; string UIName = "Anisotropic"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 181; > = 0.0;
float materialSheen < string UIGroup = "Legacy v1 Disney"; string UIName = "Sheen"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 182; > = 0.0;
float materialSheenTint < string UIGroup = "Legacy v1 Disney"; string UIName = "Sheen Tint"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 183; > = 0.0;
float materialClearcoat < string UIGroup = "Legacy v1 Disney"; string UIName = "Clearcoat"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 184; > = 0.0;
float materialClearcoatGloss < string UIGroup = "Legacy v1 Disney"; string UIName = "Clearcoat Gloss"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 185; > = 0.0;
bool roughIsGloss < string UIGroup = "Legacy v1 Disney"; string UIName = "Roughness Map Is Gloss (v1)"; int UIOrder = 186; > = false;
bool useSpecularMask < string UIGroup = "Legacy v1 Disney"; string UIName = "Specular Amount From Map Alpha (v1)"; int UIOrder = 187; > = false;

// ------------------------------------------------------------------------------------- Parallax Occlusion (generated)

bool useParallaxOcclusionMapping < string UIGroup = "Parallax Occlusion"; string UIName = "Use Parallax Occlusion Mapping"; int UIOrder = 190; > = false;
float materialPomHeightScale < string UIGroup = "Parallax Occlusion"; string UIName = "Height Scale"; string UIWidget = "Slider"; float UIMin = 0.001; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 191; > = 0.05;
int pomMinSamples < string UIGroup = "Parallax Occlusion"; string UIName = "Min Samples"; string UIWidget = "Slider"; float UIMin = 1; float UIMax = 128; float UIStep = 1; int UIOrder = 192; > = 25;
int pomMaxSamples < string UIGroup = "Parallax Occlusion"; string UIName = "Max Samples"; string UIWidget = "Slider"; float UIMin = 1; float UIMax = 256; float UIStep = 1; int UIOrder = 193; > = 75;
int parallaxOccShadowType < string UIGroup = "Parallax Occlusion"; string UIName = "Self Shadow"; string UIFieldNames = "none:simple"; int UIOrder = 194; > = 0;
float selfOccShadowStrength < string UIGroup = "Parallax Occlusion"; string UIName = "Self Shadow Strength"; string UIWidget = "Slider"; float UIMin = 0.001; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 195; > = 0.7;
float pomShadowMultiplier < string UIGroup = "Parallax Occlusion"; string UIName = "Self Shadow Multiplier"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 196; > = 0.5;

// ------------------------------------------------------------------------------------- Normal Params (generated)

int NormalCoordsysX < string UIGroup = "Normal Params"; string UIName = "Normal X (Red)"; string UIFieldNames = "Positive:Negative"; int UIOrder = 207; > = 0;
int NormalCoordsysY < string UIGroup = "Normal Params"; string UIName = "Normal Y (Green)"; string UIFieldNames = "Positive:Negative"; int UIOrder = 208; > = 0;
int NormalCoordsysZ < string UIGroup = "Normal Params"; string UIName = "Normal Z (Blue)"; string UIFieldNames = "Positive:Negative"; int UIOrder = 209; > = 0;
// END hogshade.material generated

// ------------------------------------------------------------------------------------- shadows

bool useShadows < string UIGroup = "Shadows"; string UIName = "Receive Maya Shadow Maps"; int UIOrder = 300; > = false;
float shadowDepthBias : ShadowMapBias < string UIGroup = "Shadows"; string UIName = "Shadow Depth Bias"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 10.0; float UIStep = 0.001; int UIOrder = 301; > = 0.01;
float shadowMultiplier < string UIGroup = "Shadows"; string UIName = "Shadow Strength"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 1.0; float UIStep = 0.001; int UIOrder = 302; > = 1.0;
float shadowMapTexelSize < string UIGroup = "Shadows"; string UIName = "Shadow Filter Step (1 / map size)"; string UIWidget = "Slider"; float UIMin = 0.0; float UIMax = 0.01; float UIStep = 0.0001; int UIOrder = 303; > = 0.00195313;

static const int HOGSHADE_SHADOW_TAPS = 10;
static const float2 host_shadow_taps[HOGSHADE_SHADOW_TAPS] =
{
    { -0.84052f, -0.073954f }, { -0.326235f, -0.40583f }, { -0.698464f, 0.457259f }, { -0.203356f, 0.6205847f },
    { 0.96345f, -0.194353f }, { 0.473434f, -0.480026f }, { 0.519454f, 0.767034f }, { 0.185461f, -0.8945231f },
    { 0.507351f, 0.064963f }, { -0.321932f, 0.5954349f }
};

// ------------------------------------------------------------------------------------- lights, sixteen slots

// Maya binds a scene light to each slot through the `Object = "Light N"` annotation (the v2 gather
// pattern, widened from four to sixteen). Each slot is one macro: parameters, and a shadow lookup
// over that slot's map (Maya fills SHADOWMAP and SHADOWMAPMATRIX for lights that cast shadows).
#define HOGSHADE_LIGHT_SLOT(n, ORDER, PX, PY, PZ)                                                              \
bool light##n##Enable : LIGHTENABLE < string Object = "Light " #n; string UIName = "Enable Light " #n; int UIOrder = ORDER; > = false; \
int light##n##Type : LIGHTTYPE < string Object = "Light " #n; string UIName = "Light " #n " Type"; string UIFieldNames = "None:Default:Spot:Point:Directional:Ambient"; float UIMin = 0; float UIMax = 5; float UIStep = 1; int UIOrder = ORDER + 1; > = 2; \
float3 light##n##Pos : POSITION < string Object = "Light " #n; string UIName = "Light " #n " Position"; string Space = "World"; int UIOrder = ORDER + 2; > = { PX, PY, PZ }; \
float3 light##n##Color : LIGHTCOLOR < string Object = "Light " #n; string UIName = "Light " #n " Color"; string UIWidget = "Color"; int UIOrder = ORDER + 3; > = { 1.0f, 1.0f, 1.0f }; \
float light##n##Intensity : LIGHTINTENSITY < string Object = "Light " #n; string UIName = "Light " #n " Intensity"; float UIMin = 0.0; float UIStep = 0.01; int UIOrder = ORDER + 4; > = 1.0f; \
float3 light##n##Dir : DIRECTION < string Object = "Light " #n; string UIName = "Light " #n " Direction"; string Space = "World"; int UIOrder = ORDER + 5; > = { 100.0f, 100.0f, 100.0f }; \
float light##n##ConeAngle : HOTSPOT < string Object = "Light " #n; string UIName = "Light " #n " Cone Angle"; float UIMin = 0; float UIMax = 1.5707963; int UIOrder = ORDER + 6; > = 0.46f; \
float light##n##FallOff : FALLOFF < string Object = "Light " #n; string UIName = "Light " #n " Penumbra Angle"; float UIMin = 0; float UIMax = 1.5707963; int UIOrder = ORDER + 7; > = 0.7f; \
float light##n##AttenScale : DECAYRATE < string Object = "Light " #n; string UIName = "Light " #n " Decay (Maya; the core uses Range)"; float UIMin = 0.0; float UIStep = 0.01; int UIOrder = ORDER + 8; > = 0.0; \
float light##n##Range < string Object = "Light " #n; string UIName = "Light " #n " Range (0 = unbounded)"; float UIMin = 0.0; float UIStep = 0.1; int UIOrder = ORDER + 9; > = 0.0; \
bool light##n##ShadowOn : SHADOWFLAG < string Object = "Light " #n; string UIName = "Light " #n " Casts Shadow"; int UIOrder = ORDER + 10; > = true; \
float4x4 light##n##Matrix : SHADOWMAPMATRIX < string Object = "Light " #n; string UIWidget = "None"; >; \
Texture2D light##n##ShadowMap : SHADOWMAP < string Object = "Light " #n; string UIWidget = "None"; >; \
float host_shadow##n(float3 position_ws)                                                                       \
{                                                                                                               \
    float4 pndc = mul(float4(position_ws, 1.0f), light##n##Matrix);                                            \
    pndc.xyz /= pndc.w;                                                                                         \
    if (pndc.x <= -1.0f || pndc.x >= 1.0f || pndc.y <= -1.0f || pndc.y >= 1.0f || pndc.z <= 0.0f || pndc.z >= 1.0f) \
        return 1.0f;                                                                                            \
    float2 uv = float2(0.5f * pndc.x + 0.5f, 0.5f - 0.5f * pndc.y);                                             \
    float z = pndc.z - shadowDepthBias / pndc.w;                                                                \
    float lit = 0.0f;                                                                                           \
    for (int k = 0; k < HOGSHADE_SHADOW_TAPS; ++k)                                                              \
    {                                                                                                           \
        float d = light##n##ShadowMap.SampleLevel(SamplerShadowDepth, uv + host_shadow_taps[k] * shadowMapTexelSize, 0).x; \
        lit += (z - d >= 0.0f) ? 0.0f : (1.0f / HOGSHADE_SHADOW_TAPS);                                          \
    }                                                                                                           \
    return lerp(1.0f, lit, shadowMultiplier);                                                                   \
}

HOGSHADE_LIGHT_SLOT(0, 500, 100.0f, 100.0f, 100.0f)
HOGSHADE_LIGHT_SLOT(1, 520, -100.0f, 100.0f, 100.0f)
HOGSHADE_LIGHT_SLOT(2, 540, 100.0f, 100.0f, -100.0f)
HOGSHADE_LIGHT_SLOT(3, 560, -100.0f, 100.0f, -100.0f)
HOGSHADE_LIGHT_SLOT(4, 580, 0.0f, 100.0f, 100.0f)
HOGSHADE_LIGHT_SLOT(5, 600, 0.0f, 100.0f, -100.0f)
HOGSHADE_LIGHT_SLOT(6, 620, 100.0f, 100.0f, 0.0f)
HOGSHADE_LIGHT_SLOT(7, 640, -100.0f, 100.0f, 0.0f)
HOGSHADE_LIGHT_SLOT(8, 660, 100.0f, 50.0f, 100.0f)
HOGSHADE_LIGHT_SLOT(9, 680, -100.0f, 50.0f, 100.0f)
HOGSHADE_LIGHT_SLOT(10, 700, 100.0f, 50.0f, -100.0f)
HOGSHADE_LIGHT_SLOT(11, 720, -100.0f, 50.0f, -100.0f)
HOGSHADE_LIGHT_SLOT(12, 740, 0.0f, 50.0f, 100.0f)
HOGSHADE_LIGHT_SLOT(13, 760, 0.0f, 50.0f, -100.0f)
HOGSHADE_LIGHT_SLOT(14, 780, 100.0f, 50.0f, 0.0f)
HOGSHADE_LIGHT_SLOT(15, 800, -100.0f, 50.0f, 0.0f)

// One Maya light into one core slot. Maya light types: 0 none, 1 default (directional), 2 spot,
// 3 point, 4 directional, 5 ambient (contributed nothing in v2; off here). Maya's DIRECTION points
// from the light; the core wants towards it for directional lights and the spot axis for spots.
LightSource host_light(bool enabled, int type, float3 pos, float3 color, float intensity, float3 dir,
                       float cone, float penumbra, float range, float shadow, float gamma)
{
    LightSource l = (LightSource)0;
    l.kind = 0u;
    if (enabled)
    {
        if (type == 1 || type == 4) l.kind = 1u;
        if (type == 3) l.kind = 2u;
        if (type == 2) l.kind = 3u;
    }
    l.position_ws = pos;
    float3 d = normalize(dir);
    l.direction_ws = (l.kind == 1u) ? -d : d;
    l.intensity = intensity;
    l.color = pow(max(color, 0.0f), gamma);
    l.range = range;
    // Maya's cone angle is the full cone; the penumbra widens it. The core wants cos(inner), cos(outer).
    float inner = cone * 0.5f;
    l.cone_cos = float2(cos(inner), cos(inner + max(penumbra, 0.0f)));
    l.shadow = shadow;
    l._pad = 0.0f;
    return l;
}

#define HOGSHADE_FILL_SLOT(n, SLOTS, POS, GAMMA)                                                               \
    SLOTS.light[n] = host_light(light##n##Enable, light##n##Type, light##n##Pos, light##n##Color,               \
        light##n##Intensity, light##n##Dir, light##n##ConeAngle, light##n##FallOff, light##n##Range,            \
        (useShadows && light##n##ShadowOn && light##n##Enable) ? host_shadow##n(POS) : 1.0f, GAMMA);

FixedSlots16_ host_slots(float3 position_ws, float gamma)
{
    FixedSlots16_ slots = lighting_slots_empty();
    HOGSHADE_FILL_SLOT(0, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(1, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(2, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(3, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(4, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(5, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(6, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(7, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(8, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(9, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(10, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(11, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(12, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(13, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(14, slots, position_ws, gamma)
    HOGSHADE_FILL_SLOT(15, slots, position_ws, gamma)
    slots.count = 16u;
    return slots;
}

// ------------------------------------------------------------------------------------- debug

int g_DebugMode
<
    string UIGroup = "DEBUG [Preview]";
    string UIWidget = "Slider";
    string UIFieldNames = "o.m_Color.rgb:baseColorTex.rgb:baseColorTex.aaa:bColorLin.rgb:mColorLin.rgb:p.m_albedoRGBA.rgb:p.m_albedoRGBA.aaa:pbrMetalness.xxx:pbrRoughness.xxx:pbrAO.xxx:pbrCavity.xxx:baseNormalMap.xyz:normalRaw.xyz:F0.xxx:bClum.xxx:Ctint.rgb:Cspec0.rgb:diffuse.rgb:specular.rgb:pbrRoughness.xxx:roughA.xxx:roughA2.xxx:roughnessBiasedA.xxx:roughnessBiasedA2.xxx:NdotV:ambDomeColor.rgb:ambDomeLinColor.rgb:diffEnvLin.rgb:specEnvLin.rgb:cSpecLin:baseUV:selfOccShadow:triplanarXYZ";
    string UIName = "DEBUG VIEW";
    int UIOrder = 0;
> = 0;

// ------------------------------------------------------------------------------------- vertex stage

struct vsInput
{
    float3 m_Position : POSITION0;
    float4 m_AlbedoRGBA : COLOR0;
    float4 m_VertexAO : COLOR1;
    float2 m_Uv0 : TEXCOORD0;
    float3 m_Normal : NORMAL;
    float3 m_Tangent : TANGENT;
    float3 m_Binormal : BINORMAL;
};

struct VsOutput
{
    float4 m_Position : SV_POSITION;
    float4 m_albedoRGBA : COLOR0;
    float4 m_VertexAO : COLOR1;
    float2 m_Uv0 : TEXCOORD0;
    float4 m_WorldPosition : TEXCOORD1_centroid;
    float4 m_View : TEXCOORD2_centroid;
    float3 m_NormalW : TEXCOORD6;
    float3 m_TangentW : TEXCOORD7;
    float3 m_BinormalW : TEXCOORD8;
};

VsOutput vsMain(vsInput v)
{
    VsOutput OUT = (VsOutput)0;
    OUT.m_Position = mul(float4(v.m_Position, 1.0f), WorldViewProj);
    OUT.m_NormalW = normalize(mul(v.m_Normal, (float3x3)World));
    OUT.m_TangentW = normalize(mul(v.m_Tangent, (float3x3)World));
    OUT.m_BinormalW = normalize(mul(v.m_Binormal, (float3x3)World));
    OUT.m_WorldPosition = mul(float4(v.m_Position, 1.0f), World);
    OUT.m_albedoRGBA = v.m_AlbedoRGBA;
    OUT.m_VertexAO = v.m_VertexAO;
    OUT.m_Uv0 = float2(v.m_Uv0.x, -v.m_Uv0.y);  // Maya's UV origin
    OUT.m_View.xyz = viewInv[3].xyz - OUT.m_WorldPosition.xyz;
    OUT.m_View.w = length(OUT.m_View.xyz);
    OUT.m_View.xyz *= rcp(max(OUT.m_View.w, 1e-6f));
    return OUT;
}

// ------------------------------------------------------------------------------------- parallax (v2 code, shell-owned)

// Kept from V2_uv0bn-pbs_IBLenv.fx as written (ray-marched offset with a mip-based LOD fade, and
// the "simple" five-tap self shadow); the core's surface module replaces it in phase 4.
struct host_Parallax
{
    float2 uv;
    float self_shadow;
};

host_Parallax host_parallax(VsOutput p, float3 light_dir_ws)
{
    host_Parallax r;
    r.uv = p.m_Uv0;
    r.self_shadow = 1.0f;
    if (!(useParallaxOcclusionMapping && useHeightMap))
        return r;

    float2 baseUV = p.m_Uv0;
    const float2 pomTextureDimensions = float2(1024.0f, 1024.0f);
    const int pomLODThreshold = 3;
    float2 texCoordsPerSize = baseUV * pomTextureDimensions;
    float4 dxAll = ddx(float4(texCoordsPerSize, baseUV));
    float4 dyAll = ddy(float4(texCoordsPerSize, baseUV));
    float2 dxSize = dxAll.xy, dx = dxAll.zw;
    float2 dySize = dyAll.xy, dy = dyAll.zw;
    float2 deltaTexCoords = dxSize * dxSize + dySize * dySize;
    float minTexCoordDelta = max(deltaTexCoords.x, deltaTexCoords.y);
    float pomMipLevel = max(0.5f * log2(minTexCoordDelta), 0.0f);
    if (pomMipLevel > (float)pomLODThreshold)
        return r;

    float3 n = normalize(p.m_NormalW);
    float3 t = normalize(p.m_TangentW - dot(p.m_TangentW, n) * n);
    float3 b = -normalize(p.m_BinormalW);  // v2: "had to -, why!?"
    float3x3 worldToTangent = transpose(float3x3(t, b, n));
    float3 viewDirTS = normalize(mul(-p.m_View.xyz, worldToTangent));
    float2 maxParallaxOffset = -viewDirTS.xy * materialPomHeightScale / max(abs(viewDirTS.z), 1e-4f);
    int pomNumSamples = (int)lerp(pomMinSamples, pomMaxSamples, saturate(dot(p.m_View.xyz, n)));
    float zStepSize = 1.0f / (float)pomNumSamples;
    float2 vMaxOffset = maxParallaxOffset * zStepSize;

    float2 currTexOffset = 0.0f, prevTexOffset = 0.0f, finalTexOffset = 0.0f;
    float currRayZ = 1.0f - zStepSize, prevRayZ = 1.0f;
    float currHeight = 0.0f, prevHeight = 0.0f;
    int currSampleIndex = 0;
    [loop]
    while (currSampleIndex < pomNumSamples + 1)
    {
        currHeight = heightMap.SampleGrad(SamplerAnisoWrap, baseUV + currTexOffset, dx, dy).r;
        if (currHeight > currRayZ)
        {
            float tt = (prevHeight - prevRayZ) / (prevHeight - currHeight + currRayZ - prevRayZ);
            finalTexOffset = prevTexOffset + tt * vMaxOffset;
            currSampleIndex = pomNumSamples + 1;
        }
        else
        {
            ++currSampleIndex;
            prevTexOffset = currTexOffset;
            prevRayZ = currRayZ;
            prevHeight = currHeight;
            currTexOffset += vMaxOffset;
            currRayZ -= zStepSize;
        }
    }
    float2 pomUV = baseUV + finalTexOffset;
    if (pomMipLevel > (float)(pomLODThreshold - 1))
        pomUV = lerp(pomUV, baseUV, frac(pomMipLevel));
    r.uv = pomUV;

    if (parallaxOccShadowType == 1)
    {
        float3 lightDirTS = normalize(mul(light_dir_ws, worldToTangent));
        float2 lightRayTS = lightDirTS.xy * materialPomHeightScale;
        float h0 = 1.0f - heightMap.Sample(SamplerAnisoWrap, pomUV).r;
        float h = min(1.0f, 1.0f - heightMap.Sample(SamplerAnisoWrap, pomUV + 1.0f * lightRayTS).r);
        h = min(h, 1.0f - heightMap.Sample(SamplerAnisoWrap, pomUV + 0.8f * lightRayTS).r);
        h = min(h, 1.0f - heightMap.Sample(SamplerAnisoWrap, pomUV + 0.6f * lightRayTS).r);
        h = min(h, 1.0f - heightMap.Sample(SamplerAnisoWrap, pomUV + 0.4f * lightRayTS).r);
        h = min(h, 1.0f - heightMap.Sample(SamplerAnisoWrap, pomUV + 0.2f * lightRayTS).r);
        r.self_shadow = lerp(-pomShadowMultiplier, 1.0f, 1.0f - saturate((h0 - h) * selfOccShadowStrength));
    }
    return r;
}

// ------------------------------------------------------------------------------------- pixel stage

float3 host_linear(float3 swatch, float gamma)
{
    return pow(max(swatch, 0.0f), gamma);
}

struct PsOutput
{
    float4 m_Color : SV_TARGET;
};

PsOutput pMain(VsOutput p, bool FrontFace : SV_IsFrontFace)
{
    PsOutput o;
    float gamma = linearSpaceLighting ? gammaCorrectionValue : 1.0f;

    // the directional light the parallax self shadow follows: slot 0 when bound, else straight down
    float3 pom_light = light0Enable ? normalize(-light0Dir) : float3(0.0f, 1.0f, 0.0f);
    host_Parallax par = host_parallax(p, pom_light);
    float2 uv = par.uv;

    // --- material half: sampled values or the unbound defaults, then the core's inputs()
    legacy_v2_Samples s = (legacy_v2_Samples)0;
    s.base_color = useBaseColorMap ? baseColorMap.Sample(SamplerAnisoWrap, uv) : float4(1.0f, 1.0f, 1.0f, 1.0f);
    s.roughness = useRoughnessMap ? roughnessMap.Sample(SamplerAnisoWrap, uv).g : 1.0f;
    s.metalness = useMetalnessMap ? metalnessMap.Sample(SamplerAnisoWrap, uv).g : 1.0f;
    s.specular_f0_ = useSpecularF0Map ? specularF0Map.Sample(SamplerAnisoWrap, uv).rgb : float3(0.0f, 0.0f, 0.0f);
    s.specular_amount = useSpecularMap ? specularMap.Sample(SamplerAnisoWrap, uv).r : 1.0f;
    s.ao = useAmbOccMap ? ambOccMap.Sample(SamplerAnisoWrap, uv).r : 1.0f;
    s.cavity = useCavityMap ? cavityMap.Sample(SamplerAnisoWrap, uv).r : 1.0f;
    s.emissive = (useEmissiveMap ? emissiveMap.Sample(SamplerAnisoWrap, uv).rgb : float3(1.0f, 1.0f, 1.0f))
                 * host_linear(materialEmissive, gamma) * materialEmissiveIntensity;
    s.normal_ts = useNormalMap ? (baseNormalMap.Sample(SamplerAnisoWrap, uv).xyz * 2.0f - 1.0f) : float3(0.0f, 0.0f, 1.0f);

    legacy_v2_Material m = (legacy_v2_Material)0;
    m.base_color = host_linear(materialBaseColor, gamma);
    m.roughness = materialRoughness;
    m.metalness = materialMetalness;
    m.specular = materialSpecular;
    m.specular_tint = materialSpecTint;
    m.ior = materialIOR;
    m.bump_intensity = materialBumpIntensity;
    m.use_vertex_color = useVertexC0_RGBA ? 1u : 0u;
    m.use_vertex_ao = useVertexC1_AO ? 1u : 0u;
    m.use_vertex_alpha = hasVertexAlpha ? 1u : 0u;
    m.has_alpha = hasAlpha ? 1u : 0u;
    m.normal_flip = float3(NormalCoordsysX > 0 ? -1.0f : 1.0f, NormalCoordsysY > 0 ? -1.0f : 1.0f, NormalCoordsysZ > 0 ? -1.0f : 1.0f);
    m.flip_backface_normals = flipBackfaceNormals ? 1u : 0u;
    m.specular_f0_from_map = useSpecularF0Map ? 1u : 0u;

    legacy_v2_Geometry g = (legacy_v2_Geometry)0;
    g.normal_ws = normalize(p.m_NormalW);
    g.tangent_ws = normalize(p.m_TangentW);
    g.binormal_ws = normalize(p.m_BinormalW);
    g.view_ws = normalize(p.m_View.xyz);
    g.position_ws = p.m_WorldPosition.xyz;
    g.vertex_color = float4(host_linear(p.m_albedoRGBA.rgb, gamma), p.m_albedoRGBA.a);
    g.vertex_ao = p.m_VertexAO.rgb;
    g.front_face = FrontFace ? 1u : 0u;

    ShadingInputs i;
    if (shadingModel == 1)
    {
        // legacy v1: the same samples and geometry, the Disney lobes, v1's own map semantics
        legacy_v1_Material m1 = (legacy_v1_Material)0;
        m1.base_color = m.base_color;
        m1.metalness = materialMetalness;
        m1.subsurface = materialSubsurface;
        m1.specular = materialSpecular;
        m1.roughness = materialRoughness;
        m1.specular_tint = materialSpecTint;
        m1.anisotropic = materialAnisotropic;
        m1.sheen = materialSheen;
        m1.sheen_tint = materialSheenTint;
        m1.clearcoat = materialClearcoat;
        m1.clearcoat_gloss = materialClearcoatGloss;
        m1.use_vertex_color_ao = useVertexC1_AO ? 1u : 0u;
        m1.has_alpha = hasAlpha ? 1u : 0u;
        m1.use_vertex_alpha = hasVertexAlpha ? 1u : 0u;
        m1.use_cutout_alpha = useCutoutAlpha ? 1u : 0u;
        m1.flip_backface_normals = flipBackfaceNormals ? 1u : 0u;
        m1.rough_is_gloss = roughIsGloss ? 1u : 0u;
        m1.use_specular_mask = useSpecularMask ? 1u : 0u;
        m1.normal_flip = m.normal_flip;
        legacy_v1_Samples s1 = (legacy_v1_Samples)0;
        s1.base_color = s.base_color;
        s1.specular = useSpecularMap ? specularMap.Sample(SamplerAnisoWrap, uv) : float4(1.0f, 1.0f, 1.0f, 1.0f);
        s1.roughness = s.roughness;
        s1.metalness = s.metalness;
        s1.ao = useAmbOccMap ? ambOccMap.Sample(SamplerAnisoWrap, uv).rgb : float3(1.0f, 1.0f, 1.0f);
        s1.normal_ts = s.normal_ts;
        s1.use_base_map = useBaseColorMap ? 1u : 0u;
        s1.use_specular_map = useSpecularMap ? 1u : 0u;
        s1.use_roughness_map = useRoughnessMap ? 1u : 0u;
        s1.use_metalness_map = useMetalnessMap ? 1u : 0u;
        s1.use_normal_map = useNormalMap ? 1u : 0u;
        legacy_v1_Geometry g1 = (legacy_v1_Geometry)0;
        g1.normal_ws = g.normal_ws;
        g1.tangent_ws = g.tangent_ws;
        g1.binormal_ws = g.binormal_ws;
        g1.view_ws = g.view_ws;
        g1.position_ws = g.position_ws;
        g1.vertex_color = float4(g.vertex_ao, g.vertex_color.a);  // v1 read AO and alpha from one colour set
        g1.front_face = g.front_face;
        i = legacy_v1_inputs(m1, s1, g1);
    }
    else if (shadingModel == 0)
    {
        i = lambert_inputs(m.base_color, s.ao, s.emissive, g.normal_ws, g.view_ws, g.position_ws);
    }
    else
    {
        i = legacy_v2_inputs(m, s, g);
    }

    if (useCutoutAlpha)
        clip(i.opacity < opacityMaskBias ? -1.0f : 1.0f);

    // --- environment: the cooked cubes and LUT at the model's lookup coordinates
    uint cube_w, cube_h, cube_mips;
    specularEnvTextureCube.GetDimensions(0, cube_w, cube_h, cube_mips);
    EnvironmentIBL ibl = environment_default((float)max(cube_mips, 1u));
    ibl.exposure = envExposure;
    EnvironmentSamples env = environment_sample(specularEnvTextureCube, diffuseEnvTextureCube, brdfTextureMap,
                                                SamplerCubeMap, SamplerBrdfLUT, ibl,
                                                i.surface.normal_ws, i.view_ws, models_env_lookup(i));
    if (!useEnvMaps)
    {
        env.irradiance_over_pi = 0.0f;
        env.specular = 0.0f;
    }
    float3 sky = host_linear(ambientSkyColor, gamma) * ambientSkyIntensity;
    float3 ground = host_linear(ambientGroundColor, gamma) * ambientGrndIntensity;
    float3 up = float3(0.0f, 1.0f, 0.0f);
    env.hemisphere = environment_hemisphere(sky, ground, i.surface.normal_ws, up);
    env.hemisphere_mode = (uint)hemisphericalAmbientMode;

    // --- lights: the sixteen bound slots, each with its shadow term and the parallax self shadow
    FixedSlots16_ slots = host_slots(g.position_ws, gamma);
    if (par.self_shadow < 1.0f)
    {
        for (int k = 0; k < 16; ++k)
            slots.light[k].shadow *= par.self_shadow;
    }

    // --- the lighting half
    ShadingResult r = models_shade(i, slots, env, (uint)g_DebugMode);
    float3 color = r.color;
    if (g_DebugMode > 0)
    {
        color = (shadingModel == 2 && legacy_v2_debug_is_inputs_mode((uint)g_DebugMode))
            ? legacy_v2_debug_inputs(m, s, g, uv, par.self_shadow, ambientSkyColor, ambientGroundColor, up, (uint)g_DebugMode)
            : r.debug;
    }

    float alpha = (opacity < 1.0f) ? i.opacity * opacity : i.opacity;
    o.m_Color = float4(color * alpha, alpha);  // pre-multiplied, for PMAlphaBlending
    return o;
}

// ------------------------------------------------------------------------------------- Maya transparency and shadow passes (v2 boilerplate)

void Peel(VsOutput v)
{
    float currZ = abs(mul(v.m_WorldPosition, view).z);
    float4 Pndc = mul(v.m_WorldPosition, viewPrj);
    float2 UV = Pndc.xy / Pndc.w * float2(0.5f, -0.5f) + 0.5f;
    float prevZ = transpDepthTexture.Sample(SamplerShadowDepth, UV).r;
    float opaqZ = opaqueDepthTexture.Sample(SamplerShadowDepth, UV).r;
    float bias = 0.00002f;
    if (currZ < prevZ * (1.0f + bias) || currZ > opaqZ * (1.0f - bias))
        discard;
}

float4 LinearDepth(VsOutput v)
{
    return abs(mul(v.m_WorldPosition, view).z);
}

float4 DepthComplexity(float a)
{
    return a > 0.001f ? 1.0f : 0.0f;
}

struct MultiOut2
{
    float4 target0 : SV_Target0;
    float4 target1 : SV_Target1;
};

MultiOut2 fTransparentPeel(VsOutput v, bool FrontFace : SV_IsFrontFace)
{
    Peel(v);
    MultiOut2 OUT;
    OUT.target0 = pMain(v, FrontFace).m_Color;
    OUT.target1 = LinearDepth(v);
    return OUT;
}

MultiOut2 fTransparentPeelAndAvg(VsOutput v, bool FrontFace : SV_IsFrontFace)
{
    Peel(v);
    MultiOut2 OUT;
    OUT.target0 = pMain(v, FrontFace).m_Color;
    OUT.target1 = DepthComplexity(OUT.target0.w);
    return OUT;
}

MultiOut2 fTransparentWeightedAvg(VsOutput v, bool FrontFace : SV_IsFrontFace)
{
    MultiOut2 OUT;
    OUT.target0 = pMain(v, FrontFace).m_Color;
    OUT.target1 = DepthComplexity(OUT.target0.w);
    return OUT;
}

float4 ShadowMapPS(VsOutput v) : SV_Target
{
    if (useCutoutAlpha && hasAlpha && useBaseColorMap)
        clip(baseColorMap.Sample(SamplerAnisoWrap, v.m_Uv0).a < opacityMaskBias ? -1.0f : 1.0f);
    float4 Pndc = mul(v.m_WorldPosition, viewPrj);
    float retZ = Pndc.z / Pndc.w;
    retZ += fwidth(retZ);
    return retZ.xxxx;
}

// ------------------------------------------------------------------------------------- techniques

technique11 Main
<
    bool overridesDrawState = false;
    int isTransparent = 3;
    string transparencyTest = "opacity < 1.0 || hasAlpha || hasVertexAlpha";
    bool supportsAdvancedTransparency = true;
>
{
    pass P0 < string drawContext = "colorPass"; >
    {
        SetBlendState(PMAlphaBlending, float4(0.0f, 0.0f, 0.0f, 0.0f), 0xFFFFFFFF);
        SetVertexShader(CompileShader(vs_5_0, vsMain()));
        SetPixelShader(CompileShader(ps_5_0, pMain()));
    }
    pass pTransparentPeel < string drawContext = "transparentPeel"; >
    {
        SetVertexShader(CompileShader(vs_5_0, vsMain()));
        SetPixelShader(CompileShader(ps_5_0, fTransparentPeel()));
    }
    pass pTransparentPeelAndAvg < string drawContext = "transparentPeelAndAvg"; >
    {
        SetVertexShader(CompileShader(vs_5_0, vsMain()));
        SetPixelShader(CompileShader(ps_5_0, fTransparentPeelAndAvg()));
    }
    pass pTransparentWeightedAvg < string drawContext = "transparentWeightedAvg"; >
    {
        SetVertexShader(CompileShader(vs_5_0, vsMain()));
        SetPixelShader(CompileShader(ps_5_0, fTransparentWeightedAvg()));
    }
    pass pShadow < string drawContext = "shadowPass"; >
    {
        SetVertexShader(CompileShader(vs_5_0, vsMain()));
        SetPixelShader(CompileShader(ps_5_0, ShadowMapPS()));
    }
}
