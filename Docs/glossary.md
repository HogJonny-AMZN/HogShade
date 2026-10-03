# Glossary

**Status:** Living. Started 2026-09-27 (owner: "we should absorb and build a parallel glossary like SpriteJammer does").

Canonical vocabulary. Use these exact words in code, comments, docs, commit messages and pull
requests. Do not introduce synonyms: consistent terms are what make this corpus retrievable by an
agent and navigable by a human. If a concept needs a new word, add it here first. A retired term is
struck through and kept, with what replaced it; `tools/check_docs.py` fails on a retired term used
as if it were current.

Shared with SpriteJammer where the concept is shared (the material nouns, the process nouns), so a
reader of either repo meets the same words; SpriteJammer's own entities (Actor, Swarm Unit, Deck)
stay in its glossary.

## The core and its hosts

| Term | Meaning |
| --- | --- |
| **Core** | The shading maths, written once in WGSL under `core/`, with no bindings and no entry points; every host imports it (ADR-001, ADR-002). |
| **Module** | One file under `core/`, listed in `core/manifest.toml` in dependency order, whose every name carries the module's prefix. |
| **Model** | A shading model: one of the peers selectable at runtime (`lambert`, `legacy_v1`, `legacy_v2`, the OpenPBR model next), each implementing the five-function interface (ADR-003). Not "shader": a shader is what a host compiles. |
| **Host** | A DCC, renderer or engine that imports the core through a shell: Maya `dx11Shader`, the wgpu host, modern HLSL, Maya `ogsfx`, Blender, OSL, MaterialX. |
| **Shell** | A host's own shader file that declares resources, binds parameters and calls the core (`hosts/maya_dx11/hogshade.fx`, `hosts/wgpu/*.wgsl`). Hand-written; its material UI is generated. |
| **Generated artifact** | A file under `hosts/*/generated/` or `hosts/hlsl/hogshade_core.hlsl` that `tools/build_shaders.py` wrote from the core; committed, checked, never edited. |
| **Twin** | The NumPy reference of a core function under `hogshade/reference/`, compared with the GPU by a test under `tests/core/` (ADR-004). |
| **Kept quirk** | A legacy behaviour reproduced on purpose in a port because it is the look, listed in the module header. The opposite of a deviation. |
| **Deviation** | A place where a port differs from the legacy effect, numbered in the module header and listed in the direction doc. |
| **The two halves** | A model's material half (`<model>_inputs`, run in a forward shader or a G-buffer fill) and lighting half (`_evaluate_light`, `_evaluate_env`, run in a forward shader or a light pass), split at the G-buffer boundary (ADR-005). |
| **Debug view** | A model's named intermediate selected by a mode number (v2 has 33, v1 has 8); a first-class path, never removed. |
| **Environment samples** | `EnvironmentSamples`: the irradiance, prefiltered specular, LUT pair and dome sampled once per fragment and handed to a model as numbers, so models never touch a texture. |

## Materials

The four stacked nouns are SpriteJammer's, the owner's names, kept identical here so a material
travels between the repos under one vocabulary.

| Term | Meaning |
| --- | --- |
| **Schema** | HogShade's machine-readable definition of a material type's parameters: name, type, default, range, group, widget, semantic, colour space, overridable, tier. One versioned JSON file per material type under `hogshade/material/schema/`. The contract every host UI and every binding is generated from (ADR-009, the schema design). |
| **Material Type** | The shader-facing contract a material resolves to: `hogshade-standard` (the OpenPBR-named standard material) and the legacy types (`hogshade-legacy-v1`, `hogshade-legacy-v2`, `hogshade-lambert`); in an engine, also the pipeline flags and the G-buffer targets it maps to. Very few of them. A `*.material-type.json`. |
| **Material Prime** | An authored graph over a Material Type that defines the property surface its child Materials see, authored with MaterialX's tools as a `.mtlx`. Optional: a Material Type's defaults are the implicit Prime until an authored one exists. **The owner's word; do not say master material** (Unreal's term). |
| **Material** | A record of property values against a Prime or against another Material, carrying only the deltas: the O3DE-shaped `*.material.json` document. The record of an asset; the source of truth as a property data bag. |
| **Material Instance** | Runtime, in-memory overrides on a Material that never write back: damage, wetness, team colour, selection. An engine concern, never a file here. |
| **Document** | A `*.material.json` as a file on disk, before or after resolution; the library's `load()` returns it raw. |
| **Resolved** | A Material with its parent chain followed and every default applied: the full parameter set the library's `resolve()` returns and `bind()` consumes. |
| **Finding** | One problem `validate()` reports: the document's path, the parameter (empty for the document itself) and a message. A finding never raises; a file that cannot be used at all is a `MaterialError`. |
| **Provenance** | The optional `provenance` list of a Document: `{"source", "note"}` per origin of its constants, a publication, a URL or `"author"`, with which values it covers and how (rounded, converted, chosen). Validated for shape, never inherited; the library's index shows it (S4a). |
| **Loss** | A parameter a conversion dropped and the table's reason, returned beside the converted Document by `convert()`. |
| **Host map** | A per-host JSON file beside the schema (`hogshade/material/hosts/<host>.json`) carrying only what the schema does not know for one host: identifiers, labels, UI orders, groups. A value the schema knows is a finding in the map. The generator joins schema and map. |
| **Consulted** | A source parameter a conversion table's `when` condition reads without mapping it: it shapes the output, so it is neither a mapping nor a Loss. The coverage rule counts it as covered. |
| **Meta-check** | The check of a material-type file's own shape (`check_type_data`): every field present and typed, groups declared, the `<group>_enabled` rule, the migrations list. A hundred lines of our own, no JSON Schema dependency. |
| **Conversion table** | Per legacy type, the mapping of its parameters to the standard's and the list of what has no counterpart; `convert()` applies it. How comparison between models is done: by conversion, never by a shared type. |
| **Binding** | The material-owned values and texture slots in one host's names, produced by `bind()`; never per-frame state. For the wgpu host: the frame fields at full width, the model, the texture paths and the Unbound list. |
| **Unbound** | A parameter one host cannot carry from a type it does render, with the host map's reason; returned on a Binding. Distinct from a Loss, which a conversion between types drops. |
| **Extension block** | A namespaced `ext` block in a Material that an engine owns and validates; HogShade passes it through. |
| **Game profile** | OpenPBR restricted to what glTF 2.0 and its KHR material extensions carry, with a conversion table in the repo; outside it is forward-only. |
| **Library** (of materials) | `content/materials/`: the constants-only base set written as semantic parent baselines, then a small texture-based set (CC0 or generated through the harness). |
| ~~**Master material**~~ | **RETIRED.** Unreal's term; here it is a Material Prime. |

