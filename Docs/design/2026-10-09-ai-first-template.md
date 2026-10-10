# The template repository: one upstream for the AI-first framework

**Status:** Accepted (owner, 2026-10-09: "locked"). Drafted 2026-10-09 from the owner's statements of that day and
the eleven design answers (all "as recommended"). The owner locked it after being offered two amendments, the
template running the framework on itself and harness neutrality; both are in the body below, read as part of the lock
(the owner said nothing against them). Nothing in it is built until each increment's spec and plan are accepted.

Date: 2026-10-09. Parents: [../knowledge/ai-first-framework.md](../knowledge/ai-first-framework.md) (what the
framework is), [the graph](../knowledge/ai-first-framework-graph.md), [../plan/BOARD.md](../plan/BOARD.md) (the
template row), [../standards/workflow.md](../standards/workflow.md) (the chain this document is stage 1 of).
Vocabulary: [../glossary.md](../glossary.md).

## The goal

Three repositories grew the same process independently, and each has things the others lack. The cost shows in the
inventory of 2026-10-08: a rule fixed in one repository is ported by hand to the others weeks later, or never. The
template repository ends that. It is **the upstream and the superset**: one place where every operating pattern lives
in its best form, from which a new repository starts on **day 0** doing all of it, and against which an existing
repository is checked, so that an improvement made once reaches all of them.

The requirements, in the owner's own words of 2026-10-09, this design must meet:

- it is "the maxi, the base for all operating patterns", and it drives the three existing repositories and future ones;
- it can generate the graph, and includes the base generated graph;
- it is a uv and Python template: the coding standards, the core context and instruction files, a mock `src/` with
  faux libraries;
- it deals with UX and does not avoid it;
- it has a mock or stub of every thing, step and process that makes the three repositories an improvement;
- a repository spun up from it starts doing all of this on day 0, through an initialise mechanism, with a Makefile for
  the basic commands.

## What already exists, and where

The inventory found the pieces already built, scattered. This is the supply the template draws on (line counts as read
2026-10-09):

| Piece | HogShade | LargeWorlds | SpriteJammer |
| --- | --- | --- | --- |
| Entry file (`AGENTS.md`) | 83 lines | 99 | 92 |
| Tool pointer (`CLAUDE.md`) | 20, a pointer | 655, carries standards | 297 |
| Standards files | python, wgsl, content, workflow, definition of done, ledger | python, testing, definition of done, ledger | adds `tooling.md`, `ci.md`, `documentation.md`, `performance-budget.md` |
| Docs checker | `tools/check_docs.py`, 487 lines, with the `terms` check | `tools/check_docs.py`, 488 | `scripts/check_docs.py`, with the pending-review threshold |
| Task runner | none | launchers | `Makefile` (every recipe one `uv` call, GNU Make 3.81 safe) and `scripts/check.py`, the full gate and the CI parity oracle |
| Git hooks | none | none | `.githooks/` (pre-commit, pre-push, prepare-commit-msg, post-*) |
| CI | one Windows job | two legs | Windows and Linux matrix, and `ci.md` |
| Journal | yes, per day | no | yes |
| UX mock pass, smoke gate | no | yes | no |
| Branch ownership, lanes, pending review, devblog | no | whose-branch tool | lanes, queue, devblog |
| Graph, hygiene, `terms` check, generated-doc checks | yes | partial | no |

