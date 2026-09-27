# Handoff: where HogShade is right now

**Status:** Living. Rewritten whenever work is interrupted, a decision changes, or a PR lands.
**Last updated:** 2026-09-27, evening: #26 merged and `v0.2.0` tagged; the standards pass's remainder is a PR (`docs/standards-remainder`).

A new session reads this, then `Docs/plan/BOARD.md` (gates first), then
`Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, then the newest file in `Docs/journal/`, then `Docs/ROADMAP.md`, then the plan in flight
(`Docs/superpowers/plans/phase-2-restructure.md`). `Docs/standards/definition-of-done.md` says what done means and
how much to decide alone.

## In flight

**Sit rep, 2026-09-27 evening.** Phase 2 is closed: #26 merged, `v0.2.0` tagged on the merge commit
(the owner gave permission; gate item 5, the same mesh in both hosts, deferred to track E by the
merge). The open PR is the standards pass's remainder: the decision log is decisions only now, its
working knowledge lives in `Docs/knowledge/` (`toolchain.md`, `maya-scripting.md`), its repository
state is the section at the end of this file, its open questions are the board's gates; specs and
plans are under `Docs/superpowers/`. Phase 3 is next in the order of operations and is blocked on
G3 and G4; nothing unblocked remains on the board's Next except what the owner picks from the Icebox.

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
files, and the `Docs/superpowers/` move. Not decided, the owner's: the studio package path in the
generated orchestrator profile (G1); the five gates.

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

## Rules that apply to whoever picks this up

- Never stop a process you did not start; use the orchestrator's workers through jobs. Two GUI
  Mayas crash each other; do not launch `maya.exe` beside a running GUI worker.
- Downstream users never need BATS: everything they need is committed source and cooked artifacts.
- Record decisions in the decision log in the same PR as the work; the session is not the record.

## Owner-only steps still open

Legacy pointer PR and issue on the hogjonny account; track A clearance; the orphaned 8K LFS object
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
  repo. Track A clearance steps untouched.
- The CI runner (`windows-latest`) has a DirectX 12 adapter, so the GPU tests run there through
  FXC; LFS is not hydrated on CI (`lfs: false`), so asset-dependent tests skip there.
