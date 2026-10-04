# Handoff: where HogShade is right now

**Status:** Living. Rewritten whenever work is interrupted, a decision changes, or a PR lands.
**Last updated:** 2026-10-04, night: T3 built, PR #58 open (two local review rounds, pass at 8) (five sets committed and cooked, the Maya shell reading them through `ormMap`, five renders in the gallery, the S2 gate pixel-identical); the Maya 2026.3 menu bug resolved by the owner (prefs and a USD patch; Job_Orchestrator issue 72 open for the patch's name); #56 and #57 merged; T2 merged (#53 spec, #54 setup section, #55 the build); T1 merged (#50, #51); #48 and #49 merged; S4a merged (#45, #46); before that #44 (bookkeeping), #43 (the gallery) merged after #42; before that #41 and #42 boarded the owner's gallery, manual and A/B-page ideas, #40 (the S4 design) merged with its eight questions awaiting the owner; before that #35 (S2) and its gate; before that, `hog_color`'s history settled by the owner, the old toolbox identifiers retired and track A closed (`chore/history-put-to-bed`, #32, from the LargeWorlds session), on top of #31 merged (S1, the material schema files and `hogshade.material`). Before that: #27 to #30 (the standards remainder, the schema design, the glossary, the S1 spec); #26 and `v0.2.0`.

