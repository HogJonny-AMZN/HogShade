# HogShade roadmap: the shading research repo and everything around it

Date: 2026-09-20. Owner: Jonny Galloway. Companion to
[design/2026-09-20-modernization-direction.md](design/2026-09-20-modernization-direction.md), which
holds the architecture detail. This document is the order of work across four tracks and the
gates between them. Tick items as they land.

## The goal

**Own one shader and use it anywhere the pipeline, the content tools or a workflow needs it.**
One shading core, authored once, owned by HogJonny-AMZN, that lands as a Maya look-dev material, a
Blender material, an OSL shader for offline renderers, a MaterialX document for USD, and the lighting
model inside the owner's own wgpu engine. The legacy Maya shader is the seed; HogShade is its owned
fork, port and eventual replacement, under the HogJonny-AMZN account. The name joins the
`hog_color`, `hog_wild` and `hog_rendering` family; "polyglot" is the tagline.

Every item below serves that sentence. An item that does not is out of scope.

## The one-paragraph version

Maya-PBR-BRDF-VP2 becomes **HogShade**, a shading research repo: one WGSL core holding several shading models as
peers (the 2015 and 2017 legacy models kept verbatim, plus a new OpenPBR model), imported by thin
hosts for Maya, modern HLSL, Blender, wgpu, OSL and MaterialX. SpriteJammer consumes the wgpu host through its
existing shading-model ID, with three quality tiers so a modern PBR look is the default and a cheaper
model is one byte away when the frame budget says so. Around that sit the repo transfer and history
cleanup that make the work publishable, and the employer conversation that decides what else can be.

## Tracks

| Track | What | Blocks |
| --- | --- | --- |
| A | GitHub profile and open-source clearance | Publishing anything from LargeWorlds, Job_Orchestrator, BATS |
| B | Maya-PBR-BRDF-VP2 repo hygiene | Everything in C and D |
| C | Shading core and hosts | The SpriteJammer tiers |
| D | SpriteJammer PBR tiers | Nothing downstream; it is the consumer |
| E | Parity and pipeline: colour, lights, textures, capture and diff | Every "looks the same" claim in C and D |

Tracks A and B are independent. C follows B. E starts with B and its capture tooling gates C3.
D follows C5 but its G-buffer prep and the bake decision can start any time. The reasoning behind E
is [design/2026-09-20-wysiwyg-blindspots.md](design/2026-09-20-wysiwyg-blindspots.md).

## Track A: profile and clearance

- [ ] Move the private `Bluepoint` backup repo off GitHub before raising anything with the employer.
- [ ] Ask the manager, in writing, about open-sourcing LargeWorlds under Apache 2.0, stating plainly
      that `hog_color` is a rewrite of `bp_color`, which was written for Bluepoint use. Offer to
      release the other packages separately if `hog_color` is refused.
- [ ] Raise Job_Orchestrator second, with the commit-time evidence (about 60 percent outside work
      hours, 70 commits from an employer address). BATS last or not at all.
- [ ] Archive the dead public repos (2022 O3DE templates, tutorial scaffolds, one-day experiments).
- [ ] Pin four repos: CO3DEX, Maya-PBR-BRDF-VP2, the O3DE fork, and whichever private repo is
      cleared first.
- [ ] Profile README pointing at the O3DE contribution history (428 commits, 44 merged PRs, about
      130 reviews across the org).
- [ ] Standing rule for every repo that might be published: no employer names, personal email only,
      no files copied from a studio tree, Apache-compatible dependencies only. Recorded in memory as
      the hygiene rule; LargeWorlds was scrubbed in commit 9d9e963e.

## Track B: repo hygiene (phase 1 of the spec)

Gate to finish: v2.0 loads in Maya 2026 `dx11Shader`; clone under 5 MB; licence present.

- [x] The fork under `HogJonny-AMZN` is renamed **HogShade** (2026-09-20) and is the working repo
      today; the docs branch lives there. Old URLs redirect.
