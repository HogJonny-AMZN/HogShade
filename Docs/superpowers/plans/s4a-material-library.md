# S4a plan: the base library of materials

**Status:** Proposed. Built on `feat/s4a-material-library` (one PR) after the spec merges; every task is
verified in the table at the end, filled as the work lands.

Spec: [../specs/s4a-material-library.md](../specs/s4a-material-library.md). Test-first: each task's test lands
with it.

## Tasks

- [ ] 1. The document fields: `Document.title`, `doc`, `provenance`; `from_data` reads them and refuses the
      wrong container; `validate()` reports the inner shapes; `resolve()` and `convert()` leave them alone.
      Verify: a fixture with the fields loads and validates; an empty title, a provenance entry without
      `source` and a non-list provenance each produce the named finding or error; a child does not inherit
      its parent's title.
- [ ] 2. The reverse table `hogshade-standard-to-hogshade-legacy-v2.json`. Verify: `check_table` clean; the
      `alpha_mode` condition set complete; the standard's defaults convert to a v2 document that validates and
      binds; the losses are the dropped list; two mutations name their finding.
- [ ] 3. The roster: six parents and sixteen children under `content/materials/standard/<family>/`, each with
      `title`, `doc`, `provenance`. Verify: every document loads, validates raw and resolved, converts and
      binds; the coverage test over the thirteen factor-bearing parameters passes; every document names a
      source.
- [ ] 4. `library.py` (`documents_under`, `index`), the index as the third output of
      `tools/generate_material_ui.py`, `content/materials/README.md` written. Verify: `--check` current;
      `index()` on a fixture directory renders the expected table; a broken document makes `index()` raise.
- [ ] 5. `tools/wgpu/contact_sheet.py`, the picture and its JSON legend under `verification/wgpu/library/`,
      the gallery manifest row, one GPU test (gold differs from the dielectric parent). Verify: the sheet is
      at most 1024 on a side; `generate_gallery.py --check` current; the picture read by a human and what was
      seen written in the PR.
- [ ] 6. Docs: this plan ticked with the verification table; the spec's amendments; the design's status if it
      moves; the board (S4a to Now, then struck); the glossary (Provenance); `Docs/README.md`; the handoff;
      the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| 6 | |
