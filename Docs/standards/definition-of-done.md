# Definition of done, and the autonomy protocol

**Status:** Accepted (owner, 2026-09-27, ported from SpriteJammer with its reasoning)
**Last updated:** 2026-09-27

## Principle

**Minimal now, growing with the codebase.** Process that does not catch a real failure is tax. Every
rule here exists because something drifted or broke, here or in SpriteJammer, whose definition of done
this is adapted from. The growth ladder at the bottom says what gets added when.

## DoD: an increment

An increment ends with the docs comprehensively updated so nothing drifts. A checklist item saying
"keep the docs consistent" degrades into a rubber stamp within a month, so as much as possible is
mechanised:

```bash
uv run python tools/check_docs.py          # links, status headers, the journal index and day, the ADR index
uv run python tools/check_hygiene.py       # no studio identifier outside the allowlist
uv run python tools/check_log_format.py    # log calls are f-strings, not lazy %-format
uv run pytest                              # the suite; tests/test_check_docs.py runs the checker on the corpus
uv run python tools/build_shaders.py --check --require-compilers   # after any core change
```

| # | Requirement | Enforced by |
| --- | --- | --- |
| 1 | Tests and lint pass on CI (`ruff format`, `ruff check`, `pytest`; one Windows leg, because the Maya shell needs fxc and dxc) | CI |
| 2 | Generated hosts are current and compile on every compiler after a core change | `build_shaders.py --check --require-compilers`, in CI |
| 3 | Hygiene: no employer names, personal email only, no studio files, Apache-compatible dependencies | `tools/check_hygiene.py` in CI and before every push; judgment for the rest |
| 4 | Docs match reality: the plan task ticked with its verification, the spec amended if an interface changed, `Docs/README.md` status rows, the affected knowledge file | `check_docs.py` for links and status; judgment for content |
| 5 | The decision log has every decision made in conversation, with where it is formalised | Judgment |
| 6 | [`../journal/`](../journal/README.md) appended for this session | `check_docs.py` (`journal-index`), plus judgment on content |
| 7 | [`../handoffs/CURRENT.md`](../handoffs/CURRENT.md) reflects present state when work was interrupted, a decision changed or the state moved | Judgment |
| 7a | [`../plan/BOARD.md`](../plan/BOARD.md) updated when a row lands, a gate closes, or an idea is said out loud; a landed row keeps its PR number and is struck through, never deleted | `check_docs.py` for its status line; judgment |
| 8 | **Every two-way-door decision is in the pull request's *Decisions* table**, no more than eight | The template's checkbox; judgment |
| 9 | Copilot's review assessed: each finding fixed or refuted with evidence, answered on its thread | The `review-and-pr` skill |
| 9a | A significant increment has had `/local-review diff`, its findings answered in the PR's *Review* section | The template's checkbox; the rule below |
| 10 | Landed through a pull request the owner merges | Process; the assistant never merges |

### What `check_docs.py` catches, and why each check exists

| Check | The failure it catches |
| --- | --- |
| `links` | A renamed file leaves every link to it dangling; a link whose case differs from the file passes on Windows and fails on Linux CI |
| `status` | Without a status header a reader cannot tell a decision from a hypothesis or a live document from a stale one |
| `journal-index` | A session file linked from nowhere is a session that did not happen for the next reader |
| `journal-day` | A day that changed the handoff has a journal file of its own; one file per session *and per day* (owner, 2026-10-03) |
| `adr-index` | An unindexed ADR is invisible to anyone browsing decisions |
| `terms` | A design, spec or plan without a `## Terms introduced` section, or naming a term with no glossary row: a word used across documents and code whose meaning only its author holds (ledger entry 20). Documents that predate the rule (2026-10-08) are listed in `TERMS_GRANDFATHERED`; the set only shrinks |
| `vocabulary` | A retired term used as if current: two names for one concept means an agent retrieves it by neither; the glossary's struck-through rows are the list |

## The autonomy protocol

> Keep going until you feel there is a real human-in-the-loop review need or decision. If a decision is
> a two-way door and easily changed, just go with an option and log it. If too many of these "didn't
> review" decisions queue up, stop for thorough review. (Owner, SpriteJammer, 2026-09-06; adopted here.)

### Two-way door: decide, record, continue

Cheap to reverse, no data loss, no outward effect, nothing built on top yet: naming, file layout,
document structure, which of several adequate implementations, tooling before anything depends on it,
wording, test structure, anything reversible in under an hour.

**Record it in the pull request's *Decisions* table** and keep moving. The owner's merge is the
review, so a decision not in the table was not reviewed.

### One-way door: stop and ask

Expensive to reverse, or the owner has already shown they hold an opinion:

- A new ADR, or a change to a locked design
- Anything outward-facing: merging, publishing, posting outside this repository's own pull requests,
  anything that touches the open-source clearance
- Deleting or rewriting history: the journal, the decision log, a superseded document
- Stopping a process the assistant did not start; launching a DCC beside an orchestrator worker
- Topics the owner has already corrected: artifact naming, `os.path`, process ownership, the
  order of operations
- Anything that invalidates a recorded verification

### The backstop

**Eight decisions per pull request.** More than that and the PR is too big to review in one sitting:
split it. Eight keeps the table a five-minute read, low enough that a wrong assumption cannot compound
far and high enough that the autonomy is real.

A decision the owner reverses in review is changed before merge, and the row says so. A reversal is
part of the record, not an erasure.

## Journaling cadence

Continuous, see [`../journal/README.md`](../journal/README.md). One file per session and per day, appended as work
happens: every meaningful exchange, each step that changed or taught something, whenever a belief
changes, and whenever the orchestrator made the difference.

## When `local-review` runs

Owner (SpriteJammer, adopted here): *"not on every single change, but definitely on significant or
large increments of work."* The skill is `/local-review`
([`.claude/skills/local-review/`](../../.claude/skills/local-review/SKILL.md)): an isolated reviewer
against this repository's standards and a ten-metric rubric with a 7/10 baseline.

**Significant** means any of: a new core module or model; a new host or a change to a host's frame
or parameter contract; a new job or tool; roughly 200 or more changed lines of Python or WGSL outside
`tests/`. **Not** documentation-only changes, dependency bumps, test-only changes or small fixes.

Run `/local-review diff` on the branch before asking for a merge, and put its score table in the
pull request's *Review* section with every finding fixed or declined with a reason. The trigger is
the PR template, not memory. Copilot's review is the automatic one; this is the deliberate one, and
they catch different things.

## Growth ladder

| Trigger | Add |
| --- | --- |
| The standards pass | The coding standards page, the first ADRs, `status` on every governed document, the failure-modes ledger seeded from this repo's own failures |
| The comparison framework | A verification DoD: a capture set per host, a report, pass / needs-review / fail |
| A second contributor | Branch protection, required reviews |

Do not add a tier before its trigger. A DoD for code that does not exist is ceremony.
