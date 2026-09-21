# HogShade documentation

Four layers, in the order they are written. Nothing is built from a layer that does not exist yet.

| Layer | Folder | What it answers | When it is written |
| --- | --- | --- | --- |
| Roadmap | [ROADMAP.md](ROADMAP.md) | What are the tracks and phases, in what order, and what is waiting on the owner | Once; amended as decisions land |
| Pre-spec design | [design/](design/) | What is the problem, what are the options, what is decided and why | Before a phase's spec; dated filenames |
| Spec | [specs/](specs/) | For one phase: the exact deliverable, its interfaces, its acceptance gate, what is out of scope | Before the phase's plan |
| Plan | [plans/](plans/) | For one phase: the ordered tasks with checkboxes, each small enough to verify | Before the phase's work starts |

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

## Specs and plans

| Phase | Spec | Plan | Status |
| --- | --- | --- | --- |
| 1. Repo hygiene | [specs/phase-1-hygiene.md](specs/phase-1-hygiene.md) | [plans/phase-1-hygiene.md](plans/phase-1-hygiene.md) | In progress |
| 2. Restructure (WGSL core, naga spike) | [specs/phase-2-restructure.md](specs/phase-2-restructure.md) | [plans/phase-2-restructure.md](plans/phase-2-restructure.md) | Spike passed; core skeleton, build and compile tests in PR B; PR C next |
| 3. OpenPBR model and MaterialX carrier | not yet | not yet | Design done |
| 4. Surface authoring | not yet | not yet | Design done |
| 5. wgpu host | not yet | not yet | Design done |
| 6. Other hosts | not yet | not yet | Design done |
| E1. IBL cook | [specs/e1-ibl-cook.md](specs/e1-ibl-cook.md) | [plans/e1-ibl-cook.md](plans/e1-ibl-cook.md) | Cook, tests, job and Maya check done; LFS payloads (EXR, DDS) blocked on leaving the fork network |
| E2. Cook performance and resolution | [specs/e2-cook-performance.md](specs/e2-cook-performance.md) | [plans/e2-cook-performance.md](plans/e2-cook-performance.md) | Done except the roadmap tick: numba 140x, measured to an 8192 cube |
| E. Parity and pipeline, rest | not yet | not yet | Design done |
| D. SpriteJammer tiers | lives in the SpriteJammer repo | | Design done here |
