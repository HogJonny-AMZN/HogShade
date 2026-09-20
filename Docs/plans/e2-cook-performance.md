# E2 plan: cook performance and resolution

Spec: [../specs/e2-cook-performance.md](../specs/e2-cook-performance.md). One PR. Tick a task only when
its verification ran.

## Tasks

- [x] 1. `numba` as the `jit` optional extra in `pyproject.toml`; `hogshade.ibl.prefilter` imports it
      lazily and `HAVE_NUMBA` says whether it did. Verified 2026-09-20: numba 0.67 on Python 3.12, 24 threads.
- [x] 2. Numba kernel `_prefilter_mip_numba(level_arrays, level_shapes, dirs, h_t, levels, out)`:
      per-texel loop over samples, tangent frame, half vector to world, reflect, weight, bilinear
      lookup on the selected pyramid level with wrap and clamp, `prange` over texels. Verified:
      parity test against NumPy on a 32 cube within 1e-4 relative; furnace on both backends. Verified
      2026-09-20: `tests/ibl/test_backends.py` (parity, furnace on both, run-to-run determinism).
- [x] 3. `prefilter_specular(..., backend="auto"|"numpy"|"numba")`; `cook_environment` and the CLI
      pass it through; the manifest records `backend` and provenance records seconds per mip.
      Verified 2026-09-20 by the parity test; the two backends agree to 1e-4, not to the byte (float
      accumulation order differs), so the manifest names the backend and a re-cook must use the same
      one to reproduce bytes. The spec is corrected to say so.
- [x] 4. `condition --width` so an 8K master can be conditioned to 8192x4096 (or kept as is) for a
      hero cook; default stays 4096. Verified 2026-09-20: studio 8K conditioned at 8192x4096, 50.7 MB, factor 1.
- [x] 5. `tools/bench_cook.py`: per-mip and total wall time per backend and base, sample-count
      sweep at 256, output sizes; writes the benchmark markdown. Verified 2026-09-20:
      `Docs/research/benchmarks/2026-09-20-cook-4k.md` and `-8k.md`.
- [x] 6. Measure: numpy and numba at 256, 512, 1024; numba at 2048 (from the 8K master); 256 at
      256 and 4096 samples. Extrapolate what did not run and say so. Done 2026-09-20: NumPy 256 and
      512 measured (1.3 and 4.6 min), 1024 and 2048 extrapolated (18 min, 1.2 h); numba 256 to 2048
      from 4K (0.5 s to 32 s) and 2048 to 8192 from 8K (33 s, 2.2 min, 8.5 min); sample sweep at 256
      on both. numba is 140x. Mip 0's NumPy resample is a third of the time above 2048.
- [x] 7. The highest-resolution cook that finishes under 30 minutes, from the density-matched
      source, with its size in the table. Done 2026-09-20: the density-matched ceiling is a 2048 cube
      from the 8K source, cooked in full (manifest backend numba, 256 MB specular.dds), local only;
      8192 measured at 8.5 min prefilter (4 GB) as the absolute ceiling on this machine.
- [x] 8. `content/ibl/README.md`: backends, how to install the extra, the resolution rule of thumb
      (N = W / 4), the size table. Roadmap and `Docs/README.md` status rows.
