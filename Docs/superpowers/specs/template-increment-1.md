# Template increment 1 spec: core, init, Makefile, the minimum runtime, harness adapters and the payload

**Status:** Accepted (owner, 2026-10-09: "accepted"). Drafted 2026-10-09 after the owner's "go", from the locked design
([../../design/2026-10-09-ai-first-template.md](../../design/2026-10-09-ai-first-template.md), increment 1). The
repository is created at task 2 of the plan, with the owner's go at that moment.

Board: [../../plan/BOARD.md](../../plan/BOARD.md) (the AI-first framework row). Plan:
[../plans/template-increment-1.md](../plans/template-increment-1.md). The description of what the framework is:
[../../knowledge/ai-first-framework.md](../../knowledge/ai-first-framework.md).

## Deliverable

A private repository, `ai-first-template`, whose `payload/` directory is a complete, working, harness-neutral start for
a Python and uv project that runs the framework from its first commit, whose root is the template's own instance of
that payload, and whose CI proves both. Concretely:

1. **The payload** (`payload/`): the `core`, `journal`, `tasking`, `python-uv` (minimum), `hygiene` (empty), `graph` and
   `harness-adapters` modules, the day-0 seed, `framework.toml` and the `project.json` skeleton. `ux`, `specimens` and the
   mock `src/` are `planned` in `framework.toml` and skipped.
2. **The initialiser**, `tools/init.py`: `init new` (with `--answers`, `--dry-run`, `--target`), idempotent, with a
   written record of each run. `--github`, `--clear-specimens` and `adopt` are not in this increment.
