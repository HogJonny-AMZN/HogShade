# T1 spec: the content standard and its check

**Status:** Accepted. Drafted 2026-10-03 from the accepted conventions design (the owner's "go" of the same
day) as #50, built the same night on `feat/t1-content-standard`; the build's amendments are the last section.

Date: 2026-10-03. Design:
[../../design/2026-10-03-content-conventions.md](../../design/2026-10-03-content-conventions.md), "The shape
proposed" and "The answers". S1: [s1-material-schema.md](s1-material-schema.md) (a texturable parameter's
`colour_space`; a document's texture value); S4a: [s4a-material-library.md](s4a-material-library.md) (the
index's generated pages). Plan: [../plans/t1-content-standard.md](../plans/t1-content-standard.md).
Vocabulary: [../../glossary.md](../../glossary.md).

## Deliverable

`Docs/standards/content.md`: the conventions for textures, materials, lighting and rendering, written for a
human artist and an agent at once, with the why on every rule, pointed at by `AGENTS.md`, the docs map and
Copilot's instructions. The texture rules are data before they are prose: `hogshade/material/textures.py`
holds the suffix table and the presets, the standard's tables are generated from it between markers (the
Maya shell's mechanism, S2), and `tools/check_content.py` holds every texture under `content/` and every
texture a material document binds to the rules, in CI. After T1 a texture that is misnamed, unsourced, of
an unstated normal convention, or bound to a parameter whose colour space its sidecar contradicts is a CI
finding, before any cook or host sees it. T1 ships no texture; it makes the first one (T3, which is S4b)
checkable on arrival.

## Package layout

```text
hogshade/material/
  textures.py                      # SUFFIXES (suffix -> parameter, space, runtime), PACKED, presets, name parsing
  generators.py                    # generate("content"): the standard's tables between markers
Docs/standards/content.md          # the standard; tables generated between CONTENT_BEGIN/END markers
tools/generate_material_ui.py      # a fourth output: the standard's generated tables (--check, --write)
tools/check_content.py             # the content check (CI step "Content")
tests/material/test_material_textures.py
tests/test_check_content.py
```

`textures.py`: the package exports no `textures` name (failure-modes entry 13).

**Where a texture lives.** S1 refuses any `..` in a document's texture path, and a root passed to `load()`
does not change the reference base, so a document under `content/materials/` cannot reach
`content/textures/`. A set a document binds therefore lives **beside the document**:
`content/materials/standard/<family>/<set>/T_<set>_BC.png`, bound by `<family>/<set>.material.json` as
`<set>/T_<set>_BC.png`. `content/textures/<set>/` is for sets no document binds yet (the calibration
tiles). Both are content roots; every rule below applies to each. The design's section 4 is amended by
this. The clean scratch-corpus test loads a binding through S1 in this layout, so the first set is usable
on arrival.

## The texture rules, as data

`hogshade.material.textures`:

```python
PREFIX = "T_"                                  # the owner's answer 1: every texture file carries it
SUFFIXES: dict[str, Suffix]                    # the fourteen texturable parameters of hogshade-standard
#   "_BC": Suffix(parameter="base_color", colour_space="srgb", runtime="bc7", mips="linear")
#   "_N":  Suffix(parameter="geometry_normal", colour_space="raw", runtime="bc5", normal=True) ...
PACKED: dict[str, Packed]                      # maps a document never binds: "_ORM", "_DN", "_DH"
NAME_RE                                        # T_<snake_case>_<SUFFIX>[_<variant>]  (variant: [a-z0-9]+)
def parse_name(stem) -> TextureName | None     # prefix, base, suffix, variant, or None when not admissible
def preset_for(suffix) -> Preset               # colour space, runtime format, mips, whether normal
def check_table(type_name="hogshade-standard") -> list[Finding]   # every texturable parameter has one suffix, no suffix twice, every suffix's space is the schema's
```

The table is held to the schema by `check_table` and a test: a texturable parameter without a suffix, a
suffix naming a parameter the type lacks, a suffix whose colour space is not the schema's, two suffixes for
one parameter are findings. `specular_ior` and `alpha_mode` carry no colour space and so no suffix.

## The sidecar

