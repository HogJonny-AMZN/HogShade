# T4 tier 1 plan: the procedural set

**Status:** Accepted (owner, 2026-10-04: "Go with the recommendations"). Built the same day on
`feat/t4-synthetic-set` (#68), every task ticked. Test-first where a test could come first: each task's test lands
with it; the GPU tests run on the owner's machine and are skipped on CI, which the PR states.

Spec: [../specs/t4-procedural-set.md](../specs/t4-procedural-set.md).

## Tasks

- [x] 1. **The generator** (`hogshade/testdata/synthetic.py`, `tools/gen_synthetic_textures.py`): a map for every
      suffix of the table plus the `_BC_blue` variant, a legend strip, `generate`, `render_map`, `known_points`,
      `contact_sheet`; sidecars with provenance, the normal convention and the cutout's `pack`; the licence. Verify:
      deterministic bytes, every suffix covered, the arrows point along +U and +V, the named points hold the values
      worked out by hand (the bands, the checker, the tilts, the ramps), a size the layout does not support refused.
- [x] 2. **The set under content** (`content/textures/synthetic/`, 512): generated, then cooked `--compress` with
      the cook's default `individual_outputs`. Verify: `check_content.py` clean (including `content-runtime`), the
      manifest records the carriers and every individual copy.
- [x] 3. **The cook round trip** (`tests/testdata/test_synthetic.py`): an uncompressed cook in a scratch directory;
      every known point reads back exactly through `dds2d.read_2d` (the `_ORM` channels, the individual copies, the
      cutout in the colour alpha, the 16-bit height); the document binds every map; the committed set resolves every
      parameter to its carrier or its own file and the regenerated PNGs are the committed bytes.
- [x] 4. **The host proof** (`tests/host/test_wgpu_host.py`, GPU): the vertex probe (a vertex seen, by the depth
      buffer, off a tile seam, on a flat part of the map) reads the roughness bands, the metalness checker, the AO
      and the colour patches within 0.05 on 95 percent or more, and the normal view's green and red conventions with
      their flipped controls; `Frames.depth` exposed. Verify: the probe fails with V flipped.
- [x] 5. **The proof pictures**: the contact sheet of every map, the synthetic row of `texture_matrix.py`, its
      normal debug view, the gallery's pictures and matrix row. The Maya capture waits for the orchestrator's Maya
      worker (a documented gap, not a skipped task: the job exists and takes `set_dir=content/textures/synthetic`).
- [x] 6. **Docs**: the spec accepted with *What the build found*, this plan, the board (T4's tier-1 status, the
      Marmoset worker note, the shader-ball variant), the docs map, the README, the handoff, the journal.
      Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | `tests/testdata/test_synthetic.py` (13): suffix coverage and the variant; determinism and the files reading back as the arrays; the sidecars; unsupported sizes; every strip labelled; the contact sheet; the arrows' orientation; the named points against values worked out by hand |
| 2 | `tools/check_content.py` clean on 45 source textures; the manifest's 16 records (the carriers, the individual `_AO`, `_R`, `_M` and `_O`) |
| 3 | the cook round trip, the document and the committed-set resolution tests in the same file |
| 4 | five GPU tests on the owner's machine: four parametrised map views (98 to 100 percent agreement), the normal conventions (as authored 66 and 85 percent, flipped 0); the flipped-V control run once, by hand: metalness under 1 percent, colour 60 |
| 5 | `generate_gallery.py --check` clean; the matrix row rendered |
| 6 | `check_docs.py` clean |

Totals: the full suite green on the owner's machine (GPU included); CI skips the GPU tests.
