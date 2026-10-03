# S4a plan: the base library of materials

**Status:** Accepted. Built 2026-10-03 on `feat/s4a-material-library` (one PR, stacked on the spec's #45); every
task verified in the table at the end; the local review ran before the PR opened.

Spec: [../specs/s4a-material-library.md](../specs/s4a-material-library.md). Test-first: each task's test lands
with it.

## Tasks

- [x] 1. The document fields: `Document.title`, `doc`, `provenance`; `from_data` reads them and refuses the
      wrong container; `validate()` reports the inner shapes; `resolve()` and `convert()` leave them alone.
      Verify: a fixture with the fields loads and validates; an empty title, a provenance entry without
      `source` and a non-list provenance each produce the named finding or error; a child does not inherit
      its parent's title.
- [x] 2. The reverse table `hogshade-standard-to-hogshade-legacy-v2.json`. Verify: `check_table` clean; the
      `alpha_mode` condition set complete; the standard's defaults convert to a v2 document that validates and
      binds; the losses are the dropped list; two mutations name their finding.
- [x] 3. The roster: six parents and sixteen children under `content/materials/standard/<family>/`, each with
      `title`, `doc`, `provenance`. Verify: every document loads, validates raw and resolved, converts and
      binds; the coverage test over the thirteen factor-bearing parameters passes; every document names a
      source.
- [x] 4. `library.py` (`documents_under`, `index`), the index as the third output of
      `tools/generate_material_ui.py`, `content/materials/README.md` written. Verify: `--check` current;
      `index()` on a fixture directory renders the expected table; a broken document makes `index()` raise.
- [x] 5. `tools/wgpu/contact_sheet.py`, the picture and its JSON legend under `verification/wgpu/library/`,
      the gallery manifest row, one GPU test (gold differs from the dielectric parent). Verify: the sheet is
      at most 1024 on a side; `generate_gallery.py --check` current; the picture read by a human and what was
      seen written in the PR.
- [x] 6. Docs: this plan ticked with the verification table; the spec's amendments; the design's status if it
      moves; the board (S4a to Now, then struck); the glossary (Provenance); `Docs/README.md`; the handoff;
      the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | `Document.title/doc/provenance`; `from_data` refuses a non-string title or doc and a non-list provenance (`MaterialError`); `validate()` names an empty title, a provenance entry without `note`, a non-object entry, an unknown key; a child does not inherit its parent's title and `Resolved` has no such field; `convert()` leaves them off (`test_material_library.py`, the record-field tests) |
| 2 | `hogshade-standard-to-hogshade-legacy-v2.json`: 15 map entries, 4 drops; `check_table` clean; `alpha_mode` fans out over its three choices; the standard's defaults convert to a v2 document that validates and binds; losses are the dropped list; a forgotten parameter and a reasonless drop each name their finding; `test_four_tables_ship` |
| 3 | 22 documents under `content/materials/standard/`: every one loads, validates raw and resolved, converts and binds (parametrised, 22 cases); coverage over the 13 factor-bearing standard parameters, none uncovered; every document has a title, a doc and a source; the metal children name Lagarde or the author; gold resolves to `[1.0, 0.77, 0.34]` with the parent's metalness; the cutout parent converts to `use_cutout_alpha` true; the panel's 800 nits convert to intensity 8 |
| 4 | `library.py`: `documents_under` (families in order, parents first, verified on a scratch tree), `index` (refuses a library with a finding, names the deferred materials and the table's losses), `coverage`; the index is `tools/generate_material_ui.py`'s third output, `content/materials/README.md` written and `--check` current; the package exports `documents_under`, `index`, `coverage` |
| 5 | `tools/wgpu/contact_sheet.py` on the owner's GPU: 22 cells at 192 px, 960x960, 1.8 s, `verification/wgpu/library/contact-sheet.png` (509 KB) and `contact-sheet.json`; the gallery row and `Docs/gallery.md` regenerated; the GPU test `test_a_standard_document_renders_through_the_reverse_table` (gold differs from the dielectric parent and is warmer than blue). Read by a human: the metals tell apart (gold, copper, silver, chrome, aluminium), the lacquer is red, the leaf is green, the rubber is black; the emissive pair do not glow, because the wgpu host has no emission term (an amendment, not a defect of the library) |
| 6 | This table; the spec's amendments; board (S4a to Now with its PR); docs map; handoff; journal; `check_docs.py` clean |

Totals: `uv run pytest tests/material` 264 passed; the full suite on the owner's GPU, see the PR.