- [ ] Owner decides the transfer. Path A: transfer `hogjonny/Maya-PBR-BRDF-VP2` to `HogJonny-AMZN`
      (keeps 37 stars, forks, the issue), then delete the HogShade fork after re-pushing its branches
      and rename the transferred repo to HogShade. Path B: skip the transfer; HogShade stays as is and
      the legacy repo gets a one-line README pointing at it. Either way `origin` is HogShade.
- [ ] Commit the spec and this roadmap as the first change.
- [ ] `git-filter-repo`: strip `testFiles/`, `images/`, `ShaderDevProj/` from history. Force-push.
- [ ] Git LFS: one shader-ball scene, one licence-clean HDR (owner picks), the packed test textures.
- [ ] Close the getting-started issue on the legacy repo, pointing at the README.
- [x] v3.0 salvage (2026-09-20): six of eleven includes compile against v2; all six are reformats.
      Nothing taken. Folder deleted; archive stays at
      `D:\Depot\Maya-PBR-BRDF-VP2_BAK\uncommitted-v3.0-2025-04`. Details in the direction spec.
- [x] Move `src/Shaders/HLSL/v.1.0` and `v.2.0` to `legacy/` unchanged. They are the reference.
- [x] Both legacy shaders compile clean under `fxc /T fx_5_0 /D _MAYA_=1` (warnings only).
- [x] Apache 2.0 licence, `.gitignore` rewritten, README with the getting-started guide.
- [ ] Launch Maya 2026, load the v2 shader on the shader ball, screenshot, record what
      breaks. This screenshot is the baseline every later phase diffs against. Headless `mayapy`
      cannot do it (no DirectX device); a scripted GUI launch (`maya.exe -script`) or the
      Job_Orchestrator Maya GUI worker is the automated route.

## Track C: shading core and hosts (phases 2 to 6 of the spec)

Gate for every phase: the compile tests pass and the Maya 2026 screenshot diff is explained.

### C2. Restructure

The core is written in WGSL (owner, 2026-09-20). `naga` translates it for the DCC hosts.

- [ ] **Spike, before anything else:** one core module (a GGX lobe) in WGSL, translated by `naga` to
      HLSL, wrapped in a v2-style `.fx` shell, compiled by fxc and rendered in Maya 2026. Samplers,
      texture bindings and semantics are the risk. Pass: continue. Fail: the core moves to Slang and
      WGSL becomes an emitted target; nothing else in the roadmap changes.
- [ ] Toolchain: `naga-cli` (Rust; `cargo install naga-cli`, or a pinned binary in CI) and
      `tools/build_shaders.py` stitching core modules and emitting HLSL and GLSL into
      `hosts/*/generated/`. No Rust toolchain is on the owner's machine today; adding one is a
      dependency decision to make consciously.
- [ ] `tests/compile/`: naga validates the core; fxc for dx11, glslangValidator for ogsfx, oslc for
      OSL. CI.
- [ ] `core/interface/`: `ShadingInputs`, `ShadingResult`, `IShadingModel` split into `inputs()`
      (material half) and `evaluate()` (lighting half) so forward runs both and deferred runs them
      in two passes. A shadow/depth entry exposes alpha mask, vertex offset and PDO alone.
- [ ] `core/gbuffer/`: encode and decode `ShadingInputs` against a layout parameter; ADR-002's
      layout is the first. The engine's fill and light passes and its screen-space effects share it.
- [ ] `core/models/legacy_v1/` and `legacy_v2/`: verbatim ports. Pixel-identical to the baseline
      screenshot on the shader ball.
- [ ] `core/brdf/`: the toolbox factored out of the ports (NDFs, visibility, Fresnel, diffuse).
- [ ] `core/lighting/`: `ILightSource`, `FixedSlots<16>` filled by Maya's `Object = "Light N"`
      binding (the v2 gather pattern, up from 4 slots), and `LightBuffer` for the engine. The
      legacy ports' light loops are rewritten against the interface with identical output.
- [ ] `hosts/maya_dx11/`: the `.fx` shell with the model selector in the material UI.

### C3. OpenPBR model and the MaterialX carrier

