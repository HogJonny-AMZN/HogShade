# The library of materials (S4, track F): pre-spec design

**Status:** Proposed (exploring). Drafted 2026-10-02 for the owner to lock; the questions at the end are the
decisions, each with a recommendation. Nothing is built until it is locked, then S4 gets a spec and a plan.

Date: 2026-10-02. Parent: [2026-09-27-material-schema.md](2026-09-27-material-schema.md), section 5 (locked),
and the roadmap's track F. Decision: [ADR-009](../decisions/ADR-009-hogshade-owns-the-material-schema.md).
Built so far: S1 (the types and the library), S2 (the Maya UI from the schema), S3 (the wgpu binding; three
documents under `content/materials/`). Vocabulary: [../glossary.md](../glossary.md), "Materials" (Material,
Library, Document, Resolved, Binding, Conversion table).

## The goal

A small set of materials that are the baselines an asset material is written against, so that an asset
carries only intentional deltas (O3DE's lesson, in the parent design); the schema's first real consumer
and its test data, exercising every parameter the standard type has; the getting-started kit's first
content; and, from the first texture, a library with provenance a shipped game can carry. The owner's
framing (2026-09-27): "one set of broad base materials that are constants and params only, another
smaller set texture based ... a base shading solution and library (a getting started repo for any of my
games)." The quality bar, also the owner's: generated content is slop until validated, registered and
consistent to a Megascans-grade library; the library stands above the slop by intent and accuracy.

## What already binds this design

| Decision | Where |
| --- | --- |
| Documents are O3DE-shaped deltas against a parent; the base set is written as semantic parent baselines | parent design, sections 2 and 5 (locked) |
| The standard type's names are OpenPBR's; emission in nits; `alpha_mode` default `mask` | S1 spec, the type files |
| Every document validates in CI; every export passes the glTF validator; the comparison framework renders the set in every host | parent design, section 5 |
| The texture set is CC0 or made here, never a studio tree; provenance from the first texture | roadmap track F; `content/ibl/README.md` is the precedent (source, licence, fetch date, where the master lives) |
| Generated textures enter only through the validation harness, which does not exist yet | roadmap track F; the gated-research row on the board |
| Comparison between models is by conversion, never a shared type; S1 shipped the three legacy-to-standard tables and said the reverse direction is "S2 or later, when a comparison view needs it" | parent design, question 2; S1 spec |
| The wgpu host carries the legacy types only until C3; the Maya shell renders legacy v2 and v1 | S3 spec: a standard document is refused by name |
| Texture conventions (OpenGL +Y normals, ORM packing, sRGB for base colour only, MikkTSpace) are track E's, not yet written down | roadmap track E boxes; the blind-spots design |

## The shape proposed

### 1. The base set is written against the standard type

The library's job is to be what an asset material derives from, and the asset material of this repo is the
standard (the parent design, question 4: "whatever we make for HogShade will be the base standard
Material"). Writing the base set against legacy v2 because that is what renders today would make the
library a legacy artefact on the day C3 lands. So the base set is `hogshade-standard` documents, and to
render them today the library ships the **reverse conversion table**, `hogshade-standard` to
`hogshade-legacy-v2`, under S1's coverage rule: every standard parameter mapped or dropped with a reason
(`specular_color` to nothing but a loss; `emission_luminance` in nits to v2's unitless intensity through
the placeholder scale; `alpha_mode` to the two flags through conditional constants in the other
direction; the surface opt-ins to v2's maps). Then `convert(resolve(doc), "hogshade-legacy-v2")` feeds S3's
`bind()` and the wgpu host today; the Maya shell takes a document only once a Maya-side `bind()` exists
(S3 left it to a later increment), so in S4 the set renders in wgpu, and the comparison framework later
renders it in Maya through that binding. The table is the first consumer of `convert()` in the direction the comparison needs, and
it finds the standard parameters no legacy host can show, which is itself a result for C3.

### 2. The roster: semantic parents, then named children

Two levels, both documents:

- **Parents** (`<family>/base.material.json`): one per family, the characteristic values a family shares
  and the one asset authors derive from. Proposed: `metal` (metalness 1, roughness 0.4, base colour a
  neutral conductor), `dielectric` (metalness 0, specular weight 1, IOR 1.5, roughness 0.5), `coated`
  (a dielectric with low roughness and a strong specular, the car-paint and lacquer family until the
  standard has a coat layer), `rough` (a dielectric with roughness 0.9: rubber, cloth without sheen,
  concrete), `emissive` (emission on, in nits), `cutout` (alpha_mode `mask`, the foliage and fence family),
  `translucent` deferred (no transmission in the standard's version 1).
- **Children** (`<family>/<name>.material.json`): named materials carrying only deltas against their
  parent, each under exactly one family (the directory and the parent are keyed by it). Proposed first
  roster, sixteen: `metal`: iron, steel, aluminium, gold, copper, silver, chrome, brass; `dielectric`:
  plastic_matte, plastic_glossy, ceramic; `rough`: rubber, concrete; `coated`: painted; `emissive`: panel
  (800 nits); `cutout`: leaf (no texture; the document validates the alpha path).

Each constant carries its source. Metal base colours are the linear reflectance values of the published
tables (Lagarde and de Rousiers 2014, the "Physically Based" database) rounded to two decimals; dielectric
IORs are the published indices; roughness choices are the author's and say so. The children are the
schema's test data: between them every factor-bearing parameter of the standard type is set by at least one
document, and a test asserts it. The four texture-only parameters (`geometry_normal`, `ambient_occlusion`,
`cavity`, `height`) cannot be set without a texture; their coverage is S4b's, when the texture set exists.

### 3. Provenance and a title live in the document

Documents today carry `material_type`, `material_type_version`, `parent`, `values`, `ext`. The library
needs, per document, a human title, one line of description and the provenance of its values. Two ways:
an `ext.library` block (the `ext` mechanism exists and is passed through; but `ext` is defined as an
engine's namespace that HogShade does not validate, and the library is HogShade's own), or two optional
top-level fields, `title` and `doc`, plus `provenance` (a list of `{"source", "note"}`), added to the
document format at version 1 (optional, ignored by resolution, carried into the docs reference and the
contact sheet). Recommended: the top-level fields, validated for shape by `validate()`, so the record is
HogShade's and a generator can list the library with titles.

### 4. Layout

```text
content/materials/
  README.md                          # the library's index: family, name, title, source; generated by S2's docs generator
  standard/
    metal/base.material.json         # the family's parent, in the family's directory
    metal/gold.material.json         # a child, parent "base.material.json": no `..`, S1's path rule
    dielectric/base.material.json
    dielectric/ceramic.material.json
    rough/rubber.material.json
    emissive/panel.material.json
    cutout/leaf.material.json
  legacy-v2/default.material.json    # S3's three stay as the hosts' smoke documents
  legacy-v2/metal.material.json
  legacy-v1/default.material.json
  textures/                          # S4b: the texture-based set, with a LICENSE.md per source as content/ibl has
```

A child's `parent` is `base.material.json` beside it: S1's path rule rejects every `..` component, so a
family's parent lives in the family's directory rather than under a shared `base/`. The root passed to
`load()` is `content/materials/standard/`. The index page is generated (`generate("library")`), so it
cannot drift from the files.

### 5. Proof: every document validates, the set renders, a contact sheet is the human gate

- CI: every document under `content/materials/` loads, validates raw and resolved, and, for the standard
  ones, converts to legacy v2 and binds for wgpu without error; the coverage test over the roster; the
  index page current.
- The owner's GPU: `tools/wgpu/contact_sheet.py` renders every standard document through the reverse
  table into one picture, `verification/wgpu/library/contact-sheet.png`, a grid of shader balls with
  titles, under the calibration environment. The sheet is the human gate (the pictures are read, as the
  Maya gate's were) and the first thing the comparison framework will render in the other hosts.
- Maya: the same sheet is the comparison framework's job (track E); S4 does not add a Maya job.

### 6. The texture-based set, S4b, after track E writes the conventions

Three to five materials from Poly Haven or ambientCG at 2K (the LFS budget; the 8K sources stay outside the
repo as the IBL masters do): a brick or stone, a wood, a painted metal, a ground. Each with a `LICENSE.md`
on the `content/ibl` pattern. They wait for track E's texture conventions (normal-map sign, ORM packing,
colour space) because the documents reference the channels and S1's schema already names colour spaces;
authoring them before the conventions are written would author them twice. Generated textures are not in
S4 at all; they arrive through the harness the gated-research row describes, after the harness exists.

## What this is not

- Not an asset browser, a library UI or a live link: LargeWorlds (ADR-009).
- Not textures made by a generator: that is the gated-research row, with its harness as the deliverable.
- Not the comparison framework: the contact sheet is one host's picture; the framework diffs hosts.
- Not a C3 preview: the standard documents render today only through the reverse table, which loses what
  the legacy models cannot show; the losses are listed, not hidden.

## The questions for the owner

1. **The base set's type.** Standard documents plus the reverse table (recommended: the library is what
   assets derive from, and the table is a result C3 needs anyway), or legacy v2 documents now and a
   migration later (renders without a new table; becomes a legacy artefact on the day C3 lands)?
2. **The roster.** The six families and sixteen children above, or a different cut? Anything the first
   roster must have (skin, cloth, glass) that the standard's version 1 cannot carry honestly, and which the
   roster should name as "deferred to the version that carries it" rather than fake?
3. **Values' provenance.** Published reflectance tables and IORs with the source on each document
   (recommended), or the author's eye? The recommendation makes the base set citable; the eye is faster.
4. **Title, description and provenance as top-level document fields** (recommended: the record is
   HogShade's, generators and the index read it), or an `ext.library` block (no format change; `ext` is
   defined as an engine's)?
5. **Layout.** `content/materials/standard/<family>/` with the family's parent as `base.material.json`
   inside it (recommended: S1's path rule allows no `..`), with S3's three legacy documents staying as the
   hosts' smoke documents, or one flat directory with family prefixes in the file names?
6. **The proof.** The wgpu contact sheet as the human gate (recommended; cheap, one tool, the picture the
   framework will later reproduce in Maya), or wait for the comparison framework and ship S4 with CI
   validation only?
7. **The texture set's timing.** After track E's texture conventions are written (recommended), or now
   at the risk of re-authoring? And the resolution: 2K in LFS (recommended) or 1K?
8. **The getting-started page.** With S4 (the library makes it real), or after the comparison framework
   proves the set in every host?

## Increments (each its own spec and plan once this is locked)

1. **S4a**: the document fields (title, doc, provenance), the reverse table standard to legacy v2, the base
   set (parents and children) with sources, the roster coverage test, the library index generated, the
   contact-sheet tool and its picture. About 2 d.
2. **S4b**: the texture-based set after track E's conventions, with provenance files and the cook run on
   real content. 1 to 2 d, with track E.
3. The getting-started page, when question 8 says.
