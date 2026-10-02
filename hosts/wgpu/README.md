# hosts/wgpu

The core's native home. `generated/hogshade_core.wgsl` is the stitched core (`tools/build_shaders.py`);
the files beside it are the pass entry points a wgpu renderer runs over it. WGSL has no include, so a
host stitches: core, then `common.wgsl`, then one pass file. `hogshade.wgpu_host.stitch_pass(name)`
does exactly that, and `tests/compile/` validates every stitched pass with naga.

| File | Pass | Entry points |
| --- | --- | --- |
| `common.wgsl` | shared | the frame uniform (group 0), the E1 environment bindings (group 1), the host's material and geometry builders, `host_shade` |
| `lit_mesh.wgsl` | forward | `vs_main`, `fs_main`: material half and lighting half in one fragment |
| `gbuffer_fill.wgsl` | deferred, fill | `vs_main`, `fs_main`: material half into the four ADR-002 targets |
| `deferred_light.wgsl` | deferred, light | `vs_main` (one triangle), `fs_main`: decode, reconstruct from depth, lighting half; G-buffer and depth on group 2 |

The frame uniform is laid out in `hogshade.wgpu_host.FRAME_DTYPE`; the Python side and the WGSL
struct must agree field for field, and the renderer asserts the byte size.

`tools/wgpu/viewport.py` renders the shader ball through both paths and writes
`verification/wgpu/shader-ball/<env>/forward.png` and `deferred.png`, then prints the
difference between the two: the deferred picture differs only by the G-buffer's quantisation and by
the specular F0 reconstruction, which is exact only for a dielectric at IOR 1.5 (v2's Cspec0 equals the
reconstructed 0.04); the default document's IOR is the schema's 1.45 (F0 0.0337), so the deferred picture also
carries that reconstruction error since S3.

SpriteJammer and `hog_rendering` vendor `generated/hogshade_core.wgsl` and write their own pass files
on this pattern; the binding groups here are this tool's, not a contract.
