# ADR-006: shader specialisation by `override` constants, the uber core as the record

**Status:** Proposed (owner direction, 2026-09-26; the evidence is the FXC canary)
**Date:** 2026-09-27
**Deciders:** the owner

## Context

The core is an uber shader: every model, every debug mode and every surface feature is in the one
stitched file, selected at runtime. The owner asked about long-term combinatorial explosion on
2026-09-26. The canary: the Maya shell compiled in 14 s under fxc with one legacy model and 24 s
with two. Phase 3 adds OpenPBR and phase 4 the surface-authoring features.

## Decision, proposed

The uber core stays the record: one source, every path present, selected at runtime, so
comparison views and debug modes always exist. Specialisation is a build-time layer over it: the
static axes (which models are compiled in, which surface features, deferred or forward) are WGSL
`override` constants that naga folds when a host sets them, so a shipped variant compiles only the
paths it uses. The build gains a variant description per host and emits a specialised artifact
beside the full one; the full artifact remains the one the tests run and the research host loads.

## Consequences

- No runtime branch is removed from the record; a variant is a subset, never a fork.
- `override` constants are a WGSL feature naga supports for WGSL and translates as constants for
  HLSL and GLSL; the spike for this ADR is to confirm fxc folds the dead branches and the compile
  time drops.
- Each host's variant description is one more generated input to keep current.

## Revisit if

The spike shows fxc does not eliminate the dead paths, in which case the answer is a preprocessing
step in `build_shaders.py` that strips modules per variant, with the same subset-never-fork rule.
