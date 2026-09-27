# Job_Orchestrator (BATS) in HogShade

**Status:** Living. Topic file of the HogShade knowledge base; small on purpose. Updated 2026-09-26.

## What it is, and which one

Job_Orchestrator is the owner's gRPC job system: a swarm of resident DCC workers (Maya headless
and GUI, Blender, Houdini, Unreal, a plain Python venv) with a queue, dual-mode jobs (an inline
script, or a Python module and entry point), a system-tray app, and an MCP server so an AI agent can
submit jobs and read results. "BATS" is its release packaging. Two copies matter here:

| | Where | Use |
| --- | --- | --- |
| Dev checkout | `D:\Depot\Job_Orchestrator` (`JOB_ORCHESTRATOR_ROOT`) | HogShade development. Fixes we need go there, on its own branch and PR. |
| Release BATS | wherever a user installs it | Never required. HogShade commits its sources and cooked artifacts; BATS is a developer convenience only. |

Its own agent docs are the reference for anything not here: `AGENTS.md`, `CLAUDE.md`,
`job_orchestrator/jobs/README.md` (the job-module pattern), `dcc_workers/CLAUDE.md` (worker types),
`dcc_workers/maya/CLAUDE.md` (Maya rules: `maya.cmds` and OpenMaya only, no PyMEL, no MEL eval),
`config/CLAUDE.md` (profiles and sidecars), `mcp_server/README.md` (the twenty `bats_*` tools).

## HogShade's own profile and workers (owner, 2026-09-26)

Each project owns its orchestrator profile and launcher; HogShade's is standalone and covers what
HogShade development needs. LargeWorlds and SpriteJammer get their own later, covering their
dependencies. Only one orchestrator runs at a time on a machine (one port), so stop one before
starting another.

`tools/bats/make_profile.py` derives, from the dev checkout's canon config, two generated files
that are committed and never hand-edited:

- `orchestrator_config_hogshade.json`: the canon's paths, scaling, GPU, monitoring and logging, and
  HogShade's worker types only: `hogshade_maya` (one headless mayapy), `hogshade_maya_gui` (one
  `maya.exe` with `MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11`, required by the dx11Shader host),
  `hogshade_python` (one venv Python for the cooks). Named types, the orchestrator's pattern for
  variants, so nothing in HogShade ever targets the canon `maya` type.
- `hogshade_maya_env.json`: the canon Maya environment plus the HogShade root on `PYTHONPATH`, so a
  MODULE-mode job imports `hogshade.*` directly.

`tools/bats/run_hogshade_orchestrator.bat` copies the profile into the orchestrator's config folder
(it loads named profiles only from there; loading a profile by path is a to-do on the dev checkout)
and starts the orchestrator and tray with `--config hogshade`.

## Jobs

HogShade jobs live in `hogshade/jobs/`, MODULE mode, each with a `MANIFEST` dict (name, worker type,
execution mode, description written for an agent, parameter schema, inputs, outputs, returns, spec)
and a `main(parameters) -> dict`. `hogshade.jobs.manifest()` lists them. Current jobs:

| Module | Worker | What |
| --- | --- | --- |
| `hogshade.jobs.cook_ibl` | `hogshade_python` | the E1 IBL cook |
| `hogshade.jobs.maya_ibl_check` | `hogshade_maya_gui`, main thread | load the Maya shell, bind the cooked cubes and a light, playblast, log |

A job is a thin adapter over code that also runs without the orchestrator (the cook CLI, the
`tools/maya/*.mel` launchers); a job is never the only way to run something.

`tools/bats/submit.py` submits and waits, with the dev checkout's own interpreter (it has grpc and
the protos): `--module hogshade.jobs.maya_ibl_check --gui --main-thread`, `--script file.py` for an
inline probe, `--pool` for what is running. Until a worker runs on the HogShade environment file,
`--module` wraps the import in a stub that puts the HogShade root on `sys.path` first.

## Rules learned the hard way

- **Never kill a process you did not start.** The orchestrator's workers are its; a job is the way
  to use them. `taskkill /IM maya.exe` took down a worker on 2026-09-26.
- **One orchestrator, one Maya GUI at a time.** Two GUI Mayas crash each other; a standalone
  `maya.exe -script` launch beside a running GUI worker is the same collision.
- **Maya's own errors are in its Script Editor**, not on stdout: the session helper mirrors the
  history to a file beside the log so a job result carries the effect compile error.
- `JobRequest` fields: `dcc_type` (the worker type), `execution_mode` (`HEADLESS` or `GUI`),
  `script` or `module_path` plus `entry_point`, `parameters` (strings), `execute_on_main_thread`
  (viewport work), `job_name`, `tags`. Statuses stream as enums; `JobStatus.Name()` gives the text.
- The MCP server (`launchers/run_mcp_server.ps1`, stdio or HTTP on 8765) exposes the same
  operations as `bats_*` tools; attaching it to an agent session is a settings change the owner
  approves.
