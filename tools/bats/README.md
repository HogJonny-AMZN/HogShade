# tools/bats: HogShade's Job_Orchestrator (BATS) setup

For humans. Agents read [AGENTS.md](AGENTS.md) beside this file. Background, the job list and the
rules: [Docs/knowledge/job-orchestrator.md](../../Docs/knowledge/job-orchestrator.md).

## What this is

Job_Orchestrator is the owner's job system: a swarm of resident DCC workers with a queue, a
system-tray app, and a gRPC API (plus an MCP server for agents). HogShade uses it as its
**developer track**: every Maya, Blender or cook check that needs a live application runs as a job
on a resident worker instead of launching the application per run. Downstream users of HogShade
never need it; everything they need is committed source and cooked artifacts.

HogShade runs the orchestrator with **its own profile** and **its own worker types**. The profile is
generated from the dev checkout's canon config so it inherits paths, scaling and logging, and it
replaces the worker set with:

| Worker type | What it is | Used for |
| --- | --- | --- |
| `hogshade_maya` | one headless `mayapy` | cooks, scene builds, checks without a viewport |
| `hogshade_maya_gui` | one `maya.exe` with `MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11` | the dx11Shader host: effect loads, playblasts, captures |
| `hogshade_python` | one venv Python | the IBL cook and other NumPy jobs |
| `hogshade_blender` | one headless Blender 5.2 | the Blender host, bakes, the required comparison path |

Named types are the orchestrator's pattern for variants; nothing in HogShade targets a canon type.

## Files

| File | What |
| --- | --- |
| `make_profile.py` | derives the generated files below from the dev checkout's canon config; re-run after pulling Job_Orchestrator and review the diff |
| `orchestrator_config_hogshade.json` | generated: the profile (canon settings, HogShade's worker types) |
| `hogshade_maya_env.json` | generated: the Maya worker environment; HogShade root on `PYTHONPATH`, the DirectX 11 override |
| `hogshade_blender_env.json` | generated: the Blender worker environment with `HOGSHADE_ROOT` |
| `run_hogshade_orchestrator.bat` | the launcher: copies the profile into the orchestrator's config folder, starts orchestrator and tray with `--config hogshade` |
| `submit.py` | submit a job and wait for its result; `--pool` prints the swarm. The jobs: `hogshade.jobs.cook_ibl`, `hogshade.jobs.cook_textures` (the Python worker runs on the workspace `.venv`, so `uv sync --all-extras` gives it the texture encoder), `hogshade.jobs.maya_ibl_check` and `hogshade.jobs.maya_texture_check` (a cooked set on the shell; `--param set_dir=... --param document=...`) |
| `kill_hogshade_orchestrator.bat` | the kill switch for a wedged orchestrator; see the warning below |

## Running it

```bat
set JOB_ORCHESTRATOR_ROOT=D:\Depot\Job_Orchestrator
tools\bats\run_hogshade_orchestrator.bat
"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --pool
"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --gui --main-thread --module hogshade.jobs.maya_ibl_check
```

- One orchestrator per machine: stop any other one first (tray icon, or the kill switch).
- The GUI Maya worker takes about two minutes to boot; the tray shows BOOTING then READY.
- Results of a check land under `verification/<host>/` (log first, pictures second, and for
  Maya a mirrored Script Editor history where effect compile errors appear).
- The launcher copies the profile into the orchestrator's config folder because named profiles
  load only from there. Loading a profile by path is a to-do on the dev checkout.

## The kill switch

`kill_hogshade_orchestrator.bat` runs the dev checkout's `scripts/kill_orchestrator.py`. It is the
most reliable way to clear a wedged or orphaned orchestrator, and it is blunt: besides the
orchestrator's own processes it ends **every `maya.exe`, `mayapy.exe`, `houdini.exe` and
`hython.exe` on the machine by name**, whether or not the orchestrator started them. Save work in
any open DCC first. It is for a human at the keyboard; an agent never runs it.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| `submit.py --pool` cannot connect | no orchestrator running, or another one on the port | start the HogShade one, or stop the other first |
| a worker sits at BOOTING then CRASHED | Maya startup crash (it happens), or a second GUI Maya on the machine | let the pool respawn it; close the other Maya |
| a Maya job reports no techniques for an effect | Maya's compiler rejected it (fxc is more permissive) | read `maya-history.log` beside the check's log |
| a MODULE-mode job cannot import `hogshade` | worker started without the HogShade environment file | check the profile was copied and the orchestrator started with `--config hogshade` |
| the profile looks stale after a Job_Orchestrator pull | canon changed | `uv run tools/bats/make_profile.py`, review, commit |
