# S1 plan: the schema files and `hogshade.material`

**Status:** Accepted. Done 2026-09-27 on `feat/s1-material-schema` (one PR, open for the owner's merge). Every task's
verification ran; the notes are under the tasks.

Spec: [../specs/s1-material-schema.md](../specs/s1-material-schema.md). Test-first: each task's test
lands with it.

## Tasks

- [x] 1. `hogshade/material/types.py`: the dataclasses (`ParameterDef`, `MaterialType`, `Document`,
      `Resolved`, `Finding`, `Loss`, `MaterialError`), typed and documented. Verify: `ruff` clean;
      the import test (`MaterialX` and `PySide6` absent after import) passes.
- [x] 2. `schema.py`: read a material-type file from package data through `importlib.resources`;
      the meta-check of its shape (every field, types, groups, the `enabled` rule, migrations
      list); a registry by name. Verify: a test loads each shipped file and asserts the
      meta-check finds nothing; a fixture with a missing field and one with an unknown field
      each produce the named finding.
- [x] 3. The four schema files at version 1, with the parameter lists the spec fixes: the standard
      (OpenPBR names plus `alpha_mode` and the four `surface` opt-ins), legacy v2 and v1 typed as
      the spec's tables list them, lambert. Verify: task 2's test over the real files; a test that
      the standard's parameter names are exactly the spec's list; a test that each legacy type's
      set equals the union of its model's `Material` and `Samples` fields plus the shell's flags.
- [x] 4. `document.py`: `load()` with the path rules (`PurePosixPath` normalisation, `..` and
      absolute rejected, escape of the root rejected), the version check, migrations applied.
      Verify: the good fixtures load raw; each broken path fixture raises `MaterialError` naming the
      path; the newer-version fixture raises; the fake version-2 rename migrates.
- [x] 5. `validate.py`: the raw-document rules (unknown key, type, range and `soft`, colour space,
      `blend` only with both and only on colour or slider, overridable, paths) and the resolved
      rules (completeness, `alpha_mode` against an opacity source). Verify: one test per rule on the
      broken fixtures, each asserting the finding's `parameter`.
- [x] 6. `resolve.py`: the parent chain through `load`, cycle and cross-type rejection, values child
      over parent, defaults, `ext` merged per namespace key, `chain` recorded. Verify: the grandchild
      fixture resolves with every parameter and the expected winners; the cycle and cross-type
      fixtures raise.
- [x] 7. The three conversion tables and `convert.py` with the five transforms and their payloads
      (`by`, `range`, `value`) and the `field` target. Verify: the
      coverage test (every source parameter in `map` or `dropped`, every `to` in the target); v2 to
      standard on a fixture yields the mapped values, the `Loss` list and a document that validates
      against the standard.
- [x] 8. `pyproject.toml` package data; `uv build`; a test that the wheel contains the seven files.
      Verify: the wheel listing in the PR.
- [x] 9. The human run: `mayapy -c "import hogshade.material as m; print(m.types())"` (the `types()` contract) on Maya 2026
      lists the four types. Verify: the output pasted in the PR; if `mayapy` cannot import numpy,
      say so and record it as the first item of S2's environment work.
- [x] 10. Docs: `Docs/README.md`'s specs and plans table gains the S1 row; the board's Next row
      moves to Now and then is struck with the PR; the glossary gains any noun S1 introduced;
      `Docs/handoffs/CURRENT.md`; the journal. Verify: `tools/check_docs.py` clean.

## Verification, 2026-09-27

| Task | Ran |
| --- | --- |
| 1 | `ruff check` clean; `tests/material/test_material_package.py::test_import_pulls_in_no_graphics_stack` (a subprocess import; `MaterialX`, `PySide6` and `numpy` all absent afterwards: the library is standard-library only) |
| 2 | `test_material_schema.py`: every shipped file passes the meta-check; a missing field, an unknown field, a group not declared, a default outside its range, a texture with a default or without a colour space, `strength` off a normal map, the `<group>_enabled` rule and a malformed migration each produce the named finding |
| 3 | The standard's names equal the spec's list (17); the legacy union test parses the `Material` and `Samples` structs of `core/models/legacy_v{1,2}.wgsl` and the material, normal, v1 and parallax blocks and the maps of `hosts/maya_dx11/hogshade.fx`, with an explicit alias table and a derived set, and asserts equality with each legacy type's parameter set (30 for v2, 22 for v1); a shell parameter without a schema name fails |
| 4 | `test_material_document.py`: the good fixtures load raw; `..`, five absolute spellings, an escape of a given root, a newer version, a missing file, bad JSON and malformed documents raise `MaterialError` naming the path; a version-1 document under a fake version-2 type migrates through `rename` and `remove` |
| 5 | `test_material_validate.py`: eleven broken fixtures, one rule each, asserting the finding's `parameter`; soft ranges, int against float, colour arity, `strength` bounds, blend on a vector widget and overridable through the fake-type fixture; the resolved rules (completeness, mask against a constant opacity) |
| 6 | `test_material_resolve.py`: the grandchild resolves with all 17 parameters, the expected winners, `ext` merged per namespace, `chain` child first; the cycle and cross-type fixtures raise |
| 7 | `test_material_convert.py`: the coverage rule on the three shipped tables and on tables mutated to forget, duplicate, mis-target and mis-pay; the five transforms on scalars and triples; v2 brick to standard yields the mapped values, the losses and a document that validates raw and resolved |
| 8 | `[tool.setuptools.package-data]` with the quoted key; `test_wheel_contains_the_schema_files` runs `uv build --wheel` and lists the seven files in the wheel |
| 9 | `mayapy.exe -c "import hogshade.material as m; print(m.types())"` on Maya 2026 (Python 3.11.9) printed the four types and their parameter counts `[3, 22, 30, 17]`; numpy was not needed |
| 10 | `uv run tools/check_docs.py`: 63 files, no drift; `check_hygiene.py` clean |

Totals: `uv run pytest tests/material` 108 passed; the full suite 263 passed on the owner's GPU.
