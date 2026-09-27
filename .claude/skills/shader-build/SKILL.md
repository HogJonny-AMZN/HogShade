---
name: shader-build
description: Change the WGSL core or a host shader, rebuild the generated artifacts, and verify on every compiler and both GPU backends. Use for any edit under core/ or hosts/.
---

# shader-build

## The loop

```bash
export PATH="$HOME/.cargo/bin:$PATH" MSYS_NO_PATHCONV=1     # git-bash on Windows
uv run tools/build_shaders.py                                 # stitch, naga validate, emit, fxc, dxc
uv run pytest -q tests -o addopts="" -p no:cacheprovider      # NumPy twins, GPU harness (Vulkan)
WGPU_BACKEND_TYPE=D3D12 uv run pytest -q tests/core tests/host -o addopts="" -p no:cacheprovider
uv run tools/build_shaders.py --check --require-compilers     # what CI runs: artifacts current
```

Commit the regenerated files under `hosts/*/generated/` and `hosts/generated_manifest.json` with
the change; CI fails on a stale artifact.

## Rules of the core

- Textures, samplers and uniforms are function parameters, never `@group/@binding` globals.
- Every declared name carries its module prefix (`core/manifest.toml`); public interface structs
  are the listed exemptions. A new module is added to the manifest in dependency order.
- Every core function gets a NumPy twin in `hogshade/reference/` and a GPU test in `tests/core/`
  through `gpu_harness.kernel`; tolerances are stated with the reason (float32 cancellation, fp16
  attachments).
- Constants live in `core/constants.wgsl` and are mirrored in `hogshade/core_constants.py`; the
  test fails on a missing mirror.

## Compiler pitfalls, all real

- FXC (Maya dx11Shader, wgpu's D3D12 backend) rejects: a `switch` on a value read from a uint
  texture when textures are also passed into functions ("no storage type for block output"), and
  some multi-return switch cases ("not all control paths return a value"). Use if-chains and a
  single return. Always run the D3D12 backend before pushing a shader change.
- naga: names ending in a digit get `_`; `meta` is reserved; GLSL output needs `.frag`.
- `queue.write_texture` needs no 256-byte row alignment; buffer copies and readback do.
- fxc under git-bash needs `MSYS_NO_PATHCONV=1` or its `/T` flags become paths.

## Before claiming done

Run the four commands above and quote the counts. A plan task is ticked only when its
verification ran; record the run in `Docs/verification/<host>/` when the plan asks for it.
