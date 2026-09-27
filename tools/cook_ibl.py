"""
HogShade: launcher for the IBL cook. The implementation lives in hogshade.ibl; see Docs/specs/e1-ibl-cook.md.
Package: tools/cook_ibl

    uv run tools/cook_ibl.py condition IN_8K.exr content/ibl/<name>/source_4k.exr
    uv run tools/cook_ibl.py cook content/ibl/<name>
    uv run tools/cook_ibl.py lut content/ibl/brdf_lut.dds
    uv run tools/cook_ibl.py furnace
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hogshade.ibl.cli import main

_MODULE_NAME = "tools.cook_ibl"
__version__ = "0.1.0"
__updated__ = "2026-09-27"

if __name__ == "__main__":
    sys.exit(main())
