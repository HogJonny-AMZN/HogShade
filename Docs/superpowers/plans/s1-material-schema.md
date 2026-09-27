# S1 plan: the schema files and `hogshade.material`

**Status:** Proposed. Runs after the owner approves the spec; one PR. Tick a task only when its
verification ran.

Spec: [../specs/s1-material-schema.md](../specs/s1-material-schema.md). Test-first: each task's test
lands with it.

## Tasks

- [ ] 1. `hogshade/material/types.py`: the dataclasses (`ParameterDef`, `MaterialType`, `Document`,
      `Resolved`, `Finding`, `Loss`, `MaterialError`), typed and documented. Verify: `ruff` clean;
      the import test (`MaterialX` and `PySide6` absent after import) passes.
- [ ] 2. `schema.py`: read a material-type file from package data through `importlib.resources`;
      the meta-check of its shape (every field, types, groups, the `enabled` rule, migrations
      list); a registry by name. Verify: a test loads each shipped file and asserts the
      meta-check finds nothing; a fixture with a missing field and one with an unknown field
      each produce the named finding.
- [ ] 3. The four schema files at version 1, with the parameter lists the spec fixes: the standard
      (OpenPBR names plus `alpha_mode` and the four `surface` opt-ins), legacy v2 and v1 as the
      Maya shell names them, lambert. Verify: task 2's test over the real files; a test that the
      standard's parameter names are exactly the spec's list.
- [ ] 4. `document.py`: `load()` with the path rules (`PurePosixPath` normalisation, `..` and
      absolute rejected, escape of the root rejected), the version check, migrations applied.
      Verify: the good fixtures load raw; each broken path fixture raises `MaterialError` naming the
      path; the newer-version fixture raises; the fake version-2 rename migrates.
- [ ] 5. `validate.py`: the raw-document rules (unknown key, type, range and `soft`, colour space,
      `blend` only with both and only on colour or slider, overridable, paths) and the resolved
      rules (completeness, `alpha_mode` against an opacity source). Verify: one test per rule on the
      broken fixtures, each asserting the finding's `parameter`.
- [ ] 6. `resolve.py`: the parent chain through `load`, cycle and cross-type rejection, values child
      over parent, defaults, `ext` merged per namespace key, `chain` recorded. Verify: the grandchild
      fixture resolves with every parameter and the expected winners; the cycle and cross-type
      fixtures raise.
- [ ] 7. The three conversion tables and `convert.py` with the five transforms. Verify: the
      coverage test (every source parameter in `map` or `dropped`, every `to` in the target); v2 to
      standard on a fixture yields the mapped values, the `Loss` list and a document that validates
      against the standard.
- [ ] 8. `pyproject.toml` package data; `uv build`; a test that the wheel contains the seven files.
      Verify: the wheel listing in the PR.
- [ ] 9. The human run: `mayapy -c "import hogshade.material as m; print(m.types())"` on Maya 2026
      lists the four types. Verify: the output pasted in the PR; if `mayapy` cannot import numpy,
      say so and record it as the first item of S2's environment work.
- [ ] 10. Docs: `Docs/README.md`'s specs and plans table gains the S1 row; the board's Next row
      moves to Now and then is struck with the PR; the glossary gains any noun S1 introduced;
      `Docs/handoffs/CURRENT.md`; the journal. Verify: `tools/check_docs.py` clean.
