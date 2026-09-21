# hosts

Everything under `*/generated/` and `hlsl/hogshade_core.hlsl` is written by `tools/build_shaders.py`
from `core/` and must not be edited; CI fails if a regeneration differs from what is committed
(`tools/build_shaders.py --check`). `generated_manifest.json` carries the sha256 of each artifact
and the naga version that produced it.

| Artifact | Language | Target | Consumer |
| --- | --- | --- | --- |
| `wgpu/generated/hogshade_core.wgsl` | WGSL | the core itself, no entry points, no bindings | SpriteJammer, `hog_rendering`; prepend to a pass file |
| `maya_dx11/generated/hogshade_core_sm5.hlsl` | HLSL | shader model 5.0, compiled by fxc | the Maya `.fx` shell includes it |
| `hlsl/hogshade_core.hlsl` | HLSL | shader model 6.0, compiled by dxc | Unreal custom nodes, Unity, DX12 |
| `maya_ogsfx/generated/hogshade_core.frag` | GLSL | core profile, fragment stage | the `.ogsfx` shell, phase 6 |

## What the generated code looks like

- Resources are function parameters (`TextureCube<float4>`, `SamplerState`, `Texture2D<float4>`),
  never file-scope declarations. The host declares every resource with its own annotations and
  passes it in. The spike that decided this is `Spikes/naga-fx/`.
- naga appends an underscore to names that end in a digit: `FixedSlots16` becomes `FixedSlots16_`,
  `GBufferLayoutAdr002` becomes `GBufferLayoutAdr002_`, `environment_irradiance_sh9` becomes
  `environment_irradiance_sh9_`. A host written against the HLSL or GLSL uses the generated names.
- Locals are renamed with `_1`, `_2` suffixes on collision and temporaries are `_eN`. Public
  function signatures keep their WGSL names apart from the digit rule above.
- The validation entry point `hogshade_validate` appears in the HLSL and GLSL artifacts (naga needs
  an entry point to translate; fxc and dxc need one to compile). It declares no bindings and hosts
  never call it. It is absent from the WGSL artifact.
