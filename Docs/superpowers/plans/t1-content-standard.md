# T1 plan: the content standard and its check

**Status:** Accepted. Built 2026-10-03 on `feat/t1-content-standard` (one PR, stacked on the spec's #50); every
task verified in the table at the end; the local review ran before the PR opened.

Spec: [../specs/t1-content-standard.md](../specs/t1-content-standard.md). Test-first: each task's test lands
with it.

## Tasks

- [x] 1. `hogshade/material/textures.py`: `PREFIX`, `SUFFIXES`, `PACKED`, `parse_name`, `preset_for`,
      `check_suffixes` (the spec said `check_table`; the package already exports one). Verify: the table covers the schema's fourteen texturable parameters exactly; the
      mutations and the name cases in the spec each produce the named result.
- [x] 2. The sidecar rules and `tools/check_content.py` (name, sidecar, binding, table, licence) with
      `tests/test_check_content.py` on a scratch corpus and on the repository; the CI step "Content". Verify:
      each finding in the spec is produced by its case; the repository passes.
- [x] 3. `generate("content")` and the fourth output of `tools/generate_material_ui.py`: the standard's
      suffix, packed and sidecar tables between markers. Verify: `--check` current; a table edit in
      `textures.py` makes `--check` stale until `--write`.
- [x] 4. `Docs/standards/content.md` written in the spec's order with the why on every rule; `AGENTS.md`,
      `Docs/README.md`, `.github/copilot-instructions.md` point at it; glossary rows. Verify:
      `check_docs.py` clean; a human read.
- [x] 5. Docs: this plan ticked with its table; the spec's amendments; the design's status if it moves; the
      board (T1 to Now, then struck); the handoff; the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | `hogshade/material/textures.py`: `PREFIX`, fourteen `SUFFIXES` (one per texturable parameter of the standard, held to the schema by `check_suffixes`), three `PACKED`, `NAME_RE`, `parse_name`, `preset_for`, `parameter_of`, `check_sidecar`; `test_material_textures.py`: the table covers the schema exactly (14), three mutations name their finding (a parameter without a suffix, a wrong colour space and a duplicate, a suffix on a parameter with no colour space), the name cases of the spec accept and reject as written, the presets, the sidecar rules (ten cases) |
| 2 | `tools/check_content.py` with five checks and the CI step "Content"; `tests/test_check_content.py`: the repository passes (vacuously for files, really for the table), a clean scratch set, a misnamed file and an unknown suffix, a missing and a malformed sidecar, the sidecar rules reaching the check (a normal without its convention, a contradicting colour space, a resolution not matching the PNG header), a cooked PNG, a set without `LICENSE.md`, six binding findings (a `_N` on `base_color`, a `_BC` on `emission_color` with its sidecar's colour space against the schema, a `_ORM` bound directly, a missing file, a name outside the grammar) |
| 3 | `generate("content")` renders the suffix table, the packed table and the sidecar line from `textures.py`; `tools/generate_material_ui.py` writes them between `CONTENT_BEGIN`/`CONTENT_END` in the standard as its fourth output and `--check` diffs them; `test_the_tool_check_is_clean` and `test_the_tool_check_covers_the_index` cover the tool; the standard's tables are current |
| 4 | `Docs/standards/content.md` in the spec's order (what for, textures: name, sidecar, authoring and runtime sets, sources, tangents and detail maps; materials; lighting; rendering and capture; the checks table), the owner's two answers named; `AGENTS.md` (reading order and topic table), `Docs/README.md` (standards line and the task table), `.github/copilot-instructions.md` (item 8), five glossary rows (Sidecar, Preset, Authoring set, Runtime set, Detail map); `.gitattributes` tracks PNG and TIFF under both content roots in LFS (`git check-attr` on a family path says `lfs`); `check_docs.py` clean |
| 5 | This table; the spec's amendments; board; docs map; handoff; journal |

Totals: `uv run pytest -o addopts= -q` 465 passed on the owner's machine (after the review rounds).
