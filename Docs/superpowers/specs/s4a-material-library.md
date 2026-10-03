# S4a spec: the base library of materials, written against the standard, rendered through the reverse table

**Status:** Accepted. Drafted 2026-10-03 from the accepted design (the owner's "go" of the same day) as #45, built
the same day on `feat/s4a-material-library`; the build's amendments are the last section.

Date: 2026-10-03. Design: [../../design/2026-10-02-material-library.md](../../design/2026-10-02-material-library.md),
"The shape proposed" and "The answers". Decision:
[ADR-009](../../decisions/ADR-009-hogshade-owns-the-material-schema.md). S1:
[s1-material-schema.md](s1-material-schema.md) (documents, tables, the coverage rule); S2:
[s2-material-generators.md](s2-material-generators.md) (the docs generator); S3:
[s3-wgpu-binding.md](s3-wgpu-binding.md) (`bind`, the viewport tool). Plan:
[../plans/s4a-material-library.md](../plans/s4a-material-library.md). Vocabulary:
[../../glossary.md](../../glossary.md), "Materials" (Library, Document, Conversion table, Loss).

## Deliverable

Twenty-two `hogshade-standard` documents under `content/materials/standard/`: six family parents and sixteen
named children, every constant with its source. They render in the wgpu host today through a new
conversion table, `hogshade-standard` to `hogshade-legacy-v2`, under S1's coverage rule, so
`convert(resolve(doc), "hogshade-legacy-v2")` feeds S3's `bind()`. A document may carry a `title`, a `doc`
and a `provenance`, validated for shape. The library's index page is generated and checked in CI like the
material reference. A contact sheet of the whole set, one picture, is the human gate and the gallery's
newest row. Between them the documents, parents and children, set every factor-bearing parameter of the
standard type, and a test says so: the library is the schema's test data.

## Package and content layout

```text
hogshade/material/
  model.py                                   # Document gains title, doc, provenance (optional)
  document.py                                # from_data reads the three fields; shape errors are MaterialError
  validation.py                              # the fields' shapes as findings on a raw document
  library.py                                 # the roster: documents_under(root), index(root) -> Markdown
  schema/conversions/hogshade-standard-to-hogshade-legacy-v2.json   # the reverse table
content/materials/
  README.md                                  # generated: the library's index (family, name, title, source)
  standard/<family>/base.material.json       # the parent; a child's parent is "base.material.json" beside it
  standard/<family>/<name>.material.json     # a child, deltas only
  legacy-v2/default.material.json            # S3's three, unchanged: the hosts' smoke documents
  legacy-v2/metal.material.json
  legacy-v1/default.material.json
tools/generate_material_ui.py                # a third output: content/materials/README.md
tools/wgpu/contact_sheet.py                  # every standard document rendered into one PNG
verification/wgpu/library/contact-sheet.png  # the human gate; listed in verification/gallery.json
tests/material/test_material_library.py
```

`library.py`: the package exports no `library` name, so the module name is free (failure-modes entry 13).
The documents live outside the package, so `library.py` takes a root directory and never reads package data
for them; the default root is an argument, not a constant.

## The document fields

Three optional top-level fields, version 1 of the format (no version bump: a reader that ignores them loses
nothing a renderer needs):

| Field | Shape | Rule |
| --- | --- | --- |
| `title` | non-empty string | A human name, `"Gold"`; the index and the contact sheet show it. |
| `doc` | string | One line on what the material is for. |
| `provenance` | list of `{"source": str, "note": str}` | Where each constant came from. `source` names a publication, a URL or `"author"`; `note` says which values and how (rounded, converted, chosen). A list, since a document may draw on several sources. |

`from_data` reads them onto `Document` (`title: str | None`, `doc: str | None`, `provenance: list[dict]`,
default empty) and rejects the wrong container type with `MaterialError` as it does `ext`. `validate()` on
a raw document reports the inner shapes as findings (an empty title, a provenance entry without `source`,
a non-string note). `resolve()` ignores them: a child's title is its own, never inherited; `Resolved` does
not carry them. `convert()` does not copy them onto the converted document (the converted document is a
derived value, not an authored one).

## The reverse table

`hogshade-standard-to-hogshade-legacy-v2.json`, under `check_table`'s rule: every standard parameter mapped
once, consulted or dropped with a reason; every target a v2 parameter; types kept across non-constant
transforms. The shape, non-normative:

| Standard | Legacy v2 | Transform |
| --- | --- | --- |
| `base_color`, `base_metalness`, `specular_weight`, `specular_roughness`, `specular_ior`, `emission_color`, `geometry_opacity` | `base_color`, `metalness`, `specular`, `roughness`, `ior`, `emission_color`, `opacity` | identity |
| `emission_luminance` (nits) | `emission_intensity` | scale by 0.01, the inverse of the forward table's placeholder 100 |
| `geometry_normal`, `ambient_occlusion`, `cavity`, `height` | `normal_map`, `ambient_occlusion_map`, `cavity_map`, `height_map` | identity (texture to texture) |
| `alpha_mode` | `use_cutout_alpha` | constant: `mask` to true; `opaque` to false; `blend` to false (v2 blends only through `has_alpha`, which a texture sets) |
| `specular_color` | dropped | v2 tints F0 only through `specular_f0_map`, a texture; a constant colour has no image |
| `specular_anisotropy`, `specular_rotation`, `specular_occlusion` | dropped | the 2017 model has no anisotropy and no specular occlusion term |

Losses the table cannot state, recorded here and on the index (`content/materials/README.md`), both
scheduled with the texture set (S4b), the first increment that binds a texture:

- The standard's normal `strength` does not reach `bump_intensity`: a table entry maps a parameter, not a
  field of one, and `geometry_normal` is already mapped. A `field` on the source side of an entry is the
  conversion-module change.
- The standard's mask cuts at 0.5; legacy v2 cuts at `opacity_mask_bias`, default 0.1, and the table cannot
  set it: `alpha_mode` already carries its one entry per condition (`use_cutout_alpha`), and a source may not
  carry two entries for one condition. With no opacity texture (every S4a document) the coverage is the same;
  an opacity texture in S4b would cut differently. The fix is either a second target per condition in the
  entry shape or a constant on the table's target side; S4b decides, since it is the increment that can see
  the difference.

The losses are a result, not a defect: they are the standard parameters no legacy host can show, which C3
needs listed.

## The roster

Six parents, sixteen children, each child under exactly one family (the directory and the parent agree).
Metal reflectances are the linear F0 values of Lagarde and de Rousiers, *Moving Frostbite to PBR* (2014),
table of measured conductors, rounded to two decimals; where a metal is not in that table the provenance says
whose value it is. Dielectric indices are the published refractive indices of the material. Roughness and
colours are the author's unless a source is named.

| Family | Parent sets | Children (the delta) |
| --- | --- | --- |
| `metal` | `base_metalness` 1, `specular_roughness` 0.4, `base_color` iron's 0.56 0.57 0.58 (the neutral conductor) | `iron` (the parent's values, titled); `steel` (the parent's reflectance, iron's; `specular_anisotropy` 0.6, `specular_rotation` 0: brushed; the one anisotropic document); `aluminium` 0.91 0.92 0.93; `gold` 1.00 0.77 0.34; `copper` 0.96 0.64 0.54; `silver` 0.97 0.96 0.92; `chrome` 0.55 0.56 0.55 (chromium); `brass` 0.89 0.79 0.43 (author: between gold and copper; not in the table) |
| `dielectric` | `base_metalness` 0, `specular_weight` 1, `specular_ior` 1.5, `specular_roughness` 0.5, `base_color` 0.5 | `plastic_matte` (IOR 1.49, PMMA; roughness 0.7); `plastic_glossy` (IOR 1.58, polycarbonate; roughness 0.2); `ceramic` (the parent's IOR 1.5, a glaze being a glass; roughness 0.15; `base_color` 0.9) |
| `coated` | the dielectric's values with `specular_roughness` 0.1, `specular_color` 1 1 1 written out (the lacquer and car-paint family until the standard has a coat layer) | `painted` (`base_color` 0.60 0.05 0.05) |
| `rough` | the dielectric's values with `specular_roughness` 0.9 | `rubber` (IOR 1.52, natural rubber; `base_color` 0.05); `concrete` (the parent's albedo; `specular_occlusion` 0.8) |
| `emissive` | `emission_luminance` 100, `emission_color` 1 1 1, `base_color` 0.1 | `panel` (`emission_luminance` 800) |
| `cutout` | `alpha_mode` `mask`, `geometry_opacity` 1 written out (the no-texture case; below 0.5 nothing renders, S1's rule) | `leaf` (`base_color` 0.10 0.35 0.08; the parent's roughness 0.6) |

