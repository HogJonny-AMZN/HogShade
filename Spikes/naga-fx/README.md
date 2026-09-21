# Spike: naga's HLSL inside a Maya dx11Shader effect

Phase 2, plan PR A. Question: can a WGSL core module, translated by naga, be wrapped in an `.fx`
effect that fxc compiles and Maya 2026 draws, with a texture, a sampler and a light bound through
Maya-annotated effect parameters? **Verdict, 2026-09-20: yes. WGSL stays the source language.**

| File | What |
| --- | --- |
| `ggx.wgsl` | The core side: GGX D, height-correlated Smith visibility, Schlick Fresnel, and `spike_shade`, which takes the texture, sampler and light as parameters |
| `ggx_sm50.hlsl` | `naga --shader-model 50 ggx.wgsl ggx_sm50.hlsl`, committed as evidence. 67 lines, no file-scope bindings |
| `ggx.fx` | The Maya shell: transforms, annotated texture and sliders, one light slot bound to `Light 0`, vertex and pixel shaders, a technique; the pixel shader calls `spike_shade` |
| `fxc.log` | `fxc /T fx_5_0 ggx.fx`: exit 0, only the usual effects-deprecated warning |
| `checker.png` | The texture the check binds |
| `maya_spike_check.py`, `.mel` | The Maya 2026 check; log and two frames under `verification/`. Binds the scene light to the slot explicitly (`dx11Shader -connectLight "Light 0" <light>`), reports Maya's own `-lightConnectionStatus`, captures uncompressed BMP frames and counts the sphere pixels that change when the light rotates (95 percent in the committed run); the PNGs are converted from those BMPs for the record |

## What the spike found

1. **With `@group/@binding` globals, naga 30 emits samplers through a sampler heap**
   (`SamplerState nagaSamplerHeap[2048] : register(s0, space0)` and an index buffer in `space255`).
   Register spaces are shader-model 5.1 syntax; an `fx_5_0` effect cannot declare or bind them, and
   there is no CLI switch to turn the heap off. This is the failure mode the spec named.
2. **The fix is the spec's own rule.** With no bindings in the core and the texture, sampler and
   uniform passed as function parameters, naga emits `Texture2D<float4>`, `SamplerState` and a
   plain struct as parameters and nothing at file scope. The shell declares every resource with its
   annotations and passes it in. This is the binding model for the whole core.
3. **Maya's light binding works unchanged.** `float3 light0Dir : DIRECTION < string Object = "Light 0"; >`
   in the shell is auto-bound to a scene directional light; rotating the light changed the frame.
4. **Maya's Python is 3.11.** Nested same-quote f-strings are a 3.12 feature; a script that uses
   them fails to parse inside Maya, silently from the outside, and the session then sits open until
   its timeout. Parse-check check scripts with `mayapy` before launching the GUI.
5. **naga's HLSL is readable.** Temporaries are named `_eN` and locals get `_1` suffixes on
   collision, which is fine for a generated file and irrelevant to a shell that only calls the
   API-level functions.

## Costs accepted

- A Rust toolchain for naga-cli (`Docs/verification/toolchain.md`). A 54-second release build.
- Every core function that needs a resource takes it as a parameter. That is a design constraint,
  not a limitation: it is what keeps the core host-agnostic across Maya, wgpu, Blender's `gpu`
  module and a future GLSL host.
