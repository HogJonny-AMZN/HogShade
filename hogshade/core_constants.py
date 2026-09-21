"""
HogShade: the Python mirror of core/constants.wgsl. A test parses the WGSL and checks these agree.
Package: hogshade/core_constants

Python tools (the cook, the references, the tests) read these; shaders read the WGSL. Change both
or the test fails, which is the point.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

_MODULE_NAME = "hogshade.core_constants"
__version__ = "0.1.0"
__updated__ = "2026-09-20"

PI = math.pi
INV_PI = 1.0 / math.pi
ROUGHNESS_BIAS = 0.005
IRRADIANCE_OVER_PI = 1.0
SH_A0 = math.pi
SH_A1 = 2.0 * math.pi / 3.0
SH_A2 = math.pi / 4.0
DIELECTRIC_F0 = 0.04

MODEL_LAMBERT = 0
MODEL_LEGACY_V1 = 1
MODEL_LEGACY_V2 = 2
MODEL_OPENPBR = 3

DEBUG_NONE = 0

# WGSL name -> Python value; the test walks this table
WGSL_NAMES = {
    "HOGSHADE_PI": PI,
    "HOGSHADE_INV_PI": INV_PI,
    "HOGSHADE_ROUGHNESS_BIAS": ROUGHNESS_BIAS,
    "HOGSHADE_IRRADIANCE_OVER_PI": IRRADIANCE_OVER_PI,
    "HOGSHADE_SH_A0": SH_A0,
    "HOGSHADE_SH_A1": SH_A1,
    "HOGSHADE_SH_A2": SH_A2,
    "HOGSHADE_DIELECTRIC_F0": DIELECTRIC_F0,
    "HOGSHADE_MODEL_LAMBERT": MODEL_LAMBERT,
    "HOGSHADE_MODEL_LEGACY_V1": MODEL_LEGACY_V1,
    "HOGSHADE_MODEL_LEGACY_V2": MODEL_LEGACY_V2,
    "HOGSHADE_MODEL_OPENPBR": MODEL_OPENPBR,
    "HOGSHADE_DEBUG_NONE": DEBUG_NONE,
}

_CONST = re.compile(r"^\s*const\s+([A-Z0-9_]+)\s*:\s*(f32|u32|i32)\s*=\s*([0-9.]+)u?\s*;", re.MULTILINE)


def parse_wgsl_constants(path: Path) -> dict[str, float | int]:
    """Read every top-level ``const NAME: type = literal;`` from a WGSL file."""
    text = path.read_text(encoding="utf-8")
    out: dict[str, float | int] = {}
    for name, typ, value in _CONST.findall(text):
        out[name] = float(value) if typ == "f32" else int(value)
    return out


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    parsed = parse_wgsl_constants(root / "core" / "constants.wgsl")
    for k, v in WGSL_NAMES.items():
        print(f"{k:32s} wgsl={parsed.get(k)!r:22} python={v!r}")
