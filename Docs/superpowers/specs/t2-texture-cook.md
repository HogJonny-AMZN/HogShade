# T2 spec: the texture cook

**Status:** Proposed. Drafted 2026-10-04 from the accepted conventions design (T2) and the content standard (T1);
built on `feat/t2-texture-cook` once this is merged. Two questions for the owner are at the end; the build
proceeds on their recommendations unless the owner says otherwise. Amendments made in the build go in the
last section.

Date: 2026-10-04. Design:
[../../design/2026-10-03-content-conventions.md](../../design/2026-10-03-content-conventions.md), sections 4
and 5 and answers 3 to 5. Standard: [../../standards/content.md](../../standards/content.md) ("The authoring
set and the runtime set", "Tangents, detail maps and frequency separation"). The pattern:
[e1-ibl-cook.md](e1-ibl-cook.md) (manifest, provenance, the job). T1:
[t1-content-standard.md](t1-content-standard.md) (the suffix table, the sidecar, the check). Plan:
[../plans/t2-texture-cook.md](../plans/t2-texture-cook.md). Vocabulary: [../../glossary.md](../../glossary.md)
(Cook, Authoring set, Runtime set, Sidecar, Preset, Detail map).

## Deliverable

`tools/cook_textures.py` (and the job `hogshade.jobs.cook_textures`) turns one authoring set into its runtime
set: for every source texture in a set directory, mips generated in linear space, normals in the repository's
convention, `_AO`, `_R` and `_M` packed into `_ORM`, each written as a DDS with mips under `<set>/cooked/`,
with `manifest.json` (deterministic: parameters, sha256 of every input and output) and `provenance.json`
(volatile) on the IBL cook's pattern, and the sidecars' derived fields filled and listed. The owner's
frequency separation is a cook operation: `separate` writes the macro colour at a stated low resolution and
the high-pass detail map, with the reconstruction error measured into the manifest. No host converts a
texture at load; after T2 every host reads what the cook wrote, and the first set (T3) is one command
away from its runtime form.

## Package layout

```text
hogshade/texture_cook/              # numpy; never imported by hogshade.material (which stays stdlib-only)
  png.py                            # read_png(path) -> (H, W, C) uint8 or uint16; 8/16-bit grey, RGB, RGBA, non-interlaced
  colour.py                         # srgb_to_linear, linear_to_srgb on arrays (float32), the one definition
  mips.py                           # mip chain by box average; linear space for colour, renormalised for normals
  normals.py                        # directx-y -> opengl+y flip, decode/encode, renormalise, Z reconstruction
  pack.py                           # ORM packing with neutral fills, the manifest's record of what was packed
  separate.py                       # frequency separation: wrap-padded Gaussian low-pass, high-pass, recombination error
  cook.py                           # cook_set(set_dir, ...) -> manifest; sidecar derived fields; the DDS outputs
hogshade/ibl/dds.py                 # gains write_2d(path, mips, dxgi_format) and read_2d for the 2D uncompressed formats
hogshade/jobs/cook_textures.py      # the BATS job: MODULE mode on the hogshade_python worker
tools/cook_textures.py              # uv run tools/cook_textures.py cook <set_dir> [--compress] ; separate <set_dir> --radius 16 --macro 64
tests/texture_cook/                 # png round trips, mips, normals, packing, separation, the cook on a scratch set, the job manifest
```

`hogshade.material.textures` (T1) stays the one table of suffixes and presets; the cook reads it and
writes nothing it does not say.

## Inputs

A set directory under either content root (T1): source textures `T_<set>_<SUFFIX>[_<variant>].png` (8 or
16-bit) or `.exr` (height with range), each with its sidecar and the directory's `LICENSE.md`. The cook
runs `tools/check_content.py`'s rules on the set first and refuses a set with findings: a misnamed or
unsourced texture is never cooked. **TIFF is not read in T2** (question 1); a `.tif` source is a finding
in the cook's log ("not readable in T2; convert to 16-bit PNG") rather than a silent skip.

The PNG reader is this repository's (`png.py`, zlib and numpy: the four filter types, 8 and 16-bit, grey,
grey-alpha, RGB, RGBA; interlaced and palette PNGs are refused with a message). No new dependency: the
gallery already reads PNG headers, and a reader of the common cases is a page of code with a test per
case, where Pillow would be a dependency for one function.

## The runtime set

For each source texture, by its suffix's preset (T1):

