# Spec: the AI-first framework description and its graph (steps 1 and 2)

**Status:** Proposed. Written after the build, on 2026-10-09, because the build skipped the chain (ledger entry 22);
the owner accepts or rejects it with PR #79. The conversation it records is the owner's request of 2026-10-08 ("I want
to do a dive on this repo, the context / instructions, glossary, journalling, process, etc. and describe the framework
... and build a graph, agnostic to HogShade") and the board row it became.

Board: [../../plan/BOARD.md](../../plan/BOARD.md) (the AI-first framework row). Plan:
[../plans/ai-first-framework-graph.md](../plans/ai-first-framework-graph.md). The template that step 3 designs is not
part of this spec.

## Deliverable

1. **A description**, [../../knowledge/ai-first-framework.md](../../knowledge/ai-first-framework.md): the thesis, the
   failures it prevents, the layers, one session, the principles (each a line and a link to the file that states it),
   the mechanisation ladder, how the framework itself fails, a comparison of the three repositories, what a template
   must parametrise, and the open questions.
2. **The graph as data**, [../../knowledge/ai-first-framework.graph.json](../../knowledge/ai-first-framework.graph.json):
   project-agnostic concepts in layers, joined by typed edges from a closed set of relations; `seen` says in which
   repository each concept exists today.
3. **A generator and its check**, `tools/render_framework_graph.py`: validates the data (shape, ids, closed sets,
   endpoints, orphans, relations used, Mermaid-safe ids) and writes a Mermaid page,
   [../../knowledge/ai-first-framework-graph.md](../../knowledge/ai-first-framework-graph.md); `--check` fails on a
   malformed graph or a stale page and is a CI step.

## Acceptance

- A malformed data file is a reported problem, never a traceback; each rule has a test on a mutated copy.
- `--check` agrees on LF and CRLF working copies.
- The graph names no project; a claim about HogShade is checked against its files; claims about the other two
  repositories are labelled as coming from the inventories.
- The description restates no rule that has a home elsewhere.

## Out of scope

The template repository (step 3, design first), an interactive viewer, a check that the description's repository table
agrees with the graph's `seen` letters.

## Terms introduced

**AI-first framework**, **Framework graph** and **Mechanise**: all in [../../glossary.md](../../glossary.md).
