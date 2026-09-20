# Phase 2 spec: the WGSL core and its first two hosts

Date: 2026-09-20. Design: [../design/2026-09-20-modernization-direction.md](../design/2026-09-20-modernization-direction.md)
("Architecture", "Two rendering paths", "Why WGSL is the source"), roadmap track C2. Plan:
[../plans/phase-2-restructure.md](../plans/phase-2-restructure.md).

## Deliverable

The shading core exists as WGSL under `core/`, with the v1 and v2 legacy models ported into it as
selectable peers, a numeric test harness that runs the core on the GPU against Python references,
and two hosts that consume it: `hosts/wgpu/` (the core's native home) and `hosts/maya_dx11/` (naga's
HLSL wrapped in a `.fx` shell), with `hosts/hlsl/` as the committed modern HLSL. The Maya check from
E1 renders a lit ball through the ported v2 model, replacing the black one.

## The spike comes first, and it can fail

Task 1 of the plan is a spike, not a feature: one core module (the GGX lobe and a Fresnel term) in
WGSL, translated by naga to HLSL, wrapped in a v2-style `.fx` shell, compiled by fxc, loaded by
`dx11Shader` in Maya 2026, and drawn on a sphere. Pass means WGSL stays the source language. Fail
means the core moves to Slang and WGSL becomes an emitted target, as the design doc already allows;
the rest of this spec is unchanged either way except the toolchain section.

Known risks the spike must answer: naga's HLSL emits its own struct and binding conventions
(`cbuffer` layouts, `Texture2D` and `SamplerState` declarations, entry-point signatures) that must
sit inside an effect file the `dx11Shader` plug-in accepts; naga's shader-model target (5.0 by
default) must satisfy `fx_5_0`; and naga has no notion of effect annotations, so every UI annotation
stays in the hand-written shell.

## Toolchain

- **naga-cli**, from the wgpu project, installed with `cargo install naga-cli`. That needs a Rust
  toolchain on the machine (`winget install Rustlang.Rustup`), which is a new developer dependency
  the owner accepts for this phase. CI installs it the same way and caches it. If a prebuilt binary
  becomes available the plan swaps to it.
- **wgpu-py** for the GPU test harness: the core is executed as compute shaders on the local GPU,
  the same package SpriteJammer runs on. It is the `gpu` optional extra.
- **fxc** from the Windows 10 SDK for the Maya shell, already on the machine; **dxc** for the
  `hosts/hlsl/` shader-model 6 validation.
- `tools/build_shaders.py` stitches core modules in manifest order, runs naga to validate the WGSL
  and to emit HLSL and GLSL into `hosts/*/generated/`, and runs fxc and dxc. `tests/compile/` calls
  it and fails on any error. Generated files are committed; CI checks that regeneration is a no-op.

## Module conventions in WGSL

WGSL has no `import`. A module is a file under `core/` with a header comment naming what it
provides and requires; `core/manifest.toml` lists modules in dependency order and
`build_shaders.py` concatenates them. Rules:

- Every function and struct is prefixed with its module: `brdf_ggx_d`, `lighting_LightSource`,
  `surface_triplanar_weights`. No two modules define the same name; the build fails if they do.
- No entry points in `core/`. Entry points live in hosts.
- No bindings in `core/`. Textures, samplers and uniforms are declared by hosts and passed in as
  function arguments or through the `ShadingInputs` struct. This is what keeps the core portable.
- Constants that every host must agree on (`ROUGHNESS_BIAS`, the mip-count rule, the SH band
  weights) live in `core/constants.wgsl` and are mirrored in `hogshade/core_constants.py`, with a
  test that the two agree.

## Interfaces

```wgsl
// core/interface.wgsl
struct ShadingInputs {          // the material half's output, the lighting half's input
    base_color: vec3<f32>,      // linear
    metalness: f32,
    roughness: f32,             // perceptual, before bias
    ao: f32,
    cavity: f32,
    emissive: vec3<f32>,
    normal_ws: vec3<f32>,       // unit, world space, after normal mapping
    view_ws: vec3<f32>,         // unit, surface to eye
    position_ws: vec3<f32>,
    specular_f0: vec3<f32>,     // derived by the model's inputs() from the parameters above
    opacity: f32,
    model: u32,                 // shading-model ID; the same byte the G-buffer carries
}
struct ShadingResult {
    color: vec3<f32>,           // scene-linear radiance
    debug: vec3<f32>,           // the intermediate selected by the debug mode, or zero
}
struct LightSource {            // one punctual light; see lighting.wgsl for the providers
    kind: u32,                  // 0 off, 1 directional, 2 point, 3 spot
    position_ws: vec3<f32>,
    direction_ws: vec3<f32>,    // unit, towards the light for directional
    color: vec3<f32>,           // linear, in the light-rig unit (design doc, track E)
    intensity: f32,
    range: f32,
    cone_cos: vec2<f32>,        // inner, outer
    shadow: f32,                // 0..1, supplied by the host
}
```

