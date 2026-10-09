# C-2 spec: the comparison core, its wgpu adapter and the first oracle cases

**Status:** Proposed. Drafted 2026-10-08 from the accepted design
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
| `hogshade/compare/request.py` | `CaptureRequest` (frozen dataclass): `id`; `mesh` (a name from `wgpu_host.MESHES`); `material` (a document path relative to the repo, or none); `textures` (a set directory, or none); `rig` (`environment`, `rotation_deg`, `exposure_ev`, an optional directional light); `camera` (`eye`, `target`, `up`, `fov_y_deg`, `near`, `far`); `size`; `debug_mode`; `view`. `to_json` / `from_json` in canonical form (sorted keys, no whitespace); `content_hash()` is the SHA-256 of that form **without the host**, so one request hashes the same for every host. `RequestError` names the field |
| `hogshade/compare/captureset.py` | The roles a capture set holds (`request.json`, `scene.exr`, `display.png`, `coverage.png`, `manifest.json`) and `write` / `read`. `Manifest`: host, versions, the input hashes (request, mesh, material, textures), the **level actually reached**, wall seconds. Reading validates that every role exists, the sizes agree and the request hash in the manifest matches the request on disk |
| `hogshade/compare/metrics.py` | numpy only: `abs_rel_error` (max, mean, 99th percentile of absolute and relative error under a mask), `psnr`, `ssim` (the 11-pixel Gaussian window on luminance), `coverage_overlap` (intersection over union, and the symmetric difference), `fraction_within` |
| `hogshade/compare/verdict.py` | `Verdict` (`pass`, `needs-review`, `fail`), `Threshold` (a metric, a pass bound, a fail bound, a direction), `judge`, and `accepted.json` (`verification/accepted.json`): a case id mapped to the capture hash, the reference hash and a reason; a needs-review becomes `pass (accepted)` only while both hashes match |
| `hogshade/compare/cases.py` | The case table: JSON files under `verification/cases/`, schema-validated. A case has an `id`, a `kind` (`oracle`, `regression`, `parity`), a `request`, a `check` and its `thresholds`, and optionally `"expect": "fail"` (a **control**) |
| `hogshade/compare/oracles.py` | A registry of oracle checks, each `fn(capture_set, request) -> measurements`: `quad-sphere-texel` (the four maps) and `quad-sphere-normal` (the two conventions). They are the existing `_exact_probe` and `_mesh_hit` moved into the library, importing nothing from `tests/` |
| `hogshade/compare/report.py` | `Report` and its `report.json` schema: the cases, each with kind, verdict, measurements, thresholds, the capture path and hashes; a summary of counts; `control_ok` for a control. No HTML (increment C-8) |
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

## Questions

None open: the design's six answers bind this spec. If the build finds one the design got wrong, the spec is amended
and the finding goes under a *What the build found* section, as for T4.
