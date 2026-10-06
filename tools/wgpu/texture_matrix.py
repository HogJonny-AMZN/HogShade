"""
HogShade: render every committed texture set through the wgpu host from its cooked DDS, one picture per set beside
the Maya captures, for the gallery's matrix (T3b, the owner's layout row: sets as rows, hosts as columns).
Package: tools/wgpu/texture_matrix

    uv run tools/wgpu/texture_matrix.py                 # verification/wgpu/textures/<set>/main.png, matrix.json
    uv run tools/wgpu/texture_matrix.py --debug-modes 1,11,8   # debug-NN.png beside each main.png

The four standard documents that bind a set are converted to legacy v2 (the table's losses logged once) and bound
for wgpu; the calibration grid has no document, so one is built from its maps (``hogshade.material.sets``), as the
Maya check does. Every map the runtime reports is handed to the host; the ones the host has no slot for (height,
emission) are logged by the plan and left to their factors. The forward path is written; ``matrix.json`` is the
legend: per set, the document, the slots bound, the maps without a slot and the command.
"""

from __future__ import annotations

import argparse
import json
import logging as _logging
import shlex
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hogshade.ibl.imageio import preview_srgb8, write_png_rgb8
from hogshade.material import MaterialError, bind, convert, load, resolve, runtime_textures
from hogshade.material.runtime import RuntimeTexture
from hogshade.material.sets import document_for_set
from hogshade.wgpu_host import MESHES, Renderer, Scene, load_mesh, request_device
from hogshade.wgpu_textures import PARAMETER_SLOT, TextureError

_MODULE_NAME = "tools.wgpu.texture_matrix"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

LIBRARY = ROOT / "content" / "materials" / "standard"
OUT_DIR = ROOT / "verification" / "wgpu" / "textures"
TO_TYPE = "hogshade-legacy-v2"
#: The sets in the gallery's row order: name, the document (None builds one from the set), the set directory.
SETS: tuple[tuple[str, Path | None, Path], ...] = (
    ("cobblestone_floor_04", LIBRARY / "rough" / "cobblestone_floor_04.material.json", LIBRARY / "rough"),
    ("brick_wall_001", LIBRARY / "rough" / "brick_wall_001.material.json", LIBRARY / "rough"),
    ("brown_planks_03", LIBRARY / "dielectric" / "brown_planks_03.material.json", LIBRARY / "dielectric"),
    ("metal_plate", LIBRARY / "metal" / "metal_plate.material.json", LIBRARY / "metal"),
    ("grid", None, ROOT / "content" / "textures" / "grid"),
    ("synthetic", None, ROOT / "content" / "textures" / "synthetic"),
)


