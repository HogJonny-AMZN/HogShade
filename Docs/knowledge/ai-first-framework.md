# The AI-first repository framework

**Status:** Living. Written 2026-10-08 from a read of three repositories that grew it independently
(HogShade, LargeWorlds, SpriteJammer). The claims about HogShade were checked against its files; the
claims about the other two come from the read-only inventories of that date and are marked as such, so
treat them as leads until a template's sync check reads them. The concepts and their
relations are data: [ai-first-framework.graph.json](ai-first-framework.graph.json), drawn in
[ai-first-framework-graph.md](ai-first-framework-graph.md). Nothing below depends on what the three
repositories build.

## The thesis

An agent session is stateless and a repository is not. Everything an agent needs to continue the work, to
know what it must not decide, to speak in the project's words and to catch its own mistakes has to be
**a file in the repository, found by a short path, and checked by something that goes red**. The rest of
the framework is the consequence: a file for each kind of knowledge, a rule for who may change it and a
check for each rule that a machine can hold.

It is called AI-first because the primary reader of the process documents is a session that has read
nothing else, and because the owner's attention is the scarce resource: the framework spends the owner's
time only on the decisions that are theirs (the gates and the one-way doors) and on the merge, and
makes every other decision cheap to take, record and reverse.

## What goes wrong without it

Seven failures recur in every AI-assisted repository, and each artifact below exists to stop one:

| Failure | What the agent does | What stops it |
| --- | --- | --- |
| **Forgetting** | Starts each session from the code and re-derives, or contradicts, last week | The handoff, the journal, the decision log |
| **Drift** | Two documents state one fact; one goes stale; a later session believes the stale one | One rule one home; pointers, not summaries; the docs check |
| **Overreach** | Builds an idea that was only mentioned; decides what was the owner's | The board's icebox and gates; one-way doors; owner merges |
| **Optimism** | Reports done, passing or fixed before the evidence exists | Claims after evidence; the definition of done; the pull request template |
| **Vocabulary** | Coins a second name for a concept, or a word nobody defined | The glossary and its mechanised rule |
| **Repetition** | Makes a process mistake the repository has already paid for | The failure ledger, loaded before work starts |
| **Collision** | Two sessions edit one branch, one number, one living document | Parallel-session rules; branch ownership; lane ids |

## The eight layers

The graph groups the framework into eight layers, from what is read first to what makes the rules bite.
Each layer holds artifacts, the rules about them and the checks on them.

| Layer | Question it answers | Core artifacts |
| --- | --- | --- |
| **Entry** | What do I read first, and which file wins? | the entry file, tool pointer files, scoped instructions, the documentation map |
| **State** | Where is the project, and what is waiting on whom? | the handoff, the board (gates, icebox, landed rows), the roadmap |
| **Intent** | What is about to be built, and in what chain? | pre-spec design, spec, plan, spike, mock pass |
| **Decision** | Who decides what, and where is it recorded? | the ADR, the decision log, the autonomy protocol, the decisions table |
| **Rule** | What are the standing rules and words? | standards, the definition of done, the failure ledger, the glossary |
| **Narrative** | What happened, and what did we stop believing? | the journal, the devblog |
| **Evidence** | What is the proof? | verification pictures and logs, research notes, review records |
| **Mechanics** | What makes the rules bite? | the docs check, hygiene check, boundary tests, CI, the pull request template, skills, reviews |

## One session

```text
read   entry file -> handoff -> board (gates first) -> the document the task names
work   design chain: converse and lock -> design -> spec -> plan -> test-first build
       decide two-way doors and log them; stop at one-way doors and gates
close  checks green -> docs, board, handoff, journal, ledger true -> local review
       -> pull request (the template) -> automated review answered thread by thread
merge  the owner reads the decisions table and merges; the assistant records what landed
```

The close is the part that most often goes missing, so the definition of done is a checklist and the
pull request template repeats it: a change that makes the repository's account of itself untrue is not
done, however green its tests.

## The principles

Each is a node in the graph; the link is the file that states it, and the one rule that states it is
there, not here.

1. **A pointer does not go stale; a summary does.** [AGENTS.md](../../AGENTS.md) points and states no count
   or status; the only status is [the board](../plan/BOARD.md).
2. **One rule, one home.** A rule lives in a [standard](../standards/); everything else links to it.
3. **A snapshot is not a log.** [The handoff](../handoffs/CURRENT.md) is cut to what is true now; history
   is the [journal](../journal/README.md) and git.
