---
name: bats-job
description: Submit a job to HogShade's running Job_Orchestrator (BATS) and read its result; query the worker pool; write a new job module. Use for any Maya, Blender or cook step that needs a live application, instead of launching one.
---

# bats-job

Rules first: [tools/bats/AGENTS.md](../../../tools/bats/AGENTS.md). Never stop or start processes
you did not start; if the worker you need is not in the pool, report it and stop.

## Query the pool

```bat
"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --pool
```

`JOB_ORCHESTRATOR_ROOT` defaults to `D:\Depot\Job_Orchestrator`. A connection error means no
orchestrator is running: say so. Look for `dccType` and `state` (READY is usable; BOOTING, wait;
CRASHED, the pool respawns it, do nothing). HogShade's types: `hogshade_maya`,
`hogshade_maya_gui`, `hogshade_python`, `hogshade_blender`.

## Submit a job and wait

```bat
... submit.py --module hogshade.jobs.maya_ibl_check --gui --main-thread [--param key=value ...]
... submit.py --script path\to\probe.py            # inline STRING mode, for a quick probe
```

`--gui` targets `hogshade_maya_gui`; without it, `hogshade_maya`; `--worker` overrides. Viewport
work (playblast, captures) needs `--gui --main-thread`. The tool streams status and prints the
`JobResult` as JSON: read `status`, `log`, `errorMessage`, then the files the job wrote (Maya checks:
`Docs/verification/maya/`, including the `-maya-history.log` with effect compile errors).

If the session has the `bats` MCP server, `bats_get_pool_status`, `bats_submit_job` and
`bats_get_job_result` do the same; `dcc_type` is the worker type, `execution_mode` is `GUI` for
viewport work.

## Write a new job

`hogshade/jobs/<name>.py`: a `MANIFEST` dict (name, version, worker_type, execution_mode,
description written for an agent, parameters with types and defaults, inputs, outputs, returns,
spec) and `main(parameters: dict) -> dict`. Keep it thin over code that also runs without the
orchestrator (a CLI, a `.mel` launcher). Maya rules apply inside a job: `maya.cmds` and OpenMaya
only, no PyMEL, no MEL eval. `hogshade.jobs.manifest()` must list it; add a row to
`Docs/knowledge/job-orchestrator.md`.
