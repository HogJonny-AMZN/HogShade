"""
HogShade: render the shader ball from a material document under an E1 environment through the wgpu host, offscreen,
and write the verification PNGs (phase 2 plan, task 14).
Package: tools/wgpu/viewport

    uv run tools/wgpu/viewport.py                      # verification/wgpu/shader-ball/<env>/{forward,deferred}.png
    uv run tools/wgpu/viewport.py --debug-mode 18      # the v2 specular accumulator
    uv run tools/wgpu/viewport.py --material content/materials/legacy-v1/default.material.json --variant legacy-v1
    uv run tools/wgpu/viewport.py --material content/materials/standard/rough/brick_wall_001.material.json \\
        --out-dir verification/wgpu/textures/brick_wall_001      # a textured document: its cooked set on the slots

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
from hogshade.material import bind, convert, load, resolve, runtime_textures
from hogshade.wgpu_host import MESHES, Renderer, Scene, load_mesh, request_device

_MODULE_NAME = "tools.wgpu.viewport"
_LOGGER = _logging.getLogger(_MODULE_NAME)
DEFAULT_MATERIAL = ROOT / "content" / "materials" / "legacy-v2" / "default.material.json"
__version__ = "0.1.0"
__updated__ = "2026-10-04"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="capture directory; default verification/wgpu/<mesh>/<env>[/<variant>] (<mesh> is --mesh)",
    )
    ap.add_argument("--variant", default="", help="sub-directory for a material variant, e.g. metal")
    ap.add_argument(
        "--mesh", default="shader-ball", choices=sorted(MESHES), help="what to draw (default the shader ball)"
    )
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
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    t0 = time.perf_counter()
    _LOGGER.info(
        "rendering %s under %s at %dx%d, debug mode %d",
        args.material,
        args.environment,
        args.size,
        args.size,
        args.debug_mode,
    )
    resolved = resolve(load(args.material))
    if resolved.material_type == "hogshade-standard":  # the host carries legacy v2; the reverse table gets us there
        converted, losses = convert(resolved, "hogshade-legacy-v2")
        resolved = resolve(converted)
        _LOGGER.info(
            f"standard document converted to legacy v2; the table drops "
            f"{', '.join(loss.parameter for loss in losses) or 'nothing'}"
        )
    binding = bind(resolved, "wgpu")
    textures = runtime_textures(binding.textures, Path(args.material).parent) if binding.textures else None
    if textures:
        _LOGGER.info(
            f"{len(textures)} texture(s) in their runtime form: "
            + ", ".join(f"{k} <- {v.path.name}[{v.channels}]" for k, v in textures.items())
        )
    _adapter, device = request_device()
    mesh = load_mesh(args.mesh)
    renderer = Renderer(device, mesh, environment=args.environment)
    scene = Scene(
        width=args.size,
        height=args.size,
        material=binding,
        debug_mode=args.debug_mode,
        hemisphere_mode=args.hemisphere_mode,
        environment=args.environment,
        textures=textures,
    )
    frames = renderer.render(scene)
    elapsed = time.perf_counter() - t0

    out_dir = args.out_dir or ROOT / "verification" / "wgpu" / args.mesh / args.environment
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
    _LOGGER.info(
        "GB3 %s, model %s; mesh %d vertices, %d triangles",
        renderer.gb3_format,
        binding.model,
        len(mesh.vertices),
        len(mesh.indices) // 3,
    )
    _LOGGER.info(
        "material %s (%s): %d parameter(s) the host does not carry: %s",
        args.material,
        binding.material_type,
        len(binding.unsupported),
        ", ".join(u.parameter for u in binding.unsupported) or "none",
    )
    print(
        f"ball covers {int(covered.sum())} of {covered.size} pixels; "
        f"mean linear radiance {lit.mean():.4f}, max {lit.max():.4f}"
    )
    print(f"forward vs deferred over covered pixels: mean {mean_diff:.5f}, max {max_diff:.5f}")
    _LOGGER.info("wrote %s and %s in %.1f s", out, deferred_path, elapsed)
    finite = np.isfinite(frames.forward).all() and np.isfinite(frames.deferred).all()
    return 0 if covered.any() and finite else 1


if __name__ == "__main__":
    raise SystemExit(main())
