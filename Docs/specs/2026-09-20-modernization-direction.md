# Maya-PBR-BRDF-VP2 modernization: direction

Date: 2026-09-20. Status: direction agreed with the owner; no code changed yet.
This is the pre-plan design record. The phased plan with checkboxes follows once phase 1 lands.

## Goal

Own one shader and use it anywhere the pipeline, the content tools or a workflow needs it. The
repo is the HogJonny-AMZN-owned fork, port and eventual replacement of the 2015 Maya shader; the
core is the single source and every DCC, renderer and engine target is a host of it.

## What the repo is today

- HLSL 5 `.fx` effect shaders for Maya Viewport 2.0 `dx11Shader`, two generations:
  `src/Shaders/HLSL/v.1.0` (2015) and `v.2.0` (2017: IBL, parallax occlusion mapping, tone
  mapping, depth-peeling transparency, a 32-mode debug view). Last real commit August 2017.
- 37 stars, 12 forks, one open issue asking for a getting-started guide. No licence.
- History is 128 MB: Maya scenes, IBL `.dds` cubes, Visual Studio debug output and PSDs. One 20 MB
  scene is committed sixteen times.
- A `v.3.0` folder dated 2025-04-26/27 sits uncommitted on the owner's machine. Its main `.fx` is
  corrupted (interleaved line fragments). Three includes were rewritten to a quarter of their v2 size
  and may or may not compile. `V2_`/`V3_` variants are byte copies of v2. Archived to
  `D:\Depot\Maya-PBR-BRDF-VP2_BAK\uncommitted-v3.0-2025-04` before any cleanup.
- Triplanar does not exist as a feature. Debug view 32 computes per-axis blend weights from the world
  normal and displays them. No texture is sampled through them and the weights are not normalised.

## Decisions (owner, 2026-09-20)

| Question | Decision |
| --- | --- |
| Where the repo lives | Transfer `hogjonny/Maya-PBR-BRDF-VP2` to `HogJonny-AMZN` (keeps stars, forks, issue, URL redirect). The identical fork was renamed to `Maya-PBR-BRDF-VP2-old-fork` to free the name; delete it after the transfer. |
| History | Rewrite. Strip `testFiles/`, `images/`, `ShaderDevProj/` from history; reintroduce a minimal shader-ball scene and one HDR under Git LFS. Forks diverge; acceptable. |
| Licence | Apache 2.0. |
| v3.0 folder | Salvage: compile each v3 include against the v2 main file with fxc, keep any that compile and improve on v2, drop the rest, then delete the folder. |
| Parameter model | OpenPBR for the new model, as close as the viewport allows; document every deviation. |
| Legacy models | Kept, not replaced. This is a research shader, not a runtime one. The v1 Disney/Cook-Torrance/"game" BRDFs and the v2 model stay selectable alongside OpenPBR for exploration and side-by-side comparison. Clarity beats instruction count. |
| Shared code | One shading core, imported by every host and language. Slang modules (see below). |
| Hosts | Maya `dx11Shader` (HLSL `.fx`) first; Maya `glslShader` (`.ogsfx`) second; wgpu/WGSL for the owner's Python engine (`hog_rendering`, SpriteJammer) as a consumer of the same core; OSL for Blender Cycles, 3ds Max's native OSL map and the offline renderers (Arnold, RenderMan, V-Ray, 3Delight); MaterialX document last, for LookdevX and USD. |
| WGSL | A first-class host maintained here, emitted from the Slang core by `build_shaders.py` and validated with `naga`. SpriteJammer and `hog_rendering` consume the generated `hosts/wgpu/generated/*.wgsl` (vendored or via a git dependency), never a hand-edited copy. Second host after `maya_dx11` because it serves the owner's active projects. |
| Blender EEVEE | Two routes, both kept. (1) `hosts/blender_nodes/`: a Python add-on that builds a Principled BSDF node tree from the OpenPBR parameter model and emits `surface/` (triplanar, UV utils) as generated node groups; renders in EEVEE and Cycles alike and is the route artists use. (2) `hosts/blender_gpu/`: the core's GLSL, emitted by Slang, run through Blender's `gpu` module in a viewport draw handler; the research route, where the actual core code renders inside Blender for comparison. |
| 3ds Max | No dedicated host. The owner does not need Max; it is served by the OSL host, which Max runs natively through its OSL map (since 2019), and Max becomes one of the places the OSL host is validated. The `_3DSMAX_` scaffolding in the v2 code is not carried forward. |
| OSL | A hand-maintained host, not a transpile target. Shares the parameter model, the `surface/` maths and the reference test vectors with the core; lobes are renderer closures. Lives on `main` under `hosts/osl/`, not a long-lived branch. |
| Game profile | OpenPBR restricted to what glTF 2.0 plus the KHR material extensions can carry, with a conversion table. Blender exports it, the engine imports it, nothing in between. |
| Interchange | The authored material is a MaterialX `.mtlx` document (OpenPBR is defined in MaterialX). Every host imports it. Moved from last host to phase 3. |
| Material UI | Generated from one parameter schema in every host; never hand-edited. |
| Alpha | One enum, glTF's OPAQUE / MASK / BLEND, mapped per host; MASK is the game default. |
| Parity | A calibration scene, per-host capture scripts and one diff tool land before the OpenPBR model. See `2026-09-20-wysiwyg-blindspots.md`. |
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

