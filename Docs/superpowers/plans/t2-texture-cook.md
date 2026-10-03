# T2 plan: the texture cook

**Status:** Proposed. Built on `feat/t2-texture-cook` (one PR) after the spec merges; every task verified in the
table at the end, filled as the work lands.

Spec: [../specs/t2-texture-cook.md](../specs/t2-texture-cook.md). Test-first: each task's test lands with it.

## Tasks

- [ ] 1. `hogshade/texture_cook/png.py` and `colour.py`: the PNG reader (8 and 16-bit, grey, grey-alpha, RGB,
      RGBA, the five filters None, Sub, Up, Average and Paeth; interlaced and palette refused) and the sRGB
      transfer. Verify: round trips through a test writer that emits every filter type, for grey, grey-alpha,
      RGB and RGBA at 8 and 16 bits; the refusals name their reason.
- [ ] 2. `mips.py`, `normals.py`, `pack.py`, `height.py`, and `dds.write_2d`/`read_2d` for `R8`, `R8G8`,
      `R8G8B8A8[_SRGB]`, `R16_UNORM`, `R16_FLOAT`, `R32_FLOAT`, plus `write_2d_blocks` for BC7, BC5 and BC4 (the block pitch in the header). Verify: the
      linear-average mip test, the unit-length normal mips, the `directx-y` flip recorded, the ORM packing
      with the neutral fill, the `pack` sidecar field (alpha carriers; `SIDECAR_KEYS` gains it) with its findings,
      DDS round trips per uncompressed format with mips (`R16_FLOAT` and `R32_FLOAT` for height among them), a BC4
      block decoded by hand.
- [ ] 3. `separate.py`: the wrap-padded Gaussian low-pass, the high-pass, the recombination error, the macro.
      Verify: both halves tile, `recon == source` away from clipping, the error fields are measured, the macro
      is the stated size.
- [ ] 4. `cook.py` (`cook_set`), the manifest and provenance, the sidecars' derived fields, the T1 rules applied
      first, the encoder seam with `IspcEncoder` (the `textures` extra; BC4 from an R8 surface, BC5 from RG8) the
      default and `TexconvEncoder` optional, uncompressed when neither is present; `tools/cook_textures.py` with
      `cook` and `separate`.
      Verify: a scratch set cooks, byte-identical twice, the manifest's hashes match, the sidecars gain only
      derived fields, a set with a finding is refused, `check_content.py` passes on the cooked set.
- [ ] 5. `hogshade/jobs/cook_textures.py`, registered in `hogshade.jobs.JOB_MODULES` (the registry `manifest()`
      enumerates; an unregistered module is invisible to BATS), and its test; `tools/bats/README.md` names the
      job. Verify: `hogshade.jobs.manifest()` lists it; the manifest's outputs match what the cook writes; a
      climbing `set_dir` is refused.
- [ ] 6. On the owner's machine: a Poly Haven set outside the repository cooked and separated; the
      separation picture pair under `verification/wgpu/textures/` and its gallery row. Verify: the pair
      recombines to the source by eye and by the manifest's error; the PR says what was seen.
- [ ] 7. Docs: this plan ticked with its table; the spec's amendments; the standard's runtime column
      ("or uncompressed until the encoder is present") and its cook paragraph; the board (T2 to Now, then
      struck); the glossary if a word changes; the handoff; the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| 6 | |
| 7 | |
