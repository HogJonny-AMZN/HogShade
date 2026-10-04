# Content standards: textures, materials, lighting and rendering

**Status:** Living. Written 2026-10-03 from the accepted conventions design (T1); one page for a human artist and
an agent at once, with the why on every rule and the check that holds it.
**Last updated:** 2026-10-03
**Read with:** [python.md](python.md) for the tools, [definition-of-done.md](definition-of-done.md),
[../design/2026-10-03-content-conventions.md](../design/2026-10-03-content-conventions.md) for the decisions and
the owner's answers, [../glossary.md](../glossary.md) for the words.

## What this is for

The same material must look the same in every host, and every parity bug the blind-spots design listed
in its section 6 (texture packing, gamma, compression, the normal-map sign) was a convention nobody had
written down. This page writes them down once, for both readers: an artist adding a texture and an agent
adding one follow the same rules and are held to them by the same checks. The texture rules are **data
before prose**: `hogshade/material/textures.py` holds the suffix table, the packed and derived maps, the
presets and the name grammar; the tables below are generated from it (`tools/generate_material_ui.py
--write`, `--check` in CI), so this page, the check and the cook cannot disagree. The owner's two decisions
by name: the `T_` prefix stays on every texture file, and base colour is `_BC`, never `_D` ("we are
ditching _D (diffuse)").

Checks that hold this page: `tools/check_content.py` (CI step "Content") for textures, sidecars, bindings
and licences; `tools/check_docs.py` for links and status; `tools/generate_material_ui.py --check` for the
generated tables. A rule without a check says so.

## Textures

### The name

Every texture file is `T_<base>_<SUFFIX>[_<variant>]`, on Unreal's `Prefix_BaseName_Descriptor_Variant`
pattern (Epic's recommended convention gives the pattern and the `T_` prefix and leaves the descriptors
to the project). `<base>` is `snake_case`, so a Poly Haven slug keeps its name
(`T_cobblestone_floor_04_BC`); `<SUFFIX>` is the first all-caps token and names the schema parameter the
map binds; `<variant>` (`_01`, `_damaged`, `_wet`) is lower-case and comes **after** the suffix, never
before. A name ending in a digit is fine here (no content browser renames it). `T_` says "a texture" by
copy, so a file is portable to a target that expects the prefix without a rename.

<!-- BEGIN hogshade.material.textures generated (tools/generate_material_ui.py --write); do not edit -->

Prefix `T_` on every file. One suffix per texturable parameter of `hogshade-standard` (14), from `hogshade/material/textures.py`:

| Suffix | Parameter | Colour space (the schema's) | Runtime | Authoring | Note |
| --- | --- | --- | --- | --- | --- |
| `_BC` | `base_color` | srgb | BC7, mips linear-box | 8-bit | the schema's word; never _D, diffuse means something else here |
| `_M` | `base_metalness` | raw | BC4, mips linear-box | 8-bit | metalness only, never a mask |
| `_SW` | `specular_weight` | raw | BC4, mips linear-box | 8-bit |  |
| `_SC` | `specular_color` | raw | BC7, mips linear-box | 8-bit |  |
| `_R` | `specular_roughness` | raw | BC4, mips linear-box | 8-bit | roughness, never gloss |
| `_AX` | `specular_anisotropy` | raw | BC4, mips linear-box | 8-bit |  |
| `_AR` | `specular_rotation` | raw | BC4, mips linear-box | 8-bit |  |
| `_E` | `emission_color` | srgb | BC7, mips linear-box | 8-bit |  |
| `_O` | `geometry_opacity` | raw | BC4, mips linear-box | 8-bit | or the alpha of _BC when the sidecar packs it |
| `_N` | `geometry_normal` | raw | BC5, mips linear-box | 8-bit | OpenGL +Y; two channels, Z reconstructed |
| `_AO` | `ambient_occlusion` | raw | BC4, mips linear-box | 8-bit |  |
| `_C` | `cavity` | raw | BC4, mips linear-box | 8-bit |  |
| `_SO` | `specular_occlusion` | raw | BC4, mips linear-box | 8-bit |  |
| `_H` | `height` | raw | BC4, mips linear-box | 16-bit | R16 when the cook says |

Maps a document never binds directly (the cook's packed form, the derived detail pair):

| Suffix | What | Colour space | Runtime |
| --- | --- | --- | --- |
| `_ORM` | packed: ambient occlusion in R, roughness in G, metalness in B; the runtime form of _AO, _R, _M | raw | BC7 |
| `_DN` | detail normal, derived by the cook (the high frequency of a normal map) | raw | BC5 |
| `_DH` | detail high-pass colour, derived by frequency separation; mid-grey neutral | raw | BC7 |

Sidecar fields: derived from the suffix when absent: `preset`, `colour_space`, `mips`, `runtime`, `resolution`; required of the author: `provenance` (`origin`, `url`, `licence`, `fetched`) on every texture, `normal_convention` on an authored `_N` (a derived `_DN` is the cook's); `override_reason` when a derived field is set against the suffix; `derived` listed by the cook.
<!-- END hogshade.material.textures generated -->

A map that is **not a parameter** (the packed runtime form, the derived detail pair) has its own suffix
and is never bound by a material document: a document binds `_AO`, `_R` and `_M`; the cook packs them
into `_ORM` for the runtime set. `specular_ior` and `alpha_mode` have no colour space in the schema and so
no suffix: an index of refraction and a mode are not textures. Why one suffix per parameter: the schema is
the one place a parameter's colour space is declared (S1), so a name that says the parameter says the
colour space, and the check can hold a file to it without reading pixels.

### The sidecar

Every source texture has `<T_name_SUFFIX>.texture.json` beside it, committed, read by the cook and the
check (O3DE's `.assetinfo` idea: a preset per suffix, overridable with a reason). Two kinds of field:

- **Derived from the suffix** when absent, so a sidecar may omit them: `preset`, `colour_space`, `mips`,
  `runtime`; `resolution` is read from the file. A derived field that is present and disagrees with the
  suffix is a finding unless `override_reason` says why. The cook lists the fields it filled under
  `derived`.
- **Required of the author**, because no suffix can know them: `provenance` (`origin`, `url`, `licence`,
  `fetched`; `origin` is `"author"` or the source's name) on every texture, and `normal_convention` on an
  authored `_N` (`opengl+y` or `directx-y`, **the source's**; the cook flips a DirectX source and records
  it; a derived `_DN` is the cook's, always `opengl+y`, and needs none). A normal map with no stated convention is a finding, never a guessed flip: a guessed flip is the
  silent mismatch this page exists to end.

```json
{
  "preset": "geometry_normal",
  "colour_space": "raw",
  "normal_convention": "directx-y",
  "source": "cobblestone_floor_04_nor_dx_2k.png",
  "resolution": 2048,
  "mips": "linear-box",
  "runtime": {"format": "bc5", "container": "dds"},
  "provenance": {"origin": "polyhaven", "url": "https://polyhaven.com/a/cobblestone_floor_04", "licence": "CC0-1.0", "fetched": "2026-10-03"}
}
```

### The authoring set and the runtime set

A set lives **beside the material that binds it**: `content/materials/standard/<family>/<set>/`, bound by
`<family>/<set>.material.json` as `<set>/T_<set>_BC.png`, because a document's texture path may not climb
(S1 refuses `..`, the Maya check's confinement rule) and so a texture a document binds is below the
document. `content/textures/<set>/` is for sets no document binds yet (the calibration tiles). Either way
the set directory holds the **authoring set**: one map per parameter, PNG or 16-bit TIFF, EXR for a
height map that needs range, 2K (the LFS budget; the 8K masters stay outside the repository as the IBL
masters do), in git LFS (`.gitattributes`: PNG and TIFF under `content/materials/` and `content/textures/`; `content/ibl/` keeps its display previews in plain git), with a `LICENSE.md` in the directory on the `content/ibl`
pattern (source URL, licence, fetch date, where the master lives) and the sidecars. A JPEG is not an
authoring format and is a finding wherever it lands. The **runtime set** lives
under `<set>/cooked/`, written only by the cook (T2, a BATS job on the IBL cook's pattern): `_ORM` packed,
BC-compressed DDS, mips generated in linear space, normals as `opengl+y`, with `manifest.json`
(deterministic: parameters, sha256 of inputs and outputs) and `provenance.json` (volatile). **No host
converts a texture at load**; every host reads the cooked set, as no host convolves its own IBL. The
runtime set is reproducible from the authoring set alone (`uv run tools/cook_textures.py cook <set>`; the
encoder is `ispc_texcomp`, the `textures` extra under `uv sync --all-extras`, and without it the cook writes
uncompressed and says so). The check insists that anything under `cooked/` is DDS, `manifest.json` or
`provenance.json`, and that no packed or derived map (`_ORM`, `_DN`, `_DH`) sits outside it. A sidecar's
`pack` field (`{"a": "_O"}` on `_BC`, `_E`, `_SC` or an `_ORM` source) puts a single-channel map in that
carrier's alpha; the manifest records where every channel lives. Height keeps its source precision: a 16-bit
PNG to `R16_UNORM`, a half EXR to `R16_FLOAT`, a float EXR to `R32_FLOAT`; BC4 only for an 8-bit source. A source wider than 2048 on a side is a
finding (the sidecar's `resolution` and the PNG header both). On a checkout without LFS payloads
(CI), a PNG is a pointer and the sidecar's stated resolution is logged as unverified, not judged.

Colour spaces: sRGB for base colour and emission only (`_BC`, `_E`); everything else raw. Mips are
generated in linear space. Normal maps are OpenGL +Y in the repository and BC5 at runtime (two channels,
Z reconstructed); colour is BC7; single channels are BC4. These are track E's conventions, now written
down; the roadmap's texture-conventions box points here.

### Sources and licences

Content is CC0 or made here, never a studio tree. Poly Haven and ambientCG on the IBL pattern
(`content/ibl/<env>/LICENSE.md` is the template); the owner's own legacy test tiles (`grid_*`, provenance
`"author"`) as the calibration tile (T3); a showcase set authored with the owner for what a sourced set
cannot show (T4). The sets committed in T3: `cobblestone_floor_04` and `brick_wall_001` (rough),
`brown_planks_03` (dielectric), `metal_plate` (metal), each beside the standard document that binds it, and
the grid tile under `content/textures/grid/`; `tools/fetch_polyhaven.py` brings a Poly Haven set in (md5
against the API, the suffix table's bit depth and channels at fetch: Poly Haven serves a mix of 8 and 16 bits
and grey-alpha masks). Every committed `cooked/` is block-compressed (`--compress`), as the Maya probe decided. Generated textures enter only through the validation harness the gated-research row
describes; this page's checks are its first piece.

### Tangents, detail maps and frequency separation

**MikkTSpace is a requirement, not a convention** (owner, 2026-09-26): every host, bake path and exporter
assumes it; a mesh with tangents from another basis is a validation failure with a message. The generator is
the repository's own (`hogshade.mikktspace`, T3b; the owner, 2026-10-04: "gen MikkT on arbitrary data"): it
takes positions, **the normals as the source gives them** (custom normals survive; nothing recomputes a normal),
UVs and triangles, welds by position, normal and UV with the handedness kept apart, and a host generates when a
file carries none (an OBJ). A file that carries tangents of an **unknown** basis is flagged (a WARNING naming the
mesh) and regenerated; a declared basis other than MikkTSpace is the validation failure above
(`hogshade.wgpu_host.with_tangents`). The wgpu host reads the cooked set on that frame (`hosts/wgpu/README.md`:
the material bind group, V flipped at the sample as the Maya shell negates it, `texture-compression-bc` asked of
the device, the cook's `--no-compress` output as the fallback). Maya's MikkTSpace is the preference Preferences >
Modeling > Polygon Tangent Space > "Use MikkTSpace tangents" (`polyUseMikkTSpaceTangents`, off by default; the
orchestrator's Maya workers set it at boot), not the mesh's `tangentSpace` attribute; against Maya's MikkTSpace the
handedness agrees on every corner and the direction to a median of 0.000 degrees, 98.8 percent within 1 (the T3b
spec's "what the build found"). Detail mapping
uses a derived pair: `_DH`, the high-pass colour of a map, blended by **linear light** and nothing else
(O3DE's `TextureBlend_LinearLight`, `saturate(base + 2 * mask - 1)` in display space); and `_DN`, the
detail normal, blended by reoriented normal mapping. Both come from the cook's **frequency separation**
(the owner's technique: a Gaussian low-pass on a 3x3 tiled canvas so both halves tile, the high-pass that
recombines exactly under linear light, the reconstruction error measured into the manifest), never from a
Photoshop recipe.

## Materials

A material is a document (`*.material.json`, S1): a type, a parent beside it (`base.material.json` in the
family's directory; no `..` in any path), values as deltas, `title`, `doc` and `provenance` with a note
naming every value the document sets (S4a). A texture is bound by path to a parameter; the parameter's
schema `colour_space` is the texture's colour space, and `check_content.py` holds the file's suffix to the
parameter and the sidecar's colour space to the schema's. Comparison between models is by conversion
tables, never a shared type; what a table loses is on the library index
(`content/materials/README.md`). The library's own rules are in the S4a spec; this page does not repeat
them.

## Lighting

Decided (track E, owner-locked): the cooked IBL (`content/ibl/`) is the only IBL, no host convolves its
own; the calibration environment is `studio_small_09`. The light-rig description (HDR file, rotation in a
stated axis convention, exposure in EV, punctual lights in one unit with a documented conversion per
host) is **undecided, track E**: this page will carry it when the comparison framework design (gate G4)
writes it, and says "undecided" rather than inventing it.

## Rendering and capture

Decided (track E, owner-locked): scene-referred ACEScg end to end; captures as EXR plus a display PNG
through one view transform, AgX by default, ACES first-class; comparisons raw-to-raw first,
display-to-display second. Pictures obey `verification/README.md` (PNG, at most 1024 on a side, fixed
names, plain git) and the gallery manifest. The conventions the comparison framework must state per host
(camera handedness and projection, NDC depth, UV origin, up axis and units, HDR rotation) are on the
board's comparison-framework row and **undecided** until that design.

## The checks

| Check | Holds |
| --- | --- |
| `check_content.py` content-table | the suffix table covers the schema's texturable parameters exactly, with the schema's colour spaces |
| `check_content.py` content-name | every file under `content/materials/` and `content/textures/` that is not a record is an authoring format (lower-case extension) named `T_<snake_case>_<SUFFIX>[_<variant>]` with a parameter suffix; packed and derived maps only under `cooked/`, which holds DDS, `manifest.json` or `provenance.json` |
| `check_content.py` content-sidecar | every source texture has its sidecar: provenance, an authored normal map's convention, no derived field contradicting the suffix without a reason, a stated resolution matching the PNG and within the 2K budget |
| `check_content.py` content-binding | a `hogshade-standard` document binds a file whose suffix is the bound parameter's; the sidecar's colour space is the schema's; a document of another type is logged, not held |
| `check_content.py` content-licence | every directory holding source textures carries `LICENSE.md` |
| `generate_material_ui.py --check` | the tables above are current with `hogshade/material/textures.py` |
| `check_docs.py` | this page's links and status |
