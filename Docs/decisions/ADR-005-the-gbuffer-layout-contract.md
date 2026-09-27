# ADR-005: the G-buffer encode and decode take the layout as a parameter; ADR-002 of SpriteJammer is the first

**Status:** Accepted (PR C, 2026-09-21)
**Date:** 2026-09-21, written down 2026-09-27
**Deciders:** the owner

## Context

The deferred consumer, SpriteJammer, fixed its G-buffer in its own ADR-002: four colour attachments
plus depth, octahedral normals, a shading-model ID byte in GB2. The core's lighting half must run
from what that buffer stores, and a second engine may store something else.

## Decision

`core/gbuffer.wgsl` encodes `SurfaceInputs` into targets and reconstructs `ShadingInputs` from
them against a layout struct (`GBufferLayoutAdr002` is the first); the layout is a parameter, not a
constant. `SurfaceInputs` is the stored payload and `ShadingInputs` wraps it, so forward and deferred
share one definition of the stored fields. Forward-versus-deferred parity is tested within the
attachments' quantisation (8-bit sRGB albedo, 8-bit AO, fp16 octahedral normal).

## Consequences

- What the buffer does not carry (cavity, opacity after MASK, the tangent frame, model
  parameters) is reconstructed or zeroed, and those features are forward-only until a layout adds
  them. The pros-and-cons table in the README says so.
- A second layout is a second struct and a second set of encode and decode functions, not a fork of
  the lighting half.
- The engine decides its layout in bandwidth; the core takes it.

## Revisit if

SpriteJammer claims a spare channel (specular weight or IOR, a tangent) and the layout struct grows;
the encode and decode follow, the lighting half does not change.