## Architecture: Slang core, thin host shells

```text
src/
  core/                      # Slang modules. No host, no UI, no effect syntax.
    interface/               # IShadingModel: ShadingInputs -> ShadingResult; what every model
                             #   implements and every host calls
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
    maya_ogsfx/              # .ogsfx: same shell against GLSL emitted from the core
    wgpu/                    # WGSL emitted from the core; consumed by hog_rendering / SpriteJammer
    blender_nodes/           # Python add-on: OpenPBR params -> Principled BSDF node tree, surface/
                             #   as generated node groups. EEVEE and Cycles. Artist route.
    blender_gpu/             # core GLSL via bpy `gpu` module in a viewport draw handler. Research
                             #   route: the real core renders in Blender for comparison.
    osl/                     # .osl shaders for Cycles, 3ds Max OSL map, Arnold, RenderMan, V-Ray,
                             #   3Delight: closure
                             #   composition over the same parameter model; hand-maintained port of
                             #   surface/ (triplanar, UV utils) validated against core test vectors
    materialx/               # .mtlx document mapping the OpenPBR parameters for LookdevX and USD
tools/
  build_shaders.py           # slangc → HLSL/GLSL/WGSL into hosts/*/generated/; fxc/dxc validate
tests/
  compile/                   # every host shell must compile: fxc for dx11, glslangValidator for
                             #   ogsfx, naga for WGSL, oslc for OSL. CI gate.
  reference/                 # BRDF LUT and furnace-test images regenerated from the core; a
                             #   white-furnace energy check per lobe
```

Why Slang and not macro-portable HLSL: Slang has real `import` modules, generics and interfaces,
compiles to HLSL, GLSL, SPIR-V, Metal and WGSL from one source, is hosted by Khronos and used by
NVIDIA, Valve and Unity. It ships as a pip package (`shader-slang` provides `slangc`), so it fits the
uv toolchain. Macro-portable HLSL would need a hand-maintained prelude per language and cannot express
the module boundary. The v2 code already has `#ifdef _MAYA_` / `_3DSMAX_` scaffolding; that scaffolding
moves into the host shells and disappears from the core; the `_3DSMAX_` branches are dropped, since
Max is served by OSL.

Legacy source stays in the tree unchanged under `legacy/v1.0` and `legacy/v2.0` as the reference the
ports are checked against. They are not built; they are what "verbatim" means.

What stays hand-written per host: effect techniques and passes, UI annotations (`UIGroup`, `UIWidget`,
semantics like `WorldViewProjection`), texture and sampler declarations with host-specific semantics,
transparency passes. The core exposes a `ShadingInputs` struct and an `evaluate()` per lobe; a shell
fills the struct from its textures and constants and calls the core.

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
   salvage. Verify v2.0 loads in Maya 2024 and 2026 `dx11Shader`; record what breaks.
2. **Restructure.** Slang toolchain in `pyproject.toml`, `build_shaders.py`, compile tests in CI,
   the v1 and v2 shading ported into `core/models/legacy_*` behind the `maya_dx11` shell with
   pixel-identical output to the originals on the shader ball (screenshot diff). The model selector
   and the `brdf/` toolbox are born here, factored out of the legacy ports.
3. **OpenPBR shading.** A new model beside the legacy ones: GGX + multiscatter, split-sum IBL from
   HDR input, OpenPBR parameter set and slab layering, furnace tests. The comparison view lands here
   so OpenPBR can be judged against v2 on the same shader ball.
4. **Triplanar + POM.** The surface module; per-projection parallax; debug views for weights and
   projection axes.
5. **WGSL host.** `hosts/wgpu/` emitted from the core, `naga` validation in CI, a wgpu test
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
- Slang: https://shader-slang.org/ (pip: `shader-slang`)
- Open Shading Language: https://github.com/AcademySoftwareFoundation/OpenShadingLanguage
  (`oslc`, `testshade`); Blender Cycles OSL: Script node docs
- Maya dx11Shader / glslShader effect annotations: Autodesk Maya developer docs, "Shader plug-ins"
- Original credits carried forward from the 2015 README (derkreature IBLBaker and ShaderBall,
  Hable, Pestana, Disney BRDF notes, Driscoll).
