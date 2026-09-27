---
name: local-review
description: Review HogShade code with fresh eyes (an isolated subagent) against this repository's own standards plus a ten-metric rubric (design, architecture, readability, maintainability, performance, security, error handling, logging, coding standards, and the WGSL core contract when applicable), 7/10 baseline. Use before asking for a merge on a significant increment, to review one module in full, to review a core WGSL module against the core rules, or to audit the project's design. Invoke as /local-review [diff|module|core|project] [target].
---

# Local standards reviewer (HogShade)

Reviews code with **fresh eyes**, an isolated subagent, against two inputs:

1. **This repository's standards**, discovered at run time from the files listed in step 2 (never
   pasted into this skill, so they cannot go stale here).
2. **The rubric** in [`references/rubric.md`](references/rubric.md): nine generic metrics plus the
   HogShade core contract when applicable, 7/10 baseline.

Ported from SpriteJammer's repo-agnostic skill on 2026-09-27 and adapted: a `core` mode, the
hygiene grep as a hard finding, `master` as the default branch. When it runs is process, not
preference: `Docs/standards/definition-of-done.md`, "When local-review runs". Its output goes in the
pull request's *Review* section.

## 1. Parse the invocation

`/local-review [mode] [target]`

- No args, or the first token is not a known mode: **`diff`**.
- **`diff`**: the branch against `master` plus working changes. "Review my current work."
- **`module [path]`**: one Python module in full, with its dependency neighbourhood. If `path` is
  omitted, use the file in IDE focus; if none, ask for a target rather than guessing.
- **`core [path]`**: one WGSL module under `core/` against the core contract (step 3), with its
  NumPy twin under `hogshade/reference/` and its GPU test under `tests/core/`.
- **`project`**: a holistic design and architecture pass across `core/`, `hogshade/`, `hosts/`,
  `tools/`, emphasising boundaries over line-level nits.

## 2. Discover the repository's standards

Load what exists, in this order, and stop once there is enough signal:

1. `AGENTS.md` (the non-negotiable rules) and `CLAUDE.md`
2. `Docs/standards/definition-of-done.md`, `Docs/standards/workflow.md`
3. `core/manifest.toml` (module order, the prefix rule and its exemptions), `core/README.md` if present
4. `hosts/README.md`, `hosts/hlsl/README.md`, `hosts/wgpu/README.md` (what a host may call, what is generated)
5. `tools/README.md` (tools per host, the verification layout), `Docs/knowledge/*.md`
6. `pyproject.toml` `[tool.ruff]` (120 columns, py311 target), `.github/workflows/tests.yml`
7. The decision log `Docs/design/2026-09-26-decision-log-and-working-knowledge.md`, section 2, for
   decisions a change might contradict

The rubric is constant; the concrete standards come from these files.

## 3. Gather scope (per mode)

**diff**

- Default branch: `git symbolic-ref refs/remotes/origin/HEAD` (this repo's is `master`).
- `git diff master...HEAD`, plus `git diff` and `git diff --cached`.
- Read the changed hunks and the functions they touch, enough surrounding code to judge them.
- Run the hygiene grep and treat any new match outside `legacy/` as a hard finding (the pattern quoted
  in `.claude/skills/*/SKILL.md` matches itself and is exempt):
  `git grep -n -i -E "bluepoint|sony|bp_py|bp_color" -- ':!legacy'`.
- If `core/` changed: `uv run python tools/build_shaders.py --check` must report the generated
  artifacts current; a stale artifact is a hard finding. Generated files under `hosts/*/generated/`
  are never reviewed for style, only for being current.

**module [path]**

- Read the target in full; build its neighbourhood (what it imports, what imports it) and read enough
  of each neighbour to judge fit.

**core [path]**

The core contract, each item a finding when missed:

- Every function, struct and constant in the module carries the module's prefix from
  `core/manifest.toml`, unless the manifest exempts the name as a public interface.
- Textures, samplers and uniforms arrive as function parameters; no bound globals in the core.
- Every function has a NumPy twin in `hogshade/reference/` and a GPU test in `tests/core/` that
  compares them; constants used by both are mirrored in `hogshade/core_constants.py`.
- Dispatch on the model ID is an if-chain, never a `switch` on a value derived from a uint texture while
  texture parameters are in scope (FXC rejects that shape; `core/models.wgsl`'s header). A `switch` on a
  uniform such as the debug mode, and early returns, are fine and the core uses both.
- Names ending in a digit get `_` appended by naga; a host that references one must use the
  translated spelling.
- Kept quirks of a legacy port are listed in the module header with the deviations; a quirk removed
  silently is a finding.

**project**

- Map the boundaries: `core/` (WGSL, no host knowledge), `hogshade/` (Python: reference twins, the
  wgpu host, the cook, jobs), `hosts/` (per-host shells over generated cores), `tools/` (scripts per
  host), `tests/` (compile, core, host, ibl, jobs). Sample representative modules across them.
  Emphasise architecture, design and maintainability at the system level.

## 4. Dispatch the review subagent

Spawn **one** subagent (Agent tool, `general-purpose`, run synchronously). Its prompt contains:

- The rubric **and** output template from [`references/rubric.md`](references/rubric.md).
- The discovered standards, or their relevant sections, quoted.
- The gathered scope for the mode, including the hygiene and `--check` results.

Instruct it to score every applicable metric 1 to 10, mark inapplicable ones `n/a`, justify every
sub-7 score with a `file:line` anchor and a concrete fix, not inflate scores to be agreeable, and
return the filled output template as its final result.

## 5. Relay, then offer fixes

Print the scored report. For a `diff` review before a PR, paste the table into the pull request's
*Review* section with each finding marked fixed or declined with a reason. Applying fixes is a
separate, explicit step: offer, do not auto-run; one item at a time or as a batch at the owner's
choice. Deferred defects become GitHub issues named under *Not covered*.
