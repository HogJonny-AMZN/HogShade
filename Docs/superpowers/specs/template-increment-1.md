# Template increment 1 spec: core, init, Makefile, the minimum runtime, harness adapters and the payload

**Status:** Proposed. Drafted 2026-10-09 after the owner's "go", from the locked design
([../../design/2026-10-09-ai-first-template.md](../../design/2026-10-09-ai-first-template.md), increment 1). It
becomes Accepted when the owner says so; the repository is created at task 2 of the plan, with the owner's go at that
moment.

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

## Terms introduced

**Compatibility matrix**: in [../../glossary.md](../../glossary.md), added with this spec (the glossary rule, ledger
entry 20).
