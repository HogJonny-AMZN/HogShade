# S3 plan: the wgpu binding

**Status:** Accepted. Built 2026-10-02 on `feat/s3-wgpu-binding` (one PR) after #37 approved the spec; every
task verified, see the table; the local review ran before the PR opened.

Spec: [../specs/s3-wgpu-binding.md](../specs/s3-wgpu-binding.md). Test-first: each task's test lands with it.

## Tasks

- [x] 1. The wgpu host map `hogshade/material/hosts/wgpu.json` and `check_host_map`'s wgpu entry shape
      (field and components, `unsupported` with a reason, the `@type` key suffix, double writes, widths).
      Verify: the shipped map passes and covers the union of the three types; five mutated maps each
      produce the named finding.
- [x] 2. `binding.py`: `Binding`, `Unbound` in `model.py`, `bind(resolved, host)` taking a `Resolved` only;
      `model` from the type; the standard type refused naming C3; textures listed. Verify: the v2 default document binds to `Scene()`'s defaults component
      for component; the v1 default binds the lobes; lambert binds `base_color` only; the refusals.
- [x] 3. `hogshade/wgpu_host.py`: `MaterialBinding`, `Scene.material`, `frame_bytes` packing as one loop
      over the map's fields; `MaterialBinding.from_binding`; the defaults are the v2 schema's. Verify:
      the existing host tests pass unchanged in meaning (their hand-set scenes move to
      `MaterialBinding(...)`); a bound document and the equivalent hand-set scene give identical
      `frame_bytes`.
- [x] 4. The two default documents under `content/materials/` and `tools/wgpu/viewport.py --material`
      (the `--model` flag retired). Verify: the documents validate and resolve; the viewport renders both
      on the owner's GPU, pictures under `verification/wgpu/` recaptured and named in the PR with the
      diff against the pre-S3 pictures stated (the defaults are the schema's now, so they differ).
- [x] 5. Docs: this plan ticked with a verification table; the spec's status and amendments; the board
      (S3 to Now, then struck); the glossary's Binding row if its wording changes; `Docs/README.md`; the
      handoff; the journal. Verify: `tools/check_docs.py` clean.

## Verification, 2026-10-02

| Task | Ran |
| --- | --- |
| 1 | `hosts/wgpu.json`: 39 entries (38 parameters plus `specular_tint@hogshade-legacy-v1`) over the three types; `check_host_map` clean; `entries_for` resolves the suffix; mutated maps name a double write, a component beyond the width, bound-and-unsupported, a missing reason, an unknown field, a missing entry, a texture bound, a schema key repeated, a suffix naming a type without the parameter (`test_material_bind.py`) |
| 2 | `bind(resolve(doc), "wgpu")` of the v2 default document gives `base_color (0.6, 0.6, 0.6, 0.5)`, `material (0, 1, 0, 1.45)`, `model (2, 0, 0, 0)`; the v1 document binds the lobes into `params_a`/`params_b` and `specular_tint` into `params_a[1]` with `material[2]` 0; lambert binds `base_color` only; the standard type is refused naming C3; a raw `Document`, an unknown host and an invalid material are refused; textures listed and unsupported |
| 3 | `MaterialBinding` with the v2 schema defaults, `Scene.material`, `Scene.model` a property, `frame_bytes` packing the map's fields in one loop; `MaterialBinding.from_binding`; the host tests moved to `MaterialBinding(...)`; a bound document and the hand-set scene give identical `frame_bytes` for v2 and v1 (`test_a_bound_document_and_the_hand_set_scene_pack_the_same_frame`); on the owner's GPU the v2 document and `Scene()` render identical forward images and a v1 document's `sheen` reaches the shader (`test_documents_render_through_the_binding`) |
| 4 | `content/materials/legacy-v2/default.material.json`, `legacy-v1/default.material.json`, and a third, `legacy-v2/metal.material.json`, so the committed `metal` variant stays reproducible (its `deferred.png` is new, no pre-S3 baseline); `viewport.py --material` (the `--model` and per-parameter flags gone). Pictures recaptured under `verification/wgpu/shader-ball/studio_small_09/` (default, `legacy-v1/`, `metal/`): against the pre-S3 pictures 63 percent of pixels differ (the ball), max 53 to 56 grey levels, because the defaults are the schema's now (roughness 0.5 and IOR 1.45 instead of 0.2 and 1.5; base colour 0.6 instead of 0.5) |
| 5 | This table; the spec's amendments; board, docs map, glossary (`Unbound`), handoff, journal; `check_docs.py` clean |

Totals: `uv run pytest tests/material` 199 passed; the full suite 356 passed on the owner's GPU.

| Review | Ran |
| --- | --- |
| Pre-PR `/local-review diff` | Design 6, Architecture 8, Readability 8, Maintainability 7, Performance 8, Security 8, Error handling 7, Logging 6, Coding standards 8; needs-work. The map against the WGSL verified exact (every bound entry a read the shader makes; no read unwritten). Fixed before the PR opened: `from_binding`'s hidden state (a `Scene` takes a `Binding` directly), the unconfigured debug logging in the tool, the README command `--model` that no longer ran, the stale "IOR 1.5, exact" claim in the wgpu host README, three checker rules (`types` duplicates, entry `types` outside the host, two entries selecting one parameter), `pack_fields`' width guard, one model-id table, a cached host map, a smoke block |