A new session reads this, then `Docs/plan/BOARD.md` (gates first), then
`Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, then the newest file in `Docs/journal/`, then `Docs/ROADMAP.md`, then the plan in flight
(T2, the texture cook: `Docs/superpowers/plans/t2-texture-cook.md`, Proposed with its spec, built after the
spec merges; S1 to S4a and T1 are done, their plans ticked). `Docs/standards/definition-of-done.md` says what done means and
how much to decide alone.

## In flight

**Owner, 2026-10-04 (late):** f-strings in log calls for readability, `%s` only on a measured hot path and a tight
loop never logs (collect, log once); logging is for the human troubleshooting an AI's confident error and for the
agent spelunking later. In python.md; the conversion pass is a board row. The owner also has a **three-tier
logging architecture for apps**; it is recorded nowhere yet and must be confirmed with the owner before it is written
into a standard (the guess: a stream handler for the terminal, a per-run file, and the in-app console handler,
configured at the entry point only).

**Sit rep, 2026-10-04, late.** T2 is merged: the texture cook exists on master (#53 spec and plan, #54 the
spec's setup section, #55 the build). An authoring set cooks to its runtime set under `cooked/` (DDS with mips in
linear at DDS sizes, normals to `opengl+y`, `_ORM` and alpha carriers through the `pack` sidecar field, height
at the source's precision), block-compressed through `ispc_texcomp` (the `textures` extra under `uv sync
--all-extras`, uncompressed with a warning without it), the owner's frequency separation with its error
measured, a deterministic manifest and a volatile provenance, a BATS job, the setup in every getting-started
place, the proof pictures (Poly Haven `cobblestone_floor_04`) in the gallery. What the reviews taught, now rules
in the cook: validate every shape before writing anything, write the records after every artifact and as LF
bytes, never let a re-cook drop a record whose files exist, and say in the log what was decided on the caller's
behalf. Not covered: TIFF (recommended no), `texconv` found but unwired, no host samples a texture yet. In flight:
the T3 build PR #58, awaiting the owner. What landed: four Poly Haven sets (`metal_plate`, not the spec's
`blue_metal_plate`, which has no metalness map) and the grid tile, fetched by `tools/fetch_polyhaven.py` and cooked
`--compress` because the probe showed Maya 2026 decodes every block format; `hogshade.material.runtime` and the
Maya binder; the shell's generated `ormMap`; the texture check job and five pictures. What the resident worker
taught is failure modes 16 (it keeps the previous job's modules and environment; paths must be absolute). Next:
T4, the showcase set authored with the owner; T3b, wgpu sampling textures, its own spec; the f-string pass. Open with the owner: the three-tier
logging architecture for apps (the owner will find it); the f-string conversion pass is a board row.

**Sit rep, 2026-10-02, late night.** #40 merged: the S4 design is in with eight questions and the owner
has not answered them yet; nothing of S4 is built until they do. The owner said two things worth more than
a row: this is a generate-visuals project, so PRs should carry pictures as proof, bounded against storage
(a latest vault and a gallery page: the hero scene in every rendering path, a comparison and a showcase
per feature such as parallax occlusion); and a `Docs/manual/` is coming, reusing the same pictures. Both
are Next rows with verdicts. The facts behind the verdict: the pictures are plain git, not LFS, 2.7 MB in
all, overwritten in place, so `verification/` already is the vault; what is missing is the rule, a manifest
and a generated page. Nothing is built from either until the owner says so.

**Sit rep, 2026-10-02 night.** S1 to S3 and the standards PR are merged. The owner asked for the S4 design
("design S4"); it is drafted as `Docs/design/2026-10-02-material-library.md` (Proposed, exploring) with eight
questions and a recommendation on each. The one that shapes everything: the base set written against the
standard type with a reverse conversion table (standard to legacy v2) so today's hosts render it, rather
than legacy documents that become an artefact on C3's day. The rest: a roster of six semantic parents and
sixteen children with sourced reflectance values, `title`/`doc`/`provenance` as document fields, the
layout under `content/materials/standard/`, a wgpu contact sheet as the human gate, the texture set after
track E's conventions. The owner answers the questions (in the PR or in conversation); the answers are
written into the design in their words, the status goes to Accepted/Locked, then S4a's spec and plan.

**Sit rep, 2026-10-02 evening.** S1, S2 and S3 are merged: the schema files and library, the Maya UI
generated from them, the wgpu host bound from a document. The owner took the standards PR next ("go"):
`E501` is enforced, every module declares `_LOGGER`, and, on the owner's point that the log is the record a
human reads and an agent spelunks after a failed run, `python.md` now says what to log and the library, the
host, the tools and the jobs log their inputs, decisions and artifacts; it removes the two findings the
four local reviews kept repeating. Next real work: S4, the base library, which needs track F's design
locked first (the constants-only base set as semantic parent baselines, the small texture set, the
layout under `content/materials/`, the quality bar); the comparison framework's design waits on G4.

**Sit rep, 2026-10-02, later.** S3 is built and #38 is open: `bind(resolved, "wgpu")` through
`hogshade/material/hosts/wgpu.json` (every parameter of the three legacy types bound to a frame field and
component or `unsupported` with a reason), `Binding` and `Unbound` in `model.py`, `Scene.material` in
`hogshade/wgpu_host.py` packing the map's fields in one loop, `tools/wgpu/viewport.py --material`, three
documents under `content/materials/`, the wgpu pictures recaptured (the defaults are the schema's now, so
63 percent of the ball's pixels moved). A document is now the one way a material reaches the wgpu host; the Maya shell takes its UI from the schema (S2) and a Maya-side `bind()` is a later increment.
Next: S4 (the base library, track F's design first) or the standards PR; the comparison framework waits
on G4.

**Sit rep, 2026-10-02.** #36 merged: S2 is closed on every count. The owner chose S3 ("go"). Its spec and
plan are drafted and open for approval: `bind(resolved, "wgpu")` through a wgpu host map (the S2 mechanism
with a wgpu entry shape: parameter to frame field and component, or `unsupported` with a reason, under the
same coverage rule), a `Binding` with the frame fields, the model, the texture paths and the unsupported
list; `Scene.material` replaces the hand-set material fields in `hogshade/wgpu_host.py`; `viewport.py
--material`; the library's first two documents under `content/materials/`. The standard type has no wgpu
model before C3 and is refused by name. Texture sampling stays out (no texture bind group in the host).
The owner approves the spec; then the build, about 1 d, with the local review before the PR opens.

**Sit rep, 2026-10-01 night.** S2 is merged (#35) and its one open gate is closed: the owner restarted the
orchestrator (the kill switch, then `tools/bats/run_hogshade_orchestrator.bat`), the IBL check completed on
the fresh GUI worker, and a job that rendered master's shell in the same session produced pixel-identical
pictures to the regenerated shell's. The new pictures are the committed baseline (the September one differs
by session state, 5 to 8 percent of pixels on silhouettes and highlights, which two in-session runs of one
shell do not show). The follow-up PR carries that baseline, Copilot's two post-merge findings on #35 (the
label rule's `<`, a board row), and S2 struck. Next: S3, the wgpu binding (spec first), or the standards PR;
the owner picks. Icebox: a job sets and clears its own environment on the resident worker.

**Sit rep, 2026-10-01 late.** S2 is built and #35 is open: `hogshade.material.generate("maya_dx11")`
writes the shell's material block between markers from the legacy types' schema files and the host map
`hogshade/material/hosts/maya_dx11.json`; the four UI macros are gone; `tools/generate_material_ui.py
--check` is a CI step; `generate("docs")` writes `Docs/reference/material-types.md`; 180 material tests.
The one gate not met as specified: the IBL check on the resident **GUI Maya worker crashed the worker
during the shader load** and the orchestrator did not restart it; that worker is the owner's to restart
(the kill switch and the orchestrator are human-only). The evidence came from the headless worker: master's
shell and the regenerated one load in the same session with the same technique, the same 1021 attributes
and the same defaults, and `fxc` compiles both effects. **Owner:** restart the GUI worker, then
`"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools/bats/submit.py --gui --module hogshade.jobs.maya_ibl_check`
for the pictures; if it crashes again on the regenerated shell, that is a finding against S2. Also observed:
a job's `HOGSHADE_VARIANT` leaks into the next job on the resident worker (Icebox row). Next after S2: S3 (the
wgpu binding) or the standards PR.

