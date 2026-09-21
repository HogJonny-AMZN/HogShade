// HogShade core: constants every host must agree on. Mirrored in hogshade/core_constants.py; a test
// keeps the two in step. Values here are conventions, not tunables.

const HOGSHADE_PI: f32 = 3.14159265358979;
const HOGSHADE_INV_PI: f32 = 0.318309886183791;

// Perceptual roughness is biased before squaring so a mirror never divides by zero (v2 kept 0.005).
const HOGSHADE_ROUGHNESS_BIAS: f32 = 0.005;

// The E1 cook: specular mips are linear in roughness, mip = roughness * (mip_count - 1);
// irradiance cubes and SH9 store E / pi, so multiply by albedo directly.
const HOGSHADE_IRRADIANCE_OVER_PI: f32 = 1.0;

// Spherical-harmonic cosine-lobe band weights for L2 (Ramamoorthi and Hanrahan), applied to
// radiance coefficients before dividing by pi.
const HOGSHADE_SH_A0: f32 = 3.14159265358979;
const HOGSHADE_SH_A1: f32 = 2.09439510239320;
const HOGSHADE_SH_A2: f32 = 0.78539816339745;

// Dielectric F0 assumed when a host cannot supply a specular colour (the deferred path).
const HOGSHADE_DIELECTRIC_F0: f32 = 0.04;

// Shading-model IDs: the byte the G-buffer carries and the switch in models.wgsl dispatches on.
const HOGSHADE_MODEL_LAMBERT: u32 = 0u;
const HOGSHADE_MODEL_LEGACY_V1: u32 = 1u;
const HOGSHADE_MODEL_LEGACY_V2: u32 = 2u;
const HOGSHADE_MODEL_OPENPBR: u32 = 3u;

// Debug view 0 is the final colour; the rest are model-defined intermediates.
const HOGSHADE_DEBUG_NONE: u32 = 0u;
