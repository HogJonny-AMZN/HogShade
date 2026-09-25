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

Task 1 of the plan is a spike, not a feature: one core module in WGSL (the GGX lobe and a Fresnel
term, plus a function that samples a `texture_2d` through a sampler and reads a light from a
uniform struct, so the integration path is exercised and not just the arithmetic), translated by
naga to shader-model 5 HLSL, wrapped in a v2-style `.fx` shell that declares the texture, sampler
and light parameters with Maya annotations and passes them into the generated code, compiled by
fxc, loaded by `dx11Shader` in Maya 2026, and drawn on a sphere with a bound texture and a bound
light. Pass means WGSL stays the source language. Fail means the core moves to Slang and WGSL
becomes an emitted target, as the design doc already allows; the rest of this spec is unchanged
either way except the toolchain section. A spike that compiles but cannot bind the texture or the
light is a fail, not a provisional pass.

**Verdict (2026-09-20): pass. WGSL stays the source language.** Evidence in `Spikes/naga-fx/`:
naga 30.0.1 at shader model 5.0, `fxc /T fx_5_0` exit 0, Maya 2026 draws the checker-textured
sphere with a GGX highlight from a scene light bound to `Light 0`, and rotating the light changes
the frame. One finding shapes the core: with `@group/@binding` globals naga emits a sampler heap in
register spaces that no effect can bind, so the core passes textures, samplers and uniforms as
function parameters and declares nothing at file scope. That is already the "no bindings in core"
rule below, now with a reason.

Known risks the spike had to answer: naga's HLSL emits its own struct and binding conventions
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
- **Two HLSL targets from one WGSL.** naga's HLSL backend takes a shader-model option. The build
  emits `hosts/maya_dx11/generated/hogshade_core_sm5.hlsl` at shader model 5.0, which is what an
  `fx_5_0` effect can include, and `hosts/hlsl/hogshade_core.hlsl` at shader model 6 for modern
  consumers. The Maya shell includes the SM5 artifact and never the SM6 one; fxc validates the
  first, dxc the second. Anything the core uses that SM5 cannot express fails the build, which is
  the point: the core stays within what every host can compile.
- `tools/build_shaders.py` stitches core modules in manifest order, runs naga to validate the WGSL
  and to emit both HLSL targets and GLSL into `hosts/*/generated/`, and runs fxc and dxc.
  `tests/compile/` calls it and fails on any error. Generated files are committed; CI checks that
  regeneration is a no-op.

## Module conventions in WGSL

WGSL has no `import`. A module is a file under `core/` with a header comment naming what it
provides and requires; `core/manifest.toml` lists modules in dependency order and
`build_shaders.py` concatenates them. Rules:

- Every function and struct is prefixed with its module: `brdf_ggx_d`, `lighting_fixed_slots_get`,
  `surface_triplanar_weights`. The one exemption is the public interface: the structs in
  `core/interface.wgsl` (`ShadingInputs`, `SurfaceInputs`, `ShadingResult`, `LightSource`,
  `EnvironmentIBL`) and the model entry names `<model>_inputs` and `<model>_evaluate`, which every
  host and every model spells the same way. The collision checker knows the exemption list from
  `manifest.toml`; any other unprefixed name fails the build.
- No entry points in `core/`. Entry points live in hosts.
- No bindings in `core/`. Textures, samplers and uniforms are declared by hosts and passed in as
  function arguments or through the `ShadingInputs` struct. This is what keeps the core portable.
- Constants that every host must agree on (`ROUGHNESS_BIAS`, the mip-count rule, the SH band
  weights) live in `core/constants.wgsl` and are mirrored in `hogshade/core_constants.py`, with a
  test that the two agree.

## Interfaces

```wgsl
// core/interface.wgsl (as implemented in PR B; this file is the contract, the spec quotes it)
struct SurfaceInputs {          // what the G-buffer stores; what inputs() must produce for deferred
    base_color: vec3<f32>,      // linear
    metalness: f32,
    roughness: f32,             // perceptual, before bias
    ao: f32,                    // cavity folded in at encode time
    emissive: vec3<f32>,
    normal_ws: vec3<f32>,       // unit, world space, after normal mapping
    model: u32,                 // shading-model ID; the same byte the G-buffer carries
}
struct ShadingInputs {          // the lighting half's input: the surface plus what forward has
    surface: SurfaceInputs,
    view_ws: vec3<f32>,         // unit, surface to eye
    position_ws: vec3<f32>,
    specular_f0: vec3<f32>,     // forward: from the model; deferred: mix(0.04, base_color, metalness)
    cavity: f32,                // forward only; deferred folds it into surface.ao and reconstructs 1.0
    opacity: f32,               // forward only; 1.0 after MASK in deferred
}
struct ShadingResult {
    color: vec3<f32>,           // scene-linear radiance
    debug: vec3<f32>,           // the intermediate selected by the debug mode, or zero
}
struct LightSource {            // one punctual light. The field order is the buffer ABI:
    position_ws: vec3<f32>,     //   offset 0
    kind: u32,                  //   12: 0 off, 1 directional, 2 point, 3 spot
    direction_ws: vec3<f32>,    //   16: unit, towards the light for directional; spot axis, from the light
    intensity: f32,             //   28
    color: vec3<f32>,           //   32: linear, in the light-rig unit (design doc, track E)
    range: f32,                 //   44: point and spot; <= 0 unbounded
    cone_cos: vec2<f32>,        //   48: cos(inner), cos(outer)
    shadow: f32,                //   56: 0..1, supplied by the host
    _pad: f32,                  //   60; size 64
}
```

