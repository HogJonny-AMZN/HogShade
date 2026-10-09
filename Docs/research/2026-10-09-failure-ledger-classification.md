# The three failure ledgers, classified for the template

**Status:** Living. Written 2026-10-09 by a read-only pass over HogShade (HS), LargeWorlds (LW) and SpriteJammer (SJ),
which read all 68 entries in full; it is the evidence for plan task 1 of the template's first increment
([spec](../superpowers/specs/template-increment-1.md)). Classes: **F** framework (any AI-assisted repository would
repeat it); **F?** borderline, leaning framework; **M** framework, but only for a repository that measures or benchmarks
(an optional appendix); **PY** a Python or uv lesson (the `python-uv` module's own ledger); **P** this repository's domain
(stays with its project). Entry numbers are as of 2026-10-09, and the classification is the pass's judgement, to be
reviewed in the extraction.

## HogShade

| # | Title | Class |
| --- | --- | --- |
| 1 | A belief carried from a document instead of the record | F |
| 2 | A claim made before the evidence exists | F |
| 3 | A gate whose failure a pipe swallowed | F |
| 4 | A shell heredoc carrying a script it cannot quote | F |
| 5 | A manifest nobody registered | F? |
| 6 | A checker that cannot fail for part of a file | F |
| 7 | A resident session that remembers | P |
| 8 | A test degeneracy blamed on the shader | P |
| 9 | A path parameter that arrives from outside | P |
| 10 | A default assumed from another repository | F |
| 11 | Idea velocity outrunning landing velocity | F |
| 12 | An author's additions that skip the review | F |
| 13 | A module named after the function it exports | PY |
| 14 | A reply that names a commit before the commit exists | F |
| 15 | A handoff whose header is rewritten while its reading order goes stale | F |
| 16 | A resident worker that remembers more than its scene | P |
| 17 | A hash of a file git rewrites | F? |
| 18 | A shell heredoc that rewrites the file it was meant to write | F (repeats 4) |
| 19 | A write that fails after it has already emptied the file | F? |
| 20 | A new word that never reaches the glossary | F |
| 21 | A hash of floats that pins one machine's arithmetic | PY (numeric) |
| 22 | An icebox row built without the chain | F |

## LargeWorlds

| # | Title | Class |
| --- | --- | --- |
| 1 | A number quoted without the commit it was measured on | F |
| 2 | A plan that reads as live because nothing says otherwise | F |
| 3 | A link that resolves on the machine that wrote it | F |
| 4 | A library that reaches the graphics stack at import | P (kernel: a stated boundary with no test is a hope) |
| 5 | A version bump that leaves the old floor asserted | PY |
| 6 | A lockfile that disagrees with `pyproject.toml` | PY |
| 7 | A feature flag that is always False | F? |
| 8 | A merged branch deleted under a stacked pull request | F |
| 9 | A smoke target sized for the workstation, run on the hosted runner | P |
| 10 | Reformatting files the change never touched | F |
| 11 | A shell heredoc carrying a script it cannot quote | F (same class as HS 4) |
| 12 | A timing test that compiles inside the timed loop | M |
| 13 | A fixed reservation assumed to be a ceiling | P |
| 14 | A committed artifact | F |
| 15 | Review findings the review body hides | F? (needs a repository using automated review) |
| 16 | A probe that can only return the boring answer | F |
| 17 | Two sessions writing the same living document | F |
| 18 | A CI step name with a colon | PY (CI YAML) |
| 19 | Test coordinates that never visit the singular point | PY |
| 20 | A board row read as a lock | F |
| 21 | A guard tested for a weaker property than it claims | F |
| 22 | A pull request number mistaken for a work order | F |
| 23 | `python -m pytest` passing where CI's `pytest` fails | PY (kernel: the local environment is not CI's) |
| 24 | One rule written into three files by hand | F |
| 25 | A positive answer that only proves co-location | F |

## SpriteJammer