`<T_name_SUFFIX>.texture.json` beside the source. Fields, per the design's answer 4 (committed, read by the
cook, validated by the check):

| Field | Kind | Rule |
| --- | --- | --- |
| `preset` | derived | the suffix's; an override names `override_reason` |
| `colour_space` | derived | the suffix's, which is the schema's for the parameter; omitted means the suffix's (the **effective** colour space) |
| `mips`, `runtime` | derived | the preset's |
| `resolution` | derived | read from the file; the check compares when the file is readable (PNG header) |
| `provenance` | **required** | `{"origin", "url", "licence", "fetched"}`, every value a non-empty string; `origin` is `"author"` or a source name |
| `normal_convention` | **required for `_N`** | `"opengl+y"` or `"directx-y"`, the source's; the cooked output is always `opengl+y`. A derived `_DN` is the cook's and needs none |
| `derived` | written by the cook | the list of fields it filled; informational |

The check reads a sidecar with `json.loads`; a missing sidecar beside a texture is a finding, a malformed
one is a finding, and a derived field present but disagreeing with the suffix is a finding unless
`override_reason` is set.

## The check

`tools/check_content.py` (the shape of `generate_gallery.py`: `Finding(where, message)`, `--check` only,
exit 1 on findings, counts in the log):

- **content-name**: every image file under the content roots (png, tif, tiff, exr; a jpg, jpeg, bmp or tga
  is a finding, not an authoring format) parses as `T_<base>_<SUFFIX>[_<variant>]` with a suffix from
  `SUFFIXES` or `PACKED`; the base is `snake_case`. A file under `cooked/` (judged on the path relative to
  the content root) is exempt from the source rules and must be `.dds` or the cook's manifest.
- **content-sidecar**: every source texture has its sidecar with the required fields and consistent
  derived ones.
- **content-binding**: every texture a **`hogshade-standard`** document under `content/materials/` binds
  (S1's `texture` value) names a file whose suffix maps to the bound parameter (a `_N` bound to
  `base_color` is a finding; a `_ORM` bound directly is a finding) and whose **effective** colour space,
  the sidecar's when stated and the suffix's when omitted, equals the schema's for that parameter. The
  suffix table is the standard's, so a document of another type (legacy v2's `normal_map`, say) is logged
  at INFO with its bound-texture count and not held to it; a per-type table is a later increment if a
  legacy document ever binds a texture. A positive test covers the legacy policy.
- **content-table**: `textures.check_suffixes()` is clean (`check_table` is already the conversion tables'
  name), and the standard's generated tables are current.
- **content-licence**: every directory holding source textures carries a `LICENSE.md` (the IBL pattern).

`tests/test_check_content.py` runs each on a scratch corpus (a test-built PNG, as `test_generate_gallery`
does) and on the repository, which today has no `content/textures/` and so passes vacuously except for
the table and the standard's tables, which are the real T1 proof.

## The standard

`Docs/standards/content.md`, Status Living, in this order, each rule with its why and its source:

1. **What this is for**, two readers, one page; where the checks live.
2. **Textures**: the name (generated table), the sidecar (fields table, generated), the authoring and
   runtime sets and the cook's promise (T2), sources and licences (`LICENSE.md` per set; CC0 or made here;
   never a studio tree), the MikkTSpace requirement, detail maps and frequency separation (the owner's
   technique, T2), what a sourced set cannot show and the showcase set (T4).
3. **Materials**: the document, the family directories, provenance per value, the texture binding rule,
   the four conversion tables and their losses (links, not copies).
4. **Lighting**: the rig description and the calibration environment; the cooked IBL rule; track E's
   owner-locked items quoted; "undecided, track E" where so.
5. **Rendering and capture**: scene-referred EXR plus display PNG, AgX default, the picture rule, the
   gallery, the host conventions the comparison framework must state.
6. **Checks**: the table of what `check_content.py` and `check_docs.py` hold, one row each.

`AGENTS.md` gains the standard in its table of where to look; `Docs/README.md`'s standards line names it;
`.github/copilot-instructions.md` points at it; the glossary gains **Sidecar**, **Preset**, **Authoring
set**, **Runtime set**, **Detail map**.

