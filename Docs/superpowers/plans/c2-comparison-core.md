# C-2 plan: the comparison core

**Status:** Proposed. Spec: [../specs/c2-comparison-core.md](../specs/c2-comparison-core.md). Test-first: each task's
tests land with it. The CPU tests run on CI; the GPU tests run on the owner's machine and are skipped on CI, which the
PR states. A significant increment: `/local-review diff` before asking for a merge.

## Tasks

- [ ] 1. **The request** (`hogshade/compare/request.py`, `tests/compare/test_request.py`): `CaptureRequest`, canonical
      JSON, the host-free content hash, `RequestError` naming the field. Verify: round trip; the same request with two
      hosts hashes equal; a changed field changes the hash; every field's refusal (a size not a multiple of 32, a
      non-finite number, an unknown mesh name, an `up` parallel to the view direction).
- [ ] 2. **The capture set** (`hogshade/compare/captureset.py`, `tests/compare/test_captureset.py`): roles, `Manifest`,
      `write` / `read` over `hogshade.ibl.imageio` (EXR, PNG). Verify: write then read gives the same arrays; a missing
      role, mismatched sizes, a request whose hash differs from the manifest's, and a level that overstates are each
      refused with a message naming the role.
- [ ] 3. **The metrics** (`hogshade/compare/metrics.py`, `tests/compare/test_metrics.py`): absolute and relative error,
      PSNR, SSIM, coverage overlap, `fraction_within`. Verify: each against a value worked by hand on a small array;
      identical images give PSNR infinity (a named constant, not a division by zero) and SSIM 1; an empty mask is a
      refusal, not a mean of nothing.
- [ ] 4. **The verdict and the accepted file** (`hogshade/compare/verdict.py`, `tests/compare/test_verdict.py`):
      `Verdict`, `Threshold`, `judge`, `accepted.json` read and write. Verify: pass, needs-review and fail at, inside
      and outside the bounds in both directions; an accepted difference holds only while both hashes match.
- [ ] 5. **The case table and the report** (`hogshade/compare/cases.py`, `report.py`, `verification/cases/`,
      `tests/compare/test_cases.py`, `test_report.py`): schemas, `expect: fail` controls, the report with `control_ok`.
      Verify: a malformed case is refused with its file and field; a stored report validates; a control that passes
      makes the run fail.
- [ ] 6. **The host maps the request** (`hogshade/wgpu_host.py`, `tests/host/`): `Scene` takes an optional explicit
      camera; `view_proj` uses it; the existing orbit scenes render the same bytes (a test pins this). Verify: the
      default scene's frame bytes are unchanged; an explicit camera at the orbit's eye gives the same `view_proj`.
- [ ] 7. **The wgpu adapter** (`hogshade/compare/adapters/wgpu.py`, GPU test): `capture(request, out_dir)`; refuses
      near/far other than the host's, a rotation other than 0, and any view but `"preview"`, each by name. Verify (GPU):
      a set is written, reads back, says L2p; the three refusals.
- [ ] 8. **The oracles and their controls** (`hogshade/compare/oracles.py`, `tests/compare/test_oracles.py`): the
      quad-sphere texel and normal checks moved out of the host test, the camera built from the request. Verify (CPU):
      a synthetic frame equal to the expected image passes, the same frame V-flipped fails, a flipped normal channel
      fails; (GPU) the two cases reproduce the existing probes' agreement and their controls fail.
- [ ] 9. **The command and CI** (`tools/compare.py`, `.github/workflows/tests.yml`, `.gitignore` for `captures/`):
      `validate`, `run`, `list`; `validate` as a CI step. Verify: `validate` exits 0 on the tree and 1 on a broken
      case; `run` without an adapter exits with a clear message and a distinct code (`--allow-skips` for a headless
      runner); on the owner's machine `run` passes every oracle case and every control fails.
- [ ] 10. **Docs**: the spec accepted with *What the build found*, this plan ticked, the board, the docs map, the
      README's verification section, the handoff, the journal, the knowledge file for the toolchain if it changes.
      Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 to 10 | filled in as each lands |
