# Decision log and working knowledge

**Status:** Living. Appended whenever a direction or decision is made in conversation and is not yet
in a spec, plan or ADR. The conversation is not the record; this file and the documents it links
are. If a session is lost, a new one starts here, then `ROADMAP.md`, then the plan in flight.

Written 2026-09-26 from the sessions of 2026-09-20 to 2026-09-26. Each entry says where the decision
is formalised, or "here only" when this file is the only record. Owner statements are marked
(owner). Soft directions are marked (soft): stated, agreed in principle, not yet scheduled or
specified.

## 1. Order of operations (owner, agreed 2026-09-26)

1. Phase 2 PR F: the Maya `dx11Shader` shell over the shader-model 5 artifact, sixteen light slots,
   the E1 cubes in ordinary texture slots, the IBL check tool re-run. The diff of the owner's edited
   shader ball against the verbatim OBJ happens here, because Maya is open.
2. The legacy v1 port (`core/models/legacy_v1.wgsl`).
3. The standards pass (`ROADMAP.md`, "The standards pass"): coding standards and agent context,
   review of `core/`, `hogshade/`, `hosts/`, `tools/`, ADRs for the structural decisions including
   shader specialisation.
4. Phase 2 close: deviations list, status rows, roadmap C2, VERSION `0.2.0`.
5. Phase 3 (OpenPBR, MaterialX carrier, parameter schema). The comparison framework design lands
   before phase 3's comparison view is written.

Formalised: the standards-pass section of `ROADMAP.md`; the phase 2 plan.

## 2. Decisions already formalised elsewhere (index)

| Decision | Where |
| --- | --- |
| WGSL is the core source; naga translates; Slang is the fallback | `design/2026-09-20-modernization-direction.md`; spec phase 2 |
| Textures, samplers and uniforms are function parameters in the core, never bound globals | `Spikes/naga-fx/README.md`; spec phase 2 |
| Module-prefix naming rule, exempt public names | `core/manifest.toml`; spec phase 2 |
| Model interface: `_inputs`, `_evaluate_light`, `_evaluate_env`, `_env_lookup`, `_debug`; `EnvironmentSamples` passed to both evaluate functions; `ShadingInputs.specular_weight` | spec phase 2, "Interfaces"; PR #10 |
| Dispatch is an if-chain, not a switch (FXC) | `core/models.wgsl` header; plan task 13 |
| Legacy v2 port: what is kept verbatim, six deviations | `core/models/legacy_v2.wgsl` header; design doc section "Legacy v2 port" |
| v2 furnace returns 1 plus the specular albedo; recorded, not fixed | spec phase 2, "The test harness" |
| GGX D tolerance split at alpha 0.1 | `tests/core/test_brdf_gpu.py`; plan task 9 |
| ADR-002 G-buffer layout, octahedral normals, sRGB-aware quantisation | `core/gbuffer.wgsl`; `tests/core/test_gbuffer_gpu.py` |
| E1 cook conventions (face convention, roughness linear in mip, E over pi, LUT) | `Docs/specs/e1-ibl-cook.md`; cooked manifests |
| Cook resolution sweet spot: 4K source to 1024 cube for probes, 256 default, 2048 only for a hero sky | `Docs/research/benchmarks/`; E2 plan |
| Maya 2026 only; no 3ds Max host; HogShade has its own versioning; CPV masks, CPV AO and the 33 debug views are first-class; never delete a shading path | design doc "Decisions" |
| MikkTSpace is a requirement | `ROADMAP.md` track E |
| Scene-referred ACEScg; AgX default view, ACES first-class alternative; raw and display comparison endpoints | `ROADMAP.md` track E |
| Test assets, procedural test data, bake comparisons, comparison framework design-first, own renderer framework | `ROADMAP.md` track E |
| Shader specialisation: uber core as the record, static axes through `override` constants | `ROADMAP.md`, standards pass |
| 8K HDR masters never committed; 4K conditioned sources under LFS | `.gitignore`; `content/ibl/README.md` |
| Shader ball is derkreature's OBJ verbatim, Unlicense | `content/shaderball/LICENSE.md`; `THIRD_PARTY_NOTICES.md` |

