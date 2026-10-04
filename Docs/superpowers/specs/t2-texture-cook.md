# T2 spec: the texture cook

**Status:** Proposed. Drafted 2026-10-04 from the accepted conventions design (T2) and the content standard (T1);
built on `feat/t2-texture-cook` once this is merged. Two questions for the owner are at the end; the second
is answered (`ispc_texcomp`), the first proceeds on its recommendation unless the owner says otherwise. Amendments made in the build go in the
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
  height.py                         # the height formats: 16-bit PNG, half and float EXR, the optional normalisation with its range
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

The PNG reader is this repository's (`png.py`, zlib and numpy: the five filter types, None, Sub, Up, Average
and Paeth; 8 and 16-bit; grey,
grey-alpha, RGB, RGBA; interlaced and palette PNGs are refused with a message). No new dependency: the
gallery already reads PNG headers, and a reader of the common cases is a page of code with a test per
case, where Pillow would be a dependency for one function.

## The runtime set

For each source texture, by its suffix's preset (T1):

| Preset | Source | Runtime (T2 writes) | Mips |
| --- | --- | --- | --- |
| colour (`_BC`, `_E`) | sRGB 8-bit | `R8G8B8A8_UNORM_SRGB`; alpha 255, or the packed single-channel map ("Packing" below) | box average in **linear**, re-encoded per level; the alpha averaged raw |
| data, one channel (`_M _SW _R _AX _AR _O _AO _C _SO`) | raw 8-bit | `R8_UNORM`, unless a carrier's sidecar packs it into an alpha ("Packing" below), in which case no separate file is written | box average |
| colour data (`_SC`) | raw 8-bit | `R8G8B8A8_UNORM` | box average |
| normal (`_N`) | raw 8-bit, the sidecar's convention | `R8G8_UNORM` (X, Y; Z reconstructed by the host) | average, then renormalise, per level |
| height (`_H`) | raw: 16-bit PNG, or EXR half or float | `R16_UNORM` from a 16-bit PNG; `R16_FLOAT` from a half EXR; `R32_FLOAT` from a float EXR ("Height" below) | box average in the source's precision |
| packed (`_ORM`) | from `_AO`, `_R`, `_M` | `R8G8B8A8_UNORM`: AO in R, roughness in G, metalness in B, 255 in A | box average |

