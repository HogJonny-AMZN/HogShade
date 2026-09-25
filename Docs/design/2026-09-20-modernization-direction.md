# HogShade: modernization direction for Maya-PBR-BRDF-VP2

Date: 2026-09-20. Status: direction agreed with the owner; no code changed yet.
This is the pre-plan design record. The phased plan with checkboxes follows once phase 1 lands.

## Goal

Own one shader and use it anywhere the pipeline, the content tools or a workflow needs it. The
repo is the HogJonny-AMZN-owned fork, port and eventual replacement of the 2015 Maya shader; the
core is the single source and every DCC, renderer and engine target is a host of it.

## What the repo is today

- HLSL 5 `.fx` effect shaders for Maya Viewport 2.0 `dx11Shader`, two generations:
  `src/Shaders/HLSL/v.1.0` (2015) and `v.2.0` (2017: IBL, parallax occlusion mapping, tone
  mapping, depth-peeling transparency, a 33-mode debug view). Last real commit August 2017.
  v2.0 has two entry files: `V2_uv0bn-pbs_IBLenv.fx` is the July 2017 rewrite with POM
  self-shadowing and debug modes 0 to 32, and is the reference; `uv0bn-pbs_IBLenv.fx` is the
  earlier variant (30 debug modes). Both compile under fxc.
- 37 stars, 12 forks, one open issue asking for a getting-started guide. No licence.
- History is 128 MB: Maya scenes, IBL `.dds` cubes, Visual Studio debug output and PSDs. One 20 MB
  scene is committed sixteen times.
- A `v.3.0` folder dated 2025-04-26/27 sits uncommitted on the owner's machine. Its main `.fx` is
  corrupted (interleaved line fragments). Three includes were rewritten to a quarter of their v2 size
  and may or may not compile. `V2_`/`V3_` variants are byte copies of v2. Archived to
  `D:\Depot\Maya-PBR-BRDF-VP2_BAK\uncommitted-v3.0-2025-04` before any cleanup.
- **v3.0 salvage result (2026-09-20).** With `fxc /T fx_5_0 /D _MAYA_=1`, both legacy shaders
  compile clean (warnings only). Swapping each archived v3 include into v2 one at a time: six of
  eleven compile (`samplers`, `toneMapping`, `mayaLightsShadowMaps`, `mayaLights`, `maxUtilities`,
  `propertyNames`), five do not (`lighting.sif` and `pbr.sif` redefine `cg_PI`; `pbr_shader_ui`
  references undefined macros; `mayaUtilities` has a syntax error; `mayaLightsUtilities` calls a
  function that no longer exists). The six that compile are reformatting, comment and macro-layout
  changes; `mayaLights.fxh` is cut from 548 lines to 117 with no functional gain visible. Nothing
  was taken. v2 in git is the reference; the archive stays outside the repo.
- **Maya verification.** Headless `mayapy` 2026 loads the effect but reports no techniques (no
  DirectX device without a GUI). A scripted GUI launch is the only automated route; see the roadmap.
- Triplanar does not exist as a feature. Debug view 32 computes per-axis blend weights from the world
  normal and displays them. No texture is sampled through them and the weights are not normalised.

## Decisions (owner, 2026-09-20)

