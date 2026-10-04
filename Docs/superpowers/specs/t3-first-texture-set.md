# T3 spec: the first texture set, and the host that shows it

**Status:** Accepted. Drafted 2026-10-04 from the accepted conventions design (increment 3, "T3, the first texture
set (this is S4b)"), the material-library design (section 6), the content standard and the T2 cook, merged as #57;
the three questions answered by the owner the same day with the recommendations ("your best recommendations are
fine for now"): Maya first with wgpu sampling as T3b, the four named sets plus the grid tile, concavity as `_C` and
the rest of the grid's unmapped maps left in the legacy repository. Built on `feat/t3-first-texture-set`; amendments
made in the build go in a last section.

Date: 2026-10-04. Design: [../../design/2026-10-03-content-conventions.md](../../design/2026-10-03-content-conventions.md)
(increment 3) and [../../design/2026-10-02-material-library.md](../../design/2026-10-02-material-library.md)
(section 6, answer 7). Standard: [../../standards/content.md](../../standards/content.md) ("The authoring set
and the runtime set", "Sources and licences"). The cook: [t2-texture-cook.md](t2-texture-cook.md). The library:
[s4a-material-library.md](s4a-material-library.md) (the reverse table standard to legacy v2, the contact sheet).
The hosts: [s2-material-generators.md](s2-material-generators.md) (the Maya shell's material half is generated
from the schema and the host map), [s3-wgpu-binding.md](s3-wgpu-binding.md) (a `Binding` carries texture
paths; the wgpu host binds none). Plan: [../plans/t3-first-texture-set.md](../plans/t3-first-texture-set.md).
Vocabulary: [../../glossary.md](../../glossary.md) (Authoring set, Runtime set, Calibration scene).

## Deliverable

The repository's first texture content, committed and seen: four Poly Haven sets and the owner's legacy grid
tile as authoring sets under the content standard, cooked by T2 into their runtime sets, bound by standard
documents in the library, every one of the cook's output kinds exercised on real content (`_BC` colour, `_N`
as BC5, `_ORM` packed, `_H` at its precision, `_E`), and one host rendering them: the Maya shell reads the
runtime set through two small changes to its material half, and a Maya job renders each set on the shader ball
into `verification/maya-2026/textures/<set>/` for the gallery. After T3 a material document with textures is a
first-class thing in HogShade, and a newcomer following the README cooks a committed set.

## What lands

### 1. The sets

| Set | Where | Why this one | Maps |
| --- | --- | --- | --- |
| `cobblestone_floor_04` (Poly Haven, CC0) | `content/materials/standard/rough/cobblestone_floor_04/` | T2's proof set, already cooked outside the repository; a ground with height | `_BC`, `_N`, `_R`, `_AO`, `_H` |
| `brick_wall_001` (Poly Haven, CC0) | `content/materials/standard/rough/brick_wall_001/` | the design's "brick or stone"; a wall with strong height for the detail maps | `_BC`, `_N`, `_R`, `_AO`, `_H` |
| `brown_planks_03` (Poly Haven, CC0) | `content/materials/standard/dielectric/brown_planks_03/` | the design's "wood"; anisotropic grain the standard cannot yet express, so a plain dielectric | `_BC`, `_N`, `_R`, `_AO` |
| `blue_metal_plate` (Poly Haven, CC0) | `content/materials/standard/coated/blue_metal_plate/` | the design's "painted metal"; the one set with a metalness map, so `_ORM` has all three channels | `_BC`, `_N`, `_R`, `_M`, `_AO` |
| `grid` (the owner's legacy test tiles, provenance `author`) | `content/textures/grid/` | the calibration tile (board Icebox row, owner 2026-10-03); no document binds it, so `content/textures/` | `_BC`, `_BC_blue`, `_N`, `_H`, `_R`, `_M`, `_AO`, `_E`, `_C` |

The design said "a ground" as the fourth sourced set; `cobblestone_floor_04` is that ground and is already
proven, so the four are brick, wood, painted metal, ground. The exact Poly Haven ids are the recommendation
(question 2); any CC0 set of the same kind serves, and the build names the one fetched in each `LICENSE.md`.

**Resolution and precision.** Each sourced set is fetched at 2K as PNG (the LFS budget; Poly Haven serves 2K
directly, no master is downsampled here, unlike the IBL cook): `_BC`, `_R`, `_AO`, `_M` and `_N` at 8 bits
(the content table's bit depth for each; a normal is BC5 at runtime, 8 bits a channel), `_H` at 16 bits (the
table's depth for height; the cook keeps it as `R16_UNORM`). A set is then 15 to 25 MB of
authoring PNGs and 10 to 15 MB of cooked DDS; the five sets together stay under 200 MB in LFS. The grid tile is
1K as authored (1024 on a side, 2015 to 2017); it is not upscaled.

**The grid tile's mapping** from the legacy names to the standard's suffixes, with the deliberate omissions:

| Legacy file | Standard name | Note |
| --- | --- | --- |
| `grid_color.png` | `T_grid_BC.png` | sRGB |
| `grid_blue_color.png` | `T_grid_BC_blue.png` | the blue variant of the colour, on the grammar's `_<variant>` |
| `grid_normal.png` | `T_grid_N.png` | `normal_convention: opengl+y` (the legacy shell's label: "tangent, +Y up") |
| `grid_height.png` | `T_grid_H.png` | 8-bit RGB in the source; the cook takes R and logs it; `R8_UNORM`, BC4 with the encoder |
| `grid_roughness.png`, `grid_metalness.png` | `T_grid_R.png`, `T_grid_M.png` | 8-bit grey |
| `grid_ambOcc.png` | `T_grid_AO.png` | 8-bit grey; `grid_occlusion.png` (16-bit) is the same map at higher precision and is the one taken if they differ by more than one 8-bit step |
| `grid_emmissive.png` | `T_grid_E.png` | sRGB; the legacy spelling is not carried |
| `grid_concavity.png` | `T_grid_C.png` | cavity is the concave-area term; recommended (question 3) |
| `grid_curvature.png`, `grid_convexity.png`, `grid_derivative.png`, `grid_transmission.png` | not carried | no standard parameter takes them; they stay in the legacy repository until a parameter exists |
| `grid_pbrMasks.png`, `grid_v2_pbrMasks.png` | not carried | the legacy packed masks; the cook writes `_ORM` from the parts |
| `grid_color_A.png`, `grid_white_A.png`, the `.tga` alphas | not carried | the alpha-carrier case is T4's showcase (`pack`), not the calibration tile |

### 2. The documents

One standard document per sourced set beside it, named for the set: `rough/cobblestone_floor_04.material.json`,
`rough/brick_wall_001.material.json`, `dielectric/brown_planks_03.material.json`, `coated/blue_metal_plate.material.json`.
Each binds its maps as the content standard spells them (`{"texture": "<set>/T_<set>_BC.png"}`, the authoring
file; the path may not climb), carries `title`, `doc` and a `provenance` entry naming the Poly Haven page, and
inherits its family's constants for what the set does not texture (`brown_planks_03` has no metalness map and
no `_M` sidecar; `base_metalness` stays the family's 0). A textured parameter that multiplies its factor by the
sample (legacy v2's `metalness = s.metalness * m.metalness`, roughness likewise) is bound with `factor` and
`texture` together, the factor 1.0: `blue_metal_plate` writes `base_metalness: {"factor": 1.0, "texture": ...}`,
because resolution merges a child's value keys into the parent's and the coated family's 0.0 would otherwise
suppress the map everywhere. The library index (`content/materials/README.md`,
generated) gains the four rows; the roster coverage test gains the texture bindings. The design's four
texture-only parameters are `geometry_normal`, `ambient_occlusion`, `cavity` and `height`: T3 covers three of
them with committed documents (every sourced set binds a normal and an AO; the ground and the brick bind a
height) and **defers cavity** (only the grid tile has a `_C`, and no document binds the grid in T3); the
factor-bearing textured parameters (`base_color`, `specular_roughness`, `base_metalness`) are covered as well,
and the test lists each separately so the deferral is visible.

The grid tile binds to no document in T3 (the calibration scene is track E, after G5); it is cooked and
checked like the others, and the Maya job renders it too, so the tile is seen.

### 3. From a document's texture to the runtime file: `hogshade.material.runtime`

A document names the authoring PNG; a host reads the cooked DDS; three authoring maps become one `_ORM`. The
resolution lives in the library, not in a host: `runtime_textures(binding, set_dir)` reads the set's
`cooked/manifest.json` and returns, per bound parameter, the DDS path and the channel: `base_color` to
`cooked/T_<set>_BC.dds` (`rgb`, alpha when the manifest says a map rides there), `geometry_normal` to
`cooked/T_<set>_N.dds` (`rg`, Z reconstructed by the host), `specular_roughness` to `cooked/T_<set>_ORM.dds`
channel `g`, `base_metalness` channel `b`, `ambient_occlusion` channel `r`, `height` to wherever the manifest
put it: `cooked/T_<set>_H.dds` channel `r` with that entry's format (`R16_UNORM`, `R8_UNORM` or `BC4_UNORM`), or
the alpha of the carrier whose `packed` record names the `_H` source (the cook writes no standalone `_H` then;
T2's brick fixture packs its height into `_ORM`'s alpha and is the test), `emission_color` to
`cooked/T_<set>_E.dds`. Every resolution comes from the manifest's `textures` entries, never from a fixed name. A set with no `cooked/manifest.json` is a `CookError`-shaped failure naming the cook
command, never a fallback to the PNG: the standard says no host converts at load. `check_content.py` gains
**content-runtime** (today the checker only restricts the file names inside `cooked/`; it reads no manifest):
every committed set under both content roots that has a `cooked/` directory (the bound sets under
`content/materials/` and the grid under `content/textures/` alike) has a `cooked/manifest.json`, the manifest's
`textures` and `packed` records account for every source map of the set (a document binding `_M` whose set
cooked no metalness is a finding; a set whose `_H` is in no entry is one), and the manifest's input hashes match
the authoring files when LFS payloads are present (logged as unverified when they are pointers, like
`content-sidecar`'s resolution). Tested on a fixture with a missing manifest, a missing map and a stale hash.

### 4. The host half: Maya reads the runtime set (question 1)

The Maya shell already samples eight maps (`hosts/maya_dx11/hogshade.fx`: `baseColorMap`, `baseNormalMap`,
`roughnessMap`, `metalnessMap`, `heightMap`, `ambOccMap`, `cavityMap`, `emissiveMap`), and the Maya checks
already connect a file node to a map attribute (`tools/maya/_session.py`, `connect_file`, used for the BRDF
LUT). Two things in the shell's material half do not match the runtime set, found by reading the shell against
the cook's output rather than assumed:

- **Metalness is read from green** (`metalnessMap.Sample(...).g`, the legacy "green channel" convention S1
  recorded for roughness and metalness alike), but `_ORM` carries metalness in blue. Roughness (`.g`) and AO
  (`.r`) match the packing by luck of the same convention. The change: the host map's `base_metalness` entry
  (through the reverse table, legacy v2's `metalness`) names the channel the shell reads, and the generated
  material half reads `.b` for a document whose metalness comes from an `_ORM`; concretely one generated sampler
  `ormMap` (`useOrmMap`) feeds roughness, metalness and AO from `.g`, `.b`, `.r`, and the three separate samplers
  stay for legacy documents that bind separate maps. The S2 generator gains a `packed` entry kind in the host
  map, so the shell change is generated, not hand-edited, and `--check` holds it.
- **The normal map is read as three channels** (`baseNormalMap.Sample(...).xyz * 2 - 1`), and `_N` is BC5, two
  channels, so `.z` reads 0. For legacy v2, the model every standard document reaches through the reverse table,
  that is already fine: `legacy_v2_normal_ts` (`core/models/legacy_v2.wgsl`) ignores the sampled Z and derives it
  as `sqrt(1 - clamp(x² + y², 0, 1))`, the clamp covering compressed X, Y that leave the disk. **No core change
  in T3**; the GPU test for that helper gains a two-channel case (Z sampled as 0) so the claim is held. Legacy v1
  decodes all three channels and would shade a BC5 normal wrong; v1 is not a target of T3 (no standard document
  converts to it) and the v1 case is recorded for T3b with the raw-debug view. (Copilot on #57 found the first
  draft's `normalMapChannels` uniform unnecessary; this replaces it.)

The one shell change is in the material half, which is the generated and hostable layer, not the BRDF; it
changes no picture for a document without textures, and the S2 pixel-identical gate (master's shell against the
regenerated shell on the untextured shader ball) holds that.

**The first task is a probe, not a build**: a Maya job connects cooked DDS files of every format the committed
sets will carry (BC7 sRGB and BC7, BC5, BC4, `R16_UNORM`, `R8_UNORM`, and their uncompressed counterparts) to the
shell's map attributes and logs what Maya decoded (`connect_file` already reports whether Maya read the file).
T2's proof set alone does not cover them (its height rides in `_ORM`'s alpha and its single channels are packed),
so the probe cooks two scratch sets outside the repository: the grid tile as fetched (8-bit `_H` and `_C` give
BC4 and `R8_UNORM`) and `cobblestone_floor_04` with no `pack` field (a standalone 16-bit `_H` gives `R16_UNORM`),
each once with the encoder and once `--no-compress`. Maya's image library has read DDS since the legacy days and the IBL cook's
`R16G16B16A16_FLOAT` cubes load today, but no block-compressed 2D DDS has been loaded in this repository yet, and
if BC7 or BC5 do not decode, the fallback is in the cook, not the host: `--no-compress` writes the same set
uncompressed (`R8G8B8A8_UNORM_SRGB`, `R8G8_UNORM`, `R8_UNORM`), the standard's table already says "or
uncompressed until", and the manifest tells the host which it got. The probe's log is the first artifact of the
build and decides which the committed `cooked/` carries for Maya, and the choice is carried explicitly: the
committed sets are cooked with `--compress` or `--no-compress` as the probe says (never the automatic default,
which would flip with the encoder's presence), `separate` takes the same flag, the acceptance gate's
byte-identical recipe and the README's commands name that flag, and the manifest's `compression` record is the
proof of which was used.

**The Maya binder, a deliverable of its own**: `bind(resolved, "maya_dx11")` does not exist (`binding.py` refuses
every host but `wgpu`, S3's scope), and the Maya host map describes legacy parameters, so a standard document
reaches Maya by conversion first: `convert(resolved, "hogshade-legacy-v2")` through the S4a reverse table (values
and textures alike; a converted texture keeps its path), then `bind(converted, "maya_dx11")` returns the shell's
attribute values (`materialBaseColor`, `materialMetalness`, ...), the `use<Map>` flags from which parameters are
textured, and the texture attributes (`baseColorMap`, `ormMap`, `baseNormalMap`, `heightMap`, `emissiveMap`) with
the runtime files from `runtime_textures`, keyed so a legacy parameter name finds its file. Tests: a textured
standard document converts and binds, the flags follow the textures, an untextured one binds to the same values
the S2 gate renders, and an unsupported parameter is `Unbound` with its reason as on wgpu.

**The job**: `hogshade.jobs.maya_texture_check` on the IBL check's pattern (the GUI Maya worker, `_session`,
`HOGSHADE_*` variables): it loads the shell, applies one document through the conversion, the Maya binder and
`runtime_textures`, connects each DDS to its attribute, sets the environment to `studio_small_09`, renders
`main.png` and the debug views (albedo, normal, roughness, metalness, AO) into
`verification/maya-2026/textures/<set>/`, and writes `check.log` with every connection and what Maya decoded.
One run per set, the grid tile included (a document for it is built in memory from the tile's maps, not
committed). The pictures are gallery rows in a new section, "The first texture set", each `made_by` the submit
command with its `set` parameter, as the IBL rows are.

**The wgpu host does not sample textures in T3.** S3 scoped texture bindings out "before the comparison
framework", and that stays: the wgpu host map's `unsupported` reasons are unchanged, the `Binding` carries the
paths, `runtime_textures` resolves them for a later wgpu increment (T3b, its own spec: DDS to `wgpu` textures
through `dds2d.read_2d`, the `texture-compression-bc` feature, a material bind group, the `lit_mesh` and
`gbuffer_fill` material halves sampling). The wgpu contact sheet keeps rendering the constants of the four new
documents (their families' values), which is honest: it shows what that host carries.

### 5. The README and the manual's first steps

`README.md` "The texture cook" names a committed set (`content/materials/standard/rough/brick_wall_001`) in its
commands, replacing the `<set_dir>` placeholder Copilot asked for on #55; a newcomer runs `cook` on real content
and gets a byte-identical `cooked/` (the manifest is committed, so `git status` proves it). `tools/README.md`
gains the Maya texture check; `tools/bats/README.md` and the knowledge file gain the job; the content standard's
"Sources and licences" names the five sets; the library index is regenerated.

## Tests

- `tests/test_check_content.py`: **content-runtime** on a fixture set with and without a manifest, with a
  document binding a map the cook did not write, a set whose height is in no entry, with hashes that match
  and that do not; the grid under `content/textures/` included; on the corpus, clean.
- `tests/material/test_binding.py`: the Maya binder (conversion first; values, flags, texture attributes,
  `Unbound` reasons; the untextured values equal to the S2 gate's).
- `tests/material/test_runtime.py`: `runtime_textures` on the brick fixture of the cook tests: every channel
  home, the `_ORM` channels, a packed alpha, the format carried for height, the error without a manifest.
- `tests/material/test_library.py`: the four documents validate, bind for both hosts, the coverage test's new
  rows (the four texture parameters bound at least once).
- `tests/core/`: `legacy_v2_normal_ts` with Z sampled as 0 (the BC5 case) against `normals.reconstruct_z`; the
  generated shell's `ormMap` block against the host map (`generate_material_ui.py --check`).
- `tests/jobs/`: the Maya texture check job is registered, its manifest lists its outputs, a climbing `set` is
  refused.
- The Maya pictures are read by a human: each set on the shader ball with its colour, normal and roughness
  legible, the metal plate's metalness visible, the grid tile's cells aligned, the height map's parallax on the
  cobblestones; stated in the PR.

## Acceptance gate

- `uv run tools/check_content.py` clean on the five committed sets; `pytest` green on both legs; CI's LFS-less
  checkout logs the pointers as unverified and passes.
- `uv run tools/cook_textures.py cook content/materials/standard/rough/brick_wall_001 --compress` (or
  `--no-compress`, as the probe decided; the flag the README names) on a fresh clone with LFS payloads writes a
  `cooked/` byte-identical to the committed one except `provenance.json`.
- The Maya job's pictures for the five sets under `verification/maya-2026/textures/`, in the gallery, read by
  a human; the untextured shader ball's picture unchanged by the shell change (the S2 gate).
- `build_shaders.py --check` current; the core's GPU test for `legacy_v2_normal_ts` with a two-channel sample passes.

## Out of scope

- The wgpu texture bind group (T3b). Detail-map blending in any host (`_DH`, `_DN`): the cook writes them, the
  hosts blend nothing yet; the standard names reoriented normal mapping as the host's job for a later increment.
- Anisotropy, specular colour, specular occlusion and cavity maps on the sourced sets (Poly Haven ships none;
  the grid tile's `_C` is the one cavity map and no sourced document binds one).
- T4, the showcase set authored with the owner (the alpha carrier, emission, the feature-per-map set).
- A material editor; the calibration scene (track E, G5); the comparison framework (G4).

## The questions for the owner

1. **The host half.** Recommended: Maya reads the runtime set in T3 (two generated changes to the shell's
   material half, a probe job first, the fallback being uncompressed DDS from the cook), and the wgpu texture
   bind group is T3b with its own spec. The alternative is wgpu first (fully in our hands, headless-testable,
   but a bind group, DDS upload and two material halves to write, 1 to 2 d more) with Maya following. Maya is
   the production target and already samples eight maps; that is the recommendation.
2. **The sets.** Recommended: `cobblestone_floor_04` (ground, the proof set), `brick_wall_001`,
   `brown_planks_03`, `blue_metal_plate`, all Poly Haven CC0 at 2K; plus the legacy grid tile at its 1K. Any
   other CC0 set of the same kind serves; the owner may name favourites.
3. **The grid tile's unmapped maps.** Recommended: `grid_concavity` carried as `_C` (cavity); curvature,
   convexity, derivative, transmission and the packed masks not carried until a standard parameter takes them;
   the alpha variants left to T4. The alternative is to carry everything under `content/textures/grid/legacy/`
   outside the grammar, which the content check would have to exempt; not recommended.

## Amendments after #57 merged (Copilot's nine, 2026-10-04)

All nine valid, folded into the text above and the plan:

- **No core change for the BC5 normal**: `legacy_v2_normal_ts` already derives Z with a clamp; the
  `normalMapChannels` uniform is withdrawn; a GPU test case holds it; legacy v1 recorded for T3b.
- **The Maya binder is a deliverable**: `bind()` refuses every host but wgpu; a standard document converts to
  legacy v2 through the reverse table, then binds to the shell's attributes, flags and texture slots.
- **Normals stay 8-bit** (the content table's depth); height 16-bit.
- **`blue_metal_plate` binds `base_metalness` with factor 1.0 and the texture**, since v2 multiplies the sample
  by the factor and resolution merges the child's keys into the parent's 0.0.
- **Cavity coverage is deferred**, said explicitly; the coverage test lists each parameter.
- **Height resolves through the manifest**, standalone or packed in a carrier's alpha, never by a fixed name.
- **`content-runtime` covers both content roots** (the grid included), checks manifest presence, map coverage
  and hashes; today's checker verifies none of that.
- **The probe cooks two scratch sets** so every committed format is loaded (BC4, `R8_UNORM`, `R16_UNORM`
  included), with and without the encoder.
- **The probe's choice is carried explicitly** (`--compress` or `--no-compress` on `cook` and `separate`, the
  gate's recipe and the README), never the automatic default.

## Amendments made in the build (2026-10-04)

- **`metal_plate`, not `blue_metal_plate`**: Poly Haven's `blue_metal_plate` ships no metalness map (a painted,
  dielectric plate); `metal_plate` does, so it is the metal family's set and the one whose `_ORM` carries all
  three channels. Found by reading the asset's file list, not its name.
- **Poly Haven's PNGs are a mix of depths and channel counts** (16-bit colour, grey-alpha roughness and AO, 8-bit
  normals here and 16-bit there), so `tools/fetch_polyhaven.py` brings every map to the suffix table's form at
  fetch (colour and normal 8-bit RGB, masks 8-bit grey, height 16-bit grey) and records the download's url and md5
  in the sidecar's provenance; the authoring set in the repository is the normalised one, 25 MB a set.
- **The probe's answer: Maya 2026 decodes BC7 (sRGB and linear), BC5, BC4, `R16_UNORM`, `R8_UNORM` and the
  uncompressed forms at full size** (`verification/maya-2026/textures/probe/*/check.log`), so every committed
  `cooked/` is `--compress`ed (BC7 basic); no fallback was needed.
- **The grid tile's AO is `grid_occlusion` (16-bit), not `grid_ambOcc`**: the two differ by at most one 8-bit step
  (mean 0.002), so the higher-precision source was taken and reduced to the table's 8 bits.
- **The packed map is a top-level `packed` section of the host map**, not a parameter entry (`ormMap`,
  `useOrmMap`, order 120, `channels` per legacy parameter); the generator emits it after the separate maps, the
  checker validates it, the binder writes its flag off and exposes it through `maya_packed_slots`, and the Maya
  check connects one `_ORM` there and turns the three separate flags off. The shell samples `orm.g`, `orm.b`,
  `orm.r` when the flag is on, the separate maps otherwise.
- **The resident GUI worker leaks environment between jobs** (the board's row): the first gate run landed under
  `textures/gate/` because `HOGSHADE_CHECK` from the texture job was still set. The texture job now clears its
  own keys it does not set; the gate was rerun with `check=ibl-check` named explicitly, as two renders in one
  session (master's shell, then the regenerated one).
- **A document from a set's maps** is `hogshade.material.sets.document_for_set` (the grid tile's in-memory
  document; a standard document binding every map with the multiplying factors at 1.0), used by the Maya check
  when no document is named.

