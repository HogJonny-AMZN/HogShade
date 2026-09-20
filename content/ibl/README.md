# content/ibl

The environment maps HogShade ships, and the rule that governs them: **no host convolves its own.**
Every real-time host loads the cooked data from here, produced by `tools/cook_ibl.py`, so Maya and
wgpu light a material from the same numbers.

| Environment | Role | Source |
| --- | --- | --- |
| `studio_small_09/` | Calibration. Neutral, no colour cast. The acceptance environment in the E1 spec | Poly Haven, CC0 |
| `citrus_orchard_road_puresky/` | Look-dev. Warm outdoor sky for screenshots | Poly Haven, CC0 |

## What is in an environment folder

| File | What | LFS |
| --- | --- | --- |
| `LICENSE.md` | Source URL, licence, fetch date, where the 8K master lives (outside the repo) | no |
| `source_4k.exr` | 4096x2048 linear half-float equirect, box-downsampled from the 8K master by `condition`. The reproducible source | yes |
| `preview.png` | Tonemapped equirect so the folder reads on GitHub. Display only | no |
| `cooked/specular.dds` | GGX-prefiltered RGBA16F cube, 256 base, 9 mips, roughness linear in mip (`mip / 8`) | yes |
| `cooked/irradiance.dds` | Cosine-convolved radiance over pi (E/pi), RGBA16F 32 cube. Multiply by albedo directly | yes |
| `cooked/irradiance_sh9.json` | Radiance SH L2 coefficients, nine RGB rows, with the reconstruction formula in the file | no |
| `cooked/manifest.json` | Deterministic: parameters, face convention, roughness-to-mip rule, sha256 of the source and every output | no |
| `cooked/provenance.json` | Volatile: when, on what machine, which git hash, which Python and NumPy. Excluded from reproducibility checks | no |

`brdf_lut.dds` at this level is the split-sum BRDF lookup table, environment-independent, cooked
once: 256x256 RGBA16F, x is NdotV, y is roughness, R is the scale on F0 and G the bias.

Conventions every host must match are in `hogshade/ibl/cubemap.py` and the E1 spec: Direct3D cube
faces (+X, -X, +Y, -Y, +Z, -Z), Y up, the equirect's centre column is -Z and +X is three quarters
of the way across. A host that disagrees puts the sun in the wrong place; the plan's marker test is
how the cook itself is kept honest.

## Status

The two `source_4k.exr` files and the cooked `.dds` files exist locally and are committed on a local
branch, but **cannot be pushed until the repository leaves the fork network**: GitHub refuses LFS
uploads into a public fork. Everything else (licences, manifests, SH9, previews, the tool, the tests)
is in the tree. A fresh clone can run the tool but has nothing to cook until then.

## Using the cubes in the legacy v2 Maya shader

The legacy shader was written for RGBM-encoded 8-bit cubes: it decodes `rgb.bgr * a * envLightingExp`
with `envLightingExp` defaulting to 5 and then applies a 2.23 gamma. The cooked cubes are linear
fp16 with alpha 1, so set `envLightingExp` to 1 and `linearSpaceLighting` off. Bind a base colour,
normal and masks map as well; unbound 2D maps sample black and the shader multiplies them in. The
specular cube slot renders black in Maya 2026 even with data that works in the diffuse slot; see
`Docs/plans/e1-ibl-cook.md` task 11. The phase 2 port removes all of this.

## Cooking

```text
uv sync --all-extras
uv run tools/cook_ibl.py condition <8k.exr> content/ibl/<name>/source_4k.exr   # once per environment
uv run tools/cook_ibl.py cook content/ibl/<name>                                # about 75 s
uv run tools/cook_ibl.py lut content/ibl/brdf_lut.dds                           # once per repo
uv run tools/cook_ibl.py furnace                                                # the energy check
uv run pytest tests/ibl                                                         # the rest of the checks
```

The same cook is a Job_Orchestrator job: `module_path = hogshade.jobs.cook_ibl`, `entry_point =
main`, parameters `env_dir` (and optionally `master_exr`, `base`, `samples`, `irradiance_size`).
`hogshade.jobs.manifest()` returns the agent-readable description the MCP tools list.

## Adding an environment

1. Download the 8K EXR from Poly Haven, or another CC0 or otherwise redistributable source.
2. `uv run tools/cook_ibl.py condition <8k.exr> content/ibl/<name>/source_4k.exr`
3. Write `content/ibl/<name>/LICENSE.md` on the pattern of the two here: URL, author, licence, date, role.
4. `uv run tools/cook_ibl.py cook content/ibl/<name>` and commit `cooked/` and `preview.png`.
5. Add a row to the table at the top.

LFS tracks `content/**/*.exr` and `content/**/*.dds`; previews, manifests and SH9 are plain files.