| Question | Decision |
| --- | --- |
| Where the repo lives | `HogJonny-AMZN/HogShade` (2026-09-20: the identical fork, renamed). Whether the legacy `hogjonny/Maya-PBR-BRDF-VP2` is transferred in and renamed to take over, keeping its 37 stars, is the owner's open call; see the roadmap, track B. |
| Name | **HogShade**. Joins the `hog_*` package family; "one polyglot PBR shading core" is the tagline. |
| History | Rewrite. Strip `testFiles/`, `images/`, `ShaderDevProj/` from history; reintroduce a minimal shader-ball scene and one HDR under Git LFS. Forks diverge; acceptable. |
| Licence | Apache 2.0. |
| v3.0 folder | Salvage: compile each v3 include against the v2 main file with fxc, keep any that compile and improve on v2, drop the rest, then delete the folder. |
| Parameter model | OpenPBR for the new model, as close as the viewport allows; document every deviation. |
| Legacy models | Kept, not replaced. This is a research shader, not a runtime one. The v1 Disney/Cook-Torrance/"game" BRDFs and the v2 model stay selectable alongside OpenPBR for exploration and side-by-side comparison. Clarity beats instruction count. |
| Shared code | One shading core, imported by every host and language. **Source language: WGSL** (owner, 2026-09-20: WebGPU is the native target now that SpriteJammer is the primary consumer). `naga` translates the core to HLSL and GLSL for the DCC hosts. Slang was the first choice and stays the documented fallback if naga's HLSL cannot be made to compile inside Maya's `.fx` shell; the spike that decides this is the first item of phase 2. |
| Hosts | Maya `dx11Shader` (HLSL `.fx`) first; Maya `glslShader` (`.ogsfx`) second; wgpu/WGSL for the owner's Python engine (`hog_rendering`, SpriteJammer) as a consumer of the same core; OSL for Blender Cycles, 3ds Max's native OSL map and the offline renderers (Arnold, RenderMan, V-Ray, 3Delight); MaterialX document last, for LookdevX and USD. |
| WGSL | The core itself. `hosts/wgpu/` adds only pass entry points. SpriteJammer and `hog_rendering` vendor the core files. First host, because it is the source. |
| Blender EEVEE | Two routes, both kept. (1) `hosts/blender_nodes/`: a Python add-on that builds a Principled BSDF node tree from the OpenPBR parameter model and emits `surface/` (triplanar, UV utils) as generated node groups; renders in EEVEE and Cycles alike and is the route artists use. (2) `hosts/blender_gpu/`: the core's GLSL, emitted by Slang, run through Blender's `gpu` module in a viewport draw handler; the research route, where the actual core code renders inside Blender for comparison. |
| 3ds Max | No dedicated host. The owner does not need Max; it is served by the OSL host, which Max runs natively through its OSL map (since 2019), and Max becomes one of the places the OSL host is validated. The `_3DSMAX_` scaffolding in the v2 code is not carried forward. |
| Modern HLSL | A maintained host, `hosts/hlsl/`: plain shader model 6 HLSL (no effect framework, which fxc already reports as deprecated), generated from the WGSL core by naga, committed, formatted and validated with dxc on every change, with a documented `cbuffer` and binding layout. It is what Unreal custom nodes, Unity, DX12 samples and anyone who reads HLSL consume. Generated, not hand-written: two hand-maintained sources is what this design exists to prevent. Maya's `.fx` shell wraps the same output for fxc. |
| OSL | A hand-maintained host, not a transpile target. Shares the parameter model, the `surface/` maths and the reference test vectors with the core; lobes are renderer closures. Lives on `main` under `hosts/osl/`, not a long-lived branch. |
| Game profile | OpenPBR restricted to what glTF 2.0 plus the KHR material extensions can carry, with a conversion table. Blender exports it, the engine imports it, nothing in between. |
| Interchange | The authored material is a MaterialX `.mtlx` document (OpenPBR is defined in MaterialX). Every host imports it. Moved from last host to phase 3. |
| Material UI | Generated from one parameter schema in every host; never hand-edited. |
| Alpha | One enum, glTF's OPAQUE / MASK / BLEND, mapped per host; MASK is the game default. |
| Parity | A calibration scene, per-host capture scripts and one diff tool land before the OpenPBR model. See `2026-09-20-wysiwyg-blindspots.md`. |
| Rendering paths | Deferred (SpriteJammer) and forward (Maya, Blender gpu, engine transparents and hero) served by one core split at the G-buffer boundary: a material half producing `ShadingInputs`, a lighting half consuming it, and a `gbuffer/` encode/decode between them. |
| Lights | The v2 "gather lights" pattern (DCC binds scene lights into fixed slots) is kept as the universal fallback, widened to 16 slots; the engine feeds a culled light buffer through the same interface. See the feature catalogue. |
| Triplanar | Build it properly: world-space three-axis projection, normalised weights, per-plane tangent frames for normal maps, parallax occlusion evaluated per projection. Depends on the core restructure. |

