"""
HogShade: launcher for the IBL cook. The implementation lives in hogshade.ibl; see Docs/specs/e1-ibl-cook.md.
Package: tools/cook_ibl.py

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

if __name__ == "__main__":
    sys.exit(main())