SpriteJammer is the parent of the process (HogShade's definition of done says it is "adapted from" it) and already
owns the task-runner and hooks half. The reading of the answer "HogShade first" is therefore: HogShade is the base for
the *checks and the documents*, because it is the most mechanised; SpriteJammer's task runner, hooks, CI standard and
documentation standard are taken whole, because HogShade has none.

## The shape

### What the repository is

A private GitHub *template repository*, `ai-first-template`, in the owner's account. It is also a working project:
its own CI runs every check against its mock `src/`, so a template that does not work fails its own build before any
repository can be made from it. It follows its own process (a board, a handoff, a ledger of its own); see
"The template runs the framework on itself".

The tree below is the **payload**: what a new repository receives.

```text
ai-first-template/
  framework.toml           the template version; which modules are on (a project's copy: its choices)
  project.json             a project's values: name, owner identity, default branch, slug, hygiene ids
  framework.lock           a project's copy only: the version synced from, the hash of each managed file
  AGENTS.md  CLAUDE.md     the entry file and the thin tool pointers (parametrised)
  Makefile                 the dispatcher; every recipe one `uv run` call (the SpriteJammer rule)
  pyproject.toml uv.lock   uv, ruff, pytest; Python 3.11 floor
  .githooks/  .github/  .claude/skills/
  Docs/                    map, glossary, board, handoffs, journal, decisions, design, superpowers/{specs,plans},
                           standards/, knowledge/ (the description, the graph and its page), specimens/
  tools/                   init.py  framework_sync.py  check.py  check_docs.py  check_hygiene.py
                           check_log_format.py  render_framework_graph.py  smoke.py
  src/                     the mock project: faux libraries on a neutral domain
  tests/                   the tools' tests and the faux libraries' tests
```

### The three file classes

Every file is exactly one of:

| Class | Template's job | Examples |
| --- | --- | --- |
| **Managed file** | Owns it; a repository's copy must match | `tools/check_docs.py`, `render_framework_graph.py`, the graph data and page, the framework ledger, the framework standards, the review skills |
| **Parametrised file** | Owns the skeleton; the project owns the values | `AGENTS.md`, `CLAUDE.md`, the CI workflow, the hygiene identifiers, the PR template's repository slug |
| **Project-owned file** | Ships the empty shape only; never overwrites | the board, the handoff, the journal, ADRs, designs, specs, plans, the project's glossary rows and ledger entries, `src/` |

The ledger is two files: `failure-modes.md` (managed; the framework's entries, as triggers) and
`failure-modes-project.md` (project-owned); the entry file tells an agent to load both. The glossary is one
project-owned file seeded with the framework's own terms; the docs check reads it.

### Modules

`framework.toml` switches modules; a module is a group of files, checks and CI steps that arrive and go together.

| Module | Default | What it holds | Comes from |
| --- | --- | --- | --- |
| `core` | on | entry file, docs map, handoff, board, glossary, ledger, ADRs, design chain, definition of done, workflow, docs check, PR template, `local-review` and `review-and-pr` skills | H, with S |
| `journal` | on | one file per day, the index, the journal-day check | H, S |
| `ux` | on | the UX mock pass as a stage of the chain, `standards/ux.md`, the folder shape for accepted mock canvases, the headless smoke gate, the faux UI library | L |
| `python-uv` | on | `pyproject.toml`, ruff, pytest, `python.md`, `testing.md`, the f-string log check, the boundary-test pattern | H, L, S |
| `tasking` | on | the Makefile, `tools/check.py` (the gate and CI parity oracle), `tooling.md`, `ci.md`, the hooks | S |
| `hygiene` | on, empty | the retired-identifier check with an empty list | H |
| `graph` | on | the generator, its test, the base graph and page, its CI step | H |
| `harness-adapters` | on | `AGENTS.md` as the single context, the generated adapters, the skills mirrors, `sync_adapters.py`, the `commit-msg` hook, the neutral-wording lint, the conformance probes and the compatibility matrix | new, from the inventory of harnesses |
| `specimens` | on | the specimens, their map, the walkthrough increment, the generator's coverage check | new |
| `lanes` | off | lane-prefixed board ids, the pending-review queue and threshold, deferred bugs as issues | S |
| `branch-ownership` | off | the whose-branch tool | L |
| `devblog` | off | the weekly public memo and its privacy boundary | S |
| `wgsl` | not in v1 | stays HogShade's | H |

A module that is off leaves no files behind; the pattern stays in the template for the next repository to choose. A module marked on that has not been built yet is `planned` in `framework.toml` and `init` skips it, so every increment's template is whole: the defaults are exactly the modules delivered so far. The module table is the one authority on defaults; other text refers to it.

### The initialiser

`tools/init.py`, one component with one classifier shared with the sync check.

- `init new`: asks for the project values (or reads `--answers answers.json`), writes `project.json` and
  `framework.lock`, generates the parametrised files, seeds the project-owned files with day-0 content (below),
  installs the hooks, runs `uv sync`, removes the modules that are off, and ends by running every check.
- `init adopt`: for a repository that predates the template. It classifies each existing file, reports what differs
  from the template and what is project content, and proposes one pull request. It never overwrites a project-owned
  file. This is the retrofit path for the three existing repositories.
- `init --github`: applies required checks, branch protection and automated review through `gh`. It lists each change
  and asks first, because it is outward-facing.
- `init --clear-specimens`: removes the faux `src/`, the specimens and the walkthrough once a real project starts, and turns the `specimens` module off in `framework.toml`; it edits no managed file.

Always: idempotent; `--dry-run` prints the full plan; a written record of what it read, decided and wrote and why; a
test in the template's own CI that runs `init new` into a temporary directory and requires every check to pass.

### Day 0

A repository made from the template, after `init new`:

- the **handoff** says "Day 0" with a checklist: run the conversation and lock with the owner, write the first
  pre-spec design, put the first increment on the board;
- the **board** has its sections and one gate, G1, "name the first increment"; the **glossary** holds the framework's
  terms; **ADR-001** is "adopt the framework", with the template version and a revisit-if; the first **journal** entry
  exists;
- the **hooks** are installed, **CI** is the same stage list as `make check`, and everything is green;
- the first agent session reads `AGENTS.md`, then the handoff, and starts the design chain; the UX mock pass is in the
  chain for anything a person will touch.

Acceptance, which is also the template's test: from a fresh clone, `init new` runs and `make check` passes on both
operating systems.

### The Makefile

Taken from SpriteJammer whole, with its hard rule: every recipe is one `uv run` call; logic and composition live in
Python (`tools/check.py`), so a machine without Make loses typing and not behaviour. GNU Make 3.81 compatible. The test
that enforces the rule travels with it. Targets: `help` (default), `init`, `setup`, `check`, `test`, `fix`, `graph`,
`sync`, `smoke`.

### The template runs the framework on itself

The template is a project as well as a payload, and it follows its own rules while it is developed and maintained.
To keep the two apart the shippable files live in `payload/`, and the repository root is the template's **own
instance** of the framework, generated from the payload with its own `framework.lock`. In increment 1 the root is written by `init new` pointed at the repository itself (`--target .`, the template's own values as `--answers`): it writes the managed and parametrised files from `payload/` and seeds a project-owned file only if it is absent. `init adopt`, which classifies an arbitrary existing repository, comes in increment 5 and is what retrofits the three repositories; the root needs only the simpler path. The root has its
own board, handoff, journal, ADRs, designs, specs, plans and a project ledger of lessons about developing the template.
None of that is in the payload.

- The template's CI runs the sync check at the root, so it is its own first downstream. Editing a managed file at the
  root instead of in `payload/` fails the check.
- A change to the framework is an increment through the same chain (lock, spec, plan, test-first, review, pull
  request, owner's merge), and a change to the docs checker has to pass the template's own CI before any other
  repository can receive it.
- `init new` is tested by building a repository from `payload/` into a temporary directory and running every check.
- Improvements flow in one direction: found in any repository, proposed as a pull request to the template (edited in
  `payload/`), released as a tag, reported by each repository's `--upstream`, ported by hand until `--update` exists.
- The first version is extracted from HogShade by hand, so self-hosting starts from the second version.
- A new rule that would flag the template's own older documents is introduced with a grandfathered set, as in HogShade.

### Harness neutrality

The framework does not belong to one AI model or tool. Claude Code, Gemini CLI and GitHub Copilot are the starting
set; Codex and Cursor are opt-in. The rule: **the least per-harness text, and no duplicated context.**

- **`AGENTS.md` is the only place context lives**, a pointer map into the standards files.
- **Harness adapters are generated and hold nothing.** `CLAUDE.md` is `@AGENTS.md`; Gemini CLI is pointed at
  `AGENTS.md` by a one-line `context.fileName` setting in `.gemini/settings.json` rather than a second file;
  `.github/copilot-instructions.md` is a few lines pointing at `AGENTS.md`. `tools/sync_adapters.py` writes them from the
  harnesses `framework.toml` enables and `--check` fails if an adapter gains text of its own.
- **Skills** follow the open `SKILL.md` format with one canonical home, `.agents/skills/`; the generator writes
  identical mirrors where each enabled harness looks (`.claude/skills/` for Claude Code) and checks them. No symlinks:
  they are unreliable on Windows.
- **Enforcement lives where every harness passes**: git hooks, CI and the Makefile. The rule that commits carry no AI
  attribution is a `commit-msg` hook, not a Claude-only setting. Harness settings, permissions and agent hooks stay
  per-tool and optional.
- **Review is a role.** The "fresh eyes" review is written as "review in a context that has not seen the author's
  reasoning" (a subagent, a second session, another model, Copilot), not as one tool's call. Author and reviewer are
  roles; the existing practice of one model reviewing another's pull request is the pattern.
- **Neutral wording.** Managed documents say "agent" or "assistant"; a harness is named only in the adapter list and the
  compatibility matrix, and a lint enforces it. A user's own memory feature is never the record (the framework already
  says so).
- **Conformance probes prove the adapters.** Each enabled harness must reproduce a canary from `AGENTS.md`; CI cannot run
  every harness, so the compatibility matrix records who ran each probe and when. Whether Copilot's code review reads
  `AGENTS.md` or only `.github/copilot-instructions.md` is the first thing the probes settle.
- **Scoped instructions** (nested `AGENTS.md`) wait for a later increment: their loading differs most across harnesses.
- **The matrix goes stale** because loading rules change often: it carries last-verified dates and is re-checked on a
  schedule. The facts it starts from were gathered on 2026-10-09, partly from third-party articles, and must be checked
  against each vendor's current documentation before the build.

### Specimens and the walkthrough

Every graph node gets a **specimen** in `Docs/specimens/`: a filled-in example, not a blank. The map from node to specimen lives in `Docs/specimens/specimens.json` (a path, or `null` with a written reason), not in the managed graph data, and the `specimens` module owns it: `render_framework_graph.py --check` requires the map to cover every node while the module is on, so the template cannot gain a concept without an example. Clearing the specimens removes the map with the files and turns the module off, and the graph data is untouched, so there is never a path to a deleted file and the sync check sees no managed file change. One **walkthrough increment**, a fictional feature
on the faux libraries, goes through every stage end to end (conversation and lock, design, UX mock pass, spec, plan,
test-first code, review, pull request, journal, ledger, merge), as a directory of its real artifacts. A new project
reads it before it starts and deletes it with `--clear-specimens`.

### The mock `src/`

Three small packages on a neutral domain (a task-list engine): `core` (pure), `app` (depends on `core`), and `ui` (a
headless view of `app`). They exist so that the boundary test, the log check, ruff, pytest and the smoke gate have
something to run on, and so the UX mock pass has a real surface. Nothing in them resembles a real project.

### The sync check

`tools/framework_sync.py`, report-only in v1, two reports:

- `--check` (offline, so CI can run it anywhere): for each managed file, compare the project's copy with the locked template version and report a difference as a finding, unless `framework.toml` lists an override with a reason. It catches local edits to a managed file; it cannot know the template has moved on.
- `--upstream` (needs the network and `gh`): read the template repository's latest tagged version and report "lock is behind: v1 locked, v3 current, N managed files changed" with the changed paths. It exits non-zero only past a configurable age, so a repository is told it is behind without a red build on the day the template releases; the weekly review routine runs it across the repositories.

Together they deliver the report half of propagation: an improvement made once is visible in every repository as soon as `--upstream` runs. Applying it is `--update` (pull a newer version as a pull request), a later increment, and until it exists the port is by hand, which the report makes visible and does not remove. The project overlay for the graph also comes later. Files arrive by copy plus the lock: no submodule, no subtree, no package.

## Contested files: the proposed pick for each

Where the repositories differ, this is the version I would take and why. The owner overrules by exception; a row with no
objection stands. "Confirm in the extraction" means the diff has not been read in full yet.

| File or area | Pick | Reason |
| --- | --- | --- |
| Entry file | HogShade's shape | A pointer map of 83 lines; the others carry more |
| Tool pointer | HogShade's 20-line pointer | LargeWorlds' 655 lines are standards that belong in standards files; its project content becomes scoped instructions |
| Glossary | HogShade's structure (retired terms struck, `terms` check) | The only one a check reads against designs, specs and plans |
| Definition of done | SpriteJammer's text as the parent, HogShade's autonomy protocol and significant-increment rule folded in | HogShade's is adapted from it; confirm in the extraction which rows each added |
| Ledger | The framework's entries as one managed file, each entry classified framework or project | Entry by entry; the classification is a table in the spec |
| Python standards | One core of rules plus a project section; LargeWorlds' length is not the target | The three are 137, 355 and 228 lines; confirm which rules are shared |
| Workflow | HogShade's and SpriteJammer's (the same lineage), plus the UX mock pass from LargeWorlds | LargeWorlds has no workflow file; its chain is in a ledger entry |
| Testing standard | LargeWorlds' | HogShade and SpriteJammer have none at that path |
| Docs checker | One checker, the union of the three, each feature behind its module | Three diverged copies of one file; confirm in the extraction |
| Task runner, hooks, CI, `tooling.md`, `ci.md` | SpriteJammer's, whole | The others have no equivalent |
| Documentation standard | SpriteJammer's | The others have none |
| PR template | HogShade's (it carries the Terms checkbox) | Near-twin of SpriteJammer's |
| Board shape | The common sections of the three | Same lineage; lanes arrive with the `lanes` module |
| Journal | The per-day form (HogShade) | A docs-check rule exists for it |
| Skills | `local-review` and `review-and-pr`; the host skills stay behind | The rest are tied to Maya, shaders or the orchestrator |

## Improvements the template carries, not copies

Things the inventory found wrong in all three, built right once and backported through the sync check:

| Improvement | Because |
| --- | --- |
| A line limit on the handoff, and a check that a "Last updated" date is not older than the newest content | HogShade's handoff reached 270 lines; SpriteJammer's is 876 |
| A closed status vocabulary for specs and plans, not free-form | LargeWorlds' statuses are free text, so the check cannot tell what is current |
| A rule stated in one place, and a lint for hand-kept counts | LargeWorlds states its whose-branch rule in several files |
| Every generator has a `--check` and a CI step | Generated pages drift when nothing checks them |
| The framework's own terms are in the glossary on day 0 | They were missing until the glossary rule was applied to the framework |
| Ask-before-pulling-forward is a checklist line in the template | ledger entry 22 |

## Increments (each its own spec and plan once this is locked)

Order answered by the owner. Each leaves the template green and usable; the day-0 test is the acceptance from the
first.

1. **Core, init, Makefile, and the minimum runtime**: the `core` and `tasking` modules, a minimal `python-uv` (`pyproject.toml`, `uv.lock`, ruff, pytest, the f-string log check), `hygiene` (empty) and `graph` (copied as they stand in HogShade), `harness-adapters`, `init new` (including `--target .` for the root) and `check`, the template's own CI, the `payload/` layout with the root generated from it, the day-0 seed. `ux` and `specimens` are `planned` and skipped. Acceptance: fresh clone, `init new`, `make check` green on both operating systems. About 6 to 8 d.
2. **The mock `src/` and the stack standards**: the faux libraries, the boundary test, `python.md` and `testing.md` in their reconciled form. 1 to 2 d.
3. **Specimens and the walkthrough**, the `specimens` module and its coverage check, `--clear-specimens`. 2 to 3 d.
4. **UX**: the `ux` module, the mock-pass stage, `ux.md`, the smoke gate, the faux UI library. ½ to 1 d.
5. **The sync check** (`--check` and `--upstream`) and `init adopt`, then the retrofit of HogShade, LargeWorlds and SpriteJammer, one each, 1 to 2 d each. 1 to 2 d for the tool.

Later, not in this design: `--update`, the graph overlay, further stacks (WGSL).

## Risks

- **The template becomes a fourth copy.** Mitigation: the sync check, and every improvement made in the template first.
- **The maxi is too heavy for a small project.** Mitigation: modules; the default is the table's "on" set (the core and the modules every repository needs), and a repository turns off what it does not want.
- **The initialiser is the hard part** and a bug in it ships to every new repository. Mitigation: its test in the
  template's CI, `--dry-run`, and idempotence.
- **Idea velocity.** This is a month-scale piece of work whose parts each look small (ledger entries 11 and 22).
  Mitigation: increment 1 is the only commitment this design asks for.

## Decisions already taken (owner, 2026-10-09)

| Question | Answer |
| --- | --- |
| Name and home | `ai-first-template`, private, the owner's account |
| Sync strength | Report-only first; `--update` later |
| Extraction base | HogShade first; the others win a file only where better |
| Stacks in v1 | Python and uv only; WGSL stays HogShade's |
| Delivery | Copy plus `framework.lock` |
| Default modules | The module table's "on" set: core, journal, UX, Python/uv, tasking, hygiene (empty) and graph; lanes, branch ownership and devblog off |
| Ledger | Two files: the framework's (managed) and the project's |
| Graph overlay | A later increment |
| Mock `src/` | A neutral toy domain: `core`, `app`, a headless `ui` |
| Increment order | Core, init and Makefile; stack and mock `src/`; specimens; UX; sync check |
| Contested files | I propose per file (the table above); the owner overrules |
| Where this lives | HogShade's `Docs/design/` until increment 1's close-out (plan task 12); see *Amendments after acceptance* |
| The template runs the framework on itself | The shippable files in `payload/`; the root is the template's own instance, synced from it |
| Harness neutrality | `AGENTS.md` is the only context; generated adapters for Claude Code, Gemini CLI and Copilot (Codex and Cursor opt-in); skills canonical in `.agents/skills/` with generated mirrors; conformance probes |
| When the repository is created | After the lock, as the first act of increment 1; the creation itself is outward-facing and needs the owner's go at that moment |

## Answers at the lock (owner, 2026-10-09: "locked")

1. **The contested-file table stands**: no row was objected to. Where it says "confirm in the extraction", the
   extraction reads the diff and records the result in the increment's spec.
2. **The licence line** was not answered. Default, two-way: the template carries a stated "all rights reserved" notice
   until the owner says otherwise.

## Amendments after acceptance

- **2026-10-09, found by plan task 1 (a clarification, not a change of substance).** "SpriteJammer's, whole" for the task
  runner, hooks, CI, `tooling.md`, `ci.md` and `documentation.md` means *its generic parts whole*: the template takes them
  as the base and leaves out what is specific to SpriteJammer (the LFS hook stubs, the demo targets and launchers, the
  `content` stage, the private-dependency token step, the devblog design, the `cspell` word list, `readme-current`) and
  fixes the defects the pass found (no hook installer, substring-matched parity tests, stale counts, the `Adopted`
  status). The list is in the increment 1 spec's *What the build found*. The owner's pick, SpriteJammer as the source for
  this layer, is unchanged.
- **2026-10-10, owner's answer to a review finding (changes a locked decision's timing).** The design, the increment 1 spec
  and plan stay in HogShade after the template repository was created on 2026-10-09; they move at **increment 1's
  close-out (plan task 12)**, not at creation. At task 12 the build imports them as the template's own design, spec and
  plan and marks HogShade's copies Superseded with a pointer. Until then there is one copy, here, so no HogShade link
  breaks and nothing drifts between two.

## Terms introduced

**Template repository**, **Framework module**, **Managed file**, **Parametrised file**, **Project-owned file**,
**Specimen**, **Day 0**, **Initialiser**, **Framework lock**, **Sync check**, **Payload**, **Harness adapter** and **Conformance probe**: all in [../glossary.md](../glossary.md),
added with this document (the glossary rule, ledger entry 20).