| # | Title | Class |
| --- | --- | --- |
| 1 | A number too bad to be true | M |
| 2 | A negative result inherits its implementation's assumptions | F |
| 3 | A convention imported from elsewhere, unchecked against our own measurements | F |
| 4 | Citation drift — the right number under a borrowed label | F |
| 5 | A control that cannot distinguish the alternatives | F |
| 6 | Something failed that had no business failing | F |
| 7 | A document contradicting an accepted decision | F |
| 8 | A mentioned feature treated as a work order | F |
| 9 | Work that lands unwired | F? |
| 10 | An unmechanized discipline, under pressure | F |
| 11 | Parallel sessions colliding in shared living documents | F |
| 12 | A tool that mangles its input, retried instead of routed around | F (same class as HS 4) |
| 13 | Capping a proxy, and the cost moving somewhere else | M |
| 14 | A before/after that was not back to back | M |
| 15 | A gate whose failure a pipe swallowed | F (same as HS 3) |
| 16 | CI red for days, and nobody looking | F |
| 17 | Cleanup handed over while a session still lives inside what it removes | F |
| 18 | A helper with `out=` reads its input after writing its output | P |
| 19 | A test that degrades silently when an optional extra is absent | PY |
| 20 | A deferred defect with no home | F |
| 21 | A default set from an estimate, stated with the confidence of a measurement | M |

## The merged framework lessons (the seed of the template's ledger)

Twenty-four distinct lessons; the sources are the entries above, the best wording is named first.

1. **A claim made before the evidence** (HS 2, 14; LW 1; SJ 4, 16): HS 2 is the core; HS 14 is the sub-case where the shell
   chain makes the claim; LW 1's "put the commit beside any number" stays a separate rule.
2. **A gate whose failure a pipe swallowed** (SJ 15, HS 3): SJ 15's wording, without its project references.
3. **A script carried through a shell heredoc, and a write that empties the file** (LW 11, SJ 12, HS 4, 18, 19): LW 11 plus
   SJ 12's "every patch script asserts each anchor matches once"; HS 4 and 18 are one lesson.
4. **Parallel sessions colliding in living documents** (SJ 11, LW 17).
5. **Not your branch or pull request: ownership** (LW 22, 25; SJ 17): a tool can cheaply prove "not yours" and almost never "yours".
6. **A mentioned idea or board row is not a work order or a lock** (SJ 8, LW 20, HS 22, 11).
7. **A deferred defect needs a home, an issue** (SJ 20).
8. **A document or plan reads as live or true when it is not** (LW 2, HS 15, SJ 7, HS 1).
9. **A probe or check that can only return the boring answer** (LW 16, SJ 5, HS 6, LW 7, 21, 25).
10. **A negative result inherits its implementation's assumptions** (SJ 2).
11. **Something failed that had no business failing: chase it** (SJ 6).
12. **The local environment is not CI's** (SJ 16, LW 23, SJ 19, HS 17, 21): the generic form is SJ 16.
13. **An unmechanised discipline lapses under pressure** (SJ 10).
14. **A rule written in many places drifts** (LW 24): the imperative may be restated, the rationale may not.
15. **A new concept needs its glossary row before the code** (HS 20).
16. **An author's additions skip the review** (HS 12).
17. **A default assumed from another repository** (HS 10, SJ 3).
18. **Review findings the review body hides** (LW 15): only for a repository using automated review.
19. **A merged branch deleted under a stacked pull request** (LW 8).
20. **Reformat creep, and a committed artifact** (LW 10, 14): two entries.
21. **Cleanup handed over while a session still lives inside it** (SJ 17).
22. **A link that resolves only on the writing machine** (LW 3, HS 6).
23. **Work that lands unwired** (SJ 9, HS 5): optional.
24. **The measurement appendix** (SJ 1, 13, 14, 21; LW 12): optional.

Format drift to resolve in the seed: HS 18 to 22 use "When you notice ... do ... Because" where the earlier entries use
Trigger, Do, Because; LW 22 to 25 are long with sub-sections; and LW's header lists which entries have checks by a
numbering that no longer matches.
