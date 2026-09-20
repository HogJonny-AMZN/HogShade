# Phase 2 plan: the WGSL core and its first two hosts

Spec: [../specs/phase-2-restructure.md](../specs/phase-2-restructure.md). Several PRs; the spike is its
own. Tick a task only when its verification ran.

## PR A: the spike

- [ ] 1. Toolchain: Rust via `winget install Rustlang.Rustup`, then `cargo install naga-cli`; record
      versions in `Docs/verification/toolchain.md`. Verified: `naga --version`.
- [ ] 2. `Spikes/naga-fx/`: `ggx.wgsl` (GGX D, Smith visibility, Schlick Fresnel, one function that
      combines them), `naga ggx.wgsl ggx.hlsl`, a `ggx.fx` shell that declares the effect parameters
      and a technique whose pixel shader calls the generated function, `fxc /T fx_5_0`. Verified:
      fxc exit 0; the fxc log and naga's HLSL are committed under the spike.
- [ ] 3. Maya 2026 loads `ggx.fx` on a sphere through `dx11Shader` and draws a specular highlight
      from one bound light; screenshot. Verified: `tools/maya_load_check.py` style log with
      techniques, and the PNG.
- [ ] 4. Verdict written into the spec's "spike" section: WGSL stays, or the core moves to Slang.
      Every later task assumes WGSL; if the verdict is Slang, this plan is rewritten before PR B.

## PR B: core skeleton, build and compile tests

- [ ] 5. `core/manifest.toml`, `core/constants.wgsl`, `core/interface.wgsl`, `core/lighting.wgsl`
      (`LightSource`, `FixedSlots16`, `LightBuffer` accessor), `core/environment.wgsl`
      (`EnvironmentIBL`, sampling with the E1 conventions), `core/gbuffer.wgsl` (ADR-002 layout
      encode and decode), `core/models.wgsl` (the dispatch switch with a placeholder model).
- [ ] 6. `tools/build_shaders.py`: stitch by manifest, naga validate, emit HLSL and GLSL into
      `hosts/*/generated/`, fxc and dxc validation, name-collision check. `tests/compile/` runs it.
      Verified: passes locally; CI workflow added with the Rust and SDK steps.
- [ ] 7. `hogshade/core_constants.py` mirrors `constants.wgsl`; a test parses the WGSL and compares.

## PR C: the GPU test harness and the BRDF toolbox

- [ ] 8. `wgpu` as the `gpu` extra; `tests/core/conftest.py` acquires an adapter or skips.
- [ ] 9. `core/brdf.wgsl`: GGX D, height-correlated Smith visibility, Schlick and F82-tint Fresnel,
      Lambert and Burley diffuse; `hogshade/reference/brdf.py` NumPy twins. Verified: compute-shader
      comparison on a grid within 1e-5; run recorded in `Docs/verification/`.
- [ ] 10. `core/lighting.wgsl` test: 16 slots equal 16 single calls. `core/gbuffer.wgsl` test:
      round trip within quantisation.

## PR D: the legacy v2 port

- [ ] 11. `core/models/legacy_v2.wgsl`: `inputs()` and `evaluate()` from `V2_uv0bn-pbs_IBLenv.fx`
      and `pbr.sif`, function by function, with the four deviations from the spec in the header.
      `hogshade/reference/legacy_v2.py` twin. Verified: compute comparison on a set of inputs and one
      light within 1e-4; furnace within 1 percent.
- [ ] 12. The 33 debug views as `debug` output; a test that every mode index yields a finite value.

## PR E: the wgpu host

- [ ] 13. `hosts/wgpu/lit_mesh.wgsl`, `gbuffer_fill.wgsl`, `deferred_light.wgsl` over the stitched
      core; naga-validated in `tests/compile/`.
- [ ] 14. `tools/wgpu_viewport.py`: shader ball (derkreature, glTF), legacy v2 model, studio IBL from
      `content/ibl`, one directional light; writes `Docs/verification/wgpu-v2-studio.png`. Verified:
      the PNG shows a lit ball with a specular reflection of the studio.

## PR F: the Maya host and the modern HLSL

- [ ] 15. `hosts/hlsl/hogshade_core.hlsl`: naga's SM 6 output, formatted, dxc-validated, README of
      bindings.
- [ ] 16. `hosts/maya_dx11/hogshade.fx`: parameters and annotations for the legacy v2 parameter set,
      16 light slots, textures and samplers with unbound flags, techniques, POM kept in the shell
      (marked), a call into `hogshade_core.hlsl`. fxc in `tests/compile/`.
- [ ] 17. `tools/maya_ibl_check.py` pointed at `hogshade.fx`: lit ball, specular visible, both cube
      slots decoded; screenshot and log committed. This replaces E1's partial task 11.
- [ ] 18. Legacy v1 port (`core/models/legacy_v1.wgsl`) with its own reference and tests; selectable
      in both hosts.

## Close

- [ ] 19. Design doc: the deviations list; `Docs/README.md` status rows; roadmap C2 ticked; README
      "Status" updated to phase 2 done; VERSION to `0.2.0`.