A missing channel of `_ORM` is filled with **1.0**, the identity of the `multiply` blend (S1's default), and
the manifest says which channels were packed and which filled.

### Packing

The owner's rule (2026-10-04): colour with alpha needs a packing scheme and an output type, and other
conditioning strategies will want to pack data into an alpha channel too. So packing is one mechanism, not
a list of special cases:

- **Fixed packings** are the tables' (`_ORM`: AO, roughness, metalness in R, G, B, always).
- **Alpha carriers**: a four-channel runtime map whose alpha is otherwise constant may carry one
  single-channel map of the same set and base. The carriers are `_BC`, `_E`, `_SC` (the `R8G8B8A8` maps)
  and `_ORM` (whose alpha is free). A carrier's sidecar declares it with a `pack` field, validated by the
  content check (`SIDECAR_KEYS` gains `pack`; a T1 edit inside this build):

  ```json
  {"pack": {"a": "_O"}, "provenance": {"...": "..."}}
  ```

  `pack.a` names a suffix of the tables with one channel (`_O`, `_H`, `_AO`, `_C`, `_SO`, `_M`, `_R`, `_SW`,
  `_AX`, `_AR`); the map `T_<base>_<that suffix>` of the same set is read, box-averaged raw per mip, and
  written into the carrier's alpha; no separate file is written for it, and the manifest's entry for the
  carrier records `"packed": {"A": "T_<base>_O.png"}`. A `pack` naming a suffix with no file, a
  three-channel suffix, or a carrier that is not in the list above is a finding. The authoring set stays
  one map per parameter (the standard); packing is the cook's and the manifest is how a host learns where a
  parameter's channel lives.
- **The output type for colour with alpha** is `R8G8B8A8_UNORM_SRGB` uncompressed and **BC7 with one of
  the `alpha_*` profiles** (`ispc_texcomp`'s `alpha_basic` by default; the non-alpha profiles assume alpha
  255 and would quantise a packed channel away) when compressed; the manifest records the profile. For
  `_ORM`, `R8G8B8A8_UNORM` and the same BC7 alpha profile.
- **Other conditioning strategies** (the owner's "some other texture conditioning strategies might want to
  pack data into an alpha channel as well") extend the `pack.a` value from a suffix to an object naming an
  operation, `{"from": "_H", "op": "invert"}` say; the shape is reserved here and no operation is built in
  T2. A strategy that needs more than one alpha is a new packing in the tables, not a sidecar trick.

The host side of reading a packed channel (a binding that says "geometry_opacity is the alpha of this
file") is T3's host half, informed by the manifest; T2 writes the truth, it does not yet consume it. A normal source stated as `directx-y` has its
green channel flipped before anything else, and the manifest records the flip; every runtime normal is
`opengl+y`, as the standard promises.

### Height

The owner's rule (2026-10-04): high-quality 32-bit data and half-float EXR heightmaps cook to a respectable
format, never squeezed into 8 bits. `_H` is in T1's table (height, raw, 16-bit authoring; "R16 when the cook
says"); the cook says:

| Source | Runtime | Why |
| --- | --- | --- |
| 16-bit PNG | `R16_UNORM` | the source's 65536 steps kept exactly; the range is the file's |
| EXR, half (`HALF` channel) | `R16_FLOAT` | exact for the source's precision; the range in the manifest |
| EXR, float (`FLOAT` channel) | `R32_FLOAT` | 32-bit data kept exactly; the size is the cost, the manifest says it |
| 8-bit PNG | `R8_UNORM`, or BC4 compressed | the source had 256 steps; the table's BC4 is for this case only |

The cook never compresses a height map with a block format (BC4 is 8-bit; BC6H is three-channel HDR colour
and its single-channel use wastes two channels) and never converts float to normalised without being
asked: `--height normalise` writes `R16_UNORM` from an EXR with `min` and `max` recorded in the manifest
and the sidecar, for a host that wants a fixed range, and the default keeps the float. Mips of a height
map are box averages in the source's precision. The EXR reader is `hogshade.ibl.imageio.read_exr_rgb`
extended with a single-channel read (`read_exr_channel(path, "R")` or the first channel), so no new
dependency: OpenEXR is already one. A 32-bit TIFF is question 1's territory and stays out of T2.

A float height is what parallax and displacement want; the Maya shell's parallax group reads `heightMap`
through its red channel today, and whether it samples `R16_FLOAT` and `R32_FLOAT` DDS is the host half's
to prove (T3), with the uncompressed path (`R16_UNORM`) the fallback a host is sure to read.

Mips go down to 1x1; a source that is not a power of two is cooked
as is (no resampling) and the manifest says so.

**Compression** (question 2, answered: `ispc_texcomp`). The cook writes the uncompressed DXGI formats above
through `write_2d`, and `cook.py` carries an **encoder seam**: an `Encoder` protocol (`encode(level, block_format,
alpha, profile) -> bytes`, the block bytes of one level, plus the encoder's name and version for the manifest)
with `IspcEncoder` (Intel's ISPC Texture Compressor through `ispc_texcomp`, the `textures` extra) the default
and `TexconvEncoder` (DirectXTex's `texconv` on `PATH` or named by `HOGSHADE_TEXCONV`) the optional baseline.
**One behaviour, three flags:** with no flag, compression is automatic when an encoder is present (BC7 for
colour, BC5 for normals, BC4 for one channel; height's `R16`/`R32` formats stay) and, when none is, the cook
warns once with the install command and writes uncompressed; `--compress` makes an encoder required (exit 2
with the same command when absent); `--no-compress` writes uncompressed on purpose. The manifest records the
format actually written and the encoder; the manifest's `runtime.format` is the truth a host reads, and the
standard's table says "BC7, or uncompressed until the encoder is present". The seam takes a callable, never
only a subprocess, because the owner's bar is that it runs on the BATS Python worker; `ispc_texcomp` returns
the blocks as `bytes` and `dds2d.write_2d_blocks` writes them with the block pitch in the header. BC4 takes an
R8 surface and BC5 an RG8 surface, not RGBA (found by decoding a block by hand).

The sidecar: the cook fills every derived field it has authority over (`preset`, `colour_space`, `mips`,
`runtime` with the format actually written, `resolution`) when absent, lists them under `derived`, and
never touches an authored field (`pack` is authored); a derived field present and disagreeing without `override_reason` is a
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
(0.5, 0.5), Z reconstructed on write, written as `T_<set>_DN.dds` (`R8G8_UNORM`, the derived map of T1's
table, no authored sidecar); the **macro normal** is written beside it as `T_<set>_N_macro.dds` at the
`--macro` size, carrying the low frequency as the design says (section 5: "the macro normal carrying the
low frequency"). Reoriented normal mapping is the host's blend, named in the standard, not the cook's.

## Setup, and where it is written down

The owner's rule (2026-10-04): the encoder's setup is part of setup and getting-started documentation, not
a surprise at first cook. `ispc_texcomp` is declared in `pyproject.toml` as the `textures` extra, and
`uv sync --all-extras` (the one setup command the README, CI and the BATS Python worker already share; the
worker runs on the workspace `.venv`, `tools/bats/orchestrator_config_hogshade.json`) installs it. So:

- `README.md`, "Getting started", gains **The texture cook**: `uv sync --all-extras` (names the extra and
  that it brings the ISPC encoder), `uv run tools/cook_textures.py cook <set>`, what lands under `cooked/`,
  and that without the extra the cook writes uncompressed and says so.
- `tools/README.md` names the cook beside the IBL cook, with the same two lines.
- `tools/bats/README.md` and `Docs/knowledge/job-orchestrator.md` say the Python worker's venv carries the
  `textures` extra because `--all-extras` does, and that `hogshade.jobs.cook_textures` is the job.
- The cook itself, when `ispc_texcomp` does not import: one `WARNING` naming the command
  (`uv sync --extra textures`), then an uncompressed cook with the manifest saying `"encoder": null`;
  with `--compress` asked for explicitly and no encoder, exit 2 with the same message. A `--check-setup`
  flag prints the encoder found, its version and the formats it will write, for a newcomer and for the
  getting-started page.
- The getting-started page proper is the manual's first chapter (the board's `Docs/manual/` row); when it
  exists it carries this section verbatim, and the README's subsection points at it.

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
    "T_brick_ORM.dds": {"packed": {"R": "T_brick_AO.png", "G": "T_brick_R.png", "B": "filled 1.0", "A": "T_brick_H.png"}, "...": "..."},
    "T_brick_BC.dds": {"packed": {"A": "T_brick_O.png"}, "bc7_profile": "alpha_basic", "...": "..."}
  },
  "separation": {"source": "T_brick_BC.png", "radius": 16, "sigma": 8.0, "macro": 64, "error_max": 0.0039, "error_mean": 0.00002, "clipped_texels": 7},
  "compression": {"requested": false, "encoder": null}
}
```

`provenance.json` is the IBL cook's (time, machine, git hash, Python, numpy, wall seconds). `check_content.py`
already allows both beside the DDS files.

## The job

`hogshade/jobs/cook_textures.py`, registered in `hogshade.jobs.JOB_MODULES` so `manifest()` enumerates it:
`MANIFEST` on the IBL job's shape (`worker_type` `python`, parameters
`set_dir`, `compress`, `separate`, `radius`, `macro`; inputs, outputs, returns the manifest; `spec` this
file), `main(parameters)` calling `cook.cook_set`. Runs without the orchestrator through
`tools/cook_textures.py`; a path parameter that climbs is refused (the jobs' rule).

## Tests

`tests/texture_cook/` (and `test_material_textures.py` gains the `pack` sidecar key):

- `test_png.py`: round trips through a test writer and this reader for grey, grey-alpha, RGB and RGBA at 8
  and 16 bits, under each of the five filter types (the writer emits each); an interlaced or palette PNG is
  refused with its message.
- `test_mips.py`: a 4x4 sRGB checker's first mip is the linear average re-encoded, not the sRGB average;
  the chain ends at 1x1; a normal mip is unit length.
- `test_height.py`: a 16-bit PNG ramp cooks to `R16_UNORM` with every step kept; a half EXR to `R16_FLOAT` and
  a float EXR to `R32_FLOAT`, both read back exactly; `--height normalise` records the range and maps the
  extremes to 0 and 65535; an 8-bit height is `R8_UNORM` (or BC4 with `--compress`); the manifest names the
  source's precision.
- `test_normals.py`: a `directx-y` source flips green and the manifest says so; `opengl+y` is untouched.
- `test_pack.py`: AO, R, M land in R, G, B; a missing channel is 1.0 and recorded; a `pack` sidecar puts
  `_O` into `_BC`'s alpha and `_H` into `_ORM`'s, no separate file for them, the manifest says so, the BC7
  profile is an `alpha_*` one; a `pack` naming a missing map, a three-channel suffix or a non-carrier is a
  finding.
- `test_separate.py`: on a tiling test tile, low and high both tile (the wrapped border equals the opposite
  edge within one 8-bit step), `recon == source` away from clipping, the error fields are the measured
  values, the macro is the stated size; sigma follows the radius.
- `test_cook.py`: a scratch set (the T1 test corpus's shape) cooks to the expected files, the manifest's
  sha256 match the files, cooking twice is byte-identical, the sidecars gain their derived fields and the
  authored fields are untouched, a set with a T1 finding is refused, `check_content.py` passes on the cooked
  set (DDS and the two records only under `cooked/`).
- `test_job.py`: the job manifest's outputs match what the cook writes; a climbing `set_dir` is refused.
- `test_setup.py`: with the encoder import patched away, `cook` warns with the `uv sync` command and writes
  uncompressed, `--compress` exits 2 with it, `--check-setup` reports; with it present, `--check-setup` names
  the version and the three formats.

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
2. **Compression: answered 2026-10-04.** The owner found `ispc_texcomp` (Intel's ISPC Texture Compressor,
   K0lb3's MIT binding on PyPI) and said: "if it does everything we need, we could end the spike with it, and
   log the other options for research and evaluation later." It does: wheels for Windows, Linux and macOS on
   `cp311-abi3`; BC7, BC5, BC4 from Python with no subprocess (the BATS bar); deterministic; BC7 at 37 dB on a
   noisy gradient. So T2 declares it as the `textures` extra (`uv sync --extra textures`), `IspcEncoder` is
   the default behind the seam and `TexconvEncoder` the optional baseline; compression is automatic when the
   extra is installed, a warning and uncompressed output when it is not, `--compress` makes it required (the
   one behaviour, "Compression" above). One API fact: BC4 takes
   an R8 surface and BC5 an RG8 surface, not RGBA. The other options are logged on the board's Icebox.

## Amendments made in the build

(none yet)
