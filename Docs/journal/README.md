# Journal

**Status:** Living
**Cadence:** continuous, see [Cadence](#cadence)

Append-only narrative: *what happened, when, and why.* Ported from SpriteJammer's journal on
2026-09-27 at the owner's request, with its reasoning, not only its folder.

HogShade's stated job is to modernise a shader whose original author is the owner, across hosts
that disagree with each other. **The record of what was believed, checked against the record, and
corrected is itself a result.** The v1 port proved it on its first day: the roadmap said v1 shipped
three BRDFs, the source said one, and only reading the effect's includes settled it. That sequence
survives only if it is written down as it happens; git has the *what*, the journal has the *why*.

Distinct from its neighbours, and the distinction is worth keeping sharp:

| Directory | Question | Mutability |
| --- | --- | --- |
| **`journal/`** | *What happened, when, and why?* | **Append-only.** Written as it happens, never revised |
| [`../handoffs/`](../handoffs/CURRENT.md) | *What does someone need to be productive right now?* | One living document, rewritten continuously |
| [`../design/2026-09-26-decision-log-and-working-knowledge.md`](../design/2026-09-26-decision-log-and-working-knowledge.md) | *What was decided in conversation, and where is it formalised?* | Append-only; an entry says where it was formalised |
| [`../research/`](../research/) | *What did we try, and what did we measure?* | Append-only, including failures |
| [`../knowledge/`](../knowledge/) | *What does an agent need to know about one topic?* | Living topic files, rewritten as the topic settles |

The decision log came first here and stays: it is the index of decisions. The journal is the
narrative that produced them. A decision with no journal entry behind it is a conclusion with no
reasoning; a journal entry with no decision-log row is reasoning that will be lost when the file
scrolls. Link both ways with the trailing arrow line below.

---

## Cadence

**One file per session, appended continuously**, not one file per topic written afterwards.

Append an entry:

- **Every meaningful exchange** with the owner: a question asked, a decision made, a correction given
- **At each step of incremental work**: not every command, but every *step that changed something or
  taught something*
- **Whenever a belief changes**, the highest-value trigger of all
- **Whenever the orchestrator made the difference**, see [Where BATS made the difference](#where-bats-made-the-difference)

Batch at natural breakpoints rather than after literally every message. The test is whether someone
reading it later could reconstruct *why*, not just *what*.

**A new calendar day starts a new file, always** (owner, 2026-10-03). The file is named for the day its
entries happened on and the session number restarts at 01 within the day; a session that crosses
midnight closes its file with `**Continued in:**` and opens the next day's with `**Preceded by:**`.
"When it outgrows one file" was the earlier rule, and it never fired: a judgement nobody makes
mid-session, so the file named for 2026-10-01 held three days and 27 entries before the rule became
mechanical. SpriteJammer's session 04 reached 1,600 lines across three days the same way. A reader
looking for a day opens the file named for it, and the weekly review reads days as a glob.
`tools/check_docs.py` (`journal-day`) fails when the handoff's *Last updated* date has no journal file
of that date or later, so a day that changed the state cannot pass CI without its file. The split is
never retroactive: entries are not moved between files (history is not rewritten); a file whose date
precedes some of its entries says so in its header.

**Two sessions on the same day**: the number is the session, the date is the date. Parallel sessions
take the next free number, share a date, and carry a `**Ran in parallel with:**` link.

**Why session-numbered files**: continuous journaling means the file is created before anyone knows
what the session is about, so it cannot be named after its topic. Descriptive summaries live in the
index below, which is where scanning happens.

**Retrospective entries are the exception, and say so.** The sessions of 2026-09-20 to 2026-09-27
before this journal existed are reconstructed in the decision log, not here; session 01 opens on the
day the journal was started.

---

## Entry format

Keep entries short, three to six lines. The *why* is the payload; the *what* is in git.

```markdown
### Owner: "is v1 three BRDFs or one?"

The effect includes only bigdBRDF.fxh; the Cook-Torrance and game includes never compiled (a
duplicated parameter, a missing comma, an undefined struct). So v1 is one Disney principled BRDF,
and the roadmap's "three" was a belief, not a record.
→ decision log "The v1 port" · plan task 18 · PR #19
```

A trailing `→` line links the durable artifacts the entry produced: a decision-log entry, a plan
task, a knowledge file, a PR. That is what makes the journal navigable rather than merely nostalgic.

### Where BATS made the difference

Owner, 2026-09-27: *"BATS is repeatable, durable, reduces discovery and churn over time. It's a new
paradigm, it's an agentic pipeline, it just makes sense ... so let's make it clear as we go where
it's made the most sense and an impact."*

When a step was possible, faster, or repeatable *because* it ran through the Job_Orchestrator (a
resident worker, a committed profile, a job with a manifest an agent can read), the entry carries a
second trailing line:

```markdown
→ BATS: the v1 Maya check was the same job with one parameter, 37 s on the resident worker; a
  standalone launch had cost a minute of startup, a crash in three, and two idle Mayas.
```

Be as honest the other way: when a step needed no orchestrator (the wgpu viewport runs in-process
under uv), say nothing. The case is built from real instances, and
[`../knowledge/job-orchestrator.md`](../knowledge/job-orchestrator.md) keeps the running summary.

---

## Sessions

Newest first. `tools/check_docs.py` fails when a session file is missing from this table.

| Date | Session | What happened |
| --- | --- | --- |
| 2026-10-10 | [Session 01](2026-10-10-session-01.md) | Template increment 1, tasks 3 and 4 built in the template repository (the schemas and loader, `init new`) and what their reviews found |
| 2026-10-09 | [Session 01](2026-10-09-session-01.md) | Why an iceboxed idea was built (ledger 22), the template repository's requirements and eleven answered design questions, Copilot on #78 and #79 |
| 2026-10-08 | [Session 01](2026-10-08-session-01.md) | Where the repository is against OpenPBR (v0.2.0; C3 blocked on G4 and the calibration capture), and the f-string pass: 71 lazy log calls converted, an AST check in CI |
| 2026-10-05 | [Session 02](2026-10-05-session-02.md) | The `marmoset` worker type added to HogShade's generated BATS profile on the owner's pasted note (pool 1, no environment file, one-shot by default); no bake job yet |
| 2026-10-05 | [Session 01](2026-10-05-session-01.md) | The legacy shader ball inspected in Maya (no clean unwrap; two colour sets in v2.0), the quad sphere built and a per-pixel host probe against the mesh's own triangles that agrees 100 percent, the synthetic set captured in Maya |
| 2026-10-04 | [Session 01](2026-10-04-session-01.md) | The T2 spec and plan (the texture cook): a PNG reader of our own, an encoder seam, the BC encoder spike on the owner's ask, frequency separation specified from the post |
| 2026-10-03 | [Session 01](2026-10-03-session-01.md) | The per-day journal rule made mechanical on the owner's go: a new day starts a new file, `journal-day` in the docs checker, the earlier entries of the day left in place in the 2026-10-01 file |
| 2026-10-01 | [Session 01](2026-10-01-session-01.md) | #33 merged with every S1 review metric at 7 or above; the owner chose S2 over the standards PR. The S2 spec and plan drafted: the Maya shell's material block generated between markers from the schema plus a host map of names, labels and orders, the four UI macros retired, a `--check` in CI, the docs reference generated; no value may change in S2 |
| 2026-09-27 | [Session 02](2026-09-27-session-02.md) | The LargeWorlds session, cross-repo: the owner asked what track A's "private backup repo" box meant, removed that repo, then settled `hog_color`'s history outright (their own toolbox, no approval to seek) and asked for every old reference to go. The retired identifiers became the codename `proto_color` / `proto_py` in LargeWorlds (PR #68), here and in the agent memory; the profile's `package_paths` went with them and the hygiene checker now guards the old spellings only |
| 2026-09-27 | [Session 01](2026-09-27-session-01.md) | The v1 port closed as PR #19 with the record corrected (one BRDF, not three), a test NaN that was a seed collision, the FXC canary at 24 s, and the resident worker's open history log. The owner started the journal, the definition of done, the PR template with its Decisions table, the `local-review` skill and the docs checker, all ported from SpriteJammer with their reasoning; and asked that the case for BATS be made visible wherever it made the difference |

---

## What is worth recording

In rough order of value:

1. **Beliefs that changed, and what changed them**, the single most valuable content here
2. **Decisions the owner reversed or corrected**, and the reasoning on both sides
3. **Reasoning that turned out to be wrong**; keep it, do not tidy it away. A corpus that only
   records correct reasoning teaches nothing about how the correct reasoning was reached
4. **Where the orchestrator made the difference**, or where it was not needed
5. Things deliberately left unresolved, and why
6. Surprises: a measurement or a record that contradicted an assumption

**Not** worth recording: what the architecture *is*. That belongs in the design documents and the
specs, and duplicating it here guarantees the copy drifts.
