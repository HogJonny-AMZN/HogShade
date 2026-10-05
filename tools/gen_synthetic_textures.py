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
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the set directory to write")
    ap.add_argument("--size", type=int, default=synthetic.SIZE, help="a power of two from 64 to 2048")
    ap.add_argument(
        "--sheet",
        type=Path,
        default=None,
        help="write only the contact sheet PNG of every map (the gallery's picture), not the set",
    )
    args = ap.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.sheet is not None:
        from hogshade.texture_cook import png

        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        png.write_png(args.sheet, synthetic.contact_sheet())
        _LOGGER.info(f"wrote the contact sheet of {len(synthetic.SPECS)} map(s) to {args.sheet}")
        return 0
    try:
        written = synthetic.generate(args.out, args.size)
    except synthetic.SyntheticError as e:
        _LOGGER.error(f"synthetic set: {e}")
        return 2
    _LOGGER.info(f"{len(written)} file(s) written under {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
