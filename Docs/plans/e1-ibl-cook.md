# E1 plan: the IBL cook

Spec: [../specs/e1-ibl-cook.md](../specs/e1-ibl-cook.md). One PR. Tick a task only when its
verification ran.

## Tasks

- [x] 1. `content/ibl/` layout, `.gitattributes` tracking `content/**/*.exr` and `content/**/*.dds`
      under LFS, `LICENSE.md` for both environments (Poly Haven, CC0, URL, author, fetch date, 8K
      master location outside the repo). Verified 2026-09-20: `git lfs ls-files` lists both EXRs.
- [x] 2. `tools/cook_ibl.py condition`: 8K to 4K box downsample, linear half-float EXR out.
      Verified 2026-09-20: both outputs 4096x2048; mean radiance identical to the 8K to 10 digits (box
      average is exact). studio 20.4 MB, orchard 15.7 MB.
- [ ] 3. DDS writer: DX10 header, `R16G16B16A16_FLOAT`, cube, mips. Verified: `texconv`-free check by
      reading the header back with a 40-line parser, and Maya loads the file into a `dx11Shader`
      cube slot.
- [ ] 4. Equirect to cube with the DirectX face convention. Verified: a test equirect with a red
      +X dot lands on face 0's centre; the -Z centre column lands on face 5.
- [ ] 5. GGX specular prefilter to mips, roughness linear in mip. Verified by the furnace test and by
      a visual: mip 0 is the source, the last mip is a near-constant blur.
- [ ] 6. Irradiance cube and SH9. Verified: SH9 reconstruction at the cube's texel directions matches
      the irradiance cube within 2 percent RMS.
- [ ] 7. BRDF LUT. Verified: at NdotV 1, roughness 0, scale is 1 and bias is 0 within 1 percent; the
      LUT matches the published Karis reference image by eye.
- [ ] 8. `furnace` subcommand and a pytest that runs it. Verified: passes.
- [ ] 9. Manifest with sha256 of the source and every parameter. Verified: cooking twice yields
      identical output hashes.
- [ ] 10. Cook both environments; commit outputs under LFS; `preview.png` per environment.
- [ ] 11. Maya 2026: load `studio_small_09/cooked/*.dds` into the v2 shader's environment slots on a
      sphere; screenshot to `Docs/verification/maya-2026-ibl-studio.png`.
- [ ] 12. `content/ibl/README.md`: what is here, how to add an environment, how to cook.
- [ ] 13. `hogshade/jobs/cook_ibl.py` and its manifest; a smoke test that Job_Orchestrator's MODULE
      mode can import and run it locally with the studio environment.
- [ ] 14. Roadmap track E ticked for the IBL item; `Docs/README.md` status row for E1.
