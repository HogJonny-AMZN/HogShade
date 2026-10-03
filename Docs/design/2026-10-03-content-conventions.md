# Content conventions: textures, materials, lighting and rendering, for humans and agents

**Status:** Accepted. Drafted 2026-10-03 on the owner's direction ("we should put the conventions in place as a
high priority because we are talking about making material that need textures"); the owner answered questions
1 and 2 in words and said "go" to the rest the same night, so answers 3 to 8 are the recommendations ("The
answers", below). T1 (the standard and its check) has a spec and a plan; the owner overrides any answer by
saying so, and the spec amends.

Date: 2026-10-03. Parents: [2026-09-20-wysiwyg-blindspots.md](2026-09-20-wysiwyg-blindspots.md), section 6
("texture packing, gamma and compression are unspecified"); the roadmap's track E boxes (texture conventions,
MikkTSpace, light rig, colour management); [2026-10-02-material-library.md](2026-10-02-material-library.md),
section 6 (S4b waits on these). Vocabulary: [../glossary.md](../glossary.md).

## The goal

One page a human artist and an agent both follow when they add a texture, a material, a light rig or a
capture to this repository, so that the same material looks the same in every host and a file's name and
sidecar say everything a cook needs. The owner's framing (2026-10-03): this project standardises the
conventions for *its* concerns (textures, materials, lighting, rendering), not a game's whole depot; the
depot-wide document from the owner's last prototype (`PROJECT_CONVENTIONS.md`, Prism of the Pyre, aligned
with the Allar UE5 style guide) is the reference for the *shape* of such a document, written for humans and
agents at once, with the why beside every rule.

## What already binds this design

