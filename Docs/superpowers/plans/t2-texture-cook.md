# T2 plan: the texture cook

**Status:** Accepted. Built 2026-10-04 on `feat/t2-texture-cook` (one PR, stacked on #54); every task verified in
the table at the end; the local review ran before the PR opened.

Spec: [../specs/t2-texture-cook.md](../specs/t2-texture-cook.md). Test-first: each task's test lands with it.

## Tasks

- [x] 1. `hogshade/texture_cook/png.py` and `colour.py`: the PNG reader (8 and 16-bit, grey, grey-alpha, RGB,
      RGBA, the five filters None, Sub, Up, Average and Paeth; interlaced and palette refused) and the sRGB
      transfer. Verify: round trips through a test writer that emits every filter type, for grey, grey-alpha,
      RGB and RGBA at 8 and 16 bits; the refusals name their reason.
- [x] 2. `mips.py`, `normals.py`, `pack.py`, `height.py`, and `dds.write_2d`/`read_2d` for `R8`, `R8G8`,
      `R8G8B8A8[_SRGB]`, `R16_UNORM`, `R16_FLOAT`, `R32_FLOAT`, plus `write_2d_blocks` for BC7, BC5 and BC4 (the block pitch in the header). Verify: the
      linear-average mip test, the unit-length normal mips, the `directx-y` flip recorded, the ORM packing
      with the neutral fill, the `pack` sidecar field (alpha carriers; `SIDECAR_KEYS` gains it) with its findings,
      DDS round trips per uncompressed format with mips (`R16_FLOAT` and `R32_FLOAT` for height among them), a BC4
      block decoded by hand.
- [x] 3. `separate.py`: the wrap-padded Gaussian low-pass, the high-pass, the recombination error, the macro.
      Verify: both halves tile, `recon == source` away from clipping, the error fields are measured, the macro
      is the stated size.
- [x] 4. `cook.py` (`cook_set`), the manifest and provenance, the sidecars' derived fields, the T1 rules applied
      first, the encoder seam with `IspcEncoder` (the `textures` extra; BC4 from an R8 surface, BC5 from RG8) the
      default and `TexconvEncoder` optional, uncompressed when neither is present; `tools/cook_textures.py` with
      `cook` and `separate`.
      Verify: a scratch set cooks, byte-identical twice, the manifest's hashes match, the sidecars gain only
      derived fields, a set with a finding is refused, `check_content.py` passes on the cooked set.
- [x] 5. `hogshade/jobs/cook_textures.py`, registered in `hogshade.jobs.JOB_MODULES` (the registry `manifest()`
      enumerates; an unregistered module is invisible to BATS), and its test; `tools/bats/README.md` names the
      job. Verify: `hogshade.jobs.manifest()` lists it; the manifest's outputs match what the cook writes; a
      climbing `set_dir` is refused.
- [x] 6. Setup written down: the `textures` extra in `pyproject.toml`; `README.md` "Getting started" gains "The
      texture cook" (`uv sync --all-extras`, the encoder it brings, the one command, what lands under `cooked/`);
      `tools/README.md`; `tools/bats/README.md` and `Docs/knowledge/job-orchestrator.md` (the worker's venv carries
      the extra; the job's name); the cook's `WARNING` with the `uv sync` command when the encoder is absent and
      `--check-setup`. Verify: `test_setup.py`; a fresh `uv sync --all-extras` on this machine imports
      `ispc_texcomp`; the README section read as a newcomer.
- [x] 7. On the owner's machine: a Poly Haven set outside the repository cooked and separated; the
      separation picture pair under `verification/wgpu/textures/` and its gallery row. Verify: the pair
      recombines to the source by eye and by the manifest's error; the PR says what was seen.
- [x] 8. Docs: this plan ticked with its table; the spec's amendments; the standard's runtime column
      ("or uncompressed until the encoder is present") and its cook paragraph; the board (T2 to Now, then
      struck); the glossary if a word changes; the handoff; the journal. Verify: `check_docs.py` clean.

## Verification

| Task | Ran |
| --- | --- |
| 1 | `png.py`: `read_png`/`write_png`, the five filters, 8 and 16-bit, grey, grey-alpha, RGB, RGBA; a numba kernel for the sequential unfilter with the Python loops as its twin; `test_png.py` round-trips 4 colour types x 2 depths x 5 filters through both backends (40 cases) and refuses interlaced, palette, 4-bit, a bad filter byte, a short stream |
| 2 | `mips.py` (DDS sizes `max(side // 2, 1)`, colour in linear, normals renormalised), `normals.py` (the DirectX flip, two-channel runtime form, Z reconstruction), `pack.py` (`_ORM` with the 1.0 fill; alpha carriers and `check_pack`), `height.py` (16-bit PNG, half and float EXR at their precision; `normalise` opt-in with the range), `dds2d.py` (7 uncompressed formats round-trip with mips; BC4/BC5/BC7 block writer; `decode_bc4_block` the reference the encoder is held to); `test_mips_normals_pack.py`, `test_height_separate_dds.py` |
| 3 | `separate.py`: wrap-padded Gaussian (`sigma = radius / 2`), the high-pass quantised to the 8 bits that are written, the linear-light recombination, the error measured through that quantisation (within `1/255`), the macro; tests: both halves tile (the blur of the 2x2-tiled image cropped equals the blur of the tile), the error bound, the kernel |
| 4 | `cook.py`: `cook_set` (T1's rules first, the sidecars filled before the inputs are hashed so two cooks give one manifest, `_ORM` and alpha carriers, the encoder seam, manifest and provenance) and `separate_set`; `tools/cook_textures.py` with `cook`, `separate`, `--check-setup`; `test_cook.py`: the files, the hashes, byte-identical reruns, derived-only sidecar edits, refusal before any write, the packed alpha and the flip reaching the pixels, height precision, the detail pair, `check_content.py` clean on a cooked set |
| 5 | `hogshade/jobs/cook_textures.py` registered in `JOB_MODULES`; `test_job_and_setup.py`: `manifest()` lists it, it runs like the worker calls it and its outputs list matches, a climbing `set_dir` is refused |
| 6 | The `textures` extra in `pyproject.toml` (`uv sync --all-extras` installs `ispc_texcomp` 1.0.1); README "The texture cook"; `tools/README.md`; `tools/bats/README.md`; `Docs/knowledge/job-orchestrator.md`; the cook's `WARNING` with the command and `--check-setup`, tested with the import patched away |
| 7 | Poly Haven `cobblestone_floor_04` at 1K (16-bit PNGs, CC0), cooked outside the repository with the encoder in 3.3 s (BC7 fast, BC5, the ORM with the height in its alpha), separated at radius 16 and macro 64: error max 0.0039, mean 0.0020, 440 texels clipped; the four pictures at 512 under `verification/wgpu/textures/cobblestone_floor_04/` (each under 1 MiB) in the gallery; read by a human: the high-pass is neutral grey over the flat stones and carries the edges, the recombination is the source by eye |
| 8 | This table; the spec's amendments; the standard's cook paragraph; board; handoff; journal |
| review | `/local-review diff` round 1: needs work (two hard findings, three metrics at 6); fixed: shape rules before any write, sidecars and manifest after every DDS, the separation record kept on a re-cook, the cook split per suffix, a log line per artifact and decision, EXR and encoder-load errors as findings, the tool's exit 2 on a stray error, the job's encoder asked once and its unknown `compress` warned; `test_cook_review.py` (12 tests). Round 2: needs work (one hard finding: a `pack` declared on a second `_ORM` part consumed its map and wrote it nowhere; the sidecar hash in the manifest differed from the file on disk when the cook left it alone; a short IHDR was a traceback); fixed with the one-declaration and one-base rules, the hash of the file when untouched and LF bytes for every record, `PngError` on a short IHDR, the `separation` block keyed by suffix, the detail normal's unit length tested, the precision reduction and the manifest and provenance writes logged; 4 tests more |

Totals: `uv run pytest -o addopts= -q` 565 passed (97 in `tests/texture_cook/`).