## 3. Directions not yet scheduled (soft)

- **Legacy assets as candidates (owner).** The legacy repo is re-cloned at `D:\Depot\Maya-PBR-BRDF-VP2`
  (433 MB, full history) for on-disk comparison only. Of interest: `testFiles/v2.0/shaderBall_pbr_IBLenv.ma`
  and `testFiles/v1.0/brdf_test*.m?` (the owner's edited ball: UV sets, CPV values), `testFiles/v2.0/rocks.ma`,
  the `Textures/Basic` set (grid colour, normal, height, emissive tiles, a film LUT) and the
  `Textures/IBLbaker` set (paper-mill RGBM cubes and the old BRDF LUT). Pull over only "done better";
  nothing copied as is. Here only, plus the roadmap test-assets item.
- **The base scene ships in four forms (owner):** Maya, Blender, glTF, FBX. Roadmap test-assets item.
- **Optional tool paths (owner):** Maya is the owner's production DCC; Marmoset Toolbag is, in the
  owner's view, the best game-like bake and render workflow; Substance is the AAA texturing
  standard. All optional, detected, skipped when absent; Blender is the required path. Roadmap.
- **E2 leftovers:** BC6H output when a 1024 cube ships; a numba mip-0 resample when 2048 cooks are
  routine. E2 plan notes; here as a reminder they are deliberate deferrals, not gaps.
- **The comparison output that exists is a placeholder (owner).** `tools/wgpu/viewport.py` and
  `tests/host/test_wgpu_host.py` are replaced by the designed framework, not extended. Roadmap.
- **Visual proof before merging visual work (owner preference, from the sibling project):** offer a
  page of real rendered output alongside a PR that changes a picture. Here only.

### Material data, contracts and editor: where they live (owner asked 2026-09-26; recommendation, soft)

The question: does a base material data model and editor live here and get extended in LargeWorlds
and again per game, or does this repo stay focused on shading? Recommendation, not yet decided:

- **HogShade owns the material contract** because the contract is the shader's API: the parameter
  schema (name, type, range, default, UI group, semantic), the OpenPBR-in-MaterialX document as the
  authored form, the glTF game-profile mapping, the texture conventions, and a Python library that
  loads, validates and converts a material document and produces a host's uniform and texture
  binding set. Every host UI (Maya's shell, the engine editor, the viewer) is generated from that
  one schema; parity depends on it being defined once.
- **LargeWorlds owns the editor**: Qt widgets, node graphs, asset browser, live link, engine-side
  material assets and instances, packing, streaming. It consumes the schema. A game extends the
  LargeWorlds editor and asset types, never HogShade.
- **Dependency direction is one way**: LargeWorlds depends on HogShade (pip package for the Python
  library, vendored copy of the core WGSL); HogShade never imports LargeWorlds and never depends on
  PySide6, so it stays importable inside Maya and Blender. This mirrors LargeWorlds' rule that its
  library packages carry no graphics stack.
- **Extension without forking**: the schema carries namespaced extension blocks; HogShade validates
  the core block and passes unknown namespaces through; LargeWorlds adds engine fields (layer, light
  channels, tier caps, streaming hints) in its namespace; a game adds its own. Three layers, one
  document format.
- **The grey zone**: HogShade's viewer and comparison tool get a minimal generic parameter panel
  generated from the schema; anything beyond (node graphs, asset browsing) belongs in LargeWorlds.

Decided when phase 3 designs the schema; becomes an ADR in the standards pass if the owner agrees.

### Agent instructions as a knowledge base (owner, 2026-09-26; decided)

Agent instructions and context live in a modular, AI-agnostic knowledge base of small topic files,
with an `AGENTS.md` entry point, a thin `CLAUDE.md` importing it, and a Copilot pointer; decisions
in ADRs, context in this log and the roadmap, standards separate from state. This file is the
first casualty by design: the standards pass splits it into topic files. Formalised in the
roadmap's coding-standards item (track B).

### Tools and verification layout (2026-09-26; decided during PR F)

`tools/<host>/` per DCC or host (`maya/` with `_session.py` shared by every Maya check, `wgpu/`,
later `blender/`, `toolbag/`, `substance/`); repo-level tools at the top; `verification/<host>/`
mirrors it. `tools/README.md` is the rule. Started now rather than after forty artifacts.

### Driving Maya during development: BATS or a Maya MCP as a convenience, never a dependency (owner, 2026-09-26; soft)

Launching a fresh `maya.exe -script` per check costs a minute of startup, is flaky (Maya's startup
crash, exit 127 or 139 in the first seconds), and a launcher bug leaves an idle Maya open. The owner's
BATS bridge (Job_Orchestrator) or a Maya MCP server can hold one session open and run the checks on
demand. Rule: the check scripts stay standalone modules with a `run()` and a `.mel` launcher, so
anyone with Maya can run them with no other tool; BATS or an MCP is an optional developer path that
imports the same modules into a live session. The repo takes no dependency on either. Wiring it up
is a Job_Orchestrator-side task; this repo only keeps its scripts importable.

### Job_Orchestrator: per-project profile, HogShade's own worker types (owner, 2026-09-26; decided)

Each project keeps its own orchestrator profile and launcher (HogShade now, LargeWorlds and
SpriteJammer later, each covering its dependencies); one orchestrator runs at a time. HogShade's
profile defines its own named worker types on the orchestrator's variant pattern: `hogshade_maya`
(headless), `hogshade_maya_gui` (DirectX 11 viewport), `hogshade_python`, `hogshade_blender`
(headless Blender 5.2, added the same day); every HogShade job targets those, never a canon type. The developer track
requires BATS; downstream users never do. The repo maintains the profile, the environment file, the
launcher, the submit tool, the `.mcp.json` for an agent session, and `Docs/handoffs/CURRENT.md` so a
new session continues without this one. Details: `Docs/knowledge/job-orchestrator.md`.

### Docs convention and the superpowers skills (owner, 2026-09-26; decided, applied in the standards pass)

`Docs/superpowers/{design,specs,plans,handoff}` is the cross-repo convention; HogShade's folders move
there in the standards pass. The pre-spec design stays a hand-written lock of what was discussed
and decided; the superpowers skills take over from there (brainstorming writes the spec from the
lock, writing-plans the plan, executing-plans with TDD the build, verification and code review
before a PR) from the next spec on. A handoff
file is written whenever a session is interrupted or grows long; `Docs/handoffs/CURRENT.md` is the
first.

### Verification artifact layout (owner, 2026-09-26; decided)

One directory per capture, files named by role only:
`verification/<host>[-<version>]/<check>/<variant>/<role>.<ext>` (`maya-2026/ibl-check/studio_small_09/main.png`
beside `check.log`, `debug-28.png`, `maya-history.log`; `wgpu/shader-ball/studio_small_09/forward.png`).
A file name never repeats the host, version, check or variant and never chains them with dashes; the
owner stopped that pattern the first time it appeared because agents copy existing patterns. The
comparison framework inherits this layout as its capture set. Rule in `tools/README.md`.

### The v1 port (2026-09-27; decided by the record)

v1 was one model, the Disney principled BRDF; the roadmap's "Disney, Cook-Torrance and game BRDFs"
was wrong, since the other two includes never compiled. Ported as `legacy_v1` with the interface
additions above; both legacy models are selectable in the wgpu host and the Maya shell. Lessons:
the Maya shell now takes 24 s under fxc with two models (14 s with one), the FXC canary's second
reading; a resident Maya worker keeps the previous check's scene, so every check starts with a new
scene; registered grids and the debug views are the per-host orientation and channel probes
(roadmap, procedural test data).

### The journal, and the process around it (owner, 2026-09-27; decided)

Per-session, per-task journalling of learnings, ported from SpriteJammer *with its process*, which the
owner asked for explicitly: "parse SpriteJammer and its readme, claude and instructions on the why
journalling, process, how and etc.; that's important to replicate and not just building the journal."
What landed: `Docs/journal/` (README with cadence, entry format and the session index; one file per
session, append-only), `Docs/standards/definition-of-done.md` (the DoD table, the autonomy protocol
with two-way doors recorded in the PR's *Decisions* table and one-way doors asked, eight per PR as the
split threshold, when `local-review` runs, a growth ladder), `Docs/standards/workflow.md` (the stages
and who owns which record), `.github/pull_request_template.md`, `tools/check_docs.py` with its test
(links, status, journal index, ADR index) and a CI step. Left out on purpose: SpriteJammer's
`PENDING-REVIEW.md` (its PR table replaced it there too), the failure-modes ledger and the board,
until this repo has enough of its own failures and state to fill them (standards pass). This log
stays the index of decisions; the journal is the narrative behind them.

### `local-review` skill, adapted (owner, 2026-09-27; decided)

SpriteJammer's repo-agnostic reviewer ported to `.claude/skills/local-review/` with a `core` mode for
a WGSL module against the core contract, the hygiene grep and a stale generated artifact as hard
findings, and `master` as the default branch. Runs on significant increments before a merge is
asked for; the rule is in the definition of done.

### The case for BATS, made visible as it happens (owner, 2026-09-27; decided)

"BATS is repeatable, durable, reduces discovery and churn over time. It's a new paradigm, it's an
agentic pipeline, it just makes sense ... let's make it clear as we go where it's made the most sense
and an impact." Two records: a `→ BATS:` trailing line on any journal entry where the orchestrator
made the difference, and a running table in `Docs/knowledge/job-orchestrator.md` ("Where it made the
difference"), with honest rows for the steps that needed no orchestrator. The framing that came out
of the record: the MCP is the agent's doorway to the same durable queue humans use, not a rival
pipeline; an ad-hoc DCC MCP would rediscover the session every time and hold nothing.

### Job providers and capability discovery in the orchestrator (owner, 2026-09-27; soft, a to-do on the dev checkout)

Owner: the orchestrator "needs a better way to inspect and infer jobs and capabilities. Maybe each job
provider needs to register a job source, paths, capabilities (metadata)"; the con is a burden per job
that an agent may not read the instructions for, the pro is that an agent "isn't left guessing or
searching". Evidence the same day: `hogshade.jobs.maya_ibl_check` carried a `MANIFEST` for a day and
was invisible because `JOB_MODULES` was a second manual step (Copilot, PR #19). Recommendation:
register *providers* (one line per project in its profile, `hogshade.jobs:manifest`), discover *jobs*
(the provider scans its package; a test fails on a job without a manifest, so the list can never be
forgotten), and let the orchestrator and its MCP enumerate from the providers (`bats_list_jobs`,
`bats_describe_job`, a CLI flag), so an agent that never read the docs still finds the jobs through
the tool it reaches for anyway. HogShade's `MANIFEST` shape is the candidate schema. Cost: about a
day on the dev checkout, half a day here. Here only, plus the to-do list in
`Docs/knowledge/job-orchestrator.md`.

## 4. Repository and GitHub state (as of 2026-09-26)

- HogShade left the fork network on 2026-09-26; it is standalone. LFS uploads work. `content/ibl`
  payloads and the shader ball are in.
- One orphaned LFS object exists in GitHub's LFS store: the 8K studio master, pushed once by
  mistake on the LFS branch and removed before merge. Only GitHub support can purge it; it counts
  toward the LFS quota. CC0 content, no licence issue. Here only.
- GitHub still reports the pre-rewrite repository size (about 129 MB) until its garbage collection
  runs or support is asked.
- Owner-only steps still open: merge the legacy pointer PR (`hogjonny/Maya-PBR-BRDF-VP2#2`) from
  the legacy account, delete the `legacy-pointer` branch, close legacy issue #1, archive the legacy
  repo. Track A clearance steps untouched.
- The CI runner (`windows-latest`) has a DirectX 12 adapter, so the GPU tests run there through
  FXC; LFS is not hydrated on CI (`lfs: false`), so asset-dependent tests skip there.

## 5. Working knowledge (the lessons that cost time)

### Toolchain and shell

- naga-cli 30.0.1 and Rust 1.98.1 via winget; `$HOME/.cargo/bin` on PATH in git-bash (not
  `$USERPROFILE`). `export MSYS_NO_PATHCONV=1` before fxc, dxc or naga, or git-bash rewrites `/T`
  and `/E` into paths. With that exported, native git cannot read `/tmp/...` message files: write
  commit messages to a real Windows path.
- `gh pr create` must pass `-R HogJonny-AMZN/HogShade` (a habit from the fork days; harmless now).
- naga: names ending in digits get a trailing underscore (`FixedSlots16_`); `meta` is reserved;
  GLSL output needs a `.frag` extension; struct-field parsing in the build must tolerate
  `array<LightSource, 16>`.
- FXC (Maya's dx11Shader and wgpu's D3D12 backend): rejects a `switch` on a value read from a uint
  texture in a shader that also passes textures into functions ("no storage type for block
  output"); rejects some multi-return switch cases ("not all control paths return a value").
  Single returns and if-chains compile. Check every new host shader on the D3D12 backend
  (`WGPU_BACKEND_TYPE=D3D12`) before pushing.
- `queue.write_texture` needs no 256-byte row alignment; buffer-to-texture copies and readback do.
- Recreate `.venv` after moving the clone folder: uv's script launchers embed the absolute path.

### Maya 2026 scripting (from E1 and the spike)

- Maya's Python is 3.11: no nested same-quote f-strings; parse-check scripts with `mayapy` first.
- Run checks with a scratch `MAYA_APP_DIR` and `MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11`; the
  owner's viewport preference is OpenGL Core and is never changed.
- Playblast with `offScreen=False`; the offscreen path does not draw the dx11 effect. Compare
  frames on decoded BMP pixels over the non-background region; `MImage` pixel access runs out of
  memory.
- Exit code 127 after `quit` is normal; 139 at about twelve seconds is a startup crash, so wrap
  launches in a retry loop, kill stray `maya.exe` and `mayapy` first, and never run two Maya
  instances at once.
- `dx11Shader` texture slots need a connected `file` node (`setAttr` with a string fails); lights
  are bound explicitly with `cmds.dx11Shader(node, connectLight=("Light 0", light_transform))`
  and read back with `lightConnectionStatus`; the `-e` flag is invalid on that command.
- Legacy v2 findings (never re-chase): both cube parameters use the `environment` semantic; unbound
  2D maps sample black, so an unbound cavity map blacks out specular; RGBM `.bgr` decode at
  exposure 5 and gamma 2.23. All addressed by the port's deviations.

### Process

- Roadmap, pre-spec design, spec, plan, then work; a task is ticked when its verification ran.
- Every PR is reviewed by Copilot; each finding is assessed, fixed when right, refuted with
  evidence when wrong, and answered on its thread. The owner merges and deletes the branch. Claims
  in a reply are made after the evidence exists, never before (a D3D12 claim on PR #13 went out
  early and had to be corrected).
- Hygiene before every push: no employer names, personal email, no studio files, Apache-compatible
  dependencies. LargeWorlds, Job_Orchestrator, BATS and SpriteJammer are the owner's own projects
  and may be named.
- This repository's default branch is `master`; `gh pr create` needs `--base master`. Write a
  commit-message file in its own command: a chained assertion that aborts before the file is written
  leaves the next commit reading a file that does not exist (PR G, twice).

## 6. Open questions for the owner

- Whether the owner's shader-ball edits (UV sets, CPV) matter enough to replace the verbatim OBJ
  as the calibration mesh. Decided by the diff in PR F.
- Which OCIO config seeds the repo: Blender's 4.x config (CC0, ships AgX) with the ACES views
  added, or an ACES studio config with an AgX view added.
- When the comparison framework design is written: after the standards pass (current plan) or
  pulled earlier.
- Whether the orphaned 8K LFS object is worth a support request.
- The material contract and editor split above (section 3): agree, amend, or reverse.
