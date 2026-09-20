# Phase 2 plan: the WGSL core and its first two hosts

Spec: [../specs/phase-2-restructure.md](../specs/phase-2-restructure.md). Several PRs; the spike is its
own. Tick a task only when its verification ran.

## PR A: the spike

- [x] 1. Toolchain: Rust via `winget install Rustlang.Rustup`, then `cargo install naga-cli`; record
      versions in `Docs/verification/toolchain.md`. Verified 2026-09-20: naga 30.0.1, Rust 1.98.1.
- [x] 2. `Spikes/naga-fx/`: `ggx.wgsl` (GGX D, Smith visibility, Schlick Fresnel, one function that
      combines them, plus a function that samples a `texture_2d` through a `sampler` for the base
      colour and reads one light from a uniform struct), `naga --shader-model 50 ggx.wgsl ggx.hlsl`,
      a `ggx.fx` shell that declares the texture, sampler and light as Maya-annotated effect
      parameters and passes them into the generated functions from its pixel shader,
      `fxc /T fx_5_0`. Verified: fxc exit 0; the fxc log and naga's HLSL are committed under the
      spike. If naga's texture and sampler declarations cannot be fed from effect parameters, that
      is the spike's finding and the verdict is fail. Verified 2026-09-20: fxc exit 0 (`fxc.log`);
      the first attempt with bound globals produced naga's sampler heap in register spaces, the
      parameter-passing form produces plain `Texture2D`/`SamplerState` parameters (spike README).
- [x] 3. Maya 2026 loads `ggx.fx` on a sphere through `dx11Shader`, with a file node bound to the
      texture parameter and a scene light bound to the light slot, and draws the textured ball with
      a specular highlight; screenshot. Verified: `tools/maya_load_check.py` style log with
      techniques and the decoded texture size, and the PNG. Verified 2026-09-20: techniques `['Main']`,
      texture 256x256 decoded, two frames differ with the light rotated (`verification/`).
- [x] 4. Verdict written into the spec's "spike" section: WGSL stays, or the core moves to Slang.
      Every later task assumes WGSL; if the verdict is Slang, this plan is rewritten before PR B.
      Verdict 2026-09-20: WGSL stays.

## PR B: core skeleton, build and compile tests

- [ ] 5. `core/manifest.toml` (module order and the unprefixed-name exemption list),
      `core/constants.wgsl`, `core/interface.wgsl` (`ShadingInputs`, `SurfaceInputs`, `ShadingResult`,
      `LightSource`, `EnvironmentIBL`), `core/lighting.wgsl`
      (`LightSource`, `FixedSlots16`, `LightBuffer` accessor), `core/environment.wgsl`
      (`EnvironmentIBL`, sampling with the E1 conventions), `core/gbuffer.wgsl` (ADR-002 layout
      encode and decode), `core/models.wgsl` (the dispatch switch with a placeholder model).
- [ ] 6. `tools/build_shaders.py`: stitch by manifest, naga validate, emit shader-model 5 HLSL for
      the Maya shell and shader-model 6 HLSL for `hosts/hlsl/`, GLSL, into `hosts/*/generated/`; fxc
      on the SM5 output and dxc on the SM6 output; name-collision check with the exemption list. `tests/compile/` runs it.
      Verified: passes locally; CI workflow added with the Rust and SDK steps.
- [ ] 7. `hogshade/core_constants.py` mirrors `constants.wgsl`; a test parses the WGSL and compares.

## PR C: the GPU test harness and the BRDF toolbox

- [ ] 8. `wgpu` as the `gpu` extra; `tests/core/conftest.py` acquires an adapter or skips.
- [ ] 9. `core/brdf.wgsl`: GGX D, height-correlated Smith visibility, Schlick and F82-tint Fresnel,
      Lambert and Burley diffuse; `hogshade/reference/brdf.py` NumPy twins. Verified: compute-shader
      comparison on a grid within 1e-5; run recorded in `Docs/verification/`.
- [ ] 10. `core/lighting.wgsl` test: 16 slots equal 16 single calls. `core/gbuffer.wgsl` tests:
      `SurfaceInputs` round trip within the layout's quantisation, and forward-versus-deferred parity
      (evaluate on `ShadingInputs` built directly, against evaluate on encode, decode and
      reconstruct) within that same quantisation.

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
      bindings; `hosts/maya_dx11/generated/hogshade_core_sm5.hlsl`: the SM 5 output of the same
      build, fxc-validated.
- [ ] 16. `hosts/maya_dx11/hogshade.fx`: parameters and annotations for the legacy v2 parameter set,
      16 light slots, textures and samplers with unbound flags, techniques, POM kept in the shell
      (marked), a call into `hogshade_core_sm5.hlsl`. fxc in `tests/compile/`.
- [ ] 17. `tools/maya_ibl_check.py` pointed at `hogshade.fx`: lit ball, specular visible, both cube
      slots decoded; screenshot and log committed. This replaces E1's partial task 11.
- [ ] 18. Legacy v1 port (`core/models/legacy_v1.wgsl`) with its own reference and tests; selectable
      in both hosts.

## Close

- [ ] 19. Design doc: the deviations list; `Docs/README.md` status rows; roadmap C2 ticked; README
      "Status" updated to phase 2 done; VERSION to `0.2.0`.
