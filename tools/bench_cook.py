"""
HogShade: benchmark the IBL prefilter across backends, cube sizes and sample counts (E2 plan, task 5).
Package: tools/bench_cook.py

    uv run tools/bench_cook.py --source content/ibl/studio_small_09/source_4k.exr --out Docs/research/benchmarks/2026-09-20-cook.md
    uv run tools/bench_cook.py --quick            # 256 only, both backends; a smoke run

Times ``prefilter_specular`` per mip and in total. Runs that are expected to exceed ``--budget``
seconds (from the measured per-texel cost of the previous run) are extrapolated and marked so.
The numba kernel is warmed once before timing so JIT compile is excluded.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hogshade.ibl import prefilter
from hogshade.ibl.cubemap import equirect_pyramid
from hogshade.ibl.imageio import read_exr_rgb


def cube_bytes(base: int) -> int:
    """RGBA16F cube with a full mip chain."""
    total = 0
    n = base
    while n >= 1:
        total += 6 * n * n * 8
        n //= 2
    return total


def fmt_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f} s"
    if s < 3600:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.2f} h"


def run_one(pyramid: list[np.ndarray], base: int, samples: int, backend: str) -> tuple[float, dict[int, float]]:
    timings: dict[int, float] = {}
    t0 = time.perf_counter()
    prefilter.prefilter_specular(pyramid, base=base, samples=samples, backend=backend, timings=timings)
    return time.perf_counter() - t0, timings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, default=Path("content/ibl/studio_small_09/source_4k.exr"))
    parser.add_argument("--out", type=Path, default=None, help="markdown report path")
    parser.add_argument("--bases", default="256,512,1024,2048")
    parser.add_argument("--samples", type=int, default=1024)
    parser.add_argument("--sample-sweep", default="256,1024,4096", help="sample counts to sweep at the first base")
    parser.add_argument("--budget", type=float, default=1800.0, help="skip and extrapolate runs predicted above this")
    parser.add_argument("--quick", action="store_true", help="256 only, both backends")
    parser.add_argument("--backends", default="numpy,numba", help="which backends to run, comma separated")
    args = parser.parse_args(argv)

    bases = [256] if args.quick else [int(b) for b in args.bases.split(",")]
    sweep = [] if args.quick else [int(s) for s in args.sample_sweep.split(",") if int(s) != args.samples]
    wanted = [b.strip() for b in args.backends.split(",") if b.strip()]
    backends = [b for b in wanted if b != "numba" or prefilter.HAVE_NUMBA]

    img = read_exr_rgb(args.source)
    pyramid = equirect_pyramid(img)
    src_desc = f"{args.source} ({img.shape[1]}x{img.shape[0]})"
    print(f"source {src_desc}; backends {backends}; bases {bases}")

    if prefilter.HAVE_NUMBA:
        prefilter.prefilter_specular(pyramid, base=16, samples=64, backend="numba")  # warm the JIT

    rows: list[dict] = []
    per_texel_sample: dict[str, float] = {}  # measured seconds per (texel x sample), per backend
    for backend in backends:
        for base in bases:
            texel_samples = sum(6 * (base >> m) ** 2 for m in range(1, int(np.log2(base)) + 1)) * args.samples
            predicted = per_texel_sample.get(backend, 0.0) * texel_samples
            if backend in per_texel_sample and predicted > args.budget:
                rows.append(
                    {
                        "backend": backend,
                        "base": base,
                        "samples": args.samples,
                        "seconds": predicted,
                        "extrapolated": True,
                    }
                )
                print(f"{backend:6s} base {base:5d}: predicted {fmt_seconds(predicted)}, skipped (over budget)")
                continue
            total, timings = run_one(pyramid, base, args.samples, backend)
            per_texel_sample[backend] = total / texel_samples
            rows.append(
                {
                    "backend": backend,
                    "base": base,
                    "samples": args.samples,
                    "seconds": total,
                    "extrapolated": False,
                    "per_mip": timings,
                }
            )
            print(f"{backend:6s} base {base:5d}: {fmt_seconds(total)}")
        for samples in sweep:
            total, timings = run_one(pyramid, bases[0], samples, backend)
            rows.append(
                {
                    "backend": backend,
                    "base": bases[0],
                    "samples": samples,
                    "seconds": total,
                    "extrapolated": False,
                    "per_mip": timings,
                }
            )
            print(f"{backend:6s} base {bases[0]:5d} samples {samples:5d}: {fmt_seconds(total)}")

    lines = [
        "# IBL cook benchmark",
        "",
        f"Date: {time.strftime('%Y-%m-%d')}. Source: `{src_desc}`. Machine: {platform.node()}, "
        f"{platform.platform()}, Python {sys.version.split()[0]}, NumPy {np.__version__}"
        + (f", numba {__import__('numba').__version__}" if prefilter.HAVE_NUMBA else ", numba absent")
        + ". Times are wall clock for `prefilter_specular` only (mip 0 resample plus every prefiltered mip); "
        "the irradiance, SH9, LUT and file writes add a few seconds and do not scale with the cube.",
        "",
        "| Backend | Cube base | Samples per texel | Prefilter time | Cube size (RGBA16F, all mips) | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        note = "extrapolated from the measured per-texel cost" if r["extrapolated"] else ""
        lines.append(
            f"| {r['backend']} | {r['base']} | {r['samples']} | {fmt_seconds(r['seconds'])} | "
            f"{cube_bytes(r['base']) / 1048576:.1f} MB | {note} |"
        )
    measured = {(r["backend"], r["base"], r["samples"]): r["seconds"] for r in rows if not r["extrapolated"]}
    speedups = []
    for (backend, base, samples), secs in measured.items():
        if backend == "numba" and ("numpy", base, samples) in measured:
            speedups.append(f"{measured[('numpy', base, samples)] / secs:.1f}x at base {base}, {samples} samples")
    if speedups:
        lines += ["", "numba over NumPy: " + "; ".join(speedups) + "."]
    per_mip_rows = [r for r in rows if not r["extrapolated"] and r["samples"] == args.samples]
    if per_mip_rows:
        lines += ["", "## Seconds per mip (measured runs at the default sample count)", ""]
        mips = max(len(r["per_mip"]) for r in per_mip_rows)
        lines.append("| Backend | Base | " + " | ".join(f"mip {m}" for m in range(mips)) + " |")
        lines.append("| --- | --- | " + " | ".join("---" for _ in range(mips)) + " |")
        for r in per_mip_rows:
            cells = [f"{r['per_mip'].get(m, 0.0):.2f}" for m in range(mips)]
            lines.append(f"| {r['backend']} | {r['base']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Reading it",
        "",
        "- Work scales with texels times samples; each doubling of the cube base is 4x the time.",
        (
            "- A source of width W matches a cube face of W / 4 texels; cooking a larger cube from the same source "
            "resamples mip 0 rather than adding detail."
        ),
        "- Mip 1 dominates: it has the most texels of the prefiltered mips. Mip 0 is a resample and is free.",
    ]
    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
