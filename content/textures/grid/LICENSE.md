# grid

- **Source:** the owner's own legacy test tiles, `testFiles/Assets/Models/shaderBall/grid_*.png` of
  https://github.com/HogJonny-AMZN/Maya-PBR-BRDF-VP2 (2015 to 2017)
- **Author:** Jonny Galloway (provenance `author`)
- **Licence:** the owner's; this repository's licence applies
- **Fetched:** 2026-10-04, copied from the legacy checkout and renamed to the content standard's grammar
  (the T3 spec's mapping table); 16-bit sources reduced to the suffix table's 8 bits except the height
- **Role in HogShade:** the calibration tile (the board's grid-tile row): registered cells for reading
  UVs, normal sign, roughness and metalness ramps, height and emission on any host. No document binds
  it in T3; the Maya texture check renders it from an in-memory document.
- **Not carried:** curvature, convexity, derivative, transmission (no standard parameter takes them),
  the legacy packed masks (the cook writes `_ORM`), the alpha variants (T4's showcase).
- **What is in this folder:** `T_grid_BC.png` (grid_color), `T_grid_BC_blue.png` (grid_blue_color),
  `T_grid_N.png` (grid_normal, OpenGL +Y), `T_grid_H.png` (grid_height, 8-bit source), `T_grid_R.png`,
  `T_grid_M.png`, `T_grid_AO.png` (grid_occlusion, the 16-bit one), `T_grid_E.png` (grid_emmissive),
  `T_grid_C.png` (grid_concavity as cavity); `cooked/` is written by `tools/cook_textures.py`.