Every model implements two functions with fixed names, `<model>_inputs(...) -> ShadingInputs` and
`<model>_evaluate(inputs, lights, env, debug_mode) -> ShadingResult`, and `core/models.wgsl` holds
the `switch` on `model` that dispatches to them. Forward hosts call both in one shader; the deferred
host calls `inputs` in the G-buffer fill and `evaluate` in the light pass. `core/gbuffer.wgsl`
encodes and decodes `ShadingInputs` against a layout struct, with SpriteJammer's ADR-002 layout as
the first.

`lighting.wgsl` provides `FixedSlots16` (an array of 16 `LightSource`, the v2 gather pattern, filled
by a DCC host) and `LightBuffer` (a storage buffer the engine fills after culling). Each model's
light loop is written once against an accessor that both providers satisfy.

The environment interface `EnvironmentIBL` carries the prefiltered specular cube, the irradiance
cube or SH9 constants, the BRDF LUT, the mip count and the E1 conventions (roughness linear in mip,
irradiance stored as E over pi). The v2 RGBM decode, the `.bgr` swizzle and the exposure of 5 are
not carried; that is a documented deviation of the port.

## The legacy ports

`core/models/legacy_v1.wgsl` and `core/models/legacy_v2.wgsl` are the 2015 and 2017 shading
written in WGSL against the interfaces above. "Faithful" means the same mathematics, function by
function, checked numerically; it does not mean the same bugs where a bug made the shader unusable.
The deviations, each recorded in the module header and in the design doc:

- The environment is the E1 data (linear fp16 cubes, LUT), not RGBM 8-bit cubes.
- Unbound maps have defined defaults (white base colour, flat normal, roughness and metalness from
  the scalar parameters, AO and cavity 1) instead of sampling black. In the host, "unbound" is a
  per-map flag the shell sets; in the core, a default value the caller passes.
- The `environment` semantic is not used; cube slots are ordinary texture parameters.
- The 33-mode debug view is preserved as the `debug` output selected by `debug_mode`.
- POM, self-shadowing and the depth-peeling passes are host concerns and stay in the Maya shell,
  calling the core's surface functions once those exist in phase 4; until then the shell keeps its
  own copy of the v2 POM, marked as such.

## The test harness

`tests/core/` runs core functions on the GPU through wgpu-py compute shaders over arrays of test
vectors and compares against Python references in `hogshade/reference/` (NumPy implementations of
each core function, small and readable, the same role E1's NumPy path plays for numba):

- `brdf`: GGX D, Smith visibility, Fresnel variants, on a grid of angles and roughness, within 1e-5.
- `models`: `legacy_v2_evaluate` on a set of `ShadingInputs` and one light, within 1e-4.
- `gbuffer`: encode then decode round-trips within the quantisation the layout allows.
- `lighting`: `FixedSlots16` with 16 lights sums to the same radiance as 16 single-light calls.
- A furnace: white environment, white dielectric, every model returns 1 within 1 percent.

The harness is skipped, not failed, when no GPU adapter is available; CI on a headless runner
therefore checks compile and the Python references only, and the GPU tests run on the owner's
machine and are recorded in `Docs/verification/`.

## Hosts in this phase

- `hosts/wgpu/`: `lit_mesh.wgsl` (forward: inputs then evaluate), `gbuffer_fill.wgsl` and
  `deferred_light.wgsl` (the two halves), each a thin entry point over the stitched core, validated
  by naga. A wgpu-py test viewport on the `Spikes/wgpu_tile` pattern draws the shader ball with the
  legacy v2 model under the studio IBL and writes `Docs/verification/wgpu-v2-studio.png`.
- `hosts/maya_dx11/`: `hogshade.fx`, the shell: effect parameters and annotations (generated from
  the parameter schema in phase 3; hand-written for the legacy parameter set now), texture and
  sampler declarations, the 16 light slots bound through `Object = "Light N"`, techniques and passes,
  and a call into naga's HLSL of the core. `tools/maya_ibl_check.py` re-run against it must produce a
  lit ball with the specular term visible.
- `hosts/hlsl/`: naga's shader-model 6 HLSL of the core, formatted, dxc-validated, with a README of
  its binding layout for Unreal, Unity and DX12 consumers. The Maya shell includes this file rather
  than a private copy.

## Out of scope

- OpenPBR, MaterialX, the parameter schema, the alpha enum: phase 3.
- Triplanar, parallax, layering: phase 4.
- `maya_ogsfx`, Blender, OSL: phase 6.
- Any performance work on the shaders.

## Acceptance gate

- The spike's verdict is recorded in the plan with the evidence (fxc log, Maya screenshot).
- `tests/compile/` passes: naga validates every core module and every host; fxc compiles the Maya
  shell; dxc compiles `hosts/hlsl/`. CI runs it.
- `tests/core/` passes on the owner's GPU; the run is recorded under `Docs/verification/`.
- Maya 2026 renders the ported v2 model on the shader ball under the studio IBL with a visible
  specular reflection, from the E1 check tool, screenshot committed.
- The wgpu viewport renders the same scene; the two screenshots are compared by eye in this phase
  and by the parity tooling from track E once it exists.
- `Docs/design/…-modernization-direction.md` lists every deviation the port made.
