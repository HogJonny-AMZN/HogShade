# Job_Orchestrator (BATS) in HogShade

**Status:** Living. Topic file of the HogShade knowledge base; small on purpose. Updated 2026-09-27.

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

`tools/bats/make_profile.py` derives, from the dev checkout's canon config, four generated files
that are committed and never hand-edited: the profile and one environment file per DCC, each
folding in the canon base environment (see the layering section below):

- `orchestrator_config_hogshade.json`: the canon's paths, scaling, GPU, monitoring and logging, and
  HogShade's worker types only: `hogshade_maya` (one headless mayapy), `hogshade_maya_gui` (one
  `maya.exe` with `MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11`, required by the dx11Shader host),
  `hogshade_python` (one venv Python for the cooks), `hogshade_blender` (one headless Blender 5.2 on
  its embedded Python 3.13, for the Blender host, bakes and the required comparison path). Named
  types, the orchestrator's pattern for variants, so nothing in HogShade ever targets a canon type.
- `hogshade_maya_env.json`: base plus the canon Maya environment plus the HogShade root on
  `PYTHONPATH` (so a MODULE-mode job imports `hogshade.*` directly) and the DirectX 11 viewport
  override; shared by `hogshade_maya` and `hogshade_maya_gui`.
- `hogshade_python_env.json`: base plus the canon Python worker environment plus the HogShade root.
- `hogshade_blender_env.json`: base plus the canon Blender environment plus `HOGSHADE_ROOT`;
  Blender's embedded Python ignores `PYTHONPATH`, so a Blender job puts the root on `sys.path` from
  that variable.

`tools/bats/run_hogshade_orchestrator.bat` copies the profile into the orchestrator's config folder
(it loads named profiles only from there; loading a profile by path is a to-do on the dev checkout)
and starts the orchestrator and tray with `--config hogshade`.
`tools/bats/kill_hogshade_orchestrator.bat` is the fallback for a wedged orchestrator: it runs the
dev checkout's own kill script, which also ends every Maya and Houdini process on the machine by
name. A human runs it after saving work; an agent never does.

## How the orchestrator's configuration layers, and where HogShade plugs in

The layering is deliberate; use it, never bypass it. Config: canon `orchestrator_config.json` (or a
named profile `orchestrator_config_<name>.json` in the same folder), then deep-merged sidecars
`.local.json` < `.studio.json` < `.mcp.json`. Environment, per worker: `env_profiles.json` maps a
**worker type name and mode** (`maya_gui`, `python_headless`) to a profile, and a profile chains a
`base_profile` (`base_env.json`: the orchestrator root and package on `PYTHONPATH`, the
`JOB_ORCHESTRATOR_*` variables). Two consequences that cost a restart on 2026-09-26:

- A **renamed worker type has no profile mapping** and boots with a clean environment. The
  supported path for a named variant is `environment_json_path`, the mechanism the studio
  canon mayapy worker type uses (its file is written by a pre-launch hook). HogShade generates its files.
- A **direct environment file gets no profile inheritance**, so it must fold `base_env.json` in
  itself or the worker cannot import `job_orchestrator` (the GUI Maya then never registers and sits
  at BOOTING; the Python worker exits). `make_profile.py` merges base, then the DCC environment,
  then HogShade's additions, in that order, so `${JOB_ORCHESTRATOR_ROOT}` is defined before the
  path lists that use it are expanded.

To-dos on the dev checkout, so a project overlay needs no copying or folding: load a named profile
by path; let a sidecar contribute `env_profiles` mappings and files; a kill script that ends only
the processes the orchestrator spawned, by PID; **job providers** (owner, 2026-09-27): a profile
names its provider (`hogshade.jobs:manifest`), the provider discovers its jobs by scanning rather than
by a hand-kept list, and the orchestrator, its CLI and the MCP (`bats_list_jobs`, `bats_describe_job`)
enumerate capabilities from the providers, so an agent finds jobs through the tool instead of the
docs. HogShade's side: auto-discovery in `hogshade.jobs` with a test that fails on a job without a
`MANIFEST` (today `JOB_MODULES` is a list, and the Maya job was missing from it for a day).

## Jobs

HogShade jobs live in `hogshade/jobs/`, MODULE mode, each with a `MANIFEST` dict (name, worker type,
execution mode, description written for an agent, parameter schema, inputs, outputs, returns, spec)
and a `main(parameters) -> dict`. `hogshade.jobs.manifest()` lists them. Current jobs:

| Module | Worker | What |
| --- | --- | --- |
| `hogshade.jobs.cook_ibl` | `hogshade_python` | the E1 IBL cook |
| `hogshade.jobs.cook_textures` | `hogshade_python` | the T2 texture cook; the worker's venv is the workspace `.venv`, so `uv sync --all-extras` brings its encoder (`ispc_texcomp`) |
| `hogshade.jobs.maya_ibl_check` | `hogshade_maya_gui`, main thread | load the Maya shell, bind the cooked cubes and a light, playblast, log |

