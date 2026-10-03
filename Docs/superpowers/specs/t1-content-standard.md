# T1 spec: the content standard and its check

**Status:** Proposed. Drafted 2026-10-03 from the accepted conventions design (the owner's "go" of the same
day); built on `feat/t1-content-standard` once this is merged. Amendments made in the build go in the last
section.

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
| `colour_space` | derived | the suffix's, which is the schema's for the parameter |
| `mips`, `runtime` | derived | the preset's |
| `resolution` | derived | read from the file; the check compares when the file is readable (PNG header) |
| `provenance` | **required** | `{"origin", "url", "licence", "fetched"}`, every value a non-empty string; `origin` is `"author"` or a source name |
| `normal_convention` | **required for `_N`, `_DN`** | `"opengl+y"` or `"directx-y"`, the source's; the cooked output is always `opengl+y` |
| `derived` | written by the cook | the list of fields it filled; informational |

The check reads a sidecar with `json.loads`; a missing sidecar beside a texture is a finding, a malformed
one is a finding, and a derived field present but disagreeing with the suffix is a finding unless
`override_reason` is set.

## The check

`tools/check_content.py` (the shape of `generate_gallery.py`: `Finding(where, message)`, `--check` only,
exit 1 on findings, counts in the log):

- **content-name**: every image file under `content/textures/` (png, tif, tiff, exr, jpg) parses as
  `T_<base>_<SUFFIX>[_<variant>]` with a suffix from `SUFFIXES` or `PACKED`; the base is `snake_case`.
  A file under `cooked/` is exempt from the source rules and must be `.dds` with a name the cook wrote.
- **content-sidecar**: every source texture has its sidecar with the required fields and consistent
  derived ones.
- **content-binding**: every texture a material document under `content/materials/` binds (S1's `texture`
  value) names a file whose suffix maps to the bound parameter (a `_N` bound to `base_color` is a finding)
  and whose sidecar's `colour_space` equals the schema's for that parameter.
- **content-table**: `textures.check_table()` is clean, and the standard's generated tables are current.
- **content-licence**: every set directory under `content/textures/` carries a `LICENSE.md` (the IBL
  pattern).

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

## Amendments made in the build

(none yet)
