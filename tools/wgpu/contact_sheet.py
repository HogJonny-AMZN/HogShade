"""
HogShade: render every standard document of the library through the reverse table and the wgpu host into one
contact sheet, the S4a human gate.
Package: tools/wgpu/contact_sheet

    uv run tools/wgpu/contact_sheet.py                 # verification/wgpu/library/contact-sheet.png and .json
    uv run tools/wgpu/contact_sheet.py --tile 128      # smaller tiles

Each document is resolved, converted to hogshade-legacy-v2 (the table lists what that loses, once), bound for
wgpu and rendered on the forward path under the calibration environment; the tiles are laid out in roster
order (families in the index's order, a family's parent first), five to a row. No text is drawn (no font
rasteriser in the repo): the JSON beside the picture is the legend, one entry per cell with its title and
document. The picture stays within the gallery's rule (at most 1024 on a side).
"""

from __future__ import annotations

import argparse
import json
import logging as _logging
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hogshade.ibl.imageio import preview_srgb8, write_png_rgb8
from hogshade.material import bind, convert, documents_under, load, resolve
from hogshade.material.library import family_of
from hogshade.wgpu_host import Renderer, Scene, load_shader_ball, request_device

_MODULE_NAME = "tools.wgpu.contact_sheet"
__version__ = "0.1.0"
__updated__ = "2026-10-03"
_LOGGER = _logging.getLogger(_MODULE_NAME)

LIBRARY = ROOT / "content" / "materials" / "standard"
OUT_DIR = ROOT / "verification" / "wgpu" / "library"
COLUMNS = 5
MAX_SIDE = 1024
TO_TYPE = "hogshade-legacy-v2"


def sheet_layout(count: int, tile: int, columns: int = COLUMNS) -> tuple[int, int]:
    """(width, height) in pixels of a grid of ``count`` tiles, ``columns`` to a row."""
    rows = -(-count // columns)
    return columns * tile, rows * tile


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", type=Path, default=LIBRARY, help="the standard documents' root")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--environment", default="studio_small_09")
    ap.add_argument("--tile", type=int, default=192, help="square tile size, a multiple of 32")
    ap.add_argument("--exposure-ev", type=float, default=0.0, help="display exposure for the PNG only")
    args = ap.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.tile % 32 or args.tile <= 0:
        _LOGGER.error("tile %d is not a positive multiple of 32", args.tile)
        return 2

    t0 = time.perf_counter()
    paths = documents_under(args.library)
    width, height = sheet_layout(len(paths), args.tile)
    if max(width, height) > MAX_SIDE:
        _LOGGER.error(
            "%d tiles of %d px make a %dx%d sheet, over the gallery's %d; use a smaller --tile",
            len(paths),
            args.tile,
            width,
            height,
            MAX_SIDE,
        )
        return 2
    _LOGGER.info(
        "rendering %d documents under %s at %d px tiles into a %dx%d sheet (%s)",
        len(paths),
        args.library,
        args.tile,
        width,
        height,
        args.environment,
    )

    _adapter, device = request_device()
    renderer = Renderer(device, load_shader_ball(), environment=args.environment)
    sheet = np.zeros((height, width, 3), dtype=np.float32)
    legend: list[dict] = []
    losses_logged = False
    for cell, path in enumerate(paths):
        doc = load(path, args.library)
        converted, losses = convert(resolve(doc, args.library), TO_TYPE)
        if not losses_logged:
            _LOGGER.info(
                "the %s table loses %s for every document",
                TO_TYPE,
                ", ".join(loss.parameter for loss in losses) or "nothing",
            )
            losses_logged = True
        binding = bind(resolve(converted), "wgpu")
        scene = Scene(width=args.tile, height=args.tile, material=binding, environment=args.environment)
        frame = renderer.render(scene).forward
        if not np.isfinite(frame).all():
            _LOGGER.error("%s rendered a non-finite pixel", path)
            return 1
        row, col = divmod(cell, COLUMNS)
        sheet[row * args.tile : (row + 1) * args.tile, col * args.tile : (col + 1) * args.tile] = frame
        rel = path.relative_to(args.library).as_posix()
        legend.append(
            {
                "cell": cell,
                "row": row,
                "column": col,
                "family": family_of(path, args.library),
                "document": rel,
                "title": doc.title,
            }
        )
        _LOGGER.info("cell %2d (row %d, column %d): %-28s %s", cell, row, col, doc.title, rel)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    picture = args.out_dir / "contact-sheet.png"
    write_png_rgb8(picture, preview_srgb8(sheet, args.exposure_ev))
    record = {
        "command": "uv run tools/wgpu/contact_sheet.py" + (f" --tile {args.tile}" if args.tile != 192 else ""),
        "environment": args.environment,
        "converted_to": TO_TYPE,
        "losses": [loss.parameter for loss in losses],
        "tile": args.tile,
        "columns": COLUMNS,
        "size": [width, height],
        "cells": legend,
    }
    (args.out_dir / "contact-sheet.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    _LOGGER.info(
        "wrote %s (%dx%d, %d cells) and its legend in %.1f s",
        picture,
        width,
        height,
        len(legend),
        time.perf_counter() - t0,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
