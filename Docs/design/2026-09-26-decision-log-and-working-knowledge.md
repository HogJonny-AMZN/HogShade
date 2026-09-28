# Decision log and working knowledge

**Status:** Living. Appended whenever a direction or decision is made in conversation and is not yet
in a spec, plan or ADR. Split on 2026-09-27 (the standards pass's remainder): the working knowledge
moved to `../knowledge/` (`toolchain.md`, `maya-scripting.md`; the process lessons are the definition
of done, the skills and the failure-modes ledger), the repository state to `../handoffs/CURRENT.md`,
the open questions to the board's gates. This file is the decisions and directions only. The conversation is not the record; this file and the documents it links
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
3. (Done 2026-09-27, #25; remainder on the board.) The standards pass (`ROADMAP.md`, "The standards pass"): coding standards and agent context,
   review of `core/`, `hogshade/`, `hosts/`, `tools/`, ADRs for the structural decisions including
   shader specialisation.
4. (Done 2026-09-27, the close PR.) Phase 2 close: deviations list, status rows, roadmap C2, VERSION `0.2.0`.
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
| E1 cook conventions (face convention, roughness linear in mip, E over pi, LUT) | `Docs/superpowers/specs/e1-ibl-cook.md`; cooked manifests |
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

### Material data, contracts and editor: where they live (owner asked 2026-09-26; decided 2026-09-27, ADR-009)

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

Decided by the owner on 2026-09-27 as recommended ("let's not build the material editor here, but let's own
the core generalized material schema / data"): `../decisions/ADR-009-hogshade-owns-the-material-schema.md`.

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

`Docs/superpowers/{design,specs,plans,handoff}` is the cross-repo convention as first stated; HogShade's
specs and plans moved there on 2026-09-27 (the standards pass's remainder). Design and handoffs
stayed at the top level, because that is where LargeWorlds and SpriteJammer actually keep them and
consistency with two existing repositories won over the convention's first wording; the docs map
records the deviation. The pre-spec design stays a hand-written lock of what was discussed
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
day on the dev checkout, half a day here. Owner's follow-up: "shouldn't the AI just be able to ask
the running orchestrator about workers, workflows, jobs/tasks and capabilities?" Yes; that is the
point. Today the running orchestrator answers about workers (types, state, submit, poll, results)
and nothing about jobs, because it holds a queue and a pool, not a catalogue. Providers are how it
learns the catalogue, once, at start; the agent then asks the orchestrator. Two further layers the
question implies: workers describing themselves at boot (DCC and version, plugins, viewport device,
GPU) behind a `bats_describe_worker`, and workflows as catalogued lists of job references with
edges, which do not exist yet and need their own design. Here only, plus the to-do list in
`Docs/knowledge/job-orchestrator.md`.

### The board (owner, 2026-09-27; decided)

"We should employ the same kind of ideas about evolving roadmap, board, icebox, etc. here."
`Docs/plan/BOARD.md`, on the LargeWorlds shape: gates first (G1 clearance, G2 the OCIO config, G3 the
material contract split, G4 the comparison-design date, G5 the shader-ball mesh), then Now, Next,
Blocked on whom, and an Icebox seeded from this log's section 3, the roadmap's unscheduled track E
items, section 6's open questions and the orchestrator to-dos. The roadmap stays the map of tracks and
phases; this log stays the index of decisions; the board is the tracker. Section 3 of this log stops
growing: a new idea goes to the Icebox with a cost, and a decision that schedules one is recorded here
with a pointer to its row.

### The weekly review routine (owner, 2026-09-27; soft, design first)

Owner: "something like a cloud cron job that runs on Fridays and does a deep dive on the journal and
other context, to deliver a report on CI, improvements, things to streamline, etc.; it needs to both
follow industry standards and known quantities, but also think outside of the box, anticipate and look
around corners and think about agentic context engineering and agentic development practices
(including accessing the projections, and being clear about experiments and maybes that don't prove out
and need to be redacted, reversed and displaced later)." And: "what would be really cool is if it could
text SMS me when this report is done so I actually review and look at it; generation is a thing,
reading and following up is a very different problem."

Assessment. The substrate exists and SpriteJammer already designed its twin: the Sunday devblog
routine (`docs/design/devblog.md`, locked 2026-09-13) runs a repo skill from a cloud routine, clones
private repositories, writes to a branch and opens a pull request, and found that routines have no
notification of their own. The weekly review is that design's review-side counterpart: a
`weekly-review` skill runnable locally or by a Friday routine, reading the journal, board, handoff,
decision log, merged and open PRs, Copilot threads and CI run history, and writing
`Docs/reviews/<date>-weekly-review.md` on a `claude/` branch with a pull request. The report's contract:
every claim cites a file and heading, a commit, a PR or a run id; it proposes and never edits the
board; sections for CI health, process compliance against the DoD, streamlining candidates (a manual
step the journal repeats becomes a skill or a job), agentic context engineering (what agents got wrong
and which instruction would have prevented it, the size and staleness of the knowledge files),
projections against the roadmap, a verdict table for experiments and maybes (proved, unproven,
redact or reverse or displace, with the document that holds the belief), and an explicitly labelled
speculative section for around-the-corner thinking. The follow-through loop is the part that answers
the second message: each report opens with last week's items and whether they were acted on, and
the nudge carries the three-line verdict and the PR link, not "report ready".

The nudge. SMS proper means Twilio from inside the routine with a secret in the cloud environment
and, in the US, A2P 10DLC or toll-free registration even for personal use (as of the assistant's
knowledge; verify before choosing). A push channel does the same job with one HTTP POST and one
secret: ntfy (free, open source) or Pushover (one-time fee). GitHub Mobile's review-request
notification is the zero-cost baseline and needs nothing. Recommendation: push first, SMS only if
the owner wants SMS specifically. Not built; the board's Icebox row carries the cost and the open
questions. A memory records the direction for the other repositories.

### The case for the repo, stated for the README (owner, 2026-09-27; principles)

Owner: the README must be "ultimately clear about the direction, needs, benefits and pros and cons
of this repo"; "WYSIWYG everywhere is a goal (is it possible?)"; "portable look direction is more
measurably valuable than I can state"; "rendering tech on the physics front doesn't always meet game
needs; game-like features, especially common ones, are a boon; game-like hacks make the world work
when you don't have path tracing correctness." Three principles now on the README: WYSIWYG is a
tolerance, not a promise, and the repo's job is to make every difference attributable (the BRDF is a
third; inputs and proof are the rest); the value of a portable look is stated as things to measure
(parameters authored per material, look-dev decisions re-made, time to attribute a difference, hosts
updated per change, regressions caught before a render, time to first picture in a new host, bake
error per map), to be replaced with numbers when the comparison framework publishes them; and the
three kinds of feature (physics, surface authoring, engine) with surface authoring named as the bulk
of the user-facing value and the legacy models kept as legitimate non-conserving peers. The pros and
cons table is honest about the toolchain, the FXC canary, the deferred limits, OSL as a second
implementation, and the optional orchestrator.

### The agent loop as research: heartbeat, execute, communicate (owner, 2026-09-27; soft, design first)

Owner: "my desires and expectations ... if Claude or a harness doesn't provide the framework, how do
we build that as research? OpenClaw I stopped using because almost everything it does I can just do
with AI harnesses these days, but I could have it run a heartbeat, execute things, telegram and
communicate with me."

Assessment. What the harness provides today: cloud routines (a schedule, private repositories
cloned, repo skills, a branch and a pull request; webhook triggers on GitHub events), a session-only
local cron that dies with the session, a terminal or phone push only while a session is attached, and
no SMS or Telegram. What it cannot do: reach this machine, so nothing that needs Maya or the GPU. What
the owner already owns: the orchestrator, which is "execute on my machine" with resident workers, a
queue, a manifest per job and an MCP. So the loop splits into four parts and no single substrate has
all four:

| Part | Repo-only work | Machine-bound work (Maya, GPU, bakes) |
| --- | --- | --- |
| Trigger (heartbeat) | A cloud routine, or a GitHub Actions `schedule:` running the Claude Code action | A scheduled-job type in the orchestrator, or Windows Task Scheduler submitting one |
| Context | The repo's docs: journal, board, handoff, decision log, knowledge files | The same, plus the orchestrator's own state |
| Act | A repo skill | Headless Claude Code (`claude -p "/skill"`) run as an orchestrator job on a Python worker, with a permission allowlist |
| Report and nudge | A branch and a pull request; a Telegram bot message with the verdict and the link | The same; the Telegram bridge is one job that any job can call |

Telegram rather than SMS: free, a bot token, one HTTPS call out, long polling in, and it is two-way:
"run the review" or "status" arrive as messages and become submitted jobs. That is what OpenClaw
gave, rebuilt as three small orchestrator pieces (a Telegram bridge job, a `claude -p` worker job, a
scheduled-job type) on infrastructure that already exists, with the agent as a worker and the same
definition of done (branch and PR, never merge). GitHub Actions on a cron with the Claude Code action
is the industry-standard equivalent for repo-only work and worth measuring against the routine: it
takes any secret and any notifier but needs an API key in the repository and pays per run.

Research questions, in order: unattended permissions (an allowlist per job, never the skip flag,
measured by what a run tried to do and was refused); cost and duration per run; the blast radius (a
run writes to a branch and a report, nothing else, enforced by the worker's environment); and the
follow-through loop, whether the owner reads and acts, which is the measurement the whole thing is
for. The weekly review is the first consumer; the design lock comes before either is built. This
belongs to the Job_Orchestrator dev checkout as much as here, and the board row says so.

Owner, on reading this: "so BATS becomes my OpenClaw feature set!?" Yes, with the distinction that
BATS is the body and the harness is the brain: OpenClaw was the whole agent, and what the owner
kept wanting from it (heartbeat, execution on this machine, a channel) is what the orchestrator is
three small pieces short of. Recorded as the framing for the design lock. Then: "that would be rad from the standpoint of I didn't think of it but it also makes sense
(as long as my local machine is up)", and "it also cements BATS as radical". The machine-up caveat is
the seam between the two lanes: the cloud routine covers repo-only work while the machine is off, and
a scheduled job on the machine runs as soon as possible after a missed start, so a heartbeat missed
asleep fires on wake rather than being lost. Direction agreed in principle; still design-first.

Owner, later the same day: "Claude remote is basically some part of this: something local on my
machine I can interact with via my Claude phone app and walk away. BATS provides potentially the
bridge there for almost anything!?" Yes: Remote Control gives the interactive channel (phone to a
live session on this machine) and nothing durable; the session's cron dies with it and nothing runs
with no session open. So the channel has two halves: Remote Control for the interactive case, the
bridge for unattended jobs and for any worker that is not Claude (the agent-agnostic requirement).
BATS persists under both. The design lock treats the bridge as required and Remote Control as the
convenience it already is.

### Scene direction from a phone (owner, 2026-09-27; soft, design first, with a verdict)

Owner: "show me a view of the witch's hut, and it returns an in-editor rendering; then 'I want such
and such changes to this view' and the workflow triggers, the gen-AI happens, the bake and cook, then
editor loading and positioning, the object is placed, a render happens, and it's posted to your phone
on vacation. Next gen: a web app with grease pencil and annotation tools for this context in view."
Also: "tell me when my ideas are awesome or push back when meh."

Verdict, given both ways. Awesome: the loop, because a view (camera plus scene state) is the unit a
round trip can preserve, and direction happens on a picture, not a spec; and annotation as the
instruction channel, which is how art direction has always worked. Meh as the first step: a web app;
the phone's own markup on the render plus a sentence, read by a vision-model job, is zero UI and the
right MVP; in-context grease pencil is the generation after. Pushed back: "the gen-AI happens" hides
the least deterministic step, so it is a choose-between-N gate (it proposes four, the owner picks
from the phone), never an oracle; and "editor loading and positioning" needs the editor to be a
worker with a command bus, which SpriteJammer's command-bus spike seeds and LargeWorlds does not
have, so that long-shot row is the prerequisite. Recorded in the pitch's "Around the corner" and the
board.

### Horizons for the gated workflows (owner, 2026-09-27; estimate)

Owner: "I surmise we could get this running in a month, not a year." Verdict: half right. A first
gated workflow on existing assets is a month past the three pieces, because a workflow is one Python
job that calls jobs and blocks on a bridge reply at each gate, and typed inputs and outputs can be
manifest conventions before they are a schema. The generative 3D steps (Thursday's blockout and
model) and the editor as a worker (Saturday) are the year-out parts: the first is unproven anywhere
in this repo, the second needs a command bus LargeWorlds does not have (SpriteJammer's spike proved
the shape). The pitch now says the split rather than "a year" for both days. Then the owner: "we already have an engine that starts and BATS can
operate (for work, not hobby), and that is Unreal", and "the model workflow is complex, you are
right, at least a couple of weeks". So Saturday's prerequisite exists at work today (the
orchestrator's Unreal Editor worker type) and the long shot is only the home engine; Thursday's
generative steps carry the owner's own floor of a couple of weeks. The pitch says both.

### The material library, AI generation, and the repo as a getting-started shading solution (owner, 2026-09-27; soft, design first, with verdicts)

Owner: "we can also build a small material library here, one set of broad base materials that are
constants and params only, another smaller set texture based; I would like to consider some AI
driven material and texture generation tooling and workflows here. I know Nano Banana Pro
theoretically can make material texture channels including depth maps and normal maps. Great vein
for research and learning. This could become a base shading solution and library (a getting started
repo for any of my games)."

Verdicts. The constants-only library: awesome, the schema's first consumer and its test data, ships
with the schema. The texture set: good, small, provenance a rule from the first texture (CC0 or
generated here). AI generation: awesome as research, meh as a source until gated; a generated
normal is a picture of a normal, not a derivative of the height, colour space and tiling are luck,
runs differ; the research question is validation, and the harness (normals re-derived from height
and the disagreement measured, wrap-around diff, the registered-grid probes, a schema colour-space
check, the cook, a render in every host) makes it an experiment with a verdict and a gated BATS
workflow (generate four, validate, pick one from the phone). The reframing as a getting-started
shading solution is a scope decision: roadmap track F, design first. The model's terms for
generated assets in a shipped game are a fact to verify before any generated texture is committed.

Owner, on the verdict: "agreed, meh on AI material channels and data: lossy, not coherent, the
opposite of quality, which is what the best dialled-in baking actually gives you. Still useful as
research and experimentation. Then there are other solutions like the Ubisoft PBR model and ComfyUI
extension, worth looking at, but I have the same skepticism there. If gen-AI is considered slop
until its output is validated, registered and as consistent as, say, a high-quality texture library
like Quixel Megascans, it's just a shortcut or a toy. One way to stand above the slop is intent and
accuracy, the highest quality assets and rendering." Recorded as the quality bar on track F: the
validation harness is the deliverable and any generator is a plug-in evaluated against it.

### The material record is JSON; MaterialX authors Primes and is the interchange (owner, 2026-09-27; locked)

Owner: "do we need our own material schema / data storage, a material asset or a material instance?
Yes. Should that be MaterialX? I don't know; MaterialX seems like the approach to author a base
material like ours (or a derivative of it)." Answered and locked as question 10 of the schema design:
MaterialX is where a base material or a derivative, a Material Prime, is authored, and it is the
interchange every resolved material exports to and imports from; it has no parent-child delta, no
per-project migrations, no engine-validated extension blocks, and reading it needs a 5.5 MB C++
library, so it is not the record. The record of an asset is the O3DE-shaped JSON document against
the schema; an instance is the engine's in-memory overrides and never a file. The direction doc's
2026-09-20 "Interchange" row, written before the Prime noun existed, is amended in place with the
date. The other nine questions of the design remain open; the design stays Exploring.

### The schema design locked (owner, 2026-09-27)

All ten questions answered; the design's table keeps the owner's words. The calls that shape S1:
the legacy models are separate material types sharing the document format, with conversion tables
as the comparison route ("separate and legacy, but then what's the best route to compare???", and
the answer is convert, not share); texture packing is out of the schema ("a cook and runtime loader
question, not material authoring; they are optimizations"); HogShade's standard is the base
standard for every downstream project; emission in nits; the version mechanism from the first file
with nothing brought forward; specular occlusion in the surface group as a game and taste choice;
MaterialX an optional extra (measured: Maya's Python lacks it, Blender's ships 1.39.4); the schema
as package data; the three truths of question 10. Formalised in the design; ADR-009 stands.

### `hog_color`'s history settled; the old toolbox identifiers retired (owner, 2026-09-27; locked)

Asked what the roadmap's "private backup repo" line meant, the owner removed that repo and then settled
the lineage question in four statements: the experimental colour toolbox was written on the owner's own
time and machine first; a fork of it was used at a studio and never went into a production tool; that
studio has been shuttered and no owner or code base remains; `hog_color` in LargeWorlds is a wholly new,
modernised rewrite inside the owner's private personal project. Owner: *"Derived, ported, are true but
loose. This is my code, there is no path back or approvals to seek. I just want references and history
... to just be nuked, so we stop talking about this. It's a non-concern. If there is risk (and there
isn't) I will take it. Let's put it to bed."*

Done the same day: every old identifier (the studio, its Python tree, its colour package, the class
prefix, the checkout path) retired from LargeWorlds (its PR #68, 93 files, five specs renamed), from
this repo (this branch: roadmap track A, board G1, the generated orchestrator profile's `package_paths`
and its generator, the hygiene checker and its test, one knowledge line) and from the agent memory. The
codename everywhere is `proto_color` / `proto_py`. SpriteJammer had already dropped its vendored copy.
Git history is untouched. Formalised in `Docs/ROADMAP.md` track A and `Docs/plan/BOARD.md` G1;
`tools/check_hygiene.py` now guards the old spellings only, so they cannot come back unnoticed.

### Job_Orchestrator / BATS: use freely, never distribute (owner, 2026-09-27; standing rule)

The owner gave the same account for Job_Orchestrator: their own work first, on personal time and equipment
(the first working version over a holiday break); a studio fork showcased but never in production; the
private original developed on since; their manager aware of it and of the blog posts. The owner has not
decided to publish it, sees a possible conflict of interest in doing so, and would seek a blessing first.
Owner: *"So its use during the development of HogShade, LargeWorlds, SpriteJammer and others is fine; I
just am not distributing Job_Orchestrator/BATS in any of those itself."* Formalised as roadmap track A's
third box (struck, with the rule) and a Distribution section in `Docs/knowledge/job-orchestrator.md`;
board G1 no longer lists it.

### Track A closed; the profile housekeeping leaves this repo (owner, 2026-09-27)

With both clearance boxes settled, the owner looked at what remained of track A (archive dead public repos,
pin four repos, a profile README) and said it *"doesn't have any strong relevance to HogShade, so I am not
sure why it's in this repo's roadmap being tracked; we should track that somewhere else (not sure where)."*
Track A is closed and G1 with it. The items are parked in the agent's memory so they are not lost; the
recommended home is the GitHub profile repository, which is what they are about. The owner picks.

## 4. What moved out of this file (2026-09-27)

| Was here | Now |
| --- | --- |
| Repository and GitHub state | [../handoffs/CURRENT.md](../handoffs/CURRENT.md), "Repository and GitHub state" |
| Working knowledge: toolchain and shell | [../knowledge/toolchain.md](../knowledge/toolchain.md), "Lessons that cost time" |
| Working knowledge: Maya 2026 scripting | [../knowledge/maya-scripting.md](../knowledge/maya-scripting.md) |
| Working knowledge: process | [../standards/definition-of-done.md](../standards/definition-of-done.md), [../standards/failure-modes.md](../standards/failure-modes.md), the `review-and-pr` skill |
| Open questions for the owner | [../plan/BOARD.md](../plan/BOARD.md), the gates G1 to G5 and the owner-only steps |
