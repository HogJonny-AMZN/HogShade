# E2 spec: cook performance and resolution

Date: 2026-09-20. Track E, second item. Follows [e1-ibl-cook.md](e1-ibl-cook.md). Plan:
[../plans/e2-cook-performance.md](../plans/e2-cook-performance.md).

## Deliverable

The cook runs at the resolutions a look-dev or hero asset wants, in minutes rather than hours, with
the cost measured and written down, and the NumPy path kept as the reference the fast path is
checked against.

## Why

E1's prefilter is NumPy over chunks of texels with 1024 samples each: about 66 s for a 256 cube.
The work scales with the number of texels, so a 1024 cube is 16x and a 2048 cube is 64x that, and
a 4096 cube would take the better part of a day. The owner wants the ceiling measured: the highest
cube resolution the sources support, and what it costs.

## Scope

1. **Two backends behind one function.** `prefilter_specular(..., backend="auto")` selects a numba
   kernel when numba imports and the NumPy path otherwise; `backend="numpy"` and `backend="numba"`
   force one. The numba kernel is the same algorithm (Hammersley GGX, PDF-based source level,
   bilinear equirect lookup with wrap and clamp), written as a per-texel loop over samples,
   `parallel=True` over texels with `prange`, `fastmath` off so results are reproducible. The
   irradiance and LUT paths stay NumPy; they are already exact and cheap.
2. **Parity is a test, not a claim.** For a small cube the numba result must match the NumPy result
   within float32 accumulation noise (relative 1e-4 per texel). The furnace test runs on both.
3. **Reproducibility survives, per backend.** With `parallel=True` the per-texel accumulation is
   still sequential inside the texel, so a backend's result does not depend on thread scheduling and
   two runs give identical bytes. The two backends agree to 1e-4 relative, not to the byte (float
   accumulation order differs), so the manifest records the backend and a byte-for-byte re-cook
   uses the same one. CI checks run-to-run determinism on numba and cross-backend parity.
4. **Resolution.** `--base` is already a parameter. What changes: the source level for mip 0 and the
   PDF-based level selection already scale; the DDS writer is size-agnostic; sample count stays
   1024 by default and becomes a parameter that the benchmark varies. A 4K source supports a 1024
   cube at matching texel density (a cube face of N covers 90 degrees, so N = W / 4); 2048 needs the
   8K master and 4096 would need 16K. `condition` gains `--width` so an 8K source can be kept for
   the hero cook; the repo default stays 4K.
5. **The benchmark.** `tools/bench_cook.py` times `prefilter_specular` per mip and total for
   backend in (numpy, numba) and base in (256, 512, 1024, 2048) at 1024 samples, plus 256 at
   256 and 4096 samples, on the studio source, and writes `Docs/research/benchmarks/<date>-cook.md`
   with a table, the machine, and the wall clock. Numbers that do not fit a session (the NumPy
   2048 run) are extrapolated and marked as such. Output sizes per base are in the table.
6. **Highest resolution measured.** One cook of the studio environment at the largest base that
   finishes under 30 minutes on the numba path, from the 8K master where the density argument says
   so, kept as a benchmark artefact under LFS only if the owner wants it shipped; otherwise the
   numbers are the deliverable and the file stays local.

## Out of scope

- A GPU (wgpu compute) prefilter. That is the next rung if numba is not enough; it is not needed
  to measure the ceiling.
- BC6H compression. A 2048 cube in RGBA16F is 6 x 2048 x 2048 x 8 bytes x 1.33 = 268 MB; the
  size table in the benchmark makes the case for compression later.
- Changing any convention from E1.

## Acceptance gate

- `pytest` passes with numba installed and with it absent (the numpy path is exercised either way).
- numba and NumPy agree within 1e-4 relative on a 32 cube, both pass the furnace, and numba is
  deterministic run to run.
- The benchmark document exists with measured numbers for 256, 512 and 1024 on both backends and
  for 2048 on numba, and states the speed-up.
- The manifest names the backend used.
