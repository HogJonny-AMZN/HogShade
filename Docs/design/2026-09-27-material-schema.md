# The material schema: pre-spec design

**Status:** Proposed. **Exploring**, drafted 2026-09-27 for the owner to react to and lock; nothing here is
scheduled until the owner says *Locked*, and then one spec and one plan per increment follow
(`../standards/workflow.md`). Unblocked by [ADR-009](../decisions/ADR-009-hogshade-owns-the-material-schema.md).
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
| The authored interchange is a MaterialX `.mtlx` document (OpenPBR is defined in MaterialX) | direction doc, "Interchange"; blind spot 4 |
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
| `semantic` | what the value means to a host: `roughness_perceptual`, `ior`, `normal_ts`, `emission_luminance_nits`, ... | `roughness_perceptual` |
| `colour_space` | textures only: `srgb` or `raw`; declared, never inferred | `raw` |
| `channels` | textures only: which channels carry it and the packing family (`orm`, `bc5_normal`) | `g` of `orm` |
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
uniform layouts is each backend's adapter. The model selector is a parameter (`shading_model`, enum: `openpbr`, `legacy_v2`,
`legacy_v1`, `lambert`), so the legacy models are opt-in groups of the one schema rather than
separate types (question 2).

The schema's version is HogShade's semantic version of the schema, not of the repo; a migration
list (O3DE's `versionUpdates` shape) says how a document at version N becomes N+1, and the library
applies it on load.

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

## Open questions for the owner

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | File names and extensions: `*.material-type.json` and `*.material.json`, or a HogShade-specific suffix | The generic pair; the `material_type` field carries the identity, not the extension |
| 2 | Legacy models as opt-in groups of one schema, or separate material types | One schema with `shading_model` and legacy groups: one document format, one generator, and comparison views switch models without changing files |
| 3 | Where texture packing lives: per texture in the schema (`channels`), or a cook profile the schema references | Both: the schema declares the packing family per texture; the cook profile is the engine's `ext` block |
| 4 | Is HogShade's standard material SpriteJammer's `standard` Material Type | Yes: a SpriteJammer Material Type is this schema plus its `ext.spritejammer` block; a second engine adds its own block, never a second schema |
| 5 | Emission units | OpenPBR's `emission_luminance` in nits, converted per host in the binding, so the light-rig units (track E) and emission agree |
| 6 | Migration mechanics | A list of `{from, to, ops}` in the schema, applied on load; the first schema version is 1 and the first migration is written when the second version is |
| 8 | Specular occlusion: in the core schema's `surface` group as an opt-in (HogShade's catalogue, C4), or only in an engine's `ext` block (SpriteJammer's decision makes it a Material Type property stored in GB2's spare byte) | Both are true at different layers: the parameter is a shader feature every host evaluates and belongs in `surface`; where an engine stores it (a G-buffer byte) is that engine's `ext` block and its own ADR. The schema names the parameter; the engine names the storage |
| 9 | The MaterialX Python wheel (5.5 MB of C++ that Maya's and Blender's Pythons may not carry) as a dependency of `hogshade.material` | An optional extra (`hogshade[materialx]`) behind an ADR at S5; load, validate, resolve, bind and the glTF export never import it, so the library stays importable in every DCC |
| 10 | Source of truth: the O3DE-shaped JSON document as the authored record with `.mtlx` as the Prime's authoring format and the interchange, or the `.mtlx` as the authored material | **Locked by the owner, 2026-09-27:** the JSON record; MaterialX authors a base material or a derivative (a Prime) and is the interchange. The direction doc's "Interchange" row is amended |
| 7 | Where the schema file lives: `schema/` at the root, or under `hogshade/` as package data | `hogshade/material/schema/` as package data, so a pip install of the library carries it |

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

## Increments, proposed (each its own spec and plan after the lock)

1. **S1, the schema and the library's load, validate, resolve** with tests; the first version of
   the schema covering what the core ships today (Lambert, v1, v2 parameters as opt-in groups, the
   OpenPBR base and specular parameters the C3 model will need). About 2 d.
2. **S2, the Maya generator** and the CI test that `hogshade.fx`'s material block is generated. 1 d.
3. **S3, the wgpu binding** from a document, replacing `Scene`'s hand-set fields; the base library's
   first documents render through it. 1 d.
4. **S4, the base library** (track F), validated and rendered in both hosts. 1 d.
5. **S5, the MaterialX export** and import of the OpenPBR subset. 1 to 2 d, with C3.
6. **S6, the glTF game profile** with the conversion table and the validator in CI. 1 d.

S1 to S4 need nothing from G4; S5 and S6 land with C3.