## Content and verification

| Term | Meaning |
| --- | --- |
| **Cook** | A tool in this repo that turns a source into a runtime-ready product with a manifest and provenance: the IBL cook (`hogshade/ibl`), the texture cook to come. Packing, compression and mips are the cook's, not the schema's. |
| **Check** | A scripted verification in a host that writes an incremental log first and its pictures second (`tools/maya/ibl_check.py`); runs standalone or as a job. |
| **Capture** | One directory under `verification/<host>[-<version>]/<check>/<variant>/`, files named by role only. The unit the comparison framework reads. |
| **Variant** | A sub-directory of a check for one configuration (`legacy-v1/studio_small_09`); never encoded into a file name. |
| **Sidecar** | The `<T_name_SUFFIX>.texture.json` beside a source texture: the fields the cook derives from the suffix and the ones only an author knows (provenance, a normal map's convention); `tools/check_content.py` holds it (`Docs/standards/content.md`). |
| **Preset** | What a texture suffix implies for the cook: colour space, mips, runtime format; a sidecar may override one with a reason. |
| **Authoring set** | The source textures of a set under `content/textures/<set>/`: one map per parameter, full precision, 2K in LFS, with `LICENSE.md` and sidecars. |
| **Runtime set** | What the cook writes under `<set>/cooked/`: packed `_ORM`, BC-compressed DDS, linear mips, with `manifest.json` and `provenance.json`; every host reads it, none converts at load. |
| **Detail map** | A derived pair from frequency separation: `_DH`, the high-pass colour blended by linear light, and `_DN`, the detail normal blended by reoriented normal mapping. |
| **Calibration scene** | The mesh, lights, environment and test textures every host renders for comparison: the shader ball, the registered grids, the Macbeth chart. Track E. |
| **Registered grid** | A procedural test texture with orientation marks so a capture proves per host that the up axis, the UV origin, the normal-map sign and the channel order are right. |
| **Comparison framework** | The designed (not yet built) capture-and-diff tooling with per-feature tolerances and a pass / needs-review / fail verdict. Track E, gate G4. |
| **Validation harness** | Track F's gate for generated content: normals re-derived from height, tileability, the registered-grid probes, colour space, cook, render. Nothing generated is content until it passes. |
| **Quality bar** | The owner's rule for generated content: slop until validated, registered and as consistent as a Megascans-grade library. |

## The developer track

| Term | Meaning |
| --- | --- |
| **Orchestrator** | Job_Orchestrator, the owner's job system with resident DCC workers; BATS is its release name. The developer track, never a dependency (ADR-007). |
| **Worker** | A resident process the orchestrator owns (`hogshade_maya_gui`, `hogshade_python`, ...). Never stopped by an agent. |
| **Job** | A MODULE-mode entry under `hogshade/jobs/` with a `MANIFEST` and a `main(parameters)`; a thin adapter over code that also runs by hand. |
| **Profile** | The generated orchestrator configuration and environment files under `tools/bats/`, committed, never hand-edited. |
| **The bridge** | The planned messaging job that carries a result to the owner's phone and a reply back as a job (the agent-loop design). |
| **Gate** (workflow) | A point in a gated workflow where a result waits for a person's word before the next job runs. Distinct from a board gate. |

## Process

| Term | Meaning |
| --- | --- |
| **Board** | `Docs/plan/BOARD.md`, the tracker: gates, Now, Next, Blocked, Icebox. |
| **Gate** (board) | A decision only the owner can make, numbered G1 upward; nothing downstream of an open one may be committed to. |
| **Icebox** | Where every idea said out loud lands with a cost, a reason and a verdict; a mentioned feature is not a work order. |
| **Two-way door** | A decision cheap to reverse, taken and recorded in the PR's Decisions table; the owner's merge is the review. |
| **One-way door** | A decision the owner makes: a new ADR, a change to a locked design, anything outward-facing. |
| **Pre-spec design** | A hand-written lock of what was discussed and decided, under `Docs/design/`; the owner says *Locked* and the spec follows. |
| **Spec**, **Plan** | One increment's deliverable and its ordered, verifiable tasks, under `Docs/superpowers/`. A task is ticked when its verification ran. |
| **Journal** | `Docs/journal/`, the append-only narrative, one file per session; a `→ BATS:` line where the orchestrator made the difference. |
| **Handoff** | `Docs/handoffs/CURRENT.md`, the living snapshot a new session reads first. |
| **Decision log** | `Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, the index of decisions made in conversation and where each is formalised. |
| **Ledger** | `Docs/standards/failure-modes.md`, how the process has failed here, as triggers. |
| **Verdict** | The one-line judgement attached to an idea when it is recorded: awesome, good with the value named, or meh with what would fix it. Verdicts order ideas; they never delete them. |
