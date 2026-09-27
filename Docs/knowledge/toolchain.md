# Toolchain versions (phase 2, task 1)

**Status:** Living. Recorded versions and the toolchain lessons; amended when a tool is upgraded or a lesson lands.

Recorded 2026-09-20 on BIGHOG-4090RTX, Windows 11.

| Tool | Version | Installed by |
| --- | --- | --- |
| rustup / cargo | cargo 1.98.1 (797e8a9bc 2026-08-05) | winget install Rustlang.Rustup |
| rustc | rustc 1.98.1 (48a229cea 2026-09-01) | rustup default stable |
| naga-cli | 30.0.1 | cargo install naga-cli (54 s release build) |
| fxc | Windows 10 SDK 10.0.26100.0 | already present |
| dxc | Windows 10 SDK 10.0.26100.0 | already present |
| Maya | 2026, dx11Shader.mll | already present |

Note for git-bash: the cargo bin directory is `$HOME/.cargo/bin`; `$USERPROFILE` is a Windows path and does not work on PATH.

## Lessons that cost time (moved from the decision log, 2026-09-27)

- naga-cli 30.0.1 and Rust 1.98.1 via winget; `$HOME/.cargo/bin` on PATH in git-bash (not
  `$USERPROFILE`). `export MSYS_NO_PATHCONV=1` before fxc, dxc or naga, or git-bash rewrites `/T`
  and `/E` into paths. With that exported, native git cannot read `/tmp/...` message files: write
  commit messages to a real Windows path.
- `gh pr create` must pass `-R HogJonny-AMZN/HogShade` (a habit from the fork days; harmless now).
- naga: names ending in digits get a trailing underscore (`FixedSlots16_`); `meta` is reserved;
  GLSL output needs a `.frag` extension; struct-field parsing in the build must tolerate
  `array<LightSource, 16>`.
- FXC (Maya's dx11Shader and wgpu's D3D12 backend): rejects a `switch` on a value read from a uint
  texture in a shader that also passes textures into functions ("no storage type for block
  output"); rejects some multi-return switch cases ("not all control paths return a value").
  Single returns and if-chains compile. Check every new host shader on the D3D12 backend
  (`WGPU_BACKEND_TYPE=D3D12`) before pushing.
- `queue.write_texture` needs no 256-byte row alignment; buffer-to-texture copies and readback do.
- Recreate `.venv` after moving the clone folder: uv's script launchers embed the absolute path.
