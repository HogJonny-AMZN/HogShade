# HogShade documentation

**Status:** Living. The map from task to document; rewritten as folders and documents land.

Four layers, in the order they are written. Nothing is built from a layer that does not exist yet.

| Layer | Folder | What it answers | When it is written |
| --- | --- | --- | --- |
| Roadmap | [ROADMAP.md](ROADMAP.md) | What are the tracks and phases, in what order, and what is waiting on the owner | Once; amended as decisions land |
| Pre-spec design | [design/](design/) | What is the problem, what are the options, what is decided and why | Before a phase's spec; dated filenames |
| Spec | [superpowers/specs/](superpowers/specs/) | For one phase: the exact deliverable, its interfaces, its acceptance gate, what is out of scope | Before the phase's plan |
| Plan | [superpowers/plans/](superpowers/plans/) | For one phase: the ordered tasks with checkboxes, each small enough to verify | Before the phase's work starts |
| Board | [plan/BOARD.md](plan/BOARD.md) | The tracker: owner gates, now, next, blocked on whom, and the Icebox where every idea said out loud lands with a cost | Every increment's PR |

The spec and plan folders live under `superpowers/`, the cross-repo convention the superpowers skills
write into (brainstorming writes a spec, writing-plans a plan). Design and handoffs stay at the top
level, as they do in LargeWorlds and SpriteJammer; the convention as first stated on 2026-09-26 put
them under `superpowers/` too, and consistency with the two repositories that already exist won
(the remainder of the standards pass, 2026-09-27).

A fifth document is not a layer but a safety net: the decision log
(`design/2026-09-26-decision-log-and-working-knowledge.md`) catches every direction or decision
stated in conversation before it has a spec to live in, so the record never depends on a session.

`AGENTS.md` at the repo root is the tool-neutral agent entry (`CLAUDE.md` imports it); `tools/bats/AGENTS.md`
and `tools/bats/README.md` cover the orchestrator for agents and humans.

Two more files are the session-independence layer: `handoffs/CURRENT.md` (where work is right now,
how to run the developer track, what a new session must not do) and `knowledge/` (small topic files
of the agent knowledge base; `knowledge/job-orchestrator.md` is the first).

[glossary.md](glossary.md) is the canonical vocabulary, shared with SpriteJammer where the concept is
shared; `tools/check_docs.py` fails on a retired term used as current (the check SpriteJammer boarded
as W1 and this repo built first).

