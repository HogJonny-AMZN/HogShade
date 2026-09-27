# The material schema: pre-spec design

**Status:** Accepted. **Locked by the owner on 2026-09-27**, every question answered (the table at the end
keeps the owner's words); one spec and one plan per increment follow (`../standards/workflow.md`),
S1 first. Unblocked by [ADR-009](../decisions/ADR-009-hogshade-owns-the-material-schema.md).
**Read with:** [2026-09-20-modernization-direction.md](2026-09-20-modernization-direction.md) (decisions:
parameter model, interchange, game profile, material UI, alpha),
[2026-09-20-wysiwyg-blindspots.md](2026-09-20-wysiwyg-blindspots.md) (3, 5, 6, 9),
[2026-09-20-game-shading-feature-catalogue.md](2026-09-20-game-shading-feature-catalogue.md) (physics
table, texture data, workflow touch points), the roadmap's C3 and track F, SpriteJammer's
`docs/design/materials.md` (the consumer's vocabulary and the owner's decisions of 2026-09-13).

## The goal

**One machine-readable definition of what a material is, from which every host's UI, every export
and every binding is generated, and against which every material document, including the library, is
validated.** A parameter defined once cannot drift between Maya, Blender, the engine and the docs,
which is the third of WYSIWYG the shared core does not cover.

Owner, 2026-09-27: "let's not build the material editor here, but let's own the core generalized
material schema / data." Owner, 2026-09-13, in SpriteJammer: "OpenPBR's names as the group and O3DE's
shape under it"; "one standard OpenPBR-like material for everything, where features like triplanar
are opt-ins"; versioning from the first file.

## What already binds this design

| Decided | Where |
| --- | --- |
| HogShade owns the schema, the document, the mapping and a Python library; no editor here; dependency one way; namespaced extension blocks | ADR-009 |
| OpenPBR parameter names, deviations documented | direction doc, "Parameter model" |
| A MaterialX `.mtlx` document is where a Material Prime is authored and is the interchange (OpenPBR is defined in MaterialX); the record of an asset is the JSON document (question 10, locked) | direction doc, "Interchange", as amended 2026-09-27; blind spot 4 |
| Game profile = OpenPBR restricted to what glTF 2.0 and its KHR extensions carry, with a conversion table; outside glTF is forward-only | direction doc, "Game profile"; blind spot 3 |
| Every host's material UI is generated from the schema, never hand-edited; a test asserts it | direction doc, "Material UI"; blind spot 5 |
| One alpha-mode enum, glTF's OPAQUE, MASK, BLEND; MASK the game default | direction doc, "Alpha"; blind spot 9 |
| Colour space declared per texture, never inferred from a file name; the packed runtime set and the authoring set; MikkTSpace required | catalogue, "Texture data"; blind spot 6; roadmap track E |
| OpenPBR names as the group, O3DE's shape under it (`specular_roughness: {factor, texture, ...}`); stacked parent/child materials; versioning with migrations from the first file; the schema is core, Material Types stay per engine | SpriteJammer `materials.md`, decided 2026-09-13 |
| Legacy models are peers selectable at runtime | direction doc, "Legacy models" |

## The layers

Five things, each a file or a package, each owning one concern.

### 1. The schema: a versioned definition of the standard material

One JSON file, `hogshade/material/schema/hogshade-standard.material-type.json` as package data (question 7;
the file name is question 1),
versioned, listing every parameter of HogShade's standard material. The parameter names are
OpenPBR's; each parameter carries:

| Field | Meaning | Example |
| --- | --- | --- |
| `type` | `float`, `color3`, `vector3`, `bool`, `enum`, `texture`, `int` | `float` |
| `default` | the value when unset | `0.5` |
| `range` | `[min, max]` for numbers; `soft` when a UI may exceed it | `[0, 1]` |
| `group` | the UI group, one of a fixed list (`base`, `specular`, `coat`, `fuzz`, `emission`, `geometry`, `surface`, `legacy_v1`, `legacy_v2`, `debug`) | `specular` |
| `widget` | `slider`, `color`, `toggle`, `dropdown`, `texture`, `vector` | `slider` |
| `semantic` | what the value means to a host: `roughness_perceptual`, `ior`, `normal_ts`, `emission_luminance_nits` (OpenPBR's native unit, converted per host in the binding; question 5), ... | `roughness_perceptual` |
| `colour_space` | textures only: `srgb` or `raw`; declared, never inferred. Packing, compression and mip policy are not schema: they are the cook's and the runtime loader's (question 3) | `raw` |
| `overridable` | may a child document or a runtime instance override it | `true` |
| `tier` | the lowest SpriteJammer tier that carries it, or `forward` for what the G-buffer cannot store | `2` |
| `hosts` | per-host notes where a host maps it differently, or `unsupported` with the reason | `osl: closure param` |
| `doc` | one sentence for the generated docs table | |

Opt-in features (triplanar, parallax, detail maps, layering, the legacy models' own lobes) are
groups whose parameters carry an `enabled` toggle; a group off contributes nothing and a generator
may hide it. A flag in the schema declares a feature; what it selects is the adapter's business: an
engine's Material Type maps it to a pipeline variant (O3DE's functors, SpriteJammer's `depth_offset`
and `triplanar` flags), and on the shader side ADR-006's `override` constants are the same idea. The
schema stays renderer-agnostic at the content boundary; the mapping to bind groups, variants and
uniform layouts is each backend's adapter. The legacy models are separate material types (`hogshade-legacy-v1`, `hogshade-legacy-v2`,
`hogshade-lambert`), each its own schema file with its own parameters, sharing the document format,
the library and the generators (question 2, the owner's choice). Comparison between models is by
conversion, not by a shared type: a conversion table per legacy type maps its parameters to the
standard's (base colour, roughness, metalness, specular amount, IOR, the maps) and says what has no
counterpart (v1's Disney lobes, v2's cavity), and `convert(doc, to_type)` applies it, so a comparison
view takes one document and derives the others, lossy where the table says so. The Maya shell's
`shadingModel` dropdown then selects which type's binding the shell reads.

The schema's version is HogShade's semantic version of the schema, not of the repo. The mechanism is
in the first file: a document names the version it was written against, the library refuses one
newer than it knows and migrates one older through a migration list (O3DE's `versionUpdates` shape).
The list is empty at version 1 and nothing is brought forward from before this repo (question 6);
the first migration is written when version 2 is.

### 2. The document: a material, O3DE-shaped

A material is a JSON document that names the schema and version, optionally a parent, and only the
values that differ:

```json
{
  "material_type": "hogshade-standard",
  "material_type_version": 1,
  "parent": "library/base/steel.material.json",
  "values": {
    "base_color": {"factor": [0.18, 0.21, 0.24], "texture": "steel_basecolor.png", "blend": "multiply"},
    "specular_roughness": {"factor": 0.32},
    "geometry_normal": {"texture": "steel_normal.png", "strength": 1.0}
  },
  "ext": {
    "spritejammer": {"layer": "props", "tier_cap": 2}
  }
}
```

The value shape is the owner's O3DE-derived spelling, `{factor, texture, blend}`: `factor` alone is a
constant, `texture` alone samples, both together combine as `blend` says (`multiply` the default,
`lerp` and `overlay` where the schema allows it). Importers (glTF, FBX, a `.mtlx` surface) produce
documents; a runtime never reads an imported scene's material data, and never reads source: it reads
what a cook produced from the resolved document (O3DE's lesson, SpriteJammer's Cook).

Rules: a value key is a schema parameter or the document fails validation; a parent chain resolves
to exactly one schema version; `ext` blocks are namespaced and passed through unvalidated by
HogShade (an engine validates its own); texture and `parent` paths are relative to the document, normalised on load, and rejected when
absolute or when they resolve outside the document's package root (the same rule as the Maya
check's output directory, `../standards/failure-modes.md` entry 9); nothing is inferred from a file
name.

### 3. The exports: MaterialX and the glTF game profile

- **MaterialX.** A resolved document exports to a `.mtlx` with an `open_pbr_surface` node whose
  inputs are the resolved values and image nodes with the declared colour spaces. This is the
  interchange (Maya LookdevX, USD, Blender via USD) and the source the generated OSL and GLSL
  cross-checks come from. Import is the reverse for the OpenPBR subset; a graph the schema cannot
  express imports as a Prime reference, not as values (SpriteJammer's vocabulary).
  **Source of truth (question 10).** The direction doc's "Interchange" decision (2026-09-20) says the
  authored material is the `.mtlx` document. The owner's later decisions (2026-09-13 in SpriteJammer,
  ADR-009 here) make the O3DE-shaped JSON the authored record and MaterialX the authoring format of a
  Prime and the interchange, not the record and not the runtime. The owner locked this on 2026-09-27: MaterialX authors the base material or a derivative (the Prime);
  the JSON document is the record of an asset; an instance is the engine's in-memory overrides and never a
  file. The direction doc's row is amended accordingly. The other nine questions stay open.
- **The dependency.** Measured 2026-09-27: Maya 2026's own Python (3.11.9) has no `MaterialX` module;
  Blender 5.2's Python (3.13) ships MaterialX 1.39.4. So `hogshade.material`'s core (load, validate,
  resolve, convert, bind, the glTF export) never imports MaterialX; export and import of `.mtlx` live
  behind the optional extra `hogshade[materialx]`, which Blender satisfies natively and Maya gets from
  the wheel installed into its site-packages (question 9).
- **glTF.** The game profile: a conversion table in the repo says which parameter becomes which
  glTF core or KHR extension field (`specular`, `ior`, `clearcoat`, `sheen`, `iridescence`,
  `transmission`, `emissive_strength`, `texture_transform`) and what is lost; the exporter emits
  it and the Khronos validator runs in CI on the library's exports. `alpha_mode` maps one to one.

### 4. The Python library: `hogshade.material`

Importable inside Maya and Blender: no PySide6, no engine imports, numpy allowed. Functions, not a
framework:

| Function | Does |
| --- | --- |
| `load(path) -> Document` | parse and migrate to the current schema version; the result is raw: its `parent` is a normalised path, not yet followed |
| `validate(doc_or_resolved) -> list[Finding]` | a raw document: unknown keys, types, ranges, colour spaces, path rules; a resolved one: completeness and cross-parameter rules as well |
| `convert(doc, to_type) -> Document` | a document of one type as a document of another through that pair's conversion table, lossy where the table says so; how the comparison views derive a legacy material from a standard one |
| `resolve(doc) -> Resolved` | the one place the parent chain is followed (each parent through `load`, cycles and escapes rejected): the full parameter set with defaults applied and `ext` blocks merged child over parent |
| `bind(resolved, host) -> Binding` | the material-owned values and texture slots in that host's names, and nothing per-frame: for Maya the material parameters and map slots; for the wgpu host the material fields the frame carries today (`base_color`, `material`, `model`, `params_a`, `params_b`) and the texture slots, which the host merges into its own per-frame block (view, camera, lights, environment stay the host's); for Blender a node input map. A host that grows a separate material uniform block binds that block whole |
| `export_mtlx(resolved, path)`, `export_gltf_material(resolved) -> dict` | the two exports |
| `generate(host) -> str` | the host's UI from the schema: the Maya annotations block, the Blender panel source, the docs table |

The generators are the WYSIWYG lever: `tests/` asserts that the material block of
`hosts/maya_dx11/hogshade.fx` equals `generate("maya_dx11")`, so a hand edit to the shell's UI fails
CI. The wgpu host's `Scene` and `host_Frame` are checked the same way against the binding.

### 5. The library of materials (track F)

Documents against the schema, in `content/materials/`: the constants-only base set first, written
as the semantic parent baselines a library is built on (metal, painted metal, dielectric, skin,
foliage, emissive, with characteristic roughness and tint choices), so an asset material carries
only intentional deltas against one of them (O3DE's lesson); then a small texture-based set with CC0
textures only. Generated textures enter the library through track F's validation harness and
nowhere else, and not before it exists (the quality bar: generated output is research input until
validated, registered and consistent to a Megascans-grade library). Every document validates in CI; every export passes the glTF validator;
the comparison framework renders the set in every host. The base set is the schema's test data and
the getting-started kit's first content.

## What this is not

- Not an editor, a node graph, an asset browser or a live link: LargeWorlds (ADR-009).
- Not runtime Material Instances: an engine concern over the resolved document.
- Not Substrate-style layering: a G-buffer change when it comes (SpriteJammer's call).
- Not a second parameter vocabulary: the shell's legacy v2 parameter names survive only as the
  Maya binding's names, generated from the schema.

## The questions, answered and locked (2026-09-27)

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | File names and extensions | **Locked:** `*.material-type.json` and `*.material.json`. Owner: "is good" |
| 2 | Legacy models as opt-in groups of one schema, or separate material types | **Locked: separate types.** Owner: "separate and legacy (but then what's the best route to compare???)" The route is conversion, not sharing: one document format, a conversion table per legacy type, `convert()` in the library; a comparison view derives the legacy documents from the standard one, lossy where the table says |
| 3 | Where texture packing lives | **Locked: not in the schema.** Owner: "texture packing feels like a cook and runtime loader question, not base material authoring; they are optimizations." The schema keeps colour space and semantic per texture; packing, compression and mips are the cook's profile and the loader's |
| 4 | Is HogShade's standard material SpriteJammer's `standard` Material Type | **Locked: yes.** Owner: "whatever we make for HogShade will be the base standard Material; if SpriteJammer decides on an optimized version or derivative, that's its choice as a downstream project" |
| 5 | Emission units | **Locked: OpenPBR's native, `emission_luminance` in nits, converted per host in the binding.** Owner: "pick the most flexible native; use your best recommendation" |
| 6 | Migration mechanics | **Locked: the mechanism from the first file, an empty list at version 1.** Owner: "we don't need to support bringing anything forward; this is a new repo, a new standard, and nothing uses it yet" |
| 8 | Specular occlusion's home | **Locked: in the core schema's `surface` group as an opt-in; storage is the engine's.** Owner: "it's not a physically based standard, it's a game and realtime rendering optimization and/or taste choice on what looks better" |
| 9 | The MaterialX wheel as a dependency | **Locked: an optional extra.** Measured: Maya 2026's Python has no MaterialX; Blender 5.2's ships 1.39.4. Owner: "Maya has its own MaterialX I believe" (LookdevX does; its Python does not expose it) |
| 10 | Source of truth: the O3DE-shaped JSON document as the authored record with `.mtlx` as the Prime's authoring format and the interchange, or the `.mtlx` as the authored material | **Locked by the owner, 2026-09-27:** the JSON record; MaterialX authors a base material or a derivative (a Prime) and is the interchange. The owner's restatement, three truths at three layers: "a .mtlx base material is the source of truth for how to shade; our O3DE-like material types are the source of truth for the HogShade material schema contract; and a material is the source of truth as a property data bag, or a layered override of a parent's." The direction doc's "Interchange" row is amended |
| 7 | Where the schema file lives | **Locked: package data under `hogshade/material/schema/`.** Owner: "best recommendation according to project standards and patterns" |

## Cross-repo: who consumes what

| Repo | Owns | Takes from here |
| --- | --- | --- |
| HogShade | the schema, the document format, the exports, `hogshade.material`, the library of materials, the WGSL core | |
| SpriteJammer | its Material Types (the `standard` type is this schema plus `ext.spritejammer`), the Cook that flattens a parent chain into a uniform block and texture-array layers, its deferred renderer, the vocabulary (Type, Prime, Material, Instance) | the schema and the library, through LargeWorlds or directly; its own ADR says which |
| LargeWorlds | the material editor, engine-side assets and Material Instances; nothing built yet | `hogshade.material` as a package and the core WGSL vendored. How it consumes a package is LargeWorlds' gate G1 (vendor, live dependency or publish), the same question SpriteJammer holds as its ADR-027 |

The cook shape SpriteJammer's research settled (flatten the chain, textures to array layers, one
uniform block laid out against a numpy dtype with a test that the WGSL struct agrees) is what
`bind()` produces for that host; a dtype and struct mismatch is silent, so the layout test is part of
the binding, as it already is for the wgpu host's `host_Frame`.

## Increments (each its own spec and plan; S1 next)

1. **S1, the schema files and the library's load, validate, resolve and convert** with tests; version 1
   of the standard schema (the OpenPBR base and specular parameters the C3 model will need, the
   surface opt-ins that exist today) and the three legacy types with their conversion tables. About
   2 d.
2. **S2, the Maya generator** and the CI test that `hogshade.fx`'s material block is generated. 1 d.
3. **S3, the wgpu binding** from a document, replacing `Scene`'s hand-set fields; the base library's
   first documents render through it. 1 d.
4. **S4, the base library** (track F), validated and rendered in both hosts. 1 d.
5. **S5, the MaterialX export** and import of the OpenPBR subset. 1 to 2 d, with C3.
6. **S6, the glTF game profile** with the conversion table and the validator in CI. 1 d.

S1 to S4 need nothing from G4; S5 and S6 land with C3.