Gate: E's calibration capture runs in `maya_dx11` before this phase opens, so OpenPBR is judged by it.

- [ ] `hosts/materialx/`: the `.mtlx` document is the authored material. Moved here from last place
      because it is the interchange every other host imports. Its generated OSL and GLSL become
      cross-checks for the hand-written hosts from now on.
- [ ] Parameter schema: one machine-readable definition (name, type, range, default, UI group,
      colour space) from which the Maya annotations, the Blender panel, the engine panel and the
      docs table are generated. A test asserts no host's UI is hand-edited.
- [ ] Alpha mode enum on the material: OPAQUE, MASK, BLEND as glTF defines them; per-host mapping
      documented; MASK is the game default.

- [ ] `core/models/openpbr/`: base, specular, coat, fuzz, emission, thin-film, geometry opacity.
      Subsurface as wrap-lighting, transmission thin-walled only, both documented as deviations.
- [ ] GGX with height-correlated Smith and a multiscatter energy term; split-sum IBL from an HDR
      input with a generated BRDF LUT.
- [ ] Scene-linear output; Maya colour management does the display.
- [ ] `core/compare/`: split-screen and difference views. First use: OpenPBR against v2.
- [ ] White-furnace test per lobe in `tests/reference/`.

### C4. Surface authoring (the game-like features; see the feature catalogue)

- [ ] `core/surface/`: three-axis world projection with an explicit up axis and tiling scale in
      metres (each host passes its own axis and unit conversion), normalised weights, per-plane
      tangent frames for normal maps, parallax occlusion per projection.
- [ ] Pixel depth offset from the parallaxed height, and the same offset in the shadow pass.
      SpriteJammer's Depth Offset Maps are this feature; the Maya host writes `SV_Depth`.
- [ ] Debug views: weights, projection axes, parallax offset, layer weights.
- [ ] Legacy POM stays available under the legacy models; the new one is a separate path.
- [ ] Stochastic or hex tiling; biplanar as the cheap variant for the horde tier.
- [ ] Detail maps (normal, albedo, roughness) with RNM blending and a mask; macro variation noise.
- [ ] World-aligned coverage (snow, moss, dust) and wetness, both from the triplanar up weight.
- [ ] Height-based layer blending and index or weight splat blending; two-sided foliage with thin
      translucency; wind vertex offset behind a mask.
- [ ] Specular occlusion from AO and bent normals, cavity, horizon clamp, micro-shadowing.
- [ ] Geometric specular anti-aliasing in the shader; normal-variance roughness in the cook (track E).

### C5. wgpu host (the core's native home)

- [ ] `hosts/wgpu/`: pass entry points over the core (`gbuffer_fill`, `deferred_light`, forward
      `lit_mesh`), `naga`-validated in CI. No generated step; the core files are the deliverable.
- [ ] A wgpu test viewport on the `Spikes/wgpu_tile` pattern from LargeWorlds, drawing the shader
      ball for a screenshot diff against `maya_dx11`.
- [ ] A **game profile** of the core defined as OpenPBR restricted to what glTF 2.0 and its KHR
      material extensions can carry, with a conversion table in the repo. Blender exports it and the
      engine imports it with no code in between. Anything outside glTF is forward-only (tier 3) by
      definition.
- [ ] Publish the core WGSL as the artifact SpriteJammer and `hog_rendering` vendor.

### C6. Other hosts

- [ ] `hosts/hlsl/`: the modern HLSL host. naga's SM 6 output committed and formatted, dxc validation
      in CI beside fxc, a documented cbuffer and binding layout, a README for Unreal, Unity and DX12
      consumers. The `maya_dx11` shell wraps this file rather than its own copy.
- [ ] `hosts/maya_ogsfx/`: GLSL shell for OpenGL Maya and Mac.
- [ ] `hosts/blender_nodes/`: Python add-on building a Principled BSDF tree from the OpenPBR
      parameter model, `surface/` as generated node groups. EEVEE and Cycles. Lists what Principled
      cannot express instead of dropping it. This is the Blender artist route.
