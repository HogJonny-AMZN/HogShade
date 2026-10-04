# T3b plan: the wgpu host samples the runtime set

**Status:** Accepted (owner, 2026-10-04: "go"). Drafted 2026-10-04 with the spec; question 1 (tangents) answered by the owner the same
day (a generator of our own, the normals as given, a flag for an unknown basis); built the same night on `feat/t3b-wgpu-textures`, every task ticked. Test-first: each task's test lands with it; the GPU tests run on the owner's machine and are skipped on
CI, which the PR states.

Spec: [../specs/t3b-wgpu-textures.md](../specs/t3b-wgpu-textures.md).

## Tasks

- [x] 1. **UVs and tangents in the mesh**: `load_obj` reads `vt` and keys corners on `(v, vt, vn)`; `Mesh.vertices`
      becomes position, normal, uv, tangent-with-sign (stride 48); `hogshade/mikktspace.py`, the generator on
      arbitrary data (positions, the normals as given, UVs, indices; welded as the reference welds, the sign kept
      apart); `Mesh.tangent_basis` (`mikktspace`, `unknown`, `none`) with a WARNING and regeneration for `unknown`;
      `normalise_mesh` keeps the new columns. Verify: tangents unit and tangent to the surface on a UV sphere,
      following U, the sign flipping on a mirrored island, custom normals left untouched (a sphere with
      deliberately tilted normals keeps them); **parity with Maya's MikkTSpace** on the shader ball (a BATS job
      dumps the tangents once, `tests/host/fixtures/shaderball_mikktspace.npz`; direction within 1 degree, sign
      exact, seams and mirrored islands included) and on a hand-made seam mesh; the shader ball's vertex count
      equals its distinct `(v, vt, vn, handedness)` corners and a seam both handednesses share is split; the untextured render unchanged (the arbitrary frame kept where the tangent
      is zero).
- [x] 2. **`hogshade/wgpu_textures.py`**: `upload_dds` (every mip, block pitch for BC, row pitch otherwise, the
      DXGI to wgpu format table), `neutral_texture`, `material_textures` from `runtime_textures` with the
      `_ORM` channel check; `request_device` asks for `texture-compression-bc`; a block-compressed set without
      it refused naming `--no-compress`. Verify: the format table against every format the cook writes; the
      pitch arithmetic on odd mips; an upload of the brick fixture's four DDS reads back level 0 (GPU).
- [x] 3. **The host map's `texture` entries, scoped to legacy v2** (`normal_map@hogshade-legacy-v2`,
      `ambient_occlusion_map@...`, `cavity_map@...`; the slots and channels beside `base_color`, `roughness`,
      `metalness`), `_check_wgpu_map` validating slot and channel, the coverage rule kept. Verify:
      `tests/material/test_material_bind.py` (valid map, a bad slot, a bad channel, a texture on a parameter the
      schema does not let a texture bind to; legacy v1 and Lambert entries show no `texture`).
- [x] 4. **The material bind group and `host_samples(uv)`**: group 2 on `lit_mesh` and `gbuffer_fill`, the
      `host_Textures` uniform with a bit per parameter and a slot-and-channel selector per scalar, the neutral
      slots, `host_geometry` from the interpolated tangent frame; `Scene.textures`; uploads shared by path, bind
      groups keyed by their contents. Verify: the GPU tests in the spec (textured differs where the map differs,
      the normal tilts shading, `_ORM` channels on the right inputs, roughness alone leaves metalness and AO at
      1.0, a packed cavity sampled from the alpha, two documents over one set get two bind groups, an unbound
      slot bit-identical to today, deferred equals forward within the existing tolerance).
- [x] 5. **The proof**: `viewport.py --material` on a textured document; the contact sheet with the four T3
      documents textured (caption updated); `tools/wgpu/texture_matrix.py` rendering the five sets into
      `verification/wgpu/textures/<set>/main.png`; the gallery's first matrix (sets as rows, Maya and wgpu as
      columns), which needs the gallery's `grids` entry kind from the Icebox row (built here, since this is its
      first use). Verify: `generate_gallery.py --check`; the pictures read by a human and the reading in the PR.
- [x] 6. **Docs**: `hosts/wgpu/README.md` (group 2, the formats, the feature), the S3 spec's "texture sampling
      stays out" amended by pointer, the content standard's host paragraph, the T3 spec's "out of scope" pointer,
      this plan ticked with its table, the board, the handoff, the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | `tests/host/test_mikktspace.py` (9: quad, mirrored island, UV sphere, custom normals kept, degenerate fallback, shapes, a source basis used, flagged or refused, a seam both handednesses share split with each side keeping its sign; the fixture lines up corner for corner with `load_obj`; parity with Maya's frame on the shader ball: handedness exact on 135,792 corners, direction median 0.8 degrees, 98 percent within 5, worst 35). The fixture from `hogshade.jobs.maya_mikktspace_dump` on the headless worker (Maya 2026.3 offers no MikkTSpace entry; the spec's "what the build found"). The untextured ball renders unchanged: the lit-ball, v1 and binding tests of `tests/host/test_wgpu_host.py` pass as before and the contact sheet's twenty-two constant documents are pixel-identical |
| 2 | `tests/host/test_wgpu_textures.py` (6: the format table against the cook's output, a full plan's bits and selectors with the 48-byte uniform, roughness alone, the packed cavity and distinct keys, refusals, and every mip of the brick's 2048 BC7 chain written with the block pitch and the size rounded to a block, the 2x2 and 1x1 mips included, through a recording device); the block-compressed refusal by name on the brick's DDS in `test_wgpu_host.py`. The readback of an upload is the GPU render tests of task 4 (a textured document differs from its constants), not a `copy_texture_to_buffer` of the compressed texture |
| 3 | `tests/material/test_material_bind.py` (`test_texture_entries_are_scoped_to_legacy_v2_and_validated` and the updated map checks); `generate_material_ui.py --check` clean |
| 4 | `tests/compile` (every stitched pass valid); `tests/host/test_wgpu_host.py` GPU (26 on the owner's machine): textured differs from the constants where the map differs and the base-colour view varies, the normal tilts the shading normal, the ORM channels land on roughness, metalness and AO through debug views 8, 7, 9 with roughness alone leaving metalness and AO flat, the grid's cavity through view 10, two documents over one set share uploads and get two bind groups, an empty texture set is bit-identical to none, deferred agrees on the textured ball |
| 5 | `tools/wgpu/viewport.py --material` on the brick; `tools/wgpu/contact_sheet.py` with the four T3 documents textured (cell-by-cell comparison: only those four changed); `tools/wgpu/texture_matrix.py` for the five sets; `tests/test_generate_gallery.py` (the `grids` kind: rendered as a table, unlisted cell, short row, no columns, not a list); `generate_gallery.py --check` clean |
| 6 | `check_docs.py` clean (92 files) |

Totals: the full suite green on the owner's machine (GPU included); CI skips the GPU tests and the fixture-backed
parity test runs wherever the shader ball is hydrated.
