<!--
Title: what is now true -- e.g. "Legacy v1 port: one Disney BRDF, selectable in both hosts (phase 2 task 18)".
Branch: type/<slug> (feat, fix, docs, chore, content). The owner merges and deletes the branch.
Delete any section that has nothing in it.
-->

**Board:** <!-- the row in Docs/plan/BOARD.md this lands, closes or adds; "none" is an answer, an omission is not -->

## What changed

<!-- What is now true that was not. Lead with the result, not the process. Name the plan task. -->

## Verified

<!--
What ran, where, and the artifact it left: tests on which adapter, build_shaders --check, the wgpu
pictures under verification/wgpu/..., the Maya job and its verification/maya-2026/... directory.
A claim comes after the evidence exists. Numbers without a command are estimates.
-->

## Decisions

<!--
Every two-way-door decision made on this branch: the autonomy protocol's record. The owner's merge is
the review, so a decision not listed here was not reviewed. MORE THAN 8 means the pull request is too
big: split it. One-way doors do not belong here; they stop work and get asked. Owner quotes where the
owner decided.
-->

| Decision | Alternative | Why | Reverse cost |
| --- | --- | --- | --- |
| | | | |

## Wrong along the way

<!-- Beliefs, records or measurements that did not survive. This is the research record, not an apology. -->

## Review

<!--
Significant increments only (Docs/standards/definition-of-done.md, "When local-review runs"). Paste the
score table from /local-review diff, then each finding as fixed, or declined with the reason. Copilot
reviews every push automatically; this is the deliberate one.
-->

## Not covered

<!-- What this does not verify, test or change, said plainly. An open gate is stated, never implied. -->

---

- [ ] Tests and lint green on CI, read with `gh pr checks`, not assumed
- [ ] `tools/build_shaders.py --check --require-compilers` clean, if the core changed
- [ ] Hygiene grep clean (`review-and-pr` skill)
- [ ] New terms: every word this coins (a module, dataclass, enum value, level, kind, CLI verb, document type) has its
      glossary row, and each new design, spec or plan ends with `## Terms introduced` (or says None)
- [ ] `tools/check_docs.py` clean; docs match reality: BOARD (the row struck or added, gates touched), plan task, spec, `Docs/README.md`, decision log, journal, handoff
- [ ] Review: `/local-review diff` run and its findings answered above, **or** this increment is not
      significant under the rule, and *Review* says why
- [ ] Every two-way-door decision is in *Decisions*, and there are no more than 8
