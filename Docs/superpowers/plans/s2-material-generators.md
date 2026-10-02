# S2 plan: the generators

**Status:** Proposed. Runs after the owner approves the spec; one PR. Tick a task only when its
verification ran; `/local-review diff` runs before the PR opens (the S1 lesson).

Spec: [../specs/s2-material-generators.md](../specs/s2-material-generators.md). Test-first: each task's
test lands with it.

## Tasks

- [ ] 1. The host map `hogshade/material/hosts/maya_dx11.json`, written from the shell as it is: every
      name, label, order, group, map and flag the shell declares today, nothing the schema already
      knows. `check_host_map()` in `generators.py` with the rules of the spec. Verify: the shipped map
      passes; five mutated maps (missing parameter, unknown parameter, duplicate order, duplicate name,
      a `default` key) each produce the named finding; `pyproject.toml` package data lists `hosts/*.json`.
- [ ] 2. `generate("maya_dx11")`: the maps, then the groups, explicit declarations per the spec's table.
      Verify: a test parses the generated text with the S1 union parser and asserts the parameter set,
      every decoded default (colours, scalars, bools, enum indices, the flip signs) and every emitted slider
      range (`float` and `int`; the HLSL carries no range for a colour or a vector) equal the schema's.
- [ ] 3. The shell: markers added, the four macros and their invocations replaced by the generated
      block, the host-only parameters (`shadingModel`, `linearSpaceLighting`, `gammaCorrectionValue`)
      moved to a hand-written "display and model" section above the markers. Verify: `generate()` equals
      the block byte for byte; every identifier the body references is declared (test); the S1 union
      test, now a group classification, still passes; `tools/build_shaders.py --check --require-compilers`
      clean.
- [ ] 4. `generate("docs")` and `Docs/reference/material-types.md`; the `Docs/README.md` row. Verify:
      the committed file equals the generator's output; every parameter of every type appears;
      `check_docs.py` clean.
- [ ] 5. `tools/generate_material_ui.py` with `--check` and `--write`, the CI step after the shader
      build. Verify: `--check` clean; a hand edit inside the markers makes it exit 1 with a diff (shown
      in the PR); the CI run green.
- [ ] 6. The Maya run: `tools/maya/ibl_check.py` with the regenerated shell on the `hogshade_maya_gui`
      worker (BATS if the orchestrator runs, else a human launch), pictures compared to the previous
      check. Verify: the compile log clean, the pictures identical, the attribute editor's groups as
      before; stated in the PR with the artifact path.
- [ ] 7. Docs: this plan ticked with a verification table; the spec's status and amendments; the board
      (the S2 row to Now, then struck with the PR); the glossary if a noun is new ("host map"); the
      handoff; the journal. Verify: `tools/check_docs.py` clean.
