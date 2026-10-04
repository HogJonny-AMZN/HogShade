# hosts/wgpu

The core's native home. `generated/hogshade_core.wgsl` is the stitched core (`tools/build_shaders.py`);
the files beside it are the pass entry points a wgpu renderer runs over it. WGSL has no include, so a
host stitches: core, then `common.wgsl`, then `material.wgsl` for a pass that runs the material half, then one
pass file. `hogshade.wgpu_host.stitch_pass(name)` does exactly that, and `tests/compile/` validates every
stitched pass with naga.

| File | Pass | Entry points |
| --- | --- | --- |
| `common.wgsl` | shared | the frame uniform (group 0), the E1 environment bindings (group 1), the host's material and geometry builders (the MikkTSpace frame from the vertex tangent, an arbitrary frame when the mesh has no UVs), `host_shade` |
| `material.wgsl` | the two mesh passes | the material bind group (group 2, T3b): four texture slots, the sampler, `host_Textures`; `host_samples(uv)` |
| `lit_mesh.wgsl` | forward | `vs_main`, `fs_main`: material half and lighting half in one fragment |
| `gbuffer_fill.wgsl` | deferred, fill | `vs_main`, `fs_main`: material half into the four ADR-002 targets (the environment layout sits at group 1 unused, so the slots are group 2 here too) |
| `deferred_light.wgsl` | deferred, light | `vs_main` (one triangle), `fs_main`: decode, reconstruct from depth, lighting half; G-buffer and depth on group 2, and a `host_samples` of unbound defaults so the stitched module is whole |

The mesh (`hogshade.wgpu_host.Mesh`) is position, normal, uv and a MikkTSpace tangent with its sign in `w`
(stride 48); `load_obj` reads `vt`, keys corners on `(v, vt, vn)` and generates the tangents
(`hogshade.mikktspace`, the normals as given). `Mesh.tangent_basis` says where they came from.

The material bind group, a legacy v2 document's textures in their runtime form (`Scene.textures`, from
`hogshade.material.runtime.runtime_textures`):

| Binding | Slot | Cooked format | Uncompressed |
| --- | --- | --- | --- |
| 0 | `base_color` (`_BC`) | `bc7-rgba-unorm-srgb` | `rgba8unorm-srgb` |
| 1 | `normal` (`_N`, two channels) | `bc5-rg-unorm` | `rg8unorm` |
| 2 | `orm` (`_ORM`: AO r, roughness g, metalness b) | `bc7-rgba-unorm` | `rgba8unorm` |
| 3 | `cavity` (`_C`) | `bc4-r-unorm` | `r8unorm` |
| 4 | the sampler: linear, mipmap linear, repeat, anisotropy 8 | | |
| 5 | `host_Textures`: `bound` (a bit per parameter: 1 base colour, 2 normal, 4 roughness, 8 metalness, 16 AO, 32 cavity), `sel_a` and `sel_b` (`vec4<u32>`: the slot and channel each scalar reads) | | |

A slot no document binds holds a 1x1 neutral texture; a parameter the host has no slot for (height, emission)
is logged and left to its factor. The bits are per parameter, as the Maya shell's `use<Map>` flags, so roughness
alone reads `_ORM`'s green and leaves metalness and AO at 1.0. `hogshade.wgpu_textures` maps the cook's DXGI
names to these formats and uploads a DDS with every mip; the block formats need `texture-compression-bc`,
which `request_device` asks for when the adapter offers it, and without it a block-compressed set is refused
naming `tools/cook_textures.py cook <set> --no-compress`. The mesh's V is bottom-up (the OBJ convention the
tangents were built from) and the DDS's first row is the top, so `host_samples` flips V, as the Maya shell
negates it. One bind group per distinct plan (slot files, bits, selectors), DDS uploads shared by path.

The frame uniform is laid out in `hogshade.wgpu_host.FRAME_DTYPE`; the Python side and the WGSL
struct must agree field for field, and the renderer asserts the byte size.

`tools/wgpu/viewport.py` renders the shader ball through both paths (a standard document is converted to
legacy v2 first; a textured document renders its set) and writes
`verification/wgpu/shader-ball/<env>/forward.png` and `deferred.png`, then prints the
difference between the two: the deferred picture differs only by the G-buffer's quantisation and by
the specular F0 reconstruction, which is exact only for a dielectric at IOR 1.5 (v2's Cspec0 equals the
reconstructed 0.04); the default document's IOR is the schema's 1.45 (F0 0.0337), so the deferred picture also
carries that reconstruction error since S3.

SpriteJammer and `hog_rendering` vendor `generated/hogshade_core.wgsl` and write their own pass files
on this pattern; the binding groups here are this tool's, not a contract.
