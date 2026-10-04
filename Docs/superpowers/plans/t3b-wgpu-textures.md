# T3b plan: the wgpu host samples the runtime set

**Status:** Proposed. Drafted 2026-10-04 with the spec; built after the owner answers question 1 (tangents) and
approves. Test-first: each task's test lands with it; the GPU tests run on the owner's machine and are skipped on
CI, which the PR states.

Spec: [../specs/t3b-wgpu-textures.md](../specs/t3b-wgpu-textures.md).

## Tasks

- [ ] 1. **UVs and tangents in the mesh**: `load_obj` reads `vt` and keys corners on `(v, vt, vn)`; `Mesh.vertices`
      becomes position, normal, uv, tangent-with-sign (stride 48); the MikkTSpace tangents (the owner's answer to
      question 1); `normalise_mesh` keeps the new columns. Verify: tangents unit and tangent to the surface on a
      UV sphere, following U, the sign flipping on a mirrored island; the shader ball's vertex count equals its
      distinct corners; the untextured render unchanged (the arbitrary frame kept where the tangent is zero).
- [ ] 2. **`hogshade/wgpu_textures.py`**: `upload_dds` (every mip, block pitch for BC, row pitch otherwise, the
      DXGI to wgpu format table), `neutral_texture`, `material_textures` from `runtime_textures` with the
      `_ORM` channel check; `request_device` asks for `texture-compression-bc`; a block-compressed set without
      it refused naming `--no-compress`. Verify: the format table against every format the cook writes; the
      pitch arithmetic on odd mips; an upload of the brick fixture's four DDS reads back level 0 (GPU).
- [ ] 3. **The host map's `texture` entries** (`normal_map`, `ambient_occlusion_map`, `cavity_map`; the slots
      beside `base_color`, `roughness`, `metalness`), `_check_wgpu_map` validating slot and channel, the coverage
      rule kept. Verify: `tests/material/test_material_bind.py` (valid map, a bad slot, a bad channel, a texture
      on a parameter the schema does not let a texture bind to).
- [ ] 4. **The material bind group and `host_samples(uv)`**: group 2 on `lit_mesh` and `gbuffer_fill`, the
      `host_Textures` uniform with the bound bits, the neutral slots, `host_geometry` from the interpolated
      tangent frame; `Scene.textures`; the renderer caches a set's bind group. Verify: the GPU tests in the spec
      (textured differs where the map differs, the normal tilts shading, `_ORM` channels on the right inputs, an
      unbound slot bit-identical to today, deferred equals forward within the existing tolerance).
- [ ] 5. **The proof**: `viewport.py --material` on a textured document; the contact sheet with the four T3
      documents textured (caption updated); `tools/wgpu/texture_matrix.py` rendering the five sets into
      `verification/wgpu/textures/<set>/main.png`; the gallery's first matrix (sets as rows, Maya and wgpu as
      columns), which needs the gallery's `grids` entry kind from the Icebox row (built here, since this is its
      first use). Verify: `generate_gallery.py --check`; the pictures read by a human and the reading in the PR.
- [ ] 6. **Docs**: `hosts/wgpu/README.md` (group 2, the formats, the feature), the S3 spec's "texture sampling
      stays out" amended by pointer, the content standard's host paragraph, the T3 spec's "out of scope" pointer,
      this plan ticked with its table, the board, the handoff, the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| | |

Totals: filled when the build lands.
