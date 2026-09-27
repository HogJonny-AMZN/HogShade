"""
HogShade: render the shader ball with the legacy v2 model under an E1 environment through the wgpu host, offscreen,
and write the verification PNGs (phase 2 plan, task 14).
Package: tools/wgpu/viewport

    uv run tools/wgpu/viewport.py                      # verification/wgpu/shader-ball/studio_small_09/{forward,deferred}.png
    uv run tools/wgpu/viewport.py --debug-mode 18      # the v2 specular accumulator
    uv run tools/wgpu/viewport.py --environment citrus_orchard_road_puresky --roughness 0.2 --metalness 1

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

from hogshade.ibl.imageio import preview_srgb8, write_png_rgb8
from hogshade.wgpu_host import Renderer, Scene, load_shader_ball, request_device

_MODULE_NAME = "tools.wgpu.viewport"
__version__ = "0.1.0"
__updated__ = "2026-09-27"


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
    ap.add_argument("--roughness", type=float, default=0.2)
    ap.add_argument("--metalness", type=float, default=0.0)
    ap.add_argument("--base-color", type=float, nargs=3, default=(0.5, 0.5, 0.5), metavar=("R", "G", "B"))
    ap.add_argument("--debug-mode", type=int, default=0, help="v2 g_DebugMode 0..32")
    ap.add_argument("--exposure-ev", type=float, default=0.0, help="display exposure for the PNG only")
    ap.add_argument("--hemisphere-mode", type=int, default=0, help="0 off, 1 add, 2 multiply")
    ap.add_argument("--model", default="legacy-v2", choices=("lambert", "legacy-v1", "legacy-v2"))
    for name in ("subsurface", "specular-tint", "anisotropic", "sheen", "sheen-tint", "clearcoat", "clearcoat-gloss"):
        ap.add_argument(f"--{name}", type=float, default=0.0, help="legacy v1 Disney lobe")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    adapter, device = request_device()
    info = adapter.info
    mesh = load_shader_ball()
    renderer = Renderer(device, mesh, environment=args.environment)
    scene = Scene(
        width=args.size,
        height=args.size,
        base_color=tuple(args.base_color),
        roughness=args.roughness,
        metalness=args.metalness,
        debug_mode=args.debug_mode,
        hemisphere_mode=args.hemisphere_mode,
        environment=args.environment,
        model=args.model,
        subsurface=args.subsurface,
        specular_tint=args.specular_tint,
        anisotropic=args.anisotropic,
        sheen=args.sheen,
        sheen_tint=args.sheen_tint,
        clearcoat=args.clearcoat,
        clearcoat_gloss=args.clearcoat_gloss,
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
    print(f"adapter: {info.get('device')} ({info.get('backend_type')}), GB3 {renderer.gb3_format}, model {args.model}")
    print(f"mesh: {len(mesh.vertices)} vertices, {len(mesh.indices) // 3} triangles; environment {args.environment}")
    print(
        f"ball covers {int(covered.sum())} of {covered.size} pixels; mean linear radiance {lit.mean():.4f}, max {lit.max():.4f}"
    )
    print(f"forward vs deferred over covered pixels: mean {mean_diff:.5f}, max {max_diff:.5f}")
    print(f"wrote {out} and {deferred_path} in {elapsed:.1f} s")
    finite = np.isfinite(frames.forward).all() and np.isfinite(frames.deferred).all()
    return 0 if covered.any() and finite else 1


if __name__ == "__main__":
    raise SystemExit(main())
