# citrus_orchard_road_puresky

- **Source:** https://polyhaven.com/a/citrus_orchard_road_puresky
- **Author:** as credited on the Poly Haven page above
- **Licence:** CC0 1.0 Universal (public domain dedication), Poly Haven's licence for all its assets:
  https://polyhaven.com/license
- **Fetched:** 2026-09-20, as the 8K EXR download
- **Role in HogShade:** the look-dev environment. Warm, directional outdoor sky; the one to use for
  screenshots and for judging a material, not for measuring one.
- **What is in this folder:** `source_4k.exr` is the 8K master box-downsampled 2x2 to 4096x2048 by
  `tools/cook_ibl.py condition`, linear half-float, no tonemapping or exposure change. The 8K master
  is not in the repository; the owner keeps it outside git. `cooked/` is produced from
  `source_4k.exr` by the same tool and is reproducible from this folder alone.
