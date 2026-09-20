# E1 spec: the IBL cook

Date: 2026-09-20. Track E (parity and pipeline), first item. Design:
[../design/2026-09-20-wysiwyg-blindspots.md](../design/2026-09-20-wysiwyg-blindspots.md) finding 2,
and the roadmap's "no real-time host convolves its own". Plan: [../plans/e1-ibl-cook.md](../plans/e1-ibl-cook.md).

## Deliverable

One tool in this repo turns a source HDR environment into the exact prefiltered data every
real-time host loads, records how it did it, and can be run by a person, by CI, or by
Job_Orchestrator as a `hogshade.jobs` job. Two environments ship cooked: a neutral studio for
calibration and an outdoor sky for look-dev.

## Content layout

```text
content/
  ibl/
    README.md                            # what is here, how to add an environment, how to cook
    brdf_lut.dds                         # split-sum BRDF LUT, environment-independent, cooked once
    studio_small_09/                     # calibration environment (Poly Haven, CC0)
      LICENSE.md                         # source URL, author, licence, fetch date, 8K master location
      source_4k.exr                      # 4096x2048 equirect, linear, LFS; the reproducible source
      preview.png                        # tonemapped equirect for GitHub, not LFS
      cooked/
        manifest.json                    # tool version, git hash, every parameter, source sha256
        specular.dds                     # RGBA16F cube, 256 base, GGX-prefiltered mips (256 base now; a 4K source supports 512 later)
        irradiance.dds                   # RGBA16F cube, 32
        irradiance_sh9.json              # nine RGB SH coefficients, for hosts that want constants
    citrus_orchard_road_puresky/         # look-dev environment, same layout
```

The 8K masters stay outside the repo. `source_4k.exr` is made from them by the tool's `condition`
step (box downsample, no tonemapping, no exposure change) and is what every cook starts from, so
a cook is reproducible from the repo alone.

## The tool: `tools/cook_ibl.py`

Python, NumPy, the `OpenEXR` package for reading and writing EXR, a small DDS writer of our own
(DX10 header, `DXGI_FORMAT_R16G16B16A16_FLOAT`, cube with mips). No other dependencies in the
first version. Subcommands:

| Subcommand | Does |
| --- | --- |
| `condition <8k.exr> <out_4k.exr>` | Box-filter 2x2 downsample to 4096x2048, writes linear half-float EXR |
| `cook <env dir>` | Reads `source_4k.exr`, writes everything under `cooked/` and `preview.png` |
| `lut <out.dds>` | Cooks `brdf_lut.dds` |
| `furnace` | Cooks a uniform white environment and asserts every mip of every output is white within 1 percent |

### Mathematics, fixed here so hosts agree

- **Cube from equirect:** for each cube texel, the direction through its centre, sampled from the
  equirect with bilinear filtering. Face order and orientation follow DirectX (+X, -X, +Y, -Y, +Z,
  -Z), Y up, and the equirect's centre column is -Z. The design doc's light-rig description states
  the same convention so Maya and wgpu agree on where the sun is.
- **Specular prefilter:** GGX importance sampling with the split-sum approximation, N = V = R.
  Mip `m` of `M` levels has roughness `m / (M - 1)`; base 256 gives 9 levels. 1024 samples per
  texel, with the "sample from a lower mip of the source" trick to suppress fireflies. Roughness
  to mip mapping is linear, and the shader uses the same mapping; the manifest records it.
- **Irradiance:** cosine-weighted hemisphere convolution to a 32 cube, and projected to SH L2
  (nine RGB coefficients) with the standard Ramamoorthi and Hanrahan weights.
- **BRDF LUT:** 256x256, x is NdotV, y is roughness, RG are scale and bias; GGX with
  height-correlated Smith visibility, 1024 samples. Environment-independent.
- **No exposure or tonemapping anywhere.** Outputs are scene-linear radiance in the source's units.
  Display is the host's job through the shared OCIO config.

### Manifest

`cooked/manifest.json` records: tool version, HogShade git hash, source file sha256, cube size,
mip count, sample counts, roughness-to-mip mapping, face convention, wall time, and the machine.
A cook with the same inputs and version produces byte-identical outputs; CI checks this on the
studio environment.

### Job_Orchestrator

`hogshade/jobs/cook_ibl.py` wraps the tool as a MODULE-mode job with a manifest an agent can read:
name, description, parameters (environment directory, cube size, samples), worker type
(Python), inputs and outputs. Registration with the orchestrator's tool registry is that repo's
mechanism; this repo ships the job and the manifest.

## Acceptance gate

- `furnace` passes: a white environment cooks to white at every mip of `specular.dds`, in
  `irradiance.dds`, and in the SH9 constant term.
- Both shipped environments cook from `source_4k.exr` with no manual step; re-cooking on CI
  reproduces the committed outputs byte for byte.
- Maya 2026 loads `studio_small_09/cooked/specular.dds` and `irradiance.dds` into the legacy v2
  shader's environment slots and shades the shader ball; screenshot in `Docs/verification/`.
- `content/ibl/README.md` explains how to add a third environment in five steps.

## Out of scope

- The wgpu compute path for the prefilter. NumPy first; a 256 cube with 1024 samples is minutes,
  not hours, and correctness comes first. Recorded as a later item.
- BC6H compression. RGBA16F is larger and lossless; compression is a later size decision.
- Sky models, sun extraction, or any light-rig authoring. The environment is data.
