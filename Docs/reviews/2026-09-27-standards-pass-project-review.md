# Project review for the standards pass

**Status:** Accepted (the review ran 2026-09-27; the fixes it lists were applied in the standards-pass PR, and this file says which)
**Mode:** `/local-review project`, a fresh-eyes subagent against `AGENTS.md`, the DoD, `core/manifest.toml`, the host READMEs and the ruff config
**Scope:** `core/`, `hogshade/`, `hosts/` (not `generated/`), `tools/`, `tests/`; the hygiene grep; `build_shaders.py --check`

## Scores

| Metric | Score | Notes |
| --- | :---: | --- |
| Design | 8/10 | The two-halves interface is clean and every host uses it the same way; `EnvironmentSamples` as numbers keeps the models pure |
| Architecture | 8/10 | Boundaries hold and are asserted in tests; one leak, `reference/legacy_v1.py` importing privates from `legacy_v2` |
| Readability | 8/10 | Headers explain intent and history; stale "switch" wording survived the if-chain change |
| Maintainability | 7/10 | Every check runs standalone and as a job; hand-kept mirrors each have a test; one dead parameter in the wgpu host |
| Performance | 7/10 | The cook has a numba rung; the Maya log rewrites on every append on purpose |
| Security | 7/10 | Path climbing refused; `submit.py` interpolates JSON into a raw literal; machine-path defaults contradict `tools/README.md` |
| Error handling | 8/10 | Specific exceptions with context; broad catches only where a DCC's own errors are the point |
| Logging | 6/10 | Seven modules declare `_LOGGER` and never use it; two Maya helpers print where a `Log` exists |
| Coding standards | 6/10 | Ruff clean, absolute imports, no bare except, no `os.path`; module headers missing on seven tools and both package inits; `Package:` line inconsistent |
| Core contract | 6/10 | Prefix rule enforced; `environment.wgsl` and `lambert.wgsl` have no twin and no GPU test; the "single return" rule overstates what FXC rejects; one unused constant |

Verdict: needs work, lowest 6/10. Hard findings: `proto_python` in the generated orchestrator profile (board G1, the owner's call); the grep pattern quoted in two skills matches itself (exempt by intent, now said). `build_shaders.py --check`: artifacts current.

## The ten fixes, and what happened to each

| # | Fix | Effort | Outcome in the standards pass |
| --- | --- | --- | --- |
| 1 | Strip `proto_python` from the generated profile, or record "leave while private" | 15 min | **Left to the owner** (G1); not stripped without a decision. The match is now an allowlisted, printed exception in `tools/check_hygiene.py`, which replaced the ad hoc grep after Copilot found the grep flagging the documents that quoted it |
| 2 | `environment.wgsl`: NumPy twin and GPU test | 60 min | **Done** |
| 3 | The FXC rule in the skill and rubric: a `switch` on a texture-derived value is what fxc rejects; a `switch` on a uniform and early returns are fine | 15 min | **Done**, and in `Docs/standards/wgsl.md` |
| 4 | Module headers on `tools/*.py` and the two package inits; `Package:` in dotted form | 40 min | **Done** |
| 5 | Unused `_LOGGER` in seven modules: keep-and-use or drop, and the rule on the standards page | 20 min | **Done**: dropped where nothing logs; the standard says a module declares the logger when it logs |
| 6 | "switch" wording in `constants.wgsl`, the constants test name, `hosts/README.md`; the unused `HOGSHADE_IRRADIANCE_OVER_PI` | 15 min | **Done** |
| 7 | `lambert.wgsl`: twin and GPU test | 40 min | **Done** |
| 8 | Shared reference helpers into `hogshade/reference/_common.py` | 20 min | **Done** |
| 9 | Maya helpers append to the `Log` instead of printing; `Path.open`; the dead parameter | 20 min | **Done** |
| 10 | `submit.py`: parameters through `json.dumps` and `repr`, not a raw literal | 20 min | **Done** |

## What is good and should not change

- The core contract is mechanised: the name check in `build_shaders.py`, `--check` in CI with
  `--require-compilers`, the binding assertions in `test_build.py`, `test_constants`, `test_layout`,
  the frame-layout test.
- Legacy model headers list kept quirks and numbered deviations; the twins read as the specification.
- `EnvironmentSamples` as plain numbers; each model owning its LUT coordinates; the if-chain with
  its rationale in the header.
- The Maya checks: incremental log, `output_dir` refusing climbs, the red Lambert control sphere,
  one script serving both the launcher and the orchestrator.
- `check_docs.py` explaining the failure each check exists for; the DoD's "do not add a tier before
  its trigger".
- Every module's `__main__` smoke block.
