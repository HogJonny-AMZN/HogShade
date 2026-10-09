# tools

Scripts, not library code (`hogshade/` is the library). One folder per DCC or host, so the Maya,
wgpu, Blender, Toolbag and Substance tooling never share a flat directory; repo-level tools that
belong to no host stay at the top.

## Verification artifacts

One directory per capture, files named by their role only:
`verification/<host>[-<version>]/<check>/<variant>/<role>.<ext>`, for example
`maya-2026/ibl-check/studio_small_09/main.png` beside `check.log`, `debug-28.png` and
`maya-history.log`, or `wgpu/shader-ball/studio_small_09/forward.png`. Host, version, check and
variant are directory levels; a file name never repeats them and never chains them with dashes.
The comparison framework (roadmap, track E) inherits this layout as its capture set.

| Path | What | Runs in |
| --- | --- | --- |
| `build_shaders.py` | stitch, validate and translate the WGSL core; `--check` for staleness | uv |
| `cook_ibl.py`, `bench_cook.py` | the E1 IBL cook and its benchmarks | uv |
| `cook_textures.py` | the T2 texture cook: an authoring set to its runtime set (`cook`; `--no-individual` for the packed-only packaged form), frequency separation (`separate`), `--check-setup` for the encoder | uv (`uv sync --all-extras` for the encoder) |
| `compare.py` | the comparison framework's command: `validate` the case table, the acceptances and any stored report (the CI step "Comparison", no GPU), `list` the cases, `run` the oracle cases on the wgpu host and write `captures/report.json` (exit 3 with no GPU adapter, 0 with `--allow-skips`); the design is `Docs/design/2026-10-08-comparison-framework.md` | uv |
| `render_framework_graph.py` | the AI-first framework graph: validates `Docs/knowledge/ai-first-framework.graph.json` and generates its Mermaid page; `--check` for staleness (the CI step "Framework graph") | uv |
| `check_content.py` | the content standard's check over every texture, sidecar, binding and cooked set (the CI step "Content"; `content-runtime` holds a committed `cooked/` to its manifest) | uv |
| `fetch_polyhaven.py` | one Poly Haven texture set into an authoring set: md5-checked downloads at 2K, the suffix table's depth and channels, sidecars with provenance, `LICENSE.md` (T3) | uv, network |
| `maya/_session.py` | what every Maya check shares: log, shader load, file-node binding, light binding, capture, quit | Maya's Python |
| `maya/load_check.py`, `.mel` | an effect loads and lists techniques | Maya 2026 GUI |
| `maya/ibl_check.py`, `.mel` | the cooked cubes light the HogShade shell; main view plus debug views | Maya 2026 GUI |
| `maya/texture_check.py`, `.mel` | a cooked texture set on the shell: the document (or one built from the set's maps) converted to legacy v2, bound, every DDS connected through the manifest, the formats Maya decoded logged, main view plus the texture debug views (T3) | Maya 2026 GUI |
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