- [ ] `hosts/blender_gpu/`: the core's GLSL through Blender's `gpu` module in a viewport draw
      handler, drawing the shader ball for comparison. Research only.
- [ ] `hosts/osl/`: Blender Cycles first, then 3ds Max's native OSL map as the second validation
      target (no Max-specific host; the OSL file is the Max deliverable; the owner has a Max licence). Closure composition over
      the same parameter model;
      `surface/` ported line-for-line; checked against the core's numeric test vectors with
      `testshade`. Legacy models map to `microfacet` closures where a closure exists and are
      declared unsupported where one does not.
- [ ] Substance Painter GLSL host, optional: the game profile as a Painter viewport shader so the
      texturing tool is WYSIWYG too. Cheap because it is GLSL the core already emits.

## Track D: SpriteJammer PBR tiers

SpriteJammer today: five-target deferred G-buffer (ADR-002) already carrying octahedral normal,
roughness, metallic, AO and emissive, a shading-model ID byte in GB2, and a `deferred_light.wgsl`
that lights with Lambert only. The frame is 75 to 79 percent crowd simulation and 20 to 24 percent
render, at 12.8 to 18.9 ms against a 16.67 ms budget on a 5090, with a 3070 as the real target.
Render headroom is thin, so the tiers are the design, not an afterthought.

### The tiers

| ID | Model | Source | Cost | When |
| --- | --- | --- | --- | --- |
| 0 | Lambert | today's `deferred_light.wgsl` | baseline | Floor. Never removed. |
| 1 | Game legacy | `core/models/legacy_v1` "game" BRDF: Blinn-Phong or GGX-lite, Schlick Fresnel, no IBL | small | Horde far tier, or whole frame under pressure |
| 2 | Game standard | `core/brdf` GGX, height-correlated Smith, split-sum IBL with one prefiltered probe and the LUT | moderate | Default for hero, near tier, terrain, props |
| 3 | OpenPBR forward | full model, forward pass | large | Hero and hand-placed set pieces only, forward-drawn after the deferred resolve |

SpriteJammer is deferred, so the core's material half runs in `gbuffer_fill` and its lighting half in
`deferred_light`; forward is kept for transparents and the tier 3 hero pass. Surface-authoring cost
(POM, tiling, layering) is paid once per pixel and does not scale with lights; the physics tier is
what scales with lights. The two are capped independently.

The ID is already per-pixel in GB2, so a material chooses its tier and the light pass branches on it.
A global cap clamps every ID down under budget pressure, so falling back is a runtime setting, not a
rebuild. Tier 3 needs data the G-buffer does not carry and is therefore forward-only; it is the one
tier that costs a second draw.

### Work

- [ ] Measure first: the S3 harness (500 lights at 5120x1440) with tier 0, then a stub tier 2, so
      the cost of PBR in the deferred pass is a number before any material is authored.
- [ ] Vendor the HogShade core from track C5 into `src/sj_render/shaders/common/`; the shader
      loader concatenates it ahead of the pass files. One ADR in SpriteJammer records that the
      shading maths is imported, not owned.
- [ ] `gbuffer_fill.wgsl` runs the core's material half and `core/gbuffer/` encode; the shadow and
      depth passes use the core's shadow entry so alpha masks and PDO match the main pass.
- [ ] Decide, with a benchmark, whether to claim a spare G-buffer channel for specular weight or
      IOR (glTF `KHR_materials_specular`) or assume IOR 1.5 in tier 2. Extending the G-buffer is an
      engine decision priced in bandwidth; the core takes the layout as a parameter either way.
- [ ] `deferred_light.wgsl` switches on the shading-model ID with tiers 0 to 2. Tier 1 and 2 land
      together so the comparison is available on day one.
- [ ] One IBL probe for the arena (the octahedral machinery already exists), a BRDF LUT texture
      generated by the core's reference test and shipped as content.
- [ ] `lit_mesh.wgsl` and `skinned_mesh.wgsl` gain the same tier switch for the forward path.
- [ ] Global tier cap exposed through the command bus so the agent interface can drop the tier the
      way it sets any other property.
