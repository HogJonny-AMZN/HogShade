# CLAUDE.md

@AGENTS.md

Claude-specific notes only; everything else is in the tool-neutral entry above.

- Read `Docs/handoffs/CURRENT.md`, then `Docs/plan/BOARD.md` gates first, before any work; a
  mentioned feature goes to the board's Icebox with a cost, and the PR body's *Board* line names the
  row it touches.
- Commit with `-s` (DCO). Commit and PR text carry the owner's identity only: no AI co-author
  trailer, no generated-with footer.
- In git-bash on Windows: `export MSYS_NO_PATHCONV=1` before fxc, dxc or naga; with it set, write
  commit-message files under a real Windows path, not `/tmp`. `$HOME/.cargo/bin` on PATH for naga.
- `gh pr create` takes `-R HogJonny-AMZN/HogShade --base master` (the default branch is `master`).
  The PR body follows `.github/pull_request_template.md`; the *Decisions* table is the autonomy
  protocol's record.
- `/local-review diff` before asking for a merge on a significant increment
  (`Docs/standards/definition-of-done.md` says what counts).
- The `bats` MCP server in `.mcp.json` is the orchestrator; `tools/bats/AGENTS.md` says what it may
  be used for.
