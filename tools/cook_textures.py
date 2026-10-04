"""
HogShade: launcher for the texture cook. The implementation lives in hogshade.texture_cook; see
Docs/superpowers/specs/t2-texture-cook.md.
Package: tools/cook_textures

    uv run tools/cook_textures.py cook <set_dir> [--no-compress | --compress] [--bc7-profile basic] [--height normalise]
    uv run tools/cook_textures.py separate <set_dir> [--radius 16] [--macro 64] [--source _BC] [--picture DIR]
    uv run tools/cook_textures.py --check-setup

Compression is automatic when the encoder is installed (`uv sync --all-extras` brings ispc_texcomp); without it
the cook warns once with the command and writes uncompressed. `--compress` makes the encoder required (exit 2
without it); `--no-compress` writes uncompressed on purpose.
"""

from __future__ import annotations

import argparse
import json
import logging as _logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.texture_cook.cook import CookError, cook_set, separate_set
from hogshade.texture_cook.encoders import BC7_PROFILES, encoder_report

_MODULE_NAME = "tools.cook_textures"
__version__ = "0.1.0"
__updated__ = "2026-10-04"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check-setup", action="store_true", help="print the encoder found and the formats it writes")
    sub = parser.add_subparsers(dest="command")
    c = sub.add_parser("cook", help="the runtime set from an authoring set")
    c.add_argument("set_dir", type=Path)
    g = c.add_mutually_exclusive_group()
    g.add_argument("--compress", action="store_true", help="require the encoder; exit 2 without it")
    g.add_argument("--no-compress", action="store_true", help="write uncompressed DDS on purpose")
    c.add_argument("--bc7-profile", default="basic", choices=BC7_PROFILES)
    c.add_argument(
        "--height",
        choices=("keep", "normalise"),
        default="keep",
        help="keep the source's precision, or normalise a float height to R16_UNORM with its range recorded",
    )
    s = sub.add_parser("separate", help="the owner's frequency separation on one map of the set")
    s.add_argument("set_dir", type=Path)
    s.add_argument("--radius", type=float, default=16.0, help="the Gaussian radius; sigma = radius / 2")
    s.add_argument("--macro", type=int, default=64, help="the macro's longer side, in texels")
    s.add_argument("--source", default="_BC", help="the suffix to separate (_BC, or _N for the detail normal)")
    s.add_argument(
        "--picture",
        type=Path,
        default=None,
        help="write the source, halves and recombination as PNGs here (never under content/)",
    )
    s.add_argument("--no-compress", action="store_true")
    s.add_argument(
        "--picture-size", type=int, default=512, help="the pictures' longer side at most this (the gallery's rule)"
    )
    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.check_setup:
        report = encoder_report()
        print(json.dumps(report, indent=2))
        return 0 if report["encoder"] else 1
    if args.command is None:
        parser.print_help()
        return 2
    try:
        if args.command == "cook":
            compress = True if args.compress else (False if args.no_compress else None)
            result = cook_set(
                args.set_dir,
                compress=compress,
                bc7_profile=args.bc7_profile,
                height_normalise=args.height == "normalise",
            )
            print(
                json.dumps(
                    {k: v for k, v in result.manifest.items() if k in ("set", "compression", "textures")}, indent=2
                )
            )
            return 0
        sep = separate_set(
            args.set_dir,
            radius=args.radius,
            macro_size=args.macro,
            source_suffix=args.source,
            compress=False if args.no_compress else None,
            picture_dir=args.picture,
            picture_size=args.picture_size,
        )
        print(json.dumps(sep, indent=2))
        return 0
    except CookError as e:
        _LOGGER.error("texture cook: %s", e)
        return 2
    except (ValueError, OSError) as e:  # a defect or a disk problem past the checks: the two-part message, no traceback
        _LOGGER.error("texture cook failed on %s: %s: %s", args.set_dir, type(e).__name__, e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
