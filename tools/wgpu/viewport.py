"""
HogShade: render the shader ball from a material document under an E1 environment through the wgpu host, offscreen,
and write the verification PNGs (phase 2 plan, task 14).
Package: tools/wgpu/viewport

    uv run tools/wgpu/viewport.py                      # verification/wgpu/shader-ball/<env>/{forward,deferred}.png
    uv run tools/wgpu/viewport.py --debug-mode 18      # the v2 specular accumulator
    uv run tools/wgpu/viewport.py --material content/materials/legacy-v1/default.material.json --variant legacy-v1

Both paths render every time; the tool prints the mean and max difference between them over the
pixels the ball covers, which is the deferred path's quantisation cost in scene-linear units.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import logging as _logging

from hogshade.ibl.imageio import preview_srgb8, write_png_rgb8
from hogshade.material import bind, load, resolve
from hogshade.wgpu_host import Renderer, Scene, load_shader_ball, request_device

_MODULE_NAME = "tools.wgpu.viewport"
_LOGGER = _logging.getLogger(_MODULE_NAME)  # the tool prints; nothing logs below
DEFAULT_MATERIAL = ROOT / "content" / "materials" / "legacy-v2" / "default.material.json"
__version__ = "0.1.0"
__updated__ = "2026-10-02"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="capture directory; default verification/wgpu/shader-ball/<env>[/<variant>]",
    )
    ap.add_argument("--variant", default="", help="sub-directory for a material variant, e.g. metal")
    ap.add_argument("--environment", default="studio_small_09")
    ap.add_argument("--size", type=int, default=1024, help="square output, multiple of 32")
    ap.add_argument(
        "--material",
        type=Path,
        default=DEFAULT_MATERIAL,
        help="the material document to render (S3); default content/materials/legacy-v2/default.material.json",
    )
    ap.add_argument("--debug-mode", type=int, default=0, help="v2 g_DebugMode 0..32")
    ap.add_argument("--exposure-ev", type=float, default=0.0, help="display exposure for the PNG only")
    ap.add_argument("--hemisphere-mode", type=int, default=0, help="0 off, 1 add, 2 multiply")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    binding = bind(resolve(load(args.material)), "wgpu")
    adapter, device = request_device()
    info = adapter.info
    mesh = load_shader_ball()
    renderer = Renderer(device, mesh, environment=args.environment)
    scene = Scene(
        width=args.size,
        height=args.size,
        material=binding,
        debug_mode=args.debug_mode,
        hemisphere_mode=args.hemisphere_mode,
        environment=args.environment,
    )
    frames = renderer.render(scene)
    elapsed = time.perf_counter() - t0

    out_dir = args.out_dir or ROOT / "verification" / "wgpu" / "shader-ball" / args.environment
    if args.variant:
        out_dir = out_dir / args.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "forward.png"
    deferred_path = out_dir / "deferred.png"
    write_png_rgb8(out, preview_srgb8(frames.forward, args.exposure_ev))
    write_png_rgb8(deferred_path, preview_srgb8(frames.deferred, args.exposure_ev))
    mean_diff, max_diff = frames.difference()
    covered = frames.covered
    lit = frames.forward[covered]
    print(
        f"adapter: {info.get('device')} ({info.get('backend_type')}), GB3 {renderer.gb3_format}, model {binding.model}"
    )
    print(
        f"material: {args.material} ({binding.material_type}); "
        f"{len(binding.unsupported)} parameters the host does not carry: "
        + ", ".join(u.parameter for u in binding.unsupported)
    )
    print(f"mesh: {len(mesh.vertices)} vertices, {len(mesh.indices) // 3} triangles; environment {args.environment}")
    print(
        f"ball covers {int(covered.sum())} of {covered.size} pixels; "
        f"mean linear radiance {lit.mean():.4f}, max {lit.max():.4f}"
    )
    print(f"forward vs deferred over covered pixels: mean {mean_diff:.5f}, max {max_diff:.5f}")
    print(f"wrote {out} and {deferred_path} in {elapsed:.1f} s")
    finite = np.isfinite(frames.forward).all() and np.isfinite(frames.deferred).all()
    return 0 if covered.any() and finite else 1


if __name__ == "__main__":
    raise SystemExit(main())
