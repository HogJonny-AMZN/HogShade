# Toolchain versions (phase 2, task 1)

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
