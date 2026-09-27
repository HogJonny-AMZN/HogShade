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
      a specular highlight; screenshot. Verified: `tools/maya/load_check.py` style log with
      techniques and the decoded texture size, and the PNG. Verified 2026-09-20: techniques `['Main']`,
      texture 256x256 decoded, two frames differ with the light rotated (`verification/`).
- [x] 4. Verdict written into the spec's "spike" section: WGSL stays, or the core moves to Slang.
      Every later task assumes WGSL; if the verdict is Slang, this plan is rewritten before PR B.
      Verdict 2026-09-20: WGSL stays.

## PR B: core skeleton, build and compile tests

- [x] 5. `core/manifest.toml` (module order and the unprefixed-name exemption list),
      `core/constants.wgsl`, `core/interface.wgsl` (`ShadingInputs`, `SurfaceInputs`, `ShadingResult`,
      `LightSource`, `EnvironmentIBL`), `core/lighting.wgsl`
      (`LightSource`, `FixedSlots16`, `LightBuffer` accessor), `core/environment.wgsl`
      (`EnvironmentIBL`, sampling with the E1 conventions), `core/gbuffer.wgsl` (ADR-002 layout
      encode and decode), `core/models.wgsl` (the dispatch switch with a placeholder model).
      Done 2026-09-20; the placeholder is a real Lambert model (tier 0). One adjustment from the
      spike: models expose `<model>_evaluate_light` and `<model>_evaluate_env`; the fixed-slot loop
      is `models_evaluate_slots` in the core and an engine loops its own buffer calling the per-light
      function, since WGSL has no function pointers for an accessor.
- [x] 6. `tools/build_shaders.py`: stitch by manifest, naga validate, emit shader-model 5 HLSL for
      the Maya shell and shader-model 6 HLSL for `hosts/hlsl/`, GLSL, into `hosts/*/generated/`; fxc
      on the SM5 output and dxc on the SM6 output; name-collision check with the exemption list. `tests/compile/` runs it.
      Verified 2026-09-20: naga validates, both HLSL targets compile (fxc ps_5_0, dxc ps_6_0), GLSL
      emitted, `--check` reports the committed artifacts current; `.github/workflows/tests.yml` on
      windows-latest with Rust, cached naga-cli, uv, ruff, the check, and pytest.
- [x] 7. `hogshade/core_constants.py` mirrors `constants.wgsl`; a test parses the WGSL and compares.
      Verified 2026-09-20: both directions (every Python constant matches; every WGSL constant is mirrored).

## PR C: the GPU test harness and the BRDF toolbox

- [x] 8. `wgpu` as the `gpu` extra; `tests/core/conftest.py` acquires an adapter or skips. Done
      2026-09-21: wgpu-py 0.32 on the RTX 5090 through Vulkan; `tests/core/gpu_harness.py` stitches the
      core in front of a per-test compute kernel and runs one thread per test vector.
- [x] 9. `core/brdf.wgsl`: GGX D, height-correlated Smith visibility, Schlick and F82-tint Fresnel,
      Lambert and Burley diffuse; `hogshade/reference/brdf.py` NumPy twins. Verified: compute-shader
      comparison on a grid within 1e-5; run recorded in `Docs/verification/`. Verified 2026-09-21:
      GGX D, height-correlated Smith, Schlick, F82-tint, Lambert, Burley and the GGX composite match
      the NumPy references (2e-5 relative on the grid for alpha >= 0.1; GGX D below that is limited
      by float32 cancellation at the peak and is held to 1e-2, with the reason in the test). The GPU
      run is recorded in `Docs/verification/core/gpu-tests.log` (machine, adapter, per-test result).
- [x] 10. `core/lighting.wgsl` test: 16 slots equal 16 single calls. `core/gbuffer.wgsl` tests:
      `SurfaceInputs` round trip within the layout's quantisation, and forward-versus-deferred parity
      (evaluate on `ShadingInputs` built directly, against evaluate on encode, decode and
      reconstruct) within that same quantisation. Verified 2026-09-21: 16 slots equal 16 single calls
      to 1e-6; incident geometry (directional, windowed inverse-square point, spot cone) matches the
      reference; forward and deferred Lambert agree to 1e-5 un-quantised; with ADR-002's 8-bit albedo
      and AO and fp16 octahedral normal the worst normal error is 0.11 degrees.

