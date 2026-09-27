# ADR-003: the model interface, `EnvironmentSamples`, and if-chain dispatch

**Status:** Accepted (PRs B to D, 2026-09-20 to 25; the v1 port extended it 2026-09-27)
**Date:** 2026-09-25, written down 2026-09-27
**Deciders:** the owner

## Context

Shading models are peers chosen at runtime: Lambert, the 2015 and 2017 legacy models, OpenPBR next.
Forward hosts run the material half and the lighting half in one shader; the deferred host runs the
material half in a G-buffer fill and the lighting half in a light pass. The models must never touch
a texture, so the GPU tests need none.

## Decision

Every model implements five functions, spelled the same way by every host:

| Function | Half | Purpose |
| --- | --- | --- |
| `<model>_inputs(material, samples, geometry) -> ShadingInputs` | material | build the surface from parameters, texel values and vertex data |
| `<model>_env_lookup(inputs) -> vec2` | lighting | the `(n.v, roughness)` the environment is sampled at |
| `<model>_evaluate_light(inputs, light, env) -> vec3` | lighting | one punctual light |
| `<model>_evaluate_env(inputs, env) -> vec3` | lighting | the environment term |
| `<model>_debug(inputs, slots, env, mode) -> vec3` | lighting | the named intermediate for a debug mode |

`env` is an `EnvironmentSamples` (irradiance over pi, prefiltered specular, the split-sum LUT
pair, the hemisphere dome), sampled once per fragment by `environment_sample` at the lookup the
model returned. `core/models.wgsl` dispatches on `ShadingInputs.surface.model` with an if-chain,
never a `switch`, because FXC rejects a `switch` on a value derived from a uint texture while
texture parameters are in scope. A `switch` on a uniform (the debug mode) and early returns
compile and the core uses both. `ShadingInputs` carries `specular_weight`, a tangent frame and
two `model_params` vectors for lobes the deferred path cannot store; the deferred reconstruction
builds an arbitrary frame and zeros the parameters.

## Consequences

- A host loops its own lights calling `models_evaluate_light`; the per-light maths is shared, the
  loop is per provider.
- Anisotropy and the extra Disney lobes are forward-only until the G-buffer grows a tangent channel.
- Adding a model is five functions, a manifest entry, a dispatcher line, a constant, a NumPy twin and
  a GPU test (ADR-004).
- The dispatcher is an if-chain that grows with the models; ADR-006 is the answer when it costs.

## Revisit if

The G-buffer layout changes what the deferred half can reconstruct, or a host appears whose compiler
accepts what FXC does not and the if-chain measurably costs.
