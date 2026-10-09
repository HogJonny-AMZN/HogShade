# The comparison framework: how HogShade proves that hosts agree

**Status:** Accepted (owner, 2026-10-08: "as recommended", to all six questions and to G5). Drafted 2026-10-08 when the owner opened gate G4 ("go on G4"), in the same message that agreed G2.
The roadmap fixed the six things this design must cover (owner, 2026-09-26: "designed, not improvised"); this
document makes them concrete, adds what the project has learned since, and ends with the questions and the owner's
answers. Nothing here is built, and `tools/wgpu/viewport.py` and `tests/host/test_wgpu_host.py` stay as they are until
the first increment's spec and plan are accepted ([c2](../superpowers/specs/c2-comparison-core.md)).

Date: 2026-10-08. Parents: [../ROADMAP.md](../ROADMAP.md), track E ("Comparison framework: designed, not improvised");
[2026-10-03-content-conventions.md](2026-10-03-content-conventions.md), section 7 (the conventions this framework
proves); [../../verification/README.md](../../verification/README.md) (the capture layout and the picture rule);
[../plan/BOARD.md](../plan/BOARD.md), gates G2, G4, G5. Vocabulary: [../glossary.md](../glossary.md).

## The goal

HogShade's claim is that one shader gives the same picture in every host, to a stated tolerance. A claim like that is
worth what its proof is worth, and today the proof is two PNGs and a printed mean and max (PR E), plus a set of
host probes that are exact but live inside one host's tests. This framework is the proof: **one way to ask a host for a
picture, one way to say how close two pictures are, one verdict, one report.** It is what lets the owner (and an agent
on their behalf) answer "did that change break the Maya look?" in one command, and what gates phase C3: OpenPBR is
judged by it.

## What already exists, and what it proves

| Piece | What it gives the framework |
| --- | --- |
| The exact host probes on the quad sphere (`tests/host/test_wgpu_host.py`) | The **oracle** kind of check: the right answer is computable (the texel a pixel must show; the shading normal a texel must produce), so there is nothing to compare against. 100 percent agreement, with controls that fail when V or a normal channel is flipped. They move into the framework as analytic checks, not away |
| The synthetic texture set, the quad sphere, the shader ball | Known inputs. A value at every texel, an analytic UV on every pixel |
| `Frames` from the wgpu host (`forward`, linear and before any view transform, `depth`, `covered`) | The first capture adapter: a host that already yields float scene-referred pixels and a coverage mask |
| The Maya check jobs (`tools/maya`, BATS) | The second adapter, with a limit: the capture is a playblast of the live dx11 viewport into an 8-bit PNG (the offscreen path does not draw dx11 effects). See "Hosts and what each can capture" |
| `verification/` and `gallery.json` | The layout rule (one directory per capture, files named by role) and the picture rule (PNG, at most 1024 px and 1 MiB, in plain git) |
| The noise-oracle pattern in LargeWorlds (`accepted.json`, a failure that writes a sheet and waits for a human) | The verdict model below |
| `OpenEXR` in the dependencies; `hog_color`'s AgX and ACES | Float capture files, and the view transforms to prove against OCIO |

## Decisions already taken that bind this design

- **G2 (2026-10-08):** the OCIO config is **Blender's**, vendored and iterated from (it carries ACEScg, AgX, ACES 1.3
  and 2.0 and Khronos PBR Neutral in one file); the working space is ACEScg, set in our copy; AgX is the default view;
  the licence is checked upstream and recorded in `THIRD_PARTY_NOTICES.md` before the file is committed.
- **Two endpoints, both required (owner, 2026-09-26):** the raw scene-referred frame and the display-referred frame
  after one view transform. A difference is attributable to shading or to display, never both.
