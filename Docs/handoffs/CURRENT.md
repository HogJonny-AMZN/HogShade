# Handoff: where HogShade is right now

**Status:** Living. Rewritten whenever work is interrupted, a decision changes, or a PR lands.

**Last updated:** 2026-10-09: the template repository's requirements and eleven design answers are recorded (below and on the board row); #79 (the framework description and graph) is in review; before that, 2026-10-08: the comparison framework's first increment, C-2 (`hogshade/compare/`, `tools/compare.py`), has landed (#76); the glossary rule is mechanised (#77); the write-up of this repository's own AI-first process is in progress (steps 1 and 2 are in review as #79). This line is a snapshot: the history of earlier increments is in the journal and in `git log -p` of this file, where the sit reps removed on 2026-10-08 still are.

A new session reads this, then `Docs/plan/BOARD.md` (gates first), then `Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, then the newest file in `Docs/journal/`, then `Docs/ROADMAP.md`. `Docs/standards/definition-of-done.md` says what done means and how much to decide alone.

## In flight

**State, 2026-10-08.** No plan is in flight. Landed: S1 to S4a (the material schema, its generators, the wgpu binding, the base library), T1 to T3b and T4 tier 1 (the content standard, the texture cook, the first sets, wgpu sampling, the synthetic set), the Marmoset worker (`hogshade_marmoset`), the f-string pass, and C-2. Boarded and unblocked, with no spec yet: C-1 (vendor Blender's OCIO config with ACEScg as the working space; **read the upstream licence first**), C-3 (regression cases and baselines), C-4 (the Maya float-capture spike; needs the GPU free), and the AI-first framework write-up (the description, then the graph as data, then a template repo; design first for the last). T4 tiers 2 to 4 and the authored showcase set stay with the owner.

**What the owner has said that still holds** (a summary: where a record exists, the board, the design or the standard is the authority, not this list):

- **MikkTSpace is required** (2026-10-04): our own generator on arbitrary data, the normals as given, `Mesh.tangent_basis` flagging an unknown basis with a warning and regeneration. Maya's MikkTSpace is the preference `polyUseMikkTSpaceTangents` (off by default), set at boot by the orchestrator's Maya workers (Job_Orchestrator #73).
- **The comparison framework design is accepted as amended** (2026-10-08, "as recommended"): the capture request is host-neutral, the material hash lives in the manifest only, baselines hold pixels (the PNG in git, the scene-referred EXR in LFS). G4 and G5 are closed: the verbatim shader ball stays the calibration mesh.
- **G2 is closed** (2026-10-08): Blender's OCIO config is the base, with ACEScg as the working space; the licence is still to be read before it is vendored.
- **T4**: CC0 assets are "a box of chocolates"; "at some point, even if I have to curate it, we need materials + texture assets with full leverage". The showcase set is authored with the owner.
- **Design chain** for anything new: conversation and lock, design document, spec, plan, code (`Docs/standards/workflow.md`); a board yes is not a lock.
- **Logging**: f-strings in log calls (done, and mechanised by `tools/check_log_format.py`).
- **A new word gets its glossary row first** (2026-10-08): ledger entry 20, mechanised by the docs check's `terms` check.
- **The template repository** (owner, 2026-10-09; the board row is the record): `ai-first-template`, private; the upstream and the "maxi" (every pattern from the three repositories, each an opt-in module) that drives existing and future repositories; day 0 starts the whole process through an init mechanism (`new`, `adopt`, `--github`) and a Makefile; carries the graph generator and base graph, UX as a core stage, a Python/uv stack module, a mock `src/` of faux libraries on a neutral domain, and a specimen for every concept. Answered: report-only sync first, copy plus `framework.lock`, HogShade as the extraction base, Python/uv only in v1, two ledger files, graph overlay later, increment order core+init+Makefile, stack+mock src, specimens, UX, sync check. **Not built; the design is locked** (2026-10-09, `Docs/design/2026-10-09-ai-first-template.md`, Accepted, with the template running the framework on itself and harness neutrality folded in). Increment 1's spec and plan (core, init, Makefile, the minimum runtime, harness adapters, `payload/`) are Accepted (`Docs/superpowers/specs/template-increment-1.md`, 2026-10-09); plan tasks 0 (the harness facts, from vendor documentation) and 1 (the extraction diffs) are done and recorded in the spec; task 2 is done: the private repository `HogJonny-AMZN/ai-first-template` was created on `main` (local clone `D:\Depot\ai-first-template`) with the "all rights reserved" notice, an empty `payload/` and its own board and handoff; tasks 3 (the schemas and loader) and 4 (`init new`, the payload manifest) are merged there (PRs #1 and #2, 99 tests); next is task 5, the seed documents, built in that repository; the repository is created as the first act of that increment, with the owner's go. The licence line defaults to a stated "all rights reserved" until the owner says otherwise. Ledger entry 22: ask before pulling an icebox row forward.

**Open, and only the owner can answer:**

- The three-tier logging architecture for apps (a stream handler, a per-run file, the in-app console handler, configured at the entry point only is the guess); it must be confirmed before it is written into a standard.
- *Comparison verdict* in the glossary against the board's *Verdict* on an idea: the framework's word was qualified rather than renamed (#76); the owner may prefer to rename the other, or the code identifier.
- The Marmoset bake job's design (stateless; a scene path in, files out); nothing built until it is locked.


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
