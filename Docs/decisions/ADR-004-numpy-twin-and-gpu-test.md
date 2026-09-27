# ADR-004: every core function has a NumPy twin and a GPU test

**Status:** Accepted (PR B, the GPU harness, 2026-09-21)
**Date:** 2026-09-21, written down 2026-09-27
**Deciders:** the owner

## Context

A shader that is wrong is wrong quietly: a picture that looks plausible with the wrong Fresnel term
is the normal case. Every host renders the same core, so a wrong function is wrong everywhere at
once, and the comparison framework that would catch it in pictures does not exist yet.

## Decision

Every function in `core/` that computes shading maths on numbers has a twin in `hogshade/reference/`
written in plain NumPy from the paper or the legacy source, and a test in `tests/core/` that runs the
WGSL function through the GPU harness on random inputs and compares it to the twin within a stated
tolerance. Three kinds are excluded and exercised elsewhere: functions that sample textures (the
harness binds none; the hosts and their pictures exercise them), struct builders such as
`environment_default` and the `<model>_inputs` functions (checked through every test that uses them),
and the debug selectors, which return intermediates whose own tests already cover them. The twin is written
first when the function is new; for a legacy port, the twin is the legacy source translated
line for line, quirks included, so the port is checked against the record and not against an
improved idea of it. Constants shared by both are mirrored (ADR-002). The harness runs on the
owner's GPU and on CI's DirectX 12 adapter; a test that finds no adapter skips with a reason.

## Consequences

- A port is done when its twin agrees, before any picture exists; the picture is confirmation.
- The reference package is a second implementation to maintain, in Python, and it is the oracle the
  procedural test data and the OSL host will also be checked against.
- The tolerance is part of the contract: `test_brdf_gpu.py` splits the GGX tolerance at alpha 0.1;
  the v1 and v2 tests use 2e-4 relative to each row's magnitude.
- A harness degeneracy (a random view equal to the light) is a test bug, not a shader bug
  (`Docs/standards/failure-modes.md`, entry 8).

## Revisit if

The comparison framework's captures prove more sensitive than the numeric twins for some class of
function, and the twins become the slower, weaker check.
