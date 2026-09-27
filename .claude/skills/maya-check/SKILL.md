---
name: maya-check
description: Run a Maya 2026 check of a dx11Shader effect (load, IBL, playblast, debug views) through the resident GUI worker, read Maya's own compile errors, and iterate on the shell. Use for plan gates that need a Maya picture or a technique list.
---

# maya-check

The checks live in `tools/maya/` (`_session.py` shared; `ibl_check.py`, `load_check.py`), run
either as a BATS job (the developer path, see the `bats-job` skill) or through the `.mel` launcher
by a human without BATS. An agent uses the job path; it never runs `maya.exe` itself while a GUI
worker exists.

## Run the IBL check

```bat
"%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\python.exe" tools\bats\submit.py --gui --main-thread --module hogshade.jobs.maya_ibl_check --param env=studio_small_09 --param debug_modes=18,27,28
```

Parameters: `env`, `fx` (default `hosts/maya_dx11/hogshade.fx`; the legacy shader is
`legacy/v2.0/V2_uv0bn-pbs_IBLenv.fx`), `debug_modes`, `set` (`attr=value,...`), `check` (the
output directory name).

## Read the result, in this order

1. `Docs/verification/maya-2026/<check>/<env>/check.log`: `TECHNIQUES: [...]` is the first fact. An
   empty list means Maya's compiler rejected the effect even if fxc passed it.
2. `maya-history.log` beside it: the mirrored Script Editor history; dx11Shader prints its compile errors
   there and nowhere else. Search for `error`, the effect's file name, `X3` codes.
3. `CONNECTED ... loaded size (w, h)`: `(0, 0)` means Maya could not decode a texture.
4. `LIGHT slot 0 <- ...`: the explicit light binding; "Unknown connectable light" means the effect
   has no light parameters (it did not compile).
5. The PNGs: `main.png`, then `debug-NN.png` per requested mode (18 specular accumulator, 27
   diffuse environment, 28 specular environment).

## Iterate on the shell

Edit `hosts/maya_dx11/hogshade.fx`, run `fxc /T fx_5_0 /D _MAYA_=1` locally first
(`tests/compile/test_build.py` does it), then resubmit the job; the worker is resident, so a round
trip is seconds. Known differences between fxc and Maya's compiler are recorded in
`Docs/knowledge/job-orchestrator.md` and the decision log; add any new one.

## Lessons that already cost time

- Textures bind through a connected `file` node, never a string path; lights bind explicitly with
  `connectLight`; playblast with `offScreen=False`; two GUI Mayas crash each other.
- naga appends `_` to identifiers ending in a digit (`specular_f0_`); the generated header is
  authoritative.
- A standalone `maya.exe -script` run must quit itself on every path; a launcher error must be
  logged to a file, or Maya sits open forever.
