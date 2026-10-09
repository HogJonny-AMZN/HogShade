"""
HogShade: render every standard document of the library through the reverse table and the wgpu host into one
contact sheet, the S4a human gate.
Package: tools/wgpu/contact_sheet

    uv run tools/wgpu/contact_sheet.py                 # verification/wgpu/library/contact-sheet.png and .json
    uv run tools/wgpu/contact_sheet.py --tile 128      # smaller tiles

Each document is resolved, converted to hogshade-legacy-v2 (the table lists what that loses, once), bound for
wgpu with its textures in their runtime form (T3b: a document that binds a set renders its cooked DDS; the others
render their constants on neutral slots) and rendered on the forward path under the calibration environment;
the tiles are laid out in roster order (families in the index's order, a family's parent first), six to a row,
each with a label strip under it
naming the family and the document's title (``hogshade.bitmap_font``; the owner, 2026-10-04: "they need
context"). The JSON beside the picture is the legend, one entry per cell with its title and document. The
picture stays within the gallery's rule (at most 1024 on a side).
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

from hogshade.bitmap_font import draw_text, fit
from hogshade.ibl.imageio import preview_srgb8, write_png_rgb8
from hogshade.material import (
    MaterialError,
    bind,
    convert,
    documents_under,
    load,
    load_table,
    resolve,
    runtime_textures,
)
from hogshade.material.library import family_of
from hogshade.material.runtime import RuntimeTexture
from hogshade.wgpu_host import Renderer, Scene, load_shader_ball, request_device

_MODULE_NAME = "tools.wgpu.contact_sheet"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

LIBRARY = ROOT / "content" / "materials" / "standard"
OUT_DIR = ROOT / "verification" / "wgpu" / "library"
COLUMNS = 6
MAX_SIDE = 1024
TO_TYPE = "hogshade-legacy-v2"
#: The label strip under each tile: the family on a small line, the title on a larger one, three pixels of air
#: around each (7-row glyphs: 7 at scale 1, 14 at scale 2).
FAMILY_SCALE, TITLE_SCALE = 1, 2
LABEL_PAD, LABEL_INSET = 3, 2  # air above, between and below the lines; the left inset
LABEL_H = LABEL_PAD + 7 * FAMILY_SCALE + LABEL_PAD + 7 * TITLE_SCALE + LABEL_PAD
LABEL_GREY = 0.02  # the strip's ground, linear; near black so the text reads on any tile
FAMILY_GREY = (0.6, 0.6, 0.6)  # the family line, quieter than the title


def sheet_layout(count: int, tile: int, columns: int = COLUMNS, label: int = LABEL_H) -> tuple[int, int]:
    """
    (width, height) in pixels of a grid of ``count`` tiles, ``columns`` to a row, each tile with a ``label``
    strip under it; ``count`` is at least 1.
    """
    if count < 1:
        raise ValueError("a sheet needs at least one tile")
    rows = -(-count // columns)
    return columns * tile, rows * (tile + label)


def label_for(family: str, title: str | None, width: int) -> tuple[str, str]:
    """The strip's two lines, each cut to the tile's width with a trailing dot when it does not fit."""
    room = width - 2 * LABEL_INSET
    return fit(family, room, FAMILY_SCALE), fit(title or "?", room, TITLE_SCALE)


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


def prepare(
    library: Path, to_type: str = TO_TYPE
) -> tuple[list[tuple[Path, Any, Any, dict[str, RuntimeTexture]]], list[str]]:
    """
    Every document under ``library`` loaded, converted to ``to_type`` and bound for wgpu, with its runtime textures
    (empty for a constants-only document) and the table's losses, before any device exists: ``(path, document,
    binding, textures)`` and the lost parameter names. A malformed document, chain, table, binding or cooked set
    is ``MaterialError`` here, where the tool can log it and exit.
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
        binding = bind(resolve(converted), "wgpu")
        textures = runtime_textures(binding.textures, path.parent) if binding.textures else {}
        prepared.append((path, doc, binding, textures))
    return prepared, losses


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", type=Path, default=LIBRARY, help="the standard documents' root")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--environment", default="studio_small_09")
    ap.add_argument("--tile", type=int, default=160, help="square tile size, a multiple of 32")
    ap.add_argument("--exposure-ev", type=float, default=0.0, help="display exposure for the PNG only")
    args = ap.parse_args(argv)
    defaults = ap.parse_args([])
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.tile % 32 or args.tile <= 0:
        _LOGGER.error(f"tile {args.tile} is not a positive multiple of 32")
        return 2

    t0 = time.perf_counter()
    try:
        prepared, losses = prepare(args.library)
    except MaterialError as e:
        _LOGGER.error(f"contact sheet: {e}")
        return 2
    lost = ", ".join(losses) or "nothing"
    _LOGGER.info(f"the {prepared[0][1].material_type} to {TO_TYPE} table loses {lost} for every document")
    width, height = sheet_layout(len(prepared), args.tile)
    if max(width, height) > MAX_SIDE:
        _LOGGER.error(
            f"{len(prepared)} tiles of {args.tile} px make a {width}x{height} sheet, "
            f"over the gallery's {MAX_SIDE}; use a smaller --tile"
        )
        return 2
    _LOGGER.info(
        f"rendering {len(prepared)} documents under {args.library} at {args.tile} px tiles "
        f"into a {width}x{height} sheet ({args.environment})"
    )

    _adapter, device = request_device()
    renderer = Renderer(device, load_shader_ball(), environment=args.environment)
    sheet = np.zeros((height, width, 3), dtype=np.float32)
    legend: list[dict[str, Any]] = []
    for cell, (path, doc, binding, textures) in enumerate(prepared):
        scene = Scene(
            width=args.tile, height=args.tile, material=binding, environment=args.environment, textures=textures
        )
        frame = renderer.render(scene).forward
        if not np.isfinite(frame).all():
            _LOGGER.error(f"{path} rendered a non-finite pixel")
            return 1
        row, col = divmod(cell, COLUMNS)
        y0, x0 = row * (args.tile + LABEL_H), col * args.tile
        sheet[y0 : y0 + args.tile, x0 : x0 + args.tile] = frame
        sheet[y0 + args.tile : y0 + args.tile + LABEL_H, x0 : x0 + args.tile] = LABEL_GREY
        rel = path.relative_to(args.library).as_posix()
        family = family_of(path, args.library)
        line1, line2 = label_for(family, doc.title, args.tile)
        y_family = y0 + args.tile + LABEL_PAD
        y_title = y_family + 7 * FAMILY_SCALE + LABEL_PAD
        draw_text(sheet, line1, x0 + LABEL_INSET, y_family, FAMILY_SCALE, FAMILY_GREY)
        draw_text(sheet, line2, x0 + LABEL_INSET, y_title, TITLE_SCALE)
        legend.append(
            {
                "cell": cell,
                "row": row,
                "column": col,
                "family": family,
                "document": rel,
                "title": doc.title,
                "textures": sorted(textures),
            }
        )
        _LOGGER.info(
            f"cell {cell:2d} (row {row}, column {col}): {doc.title:<28} {rel}"
            + (f" ({len(textures)} map(s))" if textures else "")
        )

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
        f"wrote {picture} ({width}x{height}, {len(legend)} cells) and its legend in {time.perf_counter() - t0:.1f} s",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
