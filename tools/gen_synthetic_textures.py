"""
HogShade: launcher for the synthetic texture set (T4 tier 1). The implementation lives in
hogshade.testdata.synthetic; see Docs/superpowers/specs/t4-procedural-set.md.
Package: tools/gen_synthetic_textures

    uv run tools/gen_synthetic_textures.py                       # content/textures/synthetic, 512
    uv run tools/gen_synthetic_textures.py --size 1024 --out some/dir
    uv run tools/gen_synthetic_textures.py --sheet verification/wgpu/textures/synthetic/maps.png   # the gallery picture
    uv run tools/cook_textures.py cook content/textures/synthetic --compress   # then cook it
"""

from __future__ import annotations

import argparse
import logging as _logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.testdata import synthetic

_MODULE_NAME = "tools.gen_synthetic_textures"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)

DEFAULT_OUT = ROOT / "content" / "textures" / "synthetic"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None, help=f"the set directory to write (default {DEFAULT_OUT})")
    ap.add_argument("--size", type=int, default=None, help="a power of two from 128 to 2048 (default 512)")
    ap.add_argument(
        "--sheet",
        type=Path,
        default=None,
        help="write only the contact sheet PNG of every map (the gallery's picture), not the set",
    )
    args = ap.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.sheet is not None:
        if args.out is not None or args.size is not None:
            ap.error("--sheet writes the contact sheet only; it takes neither --out nor --size")
        from hogshade.texture_cook import png

        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        png.write_png(args.sheet, synthetic.contact_sheet())
        _LOGGER.info(f"wrote the contact sheet of {len(synthetic.SPECS)} map(s) to {args.sheet}")
        return 0
    out, size = args.out or DEFAULT_OUT, args.size or synthetic.SIZE
    try:
        written = synthetic.generate(out, size)
    except synthetic.SyntheticError as e:
        _LOGGER.error(f"synthetic set: {e}")
        return 2
    _LOGGER.info(f"{len(written)} file(s) written under {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