3. **The gate**: `tools/check.py` (the stage list, also the CI parity oracle), a `Makefile` obeying SpriteJammer's hard
   rule (every recipe one `uv run` call, GNU Make 3.81 safe), git hooks (pre-commit fast gate, `commit-msg` rejecting an AI
   attribution trailer and requiring the sign-off the project's `project.json` names), and a CI workflow on Windows and
   Linux.
4. **The checks**, extracted and unified: `check_docs.py` (links, status headers on a closed set for every governed
   document including specs and plans, the journal index and day, the ADR index, the board, the `terms` check, retired
   vocabulary, and a line limit on the handoff; the values are under *The two new docs rules*), `check_hygiene.py`, `check_log_format.py`, and the graph generator with
   its tests.
5. **The harness layer**: `AGENTS.md` as the only context; `tools/sync_adapters.py` writing `CLAUDE.md`, the Gemini
   setting and `.github/copilot-instructions.md` from the harnesses `framework.toml` enables, and the skills mirrors from
   `.agents/skills/`; `--check` failing on an adapter that carries text of its own or a mirror that differs; a lint that
   keeps managed documents free of harness names; a conformance probe per harness and the compatibility matrix.
6. **The documents**: the entry file, docs map, glossary seeded with the framework's terms, board shell, handoff shell
   ("Day 0"), journal, ADR index with ADR-001 "adopt the framework", the framework ledger (managed) and an empty project
   ledger, the definition of done, the workflow, the Python and testing standards in reconciled form, the PR template,
   and the `local-review` and `review-and-pr` skills written as roles, not as one tool's calls.

## Interfaces

`framework.toml` (template version; per-module `on`, `off` or `planned`; enabled harnesses; overrides), `project.json`
(`name`, `slug`, `owner` identity, `default_branch`, `signoff`, `hygiene` identifiers), and the `--answers` file (JSON, `answers.json`, in the same schema as
`project.json`) are validated on load and each refusal names the field. `init new` exits 0 on success, 1 on a
refused input and 2 on a failed check at the end. The run record is a text log, `logs/init-<UTC timestamp>.log` in the target, giving what was
read, decided and written and why. `logs/` is git-ignored in the payload and is **not a tracked file**: every assertion
below about "changes no file" or "writes nothing" is about the tracked and generated files, never `logs/`. A `--dry-run`
writes no file at all, so its record goes to standard output.

## The two new docs rules

- **Closed status set.** Every governed document, specs and plans included, carries `**Status:**` in its first 12 lines
  and its first word is exactly one of `Proposed`, `Accepted`, `Living`, `Superseded`, `Abandoned` (HogShade's
  `STATUS_WORDS` today); `Superseded` must say by what. A free-form word (`Adopted`, `Draft`, `Done`) is a finding.
- **Handoff line limit.** `Docs/handoffs/CURRENT.md` may have at most **150 lines**, counting every line of the file as
  `len(text.splitlines())`; the limit is `handoff_max_lines` in `framework.toml`, default 150, and a repository may
  lower or raise it with a reason in its overrides. The finding names the count and the limit. (HogShade's handoff is 83
  after its trim; SpriteJammer's is 876 and LargeWorlds' 396, which is the failure the rule exists for.)

## Acceptance

1. **Day 0.** From a clean checkout, `init new --answers` into an empty temporary directory, then `make check`, passes on
   Windows and on Linux.
2. **Self-hosting.** The template's root is produced by `init new --target .` from `payload/`; a test regenerates it into a
   temporary directory and the managed and parametrised files match the committed root.
3. **Idempotence.** A second `init new` over a finished target changes no tracked or generated file (the run record under
   `logs/` is excluded); `--dry-run` writes no file anywhere and prints the whole plan, which is its record.
4. **Each check can fail.** For every check, a test mutates a fixture to break exactly its rule and requires the finding,
   and the same fixture unmutated passes (the instrument is proved, ledger entry 6).
5. **CI parity.** A test asserts the workflow runs `tools/check.py`'s stages in the same order; a test asserts every
   Makefile recipe is one `uv run` line.
6. **Harness neutrality.** Each adapter is generated and holds only a pointer; an adapter edited by hand, or a skills mirror
   that differs from `.agents/skills/`, fails `sync_adapters.py --check`; a managed document naming a harness outside the
   adapter list and the matrix fails the lint.
7. **Probes.** The conformance probe exists for Claude Code, Gemini CLI and Copilot. **A harness is enabled in
   `framework.toml` only after its probe has passed, with the date and who ran it in the compatibility matrix**; a harness
   whose probe has not been run is `planned` and gets no adapter. Acceptance requires every enabled harness to have a
   passing, dated probe; it does not require all three to be enabled.
8. **Hooks.** `commit-msg` rejects a message with an AI attribution trailer and one without the required sign-off, with a
   test.

## Out of scope

The mock `src/` and its boundary test (increment 2), specimens and the walkthrough (3), UX (4), the sync check,
`init adopt`, `--github` and `--clear-specimens` (5), `--update`, the graph overlay, scoped (nested) instructions, other
stacks. Not decided here and left to the plan's first tasks: the exact contents of each reconciled standard, and which of
the 22 ledger entries are framework entries.

## Decisions this spec takes (two-way)

| Decision | Alternative | Why |
| --- | --- | --- |
| The closed status set and the handoff line limit are in this increment | Defer both | The unified docs checker is built here; adding two rules to it is cheap and they are the improvements with the clearest evidence |
| "Last updated is not older than the content" is out | Include it | What counts as the document's newest content is undefined; it needs its own design |
| The root is written by `init new --target .` | `init adopt` | Adopt is for arbitrary repositories and is increment 5 (the design's decision) |
| The probes are manual and recorded, not run in CI; a harness is enabled only after its probe passed | Mock the harnesses in CI; enable all three and mark probes "not yet run" | CI cannot run the three vendors' agents, and an unproven adapter would pass the gate |
| The run record is `logs/` (git-ignored), outside every "no file changes" assertion | Omit records on no-ops and dry runs | Idempotence and a record both hold; the dry run's record is its printed plan |
| The handoff limit is 150 lines, in `framework.toml` | 100 or 200 | HogShade's trimmed handoff is 83; 150 leaves room without allowing a log; configurable with a reason |

## What the build found

Plan tasks 0 and 1, run 2026-10-09 by four read-only passes, each reading its files in full (the harness facts from the
vendors' own pages; the three repositories' checkers, definitions of done, workflows, PR templates, glossaries, ledgers,
Python standards, Makefile, gate script, hooks, CI and documentation standard). The reports are not committed; what
follows is what the build needs from them. HogShade is HS, LargeWorlds LW, SpriteJammer SJ.

### Task 0: what each harness reads (vendor documentation, 2026-10-09)

| Harness | Entry file | Skills | Notes the template acts on |
| --- | --- | --- | --- |
| **Claude Code** ([memory](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills)) | `CLAUDE.md`; reads `AGENTS.md` natively from v2.1.277, **only when no `CLAUDE.md` exists**; `@path` imports work (four hops); nothing under `.agents/` is read | `.claude/skills/<name>/SKILL.md` only; `.agents/skills` is not documented | A one-line `CLAUDE.md` (`@AGENTS.md`) is the fallback for older versions and for any repository that already has a `CLAUDE.md`; omitting it is valid on 2.1.277 or later. Skills need a mirror here |
| **Gemini CLI** ([GEMINI.md](https://geminicli.com/docs/cli/gemini-md/), [skills](https://geminicli.com/docs/cli/skills/), [config](https://geminicli.com/docs/reference/configuration/)) | `GEMINI.md`; `context.fileName` in `.gemini/settings.json` takes a string or array and accepts `AGENTS.md`; `@file` imports work (depth 5) | `.gemini/skills/` or the alias `.agents/skills/` (the alias wins) | The one-line settings file is enough. The docs carry a banner that Gemini CLI was replaced by Antigravity CLI on 2026-06-18 for some users; whether that tool behaves the same is **not checked** |
| **GitHub Copilot** ([support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support), [code review](https://docs.github.com/en/copilot/concepts/agents/code-review), [skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)) | Code review **on GitHub.com** reads `.github/copilot-instructions.md`, `.github/instructions/**`, and `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `REVIEW.md`; **in VS Code and Visual Studio it reads only `.github/copilot-instructions.md`**; the cloud agent reads `AGENTS.md` (nearest wins) | `.github/skills`, `.claude/skills` or `.agents/skills`; code review is documented to use `.github/skills` | The design's open question is answered: GitHub.com review reads `AGENTS.md`, but the IDE paths do not, so the thin `.github/copilot-instructions.md` adapter stays. No hard length limit; a soft guideline of about 1,000 lines. Review reads the PR head branch |

Consequence for the layout: `.agents/skills/` stays canonical (Gemini and Copilot read it), and only Claude Code needs a
generated mirror in `.claude/skills/`. VS Code's own documentation lists `CLAUDE.md` and `AGENTS.md` as read by its local
agent behind settings (`chat.useAgentsMdFile`, `chat.useClaudeMdFile`; nested `AGENTS.md` is experimental and off by
default), which supports leaving nested instructions out of this increment. Probes are still to be run per harness
(acceptance 7); the vendor pages above are the matrix's first sources.

### Task 1: the picks, per artifact

**Docs checker.** Take HS `tools/check_docs.py` as the base: it takes `root` everywhere (SJ's needs a monkeypatched global),
has the hardened link check (BOM, unclosed fences reported, any URL scheme, case-exact resolution bounded by the root), and
a generic index check serving both ADRs and the journal. Fold in: from LW `board-landed-rows`, `single-status`,
`glossary-row` and the replacement-aware retired-term mode; from SJ the `corpus` not-empty guard (a gate that scanned zero
files once passed), `adr-refs` (SJ's has no `Supersedes` inverse: fix), `nested-claude`, a hardened `orphan`; every
constant (directory case, exclusions, governed directories, index paths, board sections, grandfathered set) moves to
`framework.toml`. Defects found in the sources, fixed in the lift and, for HS, backported: HS's `terms` check registers only
the first bold span in a glossary cell, so a document listing **Plan** fails against the row `| **Spec**, **Plan** |`
(verified, `check_docs.py:131`); LW's ADR index breaks on a `#fragment`; SJ's `orphan` counts a file's own text;
`fences` is emitted from inside the link check.

**Definition of done.** Take HS (numbered table with an *Enforced by* column, autonomy protocol, the definition of
significant). Fold in from LW the identity and DCO section, whose-branch, the scope section ("say plainly what was left
out"), no test skipped to get green, a handoff update when the owner states a preference, and the ledger entry in the same
PR; from SJ the `make check` equivalence rule, the README-currency row, the spike and code rows of the ladder, and "what is
deliberately not here". HS's row 7a promises a landed row keeps its PR number but no HS check enforces it (LW's does): the
union checker fixes that.

**Workflow.** Take HS's `workflow.md` (roadmap tier, nine records, "ticked when its verification ran", owner merges). Fold in
SJ's lock state and the spike branch-off, and LW's chain, which is the only place a UX mock pass exists. LW has no workflow
file; its chain lives in a handoff paragraph and ledger entry 20.

**PR template.** Take HS's (the *New terms* checkbox, *Board: none* rule, *Verified*). Fold in from SJ the rule that a
deferred defect is a GitHub issue opened before merge, and an optional back-to-back *Measured* section. LW has none, which
is why its definition of done lacks the decisions-table rule.

**Glossary.** HS's two-column structure and domain sections, plus LW's `Not` column for the confusing terms and its prose
rules the check cannot carry. The template ships only process rows; domain sections stay project-owned.

**Task layer.** Take SJ's whole: the Makefile and its hard rule, `tests/test_tooling.py`, `scripts/check.py` (the stage list
and the CI parity test), `pre-commit` and `prepare-commit-msg` hooks, `.gitattributes` hook and line-ending rules,
`dependabot.yml`, `ci.md`, `tooling.md`, `documentation.md`. Leave behind: the LFS hook stubs, the demo targets and
launchers, the `content` stage, the private-dependency token step, the devblog design, the `cspell` word list,
`readme-current`. Fix in the lift: there is no hook installer and no check hooks are enabled (add `make hooks` and a check);
the help and CI-parity tests are substring matches, so a commented-out workflow line passes (parse the YAML); hard-coded
counts and "four gates" are stale (copy none); `Adopted` is outside the status vocabulary; the pending-review threshold is
written in four places (one source); `mypy` and `cspell` are configured and never run (run them or leave them out).

**Ledger.** The framework ledger seeds from 24 distinct generic lessons merged out of the 68 entries (HS 22, LW 25, SJ 21);
every entry's classification, and the merged list, are in
[../../research/2026-10-09-failure-ledger-classification.md](../../research/2026-10-09-failure-ledger-classification.md). Domain entries (GPU, Maya, wgpu, numba, game loop) stay with their
projects; Python and uv lessons go to the `python-uv` module's own ledger file; measurement lessons (SJ 1, 13, 14, 21 and
LW 12) go to an optional appendix. Same lesson in several ledgers is merged once: the heredoc class appears four times,
"a gate whose failure a pipe swallowed" twice, "board row is not a lock" three times.

**Python standards.** The three agree on a core: the module header (`_MODULE_NAME`, `__version__`, `__updated__`, `_LOGGER`),
absolute imports in three groups, complete type hints with a dtype on `NDArray`, specific exceptions, f-string logging,
reST docstrings, 120 columns, `pathlib`. Picks for the conflicts: `X | None` and `list[...]` (LW's `typing.Optional`
examples are not carried); a 3.11 floor stated as a floor, not "3.12"; f-strings with HS's measured-hot-path exception,
`# lazy-log:` marker and check; `__version__` before `__updated__`; `from __future__ import annotations` required; no
`__author__`; `print()` allowed only in a script's `main` summary and demo entry points; `E501` enforced in ruff (the
formatter does not wrap strings or docstrings). PySide6, GPU, numba, game-loop, Maya and the project invariants stay out.

### Decisions this found, for the owner to overrule (two-way)

| Decision | Alternative | Why |
| --- | --- | --- |
| One status vocabulary, the five words; SJ's `Adopted`, `Exploring` and `Locked` migrate at its retrofit | Allow SJ's | The checks can then tell what is current; the spec already fixes the five |
| The glossary's retired terms use LW's dedicated three-column table (`~~Old~~ \| Use \| Why`) | HS's inline struck-bold row | It carries the replacement, so the check is replacement-aware; HS has one retired row to migrate |
| The retired-vocabulary check is on by default in a new repository and opt-in for a retrofitted one | Always on; always opt-in | LW found 61 live references the day it tried it; a new repository has none |
| The chain has a UX mock pass stage for anything a person will touch, after the lock and before the spec | Fold it into the spec | The owner asked that the template deal with UX; LW is the only repository that has the stage |
| The journal is one file per day in the `journal` module, off for a repository that keeps none | Per session; none | HS's check keys on the day; LW has no journal and says it must not be built unasked |
| Pending-review and the lane ids are in the `lanes` module, off by default; `readme-current` is left out | Core | They exist for many parallel sessions and a benchmark corpus |
| A branch per increment; worktrees optional | Worktree required (SJ) | One mechanism in the core; SJ keeps its worktrees as an override |

### Not found here

Whether SJ or HS keep identity and sign-off rules in files other than their definition of done; whether HS's and LW's
`local-review` skills differ materially from SJ's `ci.md` rule; the full text of LW's board lines about the chain. The
extraction reads these when it reaches them.

## Terms introduced

**Compatibility matrix**: in [../../glossary.md](../../glossary.md), added with this spec (the glossary rule, ledger
entry 20).
