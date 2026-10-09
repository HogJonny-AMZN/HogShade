# Template increment 1 plan

**Status:** Proposed. Spec: [../specs/template-increment-1.md](../specs/template-increment-1.md). Nothing is ticked: the
build has not started. Test-first throughout; each group of tasks is its own pull request in the template repository
(none over eight logged decisions), and each is a significant increment, so `/local-review diff` runs before the merge.
Until the repository exists, the extraction reads the three repositories under `D:\Depot\` and the work is staged in
a scratch checkout, not in HogShade.

## Tasks

- [ ] 0. **Verify the harness facts against vendor documentation** (Claude Code memory and skills, Gemini CLI context files
      and skills, Copilot custom instructions and code review). Verify: the compatibility matrix lists, per harness, what
      it reads, the source URL and the date; the design's unconfirmed question (does Copilot code review read
      `AGENTS.md`?) is answered or marked open with the experiment that settles it.
- [ ] 1. **The extraction diffs.** Read in full and record in the spec's *What the build found*: the three `check_docs.py`
      (what each added), the three definitions of done, the three Python standards, the workflow files, the PR templates,
      the three ledgers (classify each entry framework or project, as a table), the SpriteJammer hooks, Makefile,
      `scripts/check.py`, `tooling.md`, `ci.md`, `documentation.md`. Verify: every "confirm in the extraction" row of the
      design's contested-file table has a recorded pick.
- [ ] 2. **Create the repository** (owner's go at this moment): private, `ai-first-template`, the owner's account, the
      stated "all rights reserved" notice, `payload/` and the root skeleton, the template's own board and handoff.
      Verify: the repository exists and is private (`gh repo view`).
- [ ] 3. **Schemas and loader** (`framework.toml`, `project.json`, the answers file): validation that names the field.
      Verify: a test per refusal; a valid file round-trips.
- [ ] 4. **`init new`**: `--answers`, `--dry-run`, `--target`, idempotence, the run record, exit codes. Verify: a second run
      changes no tracked or generated file (the git-ignored run record under `logs/` is excluded); `--dry-run` writes no file
      and prints the plan; each refused input exits 1 naming the field.
- [ ] 5. **The seed**: entry file and docs map, glossary, board, handoff ("Day 0"), journal, ADR-001, the framework ledger
      and an empty project ledger, the standards in reconciled form, the PR template, the skills. Verify: `check_docs.py`
      is clean on a generated repository.
- [ ] 6. **`check_docs.py`, unified**, with the closed status set (`Proposed|Accepted|Living|Superseded|Abandoned`, in the first 12 lines, for specs and plans
      too) and the handoff limit (150 lines, `handoff_max_lines`), as the spec's *The two new docs rules* define them; port
      the tests from HogShade and add one per new rule, including a value just over the limit and a free-form status. Verify: acceptance 4 for each rule.
- [ ] 7. **`check_hygiene.py`, `check_log_format.py` and the graph generator** with their tests (the graph and its page
      are the base graph as it stands). Verify: acceptance 4; the generated page is current.
- [ ] 8. **The gate**: `tools/check.py`, the `Makefile`, the hooks (pre-commit, `commit-msg`), the CI workflow on Windows and
      Linux. Verify: acceptance 5 and 8.
- [ ] 9. **The harness layer**: `sync_adapters.py` and `--check`, the adapters, the skills mirrors, the neutral-wording lint,
      the probes; enable a harness only after its probe passed. Verify: acceptance 6 and 7.
- [ ] 10. **Self-hosting**: generate the root with `init new --target .`, add the regeneration test. Verify: acceptance 2.
- [ ] 11. **Day 0 on both systems**: the CI job that builds a repository into a temporary directory and runs `make check`.
      Verify: acceptance 1 and 3, green on Windows and Linux.
- [ ] 12. **Close out**: the spec's *What the build found*, the template's handoff and journal, HogShade's board row,
      handoff and journal, the glossary. Verify: `check_docs.py` clean in both repositories.

## Terms introduced

None beyond the spec's: **Compatibility matrix**, already in [../../glossary.md](../../glossary.md).
