# ADR-001: WGSL is the core's source language, translated by naga

**Status:** Accepted (owner, 2026-09-20; proven by the spike the same day)
**Date:** 2026-09-20, written down 2026-09-27
**Deciders:** the owner

## Context

One shading core has to land as a Maya `dx11Shader` effect (HLSL, fxc, shader model 5), modern HLSL
(dxc, shader model 6), GLSL for Maya's `ogsfx`, and WGSL for the owner's wgpu engine. Slang was the
first plan: write once, emit everything. The engine, SpriteJammer, is the primary consumer and is
debugged in WGSL; a Slang core would put machine-written WGSL in its hottest shaders.

## Decision

The core is written in WGSL under `core/`. `naga-cli` validates it and translates it to HLSL and
GLSL; `tools/build_shaders.py` stitches the modules, runs naga, and writes the artifacts under
`hosts/*/generated/`, which are committed and checked in CI. Slang stays the documented fallback:
if naga's HLSL ever cannot be made to compile inside Maya's effect shell, the core moves to Slang
and WGSL becomes an emitted target, and nothing else in the design changes.

The spike (`Spikes/naga-fx/`, 2026-09-20) settled the risk: a GGX lobe in WGSL, translated by naga,
wrapped in a v2-style `.fx` shell, compiled by fxc and rendered in Maya 2026.

## Consequences

- SpriteJammer and `hog_rendering` consume the core with no translation.
- WGSL has no `import` and no preprocessor, so modules are files, `core/manifest.toml` is the import
  graph, and interfaces are conventions (ADR-002, ADR-003).
- A Rust toolchain (`cargo install naga-cli`) and the Windows SDK's fxc and dxc are build
  dependencies; CI installs and caches them (`Docs/knowledge/toolchain.md`).
- naga's naming rules leak into hosts: a name ending in a digit gains `_`.
- OSL is not a transpile target; it is a hand-maintained host checked against the core's vectors.

## Revisit if

naga's HLSL stops compiling under fxc for a construct the core needs and no if-chain or restructure
avoids it; or the primary consumer stops being a wgpu engine.