| Preset | Source | Runtime (T2 writes) | Mips |
| --- | --- | --- | --- |
| colour (`_BC`, `_E`) | sRGB 8-bit | `R8G8B8A8_UNORM_SRGB`, alpha 255 (or the `_O` map when the sidecar packs it) | box average in **linear**, re-encoded per level |
| data, one channel (`_M _SW _R _AX _AR _O _AO _C _SO`) | raw 8-bit | `R8_UNORM` | box average |
| colour data (`_SC`) | raw 8-bit | `R8G8B8A8_UNORM` | box average |
| normal (`_N`, `_DN`) | raw 8-bit, the sidecar's convention | `R8G8_UNORM` (X, Y; Z reconstructed by the host) | average, then renormalise, per level |
| height (`_H`) | raw 16-bit PNG or EXR | `R16_UNORM` | box average |
| packed (`_ORM`) | from `_AO`, `_R`, `_M` | `R8G8B8A8_UNORM`: AO in R, roughness in G, metalness in B, 255 in A | box average |

A missing channel of `_ORM` is filled with **1.0**, the identity of the `multiply` blend (S1's default), and
the manifest says which channels were packed and which filled. A normal source stated as `directx-y` has its
green channel flipped before anything else, and the manifest records the flip; every runtime normal is
`opengl+y`, as the standard promises. Mips go down to 1x1; a source that is not a power of two is cooked
as is (no resampling) and the manifest says so.

**Compression** (question 2; the owner is choosing an open-source encoder through an evaluation spike,
2026-10-04): T2 writes the uncompressed DXGI formats above through `write_2d`, and `cook.py` carries an
**encoder seam**: an `Encoder` protocol (`encode(dds_in, dds_out, block_format) -> dict`, returning the
encoder's name and version for the manifest) with one implementation shipped, `TexconvEncoder`
(DirectXTex's `texconv` found on `PATH` or named by `HOGSHADE_TEXCONV`). `--compress` selects the preset's
block format (BC7 for colour, BC5 for normals, BC4 for one channel, `R16_UNORM` stays) and runs the encoder;
absent an encoder the cook says so and writes uncompressed. The manifest records the format actually
written and the encoder; the manifest's `runtime.format` is the truth a host reads, and the standard's
table says "BC7, or uncompressed until the encoder is present". The library the spike picks is a second
`Encoder` behind the same seam, its own small increment; the owner's requirement for it is that it runs on
the BATS Python worker (Python with bindings, or Python made fast), so the seam takes a callable, never only
a subprocess.

The sidecar: the cook fills every derived field it has authority over (`preset`, `colour_space`, `mips`,
`runtime` with the format actually written, `resolution`) when absent, lists them under `derived`, and
never touches an authored field; a derived field present and disagreeing without `override_reason` is a
finding and the set is refused (T1's rule, applied before cooking).

## Frequency separation

`tools/cook_textures.py separate <set_dir> --radius 16 --macro 64 [--source _BC]`, the owner's technique as
code (co3dex 2022, section "Basic Frequency Separation" and "Tiling Textures"):

1. Read the colour map (`_BC` by default) **in its stored encoding** (the sRGB 8-bit values; the post and
   O3DE's `ApplyTextureBlend` both separate and blend in display space, so the shader's recombination
   matches by construction).
2. Pad by wrapping (`numpy.pad(mode="wrap")`) by at least `3 * sigma` on every side, so the blur sees the
   tiled neighbours; the low-pass is a separable Gaussian with `sigma = radius / 2` (the post's Photoshop
   radius 16 reads as this), cropped back to the tile. Both halves tile because the blur did.
3. `high = clip((source - low) * 0.5 + 0.5)`: the post's "subtract, offset 128, scale 2" in [0, 1]; mid-grey
   is neutral.
4. Recombination `recon = clip(low + 2 * high - 1)` (linear light, O3DE's `TextureBlend_LinearLight`); the
   **reconstruction error** `max |recon - source|` and its mean over the tile go into the manifest. The
   error is zero except where the high-pass clipped; the manifest also counts clipped texels.
5. Outputs under `cooked/`: `T_<set>_DH.dds` (the high-pass, raw, full resolution, `R8G8B8A8_UNORM`) and
   `T_<set>_BC_macro.dds` (the low-pass box-downsampled to `--macro` texels on its longer side, sRGB;
   `macro` is a variant, so the name meets the grammar); and a display PNG pair under `verification/`
   when `--picture` is given (the gallery's rule), never under `content/`.

`_DN`, the detail normal, is the same separation on the normal's X and Y channels about their neutral
(0.5, 0.5), Z reconstructed on write; the macro normal is not written (the standard's `_N` already carries
the low frequency at its own mips). Reoriented normal mapping is the host's blend, named in the standard,
not the cook's.

## Manifest and provenance

`<set>/cooked/manifest.json`, deterministic, sorted keys:

```json
{
  "tool": "hogshade.texture_cook", "tool_version": "0.1.0", "hogshade_version": "...",
  "set": "brick",
  "inputs": {"T_brick_BC.png": "<sha256>", "T_brick_BC.texture.json": "<sha256>", "...": "..."},
  "textures": {
    "T_brick_BC.dds": {"from": "T_brick_BC.png", "preset": "base_color", "format": "R8G8B8A8_UNORM_SRGB", "size": [2048, 2048], "mips": 12, "sha256": "..."},
    "T_brick_N.dds": {"from": "T_brick_N.png", "format": "R8G8_UNORM", "normal_convention_in": "directx-y", "flipped_y": true, "...": "..."},
    "T_brick_ORM.dds": {"packed": {"R": "T_brick_AO.png", "G": "T_brick_R.png", "B": "filled 1.0"}, "...": "..."}
  },
  "separation": {"source": "T_brick_BC.png", "radius": 16, "sigma": 8.0, "macro": 64, "error_max": 0.0039, "error_mean": 0.00002, "clipped_texels": 7},
  "compression": {"requested": false, "encoder": null}
}
```

`provenance.json` is the IBL cook's (time, machine, git hash, Python, numpy, wall seconds). `check_content.py`
already allows both beside the DDS files.

## The job

`hogshade/jobs/cook_textures.py`: `MANIFEST` on the IBL job's shape (`worker_type` `python`, parameters
`set_dir`, `compress`, `separate`, `radius`, `macro`; inputs, outputs, returns the manifest; `spec` this
file), `main(parameters)` calling `cook.cook_set`. Runs without the orchestrator through
`tools/cook_textures.py`; a path parameter that climbs is refused (the jobs' rule).

## Tests

`tests/texture_cook/`:

- `test_png.py`: round trips through the gallery's PNG writer and this reader for grey, RGB, RGBA at 8 and
  16 bits and every filter type (a writer that emits each filter is in the test); an interlaced or palette
  PNG is refused with its message.
- `test_mips.py`: a 4x4 sRGB checker's first mip is the linear average re-encoded, not the sRGB average;
  the chain ends at 1x1; a normal mip is unit length.
- `test_normals.py`: a `directx-y` source flips green and the manifest says so; `opengl+y` is untouched.
- `test_pack.py`: AO, R, M land in R, G, B; a missing channel is 1.0 and recorded.
- `test_separate.py`: on a tiling test tile, low and high both tile (the wrapped border equals the opposite
  edge within one 8-bit step), `recon == source` away from clipping, the error fields are the measured
  values, the macro is the stated size; sigma follows the radius.
- `test_cook.py`: a scratch set (the T1 test corpus's shape) cooks to the expected files, the manifest's
  sha256 match the files, cooking twice is byte-identical, the sidecars gain their derived fields and the
  authored fields are untouched, a set with a T1 finding is refused, `check_content.py` passes on the cooked
  set (DDS and the two records only under `cooked/`).
- `test_job.py`: the job manifest's outputs match what the cook writes; a climbing `set_dir` is refused.

## Acceptance gate

- The tests above green on CI (no GPU, no LFS payload needed: the scratch set is built in the test);
  `check_content.py`, `check_docs.py`, `check_hygiene.py` clean; ruff clean.
- On the owner's machine: the cook run on a scratch set from a Poly Haven download outside the repository
  (no set is committed in T2; T3 commits the first) with the manifest and a separation picture pair under
  `verification/wgpu/textures/` listed in the gallery as the proof the detail pair recombines; the PR says
  what was seen.

## Out of scope

- TIFF sources (question 1) and a BC encoder in the repository (question 2).
- Texture sampling in any host: the wgpu host has no texture bind group, the Maya shell binds by hand;
  seeing a cooked set is T3's host half.
- Generated textures and their validation harness (the gated-research row); the showcase set (T4).
- Reoriented normal mapping in the shaders; the macro normal.

## The questions for the owner

1. **TIFF.** Read PNG (8 and 16-bit) and EXR only, with this repository's reader and no new dependency
   (recommended: Poly Haven ships PNG; a 16-bit PNG carries what a 16-bit TIFF would; the reader is a
   page), or add Pillow as a `textures` extra and read TIFF too?
2. **Compression.** Write uncompressed DXGI formats with an encoder seam, `texconv` the first encoder when
   it is on the machine (recommended: no encoder in the repository, the manifest says what was written,
   the hosts read either), or make an encoder a required tool and refuse to cook without it? The owner is
   choosing the library by an evaluation spike (2026-10-04, `Spikes/bc_encode/`, the board's row); it lands
   behind the seam. The owner's bar: it runs on the BATS Python worker.

## Amendments made in the build

(none yet)
