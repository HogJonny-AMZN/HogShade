# The Board

**Status:** Living. Updated at the end of every increment, as the definition of done says.
**Updated:** 2026-09-27, evening: #26 merged and `v0.2.0` tagged; the standards pass's remainder as a PR.

[`../ROADMAP.md`](../ROADMAP.md) is the *roadmap*: the tracks, the phases, the order, what each is
for. [`../handoffs/CURRENT.md`](../handoffs/CURRENT.md) is the *handoff*: where work is right now and
what the owner said. The decision log is the *index of decisions*. None of them is a tracker, and until
today ideas said out loud landed in the decision log's "not yet scheduled" section without a cost or a
trigger. Owner, 2026-09-27: "we should employ the same kind of ideas about evolving roadmap, board,
icebox, etc. here." Shape from the LargeWorlds board, which took it from SpriteJammer.

**This is the tracker.** What is in flight, what is blocked and on whom, and where every idea that has
been said out loud actually went.

**A mentioned feature is not a work order.** It goes in the Icebox with a cost and a reason. It is built
when the owner says so, when it blocks work in flight, or when it is smaller than the conversation
about it.

**Reading the ids.** Rows carry the roadmap's own names (tracks A to E, phases C2 to C6, E1 and E2) or a
PR letter. A struck-through row is done and stays for the record with its PR number.

---

## Gates: decisions only the owner can make

A gate is not a task. It is a question that blocks tasks, and the cost of guessing is a rewrite.
**Nothing downstream of an open gate may be committed to.**

