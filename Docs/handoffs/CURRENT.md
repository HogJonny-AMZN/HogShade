# Handoff: where HogShade is right now

**Status:** Living. Rewritten whenever work is interrupted, a decision changes, or a PR lands.
**Last updated:** 2026-09-27, after #21 merged (nothing in flight; next is the standards pass).

A new session reads this, then `Docs/plan/BOARD.md` (gates first), then
`Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, then the newest file in `Docs/journal/`, then `Docs/ROADMAP.md`, then the plan in flight
(`Docs/plans/phase-2-restructure.md`). `Docs/standards/definition-of-done.md` says what done means and
how much to decide alone.

## In flight

**Nothing in flight.** Merged 2026-09-27: #19 (the v1 port), #20 (the journal, the definition of
done and workflow, the PR template, `tools/check_docs.py` in CI, the `local-review` skill, the board,
the BATS case), #21 (the README as the case for the repo, the pitch for the agent loop, the checker
hardened after its own local review). Next in the agreed order: the standards pass (board, Next),
then the phase 2 close at 0.2.0. The agent loop and the weekly review are Icebox rows awaiting a
design lock, not work.

Owner asks recorded this session and not yet built: none open. Standing: journal continuously; a
`→ BATS:` line wherever the orchestrator made the difference; `pathlib` everywhere.

**PR F is complete.** The Maya gate (plan task 17) passed on 2026-09-26 as a BATS job on the
`hogshade_maya_gui` worker: `Main` technique listed, cubes and LUT decoded, pictures under
`verification/maya-2026/ibl-check/studio_small_09/`. Next in the agreed order: the legacy v1 port (plan task 18), then the
standards pass, then the phase 2 close. The MCP path was validated the same day with a scratch
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