A job is a thin adapter over code that also runs without the orchestrator (the cook CLI, the
`tools/maya/*.mel` launchers); a job is never the only way to run something.

`tools/bats/submit.py` submits and waits, with the dev checkout's own interpreter (it has grpc and
the protos): `--module hogshade.jobs.maya_ibl_check --gui --main-thread`, `--script file.py` for an
inline probe, `--pool` for what is running. Until a worker runs on the HogShade environment file,
`--module` wraps the import in a stub that puts the HogShade root on `sys.path` first.

## Where it made the difference (the case for BATS, kept current)

Owner, 2026-09-27: *"BATS is repeatable, durable, reduces discovery and churn over time. It's a new
paradigm, it's an agentic pipeline, it just makes sense ... so let's make it clear as we go where
it's made the most sense and an impact."* This section is that record. Each row is a real instance;
the journal carries the narrative under a `→ BATS:` line
([Docs/journal/README.md](../journal/README.md)). Rows where the orchestrator was *not* needed are
listed too, because the case is only credible if it is honest.

| When | Without the orchestrator | Through it | Why it mattered |
| --- | --- | --- | --- |
| 2026-09-26, PR F, the Maya gate | `maya.exe -script` per attempt: a minute of startup, exit 139 one launch in three, a launcher bug left idle Mayas, two GUI Mayas crashed each other, a retry loop killed a worker | One job on the resident `hogshade_maya_gui` worker (DirectX 11 forced by the profile), the technique list and the mirrored Script Editor history back in the result | The gate had failed for a day on the standalone path; it passed the first time the check ran where the session was already up and correctly configured |
| 2026-09-27, PR G, the v1 Maya check | A second standalone campaign with the same hazards | The same job with one parameter (`variant`), 37 s | Repeatable: a check is a parameter set, not a procedure; the pictures land in the layout the comparison framework will read |
| 2026-09-26, the profile and environment files | Every session rediscovers worker types, the environment layering and the base-profile inheritance trap | `make_profile.py` generates the committed profile; a new session reads this file and submits | Discovery once. The trap that cost a restart is encoded in the generator, not remembered |
| 2026-09-26, the MCP validation | An agent drives a DCC through an ad-hoc MCP that holds no queue, no manifest and no history | The `bats_*` tools are a doorway to the same queue the humans use; a job's `MANIFEST` is written for an agent to read | The MCP is the agent's entry, not a rival pipeline; what it submits is durable and inspectable afterwards |
| The E1 cook | The CLI under uv, which still exists and is the documented path | `hogshade.jobs.cook_ibl` on `hogshade_python` | Convenience only so far; it earns its place when cooks fan out across environments |
| The wgpu viewport, the GPU tests, the shader build | In-process under uv | Not routed through the orchestrator | Honest row: nothing gained; a job is never the only way to run something |

## Distribution (owner, 2026-09-27; standing rule)

Job_Orchestrator / BATS is the owner's own private tool and stays private by the owner's choice. HogShade
uses it, writes jobs for it (`hogshade/jobs/`, `tools/bats/`) and documents it here; it never vendors,
copies or distributes the orchestrator itself. A reader without BATS finds those jobs defunct, and that is
accepted. Publishing BATS is not a task in this repo.

## Rules learned the hard way

- **Never kill a process you did not start.** The orchestrator's workers are its; a job is the way
  to use them. `taskkill /IM maya.exe` took down a worker on 2026-09-26.
- **One orchestrator, one Maya GUI at a time.** Two GUI Mayas crash each other; a standalone
  `maya.exe -script` launch beside a running GUI worker is the same collision.
- **Maya's own errors are in its Script Editor**, not on stdout: the session helper mirrors the
  history to a file beside the log so a job result carries the effect compile error, and turns the
  mirroring off at the end of the check: a resident worker otherwise keeps appending to the committed
  file and holds it open (git could not restore it on 2026-09-27).
- **A resident worker keeps the previous check's scene.** Every check starts with `cmds.file(new=True)`.
- `JobRequest` fields: `dcc_type` (the worker type), `execution_mode` (`HEADLESS` or `GUI`),
  `script` or `module_path` plus `entry_point`, `parameters` (strings), `execute_on_main_thread`
  (viewport work), `job_name`, `tags`. Statuses stream as enums; `JobStatus.Name()` gives the text.
- MCP validated 2026-09-26 with a scratch stdio client (`mcp.client.stdio` against
  `python -m mcp_server.server` in the dev checkout): twenty `bats_*` tools, `bats_list_worker_types`
  correct; `bats_get_orchestrator_status` reported `ready_workers: 0` with four READY, a counting
  bug to fix on the dev checkout. A session started in this repo attaches it through `.mcp.json`.
- The MCP server (`launchers/run_mcp_server.ps1`, stdio or HTTP on 8765) exposes the same
  operations as `bats_*` tools; attaching it to an agent session is a settings change the owner
  approves.