- [ ] Benchmark write-up per tier in `docs/research/benchmarks/`, on the 3070 as well as the 5090.
- [ ] Impostor bake (ADR-010) outputs game-profile channels per octahedral view, not lit colour, and
      renders them through the core so runtime lighting matches look-dev. Lit-colour bake stays as an
      explicit cheaper option labelled as breaking parity.
- [ ] Specular anti-aliasing: roughness from normal variance in the texture cook, geometric SAA in
      the light pass. Measured on the crowd at the long lens, not on the shader ball.
- [ ] Tier 3 only after the hero art needs coat or fuzz. It is a forward material, not a G-buffer
      change.
- [ ] Material live link, later: Maya host parameter changes publish over the command bus (S16) to a
      running engine, keyed by material name. The bus must not preclude it.
- [ ] Material authoring: the Maya `dx11Shader` host is the look-dev tool. A material authored there
      in the game profile exports its textures and parameters in the same names SpriteJammer reads.

## Track E: parity and pipeline

The inputs and the proof. Without these, "same shader" produces different pictures.

- [ ] One OCIO config in the repo; Maya and Blender point at it; the engine implements the same view
      transform and proves it numerically against OCIO on a test ramp (`hog_color` has AgX and ACES).
      Texture colour space declared per texture in the material, never inferred from a filename.
- [ ] Light-rig description: HDR file, rotation in a stated axis convention, exposure in EV, punctual
      lights in one unit with a documented conversion per host.
- [ ] IBL prefilter and BRDF LUT baked by one tool in this repo, shipped as content, run as a BATS job.
      No real-time host convolves its own.
- [ ] Texture conventions written down: OpenGL +Y normals, ORM packing, sRGB only for base colour and
      emissive, linear-space mips, BC5 normals and BC7 colour. Authoring set (one map per parameter)
      and runtime set (packed, compressed) with one cook tool, run as a BATS job.
- [ ] MikkTSpace everywhere: the engine importer generates tangents when the file has none; the Maya
      host reads supplied tangents; the calibration scene ships them.
- [ ] Calibration scene: metal and dielectric roughness ramps, 18 percent grey card, colour checker,
      normal-map test tile, triplanar cube, one alpha cutout. Same camera, rig and HDR in every host.
- [ ] Capture script per host: `mayapy` batch, `blender -b`, the engine's offscreen path. One diff
      tool with tolerance and background mask, producing a proof page. Lands before C3.
- [ ] Pin naga and wgpu-py; CI on Maya 2026 where licensing allows, Blender
      LTS; commit `hosts/*/generated/` with a CI check that regeneration produces no diff.
- [ ] **HogShade job library for Job_Orchestrator and BATS.** Every reproducible step (texture cook,
      IBL and LUT bake, calibration capture per host, sprite bake) is a MODULE-mode job in a
      `hogshade.jobs` package with a manifest per job: name, one-paragraph description written for
      an agent, parameter schema with types and defaults, worker type (Maya headless, Maya GUI,
      Blender, Python), inputs and outputs. The library registers with the orchestrator's worker
      and tool registry so the MCP server's `list_tools` and `list_worker_types` surface it, and
      an LLM can find a job, read what it does and submit it without reading source. Job clones
      and cooked outputs stay local, never in this repo. Owned jointly with Job_Orchestrator; the
      registration mechanism is that repo's, the jobs are this one's.

## Gates that only the owner passes

1. The repo transfer (track B cannot start without it).
2. The employer answer on LargeWorlds and `hog_color` (track A).
3. Which HDR environment ships under LFS.
4. Whether the horde ever needs tier 2, or tier 1 is the ceiling for anything at distance. The
   benchmark decides; the owner reads it.

## What is deliberately not on this roadmap

- Refraction or real subsurface in the viewport shader.
- A hand-written WGSL that diverges from the core. If the generated code is too slow, the fix is a
  cheaper tier in the core, so every host gets it.
- Rewriting the legacy models to be "better". They are the record.
- Any history rewrite after the one in track B.
