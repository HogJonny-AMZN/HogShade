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
import shlex
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hogshade.ibl.imageio import preview_srgb8, write_png_rgb8
from hogshade.material import MaterialError, bind, convert, documents_under, load, load_table, resolve
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
    """(width, height) in pixels of a grid of ``count`` tiles, ``columns`` to a row; ``count`` is at least 1."""
    if count < 1:
        raise ValueError("a sheet needs at least one tile")
    rows = -(-count // columns)
    return columns * tile, rows * tile


def command_line(args: argparse.Namespace, defaults: argparse.Namespace) -> str:
    """
    The invocation that reproduces this run: the tool plus every argument that differs from its default, as
    an argv list quoted for a POSIX shell (``shlex.join``), so a path with a space or a metacharacter survives.
    """
    argv = ["uv", "run", "tools/wgpu/contact_sheet.py"]
    for name in ("library", "out_dir", "environment", "tile", "exposure_ev"):
        value, default = getattr(args, name), getattr(defaults, name)
        if value != default:
            shown = value.relative_to(ROOT).as_posix() if isinstance(value, Path) and ROOT in value.parents else value
            argv += [f"--{name.replace('_', '-')}", str(shown)]
    return shlex.join(argv)


def prepare(library: Path, to_type: str = TO_TYPE) -> tuple[list[tuple[Path, Any, Any]], list[str]]:
    """
    Every document under ``library`` loaded, converted to ``to_type`` and bound for wgpu, with the table's
    losses, before any device exists: ``(path, document, binding)`` triples and the lost parameter names. A
    malformed document, chain, table or binding is ``MaterialError`` here, where the tool can log it and exit.
    """
    paths = documents_under(library)
    if not paths:
        raise MaterialError(f"no *.material.json under {library}; nothing to render")
    first = load(paths[0], library)
    losses = [d["from"] for d in load_table(first.material_type, to_type)["dropped"]]
    prepared = []
    for path in paths:
        doc = load(path, library)
        converted, _ = convert(resolve(doc, library), to_type)
        prepared.append((path, doc, bind(resolve(converted), "wgpu")))
    return prepared, losses


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", type=Path, default=LIBRARY, help="the standard documents' root")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--environment", default="studio_small_09")
    ap.add_argument("--tile", type=int, default=192, help="square tile size, a multiple of 32")
    ap.add_argument("--exposure-ev", type=float, default=0.0, help="display exposure for the PNG only")
    args = ap.parse_args(argv)
    defaults = ap.parse_args([])
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.tile % 32 or args.tile <= 0:
        _LOGGER.error("tile %d is not a positive multiple of 32", args.tile)
        return 2

    t0 = time.perf_counter()
    try:
        prepared, losses = prepare(args.library)
    except MaterialError as e:
        _LOGGER.error("contact sheet: %s", e)
        return 2
    _LOGGER.info(
        "the %s to %s table loses %s for every document",
        prepared[0][1].material_type,
        TO_TYPE,
        ", ".join(losses) or "nothing",
    )
    width, height = sheet_layout(len(prepared), args.tile)
    if max(width, height) > MAX_SIDE:
        _LOGGER.error(
            "%d tiles of %d px make a %dx%d sheet, over the gallery's %d; use a smaller --tile",
            len(prepared),
            args.tile,
            width,
            height,
            MAX_SIDE,
        )
        return 2
    _LOGGER.info(
        "rendering %d documents under %s at %d px tiles into a %dx%d sheet (%s)",
        len(prepared),
        args.library,
        args.tile,
        width,
        height,
        args.environment,
    )

    _adapter, device = request_device()
    renderer = Renderer(device, load_shader_ball(), environment=args.environment)
    sheet = np.zeros((height, width, 3), dtype=np.float32)
    legend: list[dict[str, Any]] = []
    for cell, (path, doc, binding) in enumerate(prepared):
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
        "command": command_line(args, defaults),
        "environment": args.environment,
        "converted_to": TO_TYPE,
        "losses": losses,
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
