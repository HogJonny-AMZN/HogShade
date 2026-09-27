# Agent instructions: Job_Orchestrator (BATS) in HogShade

Tool-neutral (Claude, Copilot, Codex, Cursor). Read with [README.md](README.md) (the human guide)
and [Docs/knowledge/job-orchestrator.md](../../Docs/knowledge/job-orchestrator.md).

## What you may do

- Query the swarm: `submit.py --pool`, or the `bats_get_pool_status` MCP tool.
- Submit jobs to HogShade's worker types (`hogshade_maya`, `hogshade_maya_gui`, `hogshade_python`,
  `hogshade_blender`) and wait for results: `submit.py`, or `bats_submit_job` and
  `bats_get_job_result`. Viewport work goes to `hogshade_maya_gui` with GUI mode and the main
  thread.
- Write new jobs under `hogshade/jobs/` as MODULE-mode modules with a `MANIFEST` and a
  `main(parameters) -> dict`, thin over code that also runs without the orchestrator.
- Regenerate the profile with `make_profile.py` after the dev checkout changes, and commit the diff.
- Read results and logs under `Docs/verification/<host>/`.

## What you must not do

- **Never stop, kill or restart a process you did not start.** Not the orchestrator, not its
  workers, not the owner's DCC sessions. No `taskkill /IM`, no `pkill` by name, no
  `kill_hogshade_orchestrator.bat`, no `bats_stop_orchestrator` or `bats_restart` calls unless the
  owner asks for that specific action in that turn.
- **Never launch a DCC yourself while the orchestrator has a worker for it.** A second GUI Maya
  crashes both. If the worker you need is missing, say so and let the owner start or reconfigure
  the orchestrator.
- Never edit the generated files by hand (`orchestrator_config_hogshade.json`,
  `hogshade_*_env.json`); change `make_profile.py` and regenerate.
- Never write to the dev checkout's own config folder except through the launcher's profile copy.
- Never make HogShade's tests, tools or documentation depend on the orchestrator being present.

## How to work

1. `submit.py --pool` first. If the orchestrator is down or the worker type is missing, stop and
   report; do not improvise a standalone launch.
2. Submit the job, wait, and read the whole result: `status`, `log`, `errorMessage`, and the files
   the job wrote. For Maya checks the effect compile error is in the mirrored Script Editor history
   beside the log, not in stdout.
3. Iterate on the shader or script, resubmit. The worker is resident; a job costs seconds, not a
   Maya startup.
4. Record what you learned in `Docs/knowledge/job-orchestrator.md` (rules) or the decision log
   (decisions) in the same PR as the work.
5. If the session is ending or growing long, update `Docs/handoffs/CURRENT.md` before anything else.

## Connecting the MCP server

The repo's `.mcp.json` declares the `bats` server (the dev checkout's `mcp_server.server` on its
venv). Claude Code asks the owner to approve it on first use; other hosts read the same file or
their own equivalent. The MCP tools and `submit.py` do the same things; prefer whichever the
session has.