| Gate | State | What it blocks | What it needs |
| --- | --- | --- | --- |
| ~~**G1 · Track A, open-source clearance**~~ | 🟢 **CLOSED 2026-09-27.** The clearance half settled by the owner's account (`hog_color` the owner's own toolbox rewritten; Job_Orchestrator / BATS used here, never distributed; the backup repo gone); the generated profile's dev-checkout path dropped. The profile housekeeping is account work with no strong relevance to HogShade (owner) and left the roadmap; parked in the agent's memory until the owner names a home | — | Done: roadmap track A closed; `tools/check_hygiene.py` guards the retired spellings; publishing anything from this repo is the owner's call alone |
| **G2 · Which OCIO config seeds the repo** | 🟡 **Open.** Blender's 4.x config (CC0, ships AgX) with the ACES views added, or an ACES studio config with an AgX view added, or an own AgX view from the published transform | Track E colour management: scene-referred ACEScg captures, the AgX default view, the ACES alternative, the wgpu host's numeric twin of the view | The owner's pick; the roadmap's colour-management item holds the trade-off |
| ~~**G3 · The material contract and editor split**~~ | 🟢 **CLOSED 2026-09-27.** Owner: "let's not build the material editor here, but let's own the core generalized material schema / data." [ADR-009](../decisions/ADR-009-hogshade-owns-the-material-schema.md) | — | Done: HogShade owns the schema, the document, the mapping and the Python library; LargeWorlds owns the editor; dependency one way |
| **G4 · When the comparison framework design is written** | 🟡 **Open.** The current plan says after the standards pass; the owner may pull it earlier | The pixel-identical screenshot diff of both legacy ports against the legacy effects (plan task 18's open half); the C3 comparison view; the bake comparisons | A date relative to the standards pass |
| **G5 · Does the owner's edited shader ball replace the verbatim OBJ?** | 🟡 **Open.** The legacy scene carries UV sets and CPV values the verbatim OBJ lacks; the diff was meant to happen while Maya was open in PR F and did not | The calibration mesh in track E's calibration scene; the CPV mask and AO features in C4 need a mesh that carries them | A diff of `testFiles/v2.0/shaderBall_pbr_IBLenv.ma` against `content/shaderball/`, then a yes or no |

---

## Now

| Item | Cost | Notes |
| --- | --- | --- |
| **S4 · the library of materials, pre-spec design** (`docs/s4-library-design`, [#40](https://github.com/HogJonny-AMZN/HogShade/pull/40) open; [design](../design/2026-10-02-material-library.md)) | ½ d, drafted; the owner locks | Eight questions with recommendations: standard documents plus the reverse table, a roster of six families and sixteen children with sourced values, title and provenance as document fields, the layout, the wgpu contact sheet as the gate, the texture set after track E's conventions. Nothing built until locked |
| ~~**The standards PR: E501 on and `_LOGGER` across the tree**~~ | — | ✅ **Merged 2026-10-02 as [#39](https://github.com/HogJonny-AMZN/HogShade/pull/39)**, with the owner's point folded in: `python.md` says what a log is for and the code leaves the record `E501` enforced in `pyproject.toml`; the 24 lines over 120 wrapped (docstrings reflowed, WGSL harness strings one statement per line, long literals split inside their parentheses); the 30 modules without a logger given `_LOGGER` from `_MODULE_NAME` per `python.md`, with the import and the metadata block where those were missing too. Then, on the owner's point that a log is for humans and for an agent spelunking a failed run: `python.md` says what to log, and the library, the host, the tools and the jobs leave that record (inputs, decisions, artifacts), two tests hold it. 358 tests. |
| ~~**S3 · the wgpu binding, the build**~~ | — | ✅ **Merged 2026-10-02 as [#38](https://github.com/HogJonny-AMZN/HogShade/pull/38)**; Copilot's four findings fixed (the binder slot seeded, a malformed `types` a finding, the host-coverage wording, the plan's API) `bind(resolved, "wgpu")` through the wgpu host map (39 entries, every unbound parameter a recorded `Unbound`), `Scene.material`, `viewport.py --material`, three documents under `content/materials/`, the wgpu pictures recaptured with the schema's defaults; 199 material tests. Merge when read |
| ~~**S3 · the wgpu binding, spec and plan**~~ | — | ✅ **Merged 2026-10-02 as [#37](https://github.com/HogJonny-AMZN/HogShade/pull/37)** (Copilot's four findings fixed: the schema's defaults win, a non-normative excerpt, `Unbound`, `bind()` takes a `Resolved`) | `bind(resolved, "wgpu")` through a wgpu host map (parameter to frame field and component, or `unsupported` with a reason, the S2 coverage rule); `Scene.material` replaces the hand-set fields; `viewport.py --material`; the library's first two documents. Owner approves the spec, then the build |
| ~~**S2 · the generators, the build**~~ | — | ✅ **Merged 2026-10-01 as [#35](https://github.com/HogJonny-AMZN/HogShade/pull/35).** The Maya block generated between markers from the schema and the host map, the macros retired, `--check` in CI, the docs reference; 180 tests. The GUI picture run landed after the merge (the owner restarted the orchestrator): master's shell and the regenerated shell render pixel-identical in one session; the new pictures are the baseline, in the follow-up PR with Copilot's two post-merge findings |
| ~~**S2 · the generators, spec and plan**~~ | — | ✅ **Merged 2026-10-01 as [#34](https://github.com/HogJonny-AMZN/HogShade/pull/34)** (Copilot's four findings fixed) |
| ~~**S1, the second review's fixes**~~ | — | ✅ **Merged 2026-09-28 as [#33](https://github.com/HogJonny-AMZN/HogShade/pull/33).** `when` on several sources and the condition-set rules, `validate()` never raises, `convert()` refuses an invalid material; every review metric at 7 or above. The re-review of #31 had scored error handling 6 and found the cutout mapping ignored `has_alpha`; the third review ran before the PR opened and added the condition-set rules; 158 tests |
| ~~**S1 · the material schema files and `hogshade.material`**~~ | — | ✅ **Merged 2026-09-28 as [#31](https://github.com/HogJonny-AMZN/HogShade/pull/31).** Four `*.material-type.json` (the standard with OpenPBR names, legacy v2 and v1 typed from the structs and the shell with a test tying them, lambert), three conversion tables under the coverage rule, `load`, `validate`, `resolve`, `convert`; 133 tests; the wheel carries the data; mayapy imports it. Amendments in the spec's last section. Merge when read |
| ~~**The standards pass, remainder**~~ | — | ✅ **Merged 2026-09-27 as [#27](https://github.com/HogJonny-AMZN/HogShade/pull/27)**; the design's cross-repo catch-up and the O3DE lessons as #28, the glossary and `check_vocabulary` as #29, S1's spec and plan as #30. The decision log's working knowledge into `Docs/knowledge/toolchain.md` and `maya-scripting.md`, its repository state into the handoff, its open questions to the gates; specs and plans under `Docs/superpowers/` with every link and reference fixed (design and handoffs stay at the top level, as in the sibling repos). Merge when read |
| ~~**Phase 2 close**~~ | — | ✅ **Merged 2026-09-27 as [#26](https://github.com/HogJonny-AMZN/HogShade/pull/26)**, tagged `v0.2.0`; gate item 5 deferred to track E by the merge |
| ~~**The standards pass**~~ | — | ✅ **Merged 2026-09-27 as [#25](https://github.com/HogJonny-AMZN/HogShade/pull/25).** Two standards pages, the ledger, Copilot's instructions, ADR-001 to 008, status on every document, the project review with its ten fixes, `tools/check_hygiene.py` from Copilot's review of it; thirteen findings answered |
| ~~**PR H · the process port** (#20)~~ | — | ✅ **Merged 2026-09-27 as [#20](https://github.com/HogJonny-AMZN/HogShade/pull/20).** The journal, `Docs/standards/`, the PR template, `tools/check_docs.py` in CI, the `local-review` skill, the BATS case, this board; Copilot's two findings fixed |
| ~~**PR I · the README as the case for the repo**~~ | — | ✅ **Merged 2026-09-27 as [#21](https://github.com/HogJonny-AMZN/HogShade/pull/21).** WYSIWYG as a tolerance, the measurable value of a portable look, physics beside game features, pros and cons; the pitch for the agent loop; the checker hardened after its first local review (unclosed fences, links above the root) |
| ~~**PR G · the legacy v1 port** (plan task 18)~~ | — | ✅ **Merged 2026-09-27 as [#19](https://github.com/HogJonny-AMZN/HogShade/pull/19).** One Disney BRDF, not three; selectable in both hosts; Copilot's two findings fixed in `569b5bf`. The pixel-identical diff against the legacy effect waits on G4 |
| ~~**PR F · the Maya shell**~~ | — | ✅ Merged 2026-09-27 as #18 (the gate passed on the `hogshade_maya_gui` worker) after #15 to #17 (the orchestrator profile, workers, kill script, agent files) |
| ~~**PRs A to E · spike, skeleton, GPU harness, BRDF toolbox, legacy v2 port, wgpu host**~~ | — | ✅ #9 to #14, 2026-09-20 to 26 |

---

## Next: unblocked, ready to pick up

Nothing here is committed to. Each is sized; the owner picks. The agreed order (decision log, section 1)
is the first two rows, in that order.

| Item | Cost | Notes |
| --- | --- | --- |
| **A job sets and clears its own environment on the resident worker** (`HOGSHADE_VARIANT` from an earlier job leaked into the next; S2 build) | ½ d in `hogshade.jobs` | Observed 2026-10-01: the crashed IBL check wrote under `legacy-v1/` with no variant passed. The job module should set its environment from parameters and restore it in `finally` |
| **Job providers and capability discovery** (owner note, 2026-09-27) | 1 d on the Job_Orchestrator dev checkout, ½ d here | Decision log, "Job providers and capability discovery". Here: `hogshade.jobs` discovers its jobs by scanning, a test fails on a job without a `MANIFEST` (the Maya job was unregistered for a day). There: a provider field in the profile, `bats_list_jobs` and `bats_describe_job`, a CLI flag. Cross-repo; the HogShade half can go first |
| **The history-log fix, verified** | one job | `tools/maya/_session.py` now stops Script Editor mirroring at the end of a check (PR H); the next Maya job proves the committed log stops growing |

---

## Blocked

| Item | Blocked on |
| --- | --- |
| **Phase C3 · OpenPBR model, MaterialX carrier, parameter schema** | **G4** because the roadmap says E's calibration capture runs in `maya_dx11` before C3 opens; G3 closed 2026-09-27 (ADR-009); the schema's design is locked and S1 is built (Now) |
| **The comparison framework** (roadmap, track E) | **G4** for its design date. Design first, then spec, then build; `tools/wgpu/viewport.py` is replaced, not extended. Its design states the cross-host conventions before any diff: camera handedness and projection, the NDC depth range, the UV origin, the up axis and units, the HDR rotation (the blind-spots design names the last two; the owner asked on 2026-10-01 that coordinates be accounted for) |
| **Colour management: ACEScg, AgX default, ACES alternative** (track E) | **G2** |
| **The pixel-identical screenshot diff of v1 and v2 against the legacy effects** | The comparison framework |
| **Track D · the SpriteJammer tiers** | C5's published core WGSL; SpriteJammer's own board carries the consuming rows |
| **Test assets and the calibration scene** (track E) | **G5** for the mesh; the procedural test-data tool can start any time and is in the Icebox with a cost |
| **The shader-specialisation ADR** | The standards pass writes it; the FXC canary (14 s with one model, 24 s with two) is the evidence it cites |

---

## Icebox: said out loud, not scheduled

Everything mentioned in conversation lands here with a cost and a reason, rather than being built or
forgotten. **An empty Icebox means ideas are going missing.**

### Ideas said out loud

| Item | Cost | Why not now |
| --- | --- | --- |
| **Track F, pre-spec design: the material library and the repo as a getting-started shading solution** (owner, 2026-09-27; drafted 2026-10-02 as the S4 design, Now) | ½ d of conversation and writing, after or with the schema design | Verdict: awesome as a scope decision, and it changes what "done" means for the repo, so it gets a design the owner locks before anything is built. Roadmap track F |
| **The base material library, constants only** | 1 d once the schema is locked | Verdict: awesome; the schema's first consumer and its test data. Waits on the schema's design (Next) |
| **The texture-based set, small, CC0 or generated here** | 1 to 2 d, with track E's texture conventions | Verdict: good, with provenance as a rule from the first texture; drives the cook with real content. After the base set |
| **AI-driven material and texture generation, as gated research** (owner names Nano Banana Pro) | a design first; the validation harness 2 to 3 d; the generation job 1 d on the Python worker | Verdict: awesome as research, meh as a content source until gated. A generated normal is a picture of a normal, not a derivative of the height; the harness (re-derived normals, tileability, the registered-grid probes, colour space, cook, render) turns it into an experiment with a verdict. The model's terms for shipped assets are verified first. A textbook gated BATS workflow. Owner's bar, 2026-09-27: generated content is slop until validated, registered and as consistent as a Megascans-grade library; the Ubisoft PBR model and its ComfyUI extension are candidates under the same harness and the same skepticism |
| **Procedural test data: hydrate everything** (owner, 2026-09-26; registered grids 2026-09-27) | 1 to 2 d for the tool and the first set (Macbeth chart, grey card, ramps, UV grid with orientation marks, normal tiles with a known slope, height tile, alpha cutout, fallback primitives) | Track E; nothing consumes it until the comparison framework (G4) reads it. The IBL cook is the pattern |
| **Bake comparisons: Blender required, Maya, Toolbag and Substance optional** (owner, 2026-09-26) | 2 to 3 d for the Blender path and the diff tool; ½ d per optional tool | Track E; needs the mesh set (G5) and the framework's report format (G4) |
| **This repo's own renderer and viewer, structured like `hog_rendering`** (owner, 2026-09-26) | grows with the framework | `hogshade.wgpu_host` is the seed; it becomes a viewer when the comparison framework needs one |
| **Legacy assets as candidates: the owner's shader ball, `rocks.ma`, the Basic and IBLbaker texture sets** (owner, 2026-09-26) | ½ d each, "done better", nothing copied as is | The re-clone at `D:\Depot\Maya-PBR-BRDF-VP2` is for comparison only; a phase asks for each when it needs it (G5 for the ball) |
| **The base scene in four forms: Maya, Blender, glTF, FBX** (owner, 2026-09-26) | ½ d once the calibration scene exists | Track E, after G5 |
| **Visual proof page before merging visual work** (owner preference, from the sibling project) | ¼ d per PR that changes a picture | A habit, not a build; offered per PR |
| **E2 leftovers: BC6H output, a numba mip-0 resample** | ½ d each | Deliberate deferrals from the E2 plan; BC6H when a 1024 cube ships, the resample when 2048 cooks are routine |
| **Self-describing workers** (`bats_describe_worker`: DCC and version, plugins, viewport device, GPU) | 1 d on the dev checkout | Follows job providers; the owner's question of 2026-09-27 ("shouldn't the AI just be able to ask the running orchestrator?") |
| **Workflows as catalogued lists of job references with edges** | a design first | Does not exist in the orchestrator; needs typed job inputs and outputs (providers) before it can |
| **Dev-checkout to-dos: profile by path, sidecar `env_profiles` mappings, a PID-based kill script, the `ready_workers` count bug in the MCP status** | ½ d each | `Docs/knowledge/job-orchestrator.md`; each removes a fold or a workaround HogShade carries today |
| **Material live link: Maya host parameter changes published to a running engine** (track D) | after the command bus and the schema | Roadmap; the bus must not preclude it |
| **A Substance Painter GLSL host** (C6) | cheap once the GLSL host exists | Optional tool; C6 |
| **Copilot's suppressed notes on #19 and #20 for the standards-pass review of `hosts/` and `tools/maya`**: which vertex colour set carries AO in `hogshade.fx` (COLOR0 versus COLOR1) and whether the v1 path reads the one the v2 path documents; per-model debug-mode defaults in `ibl_check.py` once the model is a job parameter | ½ d inside the standards pass | Neither changes a verified picture today; both are the kind of drift the pass reviews host by host |
| ~~**The studio checkout path in the generated orchestrator profile**~~ | — | **Done 2026-09-27:** `package_paths` is dropped from the generated profile and excluded in `make_profile.py`, so a regeneration stays clean |
| **The weekly review routine** (owner, 2026-09-27): a Friday cloud routine that reads the journal, the board, the handoff, the decision log, the PRs and CI runs, and delivers a report on CI health, process compliance, what to streamline, agentic context engineering, projections against the roadmap, and the experiments and maybes that did not prove out and need redacting, reversing or displacing; industry practice and around-the-corner thinking both, each claim cited; then nudges the owner's phone, because "generation is a thing, reading and following up is a very different problem" | ½ d pre-spec design with the owner, 1 to 2 d for the skill, ½ d for the routine and the nudge, the first run measured | Cross-repo (HogShade, LargeWorlds, SpriteJammer, Job_Orchestrator all have the sources) and design-first, on SpriteJammer's devblog design (`docs/design/devblog.md`), which already settled the substrate: a routine plus a skill, a branch and a pull request as the artifact, private sources read and a redaction gate before anything leaves. Open for the owner: which repos and where the reports live; SMS proper (Twilio, with US A2P registration friction) against a push channel (ntfy or Pushover, one HTTP POST and one secret) with the GitHub Mobile review request as the zero-cost baseline; and the follow-through loop, where each report opens with last week's items and whether they were acted on. Decision log, "The weekly review routine" |

| **The agent loop as research: heartbeat, execute, communicate** (owner, 2026-09-27: "if Claude or a harness doesn't provide the framework, how do we build that as research? OpenClaw I stopped using because almost everything it does I can just do with AI harnesses these days, but I could have it run a heartbeat, execute things, telegram and communicate with me") | ½ d design lock; then per lane: a Telegram bridge job in the orchestrator (1 d), `claude -p` as an orchestrator worker job with a permission allowlist (1 to 2 d, the risky one), a scheduled-job type in the orchestrator (½ d); the weekly review is the first consumer | Design first. The finding that shapes it: the loop is four parts and no one substrate has all four. Trigger: a cloud routine or a GitHub Actions `schedule:` for repo-only work, the orchestrator for anything needing this machine (Maya, the GPU). Context: the repo's own docs, already built for it. Act: a repo skill in the cloud, or headless Claude Code (`claude -p`) run as an orchestrator job here. Report and nudge: a branch and PR, plus a Telegram bot (free, one token, one HTTPS POST out, long-poll in) as the two-way channel, which also gives inbound commands ("run the review", "status") that submit jobs. That reconstructs what OpenClaw provided on infrastructure the owner already owns, with the agent as a worker and the same DoD (branch and PR, never merge). Research questions: unattended permissions without `--dangerously-skip-permissions`, cost per run, what a run may touch, and whether the owner reads the result (the follow-through loop). Decision log, "The agent loop as research"; the pitch: `Docs/design/2026-09-27-pitch-bats-as-the-agents-body.md` |
| **Scene direction from a phone** (owner, 2026-09-27): "show me a view" returns an in-editor render; "I want such and such changes" triggers a workflow (a generative step, cook and bake, editor load and placement, a render of the same view) posted to the phone; next generation, annotation tools in the view's context | design first; the MVP is the character workflow plus a named view and a vision-model job that reads phone markup (2 to 3 d once the agent loop and job providers exist); the in-context annotation tool is a product (weeks) | Verdict: the loop is awesome (a view is the right unit; direction happens on a picture), the web app is meh as a first step (the phone's own markup plus a sentence is zero UI), and the generative step is the weak link, so it is a choose-between-N gate, never an oracle. Waits on the editor as a worker (the row below) and on job providers. Decision log, "Scene direction from a phone" |
| **A path-tracing baseline, and a ray-tracing native app "for the coolness factor"** (owner, 2026-09-27, "long term to do") | the baseline: 2 to 3 d for a reference path tracer over the core's NumPy twins or a small wgpu compute kernel, on the calibration scene; the app: weeks | Long term by the owner's own words. The baseline is the more valuable half and belongs to track E: a ground-truth render of the calibration scene that every real-time host is measured against, the way the white furnace measures a lobe (OpenPBR's reference is a path tracer, so C3's model is judged by one). The native app rides on the repo's own renderer row above and on wgpu ray-query support in `wgpu-py`, which is not proven here yet. Neither starts before the comparison framework (G4) says what a baseline must produce |

### Owner-only steps

| Item | Notes |
| --- | --- |
| **Merge the legacy pointer PR and close the getting-started issue** on `hogjonny/Maya-PBR-BRDF-VP2`; archive that repo; delete `legacy-pointer` here | Roadmap, track B |
| **The orphaned 8K LFS object** | A support request, optional; the file is gitignored and never committed again |

---

## How this stays honest

- **Every increment's PR updates this file** in the same change, as the definition of done says for
  the handoff. A row that lands gets its PR number and a strike-through; nothing is deleted.
- **A row's cost is a guess until someone measures it**, and says so when it changes.
- **An idea from conversation goes to the Icebox in the same session it was said**, with the date and
  the owner's words where they matter. If it is not here, it has gone missing.
- **Gates close only with a recorded decision**: a decision-log entry naming the date, an ADR, or a PR.
- **Duplicate ids are a bug.** Row names are the roadmap's; a new lane gets a letter the roadmap does
  not use.
- When the board disagrees with `git log`, `git log` is right about the past and the board is wrong;
  fix the board.