def prepare(name: str, document: Path | None, where: Path) -> tuple[Any, dict[str, RuntimeTexture], list[str]]:
    """The wgpu binding, the runtime textures and the table's losses for one set; ``MaterialError`` on any fault."""
    if document is not None:
        doc = load(document, LIBRARY)
        resolved = resolve(doc, LIBRARY)
        doc_dir = document.parent
    else:
        doc = document_for_set(where)
        resolved = resolve(doc)
        doc_dir = doc.root
    converted, losses = convert(resolved, TO_TYPE)
    binding = bind(resolve(converted), "wgpu")
    textures = runtime_textures(binding.textures, doc_dir)
    _LOGGER.info(
        f"{name}: {document.name if document else 'a document from the set'} bound with {len(textures)} map(s): "
        + ", ".join(f"{k} <- {v.path.name}[{v.channels}]" for k, v in textures.items())
    )
    return binding, textures, [loss.parameter for loss in losses]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR, help="<out-dir>/<set>/main.png")
    ap.add_argument("--environment", default="studio_small_09")
    ap.add_argument(
        "--mesh",
        default="shader-ball",
        choices=sorted(MESHES),
        help="what to draw; another mesh writes under <out-dir>/<mesh>/, leaving the shader ball pictures alone",
    )
    ap.add_argument("--size", type=int, default=512, help="square output, a multiple of 32, at most 1024")
    ap.add_argument("--debug-modes", default="", help="comma-separated v2 debug modes, each a debug-NN.png")
    ap.add_argument("--exposure-ev", type=float, default=0.0, help="display exposure for the PNG only")
    ap.add_argument("--only", default="", help="comma-separated set names; default every set")
    args = ap.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.size % 32 or not 0 < args.size <= 1024:
        _LOGGER.error(f"size {args.size} is not a multiple of 32 within the gallery's 1024")
        return 2
    modes = [int(m) for m in args.debug_modes.split(",") if m.strip()]
    chosen = [s for s in SETS if not args.only or s[0] in args.only.split(",")]
    if not chosen:
        _LOGGER.error(f"--only {args.only!r} names none of {[s[0] for s in SETS]}")
        return 2

    t0 = time.perf_counter()
    try:
        prepared = [(name, where, *prepare(name, document, where)) for name, document, where in chosen]
    except MaterialError as e:
        _LOGGER.error(f"texture matrix: {e}")
        return 2
    _adapter, device = request_device()
    renderer = Renderer(device, load_mesh(args.mesh), environment=args.environment)
    root = args.out_dir if args.mesh == "shader-ball" else args.out_dir / args.mesh  # another mesh never overwrites
    legend: dict[str, Any] = {
        "command": "uv run tools/wgpu/texture_matrix.py "
        + " ".join(shlex.quote(a) for a in (sys.argv[1:] if argv is None else argv)),
        "mesh": args.mesh,
        "environment": args.environment,
        "size": args.size,
        "converted_to": TO_TYPE,
        "sets": {},
    }
    for name, where, binding, textures, losses in prepared:
        out = root / name
        out.mkdir(parents=True, exist_ok=True)
        scene = Scene(
            width=args.size, height=args.size, material=binding, environment=args.environment, textures=textures
        )
        try:
            plan = scene.plan()
            frames = renderer.render(scene)
        except TextureError as e:
            _LOGGER.error(f"{name}: {e}")
            return 1
        if not np.isfinite(frames.forward).all():
            _LOGGER.error(f"{name} rendered a non-finite pixel")
            return 1
        write_png_rgb8(out / "main.png", preview_srgb8(frames.forward, args.exposure_ev))
        for mode in modes:
            debug = renderer.render(
                Scene(
                    width=args.size,
                    height=args.size,
                    material=binding,
                    environment=args.environment,
                    textures=textures,
                    debug_mode=mode,
                )
            ).forward
            write_png_rgb8(out / f"debug-{mode:02d}.png", preview_srgb8(debug, args.exposure_ev))
        mean_diff, max_diff = frames.difference()
        unslotted = sorted(p for p in textures if p not in PARAMETER_SLOT)
        legend["sets"][name] = {
            "set": where.relative_to(ROOT).as_posix() if where.is_relative_to(ROOT) else str(where),
            "slots": sorted(plan.sources),
            "bound": sorted(p for p in textures if p not in unslotted),
            "without_a_slot": unslotted,
            "losses": losses,
            "forward_vs_deferred": {"mean": round(float(mean_diff), 6), "max": round(float(max_diff), 6)},
        }
        _LOGGER.info(
            f"{name}: slots {', '.join(sorted(plan.sources))}; without a slot: {', '.join(unslotted) or 'none'}; "
            f"forward vs deferred mean {mean_diff:.5f}, max {max_diff:.5f}; wrote {out / 'main.png'}"
        )
    root.mkdir(parents=True, exist_ok=True)
    (root / "matrix.json").write_text(json.dumps(legend, indent=2) + "\n", encoding="utf-8", newline="\n")
    _LOGGER.info(f"{len(prepared)} set(s) rendered in {time.perf_counter() - t0:.1f} s; legend {root / 'matrix.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
