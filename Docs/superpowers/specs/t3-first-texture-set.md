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
directly, no master is downsampled here, unlike the IBL cook): `_BC`, `_R`, `_AO`, `_M` at 8 bits (they are
8-bit at runtime, BC7 and BC4), `_N` and `_H` at 16 bits (the cook keeps height at 16 bits as `R16_UNORM`, and
a 16-bit normal survives the BC5 encode with less banding on flat areas). A set is then 15 to 25 MB of
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
no `_M` sidecar; `base_metalness` stays the family's 0). The library index (`content/materials/README.md`,
generated) gains the four rows; the roster coverage test gains "the four texture parameters covered" from the
design: `base_color`, `geometry_normal`, `specular_roughness`, `ambient_occlusion` bound at least once, plus
`base_metalness` and `height` from the sets that have them.

The grid tile binds to no document in T3 (the calibration scene is track E, after G5); it is cooked and
checked like the others, and the Maya job renders it too, so the tile is seen.

### 3. From a document's texture to the runtime file: `hogshade.material.runtime`

A document names the authoring PNG; a host reads the cooked DDS; three authoring maps become one `_ORM`. The
resolution lives in the library, not in a host: `runtime_textures(binding, set_dir)` reads the set's
`cooked/manifest.json` and returns, per bound parameter, the DDS path and the channel: `base_color` to
`cooked/T_<set>_BC.dds` (`rgb`, alpha when the manifest says a map rides there), `geometry_normal` to
`cooked/T_<set>_N.dds` (`rg`, Z reconstructed by the host), `specular_roughness` to `cooked/T_<set>_ORM.dds`
channel `g`, `base_metalness` channel `b`, `ambient_occlusion` channel `r`, `height` to `cooked/T_<set>_H.dds`
(`r`, with the manifest's format so the host knows `R16_UNORM` from `R8_UNORM`), `emission_color` to
`cooked/T_<set>_E.dds`. A set with no `cooked/manifest.json` is a `CookError`-shaped failure naming the cook
command, never a fallback to the PNG: the standard says no host converts at load. `check_content.py` gains
**content-runtime**: every bound set under `content/materials/` has a `cooked/manifest.json` whose `textures`
cover every map the document binds (a document binding `_M` whose set cooked no metalness is a finding), and
the manifest's input hashes match the authoring files when LFS payloads are present (logged as unverified when
they are pointers, like `content-sidecar`'s resolution).

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
- **The normal map is read as three channels** (`baseNormalMap.Sample(...).xyz * 2 - 1`), but `_N` is BC5, two
  channels; `.z` reads 0 and the decoded normal points into the surface. The change belongs to the core's
  material half, the `<model>_inputs` function that turns texture samples into `SurfaceInputs`: a two-channel
  normal has Z reconstructed as `sqrt(1 - x² - y²)` (the cook's `normals.reconstruct_z` is the NumPy twin
  already), selected by a `normalMapChannels` uniform the generated shell sets from the binding (2 for a
  cooked `_N`, 3 for a legacy RGB normal). A core change carries the core contract: the prefix rule, the NumPy
  twin, the GPU test in `tests/core/`, `build_shaders.py --check` current.

Both changes are in the material half, which is the generated and hostable layer, not the BRDF; neither changes
a picture for a document without textures, and the S2 pixel-identical gate (master's shell against the
regenerated shell on the untextured shader ball) holds that.

**The first task is a probe, not a build**: a Maya job connects one cooked set's DDS files (BC7 sRGB, BC5, BC4,
`R16_UNORM`) to the shell's map attributes and logs what Maya decoded (`connect_file` already reports whether
Maya read the file). Maya's image library has read DDS since the legacy days and the IBL cook's
`R16G16B16A16_FLOAT` cubes load today, but no block-compressed 2D DDS has been loaded in this repository yet, and
if BC7 or BC5 do not decode, the fallback is in the cook, not the host: `--no-compress` writes the same set
uncompressed (`R8G8B8A8_UNORM_SRGB`, `R8G8_UNORM`, `R8_UNORM`), the standard's table already says "or
uncompressed until", and the manifest tells the host which it got. The probe's log is the first artifact of the
build and decides which the committed `cooked/` carries for Maya.

**The job**: `hogshade.jobs.maya_texture_check` on the IBL check's pattern (the GUI Maya worker, `_session`,
`HOGSHADE_*` variables): it loads the shell, applies one document through `bind(resolved, "maya_dx11")` and
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
  document binding a map the cook did not write, with hashes that match and that do not; on the corpus, clean.
- `tests/material/test_runtime.py`: `runtime_textures` on the brick fixture of the cook tests: every channel
  home, the `_ORM` channels, a packed alpha, the format carried for height, the error without a manifest.
- `tests/material/test_library.py`: the four documents validate, bind for both hosts, the coverage test's new
  rows (the four texture parameters bound at least once).
- `tests/core/`: the two-channel normal reconstruction's GPU test against `normals.reconstruct_z`; the generated
  shell's `ormMap` block against the host map (`generate_material_ui.py --check`).
- `tests/jobs/`: the Maya texture check job is registered, its manifest lists its outputs, a climbing `set` is
  refused.
- The Maya pictures are read by a human: each set on the shader ball with its colour, normal and roughness
  legible, the metal plate's metalness visible, the grid tile's cells aligned, the height map's parallax on the
  cobblestones; stated in the PR.

## Acceptance gate

- `uv run tools/check_content.py` clean on the five committed sets; `pytest` green on both legs; CI's LFS-less
  checkout logs the pointers as unverified and passes.
- `uv run tools/cook_textures.py cook content/materials/standard/rough/brick_wall_001` on a fresh clone with
  LFS payloads writes a `cooked/` byte-identical to the committed one except `provenance.json`.
- The Maya job's pictures for the five sets under `verification/maya-2026/textures/`, in the gallery, read by
  a human; the untextured shader ball's picture unchanged by the shell change (the S2 gate).
- `build_shaders.py --check` current; the core's GPU test for the reconstruction passes.

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
