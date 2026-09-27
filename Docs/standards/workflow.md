# Workflow: from conversation to merge

**Status:** Accepted (owner, 2026-09-26 for the stages; 2026-09-27 for the records table)
**Last updated:** 2026-09-27
**Read with:** [definition-of-done.md](definition-of-done.md) · [../README.md](../README.md) · [../journal/README.md](../journal/README.md)

**The order is: roadmap, then align in conversation and lock a pre-spec design, then one spec, one
plan and one test-driven build per increment, reviewed, closed out, merged by the owner.** The
pre-spec design is a hand-written lock of what was discussed and decided; the superpowers skills take
over from there (owner, 2026-09-26).

## The stages

| # | Stage | Produces | Lives in | Gate |
| --- | --- | --- | --- | --- |
| 0 | **Roadmap** | Tracks, phases, order, what waits on the owner | [../ROADMAP.md](../ROADMAP.md) | Amended as decisions land |
| 1 | **Converse and lock a design** | Intent, acceptance criteria, decomposition, decisions locked, open questions | `Docs/design/<date>-<topic>.md` | **The owner locks it** |
| 2 | **Spec** | One increment's exact deliverable, interfaces, acceptance gate, out of scope | `Docs/superpowers/specs/` (brainstorming skill from the lock) | Owner approval |
| 3 | **Plan** | Ordered tasks with checkboxes, each small enough to verify | `Docs/superpowers/plans/` (writing-plans skill) | Owner review |
| 4 | **Build** | Code and tests, test-first; a NumPy twin and a GPU test for every core function | A branch `type/<slug>` | Tests green on CI, `build_shaders.py --check` |
| 5 | **Review** | Copilot on every push; `/local-review diff` on a significant increment | The pull request | Findings fixed or declined with a reason |
| 6 | **Close out** | Plan task ticked with its verification, spec amended, decision log, journal, handoff, knowledge files | Per [definition-of-done.md](definition-of-done.md) | `check_docs.py` green |
| 7 | **Merge** | The increment on `master` | GitHub | **The owner merges and deletes the branch** |

A plan task is ticked when its verification ran, never when its code was written. A phase is done
when the spec's acceptance gate passed and the roadmap, README and affected design doc were updated.

## Who owns what

A program of several increments has several records, and each owns one thing. Duplicating between
them is how they drift.

| Record | Owns | Does not own |
| --- | --- | --- |
| **Roadmap** | The tracks, the phases, the owner gates | Any increment's design |
| **Design doc** | **Why**: goal, options, what is decided and why | Status, or an increment's detailed design |
| **Spec** | **What one increment builds** and how it is verified | The program; it links up to its design |
| **Plan** | The ordered tasks and their verification notes | Rationale beyond a line |
| **Board** | **Status**: gates, now, next, blocked, Icebox | Rationale beyond a line |
| **Decision log** | Every decision stated in conversation, and where it is formalised | The narrative that led to it |
| **Journal** | **The narrative**: what happened, which beliefs changed, where BATS made the difference | Current truth |
| **Handoff** | **The snapshot** a new session needs | History |
| **Knowledge files** | One topic each, for an agent: how the orchestrator works, the toolchain | Decisions (they link to the log) |

## Standing rules at every stage

- **A mentioned feature is not a work order.** It goes on the board's Icebox with a cost, unless the
  owner says build it or it blocks work in flight.
- **Two-way doors are decided and recorded in the PR's *Decisions* table; one-way doors are asked.**
  The autonomy protocol in [definition-of-done.md](definition-of-done.md).
- **Never stop a process you did not start; never launch a DCC beside an orchestrator worker for it.**
- **Work lands through a pull request the owner merges.** The assistant never merges.
- **Record the orchestrator's impact where it happened**, in the journal's `→ BATS:` line and the
  running summary in [../knowledge/job-orchestrator.md](../knowledge/job-orchestrator.md).