## PR D: the legacy v2 port

- [x] 11. `core/models/legacy_v2.wgsl`: `inputs()` and `evaluate()` from `V2_uv0bn-pbs_IBLenv.fx`
      and `pbr.sif`, function by function, with the four deviations from the spec in the header.
      `hogshade/reference/legacy_v2.py` twin. Verified: compute comparison on a set of inputs and one
      light within 1e-4; furnace within 1 percent. Verified 2026-09-25: `legacy_v2_inputs` (2048
      random materials, samples and tangent frames), `legacy_v2_evaluate_light` (2048 inputs with a
      directional, point or spot light), `legacy_v2_evaluate_env` (all three hemisphere modes) and
      `models_shade` through the dispatcher match the NumPy twin within 1e-4 relative. The furnace
      returns 1 + (F0 * lut.x + lut.y) exactly as predicted (v2 has no diffuse energy conservation):
      the test asserts that value; the spec's furnace line is amended. Six deviations, not four, in
      the header and the design doc. Interface change: `EnvironmentSamples` replaces the bare
      irradiance argument and `ShadingInputs.specular_weight` is added (spec updated). The toolbox
      gains `brdf_g1_schlick_ggx` and `brdf_vis_hable` (Hable's G1V product) with references.
- [x] 12. The 33 debug views as `debug` output; a test that every mode index yields a finite value.
      Verified 2026-09-25: modes 0 to 32 through `legacy_v2_debug` are finite and equal the reference
      on 128 random inputs each; the twelve texel-and-UV modes (`legacy_v2_debug_is_inputs_mode`)
      are also computed exactly by `legacy_v2_debug_inputs` for forward hosts and match the
      reference. `Docs/verification/core/gpu-tests.log` refreshed: 69 core tests on the RTX 5090
      (the host is named BIGHOG-4090RTX after its previous card; the log's adapter line is the
      truth). Copilot on PR D: the lookup coordinates moved into the model (`models_env_lookup`,
      tested); FXC on the CI runner's DX12 adapter rejected two multi-return switch cases in
      `legacy_v2_debug`, now single `select` returns, so the GPU tests run on CI too.

## PR E: the wgpu host

- [x] 13. `hosts/wgpu/lit_mesh.wgsl`, `gbuffer_fill.wgsl`, `deferred_light.wgsl` over the stitched
      core; naga-validated in `tests/compile/`. Done 2026-09-26: plus `common.wgsl` (the frame uniform,
      the environment bindings, the host's material and geometry builders, `host_shade`); the three
      stitched passes validate under naga in `tests/compile/` and compile on the RTX 5090 through
      Vulkan. The deferred pair renders into ADR-002's real formats (rgba8unorm-srgb, rgba16float,
      rgba8uint, rg11b10ufloat) so its cost is measured, not modelled. FXC finding (Copilot asked for a
      D3D12 check): the deferred pass failed under wgpu's D3D12 backend with FXC's "no storage type
      for block output", bisected to `switch (i.surface.model)` in `core/models.wgsl` when the
      selector comes from the uint G-buffer texture in a shader that also passes textures into
      functions; the dispatcher is an if-chain now and both backends render the pass.
- [x] 14. `tools/wgpu/viewport.py`: shader ball (derkreature, OBJ; the plan first said glTF), legacy v2 model, studio IBL from
      `content/ibl`, one directional light; writes `Docs/verification/wgpu/shader-ball/<env>/forward.png`. Verified:
      the PNG shows a lit ball with a specular reflection of the studio. Done 2026-09-26: the ball is
      the OBJ, not glTF (that repository ships OBJ and FBX; `content/shaderball/`, Unlicense, LFS),
      read by `hogshade.wgpu_host.load_obj`. `hogshade.wgpu_host.Renderer` draws both paths offscreen
      and reads them back; the tool writes the forward and deferred PNGs and prints their difference.
      Verified: `wgpu/shader-ball/studio_small_09/forward.png` (grey dielectric, roughness 0.2) shows the studio softbox in the
      cavity and on the rim; `wgpu/shader-ball/studio_small_09/metal/forward.png` (metal, roughness 0.15) mirrors the studio.
      Forward versus deferred over the ball, 1024 px: dielectric mean 0.005 and max 0.41 scene-linear
      (silhouette pixels); metal mean 0.06 with a max of 134 at the hottest highlight pixel, where
      the fp16 normal moves v2's unbounded grazing specular. `tests/host/test_wgpu_host.py` renders
      at 96 px and asserts coverage, a lit ball, path agreement and a non-zero specular debug view.

## PR F: the Maya host and the modern HLSL

- [x] 15. `hosts/hlsl/hogshade_core.hlsl`: naga's SM 6 output, formatted, dxc-validated, README of
      bindings; `hosts/maya_dx11/generated/hogshade_core_sm5.hlsl`: the SM 5 output of the same
      build, fxc-validated. Done 2026-09-26: both artifacts have been generated and validated by
      every build since PR B; `hosts/hlsl/README.md` documents that there is no binding layout
      (every resource is a function parameter), the functions a consumer calls, naga's renamed
      identifiers, and points at the Maya shell as the worked example.
- [x] 16. `hosts/maya_dx11/hogshade.fx`: parameters and annotations for the legacy v2 parameter set,
      16 light slots, textures and samplers with unbound flags, techniques, POM kept in the shell
      (marked), a call into `hogshade_core_sm5.hlsl`. fxc in `tests/compile/`. Done 2026-09-26: the
      shell keeps v2's parameter names; per-map "use" flags stand in for v2's sample-black test;
      the cube slots are plain (no `environment` semantic); sixteen `Object = "Light N"` slots come
      from one macro each with a per-slot shadow-map lookup, filled into `FixedSlots16_` with Maya's
      light types mapped (ambient off, decay ignored in favour of a per-slot range); the specular
      cube's mip count is read with `GetDimensions`; v2's parallax offset and simple self shadow are
      in the shell marked as such (the "stencil" self-shadow variant is not carried); no in-shader
      tone mapping, the output is scene-linear pre-multiplied. `tests/compile/` compiles it with
      `fxc /T fx_5_0 /D _MAYA_=1`: 14 seconds, the FXC canary's first reading. One naga rename bit:
      `specular_f0` is `specular_f0_` in the generated HLSL.
- [x] 17. `tools/maya/ibl_check.py` pointed at `hogshade.fx`: lit ball, specular visible, both cube
      slots decoded; screenshot and log committed. This replaces E1's partial task 11.
      **In progress 2026-09-26.** The shell compiles under fxc but Maya's dx11Shader lists no
      techniques for it, so Maya's own compile error is the next thing to read; the session helper
      now mirrors the Script Editor history to a file beside the log for that. Standalone
      `maya.exe -script` runs proved fragile (startup crashes, an idle instance left behind by a
      launcher bug, and a retry loop that killed a Maya the owner's orchestrator had started), so
      the check moves to a Job_Orchestrator (BATS) job on a resident Maya GUI worker; the `.mel`
      launcher stays for anyone without BATS. `tools/maya/_session.py` is shared by both paths.
      **Passed 2026-09-26** as the job `hogshade.jobs.maya_ibl_check` on the `hogshade_maya_gui`
      worker (PR #18): `TECHNIQUES: ['Main']` (effect load 14.4 s), both cubes decoded (256 and 32),
      the LUT decoded (256), `RESULT: OK`; `Docs/verification/maya-2026/ibl-check/studio_small_09/main.png`
      shows the lit grey dielectric with the key-light highlight and the studio reflection, and
      `debug-28.png` (the specular environment term) mirrors the studio in the ball. The compile
      failure of the first standalone runs was the string parameters carrying vertex semantics,
      removed in PR #15; nothing else changed in the shell. E1 task 11 is closed by this.
- [ ] 18. Legacy v1 port (`core/models/legacy_v1.wgsl`) with its own reference and tests; selectable
      in both hosts.

## Close

- [ ] 19. Design doc: the deviations list; `Docs/README.md` status rows; roadmap C2 ticked; README
      "Status" updated to phase 2 done; VERSION to `0.2.0`.