## Principles

- **Research project first.** The goal is to explore and compare shading models in a DCC viewport,
  not to ship the fastest possible shader. Prefer readable code, named intermediate values and
  debug views over micro-optimisation. Do not remove a path because a newer one exists.
- **Models are peers.** Every shading model, legacy or new, implements the same core interface and
  is chosen at runtime from the material UI. Comparison views render two models split-screen or
  as a difference image.
- **One source, many hosts.** The maths lives once, in the core, and every host and language
  imports it.

## Architecture: WGSL core, thin host shells

```text
src/
  core/                      # WGSL. No host, no UI, no effect syntax. Modules are files
                             #   stitched by tools/build_shaders.py (SpriteJammer's shader_loader
                             #   already concatenates common/ files this way).
    interface/               # IShadingModel split in two: inputs() builds ShadingInputs from the
                             #   material half; evaluate() turns ShadingInputs + lights into a
                             #   ShadingResult. Forward runs both; deferred runs them in two passes
    gbuffer/                 # encode/decode ShadingInputs to and from a G-buffer layout; the one
                             #   definition the fill pass, the light pass and screen-space effects share
    models/
      openpbr/               # OpenPBR slabs: base (diffuse, metal), specular, coat, fuzz,
                             #   emission, thin-film, subsurface (approximated), geometry (opacity)
      legacy_v1/             # 2015 models, ported verbatim: Disney "bigd", Cook-Torrance, "game"
      legacy_v2/             # 2017 model: the v2 uv0bn-pbs_IBLenv shading, ported verbatim
    brdf/                    # the toolbox every model draws from: NDFs (GGX, Beckmann, Blinn-Phong),
                             #   visibility terms (Smith height-correlated, Schlick-GGX, implicit),
                             #   Fresnel variants (Schlick, F82-tint, exact dielectric), multiscatter
                             #   energy term, diffuse models (Lambert, Burley, Oren-Nayar)
    compare/                 # split-screen and difference-image evaluation of two models
    ibl/                     # split-sum: prefiltered radiance + BRDF LUT; SH or irradiance map
    lighting/                # ILightSource + two providers: FixedSlots<N> (DCC-bound "gather"
                             #   slots, the v2 pattern, 16 by default) and LightBuffer (engine
                             #   culled list). One light loop per model against the interface
    surface/                 # triplanar projection, parallax occlusion, normal blending, UV utils
    color/                   # scene-linear in/out; view transforms (ACES, AgX) for hosts that
                             #   cannot delegate display to the DCC
  hosts/
    maya_dx11/               # .fx: techniques, passes, UI annotations, Maya semantics, transparency
    hlsl/                    # modern SM 6 HLSL from naga, committed, dxc-validated, cbuffer layout
                             #   documented; the maya_dx11 shell wraps it; UE, Unity, DX12 consume it
    maya_ogsfx/              # .ogsfx: same shell against GLSL emitted from the core
    wgpu/                    # the core as-is plus pass entry points; SpriteJammer and
                             #   hog_rendering consume it with no translation step
    blender_nodes/           # Python add-on: OpenPBR params -> Principled BSDF node tree, surface/
                             #   as generated node groups. EEVEE and Cycles. Artist route.
    blender_gpu/             # naga GLSL of the core via bpy `gpu` module in a draw handler. Research
                             #   route: the real core renders in Blender for comparison.
    osl/                     # .osl shaders for Cycles, 3ds Max OSL map, Arnold, RenderMan, V-Ray,
                             #   3Delight: closure
                             #   composition over the same parameter model; hand-maintained port of
                             #   surface/ (triplanar, UV utils) validated against core test vectors
    materialx/               # .mtlx document mapping the OpenPBR parameters for LookdevX and USD
tools/
  build_shaders.py           # stitch core modules → WGSL; naga → HLSL (SM 5.0) and GLSL into
                             #   hosts/*/generated/; naga validates WGSL, fxc validates the .fx shells
tests/
  compile/                   # naga validates the core; every host shell must compile: fxc for
                             #   dx11, glslangValidator for ogsfx, oslc for OSL. CI gate.
  reference/                 # BRDF LUT and furnace-test images regenerated from the core; a
                             #   white-furnace energy check per lobe
```

