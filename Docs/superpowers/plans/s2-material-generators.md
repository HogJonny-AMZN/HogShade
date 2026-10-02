# S2 plan: the generators

**Status:** Accepted. Built 2026-10-01 on `feat/s2-material-generators` (one PR) after #34 approved the spec;
all seven tasks verified; task 6 (the GUI Maya run) was met after the merge, once the owner restarted the
orchestrator (the follow-up PR), see the table.

Spec: [../specs/s2-material-generators.md](../specs/s2-material-generators.md). Test-first: each task's
test lands with it.

## Tasks

- [x] 1. The host map `hogshade/material/hosts/maya_dx11.json`, written from the shell as it is: every
      name, label, order, group, map and flag the shell declares today, nothing the schema already
      knows. `check_host_map()` in `generators.py` with the rules of the spec. Verify: the shipped map
      passes; five mutated maps (missing parameter, unknown parameter, duplicate order, duplicate name,
      a `default` key) each produce the named finding; `pyproject.toml` package data lists `hosts/*.json`.
- [x] 2. `generate("maya_dx11")`: the maps, then the groups, explicit declarations per the spec's table.
      Verify: a test parses the generated text with the S1 union parser and asserts the parameter set,
      every decoded default (colours, scalars, bools, enum indices, the flip signs) and every emitted slider
      range (`float` and `int`; the HLSL carries no range for a colour or a vector) equal the schema's.
- [x] 3. The shell: markers added, the four macros and their invocations replaced by the generated
      block, the host-only parameters (`shadingModel`, `linearSpaceLighting`, `gammaCorrectionValue`)
      moved to a hand-written "display and model" section above the markers. Verify: `generate()` equals
      the block byte for byte; every identifier the body references is declared (test); the S1 union
      test, now a group classification, still passes; `tools/build_shaders.py --check --require-compilers`
      clean.
- [x] 4. `generate("docs")` and `Docs/reference/material-types.md`; the `Docs/README.md` row. Verify:
      the committed file equals the generator's output; every parameter of every type appears;
      `check_docs.py` clean.
- [x] 5. `tools/generate_material_ui.py` with `--check` and `--write`, the CI step after the shader
      build. Verify: `--check` clean; a hand edit inside the markers makes it exit 1 with a diff (shown
      in the PR); the CI run green.
- [x] 6. The Maya run: `tools/maya/ibl_check.py` with the regenerated shell on the `hogshade_maya_gui`
      worker (BATS if the orchestrator runs, else a human launch), pictures compared to the previous
      check. Verify: the compile log clean, the pictures identical, the attribute editor's groups as
      before; stated in the PR with the artifact path.
- [x] 7. Docs: this plan ticked with a verification table; the spec's status and amendments; the board
      (the S2 row to Now, then struck with the PR); the glossary if a noun is new ("host map"); the
      handoff; the journal. Verify: `tools/check_docs.py` clean.

## Verification, 2026-10-01

| Task | Ran |
| --- | --- |
| 1 | `hosts/maya_dx11.json`: 38 entries, the legacy union; `check_host_map` clean; seven mutated maps each name their finding (`test_material_generate.py`); package data `hosts/*.json` in the wheel test |
| 2 | `test_generated_block_declares_the_schema_values`: the block parsed back, every decoded default (colours, scalars, bools, enum indices, flip signs) and every emitted float and int range equal the schema's |
| 3 | The shell: environment section moved above, a hand-written "display and model" section (`shadingModel`, `linearSpaceLighting`, `gammaCorrectionValue`), the markers, the four macros gone (`test_shell_has_no_ui_macros_left`), `shadowMultiplier` an explicit declaration in its Shadows group; four attributes change UI group (the three parallax sliders the slider macro had put in Material Properties, and `shadowMultiplier`), settled as intentional in the spec's amendments; `generate()` equals the block byte for byte; every host-map identifier is declared and read by the body; the S1 union test now parses declarations and still passes; `tools/build_shaders.py --check --require-compilers` clean; `fxc /T fx_5_0` compiles the regenerated effect (909 965 bytes) and master's (909 849) with the same warnings |
| 4 | `Docs/reference/material-types.md` equals `generate("docs")`; every parameter of every type listed; `check_docs.py` clean (68 files) |
| 5 | `tools/generate_material_ui.py --check` clean; a hand edit inside the markers (0.5 to 0.55 on `materialRoughness`) exits 1 with the diff; the CI step after the shader build |
| 6 | **Met on 2026-10-01 after the merge of #35**, once the owner restarted the orchestrator with a fresh GUI worker: the IBL check job completed (`RESULT: OK`, `Main` technique, shader load 28.6 s) and wrote the pictures under `verification/maya-2026/ibl-check/studio_small_09/` (committed in the follow-up PR as the new baseline). The pictures differ from the 2026-09-27 baseline on 5 to 8 percent of pixels (silhouettes and highlights, mean a quarter of a grey level), so a third job rendered **master's shell in the same session**: its pictures and the regenerated shell's are pixel-identical (max 0 on `main.png`, max 1 on two debug views), and two runs of one shell in one session are identical too. The difference from September is between Maya sessions, not between shells. Before the restart: The IBL check job on the resident `hogshade_maya_gui` worker crashed the worker during the shader load (job `1785f4a7`, 22:22:46; the check log stops after "log is incremental", the worker state CRASHED, no restart). The orchestrator's worker is not mine to restart and a Maya beside it is forbidden, so the evidence came from the headless `hogshade_maya` worker instead: one job loaded master's shell and the regenerated shell in the same session; both report the `Main` technique, the same 1021 user attributes and the same defaults and nice names on every attribute. A parse failure would have shown there. The viewport pictures still need a GUI run after the worker is restarted (owner) |
| 7 | This table; the spec's amendments; board, docs map, glossary, handoff, journal; `check_docs.py` clean |

Totals: `uv run pytest tests/material` 180 passed; the full suite 335 passed on the owner's GPU.

| Review | Ran |
| --- | --- |
| Pre-PR `/local-review diff` | Design 7, Architecture 8, Readability 8, Maintainability 6, Security 8, Error handling 6, Logging 7, Coding standards 8; needs-work. It refuted "only `shadowMultiplier` moved": the slider macro had hard-coded `Material Properties`, so three parallax sliders move too (recorded as intentional). Fixed before the PR opened: reserved-word and label rules on the map, a non-object map as `MaterialError`, whole-line CRLF-tolerant markers matched exactly once, the tool's exit 2 on a `MaterialError`, LF on write, the identifier test's dead anchor and stale allowance |