**Sit rep, 2026-10-01.** #33 merged (every S1 review metric at 7 or above). The owner chose S2 over the
standards PR ("S2, the generators, go"). S2's spec and plan are drafted and open for approval:
`generate("maya_dx11")` produces the Maya shell's material block from the legacy types' schema files
plus a host map that carries only names, labels, orders and groups; the block lives between markers in
`hogshade.fx`, the four UI macros retire for explicit declarations, `tools/generate_material_ui.py
--check` runs in CI, `generate("docs")` writes `Docs/reference/material-types.md`. The spec forbids any
change to names, defaults or ranges: S2 reproduces the UI, a difference the first regeneration surfaces is
settled before `--write`. The human gate is the Maya check on the `hogshade_maya_gui` worker with the
regenerated shell. The standards PR (E501, loggers) is a Next row. The owner approves the spec; then the
build, about 1 d, with the local review before the PR opens.

**Sit rep, 2026-09-27 late night.** #31 (S1) and #32 (the history put to bed, from the LargeWorlds
session) are merged. The owner asked how to raise the review's low scores; the answer was to re-run the
review on the merged head, which scored 7 to 8 everywhere but error handling (6) and found that the
cutout mapping sent every opaque legacy material to `blend`. Both are fixed on `fix/s1-review-round-2`
(#33 open): `when` conditions may read several source parameters, `validate()` never raises, `convert()`
refuses an invalid material, and the rest of the review's list. The process lesson, for the definition
of done: run `/local-review diff` before `gh pr create`, and again after the fixes until nothing is
below 7; the first S1 review ran after the PR opened and its findings became a second commit. Not done
and worth a PR of its own: `extend-select = ["E501"]` plus the logger in the rest of the tree (26 long
lines and about 20 loggers outside `hogshade/material/`). Next real work: S2, the generators; spec first.

**Sit rep, 2026-09-27 night.** S1 is built and #31 is open for the owner: `hogshade/material/`
(`model`, `schema`, `document`, `validation`, `resolution`, `conversion`), four `*.material-type.json`
and three conversion tables as package data, 133 tests, the wheel check, and the mayapy import run
(Maya 2026's Python 3.11.9 lists the four types; the library is standard-library only). The build
amended the spec in seven places, all two-way doors listed in the spec's last section and the PR's
Decisions table; the ones worth knowing: the modules are `validation.py`, `resolution.py` and
`conversion.py` because the package's re-exported functions shadowed the spec's names, opt-in groups
are inferred from a `<group>_enabled` bool, legacy v2 carries `specular_f0_map`, and the resolved
`mask` finding fires only for a constant opacity below the cut. Next in the schema's six increments
is S2, the generators (the Maya material block and the wgpu struct from the type files); it needs a
spec, and nothing from G4. The local review (needs-work, lowest 6/10) and Copilot's ten findings on #31 are fixed in the second
commit and answered on their threads; the PR waits on the owner's merge.

**Sit rep, 2026-09-27 evening.** Phase 2 is closed: #26 merged, `v0.2.0` tagged on the merge commit
(the owner gave permission; gate item 5, the same mesh in both hosts, deferred to track E by the
merge). The open PR is the standards pass's remainder: the decision log is decisions only now, its
working knowledge lives in `Docs/knowledge/` (`toolchain.md`, `maya-scripting.md`), its repository
state is the section at the end of this file, its open questions are the board's gates; specs and
plans are under `Docs/superpowers/`. Phase 3 is next in the order of operations and is blocked on
G4 only: the owner closed G3 the same evening (ADR-009, HogShade owns the material schema and
data, the editor lives in LargeWorlds), so the schema's pre-spec design is the unblocked Next row; it is drafted
(`Docs/design/2026-09-27-material-schema.md`, Accepted) and is locked in full (2026-09-27, all ten questions answered in the owner's words). S1's spec and
plan are drafted (`Docs/superpowers/specs/s1-material-schema.md`, `plans/s1-material-schema.md`,
Proposed): the four schema files as package data, the three conversion tables, and
`hogshade.material`'s load, validate, resolve and convert with tests. The owner approves the spec;
then the plan runs as one PR, about 2 d, and needs nothing from G4.

What the standards pass landed: `Docs/standards/python.md` and `wgsl.md`, `Docs/standards/failure-modes.md`
(twelve entries from this week, five with checks), `.github/copilot-instructions.md`, `Docs/decisions/`
with ADR-001 to ADR-008 and the index (`check_docs.py` governs it), a `**Status:**` line on every
document under `Docs/` with the checker widened to all of it, and a project review
(`Docs/reviews/2026-09-27-standards-pass-project-review.md`, needs-work, lowest 6/10) with its ten
fixes applied: NumPy twins and GPU tests for `environment.wgsl` and `lambert.wgsl`, module headers on
every tool, unused loggers dropped and the rule written, the stale "switch" wording and the unused
`HOGSHADE_IRRADIANCE_OVER_PI` removed (artifacts regenerated), the FXC rule restated as what actually
bites, the Maya helpers logging to their `Log`, `Path.open`, a dead parameter gone, shared reference
helpers in `hogshade/reference/_common.py`, `submit.py`'s stub built from a literal. the suite green
on the owner's GPU, the run log at `verification/core/gpu-tests.log` with its commit;
`build_shaders.py --check --require-compilers` clean.

Not done, on purpose, and on the board as the pass's remainder: the decision log split into topic
files, and the `Docs/superpowers/` move. Not decided, the owner's: the gates G2 to G5 (G1 closed 2026-09-27).

Next in the agreed order: the phase 2 close (deviations list, status rows, roadmap C2, VERSION
`0.2.0`), then phase 3. The agent loop and the weekly review stay Icebox rows awaiting a design lock.

Owner asks recorded this session and not yet built: none open. Standing: journal continuously; a
`→ BATS:` line wherever the orchestrator made the difference; `pathlib` everywhere.

**PR F is complete.** The Maya gate (plan task 17) passed on 2026-09-26 as a BATS job on the
`hogshade_maya_gui` worker: `Main` technique listed, cubes and LUT decoded, pictures under
`verification/maya-2026/ibl-check/studio_small_09/`; the v1 port followed as #19. The MCP path was validated the same day with a scratch
stdio client: twenty tools, correct per-type counts.

## How to run the developer track

1. Stop any running orchestrator: its tray icon, or for a wedged one
   `toolsats\kill_hogshade_orchestrator.bat` (human only; it ends every Maya and Houdini process
   on the machine). One orchestrator per machine.
2. `tools\bats\run_hogshade_orchestrator.bat` (needs `JOB_ORCHESTRATOR_ROOT`, default
   `D:\Depot\Job_Orchestrator`). It brings up `hogshade_maya` (headless), `hogshade_maya_gui`
   (DirectX 11), `hogshade_python` and `hogshade_blender`, plus the tray.
3. Check the pool: `"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --pool`.
4. Run the gate: `... submit.py --gui --main-thread --module hogshade.jobs.maya_ibl_check`. Results
   land in `verification/maya-2026/ibl-check/<env>/` (`check.log`, `main.png`, `debug-NN.png`, `maya-history.log`).
5. An agent session in this repo gets the BATS MCP server from `.mcp.json` (approve it when Claude
   Code asks); the `bats_*` tools do what `submit.py` does.

## The sibling repositories, as of 2026-09-27 (owner)

Owner: "I haven't caught SpriteJammer up to speed with LargeWorlds; I was getting LargeWorlds fully
ported to wgpu first, so SpriteJammer itself is currently the most stale and the most in need of
catching up to LargeWorlds and HogShade work." What moved under SpriteJammer that its docs do not
know: LargeWorlds is wgpu-only (its ADR-012, 2026-09-25; the docs that call `hog_rendering`
OpenGL are stale); HogShade owns the material schema and data (ADR-009) and has the schema's
pre-spec design drafted, so SpriteJammer's MT1 keeps the Material Types, the Cook and the demo and
takes the schema from here; the board, journal, DoD and checker conventions landed here from
SpriteJammer's own pattern and are now the same shape in all three repos. Nothing in this repo
waits on SpriteJammer; its catch-up is a session in that repo.

## Rules that apply to whoever picks this up

- Never stop a process you did not start; use the orchestrator's workers through jobs. Two GUI
  Mayas crash each other; do not launch `maya.exe` beside a running GUI worker.
- Downstream users never need BATS: everything they need is committed source and cooked artifacts.
- Record decisions in the decision log in the same PR as the work; the session is not the record.

## Owner-only steps still open

Legacy pointer PR and issue on the hogjonny account; the orphaned 8K LFS object
(support request, optional). See the decision log, section 4.

## Repository and GitHub state (moved from the decision log, 2026-09-27; as of 2026-09-26 unless dated)

- HogShade left the fork network on 2026-09-26; it is standalone. LFS uploads work. `content/ibl`
  payloads and the shader ball are in.
- One orphaned LFS object exists in GitHub's LFS store: the 8K studio master, pushed once by
  mistake on the LFS branch and removed before merge. Only GitHub support can purge it; it counts
  toward the LFS quota. CC0 content, no licence issue. Here only.
- GitHub still reports the pre-rewrite repository size (about 129 MB) until its garbage collection
  runs or support is asked.
- Owner-only steps still open: merge the legacy pointer PR (`hogjonny/Maya-PBR-BRDF-VP2#2`) from
  the legacy account, delete the `legacy-pointer` branch, close legacy issue #1, archive the legacy
  repo. Track A closed 2026-09-27: the clearance boxes settled by the owner's account, the profile
  housekeeping moved out of this repo (account work, parked in the agent's memory until the owner names a home).
- The CI runner (`windows-latest`) has a DirectX 12 adapter, so the GPU tests run there through
  FXC; LFS is not hydrated on CI (`lfs: false`), so asset-dependent tests skip there.