| Decision | Where |
| --- | --- |
| A texture's colour space is the schema's: `colour_space` on every texturable parameter of the material type, never inferred from a file name; a document binds a texture to a parameter and inherits the parameter's space | S1 spec; track E's colour-management box |
| OpenGL +Y normals, ORM packing, sRGB for base colour and emissive only, linear-space mips, BC5 normals and BC7 colour; an authoring set and a runtime set with one cook tool run as a BATS job | roadmap track E, the texture-conventions box (unticked) |
| MikkTSpace is a requirement, not a convention; a mesh with another basis fails validation | roadmap track E (owner, 2026-09-26) |
| Scene-referred ACEScg captures, AgX default view, ACES first-class alternative; captures as EXR plus display PNG | roadmap track E (owner, 2026-09-26) |
| Light rig: HDR file, rotation in a stated axis convention, exposure in EV, punctual lights in one unit | roadmap track E |
| Content is CC0 or made here, never a studio tree; provenance from the first texture (`LICENSE.md` beside the source, the IBL pattern) | roadmap track F; `content/ibl/<env>/LICENSE.md` |
| Generated textures enter only through a validation harness that does not exist yet | the gated-research row |
| 2K in LFS for the texture set; the 8K masters stay outside the repo | the S4 design, answer 7 |
| Pictures: PNG, at most 1024 on a side, fixed names, plain git | `verification/README.md` (#43) |
| Cook outputs carry a deterministic `manifest.json` and a volatile `provenance.json` | `content/ibl/README.md` (E1) |

## The shape proposed

### 1. One standard, two readers

`Docs/standards/content.md`, beside `python.md` and `wgsl.md`: the rules below with the why on each, written
so an agent can follow them without the conversation and an artist can follow them without the code.
`AGENTS.md` and the docs map point at it; `.github/copilot-instructions.md` too. A rule that a tool can
check gets its check (`tools/check_content.py`, a CI step), on the pattern of `check_docs.py` and
`generate_gallery.py --check`: a texture whose name, sidecar and pixels disagree is a finding, not a
surprise in a host.

### 2. Texture naming: Unreal's pattern, this repo's suffixes

Unreal's recommended convention is the pattern `Prefix_BaseName_Descriptor_Variant`, underscores, no
spaces, with `T_` for textures; Epic's page lists the prefix and leaves the channel descriptors to the
project. The owner's prototype fixed them as `_D _N _R _M _E _A`. Recommended here, one suffix for every
texturable parameter of the standard type (the fourteen that carry a `colour_space` in the schema), so a
name says which parameter it binds and a schema addition is a table addition; the check holds the table
to the schema:

| Suffix | Parameter (standard type) | Colour space (the schema's) | Runtime format |
| --- | --- | --- | --- |
| `_BC` | `base_color` | sRGB | BC7, mips in linear |
| `_M` | `base_metalness` | raw | BC4 |
| `_SW` | `specular_weight` | raw | BC4 |
| `_SC` | `specular_color` | raw | BC7 |
| `_R` | `specular_roughness` | raw | BC4 |
| `_AX` | `specular_anisotropy` | raw | BC4 |
| `_AR` | `specular_rotation` | raw | BC4 |
| `_E` | `emission_color` | sRGB | BC7 |
| `_O` | `geometry_opacity` | raw | BC4, or the alpha of `_BC` when the sidecar packs it |
| `_N` | `geometry_normal` | raw, OpenGL +Y | BC5 (two channels, Z reconstructed) |
| `_AO` | `ambient_occlusion` | raw | BC4 |
| `_C` | `cavity` | raw | BC4 |
| `_SO` | `specular_occlusion` | raw | BC4 |
| `_H` | `height` | raw, 16-bit authoring | BC4 (8-bit) or R16 when the cook says |

`specular_ior` and `alpha_mode` have no colour space in the schema and so no suffix: an IOR map and a
mode are not textures. Three more suffixes name maps that are **not parameters**: the cook's packed
runtime form and the derived detail pair (section 5), which a document never binds directly:

| Suffix | What | Colour space | Runtime format |
| --- | --- | --- | --- |
| `_ORM` | packed: AO in R, roughness in G, metalness in B; the runtime form of `_AO`, `_R`, `_M` | raw | BC7 |
| `_DN` | detail normal, derived (section 5) | raw, OpenGL +Y | BC5 |
| `_DH` | detail high-pass colour, derived (section 5) | raw, mid-grey neutral | BC7 |

`_BC` rather than Unreal's `_D`: the schema's parameter is `base_color` and the 2015 model's word is
albedo; "diffuse" is the one word that means something else in a metal-roughness material. `_M` is
metalness only, never "mask", so a packed map is always `_ORM` and never ambiguous. The variant slot
carries `_01`, `_damaged`, `_wet`, after the suffix never before it (the owner's prototype rule). The
base name is `snake_case`, as a Poly Haven slug already is (`cobblestone_floor_04`), so a sourced set
keeps its origin's name. A name that ends in a digit is fine here (no `MakeUniqueObjectName`); the
prototype's warning about that is Unreal's, recorded as not applying.

The `T_` prefix was question 1, recommended dropped inside `content/` (a directory already says "texture");
the owner kept it ("The answers"): every texture file carries `T_`, and the check holds it.

### 3. The texture sidecar: O3DE's idea, this repo's file

O3DE keeps an `.assetinfo` beside each source texture: a preset chosen by the file's suffix (Albedo,
Normal, Roughness and so on, each fixing compression, sRGB, mip generation), overridable per texture and
per platform. Recommended here: `<name>.texture.json` beside the source, read by the cook and validated
by the check. Its fields are of two kinds. **Derived from the suffix** when absent, so a sidecar may omit
them: `preset`, `colour_space`, `mips`, `runtime`; `resolution` is read from the file. **Required of the
author**, because no suffix can know them: `provenance` (origin, URL, licence, fetch date) for every
texture, and `normal_convention` for a `_N` or `_DN` (the source's convention, `opengl+y` or `directx-y`;
the cook flips a DirectX source to the repo's OpenGL +Y and records that it did). A normal map with no
stated convention is a finding, never a guessed flip, which is exactly the silent mismatch the convention
exists to end. A sidecar the cook writes carries `"derived": true` on the fields it filled, so a reader
knows which were authored. The example, valid JSON:

```json
{
  "preset": "normal",
  "colour_space": "raw",
  "normal_convention": "directx-y",
  "source": "cobblestone_floor_04_nor_dx_2k.png",
  "resolution": 2048,
  "mips": "linear-box",
  "runtime": {"format": "bc5", "container": "dds"},
  "provenance": {"origin": "polyhaven", "url": "https://polyhaven.com/a/cobblestone_floor_04", "licence": "CC0-1.0", "fetched": "2026-10-03"}
}
```

`preset` is chosen from the suffix table (an override says why); `colour_space` must equal the schema's
for the parameter the document binds; `normal_convention` is the source's, and the cooked output is
always `opengl+y`.

Presets, one per suffix row above, are a table in the standard and a dictionary in the cook; a sidecar
that names a preset the suffix does not imply is a finding unless it carries `"override_reason"`. The
material document binds the texture by path to a parameter, and the parameter's `colour_space` in the type
schema is the colour space (S1: a document value carries `factor`, `texture`, `blend`, `strength`, nothing
else); the check resolves the document's type and parameter and asserts the schema's space and the
sidecar's agree, so a wrong colour space fails in CI rather than in a viewport.

### 4. The authoring set and the runtime set, one cook

*Amended by T1 (2026-10-03): a set a document binds lives beside that document,
`content/materials/standard/<family>/<set>/`, because S1 refuses `..` in a texture path; `content/textures/<set>/`
is for sets no document binds yet. The T1 spec's amendments say why.*

`content/textures/<set>/` (or the family's `<set>/`) holds the authoring set: one map per parameter, PNG or 16-bit TIFF, EXR for
height when it needs range, 2K, in LFS, with `LICENSE.md` on the IBL pattern and the sidecars.
`tools/cook_textures.py` (a BATS job like the IBL cook) produces the runtime set beside it under
`cooked/`: packed `_ORM`, BC-compressed DDS, mips generated in linear space, normals in the stated
convention, plus `manifest.json` (deterministic, sha256 of inputs and outputs) and `provenance.json`
(volatile). No host converts a texture at load; every host reads the cooked set, as no host convolves its
own IBL. The runtime set is reproducible from the authoring set alone, and the check says so.

### 5. Frequency separation as a cook operation, for detail mapping

The owner's technique (co3dex, *Image Frequency Separation for Texture Detail Mapping*, 2022): a Gaussian
low-pass and a high-pass that recombine exactly under a linear-light blend, done on a 3x3 tiled canvas so
both halves still tile, with the low-pass free to be downsampled to a few texels (macro colour) while the
high-pass keeps the detail. That is a cook operation, not a Photoshop recipe: `cook_textures.py
separate --radius 16` writes `<name>_macro_BC` (the low-pass, at a resolution the sidecar states) and
`<name>_DH` (the high-pass, mid-grey neutral, raw), tiling-aware by wrapping the blur, with the
reconstruction error measured and written to the manifest (the post's "difference appears black" as a
number). The shader side already has the blend: O3DE's `TextureBlend_LinearLight` is `saturate(base + 2 *
mask - 1)` in display space; HogShade's core gets the same function with the colour-space handling the
post quotes, and the standard's `_DH` row says the blend is linear light and nothing else. The owner's
note in the post ("there is a really good chance there is a more correct and error-free way ... fairly easy
to write a Python script") is this increment.

A detail normal `_DN` follows the same shape: the high-frequency normal of a set, blended by reoriented
normal mapping (the roadmap's detail-maps box), with the macro normal carrying the low frequency.

### 6. What a basic PBR set cannot show, and who authors it

Poly Haven and ambientCG sets carry base colour, normal, roughness, AO, displacement, sometimes metalness.
They prove the four texture parameters S4a could not cover and the cook end to end. They cannot show
detail mapping, parallax with self-shadow, cavity, specular colour, cutout with a real mask, or emission
with a map: nothing in the sourced set exercises them. The owner said this needs human help, and that is
the honest answer: a **showcase set**, authored or conditioned here, one map per feature, owned by the
owner with the cook's help (frequency separation makes the detail pair from any sourced colour map; a
height map makes parallax; a hand-painted mask makes the cutout). The library's `wanted` list on the
gallery is where each showcase lands, as the per-feature comparison the owner asked for on 2026-10-02.

Sources, in order of readiness:

- **Poly Haven textures** (CC0, the IBL pattern): `cobblestone_floor_04` is the post's own example and a
  ground; a brick, a wood, a painted metal after it. 2K downloads, the 8K masters outside the repo.
- **The owner's legacy test files** (`D:\Depot\Maya-PBR-BRDF-VP2\testFiles`, the owner's own work): the
  `grid_*` set is already a calibration tile set (colour, normal, height, roughness, metalness, AO,
  emissive, curvature, convexity, transmission, packed masks), which the roadmap's calibration-scene box
  names as "normal-map test tile"; `Textures/Basic` has the flat and bump normals and the 50 percent
  grey. Candidates to pull over on the standard's names, with provenance "author, 2015 to 2017"; the
  `IBLbaker` DDS files are MIT (Matt Davidson) and superseded by the E1 cook, so they stay out.
- **The showcase set**, section 6, after the cook exists.

### 7. Materials, lighting and rendering: the rules this standard collects

Not new decisions; the standard gathers what is scattered so a reader finds them in one place, each with
its source:

- **Materials**: the document format and its rules (S1); a child's parent beside it; title, doc and
  provenance per document with a note naming every set value (S4a); the family directories; a bound
  texture's sidecar agreeing with the colour space of the schema parameter it binds; MikkTSpace required of
  every mesh.
- **Lighting**: the light-rig description (HDR file, rotation axis convention, exposure in EV, punctual
  lights in one unit with the per-host conversion), the calibration environment `studio_small_09`, the
  cooked IBL as the only IBL. Owner-locked items from track E, quoted.
- **Rendering and capture**: scene-referred ACEScg EXR plus the display PNG through one view transform
  (AgX default), the picture rule, the gallery manifest, the host conventions the comparison framework
  must state (camera handedness and projection, NDC depth, UV origin, up axis and units, HDR rotation;
  the board's comparison-framework row). Where track E has not decided, the standard says "undecided,
  track E" rather than inventing.

## What this is not

- Not the comparison framework (gate G4): the standard states conventions; the framework proves hosts
  agree under them.
- Not generated textures: those enter through the gated-research harness, and the cook's validation (the
  check, the reconstruction error, the sidecar agreement) is the first piece of that harness.
- Not a depot layout for a game: the prototype's document covers `Source/` versus `Content/`, levels,
  Perforce; this repo has `content/` and git LFS, and says so in one paragraph.

## The questions for the owner

1. **The `T_` prefix.** Drop it inside `content/` and let exporters add it per target (recommended), or
   keep Unreal's prefix on every file so a name is portable by copy?
2. **The colour suffix.** `_BC` for base colour (recommended: the schema's word, unambiguous beside
   metalness), or Unreal's `_D`?
3. **Packing.** `_ORM` (AO, roughness, metalness; the roadmap's word and glTF's `metallicRoughness` order
   extended) as the one runtime packing (recommended), or also an `_MRA`/`_RMA` variant for a target?
4. **The sidecar.** `<name>.texture.json` written by the cook from the suffix and committed (recommended:
   the document and the sidecar are both JSON the library reads), or sidecars generated only, never
   committed?
5. **Frequency separation in the cook.** Build it in the first cook increment (recommended: it is the
   owner's technique, it makes the detail showcase from any sourced map, and the reconstruction error is a
   number the manifest carries), or after the plain cook lands?
6. **The legacy grid set.** Pull the `grid_*` tile set over on the standard's names as the calibration tile
   (recommended; it is the owner's own, already covers most channels), or source a fresh tile?
7. **The showcase set's authorship.** The owner authors the maps a sourced set cannot provide (detail,
   cutout mask, cavity) with the cook conditioning them (recommended, per the owner's "may need my human
   help"), or the agent conditions everything from sourced maps and the owner reviews?
8. **Where the human-and-agent instructions live.** One `Docs/standards/content.md` with the why on every
   rule, pointed at by `AGENTS.md` (recommended: one file both readers load), or split into a human page
   and an agent page?

## The answers (2026-10-03)

1. **The `T_` prefix stays.** Owner: "yes T_ for texture files." The recommendation to drop it inside
   `content/` is overridden: every texture file is `T_<name>_<suffix>[_<variant>]`, portable by copy, and
   the check holds the prefix as well as the suffix. The exporter argument stands only as the reason a
   target's prefix never needs translating.
2. **`_BC` for base colour.** Owner: "we are ditching _D (diffuse), _BC is better."
3. **`_ORM` is the one runtime packing** (the owner's "go"; the recommendation). A target that wants another
   order gets it from the cook as an export, never as a second authoring convention.
4. **The sidecar is committed**, `<name>.texture.json` beside the source, read by the cook and the check.
5. **Frequency separation is in the first cook increment** (T2).
6. **The legacy `grid_*` tile set comes over** on the standard's names as the calibration tile, provenance
   "author", in T3.
7. **The owner authors the showcase maps** a sourced set cannot provide; the cook conditions them (T4).
8. **One standard, `Docs/standards/content.md`**, for both readers, pointed at by `AGENTS.md`.

## Increments (each its own spec and plan once this is locked)

1. **T1, the standard and its check**: `Docs/standards/content.md`, the suffix and preset tables, the
   sidecar schema, `tools/check_content.py` in CI, the glossary rows. Half a day; unblocks S4b.
2. **T2, the texture cook**: `tools/cook_textures.py` as a BATS job on the IBL cook's pattern, with
   frequency separation (question 5), the manifest and provenance, the sidecar written from the suffix.
   One to two days.
3. **T3, the first texture set** (this is S4b): three to five Poly Haven sets and the legacy grid tile at 2K
   in LFS, cooked, bound by standard documents, the four texture parameters covered, the contact sheet
   extended. One to two days, plus the host side (a Maya bind or the wgpu texture bind group) to see them.
4. **T4, the showcase set**: one map per feature the uber material carries, authored with the owner,
   each a gallery row. Owner-paced.