4. **A mentioned feature is not a work order.** It lands on [the board's](../plan/BOARD.md) icebox with a cost;
   a design is built from only once the owner has locked it ([workflow](../standards/workflow.md)).
5. **Two kinds of door.** Two-way doors are decided and logged; one-way doors are asked
   ([definition of done](../standards/definition-of-done.md), the autonomy protocol).
6. **Supersede, do not rewrite.** History is amended in a section of its own or replaced by a new record
   ([ADRs](../decisions/README.md)).
7. **Claims follow evidence.** Done, passing and fixed are reported after the check ran, and a check is
   believed only after it has produced the other answer ([ledger](../standards/failure-modes.md), entries 2 and 6).
8. **One word per concept.** [The glossary](../glossary.md); a new word gets its row first (ledger entry 20).
9. **Mechanise the class.** A process failure becomes a ledger entry in the same change, and a check where
   one can hold it ([ledger](../standards/failure-modes.md)).
10. **The owner's merge is the review.** The assistant never merges; the decisions table is what the owner
    reads to merge in minutes ([pull request template](../../.github/pull_request_template.md)).

## The mechanisation ladder

A rule is only as strong as how it is held. In rising strength:

1. **Prose** in a standard. Held by an agent that read it.
2. **A checklist line** in the definition of done and the pull request template. Held by an agent that is
   about to claim done.
3. **A review rubric line.** Held by a fresh-eyes reviewer, who sees the diff without the author's context.
4. **A check** that goes red in CI. Held by the pipeline, whoever the author is.
5. **A generator** that writes the document from the source of truth, with a `--check` that fails when the
   committed copy is stale. Held by construction: the document cannot drift because nobody writes it.

The glossary rule shows the climb: it was prose, it failed on 2026-10-08 (the ledger's entry 20), and it now
sits on every rung: the vocabulary bullet of the entry file, the definition-of-done row, the template
checkbox, a rubric finding, and a `terms` check in the docs check. A rule that sits only on rung 1 is
a wish. This graph's own page is on rung 5.

## How the framework itself fails

The framework is a set of documents, so it drifts like one. The inventory of 2026-10-08 found its own
failures in the repository that describes them:

- **The handoff became a log.** HogShade's grew to 270 lines, with a 5,300-character "last updated" line and
  about 200 lines of status reports from three weeks, which is ledger entry 15, in the file that entry names.
  The inventory found SpriteJammer's far larger still. Fix: cut to a snapshot (a line, the state, what the owner said that is written
  nowhere else, the open questions). Open: no check compares a document's date with its content.
- **A hand-kept count went stale.** The ledger header listed the entries that had checks and was wrong within
  weeks; a board header that said when it was updated went unchanged through eleven increments. Fix: state
  the fact where it lives, or not at all.
- **A rule restated in many places.** The inventory found LargeWorlds stating its whose-branch rule in several
  files and carrying a long instruction file with duplicated standards, which its own audit had already split
  once. A rule restated for convenience is a drift scheduled.
- **A promise of a future document that landed and was never updated.** The entry file kept saying the
  standards "arrive in a later pass" for eleven days after they had.
- **Status vocabulary without a closed set.** Free-form status words on specs and plans (LargeWorlds) mean the
  docs check cannot say which are current. A closed set, enforced, is the cure.
- **A concept used heavily and never defined.** The framework's own words (definition of done, significant
  increment, autonomy protocol) were missing from the glossary until the glossary rule was applied to the
  framework itself.
- **Automation that proves the wrong thing.** A hash pinned to one machine's float arithmetic; a check that
  swallowed its own failure through a pipe; a manifest nobody registered. Each is a ledger entry, and
  each is evidence that a check must first be shown capable of failing.

## Three repositories, one framework

H is HogShade, L is LargeWorlds, S is SpriteJammer. A concept the graph marks with all three letters is
the stable core; a concept with one letter is either an experiment worth lifting or a need local to that
project.

| Concept | H | L | S | Note |
| --- | --- | --- | --- | --- |
| Entry file with tool pointers; handoff; board; glossary; ledger; standards; ADRs | yes | yes | yes | The core |
| Journal, one file per session | yes | no | yes | L keeps its narrative in the handoff and git, and pays for it |
| One journal file per day, session numbers restarting | yes | n/a | not checked | A convention in H; the docs check requires a journal file for the handoff's day |
| Terms-introduced section and its check | yes | no | no | Mechanised 2026-10-08 (HogShade ledger entry 20) |
| Controls and amendments after acceptance | yes | no | no | Came from the comparison framework |
| Branch-ownership tool | no | yes | no | Needed because many sessions share one owner identity (L's `tools/whose_branch.py`) |
| Pending-review queue, lane ids, deferred bugs as issues | no | no | yes | Needed by many parallel lanes |
| CI parity oracle (local runner and CI share one stage list) | no | no | yes | |
| Weekly devblog with a privacy boundary | no | no | yes | Public-facing writing is a separate pipeline |
| Mock pass (UX canvas reviewed before the widget) | no | yes | no | A UI project's need |
| Smoke gate (launch and drive every app) | no | yes | no | |
| Hygiene check for retired identifiers | yes | no | no | Specific to a project with a history to keep out |
| Generated documents with `--check` | yes | yes | no | |

## What a template would carry

A template repository starts with the core row of the table, parametrised, and leaves the experiments as
opt-in modules. What is project-specific and must be a parameter, not text:

- the owner identity rule, the default branch and the repository slug;
- the hygiene identifiers (empty by default; the check exists and lists nothing);
- the core contract: the one stack the standards describe (language, test runner, linter), swapped as a unit;
- the tool pointers present (one per agent the project uses);
- the skills the project needs, with the review skills generic and the host-specific ones removed.

What it must not carry is the content: no ADRs, no ledger entries, no glossary rows that belong to a project.
The framework's own entries are the exception, because the framework's failures are as true for a new
repository as for these three. The template design is the next step and lives in its own document.

## Open questions

- **Is the template the upstream of each repository's process documents?** If it is, the shared
  standards (the definition of done, the ledger's framework entries, the docs check) are checked against it
  and a repository's drift from the template is a finding; if it is a copy, the three repositories diverge
  again within a month. Recommended: upstream, with a sync check. This is the owner's decision.
- **Which of the one-letter concepts graduate into the core?** The pending-review queue, the parity oracle and
  the branch-ownership tool each solve a problem that every parallel-session project has; they were built
  where the problem showed first.
- **How do two repositories keep one ledger?** Framework entries belong to the template, project entries to
  the project, and today they share a file.
