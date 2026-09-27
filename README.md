# HogShade

**One shading core, written once, that looks the same in every tool a game is made with.**

HogShade is a shading research repo and a working shader. One core in WGSL holds several shading
models as peers (the author's 2015 and 2017 legacy models kept verbatim, an OpenPBR model next), and
thin hosts import it: Maya's DirectX 11 viewport, modern HLSL, wgpu, Blender, OSL and MaterialX.
It replaces [Maya-PBR-BRDF-VP2](https://github.com/hogjonny/Maya-PBR-BRDF-VP2), the same author's
physically based HLSL shader for Maya Viewport 2.0, now frozen as a record that points here.

The rest of this page is the case for the direction: what the repo is for, whether its goal is
even possible, why a portable look is worth more than it sounds, why game features matter as much
as correct physics, and what it costs. Then status, the map, and how to run it.

## The direction, in one paragraph

A material is authored once, in one vocabulary (OpenPBR names, a MaterialX document as the carrier),
against one shading core whose every function has a NumPy twin and a GPU test. Each tool the author
works in gets a host: a shell that binds that tool's textures, lights and parameters to the core's
functions and nothing more. The inputs that make two renderers disagree (colour management, light
units, texture conventions, tangent basis) are pinned by the repo, not left to each host's default.
A comparison framework captures the same scene in every host and reports where they differ and by
how much. Game-like surface features (projections, parallax, layers, detail, masks, vertex colour)
are first-class in the core beside the physics, because they are most of what an artist touches.

## WYSIWYG everywhere: is it possible?

Not in the naive sense, and the repo does not claim it. A rasterised viewport has no global
illumination; Cycles importance-samples an environment that a real-time host reads as prefiltered
mips; a deferred engine carries less per pixel than a forward viewport. Two different renderers will
never produce identical pixels, and a promise that they will is the kind of promise that gets
debugged by eye at midnight.

What is possible, and what this repo is built to deliver:

| Layer | What "the same" means | How it is proven |
| --- | --- | --- |
| The BRDF | Identical maths in every host, to floating-point tolerance | Every core function has a NumPy twin and a GPU test; every host imports the same generated file, never a re-implementation |
| The inputs | The same colour pipeline, light units, texture conventions and tangent basis everywhere | One OCIO config (ACEScg working space, AgX default view, ACES alternative), a light-rig description in stated units, texture conventions written down, MikkTSpace as a requirement rather than a convention |
| The picture | The difference between two hosts is measured, attributable and either accepted or fixed | A comparison framework: the same calibration scene captured in every host, scene-referred and display-referred, per-feature tolerances, a pass / needs-review / fail verdict, a report a human reads |

The honest framing: **WYSIWYG here is a tolerance, not a promise.** A shared BRDF is roughly a
third of it; the inputs and the proof are the other two thirds, and the original direction had
covered the BRDF well and the rest barely
([Docs/design/2026-09-20-wysiwyg-blindspots.md](Docs/design/2026-09-20-wysiwyg-blindspots.md)).
The repo's job is to make every remaining difference attributable to a named cause: shading, an
input, or the display. A difference nobody can attribute is the thing this project exists to end.

## Why a portable look is worth more than it sounds

The cost of not having one is paid in small, unmeasured pieces, which is why it is easy to
understate. It is paid every time a material exists in more than one tool:

| Without a portable core | With one | What to measure |
| --- | --- | --- |
| A material is authored once per tool: the Maya look, the engine material, the Blender node tree, each by hand, each drifting | Authored once; every host's parameter panel is generated from one schema | Parameters authored per material: N hosts against 1 |
| A look-dev decision (roughness here, tint there) is re-made per host, from memory | Made once, carried by the document | Look-dev decisions re-made: N against 0 |
| "It looks different in the engine" is debugged by eye, a picture beside a picture | A diff report names the region, the metric and the likely cause | Time to attribute one difference: hours against minutes |
| A shading fix lands in one tool and waits for the others | One pull request lands it everywhere the core is imported | Hosts updated per shading change: 1 against all. The legacy v1 port landed in wgpu and Maya in one PR |
| A regression is found when someone notices a picture | A regression fails a numeric test before any host renders | Regressions caught before a render: the NumPy twins and GPU tests, on every push |
| A new tool means a new shader | A new tool means a shell: bind textures, lights and parameters | Time to first picture in a new host: the Maya shell was one pull request over the generated core |
| Baked content (normals, AO, curvature) is trusted per tool | Bakes are compared against one reference bake with stated tolerances | Bake error per map, against Blender's bake |

The right-hand column is what the comparison framework will publish as numbers. Until it exists,
the evidence is this repo's own history: the same shading model verified in two hosts from one
change, with pictures under `verification/`. When the numbers exist they go here.

## Physics correctness is not the whole job

OpenPBR says how a surface responds to light. It says nothing about how the inputs reach a pixel:
projected without seams, tiled without repetition, layered by height, detailed at close range,
masked by vertex colour, occluded by a heightfield, wet on the upward faces. Those game-like
features are most of what an artist touches, and most of what makes a world read as a world when
there is no path tracer to make it correct.

So the core sorts its features into three kinds and gives each a home
([the catalogue](Docs/design/2026-09-20-game-shading-feature-catalogue.md)):

- **Physics**: the surface response. OpenPBR's domain. `core/models/`, `core/brdf/`.
- **Surface authoring**: how parameters arrive at a pixel. OpenPBR is silent here; this is
  `core/surface/` and the texture cook, and it is the bulk of the user-facing value: triplanar and
  biplanar projection, stochastic tiling, parallax with self-shadowing and depth offset, detail maps,
  height and splat blending, coverage and wetness, foliage translucency, wind, vertex-colour masks
  and AO, specular occlusion, geometric specular anti-aliasing.
- **Engine**: what one material shader cannot do alone. Probes, shadows, decals, post. Consumers of
  the core, not the core.

The legacy models are kept verbatim as selectable peers for the same reason: a model that is not
energy conserving by design is a legitimate choice when the frame budget says so, and a hack that
made a 2017 game world look right is a feature until something proves it is not. A path-tracing
baseline of the calibration scene is planned as ground truth to measure the hacks against, not as
a replacement for them.

## Pros and cons

| Pro | Con |
| --- | --- |
| One core, one set of tests, one vocabulary; a shading change is one pull request | The core is WGSL translated by naga, so the toolchain has a Rust dependency, a Windows SDK for fxc and dxc, and generated files that must be committed and kept current |
| The maths is proven numerically before a picture exists | A picture still needs a GPU and, for Maya, a licence and a GUI session; hosted CI can compile but cannot look |
| Legacy models are peers, so nothing is thrown away and every comparison has a baseline | The legacy quirks are kept on purpose, so known-wrong behaviours ship as selectable options and the docs must say which |
| Hosts are thin shells, so a new tool is a shell, not a shader | Each host has its own lessons (Maya rejects string parameters with semantics, FXC rejects a `switch` on a texture-derived value) and those lessons are part of the repo's weight |
| Forward and deferred share the core, split at the G-buffer boundary | Deferred carries less per pixel: anisotropy and the extra lobes are forward-only until the G-buffer grows a tangent channel |
| Every model added is available everywhere | Every model added grows the uber shader; the Maya shell compiled in 14 s with one legacy model and 24 s with two, and specialisation is the planned answer |
| OSL through closures gives offline renderers the same parameter model | OSL is a second implementation of the physics, not a transpile; it is checked against the core's vectors rather than generated from it |
| OpenPBR and MaterialX are open standards other people maintain | Both are moving targets; the repo pins versions and re-validates on each bump |
| Maya 2026 only, DirectX 11, so one viewport to get right | No OpenGL Maya, no older Maya, no 3ds Max host (OSL is the Max deliverable) |
| The developer track runs checks as jobs on resident DCC workers, repeatable and durable | That track needs the author's Job_Orchestrator; downstream users never do, and the repo carries a standalone path for everything |

## What it needs

- **The inputs pinned**: one OCIO config, a light-rig description, written texture conventions,
  MikkTSpace everywhere. Track E on the roadmap.
- **The proof**: the comparison framework, designed before it is built, with a calibration scene,
  procedural test data (a Macbeth chart, ramps, registered grids with orientation marks) and
  per-feature tolerances.
- **The hosts**: Maya and wgpu render today; MaterialX, Blender, OSL and modern HLSL follow in
  the roadmap's order.
- **A contributor's machine**: Python 3.11 to 3.13 with `uv`, Rust for `naga-cli`, the Windows 10
  SDK for fxc and dxc, a GPU for the GPU tests, Maya 2026 for the Maya checks. Nothing else is
  required; the orchestrator is optional ([Docs/knowledge/job-orchestrator.md](Docs/knowledge/job-orchestrator.md)).

## Status

Phase 2, the restructure, nearly closed (2026-09-27). The WGSL core under `core/` holds the
interfaces, the BRDF toolbox, sixteen light slots, the ADR-002 G-buffer encode and decode, a Lambert
model and both legacy models ported function by function, each with a NumPy twin and a GPU test.
`tools/build_shaders.py` translates it with naga into the artifacts under `hosts/` (shader-model 5
and 6 HLSL, GLSL, WGSL), validated by fxc and dxc on every change. Both legacy models render the
shader ball in the wgpu host, forward and deferred, and in Maya 2026 through the `dx11Shader` shell
with a Shading Model dropdown; the pictures are under `verification/`. The IBL cook produces the
prefiltered cubes, irradiance, SH9 and the BRDF LUT, with payloads under Git LFS. Next: the
standards pass, then the phase 2 close at `0.2.0`, then OpenPBR and the MaterialX carrier.

**Version:** `0.1.0-dev` ([VERSION](VERSION)). HogShade has its own versioning; "v1" and "v2" in this
repo always mean the 2015 and 2017 legacy shaders under `legacy/`, never a HogShade release. `1.0.0`
is the first release where the core renders the same material in Maya and wgpu within the
comparison framework's tolerances.

Where things stand and what is decided: [Docs/plan/BOARD.md](Docs/plan/BOARD.md) (the tracker:
owner gates, in flight, blocked, and every idea said out loud with a cost),
[Docs/ROADMAP.md](Docs/ROADMAP.md) (the tracks and phases),
[Docs/handoffs/CURRENT.md](Docs/handoffs/CURRENT.md) (where work is right now),
[Docs/design/2026-09-20-modernization-direction.md](Docs/design/2026-09-20-modernization-direction.md)
(the architecture and the decisions), and [Docs/README.md](Docs/README.md) (the map).

| Path | What |
| --- | --- |
| `core/` | The WGSL core: `interface.wgsl`, `brdf.wgsl`, `lighting.wgsl`, `gbuffer.wgsl`, `models.wgsl`, `models/{lambert,legacy_v1,legacy_v2}.wgsl`; `manifest.toml` orders the modules and names the prefix rule |
| `hogshade/` | Python: the NumPy reference twins (`reference/`), the wgpu host, the IBL cook, the jobs |
| `hosts/` | Per-host shells over the generated core: `maya_dx11/hogshade.fx`, `wgpu/`, `hlsl/`, `maya_ogsfx/`; `generated/` folders are build output, committed and checked |
| `legacy/v1.0/` | 2015 shader: one Disney principled BRDF (the Cook-Torrance and "game" includes in the tree were never compiled by the effect), one bound light. Entry: `mayaVP2_pbrBRDF.fx` |
| `legacy/v2.0/` | 2017 shader: IBL from pre-convolved cubes, parallax occlusion mapping with self-shadowing, tone mapping, depth-peeling transparency, a 33-mode debug view. Entry: `V2_uv0bn-pbs_IBLenv.fx` (the July 2017 rewrite; `uv0bn-pbs_IBLenv.fx` is the earlier variant; both compile) |
| `content/` | The shader ball (derkreature's OBJ, Unlicense) and the cooked IBL sets; large payloads under LFS |
| `tools/` | Scripts per host: the shader build, the cook, the Maya checks, the wgpu viewport, the orchestrator profile; `tools/README.md` |
| `tests/` | Compile tests, core GPU tests against the twins, host tests, cook and job tests, the docs checker |
| `verification/` | One directory per capture: `<host>[-<version>]/<check>/<variant>/<role>.<ext>` |
| `Docs/` | Roadmap, board, design, specs, plans, standards, journal, knowledge, handoff; [Docs/README.md](Docs/README.md) |

## Getting started

### The HogShade shell in Maya 2026

Tested with Maya 2026 on Windows; the only supported version. Viewport 2.0 must be on DirectX 11
(Preferences > Display > Viewport 2.0 > Rendering engine) and the `dx11Shader` plug-in loaded.

1. Create a `DX11 Shader` node in the Hypershade and set its **Shader File** to
   `hosts/maya_dx11/hogshade.fx` from your clone. The technique list shows `Main`.
2. Assign it to a mesh with UVs, normals and tangents; a sphere is fine.
3. Pick a model in the **Shading Model** dropdown: Lambert, Legacy v1 (2015 Disney), Legacy v2 (2017).
4. Bind a scene light into `Light 0` (each of the sixteen light groups has a Light Binding menu).
5. For environment lighting, connect file nodes for `specularEnvTextureCube` and
   `diffuseEnvTextureCube` from `content/ibl/<env>/cooked/` and `brdfTextureMap` from
   `content/ibl/brdf_lut.dds` (colour space Raw), and tick `useEnvMaps`. An unbound map
   falls back to the default the shell names for it rather than sampling nothing.
6. The `g_DebugMode` slider steps through the model's debug views (v2: 33 modes; v1: 8).

The scripted version of the same check, which also captures the pictures under `verification/`,
is in [tools/README.md](tools/README.md); through the developer track it is one job on a resident
Maya worker.

### The legacy v2 shader

Set **Shader File** to `legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx` and pick `TessellationOFF`. The legacy
shader samples its maps unconditionally, so assign `baseColorMap` (sRGB), `baseNormalMap` and
`pbrMasksMap` (packed roughness, metalness, AO, cavity; the slot label names the order); with no
environment cubes, untick `useEnvMaps`. Its `DEBUG VIEW` slider has 33 modes.

### Compile without Maya

On a machine with the Windows 10 SDK:

```text
fxc /T fx_5_0 /D _MAYA_=1 /Fo out.fxo hosts\maya_dx11\hogshade.fx
uv run tools/build_shaders.py --check --require-compilers
```

Headless `mayapy` can load an effect but cannot compile it (no DirectX device).

### The wgpu host

```text
uv sync --all-extras
uv run tools/wgpu/viewport.py --model legacy-v1
```

renders the shader ball forward and deferred to `verification/wgpu/shader-ball/<env>/legacy-v1/`.

## Licence

Apache 2.0. See [LICENSE](LICENSE). Third-party code embedded in the legacy shaders, and one
provenance question still open, are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Acknowledgements

Carried forward from the 2015 README. Nothing here was invented from scratch; the implementation
draws on a lot of generously published work:

- [derkreature](https://github.com/derkreature), for [IBLBaker](https://github.com/derkreature/IBLBaker)
  (the pre-convolved environment cubes the v2 shader reads) and the
  [ShaderBall](https://github.com/derkreature/ShaderBall) used for testing
- John Hable, [filmicworlds.com](http://www.filmicworlds.com/author/john-hable/) and filmicgames.com
- Alexandre Pestana, [Disney principled BRDF implementation](http://www.alexandre-pestana.com/disney-principled-brdf-implementation/)
- [ruh.li Cook-Torrance notes](http://ruh.li/GraphicsCookTorrance.html)
- Disney, [Physically Based Shading at Disney](https://disney-animation.s3.amazonaws.com/library/s2012_pbs_disney_brdf_notes_v2.pdf)
  and the [BRDF explorer](https://github.com/wdas/brdf/blob/master/src/brdfs/disney.brdf)
- Rory Driscoll, [Physically based shading](http://www.rorydriscoll.com/2013/11/22/physically-based-shading/)
- The parallax occlusion mapping in v2 is an unabashed adaptation of
  [hamish-milne/POMUnity](https://github.com/hamish-milne/POMUnity), the GameDev.net article
  "A closer look at parallax occlusion mapping", and the d3dcoder.net notes

And everyone who contributed to those projects.