Deferred by name, never faked: skin, cloth with sheen, glass, water (transmission, subsurface, a coat layer
are the standard version that carries them). The index lists them under "Deferred" with the reason.

**Coverage**: the thirteen factor-bearing parameters of the standard (`base_color`, `base_metalness`,
`specular_weight`, `specular_color`, `specular_roughness`, `specular_ior`, `specular_anisotropy`,
`specular_rotation`, `emission_luminance`, `emission_color`, `geometry_opacity`, `alpha_mode`,
`specular_occlusion`) are each set by at least one document of the roster; a test enumerates the type's
non-texture parameters and asserts it, so a schema addition fails the test until the library covers it. The
four texture parameters are S4b's.

## The library module

| Function | Contract |
| --- | --- |
| `documents_under(root) -> list[Path]` | Every `*.material.json` under `root`, sorted, parents before children within a family (`base.material.json` first). |
| `index(root) -> str` | The Markdown index of the library at `root`: a table per family (name, title, doc, the parameters the document sets, the sources), the deferred list, the known losses of the reverse table; a generated-file header. Loads and validates every document; a finding is `MaterialError`, so the index cannot describe a broken library. |

`tools/generate_material_ui.py` gains the index as a third output (`--check` diffs it, `--write` writes it);
the CI step "Material UI" covers it with no new step. The tool's docstring says so.