[reviews/](reviews/2026-09-27-pitch-editorial-plan.md) holds review artifacts written for a future reader: editorial
plans with their findings, rejections and scorecards, and local code reviews when they are kept
(the standards pass's project review is one). [decisions/](decisions/README.md) holds the ADRs,
append-only, each with a *Revisit if*. [standards/](standards/definition-of-done.md) also carries
[python.md](standards/python.md), [wgsl.md](standards/wgsl.md) and
[failure-modes.md](standards/failure-modes.md); `.github/copilot-instructions.md` points Copilot at them.

Three more folders are the process, ported from SpriteJammer on 2026-09-27 with its reasoning:
[journal/](journal/README.md) (the append-only narrative, one file per session: what happened, which
beliefs changed, where BATS made the difference), [standards/](standards/definition-of-done.md) (the
definition of done with the autonomy protocol, and [standards/workflow.md](standards/workflow.md) for
the stages and which record owns what), and `tools/check_docs.py`, which fails the build on a broken
link, a governed document without a status line, or a session missing from the journal index.

| If you are... | Read |
| --- | --- |
| Starting any session | `handoffs/CURRENT.md`, then `plan/BOARD.md` (gates first), then the decision log, then the newest journal file |
| New to the project, or naming anything | [glossary.md](glossary.md): one word per concept; use these words and no synonyms; add a concept's word there before using it |
| An idea was said out loud | `plan/BOARD.md`, Icebox, with a cost and a reason; it is not a work order |
| Finishing an increment | `standards/definition-of-done.md`, the PR template, `journal/README.md` |
| Deciding something the owner has not | The autonomy protocol in `standards/definition-of-done.md` |
| Running anything in Maya or Blender | `knowledge/job-orchestrator.md`, then the `bats-job` and `maya-check` skills |
| Touching the core | `standards/wgsl.md`, then `decisions/README.md` (ADR-002 to ADR-005), `superpowers/specs/phase-2-restructure.md` "Interfaces", `core/manifest.toml`, the `shader-build` and `local-review` skills |
| Writing any Python | `standards/python.md` |
| Making a structural decision | `decisions/README.md`: read the ADRs, then add one |
| Something went wrong in the process | `standards/failure-modes.md`: find the trigger, or add the entry in the same PR |

Checkboxes in the roadmap track phases and owner gates. Checkboxes in a plan track tasks. A task
is ticked when its verification ran, not when its code was written. "Done" for a phase means the
spec's acceptance gate passed and the roadmap, the README and any affected design doc were updated.

## Current design documents

- [design/2026-09-20-modernization-direction.md](design/2026-09-20-modernization-direction.md): the
  architecture and every decision to date. Start here.
- [design/2026-09-20-game-shading-feature-catalogue.md](design/2026-09-20-game-shading-feature-catalogue.md):
  every game shading and material feature, sorted into physics, surface authoring and engine, with
  the module, tier, rendering-path half and hosts that carry it.
- [design/2026-09-20-wysiwyg-blindspots.md](design/2026-09-20-wysiwyg-blindspots.md): what it takes for
  the same material to look the same in every host, and the gaps the first direction had.
- [reference/material-types.md](reference/material-types.md): every material type's parameters, generated
  from the schema by `tools/generate_material_ui.py --write` and checked in CI; edit the schema, not the file.
- [design/2026-10-02-material-library.md](design/2026-10-02-material-library.md): the library of materials
  (S4, track F), Exploring: the base set as standard documents with a reverse conversion table, the
  roster of parents and children with sourced values, title and provenance in the document, the layout,
  the contact sheet as the proof, the texture set after track E; eight questions for the owner.
- [design/2026-09-27-material-schema.md](design/2026-09-27-material-schema.md): the material
  schema's pre-spec design, locked by the owner on 2026-09-27: the versioned parameter definition,
  the O3DE-shaped document, the MaterialX and glTF exports, the `hogshade.material` library and its
  generators, the library of materials, a cross-repo table, the ten questions answered in the owner's words, six increments.
- [design/2026-09-27-pitch-bats-as-the-agents-body.md](design/2026-09-27-pitch-bats-as-the-agents-body.md):
  the pitch for the agent loop on the orchestrator (why, why BATS, what, how, risks, the ask), written
  for the owner's team; Proposed until sent.
- [design/2026-09-26-decision-log-and-working-knowledge.md](design/2026-09-26-decision-log-and-working-knowledge.md):
  the living log of directions and decisions made in conversation, the order of operations, the
  repository state, and the lessons that cost time. A new session starts here. Appended, never
  rewritten; when an entry is formalised in a spec, plan or ADR, the entry says where.

## Specs and plans

| Phase | Spec | Plan | Status |
| --- | --- | --- | --- |
| 1. Repo hygiene | [superpowers/specs/phase-1-hygiene.md](superpowers/specs/phase-1-hygiene.md) | [superpowers/plans/phase-1-hygiene.md](superpowers/plans/phase-1-hygiene.md) | In progress |
| 2. Restructure (WGSL core, naga spike) | [superpowers/specs/phase-2-restructure.md](superpowers/specs/phase-2-restructure.md) | [superpowers/plans/phase-2-restructure.md](superpowers/plans/phase-2-restructure.md) | Done 2026-09-27, `0.2.0`: PRs A to G plus the standards pass; both legacy models in both hosts; the acceptance gate met except item 5 (the same mesh in both hosts), deferred to track E by the owner at the close |
| 3. OpenPBR model and MaterialX carrier | not yet | not yet | Design done |
| 4. Surface authoring | not yet | not yet | Design done |
| 5. wgpu host | not yet | not yet | Design done |
| 6. Other hosts | not yet | not yet | Design done |
| S1. The material schema files and `hogshade.material` (load, validate, resolve, convert) | [superpowers/specs/s1-material-schema.md](superpowers/specs/s1-material-schema.md) | [superpowers/plans/s1-material-schema.md](superpowers/plans/s1-material-schema.md) | Built 2026-09-27 (`feat/s1-material-schema`, [#31](https://github.com/HogJonny-AMZN/HogShade/pull/31) open): four types, three tables, `hogshade.material` with 133 tests; mayapy 3.11.9 lists the four types |
| S2. The generators: the Maya shell's material UI and the docs reference from the schema | [superpowers/specs/s2-material-generators.md](superpowers/specs/s2-material-generators.md) | [superpowers/plans/s2-material-generators.md](superpowers/plans/s2-material-generators.md) | Built 2026-10-01 (`feat/s2-material-generators`, [#35](https://github.com/HogJonny-AMZN/HogShade/pull/35) open): the Maya block and the docs reference generated and checked in CI; the GUI Maya picture run met after the merge (pixel-identical to master's shell in one session) |
| S3. The wgpu binding: a material document into the wgpu host's frame | [superpowers/specs/s3-wgpu-binding.md](superpowers/specs/s3-wgpu-binding.md) | [superpowers/plans/s3-wgpu-binding.md](superpowers/plans/s3-wgpu-binding.md) | Built 2026-10-02 (`feat/s3-wgpu-binding`, [#38](https://github.com/HogJonny-AMZN/HogShade/pull/38) open): a document is the one way a material reaches the wgpu host; the wgpu pictures recaptured with the schema's defaults |
| E1. IBL cook | [superpowers/specs/e1-ibl-cook.md](superpowers/specs/e1-ibl-cook.md) | [superpowers/plans/e1-ibl-cook.md](superpowers/plans/e1-ibl-cook.md) | Done: cook, tests, job, Maya diffuse-term check, LFS payloads in the repo (2026-09-26) |
| E2. Cook performance and resolution | [superpowers/specs/e2-cook-performance.md](superpowers/specs/e2-cook-performance.md) | [superpowers/plans/e2-cook-performance.md](superpowers/plans/e2-cook-performance.md) | Done except the roadmap tick: numba 140x, measured to an 8192 cube |
| E. Parity and pipeline, rest | not yet | not yet | Design done |
| D. SpriteJammer tiers | lives in the SpriteJammer repo | | Design done here |
