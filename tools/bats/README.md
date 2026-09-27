# tools/bats

HogShade's Job_Orchestrator (BATS) profile, launcher and submit tool. Background, rules and the job
list: [Docs/knowledge/job-orchestrator.md](../../Docs/knowledge/job-orchestrator.md).

| File | What |
| --- | --- |
| `make_profile.py` | derives the two generated files below from the dev checkout's canon config; re-run after pulling Job_Orchestrator |
| `orchestrator_config_hogshade.json` | generated: HogShade's worker types (`hogshade_maya`, `hogshade_maya_gui`, `hogshade_python`) on the canon settings |
| `hogshade_maya_env.json` | generated: the Maya worker environment with the HogShade root on `PYTHONPATH` and the DirectX 11 viewport override |
| `run_hogshade_orchestrator.bat` | copies the profile into the orchestrator's config folder and starts orchestrator plus tray with `--config hogshade` |
| `submit.py` | submit a job and wait; `--pool` shows what is running |

```bat
set JOB_ORCHESTRATOR_ROOT=D:\Depot\Job_Orchestrator
tools\bats\run_hogshade_orchestrator.bat
"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --pool
"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --gui --main-thread --module hogshade.jobs.maya_ibl_check
```

Stop any other orchestrator first; two on one port do not coexist.
