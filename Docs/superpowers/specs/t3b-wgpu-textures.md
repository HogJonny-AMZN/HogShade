# T3b spec: the wgpu host samples the runtime set

**Status:** Accepted (owner, 2026-10-04: "go"; question 2 on its recommendation). Drafted 2026-10-04 from the T3 spec's "out of scope" (wgpu samples no texture), the content
standard and the T2 cook. Question 1 (tangents) is answered by the owner the same day: a MikkTSpace generator of our
own on arbitrary data, the source's normals taken as given, and a flag for assets that arrive with baked tangents of
an unknown basis; question 2 proceeds on its recommendation.

Date: 2026-10-04. Standard: [../../standards/content.md](../../standards/content.md) ("The authoring set and the
runtime set"; "Tangents, detail maps and frequency separation": MikkTSpace is a requirement). The cook:
[t2-texture-cook.md](t2-texture-cook.md) (the DDS formats). The first set:
[t3-first-texture-set.md](t3-first-texture-set.md) (`hogshade.material.runtime`, the Maya half, the probe). The
wgpu host: [s3-wgpu-binding.md](s3-wgpu-binding.md) (the host map, the `Binding`, `Scene.material`). Plan:
[../plans/t3b-wgpu-textures.md](../plans/t3b-wgpu-textures.md). Vocabulary: [../../glossary.md](../../glossary.md).

## Deliverable

The wgpu host reads a cooked texture set the way the Maya shell does since T3: a standard document that binds
textures renders on the shader ball through the forward and deferred paths with its colour, normal, roughness,
metalness and ambient occlusion sampled from the DDS the cook wrote, and the gallery's first comparison matrix
puts the five committed sets on both hosts side by side. After T3b the wgpu host map carries no texture
parameter as `unsupported` except height (parallax is not in this host) and emission (no emission term), and
the two hosts render the same material from the same files, which is the floor the comparison framework (G4)
stands on.

## What the host lacks today, read from the code

- **No UVs.** `wgpu_host.load_obj` reads `v`, `vn` and `f` and drops the `vt` records the shader ball carries
  (50,914 of them); the vertex is position and normal (`array_stride` 24), the shaders' `host_VertexIn` has two
  locations.
- **No tangents.** `host_tangent_frame` builds an arbitrary frame around the normal, which is correct only
  for a flat normal map; a real normal map needs the frame the texture was baked in.
- **No texture bind group.** Group 0 is the frame, group 1 the environment, group 2 (deferred light pass) the
  G-buffer; `host_samples()` returns the unbound defaults (`vec4(1)`, `1.0`, `(0, 0, 1)`).
- **No block-compressed formats requested.** `request_device` asks for `rg11b10ufloat-renderable` only.
- **The host map** marks `normal_map`, `ambient_occlusion_map`, `cavity_map`, `height_map`, `specular_f0_map`
  as `unsupported` ("no texture bindings in the wgpu host before the comparison framework"), and colour,
  roughness and metalness as frame fields (factors), never textures.

## What lands

### 1. The mesh carries UVs and tangents

`Mesh.vertices` becomes `(n, 12)` float32: position, normal, uv, tangent with its sign in `w`
(`float32x3, float32x3, float32x2, float32x4`; stride 48). `load_obj` reads `vt` and keys a vertex on
`(v, vt, vn)`. Tangents come from a MikkTSpace implementation (question 1): the standard says every host
generates MikkTSpace tangents when a file carries none, the OBJ carries none, and a normal map baked in Maya
(MikkTSpace by default since 2026) decodes correctly only in that frame. The shaders' `host_VertexIn` gains
`uv` and `tangent`; `host_geometry` builds the frame from the interpolated tangent, bitangent (`cross(n, t) *
sign`) and normal, and keeps the arbitrary frame only when the tangent is zero (a mesh without UVs).

### 1b. Tangents on arbitrary data, and the flag for an unknown basis (owner, 2026-10-04)

`hogshade/mikktspace.py` (numpy, library) takes what any source gives: positions, **the normals as provided**
(MikkTSpace consumes custom normals and survives them; the generator never recomputes a normal, it only builds
the tangent frame around the one it is handed), UVs and triangle indices, and returns per-corner tangents with
the handedness sign, welded the way the reference does (by position, normal and UV, angle-weighted, the sign
kept separate so a mirrored island does not average to zero; never by position alone, which would blend
frames across a normal or UV seam). The implementation is held to the reference, not only to sphere
tests: a **parity fixture** of the shader ball's tangents and signs from Maya's own MikkTSpace (a BATS job
dumps them once from the legacy scene, committed as `tests/host/fixtures/shaderball_mikktspace.npz`) is
compared vertex by vertex, seams and mirrored islands included, within a stated tolerance (direction within
1 degree, sign exact); a second fixture is a small hand-made mesh with a UV seam and a mirrored island. It is the one generator for every host and
exporter here, the standard's requirement made code: the wgpu host calls it when a file carries no tangents,
the Maya side relies on Maya's own MikkTSpace (default since 2026) and the comparison framework later checks
the two agree on the shader ball.

**The flag.** A mesh that arrives with tangents already baked in (an FBX, a glTF, an OBJ with a custom
extension) carries them in an unknown basis unless its provenance says MikkTSpace. `Mesh` gains
`tangent_basis: "mikktspace" | "unknown" | "none"`: `"mikktspace"` when generated here or declared by the
asset's record, `"unknown"` when the file carried tangents and nothing says how they were made, `"none"` when
the file has none and the host generated them. The host logs an `"unknown"` as a WARNING, regenerates with the
generator anyway (the project assumes and requires MikkTSpace; an unknown basis is not trusted), and the
record beside a committed mesh (`content/shaderball/`'s and every asset after it) states its basis, which
`check_content.py` reads once meshes join the content standard (a follow-on row, not T3b).

### 2. The material bind group

Group 2 on the forward (`lit_mesh`) and geometry (`gbuffer_fill`) pipelines; the deferred light pass keeps
its G-buffer at group 2 (group indices are per pipeline layout):

| Binding | What | Format, compressed | Format, uncompressed |
| --- | --- | --- | --- |
| 0 | `base_color` | `bc7-rgba-unorm-srgb` | `rgba8unorm-srgb` |
| 1 | normal (`_N`, two channels) | `bc5-rg-unorm` | `rg8unorm` |
| 2 | `_ORM` (AO red, roughness green, metalness blue) | `bc7-rgba-unorm` | `rgba8unorm` |
| 3 | cavity (`_C`) | `bc4-r-unorm` | `r8unorm` |
| 4 | the sampler: linear, mipmap linear, repeat, anisotropy 8 | | |
| 5 | `host_Textures` uniform: a bit **per textured parameter** (base colour, normal, roughness, metalness, AO, cavity), and for each scalar parameter the slot it reads and the channel (0 to 3) | | |

A slot a document does not bind holds a 1x1 neutral texture (white, flat normal `(128, 128)`, white ORM,
white cavity). The bits are **per parameter, not per slot** (the Maya shell's `use<Map>` flags, one each, and
T3's rule that a packed channel is read only where its own parameter is bound): a document binding roughness
alone reads `_ORM`'s green and leaves metalness and AO at their unbound 1.0, as Maya does. The scalar
parameters carry a **channel selector** because the cook may put a map anywhere the sidecar says: roughness,
metalness and AO in `_ORM`'s g, b, r as a rule, and cavity in its own BC4 red or, when a sidecar packs it, in
a carrier's alpha (`runtime_textures` reports the slot's path and `channels`, `"a"` included); the uniform
carries what the runtime reported, and the shader selects by index rather than assuming red. Height and emission are not slots:
the wgpu host has no parallax and no emission term (the host map says so, as today).

### 3. The DDS upload and the device features

`hogshade/wgpu_textures.py` (new, numpy and wgpu, imported by the host only): `upload_dds(device, path) ->
(texture, format, mips)` from `dds2d.read_2d`, every level written (`write_texture` with the block pitch for
a block format, the row pitch for an uncompressed one), the DXGI name mapped to the wgpu format above;
`neutral_texture(device, kind)` for the unbound slots; `material_textures(device, runtime) -> bind group
entries` from `hogshade.material.runtime.runtime_textures`, the `_ORM` channels checked against the slot's
expectation (AO r, roughness g, metalness b) as the Maya check does. `request_device` asks for
`texture-compression-bc` when the adapter has it; without it, a block-compressed set is refused with a message
naming `tools/cook_textures.py cook <set> --no-compress` (the cook's uncompressed output is the fallback, the
manifest says which was written). `R16_UNORM` is not a core wgpu format and height is not a slot, so nothing
is lost by not handling it in T3b.

### 4. The host map and the binder

`hogshade/material/hosts/wgpu.json` gains a `texture` entry kind beside `field`/`components` and
`unsupported`, **scoped to legacy v2 with the map's `@` keys** (`"normal_map@hogshade-legacy-v2": {"texture":
"normal"}`, `"ambient_occlusion_map@hogshade-legacy-v2": {"texture": "orm", "channel": "r"}`,
`"cavity_map@hogshade-legacy-v2": {"texture": "cavity"}`; the factor-bearing `base_color`, `roughness`,
`metalness` keep their fields and gain the slot and channel under the same `@` keys), because `host_inputs()`
samples for legacy v2 only: legacy v1 and Lambert keep their factor and `unsupported` entries unchanged, and a
test holds that `entries_for` on those two types shows no `texture`. `_check_wgpu_map` validates the kind (a slot
name from the host's list, a channel letter where the slot is packed) and the coverage rule stays: every
parameter bound, textured or `unsupported` with a reason. `bind(resolved, "wgpu")` is unchanged in shape;
`Binding.textures` already carries the paths, and the host resolves them with `runtime_textures(binding.textures,
doc_dir)`. `Scene` gains `textures: dict[str, RuntimeTexture] | None`. **A bind group is keyed by its
contents, not by the set**: the DDS uploads are shared by path within a device, and the bind group's key is the
tuple of (slot path, channel) per parameter plus the bound mask, because one set serves several documents
(the grid's `T_grid_BC` and `T_grid_BC_blue` are two documents over one manifest) and two documents binding
different subsets of a set need different neutral slots and bits.

### 5. `host_samples()` reads the slots

```wgsl
// one texel per slot, sampled once; a scalar parameter picks its slot and channel from the uniform
fn host_scalar(texels: array<vec4<f32>, 4>, sel: vec2<u32>, bound: bool) -> f32 {
    return select(1.0, texels[sel.x][sel.y], bound);
}
fn host_samples(uv: vec2<f32>) -> legacy_v2_Samples {
    var s: legacy_v2_Samples;
    let b = host_textures.bound;   // bit per parameter: 1 base colour, 2 normal, 4 roughness, 8 metalness, 16 AO, 32 cavity
    var texels: array<vec4<f32>, 4>;
    texels[0] = textureSample(host_base_color, host_material_sampler, uv);
    texels[1] = textureSample(host_normal, host_material_sampler, uv);
    texels[2] = textureSample(host_orm, host_material_sampler, uv);
    texels[3] = textureSample(host_cavity, host_material_sampler, uv);
    s.base_color = select(vec4<f32>(1.0), texels[0], (b & 1u) != 0u);
    let n_rg = select(vec2<f32>(0.5), texels[1].rg, (b & 2u) != 0u);
    s.normal_ts = vec3<f32>(n_rg * 2.0 - 1.0, 0.0);   // legacy_v2_normal_ts derives Z (T3's finding)
    s.roughness = host_scalar(texels, host_textures.roughness_sel, (b & 4u) != 0u);
    s.metalness = host_scalar(texels, host_textures.metalness_sel, (b & 8u) != 0u);
    s.ao = host_scalar(texels, host_textures.ao_sel, (b & 16u) != 0u);
    s.cavity = host_scalar(texels, host_textures.cavity_sel, (b & 32u) != 0u);
    ...
}
```

Every slot is sampled unconditionally (uniform control flow keeps the derivatives for mip selection valid)
and a neutral 1x1 costs nothing to sample; the bits and selectors decide what is used.

The core is untouched: `legacy_v2_inputs` multiplies the samples by the factors as it always did, and
`legacy_v2_normal_ts` reconstructs Z with its clamp, the same path Maya's BC5 normal takes. The core contract
is not in scope; the host's WGSL changes are in `hosts/wgpu/common.wgsl`, `lit_mesh.wgsl` and
`gbuffer_fill.wgsl`.

### 6. The proof

`tools/wgpu/viewport.py --material <document>` renders a textured document; the contact sheet renders the
four T3 documents with their textures (the sheet's caption loses its "constants only" sentence); a new
`tools/wgpu/texture_matrix.py` renders the five sets (the grid tile through `document_for_set`) in the forward
path into `verification/wgpu/textures/<set>/main.png` beside the Maya captures, and the gallery's first
**matrix** (the owner's layout row): sets as rows, Maya and wgpu as columns, so the two hosts' renders of one
file sit side by side. The two pictures will not match pixel for pixel (different mesh, camera and output
space; G4's framework is what makes them a diff), but a human can see the same brick, the same metalness.

## Tests

- `tests/host/test_wgpu_host.py` (GPU, skipped without an adapter or LFS payloads): a textured document
  renders, its colour differs from the untextured one where the map differs, a normal map tilts the shading
  (the brick's mortar lines darker than the untextured ball at the same pixels), `_ORM` channels land on the
  right inputs (the grid tile's metalness cells read metal through debug mode), an unbound slot equals the
  untextured render bit for bit, a block-compressed set without the feature is refused by name.
- `tests/host/test_mikktspace.py` or the binding's tests: tangents on a UV sphere are tangent to the surface,
  unit, follow the U direction, the sign flips on a mirrored island; `load_obj` keeps UVs and the vertex
  count matches `(v, vt, vn)` corners.
- `tests/material/test_material_bind.py`: the wgpu map's texture entries validate, a malformed slot or channel
  is a finding, the coverage rule holds, `bind()` still lists every texture.
- `hogshade/wgpu_textures.py` without a device: the DXGI to wgpu format table covers every format the cook
  writes except `R16_*`/`R32_FLOAT` (named as not slots), the block pitch arithmetic for odd mip sizes.

## Acceptance gate

- The five committed sets render in the wgpu host from their cooked DDS (block-compressed, the feature
  present on the owner's machine) and the pictures sit beside the Maya ones in the gallery matrix.
- The untextured library renders unchanged: the contact sheet's twenty-two constant documents are pixel
  identical to today's (the neutral slots and the arbitrary-frame fallback keep the old path).
- `generate_material_ui.py --check`, `check_content.py`, `check_docs.py`, `generate_gallery.py --check` clean;
  `pytest` green on both legs (GPU tests skipped on CI, run on the owner's machine and stated in the PR).

## Out of scope

- Height and parallax in the wgpu host; emission; opacity and cutout (the host renders opaque); the detail
  maps' blending; legacy v1 with textures (no standard document converts to it).
- The comparison framework itself (G4): the matrix is a human's side by side, not a diff.
- The quad sphere (an Icebox row): the shader ball stays the mesh here; the matrix's second row can take the
  quad sphere when it exists.

## The questions for the owner

1. **Tangents.** Answered (owner, 2026-10-04): "we absolutely need a way to gen MikkT on arbitrary data, and then
   flag it if it came with baked assets of an unknown tangent base"; MikkTSpace "accounts for and survives custom
   normals, whatever normals the source provides; my goal is a future-forward and correct project that assumes and
   requires MikkT, which Maya supports now." So: the generator of our own in numpy (section 1b), the normals as
   given, the `tangent_basis` flag with a WARNING and regeneration for an unknown basis. The PyPI binding is not
   taken.
2. **Where the wgpu renders of the sets live.** Recommended: `verification/wgpu/textures/<set>/main.png` beside
   the existing separation pictures of `cobblestone_floor_04` and `brick_wall_001`, mirroring
   `verification/maya-2026/textures/<set>/`, so the gallery matrix reads one path pattern per host.

## Amendments after the spec's review (Copilot on #61, 2026-10-04)

All five valid and folded into the text above:

- **Texture entries scoped to legacy v2** with the host map's `@` keys; legacy v1 and Lambert keep their
  factor and `unsupported` entries, since `host_inputs()` samples for v2 only; tested.
- **A bind group is keyed by its contents** (slot paths, channels, bound mask), uploads shared by path: one
  set serves several documents and two documents may bind different subsets.
- **Bits per parameter, not per slot**, with channel selectors for the scalar parameters: roughness alone
  reads `_ORM`'s green and leaves metalness and AO unbound, as Maya does since T3.
- **A packed cavity** (a carrier's alpha) is sampled from the channel the runtime reports, never assumed red;
  a regression with a packed `_C`.
- **MikkTSpace held to the reference**: the weld is by position, normal and UV (never position alone) and a
  parity fixture from Maya's MikkTSpace on the shader ball, seams and mirrored islands included, is a test.

## What the build found (2026-10-04, `feat/t3b-wgpu-textures`)

- **Maya 2026.3 exposes no MikkTSpace choice on a mesh.** The job that dumps the fixture
  (`hogshade.jobs.maya_mikktspace_dump`, headless) asks the mesh's `tangentSpace` enum and gets
  `detectWindingRightHanded`, `rightHanded`, `detectWindingLeftHanded`, `leftHanded`; it records the names and
  selects nothing. So the fixture is Maya's default basis and the parity test (`tests/host/test_mikktspace.py`)
  states the measured distance rather than identity: on the shader ball's 135,792 corners the handedness agrees
  on every corner (20,628 mirrored on both sides), the direction agrees to a median of 0.8 degrees, 98 percent
  within 5 degrees, the worst corner 35 degrees; uniform or area weighting instead of MikkTSpace's angle weighting
  moves none of those numbers, so the gap is Maya's smoothing rule, not ours. Where Maya's MikkTSpace lives (the
  owner's "supported in Maya now"; the exporters, the viewport preference, a newer attribute) is a question for
  the owner; the generator is held to the reference either way.
- **Group 2 is per pipeline layout**, and the fill pass had no group 1: it now carries the environment layout
  unused at group 1 so `material.wgsl` can say `@group(2)` once for both mesh passes. The light pass keeps its
  G-buffer at group 2 and defines a `host_samples` of unbound defaults, since `host_inputs()` in `common.wgsl`
  names it and WGSL needs the symbol in every stitched module.
- **`host_Textures` is 48 bytes as WGSL lays it out**: `bound: u32` at 0, then two `vec4<u32>` at 16 and 32 (the
  selectors in pairs), not nine packed `u32`; `MaterialPlan.uniform_bytes()` writes that layout and the test
  unpacks it.
- **V is flipped at the sample**, not in the mesh: the tangents are built from the OBJ's bottom-up V and the
  DDS's first row is the top, which is how the Maya shell does it (`m_Uv0.y` negated).
- **The deferred path agrees on a textured ball** within the untextured tolerance (brick: mean 0.0007, max 0.006);
  the grid tile's max rises to 1.8 on silhouette pixels of its metal cells (mean 0.017), the G-buffer's
  quantisation of a high-contrast metalness, not a texture fault.
- **The packed-cavity regression is a plan test, not a GPU test**: no committed set packs `_C` into a carrier's
  alpha (the grid's is its own BC4), so the selector is proven at the plan level (`tests/host/test_wgpu_textures.py`)
  and the GPU test reads the grid's own cavity through debug view 10. T4's set, with the alpha carrier, closes it.
- **The contact sheet's twenty-two constant documents are pixel-identical** to the committed sheet (compared cell
  by cell before overwriting it); only the four T3 documents changed, which is the gate. The untextured shader
  ball (`shader-ball/studio_small_09/forward.png`) re-rendered to one pixel one step off the committed capture,
  the GPU's run-to-run jitter the Maya gate also sees; the committed picture stands.
- **A carrier in the base-colour slot is one carrier.** A map packed into `_E`'s or `_SC`'s alpha maps that carrier
  onto the `base_color` slot, so a document binding it beside `_BC` is a slot conflict (`TextureError`), not a
  render. No committed set does this; T4's alpha carrier decides whether the host grows a fifth slot.
- **`tangent_basis="unknown"` has its path**: `with_tangents(..., tangents=, tangent_basis=)` takes a source's
  tangents, uses a `mikktspace` basis as given, flags `unknown` with a WARNING and regenerates, and refuses any
  other basis (the content standard's validation failure). No loader here passes tangents yet (the OBJ carries
  none); the first that does gets the rule for free.

