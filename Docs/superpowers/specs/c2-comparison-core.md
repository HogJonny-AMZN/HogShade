# C-2 spec: the comparison core, its wgpu adapter and the first oracle cases

**Status:** Accepted (owner, 2026-10-08: "go"); built, #76. Drafted 2026-10-08 from the accepted design
([../../design/2026-10-08-comparison-framework.md](../../design/2026-10-08-comparison-framework.md), increment C-2).
The first increment of the framework; nothing here needs Maya, Blender or a colour pipeline beyond what the wgpu
host has today.

Board: [../../plan/BOARD.md](../../plan/BOARD.md) (the comparison framework). Conventions it proves:
[../../standards/content.md](../../standards/content.md). The probes it ports:
[../../../tests/host/test_wgpu_host.py](../../../tests/host/test_wgpu_host.py) (the quad-sphere section). The picture
and layout rules: [../../../verification/README.md](../../../verification/README.md).

## Deliverable

A pure library, `hogshade/compare/`, an adapter that turns a **capture request** into a **capture set** from the wgpu
host at level **L2p** (scene-linear float, untagged; the design's provisional level), the metrics and the verdict
model, a case table, a report, and a command, `tools/compare.py`, that validates the case table anywhere and runs the
**oracle** cases where a GPU exists. The first cases are the quad-sphere probes, ported: the texel each pixel must show
(roughness, metalness, AO, colour) and the normal-map conventions, each with its **control** (the same check with the
expectation deliberately wrong, which must fail). That is a working end-to-end chain on one host.

## The modules

| Module | What it is |
| --- | --- |
| `hogshade/compare/request.py` | `CaptureRequest` (frozen dataclass), **host-neutral: no host or version field**; `id`; `mesh` (a canonical id from
`hogshade/compare/meshes.py`, a small registry the library owns: `shader-ball`, `quad-sphere`; the wgpu adapter maps
it to `wgpu_host.MESHES`, and the manifest records the content hash of what was loaded); `material` (a document path relative to the repo, or none); `textures` (a set directory, or none); `rig` (`environment`, `rotation_deg`, `exposure_ev`, an optional directional light); `camera` (`eye`, `target`, `up`, `fov_y_deg`, `near`, `far`); `size`; `debug_mode`; `view`. `to_json` / `from_json` in canonical form (sorted keys, no whitespace); `content_hash()` is the SHA-256 of that form, so one request hashes the same for every host because it names none. `RequestError` names the field |
| `hogshade/compare/captureset.py` | The roles a capture set holds and `write` / `read`. **Required roles depend on the declared level**: L2 and L2p need `request.json`, `scene.exr`, `display.png`, `coverage.png`, `manifest.json`; L1 needs `request.json`, `display.png` and `manifest.json` (the mask is optional, since a Maya playblast gives none; a case that needs a mask refuses a set without one); L0 only `request.json`, `manifest.json` and at least one log. Logs are optional otherwise and listed in the manifest; an unknown file is refused. `Manifest`: the host and its versions (the request names no host), the input hashes of everything actually loaded (request, mesh, material document, textures, **and the environment files the rig named**, so replacing an HDR in place changes the record even though the request text is unchanged), the **level actually reached**, the log names, wall seconds. Reading validates the level's roles, that the sizes agree and that the request hash in the manifest matches the request on disk. C-2 itself writes only L2p, but reads every level, so the Maya adapter will not have to change the reader |
| `hogshade/compare/metrics.py` | numpy only: `abs_rel_error` (max, mean, 99th percentile of absolute and relative error under a mask), `psnr(a, b, data_range, mask)` and `ssim(a, b, data_range, mask)` (the 11-pixel Gaussian window on luminance), `coverage_overlap` (intersection over union, and the symmetric difference), `fraction_within`. **The data range is an explicit argument, never inferred**: scene-linear frames are not bounded to [0, 1], so a case states its peak (for example 1.0 for a display-referred picture, or the reference's stated peak for a scene-referred one) and the verdict record repeats it; a missing or non-positive range is a refusal |
| `hogshade/compare/verdict.py` | `Verdict` (`pass`, `needs-review`, `fail`), `Threshold` (a metric, a pass bound, a fail bound, a direction), `judge`, and `accepted.json` (`verification/accepted.json`): a case id mapped to the capture hash, the reference hash and a reason; a needs-review becomes `pass (accepted)` only while both hashes match |
| `hogshade/compare/cases.py` | The case table: JSON files under `verification/cases/`, schema-validated. A case has an `id`, a `kind` (`oracle`, `regression`, `parity`), a `request`, a `check` (`{"name": ..., "data_range": ..., ...}`: **`check.data_range` is the explicit peak** for any check that measures a float frame, a positive number, refused when missing or not positive) and its `thresholds`, and optionally `"expect": "fail"` (a **control**) |
| `hogshade/compare/oracles.py` | A registry of oracle checks, each `fn(capture_set, request) -> measurements`: `quad-sphere-texel` (the four maps) and `quad-sphere-normal` (the two conventions). They are the existing `_exact_probe` and `_mesh_hit` moved into the library, importing nothing from `tests/` |
| `hogshade/compare/report.py` | `Report` and its `report.json` schema: the cases, each with kind, verdict, measurements (each carrying the `data_range` it was taken with), thresholds, the capture path and hashes; a summary of counts; `control_ok` for a control. No HTML (increment C-8) |
| `hogshade/compare/adapters/wgpu.py` | `capture(request, out_dir)`: builds the host scene from the request, renders, writes the set at L2p |
| `tools/compare.py` | `validate` (no GPU: the case table, every request, the thresholds, `accepted.json`, a stored report against its schema), `run` (the GPU path), `list` |

## The request becomes a host scene, or is refused by name

The wgpu `Scene` is an orbit camera and a fixed target today. The adapter maps what it can and **refuses what it
cannot, by name**, rather than rendering something near:

- **Camera:** `Scene` gains an optional explicit camera (`eye`, `target`, `up`); when set, `view_proj` uses it instead
  of the orbit. `fov_y_deg` maps directly. `near` and `far` must equal the host's `NEAR_PLANE` and `FAR_PLANE`
  (`UnsupportedRequest` otherwise); the depth buffer's linearisation depends on them.
- **Rig:** `environment` maps to `Scene.environment`; `exposure_ev` to `env_exposure = 2 ** ev`; an optional
  directional light to the host's light fields. `rotation_deg` other than 0 is `UnsupportedRequest`: the host has no
  environment rotation yet, and the design's table lists HDR rotation as "not yet proved on any host".
- **Material and textures:** the document is bound with `hogshade.material` (`bind(..., "wgpu")`) and its set loaded
  through `runtime_textures`, exactly as the existing tests do.
- **View:** C-2 supports only `"preview"`, the host's placeholder (Reinhard plus sRGB), and the manifest says so;
  `"agx"` and `"aces"` are `UnsupportedRequest` until increment C-1.

## The oracle cases

`quad-sphere-texel` renders the quad sphere with the synthetic set in a debug view and, for every `stride`-th covered,
non-grazing pixel away from a face edge, intersects the ray with the mesh's own triangles (the barycentric
interpolation the rasteriser performs), looks up the texel the pixel must show, and reports the fraction within a
tolerance on pixels that sit on a flat part of the map. The thresholds are the existing tests' (pass at 0.99). The
camera for the rays is built from the request, not from the host's `Scene`, so the oracle does not share the host's
own camera code.

`quad-sphere-normal` reports, per channel (green leans in V, red leans in U), the fraction matching the authored
convention and the fraction matching the **flipped** one; the case passes when the first is at least 0.99 and the
second at most 0.01.

**Controls.** For each oracle there is a twin case with `"expect": "fail"` whose expectation is wrong on purpose (V
flipped for the texel check; a flipped channel for the normal check). The report records `control_ok = true` when it
fails, and a control that passes is itself a failure of the run: the instrument could not tell right from wrong.

## What is not in C-2

Regression and parity (cases of those kinds validate but `run` refuses them, naming C-3 and C-5); baselines; Maya and
Blender; the colour pipeline and the AgX and ACES views (C-1); FLIP (C-7); the HTML report (C-8). The existing probes
in `tests/host/test_wgpu_host.py` **stay** until the cases reproduce their numbers and C-3 has landed; nothing is
deleted before its replacement has passed the same checks.

## The tests

CPU-only, run on CI, all of them: request round trip, canonical hashing and the host excluded from the hash; the
capture set write/read and every way a set can be malformed; each metric against a hand-worked value; the verdict
bounds and the accepted-differences hashes; the case table schema; the report schema; the oracle checks fed a
synthetic frame built to equal the expected image (pass) and the same frame V-flipped (fail), so the instrument is
shown to produce both answers without a GPU.

GPU, skipped on CI and run on the owner's machine: the adapter end to end, the `run` command, and the two oracle cases
with their controls reproducing the existing probes' agreement (about 100 percent).

## Acceptance

1. `uv run tools/compare.py validate` is clean and runs as a CI step.
2. On the owner's machine, `uv run tools/compare.py run` renders the quad-sphere cases, every oracle case passes, every
   control fails as it should, and `report.json` validates against its schema.
3. A capture set the run wrote is readable by `captureset.read`, its request hash matches, and its manifest says L2p.
4. The check classes in the design's table that C-2 touches (UV origin, normal convention, channel routing on wgpu)
   are the cases themselves; nothing is marked proved that no case proves.

## What the build found (2026-10-08, `feat/c2-comparison-core`)

- **The chain works end to end on the owner's machine** (RTX 5090, Vulkan, wgpu-py 0.32), at 512 px on the synthetic set:
  the five ordinary cases pass and all four controls fail as they should. The oracle reads 7,837 flat roughness pixels,
  9,047 metalness, 1,158 AO and 3,371 colour, every one at agreement 1.0; the normal check reads 1,523 green-leaning and
  6,589 red-leaning pixels, authored 1.0 and flipped 0.0. The controls: metalness with V flipped agrees 0.011, colour 0.54,
  and a flipped green or red expectation drives that channel's authored fraction to 0.0. These are the numbers the host
  tests reported before (1,522 and 6,593 then; the small difference is the oracle's rays now coming from the request,
  not the host's `Scene`).
- **The independence claim is tested, not asserted.** The oracle builds rays from the request's camera by basis vectors;
  a test shows they equal the inverse of the host's view-projection to 1e-9 for the same camera, and separate pixels whose
  answer is worked by hand (the middle of the picture is the +Z face's (0.5, 0.5), normal +Z, u along +X) pin the geometry.
- **A control is not ok merely because it failed.** The local review found that a control failing only because a pixel
  count fell short never used its wrong expectation. A control now names the metrics that must fail (`fails_on`), the
  committed controls name theirs, and `control_ok` is true only when it failed by measuring, on those metrics.
- **What the spec had not said, added in the build:** `CheckSpec` declares its metrics and its parameters (an unknown
  parameter ran as a normal check, `stride: 0` crashed a run), so a typo is refused at load; an acceptance's reference
  hash covers the check's parameters, the data range, the thresholds and a hash of the oracle's own source (so changing the
  oracle's arithmetic re-opens every needs-review without anyone remembering to bump a version); `captureset.write` stages
  in a sibling directory and replaces the old set only once the new one is whole (it used to delete first, and a failed
  write left half a set); the runner always yields a report (a capture that raises, or is of the wrong request, fails
  its case and the run goes on); a report with no ordinary case is not ok.
- **The wgpu host needed one change:** `Scene.camera`, an optional explicit `(eye, target, up)`. A test recomputes the
  orbit's original formula (a look-at from the orbit's eye to a fixed target, and the perspective) for three scenes and
  requires `view_proj` to equal it exactly, so the orbit is provably untouched. **CI caught a first version that pinned
  a SHA-256 of the packed frame bytes taken on the owner's machine: float bytes differ in the last bits between numpy
  builds, so a hash of floats pins one platform's arithmetic, not the behaviour.**
- **The coverage test's first bound was a guess**: a unit sphere four metres away under a 32 degree field fills about
  0.63 of the picture (pi/4 of the (tan 14.4 / tan 16) square), not under 0.6. Worked out, then asserted.
- **Local review** (`/local-review diff`, one round): Design 7, Architecture 7, Readability 8, Maintainability 7, Performance 8,
  Security 8, Error handling 5, Logging 6, Coding standards 8; needs work (lowest 5). Fixed: the non-atomic write, raw
  `TypeError` and `UnicodeDecodeError` escaping typed errors, the run that aborted with no report, a `KeyError` in a check
  masquerading as "could not measure", the thin logging in the adapter, runner and tool, the runner trusting whatever
  capture it was handed, thresholds and range missing from the acceptance hash, unvalidated check parameters, an empty
  report that was ok, numpy scalars refused as a data range, an adapter failure reported as "no adapter" (and green under
  `--allow-skips`), and an `assert` for an invariant. Declined with reasons: `_flat_around`'s per-pixel loop (about 14k
  iterations at 512 px, fine; revisit at 4096), the duplicated `_SHA256` and `_ID` patterns and object-field validators
  across request, captureset, verdict and report (a shared validation module is worth it when a fourth consumer appears,
  C-3), and the `sys.path` insertion in the tools test (it works under the repo's import mode; the sibling pattern would
  make every test take the module as a parameter).
- **GPU tests are skipped on CI** (no adapter, LFS not hydrated); the CPU tests prove the logic with a fake adapter that
  writes real capture sets, and the owner's run is the acceptance.

## Questions

None open: the design's six answers bind this spec. If the build finds one the design got wrong, the spec is amended
and the finding goes under a *What the build found* section, as for T4.