## Tests

- `tests/material/test_material_textures.py`: the shipped table passes `check_table`; the fourteen
  suffixes cover the schema's texturable parameters exactly; mutations name their finding; `parse_name`
  accepts `T_cobblestone_floor_04_BC`, `T_grid_N_01`, rejects `cobblestone_BC` (no prefix),
  `T_Cobblestone_BC` (not snake_case), `T_grid_XX`, `T_grid_BC_Damaged`; `preset_for("_N").normal` is true.
- `tests/test_check_content.py`: the scratch corpus with one good set is clean; a misnamed file, a missing
  sidecar, a sidecar without provenance, a `_N` without `normal_convention`, a derived field contradicting
  the suffix without a reason, a document binding a `_N` to `base_color`, a set without `LICENSE.md` each
  name their finding; the repository passes.
- `test_material_generate.py`: the standard's generated tables equal the committed ones (`--check`).

## Acceptance gate

- `uv run pytest tests/material tests/test_check_content.py tests/test_check_docs.py` green on CI; the CI
  step "Content" (`uv run tools/check_content.py`) green; `generate_material_ui.py --check` current with
  the standard's tables; `check_docs.py`, `check_hygiene.py` clean.
- A human reads `Docs/standards/content.md` top to bottom and finds every rule with a why; the owner's
  two answers are visible as rules (`T_`, `_BC`).

## Out of scope

- The cook (T2), the first texture set (T3, S4b), the showcase set (T4).
- Reading pixels beyond the PNG header (no pillow): the check holds names, sidecars and bindings, not
  content; the cook's manifest will hold content.
- Lighting and rendering rules not yet decided by track E: the standard says "undecided" rather than
  deciding.

## Amendments made in the build (2026-10-03)

- **A set lives beside the material that binds it.** The spec and the design placed sets under
  `content/textures/<set>/`, but S1 refuses any `..` in a document's texture path, so no document under
  `content/materials/` could bind a texture there: the placement rule and the binding rule could not both
  hold (the pre-PR review). Decided: a bound set is a sub-directory of the family that owns it,
  `content/materials/standard/<family>/<set>/`, bound as `<set>/T_<set>_BC.png`; `content/textures/<set>/`
  stays for sets no document binds yet (the calibration tiles). The content roots are both; the name,
  sidecar and licence rules apply to each; the licence is per directory of source textures. The design's
  section 4 is amended by reference.
- The binding check holds `hogshade-standard` documents only (the suffix table is the standard's); a document
  of another type with bound textures is logged at INFO and not judged. `cooked/` is recognised on the path
  relative to the content root, not the absolute path (a checkout under a directory named `cooked` is fine).
  An LFS pointer where a PNG should be logs the resolution as unverified (CI's checkout). A JPEG, BMP or TGA
  anywhere under the content roots is a finding: not an authoring format. A sidecar's stated `resolution`
  may not be a bool; a partial `runtime` object agrees key by key; a derived `_DN` needs no author-stated
  convention, it is the cook's.
- The table check is `check_suffixes()`, not `check_table()`: the package already exports
  `conversion.check_table`, and one name for two checks would be the synonym drift the glossary forbids.
  `parameter_of(suffix)` was added so the binding check can ask which parameter a suffix is without
  reaching into the table.
- `parse_name` returns a `TextureName` for any stem that meets the grammar, with `known` saying whether the
  suffix is in the tables; the check reports "not the grammar" and "unknown suffix" as different findings.
- The sidecar's `resolution`, when stated, is compared with the PNG header (the gallery's reader); other
  formats are not read.
- The content-binding check locates a bound texture relative to the document (the texture string is
  document-relative, S1) and does not apply the name or licence rules to it: those are the textures
  directory's. A test says so. A document that binds a `_ORM` directly is a finding: the packed form is the
  cook's output, never an authoring input.
- The CI step is "Content", after "Gallery"; PNG and TIFF under both content roots are LFS from now (the
  second review round: a bound set under `content/materials/` must be tracked too), so the first set lands
  tracked wherever it lives.
- `.github/copilot-instructions.md` gains item 8, the content rules, so Copilot reviews a texture PR against
  the same page.
