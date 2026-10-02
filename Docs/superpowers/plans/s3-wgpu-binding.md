# S3 plan: the wgpu binding

**Status:** Proposed. Runs after the owner approves the spec; one PR. Tick a task only when its
verification ran; `/local-review diff` runs before the PR opens.

Spec: [../specs/s3-wgpu-binding.md](../specs/s3-wgpu-binding.md). Test-first: each task's test lands with it.

## Tasks

- [ ] 1. The wgpu host map `hogshade/material/hosts/wgpu.json` and `check_host_map`'s wgpu entry shape
      (field and components, `unsupported` with a reason, the `@type` key suffix, double writes, widths).
      Verify: the shipped map passes and covers the union of the three types; five mutated maps each
      produce the named finding.
- [ ] 2. `binding.py`: `Binding`, `bind(resolved, host)`; `model` from the type; the standard type refused
      naming C3; textures listed. Verify: the v2 default document binds to `Scene()`'s defaults component
      for component; the v1 default binds the lobes; lambert binds `base_color` only; the refusals.
- [ ] 3. `hogshade/wgpu_host.py`: `MaterialBinding`, `Scene.material`, `frame_bytes` packing as one loop
      over the map's fields; `MaterialBinding.from_binding`. Verify: the existing host tests pass
      unchanged in meaning (their hand-set scenes move to `MaterialBinding(...)`); a bound document and
      the equivalent hand-set scene give identical `frame_bytes`.
- [ ] 4. The two default documents under `content/materials/` and `tools/wgpu/viewport.py --material`
      (the `--model` flag retired). Verify: the documents validate and resolve; the viewport renders both
      on the owner's GPU, pictures under `verification/wgpu/` named in the PR; the v2 picture equals the
      pre-S3 default render.
- [ ] 5. Docs: this plan ticked with a verification table; the spec's status and amendments; the board
      (S3 to Now, then struck); the glossary's Binding row if its wording changes; `Docs/README.md`; the
      handoff; the journal. Verify: `tools/check_docs.py` clean.