## The contact sheet

`tools/wgpu/contact_sheet.py`: for every document under `content/materials/standard/`, `convert()` to legacy
v2, `bind()` for wgpu, render the forward path at 192 px under `studio_small_09`, and tile the frames in
roster order (parents first within each family, families in the index's order) into one PNG, five columns,
at most 1024 on a side (the gallery's rule), written to `verification/wgpu/library/contact-sheet.png`. The
tool logs the grid position of every title and the losses of the conversion once, and writes
`contact-sheet.json` beside the picture (title per cell, the command, the environment) so the picture can
be read without the log. No text is drawn into the picture (no font rasteriser in the repo); the JSON is the
legend. The gallery manifest lists the picture with the command.

## Tests

`tests/material/test_material_library.py`:

- Every document under `content/materials/` loads, validates raw and resolved, and resolves to its type; a
  child's parent is `base.material.json` in its own directory; no document under `standard/` is of another type.
- Every standard document converts to legacy v2 without error and the converted document validates and binds
  for wgpu; the losses are exactly the table's dropped list.
- The reverse table passes `check_table` and the conditional set over `alpha_mode` is complete (one entry per
  choice); mutations (a standard parameter neither mapped nor dropped, a drop without a reason) name the
  finding, as `test_material_convert` does for the forward tables.
- Coverage: the factor-bearing parameters of the standard are each set by at least one roster document.
- The document fields: a loaded document carries `title`, `doc`, `provenance`; `validate()` names an empty
  title, a provenance entry missing `source`, a non-list provenance (through `from_data`, `MaterialError`);
  resolution does not inherit a title; conversion does not copy one.
- `index(root)` on the fixtures directory renders the expected table; on `content/materials/standard/` it
  equals the committed `content/materials/README.md` (the `--check` path).
- Provenance: every roster document names at least one source; every metal child's source names Lagarde or
  the author.

`tests/host/test_wgpu_host.py` gains one GPU test: a standard document (gold) renders through the reverse
table and differs from the dielectric parent.

## Acceptance gate

- `uv run pytest tests/material tests/host` green on CI; `tools/generate_material_ui.py --check` current with
  the index; `tools/generate_gallery.py --check` current with the contact sheet listed; `check_docs.py`,
  `check_hygiene.py` clean.
- On the owner's GPU: `uv run tools/wgpu/contact_sheet.py` writes the sheet; it is read by a human (the gate
  the Maya check set) and the PR says what was seen: the metals tell apart, gold is gold, the leaf renders
  (opacity 1 under mask). Not on this host: emission. The wgpu host map marks `emission_color` and
  `emission_intensity` unsupported and `hosts/wgpu/common.wgsl` feeds zero emissive, so the emissive parent
  and the panel render alike, as their dark base colour; the sheet's caption says so, and the emission test
  is the document's (800 nits convert to intensity 8). Emission in wgpu is a host change outside S4a; Maya
  carries emission and the comparison framework's sheet will show it.

## Out of scope

- The texture set and its conventions (S4b, after track E). The four texture parameters' coverage.
- A Maya rendering of the set (the comparison framework's job, track E); a Maya-side `bind()`.
- The getting-started page (the manual's first chapter, after its outline).
- A `field` on the source side of a conversion entry (the normal strength loss, above).
- Titles drawn into the contact sheet (needs a font rasteriser; the JSON legend stands in).

## Amendments made in the build (2026-10-03)

- **The emissive family does not glow in wgpu.** The acceptance gate said "the emissive panel is bright"; it is
  not, and cannot be: the wgpu host map carries no emission parameter (`emission_color` and
  `emission_intensity` are `unsupported` since S3, the host has no emission term). The pair render as their
  dark base colour. The documents are right (800 nits convert to v2 intensity 8, a test says so); the Maya
  shell carries emission, so the comparison framework's Maya sheet will show it. The gallery caption says so.
- **Brushed steel is iron on the sheet**: anisotropy is a loss of the table, as the spec lists; the document
  is the one that sets `specular_anisotropy` for coverage, and renders identically to iron through v2.
- `library.py` also exports `coverage(root, type)` (parameter to the documents setting it) and
  `factor_parameters(type)`, so the coverage test enumerates the schema rather than a hand list; a schema
  addition fails the test until a document sets it. `family_of(path, root)` is shared with the contact sheet.
- `documents_under` sorts the families in `FAMILY_ORDER` then alphabetically, so a new family lands after the
  six without an edit, and the parent before its children; the index and the sheet share the order.
- The index lists the deferred materials (`DEFERRED`) and the table's unstated loss (`UNSTATED_LOSSES`) from
  constants in `library.py`, so the page and the spec cannot drift apart on either.
- The record fields' inner shapes are findings on a raw document only (`_record_findings`); a wrong container
  (a non-string title, a non-list provenance) is `MaterialError` in `from_data`, as `ext` is.
- The contact-sheet legend records the command, the environment, the target type and the losses beside the
  cells, so the picture's provenance is complete without the log.

### After the pre-PR review (2026-10-03)

- A child restates no value its parent sets identically (a test over the roster); `iron` is the one exception,
  titled on purpose as the parent's values named. Four restated values were trimmed (steel's and concrete's
  base colour, ceramic's IOR, the leaf's roughness) and their provenance notes say the value is the parent's.
- Two more unstated losses on the index: `alpha_mode` `blend` lands as opaque in v2 (`has_alpha` stays false;
  one entry per condition), and the standard's `mask` default makes every converted document
  `use_cutout_alpha` true, harmless at opacity 1 with no opacity texture, which is every base-set document.
- `index()` warns when it leaves the losses section out (several types in one library, or no table) instead
  of omitting it in silence. A document directly under the root sorts before the families, as the docstring
  said and the code now does.
- The mask threshold loss Copilot found on #45 (the standard cuts at 0.5, v2 at `opacity_mask_bias` 0.1, the
  table cannot set it) is on the index's unstated-losses list beside the other three.
- The contact sheet refuses an empty library and a missing root (exit 2, logged) before writing anything, takes
  the losses from the table once rather than from the loop, and records the full reproducing command (every
  argument that differs from its default), tested without a GPU.
