# Handoff: where HogShade is right now

**Status:** Living. Rewritten whenever work is interrupted, a decision changes, or a PR lands.
**Last updated:** 2026-09-26, PR #18 (the Maya gate passed; PR F complete).

A new session reads this, then `Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, then
`Docs/ROADMAP.md`, then the plan in flight (`Docs/plans/phase-2-restructure.md`).

## In flight

**PR F is complete.** The Maya gate (plan task 17) passed on 2026-09-26 as a BATS job on the
`hogshade_maya_gui` worker: `Main` technique listed, cubes and LUT decoded, pictures under
`Docs/verification/maya-2026/ibl-check/studio_small_09/`. Next in the agreed order: the legacy v1 port (plan task 18), then the
standards pass, then the phase 2 close. The MCP path was validated the same day with a scratch
stdio client: twenty tools, correct per-type counts.

## Previous state (kept until the v1 port starts)

Phase 2 PR F: the Maya `dx11Shader` shell over the generated shader-model 5 core. Done and committed
on the branch: `hosts/maya_dx11/hogshade.fx` (compiles under fxc in 14 s, `tests/compile`),
`hosts/hlsl/README.md`, tools reorganised per host (`tools/maya/`, `tools/wgpu/`, `tools/bats/`),
`Docs/verification/{maya,wgpu,core}/`, the Job_Orchestrator profile, launcher, submit tool and the
`hogshade.jobs.maya_ibl_check` job, this repo's `.mcp.json`, `Docs/knowledge/job-orchestrator.md`.

**Open: plan task 17, the Maya gate.** Maya's dx11Shader lists no techniques for the shell although
fxc accepts it. The next step is to run the check as a job on the `hogshade_maya_gui` worker and
read Maya's compile error from the mirrored Script Editor history the job writes beside its log.
Suspects already removed: string parameters carrying vertex semantics. Untested suspects: the
`#include "generated/..."` subfolder path (the spike used a same-folder include), the `string
ColorSpace` annotations, the fourteen-second compile against Maya's compile timeout.

## How to run the developer track

1. Stop any running orchestrator: its tray icon, or for a wedged one
   `toolsats\kill_hogshade_orchestrator.bat` (human only; it ends every Maya and Houdini process
   on the machine). One orchestrator per machine.
2. `tools\bats\run_hogshade_orchestrator.bat` (needs `JOB_ORCHESTRATOR_ROOT`, default
   `D:\Depot\Job_Orchestrator`). It brings up `hogshade_maya` (headless), `hogshade_maya_gui`
   (DirectX 11), `hogshade_python` and `hogshade_blender`, plus the tray.
3. Check the pool: `"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --pool`.
4. Run the gate: `... submit.py --gui --main-thread --module hogshade.jobs.maya_ibl_check`. Results
   land in `Docs/verification/maya-2026/ibl-check/<env>/` (`check.log`, `main.png`, `debug-NN.png`, `maya-history.log`).
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
