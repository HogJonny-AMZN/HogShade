# ADR-002: resources are function parameters, and every core name carries its module prefix

**Status:** Accepted (the spike, 2026-09-20; the spec's "Module conventions")
**Date:** 2026-09-20, written down 2026-09-27
**Deciders:** the owner

## Context

A shading core that is included by a Maya effect, a wgpu pass and a GLSL shell cannot own its
bindings: each host declares resources with its own annotations and binding model. And WGSL has no
namespaces, so ten modules concatenated into one file share one flat name space.

## Decision

- No bindings and no entry points in `core/`. Textures, samplers and uniforms arrive as function
  parameters, or through the `ShadingInputs` struct. A host declares every resource and passes it in.
  The spike proved that fxc accepts texture and sampler parameters through naga's HLSL.
- Every function, struct and constant a module declares starts with that module's prefix, named in
  `core/manifest.toml`. The public interface structs listed under `[names].exempt` are the one
  exception; the build fails on any other unprefixed name or on a name declared twice.
- Constants every host must agree on live in `core/constants.wgsl` with the `HOGSHADE_` prefix and
  are mirrored in `hogshade/core_constants.py`, with a test that the two agree.

## Consequences

- The core is portable by construction; a new host is a shell, not a shader.
- Function signatures are long (a cube, a LUT, samplers and an IBL struct on `environment_sample`).
  Accepted: the alternative is per-host copies of the maths.
- FXC constrains the shapes that pass through: a `switch` on a value derived from a uint texture
  with texture parameters in scope is rejected, hence ADR-003's if-chain.
- Renaming a module renames its prefix everywhere; the collision checker makes that a build error
  rather than a silent shadow.

## Revisit if

WGSL gains modules or namespaces that naga translates, or a host appears that cannot pass resources
as parameters.
