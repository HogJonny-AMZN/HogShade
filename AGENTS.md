# AGENTS.md

Tool-neutral entry point for any coding agent in this repository. Short on purpose: the knowledge
lives in small topic files, and this is the map. (The full standards and agent context arrive in
the phase 2 standards pass; until then these pointers are the contract.)

## Read first

1. [Docs/handoffs/CURRENT.md](Docs/handoffs/CURRENT.md): where work is right now and how to run it.
2. [Docs/design/2026-09-26-decision-log-and-working-knowledge.md](Docs/design/2026-09-26-decision-log-and-working-knowledge.md):
   every decision and lesson to date, with where each is formalised.
3. [Docs/README.md](Docs/README.md): the document layers (roadmap, design, spec, plan) and the
   current specs and plans; [Docs/ROADMAP.md](Docs/ROADMAP.md) for what comes next.

## Topic files

| Topic | File |
| --- | --- |
| Job_Orchestrator (BATS): the developer track, worker types, jobs, rules | [Docs/knowledge/job-orchestrator.md](Docs/knowledge/job-orchestrator.md), [tools/bats/AGENTS.md](tools/bats/AGENTS.md) |
| Tools layout per host | [tools/README.md](tools/README.md) |
| Generated hosts and what to call in the core | [hosts/README.md](hosts/README.md), [hosts/hlsl/README.md](hosts/hlsl/README.md), [hosts/wgpu/README.md](hosts/wgpu/README.md) |
| IBL content and the cook | [content/ibl/README.md](content/ibl/README.md), [Docs/specs/e1-ibl-cook.md](Docs/specs/e1-ibl-cook.md) |

## Skills (procedures)

Plain-markdown procedures under `.claude/skills/<name>/SKILL.md`, Claude's layout, readable by any
agent: `bats-job` (submit and read jobs), `maya-check` (a Maya check through the resident worker
and how to read its result), `shader-build` (change the core, rebuild, verify on every compiler),
`review-and-pr` (the PR checklist and how to assess a Copilot review). Follow the matching one
before improvising; add one when a procedure has been done twice.

## Non-negotiable rules

- The doc process: roadmap, pre-spec design (a hand-written lock of what was decided), spec, plan,
  then work; a plan task is ticked when its verification ran, never when code was written.
- The core is WGSL; textures, samplers and uniforms are function parameters, never bound globals;
  every core module carries its prefix; every core function has a NumPy twin and a GPU test.
- Never stop a process you did not start; never launch a DCC beside an orchestrator worker for it.
- Hygiene before every push: no employer names, personal email only, no studio files,
  Apache-compatible dependencies. LFS only for what cannot be generated; 8K masters never.
- Every PR is reviewed by Copilot; assess each finding, fix or refute with evidence, reply on the
  thread; the owner merges. Claims in a reply come after the evidence exists.
- Record decisions and lessons in the decision log or a topic file in the same PR as the work.