- **Closeness is chosen per feature and stated in the manifest, not one global tolerance** (owner, 2026-09-26).
- **Baselines are regenerated on purpose by a command, never by a test** (owner, 2026-09-26).
- **MikkTSpace is required of every mesh** (owner, 2026-09-26), so a tangent basis is never a variable.
- **One directory per capture, files named by role** (owner, the artifact-naming rule).

## The shape proposed

### 1. Three kinds of comparison, one machinery

| Kind | The question | The reference is | Example |
| --- | --- | --- | --- |
| **Oracle** | Is this host's pixel what the maths says? | An analytic answer computed by the test | The quad sphere probe: the texel at each pixel; the white furnace per lobe |
| **Regression** | Did my change move this host's picture? | The same host's committed baseline | A shader edit shows up as a diff against a known picture |
| **Parity** | Do two hosts agree? | Another host's capture of the same request | wgpu against Maya on the calibration scene; v1 and v2 ports against the legacy effects |

An oracle check needs no second host and no GPU in CI beyond the host under test, so it is the cheapest and the
strongest; the framework prefers it wherever the answer is computable, and falls back to regression and parity where
it is not. All three produce the same artifact (a verdict record) and the same report page.

### 2. The unit is a capture set, from a request

A **capture request** (`request.json`, schema-validated) is everything a host needs, in the framework's own
conventions and nothing host-specific:

- the mesh (name and content hash; MikkTSpace tangents, per the standard),
- the material (a document path and hash from the library),
- the light rig: the HDR file (the cooked IBL), rotation in degrees about +Y, exposure in EV,
- the camera: eye, target, up, vertical field of view in degrees, near and far, in metres,
- the image size, the debug mode (one of the model's views, or none), the view transform name, the host and its
  version.

A host's **adapter** turns the request into that host's scene, renders, and writes a **capture set** into one
directory, `<host>[-<version>]/<check>/<variant>/` (the existing rule), with files named by role:

| Role | What |
| --- | --- |
| `request.json` | the request that produced it, so a capture can be reproduced and a diff explained |
| `scene.exr` | scene-referred ACEScg, half or float, with the colour space in the metadata (when the host can; see below) |
| `display.png` | after the one view transform, 8-bit (the picture the gallery may list) |
| `coverage.png` | 8-bit mask of the pixels the mesh covers, for silhouette exclusion |
| `manifest.json` | the host, versions (Maya, driver, wgpu, naga), hashes of the inputs, the capture level reached, the wall time |
| `*.log` | the host's own log (kept on purpose, per the verification rule) |

The adapters are jobs where the host needs an application (Maya and Blender through BATS), and plain functions where it
does not (wgpu). The framework itself never launches a host: it reads capture sets.

### 3. Conventions stated once, proved by the framework

The standard says these must be stated before any diff, because "same shader" otherwise produces different pictures
for reasons that are nobody's shading. The framework fixes one **canonical** convention in the request and each adapter
converts to its host; the framework then **proves** the conversion with registered-grid and analytic captures.

| Convention | Canonical | Where it is already proved |
| --- | --- | --- |
| Handedness and up | Right-handed, **Y up**, metres | wgpu: by construction. Maya: Y-up natively. Blender (Z-up) and glTF/engine import: adapter converts. Not yet proved on any host but wgpu |
| Projection and NDC depth | Reverse-agnostic, depth range **0 to 1**, perspective with a vertical FOV | wgpu (`view_projection_for`, the `(0, 1)` clip range) |
| UV origin | **Bottom-left, V up** in the request; a host that samples top-left flips on import | wgpu: proved, with a V-flip control that fails. Maya: captured, not yet asserted |
| Normal maps | OpenGL (+Y), tangent space, MikkTSpace | wgpu: proved, flipped channel fails. Maya's tangents: proved equal to ours (median 0.000 degrees) |
| Texture channels | The suffix table in the content standard | wgpu: proved on the synthetic set for roughness, metalness, AO, colour |
| Working space and views | ACEScg; AgX default, ACES 1.3 and 2.0 alternatives, from the vendored OCIO config | Not yet; the wgpu host's preview is Reinhard plus sRGB, labelled a placeholder |
| HDR rotation and exposure | Degrees about +Y; EV as a stop count applied before the view transform | Not yet |
| Light units | One documented unit per punctual light, conversion per host | Not yet (the shell binds one directional light) |

The table is the design's honest inventory: five rows are settled on the wgpu host alone and three are not proved on
any host. The parity work is, in large part, closing the "not yet" cells.

### 4. Hosts and what each can capture

A host reaches a **capture level**, recorded in its manifest, and the framework compares only like with like:

| Level | What the host gives | Honest limit |
| --- | --- | --- |
| **L2, scene-referred** | `scene.exr` tagged ACEScg and the display PNG through the framework's view transform | The target for every host; needs the colour pipeline (increment C-1) |
| **L2p, provisional** | Scene-linear float, its primaries untagged or not ACEScg, and the host's own preview transform | Enough for oracle and regression cases on one host; **refused by parity cases**, since primaries and view are not those of the other host |
| **L1, display-referred** | The display PNG from the host's own view transform, 8-bit | A diff here mixes shading and display; flagged as such in the report |
| **L0, none** | Nothing capturable | The host is not compared |

- **wgpu (native):** **L2p today**: `Frames.forward` is scene-linear float, but untagged, and the viewport's display
  picture is the Reinhard-plus-sRGB placeholder. It becomes L2 with increment C-1 (the ACEScg tag and the
  framework's views), and the manifest records the level it actually reached, so a set can never claim more.
- **Maya 2026 (dx11 shell):** **L1 today.** The capture is a playblast of the live viewport into an 8-bit PNG through
  Maya's own colour management, so the "raw first" endpoint is not available. This is the largest open question in the
  design (question 4): what float or HDR output the dx11 viewport can be coaxed into (a debug mode that writes
  scene-linear to an encoded channel, a viewport float render target, `ogsRender`), and whether the answer is "none"
  and Maya parity stays display-referred with a stated limit.
- **Blender (headless):** L2 is expected (Cycles/EEVEE render to float EXR); the adapter builds the Principled BSDF tree
  from the document, which is itself an approximation of the shader, so Blender parity compares **the document's look**
  to the shader's, not two copies of one shader. The report says so.
- **Engine and others:** later; the adapter contract is the same.

### 5. Closeness: a metric chosen per feature, stated in the manifest

No global tolerance. Each **case** (a request plus what to compare) names its metric and its thresholds, and the verdict
record repeats them.

| Metric | On | Notes |
| --- | --- | --- |
| Exact / analytic | Oracle checks | A fraction of pixels within a tolerance in texels or degrees; the quad sphere probe's 0.99 agreement is the model |
| Absolute and relative error | Scene-referred `scene.exr`, masked | Max, mean and a percentile; per-patch on the Macbeth chart, per-bin on the roughness ramps |
| PSNR | Scene-referred, masked | A cheap global figure; never the verdict alone |
| SSIM | Display-referred | Structure, on the 8-bit pictures |
| A perceptual metric for rendering (NVIDIA FLIP) | Display-referred | What a person would notice; question 3 on the dependency |

Masks are part of the case: coverage, silhouette exclusion (an edge band), and named regions (patches, bins). A case
with no mask is a finding, since a background that matches proves nothing. **The coverage masks are compared
first, as a structural metric of their own** (the overlap as a fraction of the union, and a minimum overlap below
which the case fails): intersecting them is only allowed once that passes, because a shifted, scaled or clipped
silhouette would otherwise be discarded as "pixels only one host drew" and the rest could still agree.

### 6. The verdict: pass, needs-review, fail

Three outcomes, as LargeWorlds' noise oracle:

- **pass:** every metric within its threshold.
- **fail:** a metric past its hard bound, or a structural fault (wrong size, missing role, a request hash that does not
  match the capture).
- **needs-review:** between the bounds. The run writes the diff artifacts (a heatmap, a side-by-side, a per-region
  table) and waits; a human records the verdict in `verification/accepted.json` with the reason and the
  capture hashes, and the next run reads it. An accepted difference stays accepted only while both hashes match, so a
  later change re-opens it.

### 7. Baselines

A regression case compares against a **baseline**: a committed capture with its hashes. A baseline is made only by
`tools/compare.py baseline --case ...`, which says what it overwrote, and never by a test. A baseline must hold
the **pixels**, not only a hash: after a shader change a regenerated capture is the new picture, and a hash can say
they differ but cannot rebuild the old one to diff against. Where the scene-referred pixels live is question 2 (the
EXR is too large for the picture rule).

### 8. One report

Every run writes one `report.json` (schema-validated) and a static `report.html`: a thumbnail grid of cases coloured by
verdict, each opening to the pair, the diff and the numbers, with the gallery's picture rules applied to what is
committed. The host parity runs, the bake comparisons (later) and the deferred-versus-forward check write the same
report, so a reader learns one page. The A/B wipe page on the board folds into this report rather than being a second
tool.

### 9. Scale and CI

A run is driven from a table of cases (hundreds across hosts, features and debug views). On the owner's machine it
renders; in CI, which has no GPU or DCC, it **checks the report schema, the case table, the request hashes and the
committed baselines against their hashes**, and runs the oracle checks that need only numpy. The GPU runner, if one
appears, runs the rest.

### 10. Where it lives

`hogshade/compare/` (a pure library: requests, capture-set reading, metrics, verdicts, the report; numpy and OpenEXR
only), `tools/compare.py` (the command), `hogshade/compare/adapters/` (wgpu; Maya and Blender as jobs in
`hogshade/jobs/`). `tests/compare/` mirrors it. `tools/wgpu/viewport.py` becomes a thin caller of the wgpu adapter and
`tests/host/test_wgpu_host.py`'s probes become oracle cases in the case table; nothing is deleted before its
replacement passes the same checks.

## The first slice, so the design stays honest

The smallest thing that proves the whole chain, before anything is generalised:

1. The request, the capture set, the verdict and the report schema, with the wgpu adapter.
2. **Oracle cases** on the quad sphere and the synthetic set (the existing probes, ported) and a **regression case**
   on the shader ball. No second host.
3. The Maya adapter at whatever level the question-4 spike finds, then the **first parity case**: wgpu against Maya on
   the quad sphere with the synthetic set, which needs both hosts at the same level (C-1 gives wgpu L2). That is the
   "calibration capture in `maya_dx11`" the roadmap puts before C3.

Blender, FLIP, the HTML polish and the engine come after, each its own increment.

## What this is not

- Not the colour-management implementation: G2 picks the config; vendoring it and the wgpu host's numeric twin of the
  views are their own increments (a prerequisite of L2 parity, listed below).
- Not a replacement for unit tests: the 728 tests stay; this is the cross-host proof layered above them.
- Not a renderer: `hogshade.wgpu_host` stays the seed of the viewer; this is the measurement around it.
- Not the pixel-identical diff of v1 and v2 against the legacy effects: that is a parity case this framework enables,
  built after the first slice.

## The questions for the owner

1. **The first slice.** Is the slice above the right "enough for C3": oracle and regression cases on wgpu, then wgpu
   against Maya on the quad sphere with the synthetic set? *Recommendation: yes. It uses the exact oracles already
   built, and the Maya half is the calibration capture the roadmap asks for.*
2. **Where baselines live.** The EXR does not fit the picture rule (1 MiB). A hash alone is not a baseline (it
   detects a change but cannot supply the old pixels to diff), so the options are: (a) the display PNG in plain git,
   which gives **display-referred** regression only; (b) the EXR in Git LFS under `verification/baselines/` (a
   `.gitattributes` addition; `content/**` is LFS today), which gives scene-referred regression too; (c) both.
   *Recommendation: (c). The PNG is the human-readable baseline in plain git; the EXR is in LFS, kept small by
   baselining at 512 px in half float (tens of cases, around a megabyte each), and CI checks the pointer and hash
   even where it does not pull LFS.*
3. **FLIP.** The roadmap names NVIDIA FLIP. The Python package is a new dependency (compiled, BSD-3), which needs a
   getting-started line and an in-tool message. numpy and OpenEXR cover everything else, and SSIM is a few dozen lines of
   numpy. *Recommendation: build the metric interface now with absolute/relative error, PSNR and SSIM in numpy, and add
   FLIP as an optional extra behind it in a later increment, your call when you want it.*
4. **Maya float capture: a spike first?** Maya's dx11 capture is 8-bit and display-referred today. Before the Maya
   adapter is designed in detail, a half-day measurement of what the viewport can give (a debug mode that encodes
   scene-linear into a channel, a float viewport target, `ogsRender`) tells whether Maya parity is L2 or stays L1 with a
   stated limit. *Recommendation: yes, as the first Maya step. It runs on the GUI worker, so it waits for a time you are
   not using the GPU.*
5. **The canonical conventions.** The table in section 3 fixes Y-up right-handed metres, NDC depth 0 to 1, UV origin
   bottom-left with V up, OpenGL +Y normals and ACEScg. Any you would change? *Recommendation: as written; they match
   Maya and the wgpu host already, and the others convert on import.*
6. **Naming and place.** `hogshade.compare`, `tools/compare.py`, `verification/accepted.json`, a case table in
   `verification/cases/`. *Recommendation: as written.*

## Increments (each its own spec and plan once this is locked)

| # | Increment | Needs |
| --- | --- | --- |
| C-1 | The vendored OCIO config (licence checked) and `hogshade.compare`'s colour module: the views in numpy proved against OCIO | G2, the OCIO Python bindings or a build-time proof |
| C-2 | The request, capture set, verdict and report schemas; the wgpu adapter at **L2p**; the oracle cases ported | This design accepted. Oracle and regression cases need no more than L2p; the manifest records the level reached |
| C-3 | Regression cases and `compare.py baseline` | C-2, question 2 |
| C-4 | The Maya float-capture spike (a measurement, its own deliverable) | C-2, the GUI worker, question 4 |
| C-5 | The Maya adapter and the first parity case, wgpu against Maya on the quad sphere | C-1 (a parity case refuses L2p), C-3, C-4 |
| C-6 | The Blender adapter and its parity case | C-5 |
| C-7 | FLIP behind the metric interface | question 3, C-2 |
| C-8 | The HTML report and the A/B wipe | C-2 |
| C-9 | The v1 and v2 pixel-identical diff against the legacy effects | C-5 |

## The answers (2026-10-08)

The owner answered "as recommended" to every question above, so the recommendations stand as written, with the
baseline revision Copilot's review forced (a baseline holds pixels):

1. The first slice is as written: oracle and regression cases on wgpu, then wgpu against Maya on the quad sphere with
   the synthetic set.
2. Baselines: the display PNG in plain git and the scene-referred EXR in LFS, baselined small (512 px, half float);
   CI checks the pointer and hash even where it does not pull LFS.
3. FLIP is deferred behind the metric interface (C-7); the first metrics are numpy.
4. The Maya float-capture spike is the first Maya step (C-4), run when the GPU is free.
5. The canonical conventions are as in section 3.
6. `hogshade.compare`, `tools/compare.py`, `verification/accepted.json` and `verification/cases/`.

**G5, answered with them (owner, 2026-10-08: "as recommended"):** no. The verbatim shader ball stays the
calibration mesh. The vertex-colour and vertex-AO features (C4) are tested with a procedural colour set with known
values, not the legacy ball's colour sets; a separate "shader ball with CPV" mesh is an optional later row.
