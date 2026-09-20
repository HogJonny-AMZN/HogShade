# content/ibl

The environment maps HogShade ships, and the rule that governs them: **no host convolves its own.**
Every real-time host loads the cooked data from here, produced by `tools/cook_ibl.py`, so Maya and
wgpu light a material from the same numbers.

| Environment | Role | Source |
| --- | --- | --- |
| `studio_small_09/` | Calibration. Neutral, no colour cast. The acceptance environment in the E1 spec | Poly Haven, CC0 |
| `citrus_orchard_road_puresky/` | Look-dev. Warm outdoor sky for screenshots | Poly Haven, CC0 |

Each folder holds a `LICENSE.md` (source URL, licence, fetch date), `source_4k.exr` (4096x2048
linear half-float, under Git LFS, made from the 8K master by the tool's `condition` step), and,
once E1 lands, `cooked/` with the prefiltered specular cube, the irradiance cube, the SH9
constants and a manifest. The 8K masters are not in the repository.

## Status

E1 in progress: the `condition` step exists and both sources are here. The cook itself, the BRDF
LUT and the cooked outputs follow in the E1 PR (`Docs/plans/e1-ibl-cook.md`).

## Adding an environment

1. Download the 8K EXR from Poly Haven, or another CC0 or otherwise redistributable source.
2. `uv run --no-project --with OpenEXR --with numpy tools/cook_ibl.py condition <8k.exr> content/ibl/<name>/source_4k.exr`
3. Write `content/ibl/<name>/LICENSE.md` on the pattern of the two here: URL, author, licence, date, role.
4. `tools/cook_ibl.py cook content/ibl/<name>` (once E1 lands) and commit `cooked/`.
5. Add a row to the table above.

LFS tracks `content/**/*.exr` and `content/**/*.dds`; previews and manifests are plain files.
