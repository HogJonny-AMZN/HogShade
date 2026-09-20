# E1 plan: the IBL cook

Spec: [../specs/e1-ibl-cook.md](../specs/e1-ibl-cook.md). One PR. Tick a task only when its
verification ran.

## Tasks

- [ ] 1. `content/ibl/` layout, `.gitattributes` tracking `content/**/*.exr` and `content/**/*.dds`
      under LFS, `LICENSE.md` for both environments (Poly Haven, CC0, URL, author, fetch date, 8K
      master location outside the repo). **Partial 2026-09-20:** layout, attributes and licences are
      in; the two `source_4k.exr` files are conditioned and committed on a local branch but GitHub
      refuses LFS uploads into a public fork, so they are not in the repository yet. Ticks when
      `git lfs ls-files` on a fresh clone lists both EXRs, after the owner leaves the fork network.
- [x] 2. `tools/cook_ibl.py condition`: 8K to 4K box downsample, linear half-float EXR out.
      Verified 2026-09-20: both outputs 4096x2048; the float32 box average preserves mean radiance to
      10 digits, and the record now also reports the mean after float16 quantisation, which is what
      the file holds (within 0.05 percent on both). studio 20.4 MB, orchard 15.7 MB, local only until
      task 1 completes.
- [ ] 3. DDS writer: DX10 header, `R16G16B16A16_FLOAT`, cube, mips. Verified: `texconv`-free check by
      reading the header back with a 40-line parser, and Maya loads the file into a `dx11Shader`
      cube slot.
- [ ] 4. Equirect to cube with the face and latitude formulas fixed in the spec. Verified with
      asymmetric markers, not centre dots: a synthetic equirect with a distinct colour at each of
      +X, -X, +Y, -Y, +Z, -Z and a seventh marker off-centre on the +X face (at +u, -v) must land on
      the expected face, in the expected texel quadrant, with the expected orientation; a rotated
      or mirrored face fails the quadrant check.
- [ ] 5. GGX specular prefilter to mips, roughness linear in mip. Verified by the furnace test and by
      a visual: mip 0 is the source, the last mip is a near-constant blur.
- [ ] 6. Irradiance cube and SH9. Verified: SH9 reconstruction at the cube's texel directions matches
      the irradiance cube within 2 percent RMS.
- [ ] 7. BRDF LUT. Verified: at NdotV 1, roughness 0, scale is 1 and bias is 0 within 1 percent; the
      LUT matches the published Karis reference image by eye.
- [ ] 8. `furnace` subcommand and a pytest that runs it. Verified: passes.
- [ ] 9. `manifest.json` (deterministic: parameters, conventions, source sha256, output sha256s,
      tool version) and `provenance.json` (volatile: wall time, machine, git hash). Verified: cooking
      twice yields byte-identical `manifest.json` and outputs; only `provenance.json` differs.
- [ ] 10. Cook both environments; commit outputs under LFS; `preview.png` per environment.
- [ ] 11. Maya 2026: load `studio_small_09/cooked/*.dds` into the v2 shader's environment slots on a
      sphere; screenshot to `Docs/verification/maya-2026-ibl-studio.png`.
- [ ] 12. `content/ibl/README.md`: what is here, how to add an environment, how to cook.
- [ ] 13. `hogshade/jobs/cook_ibl.py` and its manifest; a smoke test that Job_Orchestrator's MODULE
      mode can import and run it locally with the studio environment.
- [ ] 14. Roadmap track E ticked for the IBL item; `Docs/README.md` status row for E1.
