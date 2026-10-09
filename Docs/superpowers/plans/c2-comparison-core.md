# C-2 plan: the comparison core

**Status:** Accepted (owner, 2026-10-08: "go"); built the same day on `feat/c2-comparison-core` (#76), every task ticked. Spec: [../specs/c2-comparison-core.md](../specs/c2-comparison-core.md). Test-first: each task's
tests land with it. The CPU tests run on CI; the GPU tests run on the owner's machine and are skipped on CI, which the
PR states. A significant increment: `/local-review diff` before asking for a merge.

## Tasks

- [x] 1. **The request** (`hogshade/compare/request.py`, `tests/compare/test_request.py`): `CaptureRequest` (host-neutral),
      `meshes.py` (the canonical ids), canonical JSON, the content hash, `RequestError` naming the field. Verify: round
      trip; a request carrying a `host` field is refused as unknown; a changed field changes the hash; every field's
      refusal (a size not a multiple of 32, a non-finite number, an unknown mesh id, an `up` parallel to the view
      direction).
- [x] 2. **The capture set** (`hogshade/compare/captureset.py`, `tests/compare/test_captureset.py`): roles, `Manifest`,
      `write` / `read`, EXR through `hogshade.ibl.imageio` (`read_exr_rgb`, `write_exr_rgb`) and PNG through
      `hogshade.texture_cook.png` (`read_png`, `write_png`: uint8 grayscale and RGB, so the one-channel coverage mask and
      the display picture both round-trip; a grayscale PNG reads back as (H, W, 1), checked 2026-10-08; `imageio`'s PNG writer is RGB-only and there is no reader there). Verify: write then read gives the same arrays; the roles
      each level requires (an L1 set without `scene.exr` or `coverage.png` reads, an L2 set without either is refused, an
      L0 set needs a log); the manifest records a hash for the environment files the rig named, and replacing one in
      place changes it while the request hash stays;
      a missing role, mismatched sizes, a request whose hash differs from the manifest's, an unknown file, and a level
      that overstates are each refused with a message naming the role.
- [x] 3. **The metrics** (`hogshade/compare/metrics.py`, `tests/compare/test_metrics.py`): absolute and relative error,
      PSNR and SSIM (each with an explicit `data_range`), coverage overlap, `fraction_within`. Verify: each against a
      value worked by hand on a small array; PSNR on the same arrays with two data ranges differs by exactly the
      expected decibels; identical images give PSNR infinity (a named constant, not a division by zero) and SSIM 1; a
      missing or non-positive data range and an empty mask are refusals, not a mean of nothing.
- [x] 4. **The verdict and the accepted file** (`hogshade/compare/verdict.py`, `tests/compare/test_verdict.py`):
      `Verdict`, `Threshold`, `judge`, `accepted.json` read and write. Verify: pass, needs-review and fail at, inside
      and outside the bounds in both directions; an accepted difference holds only while both hashes match.
- [x] 5. **The case table and the report** (`hogshade/compare/cases.py`, `report.py`, `verification/cases/`,
      `tests/compare/test_cases.py`, `test_report.py`): schemas, `expect: fail` controls, the report with `control_ok`.
      Verify: a malformed case is refused with its file and field; a missing or non-positive `check.data_range` is refused;
      a stored report validates and round-trips with each measurement's `data_range`; a control that passes makes the run
      fail.
- [x] 6. **The host maps the request** (`hogshade/wgpu_host.py`, `tests/host/`): `Scene` takes an optional explicit
      camera; `view_proj` uses it; the existing orbit scenes render the same bytes (a test pins this). Verify: the
      default scene's frame bytes are unchanged; an explicit camera at the orbit's eye gives the same `view_proj`.
- [x] 7. **The wgpu adapter** (`hogshade/compare/adapters/wgpu.py`, GPU test): `capture(request, out_dir)`; refuses
      near/far other than the host's, a rotation other than 0, and any view but `"preview"`, each by name. Verify (GPU):
      a set is written, reads back, says L2p; the three refusals.
- [x] 8. **The oracles and their controls** (`hogshade/compare/oracles.py`, `tests/compare/test_oracles.py`): the
      quad-sphere texel and normal checks moved out of the host test, the camera built from the request. Verify (CPU):
      a synthetic frame equal to the expected image passes, the same frame V-flipped fails, a flipped normal channel
      fails; (GPU) the two cases reproduce the existing probes' agreement and their controls fail.
- [x] 9. **The command and CI** (`tools/compare.py`, `.github/workflows/tests.yml`, `.gitignore` for `captures/`):
      `validate`, `run`, `list`; `validate` as a CI step. Verify: `validate` exits 0 on the tree and 1 on a broken
      case; `run` without an adapter exits with a clear message and a distinct code (`--allow-skips` for a headless
      runner); on the owner's machine `run` passes every oracle case and every control fails.
- [x] 10. **Docs**: the spec accepted with *What the build found*, this plan ticked, the board, the docs map, the
      README's verification section, the handoff, the journal, the knowledge file for the toolchain if it changes.
      Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | `tests/compare/test_request.py` (45): round trip, host-free hash, a `host` field refused as unknown, every field's refusal named |
| 2 | `tests/compare/test_captureset.py` (29): the roles each level requires, L1 and L0 sets, overstating refused, unknown files, a mixed set, a failed write leaving the old set intact, typed errors for bad manifests and files, environment hashes |
| 3 | `tests/compare/test_metrics.py` (25): each metric against a hand value or an independent window loop; the data range explicit, numpy scalars accepted, empty masks and pictures refused |
| 4 | `tests/compare/test_verdict.py` (33): the bounds both ways, worst-of, acceptances holding only while both hashes match, a fail never rescued |
| 5 | `tests/compare/test_cases.py` (45) and `test_report.py` (32): refusals naming file and field, parameters validated through the registry, `fails_on`, the report schema, an empty report not ok |
| 6 | `tests/host/test_wgpu_host.py`: three orbit scenes build exactly the original look-at and perspective (recomputed in the test, not a hash of float bytes, which differ between platforms); an explicit camera at the orbit's eye gives the orbit's view-projection; the camera looks where told |
| 7 | `tests/compare/test_wgpu_adapter.py` (16): the refusals by name, the request-to-scene mapping, input hashes by content; **GPU, on the owner's machine**: a capture writes a readable L2p set with every input hashed, two captures have the same pixels, a refused request writes nothing, one stop of exposure doubles the lit pixels |
| 8 | `tests/compare/test_oracles.py` (24): ideal frames pass, V-flipped and shifted ones fail, each normal channel flipped is caught, the geometry pinned by hand, the rays equal the host's inverse view-projection, the refusals |
| 9 | `tests/compare/test_runner.py` (16) and `tests/tools/test_compare.py` (14): the committed table run on ideal captures, wrong captures, a raising capture, a wrong-request capture, acceptances, `fails_on` controls; `validate`, `list` and `run` with a fake adapter and exit codes. **On the owner's machine** `uv run tools/compare.py run`: 5 pass, 0 needs-review, 0 fail; 4 of 4 controls failed as they should; the report validates |
| 10 | `check_docs.py`, `check_hygiene.py`, `check_log_format.py`, ruff clean; the spec, the board, the docs map, the handoff, the journal |

## Terms introduced

**Capture request**, **Capture set**, **Capture level**, **Adapter**, **Case**, **Oracle**, **Regression** (case),
**Parity** (case), **Control**, **Comparison verdict**, **Accepted difference**, **Baseline** and **Data range**: all in
[../../glossary.md](../../glossary.md), added when the owner noticed they were missing (ledger entry 20).
