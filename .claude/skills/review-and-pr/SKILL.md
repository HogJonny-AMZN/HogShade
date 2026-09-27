---
name: review-and-pr
description: Open a HogShade pull request the way this repo expects, and assess a Copilot review on one (fix valid findings, refute wrong ones with evidence, reply on every thread). Use when work is ready to push or when the owner says a review is waiting.
---

# review-and-pr

## Before the PR

1. Hygiene grep, nothing new may match outside `legacy/` and the roadmap's own clearance track:
   `git grep -n -i -E "bluepoint|sony|bp_py|bp_color" -- ':!legacy'`.
2. Lint and tests: `uv run ruff format hogshade tests tools`, `uv run ruff check hogshade tests
   tools`, the full suite, and for shader changes the `shader-build` skill's four commands.
3. Docs in the same PR: the plan task ticked with a dated verification note, the spec amended if
   an interface changed, `Docs/README.md` status rows, the decision log for any decision made in
   conversation, `Docs/handoffs/CURRENT.md` if work is interrupted or the state changed.
4. `tools/check_docs.py` clean; the journal appended (`Docs/journal/README.md`); for a significant
   increment, `/local-review diff` with its table pasted into the PR's *Review* section.
5. Commit with `-s`; write the message file in its own command (a chained assertion that aborts
   before writing it leaves the commit reading a missing file), under a real Windows path when
   `MSYS_NO_PATHCONV=1` is set; `gh pr create -R HogJonny-AMZN/HogShade --base master` (the default
   branch is `master`, not `main`). The body follows `.github/pull_request_template.md`: every
   two-way-door decision in *Decisions* (at most eight), what was verified, what is still open; an
   open gate is stated, never implied.

## Assessing a Copilot review

```bash
gh api repos/HogJonny-AMZN/HogShade/pulls/<n>/comments --jq '.[] | "\(.id) \(.path):\(.line)\n\(.body)\n"'
gh pr checks <n> -R HogJonny-AMZN/HogShade
```

For each finding: decide valid or not from the code, not from the comment's confidence. Valid:
fix it, and test the fix. Wrong: refute with evidence (a test, a spec line, a measured number),
never with an assertion. Then reply on the thread:

```bash
gh api -X POST repos/HogJonny-AMZN/HogShade/pulls/<n>/comments/<id>/replies -f body="..."
```

A reply states what was done or why not; a claim in a reply is made after the evidence exists
(a claimed test run that had not finished had to be corrected once). Copilot has been wrong about
octahedral encoding, `write_texture` alignment and the owner's own project name being an
employer; it has been right about most things else. Check CI on the PR after pushing; a CI
failure Copilot did not mention is still yours.

The owner merges and deletes the branch; never merge.
