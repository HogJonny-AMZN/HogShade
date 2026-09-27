# WGSL core standards

**Status:** Accepted (the standards pass, 2026-09-27; the rules the spec and the spike set, collected)
**Last updated:** 2026-09-27
**Read with:** [python.md](python.md), the ADRs in [../decisions/](../decisions/README.md), [../specs/phase-2-restructure.md](../superpowers/specs/phase-2-restructure.md) "Module conventions" and "Interfaces"

The core under `core/` is the one source of the shading maths. Everything under `hosts/*/generated/`
and `hosts/hlsl/hogshade_core.hlsl` is built from it by `tools/build_shaders.py` and is never
edited by hand; CI fails when a regeneration differs from what is committed.

## The contract, in one table

| Rule | Why | Enforced by |
| --- | --- | --- |
| Every function, struct and constant in a module carries the module's prefix from `core/manifest.toml`; only the names under `[names].exempt` (the public interface structs) are bare | WGSL has no namespaces; the manifest is the import graph and the prefix is the namespace | The build's collision check fails on an unprefixed or duplicated name |
| No bindings and no entry points in `core/`; textures, samplers and uniforms arrive as function parameters | This is what makes one core portable to a Maya effect, a wgpu pass and a GLSL shell ([ADR-002](../decisions/ADR-002-resources-as-parameters-and-the-prefix-rule.md)) | naga validation of the stitched core; the spike that decided it is `Spikes/naga-fx/` |
| Every core function that computes shading maths on numbers has a NumPy twin in `hogshade/reference/` and a GPU test in `tests/core/` that compares them. Excluded, and exercised elsewhere: functions that sample textures (`environment_specular`, `environment_irradiance_cube`, `environment_brdf_lut`, `environment_sample`), struct builders (`environment_default`, the `<model>_inputs` functions, checked through the tests that use them), and the debug selectors, which return named intermediates the tests of those intermediates already cover | The maths is proven numerically before any host renders it ([ADR-004](../decisions/ADR-004-numpy-twin-and-gpu-test.md)) | Review; the `local-review` skill's `core` mode lists a missing twin as a finding |
| Constants every host must agree on live in `core/constants.wgsl` and are mirrored in `hogshade/core_constants.py` | A constant that drifts between the shader and the reference is a silent wrong answer | `tests/core/test_constants.py` |
| Dispatch on the model ID is an if-chain, never a `switch` on a value derived from a uint texture while texture parameters are in scope; a `switch` on a uniform (the debug mode) and early returns are fine | FXC rejects that one shape (`core/models.wgsl`'s header has the rationale; [ADR-003](../decisions/ADR-003-the-model-interface.md)); `lambert_debug` and the v2 debug views switch on the mode and compile | `tests/compile/test_build.py` runs fxc on the Maya shell |
| A model implements `<model>_inputs`, `<model>_env_lookup`, `<model>_evaluate_light`, `<model>_evaluate_env`, `<model>_debug`, and is registered in `core/models.wgsl` and `core/manifest.toml` | Models are peers chosen at runtime; the interface is the only thing a host knows | The dispatcher; `tests/core/test_constants.py` asserts the model IDs |
| A name ending in a digit gets `_` appended by naga (`FixedSlots16_`, `sh9_`); hosts written against HLSL or GLSL use the translated spelling | naga's rule; a host that spells the WGSL name does not compile | fxc and dxc in `tests/compile/` |
| A legacy port keeps its quirks verbatim and lists every deviation in the module header | The legacy models are the record; a quirk removed silently is a comparison that can never be made | Review; the design doc's port sections |

## Header comment

Every module opens with a comment block, the shader's equivalent of the Python header:

```wgsl
// HogShade core: the BRDF toolbox every model draws from. Pure functions of angles and parameters;
// no textures, no lights. NumPy twins in hogshade/reference/brdf.py; the GPU harness compares them.
//
// Conventions: n, v, l, h are unit vectors; n_dot_x are clamped by the caller unless stated;
// roughness is perceptual and alpha = roughness squared.
```

What it must say: what the module provides, what it requires, where its twin lives, and the
conventions a caller must honour (vector spaces, clamping, units). A model's header also carries
the kept-quirks and deviations lists.

## Style

- `let` over `var`; a `var` is a deliberate mutation.
- Named intermediates over clever one-liners: this is a research shader and the debug views read
  them.
- Comment the why for every precision workaround, compiler quirk and kept legacy behaviour; the
  what is readable.
- Struct fields are named identically to the Python side (`hogshade/core_layout.py` mirrors the
  `LightSource` ABI and a test checks the offsets).
- No magic numbers for model IDs, debug modes or layout choices: `HOGSHADE_*` constants, mirrored.

## Building and checking

```text
uv run tools/build_shaders.py                          # stitch, validate, translate, write hosts/*/generated/
uv run tools/build_shaders.py --check --require-compilers   # what CI runs: artifacts current, fxc and dxc pass
uv run pytest tests/core tests/compile                 # the twins on the GPU, the hosts on every compiler
```

In git-bash on Windows, `export MSYS_NO_PATHCONV=1` before fxc, dxc or naga, and `$HOME/.cargo/bin`
on `PATH` for naga (`../knowledge/toolchain.md`).

## Hosts

A host is a shell: it declares the resources with its own annotations, binds parameters and
textures, and calls the core's functions. It adds pass entry points and nothing else of the
shading maths. A host's own WGSL (`hosts/wgpu/*.wgsl`) follows the same header and naming rules
with the `host_` prefix. The Maya shell's parameter names follow the legacy v2 names so a scene
authored against v2 rebinds without renaming.

## Performance note, not yet a rule

The Maya shell compiled in 14 s under fxc with one legacy model and 24 s with two. Every model
added grows the uber shader. Shader specialisation through `override` constants is the planned
answer ([ADR-006](../decisions/ADR-006-shader-specialisation-by-override-constants.md), Proposed);
until it lands, the compile time is a number the phase close records.
