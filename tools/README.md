# tools

Scripts, not library code (`hogshade/` is the library). One folder per DCC or host, so the Maya,
wgpu, Blender, Toolbag and Substance tooling never share a flat directory; repo-level tools that
belong to no host stay at the top. Verification artifacts a tool writes go to the matching folder
under `Docs/verification/` (`maya/`, `wgpu/`, `core/`), named `<host>-<version>-<what>.<ext>`.

| Path | What | Runs in |
| --- | --- | --- |
| `build_shaders.py` | stitch, validate and translate the WGSL core; `--check` for staleness | uv |
| `cook_ibl.py`, `bench_cook.py` | the E1 IBL cook and its benchmarks | uv |
| `maya/_session.py` | what every Maya check shares: log, shader load, file-node binding, light binding, capture, quit | Maya's Python |
| `maya/load_check.py`, `.mel` | an effect loads and lists techniques | Maya 2026 GUI |
| `maya/ibl_check.py`, `.mel` | the cooked cubes light the HogShade shell; main view plus debug views | Maya 2026 GUI |
| `wgpu/viewport.py` | the shader ball through the wgpu host, forward and deferred, to PNGs | uv, needs a GPU |
| `bats/` | HogShade's Job_Orchestrator profile, launcher and submit tool (`bats/README.md`) | the dev orchestrator |

## Adding a host

Make `tools/<host>/`, put shared session code in `_session.py` beside the scripts, and give each
check one launcher in the host's native form (`.mel` for Maya, `blender -b --python` for Blender,
the tool's own script runner for Toolbag and Substance). A check writes an incremental log first
and its pictures second, so a crash still leaves evidence. Launchers take the repo root from
`HOGSHADE_ROOT` and never hard-code a machine path.

## Running the Maya checks

```bat
set MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11
set MAYA_APP_DIR=%TEMP%\hogshade_maya_prefs
set HOGSHADE_ROOT=D:/Depot/HogShade
"C:\Program Files\Autodesk\Maya2026\bin\maya.exe" -script tools/maya/ibl_check.mel
```

The device override forces DirectX 11 for that session without touching the user's viewport
preference; the scratch preferences folder keeps the session out of the user's Maya settings.
Maya exits 127 after a scripted quit, which is normal; 139 within the first seconds is a startup
crash, so run it again.
