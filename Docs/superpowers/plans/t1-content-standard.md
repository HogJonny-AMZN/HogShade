# T1 plan: the content standard and its check

**Status:** Proposed. Built on `feat/t1-content-standard` (one PR) after the spec merges; every task verified
in the table at the end, filled as the work lands.

Spec: [../specs/t1-content-standard.md](../specs/t1-content-standard.md). Test-first: each task's test lands
with it.

## Tasks

- [ ] 1. `hogshade/material/textures.py`: `PREFIX`, `SUFFIXES`, `PACKED`, `parse_name`, `preset_for`,
      `check_table`. Verify: the table covers the schema's fourteen texturable parameters exactly; the
      mutations and the name cases in the spec each produce the named result.
- [ ] 2. The sidecar rules and `tools/check_content.py` (name, sidecar, binding, table, licence) with
      `tests/test_check_content.py` on a scratch corpus and on the repository; the CI step "Content". Verify:
      each finding in the spec is produced by its case; the repository passes.
- [ ] 3. `generate("content")` and the fourth output of `tools/generate_material_ui.py`: the standard's
      suffix, packed and sidecar tables between markers. Verify: `--check` current; a table edit in
      `textures.py` makes `--check` stale until `--write`.
- [ ] 4. `Docs/standards/content.md` written in the spec's order with the why on every rule; `AGENTS.md`,
      `Docs/README.md`, `.github/copilot-instructions.md` point at it; glossary rows. Verify:
      `check_docs.py` clean; a human read.
- [ ] 5. Docs: this plan ticked with its table; the spec's amendments; the design's status if it moves; the
      board (T1 to Now, then struck); the handoff; the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
