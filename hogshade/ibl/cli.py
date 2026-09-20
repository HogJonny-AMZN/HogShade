"""
HogShade: command line for the IBL cook. ``tools/cook_ibl.py`` is a thin launcher for this.
Package: hogshade/ibl/cli
"""

from __future__ import annotations

import argparse
import json
import logging as _logging
import sys
from pathlib import Path

_MODULE_NAME = "hogshade.ibl.cli"
__version__ = "0.1.0"
__updated__ = "2026-09-20"
_LOGGER = _logging.getLogger(_MODULE_NAME)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cook_ibl", description="HogShade IBL cook (Docs/specs/e1-ibl-cook.md)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("condition", help="8K master -> 4096x2048 half-float source_4k.exr")
    p.add_argument("src", type=Path)
    p.add_argument("dst", type=Path)

    p = sub.add_parser("cook", help="environment dir with source_4k.exr -> cooked/")
    p.add_argument("env_dir", type=Path)
    p.add_argument("--base", type=int, default=256)
    p.add_argument("--samples", type=int, default=1024)

    p = sub.add_parser("lut", help="write the split-sum BRDF LUT")
    p.add_argument("dst", type=Path)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--samples", type=int, default=1024)

    p = sub.add_parser("furnace", help="white-environment energy check")
    p.add_argument("--base", type=int, default=32)
    p.add_argument("--samples", type=int, default=256)

    args = parser.parse_args(argv)
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")

    from hogshade.ibl import cook

    if args.cmd == "condition":
        print(json.dumps(cook.condition(args.src, args.dst), indent=2))
        return 0
    if args.cmd == "cook":
        print(json.dumps(cook.cook_environment(args.env_dir, base=args.base, samples=args.samples), indent=2))
        return 0
    if args.cmd == "lut":
        print(cook.cook_lut(args.dst, size=args.size, samples=args.samples))
        return 0
    if args.cmd == "furnace":
        report = cook.furnace(base=args.base, samples=args.samples)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