The nesting is deliberate: `SurfaceInputs` is the deferred payload and `ShadingInputs` wraps it, so
the two paths share one definition of the stored fields. `hogshade/core_layout.py` mirrors the
`LightSource` order and offsets and a test checks the WGSL against it.

Every model implements `<model>_inputs(...) -> ShadingInputs`, `<model>_evaluate_light(inputs,
light, env) -> vec3` for one light, `<model>_evaluate_env(inputs, env) -> vec3` and
`<model>_debug(inputs, slots, env, mode) -> vec3`, where `env` is an `EnvironmentSamples`: the
irradiance over pi, the prefiltered specular radiance, the split-sum LUT pair and the v2 hemisphere
dome, sampled once per fragment by `environment_sample` (numbers, so the models never touch a
texture and the GPU tests need none). The per-light function receives it because the v2 model scales
its direct specular by the LUT (PR D, 2026-09-25; the first draft passed only `irradiance_over_pi`).
`ShadingInputs` also carries `specular_weight`, the material's specular amount (v2 `materialSpecular`,
OpenPBR `specular_weight`), forward-only and one after reconstruction.
`core/models.wgsl` holds the `switch` on `surface.model` for
each, plus `models_evaluate_slots` (the loop over `FixedSlots16`) and `models_shade` (direct plus
environment plus emissive, with the debug slot). WGSL has no function pointers, so an engine loops
its own light buffer calling `models_evaluate_light`; the per-light maths is shared, the loop is per
provider. Forward hosts call inputs and the evaluations in one shader; the deferred host calls
`inputs` in the G-buffer fill (through `gbuffer_encode_from_inputs`) and the evaluations in the
light pass after `gbuffer_reconstruct`.

**The deferred payload contract.** A G-buffer does not carry all of `ShadingInputs`, so the struct
is split into what is stored and what is reconstructed:

```wgsl
struct SurfaceInputs {          // what the G-buffer stores; what inputs() must produce for deferred
    base_color: vec3<f32>,
    metalness: f32,
    roughness: f32,
    ao: f32,                    // cavity is folded into ao at encode time
    emissive: vec3<f32>,
    normal_ws: vec3<f32>,
    model: u32,
}
// ShadingInputs = SurfaceInputs + view_ws, position_ws (reconstructed per pixel from depth and the
// camera by the light pass) + specular_f0 (derived: mix(vec3(0.04), base_color, metalness) in the
// deferred path; a model may derive it differently in forward, and that is a documented tier-3
// difference) + opacity (1.0 in the deferred path; MASK has already discarded).
```

`core/gbuffer.wgsl` encodes and decodes `SurfaceInputs` against a layout struct, with SpriteJammer's
ADR-002 layout first; the quantisation of each field (octahedral normal in `rgba16float`, 8-bit
albedo and AO) is part of the contract and the round-trip test measures it. `evaluate()` consumes
`ShadingInputs` in both paths; the deferred host builds it from `SurfaceInputs` plus the
reconstruction above. Fields only forward can supply (a distinct specular colour, coat, anisotropy,
opacity blending) are exactly the tier-3 list in the design doc. A parity test evaluates the same
surface through the forward path and through encode, decode and reconstruct, and the difference
must be within the quantisation the layout allows (task 10 of the plan). Any field that cannot be
reconstructed or defaulted is a build error, not a silent divergence.

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
- A furnace: white environment, white dielectric, every model returns 1 within 1 percent. Amended
  for the legacy ports (2026-09-25): a legacy model returns what the legacy shader returned, and
  the test asserts that value; v2 never scales diffuse by (1 - F), so it returns 1 plus the
  specular albedo, a few percent facing the camera and up to 0.57 at grazing. Recorded, not fixed:
  the ports are the record.

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
  and a call into naga's shader-model 5 HLSL of the core. `tools/maya_ibl_check.py` re-run against it
  must produce a lit ball with the specular term visible.
- `hosts/hlsl/`: naga's shader-model 6 HLSL of the core, formatted, dxc-validated, with a README of
  its binding layout for Unreal, Unity and DX12 consumers. The Maya shell includes the shader-model 5
  artifact of the same WGSL (`hosts/maya_dx11/generated/hogshade_core_sm5.hlsl`), not this file; both
  are generated by one build from one source, and the build fails if the core uses anything SM5
  cannot express.

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