### Why WGSL is the source, and what that costs

The owner's engine is wgpu, so WGSL is the language the core runs in natively and the one that is
debugged in the engine. Generating it from another language (the original Slang plan) would have put
machine-written WGSL in the engine's hottest shaders. With WGSL as the source:

- **SpriteJammer consumes the core with no translation.** Its `shader_loader` already stitches
  `common/*.wgsl` ahead of pass files; the core is more of the same.
- **`naga`** (wgpu's own shader translator, part of the same project the engine depends on)
  emits HLSL and GLSL for the DCC hosts and validates WGSL. Its HLSL backend targets shader model
  5.0 and up, which is what `fx_5_0` effects wrap.
- **The cost is modules.** WGSL has no `import` and no preprocessor. Module boundaries are file
  boundaries and a stitching step in `build_shaders.py`; interfaces are conventions (a `ShadingInputs`
  struct and named `fn`s per model), not language features. Generics are out; the model selector is
  a `switch` on the shading-model ID. For a research shader this is acceptable and it is what the
  engine does already.
- **Maya's `.fx` shell wraps naga's HLSL.** naga emits free functions and structs; the shell
  declares the effect parameters, textures, samplers and techniques and calls into the generated
  code. The one open risk is naga's handling of samplers, texture bindings and `SV_` semantics
  inside an effect; the phase 2 spike settles it before anything else is built.
- **A modern HLSL host is a committed output, not a second source.** `hosts/hlsl/` holds naga's
  shader model 6 HLSL, formatted and validated with dxc, with a documented binding layout, so it
  reads and consumes as a maintained HLSL shader. If the owner ever wants HLSL to be the language
  the core is *written* in, the pipeline inverts: HLSL source, `dxc -spirv`, naga to WGSL and GLSL.
  That is a real option and it is not the one chosen, because WGSL is what the primary consumer
  runs and debugs.
- **Slang stays the fallback.** If the spike fails, the core moves to Slang and WGSL becomes an
  emitted target; every other decision in this document is unchanged.

The v2 code's `#ifdef _MAYA_` / `_3DSMAX_` scaffolding moves into the host shells and disappears
from the core; the `_3DSMAX_` branches are dropped, since Max is served by OSL.

Legacy source stays in the tree unchanged under `legacy/v1.0` and `legacy/v2.0` as the reference the
ports are checked against. They are not built; they are what "verbatim" means.

### Legacy v2 port: what was kept and what deviates (PR D, 2026-09-25)

`core/models/legacy_v2.wgsl` is `V2_uv0bn-pbs_IBLenv.fx` plus `pbr.sif`, function by function, on
the core interfaces. Kept verbatim because they are the look: specular carries NdotL squared (the
Hable GGX includes NdotL and the light term multiplies by it again); the GGX Fresnel uses only the
red channel of Cspec0 (it went through a `float` parameter) and the colour arrives through cSpecLin;
cSpecLin (`mix(Cspec0, base, metalness) * lut.x + lut.y`) scales the direct specular as well as the
environment specular; the final specular is multiplied by the linear base colour; diffuse is not
scaled by (1 - F), so a white furnace returns 1 + the specular albedo (a few percent facing, up to
0.57 at grazing, measured); the roughness bias goes on alpha for the lobes and on the perceptual
roughness for the lookups; NdotV is abs(n.v) + 1e-4.

Deviations, each recorded in the module header:

1. **Environment.** The E1 linear cubes and LUT replace RGBM 8-bit cubes: the RGBM decode, the `.bgr`
   swizzle, the exposure of 5, the gamma parameter and the constant nine-mip count are gone. Hosts
   pass linear values; colour management is the host's.
2. **Unbound maps.** The host passes defaults (white base, flat normal, roughness and metalness maps
   of one so the scalars rule, AO and cavity one) instead of v2's "black unless > 0" tests. The
   black specular from an unbound cavity map, found in E1's Maya check, goes with it.
3. **Lights.** Geometry and attenuation come from `lighting.wgsl` (windowed inverse square, smooth
   spot cone) instead of Maya's `1 / (d * decay)` and `cos(angle)`; a light's shadow scales that
   light only, where v2 multiplied the running sum, so the result depended on slot order; the
   "ambient" light kind, which contributed nothing in v2 (NdotL of -n is zero), is dropped.
4. **Emissive and the specular map.** Both were sampled and never used. Emissive is added by
   `models_shade`; the specular map scales `specular_weight` (its default of one keeps v2's output).
5. **Vertex AO** uses the red channel: `surface.ao` is a scalar.
6. **Host concerns.** POM, POM self-shadowing, depth peeling, tone mapping and the twelve debug
   modes that read texels or UVs stay in the host; the core answers those modes from the nearest
   `ShadingInputs` value so every mode is finite in a deferred host, and `legacy_v2_debug_inputs`
   computes them exactly for a forward host.

What stays hand-written per host: effect techniques and passes, UI annotations (`UIGroup`, `UIWidget`,
semantics like `WorldViewProjection`), texture and sampler declarations with host-specific semantics,
transparency passes. The core exposes a `ShadingInputs` struct and an `evaluate()` per lobe; a shell
fills the struct from its textures and constants and calls the core.

## Two rendering paths, one core split at the G-buffer boundary

SpriteJammer is deferred (ADR-002: a five-target G-buffer, lights resolved in a full-screen pass).
Maya, Blender's `gpu` viewport and the engine's transparent and hero passes are forward. The core
must serve both without two copies of the maths, so it is split in two halves with the G-buffer as
the seam:

```text
core/
  surface/   +  models/*/inputs   ->  ShadingInputs        (the "material" half)
  models/*/evaluate + lighting/   ->  ShadingResult        (the "lighting" half)
```

- **Forward.** One shader runs both halves: sample textures, project, parallax, layer, build
  `ShadingInputs`, then loop lights and evaluate. Maya `dx11Shader`, `ogsfx`, `blender_gpu`,
  Substance Painter, and the engine's `lit_mesh`, `skinned_mesh` and tier 3 hero pass.
- **Deferred.** `gbuffer_fill` runs the material half and encodes `ShadingInputs` into the
  G-buffer; `deferred_light` decodes it and runs the lighting half, branching on the shading-model
  ID. The encode and decode live in the core (`core/gbuffer/`) so the packing is one definition
  used by both passes and by the engine's other consumers (SSAO, SSR, decals).
- **Shadow and depth passes** run only the parts of the material half they need: alpha mask,
  vertex offset, and pixel depth offset. The core exposes those as a separate entry so the shadow
  pass does not sample the full material.

What the G-buffer can carry decides what the deferred tiers can shade. With ADR-002's layout
(albedo + AO, octahedral normal + roughness + metallic, classification byte, emissive, depth):

| Input | Deferred | Why |
| --- | --- | --- |
| Base colour, metalness, roughness, AO, emissive, normal | yes | Carried directly |
| Specular weight or IOR, specular colour | no, unless a spare channel is claimed | glTF `KHR_materials_specular` needs it; default IOR 1.5 is assumed in tier 2 |
| Anisotropy | no | Needs a tangent; octahedral normal has none |
| Coat, fuzz, thin-film, subsurface, transmission | no | Extra lobes and parameters; tier 3 forward |
| Alpha BLEND | no | Deferred is opaque and MASK; blend goes forward |
| Pixel depth offset | yes | Written in `gbuffer_fill`, read by every later pass |

Extending the G-buffer (a second normal for coat, a tangent, a spare `rgba8` for specular and
subsurface) is an engine decision with a bandwidth cost the engine's benchmarks price. The core
must not assume it; the encode function takes the layout as a parameter and the shading-model ID
says which inputs are valid.

Forward+ or a visibility buffer would change the pass structure but not this split; the material
half and the lighting half are the same functions either way.

## OSL: closures, not a transpile

OSL has no light loop; a surface shader returns a weighted sum of closures (`microfacet("ggx", ...)`,
`diffuse`, `sheen`, `emission`, and in Cycles the `principled_bsdf` closure) and the renderer
integrates them. The BRDF lobe code in `core/models/` therefore cannot be shared as text. What is
shared:

- **The parameter model.** The OpenPBR parameter set, defaults and texture packing are the same
  names in every host, so a material authored in Maya reads the same in Blender.
- **`surface/`.** Triplanar projection, UV utilities and normal blending are pure vector maths and
  port line-for-line. Parallax occlusion ports as UV offset only; OSL cannot clip silhouettes.
- **Test vectors.** The core's reference tests emit numeric fixtures (inputs, expected weights,
  projected UVs, Fresnel and NDF values) and the OSL host is checked against them with `testshade`
  from the OSL toolset, or Blender headless. This is how the OSL port is kept honest rather than
  by reading two files side by side.
- **Legacy models in OSL.** Cook-Torrance and the Disney lobes map to `microfacet` closures with
  the matching distribution; the "game" BRDF and any custom lobe can be expressed as a
  `generic_bsdf`-style closure only where the renderer supports it. Where a legacy model cannot
  be represented as a closure, the OSL host says so in a comment and skips it; it is not
  approximated silently.

## Blender: EEVEE and Cycles

Cycles runs OSL through the Script node on CPU and, since 4.x, on OptiX GPU. EEVEE runs neither OSL
nor user GLSL in its material system; its only material language is the node tree. Blender 4.x's
Principled BSDF is itself an OpenPBR-adjacent model (base, specular with IOR, coat, sheen, emission,
thin-film since 4.2, subsurface, transmission), so the honest EEVEE host is a **node-tree generator**:

- `hosts/blender_nodes/` is a Python add-on. Given a material in the OpenPBR parameter model, it
  builds the Principled BSDF tree, wires the packed textures, and inserts `surface/` as node groups
  (triplanar projection, UV utilities, normal blending) generated from the same source of truth as
  the core. The add-on is the Blender import for a material authored in the Maya host. It renders
  in EEVEE and Cycles alike, so it also gives Cycles a route that needs no OSL.
- Parameters Principled cannot express are listed by the generator at import time, not dropped
  silently. Parallax occlusion has no node equivalent and is omitted with a warning.
- `hosts/blender_gpu/` is the research route. Blender's `gpu` module runs user GLSL in a viewport
  draw handler, outside the material system. The core's GLSL, emitted by Slang, draws the shader
  ball inside Blender with the same lights and camera, so the legacy models and the comparison views
  work there. It is not a material and is not for artists.

USD and MaterialX import of OpenPBR is improving in Blender but is not yet a reliable material path,
so it is a cross-check for the node generator, not a host of its own.

The MaterialX host also yields OSL for free: MaterialX's OSL shader generator emits it from the
`.mtlx` document. That generated OSL is the cross-check for the hand-written host, not a
replacement for it; the hand-written one carries the research models and the debug views.

## OpenPBR fit in a rasterised viewport

Represent the full parameter set so textures round-trip, but implement lobes at viewport fidelity:

- Base, specular, coat, fuzz, emission, geometry opacity: real-time implementations exist for all.
- Subsurface: screen-space or wrap-lighting approximation; document the deviation.
- Transmission: thin-walled only; refraction is out of scope for a forward viewport shader.
- Thin-film: implement the iridescence term; it is cheap.
- Layering follows the OpenPBR slab order; energy conservation via the multiscatter term and
  albedo-scaling between slabs.

Output is scene-linear. One OCIO config in the repo drives display in every host that has colour
management, and the engine implements the same view transform numerically; the `color/` module exists for the
wgpu host and the `blender_gpu` viewport.

## Phases (each a PR; the gate is a Maya 2026 launch plus the compile tests)

Phases 1 and 2 are sequential. After phase 2 the hosts and models are independent and can proceed
in any order; the numbering below is the recommended one.

1. **Hygiene.** History rewrite via `git-filter-repo`, LFS test set, licence, `.gitignore`,
   README with the getting-started guide the open issue asks for, delete the `v.3.0` folder after
   salvage. Verify v2.0 loads in Maya 2026 `dx11Shader`; record what breaks.
2. **Restructure.** Spike first: naga-translated HLSL of one core module compiles inside a v2-style
   `.fx` shell under fxc and renders in Maya; if not, switch the core to Slang and continue. Then
   `naga` in the toolchain, `build_shaders.py`, compile tests in CI,
   the v1 and v2 shading ported into `core/models/legacy_*` behind the `maya_dx11` shell with
   pixel-identical output to the originals on the shader ball (screenshot diff). The model selector
   and the `brdf/` toolbox are born here, factored out of the legacy ports.
3. **OpenPBR shading.** A new model beside the legacy ones: GGX + multiscatter, split-sum IBL from
   HDR input, OpenPBR parameter set and slab layering, furnace tests. The comparison view lands here
   so OpenPBR can be judged against v2 on the same shader ball.
4. **Triplanar + POM.** The surface module; per-projection parallax; debug views for weights and
   projection axes.
5. **wgpu host.** `hosts/wgpu/`, the core's native home: pass entry points over the core files as-is, `naga` validation in CI, a wgpu test
   viewport (the `Spikes/wgpu_tile` pattern from LargeWorlds) rendering the shader ball for a
   screenshot diff against `maya_dx11`. SpriteJammer switches to consuming it.
6. **Other hosts.** `maya_ogsfx`, then Blender: the node generator (EEVEE and Cycles) first because
   it is the artist route, then `blender_gpu` for comparison, then OSL (Blender Cycles first, then
   3ds Max's native OSL map, verified against the core test vectors), then the MaterialX document,
   whose generated OSL cross-checks the hand-written host.

## Open questions for the owner

- Which HDR environment to ship under LFS (licence-clean; the old ones came from IBLBaker).

## References

- OpenPBR specification: https://academysoftwarefoundation.github.io/OpenPBR/
- naga (wgpu's shader translator): https://github.com/gfx-rs/wgpu/tree/trunk/naga (`cargo install naga-cli`)
- WGSL specification: https://www.w3.org/TR/WGSL/
- Slang, the fallback: https://shader-slang.org/ (pip: `shader-slang`)
- Open Shading Language: https://github.com/AcademySoftwareFoundation/OpenShadingLanguage
  (`oslc`, `testshade`); Blender Cycles OSL: Script node docs
- Maya dx11Shader / glslShader effect annotations: Autodesk Maya developer docs, "Shader plug-ins"
- Original credits carried forward from the 2015 README (derkreature IBLBaker and ShaderBall,
  Hable, Pestana, Disney BRDF notes, Driscoll).
