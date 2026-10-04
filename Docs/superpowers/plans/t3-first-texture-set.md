# T3 plan: the first texture set, and the host that shows it

**Status:** Proposed. Drafted 2026-10-04 with the spec; built after the owner answers the spec's first question
(the host half) and approves. Test-first: each task's test lands with it; the Maya probe is task 1 because its
answer decides what the committed runtime sets carry.

Spec: [../specs/t3-first-texture-set.md](../specs/t3-first-texture-set.md).

## Tasks

- [ ] 1. **The Maya DDS probe** (`hogshade.jobs.maya_texture_check` in its first form): on the GUI Maya worker,
      connect T2's proof set (`cobblestone_floor_04`, cooked outside the repository: BC7 sRGB, BC5, BC4,
      `R16_UNORM`) to the shell's map attributes and log what Maya decoded; repeat with the same set cooked
      `--no-compress`. Verify: `check.log` under `verification/maya-2026/textures/probe/` names each format
      and whether it loaded; the decision (block-compressed or uncompressed for Maya) recorded in the spec.
- [ ] 2. **The sets fetched and named**: four Poly Haven sets at 2K as PNG (8-bit colour, roughness, AO,
      metalness; 16-bit normal and height) renamed to the grammar under their families, the grid tile from the
      legacy repository renamed per the spec's table under `content/textures/grid/`, a `LICENSE.md` per set on
      the IBL template, a sidecar per map (`normal_convention` on every `_N`, provenance). Verify:
      `uv run tools/check_content.py` clean; the LFS attributes take every PNG (`git lfs ls-files`).
- [ ] 3. **The sets cooked and committed**: `uv run tools/cook_textures.py cook <set>` per set with the
      encoder, `cooked/` committed (DDS in LFS, the manifest and provenance in plain git); `separate` run on
      `brick_wall_001` for a second gallery pair. Verify: a second cook is byte-identical except
      `provenance.json`; the manifests' input hashes match the committed PNGs.
- [ ] 4. **The documents**: four standard documents binding their sets, `title`, `doc`, `provenance`; the
      library index regenerated; the roster coverage test gains the texture-parameter rows. Verify:
      `tests/material/test_library.py`; `generate_material_ui.py --check` clean.
- [ ] 5. **`hogshade.material.runtime.runtime_textures`** and `check_content.py`'s **content-runtime** rule.
      Verify: `tests/material/test_runtime.py` on the cook tests' brick fixture (every channel home, the
      `_ORM` channels, the packed alpha, height's format, the error without a manifest);
      `tests/test_check_content.py` with and without a manifest, a map the cook did not write, mismatched
      hashes, pointers logged as unverified.
- [ ] 6. **The Maya shell's material half reads the runtime set**: the host map's `packed` entry kind and the
      generated `ormMap` sampler (roughness `.g`, metalness `.b`, AO `.r`), the two-channel normal
      reconstruction in the core's `<model>_inputs` with `normalMapChannels`, its NumPy twin and GPU test;
      `build_shaders.py --check` current. Verify: `tests/core/` green; the untextured shader-ball picture
      unchanged (the S2 gate, a Maya job run); `generate_material_ui.py --check` clean.
- [ ] 7. **The Maya texture check job in full**: one run per set (the grid tile from an in-memory document),
      `main.png` and the debug views under `verification/maya-2026/textures/<set>/`, `check.log` with every
      connection; registered in `JOB_MODULES`; the gallery section "The first texture set" with a row per set
      and the `brick_wall_001` separation pair. Verify: `tests/jobs/`; `generate_gallery.py --check`; the
      pictures read by a human and the reading stated in the PR.
- [ ] 8. **Docs**: README's cook commands name `brick_wall_001`; `tools/README.md`, `tools/bats/README.md`,
      the knowledge file (the job); the content standard's sources paragraph names the five sets; the
      glossary if a word changes; this plan ticked with its table; the spec's amendments; the board (T3 to
      Now, then struck); the handoff; the journal. Verify: `check_docs.py` clean; the README read as a
      newcomer with a fresh LFS clone.

## Verification

| Task | Ran |
| --- | --- |
| | |

Totals: filled when the build lands.
