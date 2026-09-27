# CLAUDE.md

@AGENTS.md

Claude-specific notes only; everything else is in the tool-neutral entry above.

- Commit with `-s` (DCO). Commit and PR text carry the owner's identity only: no AI co-author
  trailer, no generated-with footer.
- In git-bash on Windows: `export MSYS_NO_PATHCONV=1` before fxc, dxc or naga; with it set, write
  commit-message files under a real Windows path, not `/tmp`. `$HOME/.cargo/bin` on PATH for naga.
- `gh pr create` takes `-R HogJonny-AMZN/HogShade`.
- The `bats` MCP server in `.mcp.json` is the orchestrator; `tools/bats/AGENTS.md` says what it may
  be used for.
