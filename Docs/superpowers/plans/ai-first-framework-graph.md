# Plan: the AI-first framework description and its graph

**Status:** Proposed. Written after the build, on 2026-10-09 (ledger entry 22); every task below is ticked because it
was done and verified before the plan existed, which is the failure the entry records. Spec:
[../specs/ai-first-framework-graph.md](../specs/ai-first-framework-graph.md). A significant increment (a new tool):
`/local-review diff` ran and its findings were fixed.

## Tasks

- [x] 1. **Inventories** (read-only, three repositories): entry points, artifacts, concepts, relations, mechanised
      checks, rituals. Verify: each report names its files; the HogShade claims were checked against the repository.
- [x] 2. **The graph data** (`Docs/knowledge/ai-first-framework.graph.json`): nodes in eight layers, ten relations.
      Verify: `render_framework_graph.py --check` clean; no project name in any label or summary (test).
- [x] 3. **The generator** (`tools/render_framework_graph.py`, `tests/test_framework_graph.py`): `problems`, `render`,
      `check`, `write`, `main`. Verify: a test per rule on a mutated copy; 17 malformed shapes reported, never a
      traceback; an unreadable page is a `GraphError`; exit codes 0, 1 and 2.
- [x] 4. **The description** (`Docs/knowledge/ai-first-framework.md`). Verify: `check_docs.py` clean; the review
      (`/local-review diff`) found two claims HogShade does not back and the restated principles; both fixed.
- [x] 5. **Wiring**: a CI step, `AGENTS.md`, the docs map, `tools/README.md`, glossary rows, the definition-of-done
      command list. Verify: CI green on the PR's head commit.
- [x] 6. **Copilot's review** (#79): four comments, all valid; fixed in the follow-up commit (a relation declared and
      never used is now a validator finding, a CRLF control, the command list, and this spec and plan).

## Terms introduced

None beyond the spec's: **AI-first framework**, **Framework graph** and **Mechanise**, already in
[../../glossary.md](../../glossary.md).
