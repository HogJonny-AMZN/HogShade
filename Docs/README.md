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
| 1. Repo hygiene | [specs/phase-1-hygiene.md](superpowers/specs/phase-1-hygiene.md) | [plans/phase-1-hygiene.md](superpowers/plans/phase-1-hygiene.md) | In progress |
| 2. Restructure (WGSL core, naga spike) | [specs/phase-2-restructure.md](superpowers/specs/phase-2-restructure.md) | [plans/phase-2-restructure.md](superpowers/plans/phase-2-restructure.md) | Done 2026-09-27, `0.2.0`: PRs A to G plus the standards pass; both legacy models in both hosts; the acceptance gate met except item 5 (the same mesh in both hosts), deferred to track E by the owner at the close |
| 3. OpenPBR model and MaterialX carrier | not yet | not yet | Design done |
| 4. Surface authoring | not yet | not yet | Design done |
| 5. wgpu host | not yet | not yet | Design done |
| 6. Other hosts | not yet | not yet | Design done |
| E1. IBL cook | [specs/e1-ibl-cook.md](superpowers/specs/e1-ibl-cook.md) | [plans/e1-ibl-cook.md](superpowers/plans/e1-ibl-cook.md) | Done: cook, tests, job, Maya diffuse-term check, LFS payloads in the repo (2026-09-26) |
| E2. Cook performance and resolution | [specs/e2-cook-performance.md](superpowers/specs/e2-cook-performance.md) | [plans/e2-cook-performance.md](superpowers/plans/e2-cook-performance.md) | Done except the roadmap tick: numba 140x, measured to an 8192 cube |
| E. Parity and pipeline, rest | not yet | not yet | Design done |
| D. SpriteJammer tiers | lives in the SpriteJammer repo | | Design done here |
