# T3 plan: the first texture set, and the host that shows it

**Status:** Accepted. Drafted 2026-10-04 with the spec (#57); the owner took the recommendations the same day; built
on `feat/t3-first-texture-set` the same day, every task verified in the table at the end. Test-first: each task's test lands with it; the Maya probe is task 1 because its
answer decides what the committed runtime sets carry.

Spec: [../specs/t3-first-texture-set.md](../specs/t3-first-texture-set.md).

## Tasks

- [x] 1. **The Maya DDS probe** (`hogshade.jobs.maya_texture_check` in its first form): on the GUI Maya worker,
      connect two scratch sets cooked outside the repository, the grid tile as fetched (BC7 sRGB, BC7, BC5, BC4
      from its 8-bit `_H` and `_C`) and `cobblestone_floor_04` without its `pack` field (a standalone 16-bit
      `_H`, `R16_UNORM`), each once with the encoder and once `--no-compress`, to the shell's map attributes and
      log what Maya decoded, and the menu-bar state (Job_Orchestrator issue 72). Verify: `check.log` under
      `verification/maya-2026/textures/probe/` names each format and whether it loaded; the decision
      (block-compressed or uncompressed for Maya) recorded in the spec and carried as the explicit flag.
- [x] 2. **The sets fetched and named**: four Poly Haven sets at 2K as PNG (8-bit colour, roughness, AO,
      metalness and normal; 16-bit height, the content table's depths) renamed to the grammar under their families, the grid tile from the
      legacy repository renamed per the spec's table under `content/textures/grid/`, a `LICENSE.md` per set on
      the IBL template, a sidecar per map (`normal_convention` on every `_N`, provenance). Verify:
      `uv run tools/check_content.py` clean; the LFS attributes take every PNG (`git lfs ls-files`).
- [x] 3. **The sets cooked and committed**: `uv run tools/cook_textures.py cook <set> --compress` (or
      `--no-compress`, the probe's choice, never the automatic default) per set, `cooked/` committed (DDS in
      LFS, the manifest and provenance in plain git); `separate` with the same flag on `brick_wall_001` for a
      second gallery pair. Verify: a second cook with the same flag is byte-identical except `provenance.json`;
      the manifests' input hashes match the committed PNGs; the `compression` record says which.
- [x] 4. **The documents**: four standard documents binding their sets, `title`, `doc`, `provenance`;
      `blue_metal_plate` binds `base_metalness` with factor 1.0 and its texture; the library index regenerated;
      the roster coverage test lists each textured parameter (normal, AO, height covered; cavity deferred and
      said so). Verify: `tests/material/test_library.py`; `generate_material_ui.py --check` clean.
- [x] 5. **`hogshade.material.runtime.runtime_textures`** (every home from the manifest; height standalone or
      in a carrier's alpha) and `check_content.py`'s **content-runtime** rule over both content roots.
      Verify: `tests/material/test_runtime.py` on the cook tests' brick fixture (every channel home, the
      `_ORM` channels, the height in `_ORM`'s alpha, a standalone height's format, the error without a
      manifest); `tests/test_check_content.py` with and without a manifest, a map the cook did not write, a
      height in no entry, mismatched hashes, pointers logged as unverified, the grid set included.
- [x] 5b. **The Maya binder**: `convert(resolved, "hogshade-legacy-v2")` carrying textures, then
      `bind(converted, "maya_dx11")` returning attribute values, `use<Map>` flags and texture slots with the
      runtime files. Verify: `tests/material/test_binding.py` (a textured document, an untextured one equal to
      the S2 gate's values, `Unbound` reasons).
- [x] 6. **The Maya shell's material half reads the runtime set**: the host map's `packed` entry kind and the
      generated `ormMap` sampler (roughness `.g`, metalness `.b`, AO `.r`); no core change (v2 derives Z), a
      GPU test case for `legacy_v2_normal_ts` with Z sampled as 0; `build_shaders.py --check` current. Verify:
      `tests/core/` green; the untextured shader-ball picture unchanged (the S2 gate, a Maya job run);
      `generate_material_ui.py --check` clean.
- [x] 7. **The Maya texture check job in full**: one run per set (the grid tile from an in-memory document),
      `main.png` and the debug views under `verification/maya-2026/textures/<set>/`, `check.log` with every
      connection; registered in `JOB_MODULES`; the gallery section "The first texture set" with a row per set
      and the `brick_wall_001` separation pair. Verify: `tests/jobs/`; `generate_gallery.py --check`; the
      pictures read by a human and the reading stated in the PR.
- [x] 8. **Docs**: README's cook commands name `brick_wall_001` with the probe's compression flag; `tools/README.md`, `tools/bats/README.md`,
      the knowledge file (the job); the content standard's sources paragraph names the five sets; the
      glossary if a word changes; this plan ticked with its table; the spec's amendments; the board (T3 to
      Now, then struck); the handoff; the journal. Verify: `check_docs.py` clean; the README read as a
      newcomer with a fresh LFS clone.

## Verification

| Task | Ran |
| --- | --- |
| 1 | The probe: four runs on the GUI worker (`verification/maya-2026/textures/probe/{grid,cobblestone_floor_04}-{compressed,uncompressed}/check.log`), the grid tile as fetched and `cobblestone_floor_04` without its `pack` field, with the encoder and `--no-compress`: BC7 sRGB, BC7, BC5, BC4, `R16_UNORM`, `R8_UNORM`, `R8G8B8A8_UNORM[_SRGB]`, `R8G8_UNORM` all decoded at full size (`loaded size (1024, 1024)` / `(2048, 2048)`); the menu bar 63 entries. Decision: `--compress` for every committed set |
| 2 | `tools/fetch_polyhaven.py` for `cobblestone_floor_04`, `brick_wall_001`, `brown_planks_03`, `metal_plate` at 2K (md5 against the API; a 16-bit colour, grey-alpha masks and 16-bit normals brought to the table's form); the grid tile from the legacy checkout on the spec's table (occlusion 16-bit over ambOcc, one step apart); `check_content.py` clean on 30 source textures; 38 LFS files |
| 3 | `cook ... --compress` per set (BC7 basic, BC5, BC4, `R16_UNORM`); `separate brick_wall_001 --compress`, pictures at 512; a re-cook of `brick_wall_001` byte-identical except `provenance.json`; the manifests' `compression` records `ispc_texcomp` |
| 4 | Four documents, the metalness factor 1.0 with the map; index regenerated (26 documents); `texture_coverage`: normal, AO, height, colour, roughness in four, metalness in one, cavity deferred (test) |
| 5 | `hogshade.material.runtime` (`test_material_runtime.py`: every home, the ORM channels, the height in the ORM's alpha and standalone with its format, the errors); `content-runtime` (`test_check_content.py`: a cooked corpus passes, a missing record, a changed input, an empty and an unreadable manifest, a pointer logged) |
| 5b | `bind(resolved, "maya_dx11")` after `convert`: attributes, flags, `maya_map_slots`, refusals; an untextured document binds the flags off (`test_material_runtime.py`); `document_for_set` (`test_material_sets.py`) |
| 6 | The host map's `packed` section, `ormMap` generated after the separate maps, the checker's findings, `maya_packed_slots`, the shell sampling `orm.g/.b/.r` (`test_material_packed.py`); `generate_material_ui.py --check` clean. The S2 gate: master's shell and the regenerated one, untextured, in one Maya session: 0 differing pixels on `main.png` and the three debug views (`verification/maya-2026/ibl-check/gate/{master,ormmap}/`) |
| 7 | `hogshade.jobs.maya_texture_check` registered (`test_material_sets.py`); five runs, every one `RESULT: OK`, the ORM connected once to `ormMap` with the separate flags off, formats decoded 5/5, 5/5, 5/5, 6/6, 8/8; pictures under `verification/maya-2026/textures/<set>/`, the gallery section "The first texture set" and the brick wall's separation rows; read by a human: the cobbles, the bricks and the planks legible with their relief, the grid's cells aligned, the metal plate dark under the studio light with its metalness view showing the plate's pattern |
| 8 | README (the cook commands name `brick_wall_001` with `--compress`, the fetch tool, the Maya check), `tools/README.md`, `tools/bats/README.md`, the knowledge file (the job and the resident-worker rule), the standard's sources, the spec's amendments, failure modes 16, this plan, the board, the handoff, the journal; `check_docs.py` clean |

Totals: `uv run pytest -o addopts= -q` 595 passed (103 in `tests/texture_cook/`, 30 new for T3 across `tests/material/` and `tests/test_check_content.py`).
